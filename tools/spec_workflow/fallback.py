"""The local zero-cost fallback of a headless agent step (#23, ADR-0014).

When the operator opted in for a run (`ballast run start|resume
--local-fallback MODEL`), a headless step whose first primary attempt failed
on quota, provider availability or a missing CLI, and changed nothing, may run
once more on `codex exec --oss --local-provider ollama` against the operator's
Ollama model at its fixed loopback endpoint. This module holds what the
wrapper (agent.py) and the launcher (run.py) need for that:

- the operator setting `fallback.json` in the run's operator directory;
- the normalized cause of a failed attempt (`classify`);
- the worktree state evidence (`state_evidence`);
- the eligibility probes, which refuse before any prompt is sent (`probe`);
- the fallback argv and environment, and their exact comparison;
- the `codex exec --json` event parser and the ledger records.

Every check that cannot be established refuses. Nothing here sends a prompt
or repository content; the probes send only the model name to loopback. It
uses only the standard library and runs under `python3 -I -S`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

# Never read or write checkout bytecode, including for the imports below.
sys.pycache_prefix = os.devnull

import autonomy  # noqa: E402
import ledger  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterable

VERSION = 1
PROVIDER = "ollama"
SETTING_FILE = "fallback.json"
SETTING_FIELDS = {
    "version",
    "enabled",
    "provider",
    "model",
    "digest",
    "set_at",
    "set_by",
}
# Ollama's default endpoint, the one `codex --oss` uses without an override
# (DEC-0003). There is no endpoint option: probes and Codex use the same one.
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
MIN_OLLAMA_VERSION = (0, 13, 4)
MIN_SERVED_CONTEXT = 16384
ENDPOINT_VARIABLES = ("CODEX_OSS_BASE_URL", "CODEX_OSS_PORT", "OLLAMA_HOST")
# Codex reaches github.com and chatgpt.com at start-up even with a local
# provider and an empty home (live check, SEC-001). The operator's proxy
# variables are removed (a proxy would carry the prompt off the machine) and
# every proxy-aware request is sent to a closed local port instead; only
# loopback, where Ollama listens, bypasses it. Not a network boundary (a
# process can ignore the variables); tool processes have no network in Codex's
# sandbox, and no content is sent to these hosts by the model request itself.
PROXY_VARIABLES = frozenset(
    {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY", "NO_PROXY"}
)
BLACKHOLE_PROXY = "http://127.0.0.1:9"
BLACKHOLE = {
    name: value
    for upper, value in (
        ("HTTP_PROXY", BLACKHOLE_PROXY),
        ("HTTPS_PROXY", BLACKHOLE_PROXY),
        ("ALL_PROXY", BLACKHOLE_PROXY),
        ("NO_PROXY", "127.0.0.1,localhost,::1"),
    )
    for name in (upper, upper.lower())
}
PROBE_SECONDS = 10.0
REQUEST_SECONDS = 5.0
RESPONSE_LIMIT = 1024 * 1024
TAIL_BYTES = 64 * 1024
# Human-gated fallback timeout; an Autonomous one has the remaining wall time.
HUMAN_GATED_SECONDS = 3600.0
# Codex's system configuration layers (pilot item 5); any file here refuses.
CODEX_SYSTEM_DIR = Path("/etc/codex")
MODEL_HINT = "--local-fallback needs a local model name such as qwen3:4b"

# Same values as agent.EXIT_* (a test keeps them equal).
EXIT_BLOCKED = 3
EXIT_TAMPERED = 4
EXIT_LIMIT = 5
EXIT_AUTH = 6
EXIT_INTERRUPTED = 130

QUOTA = "quota-exhausted"
UNAVAILABLE = "provider-unavailable"
CLI_MISSING = "cli-unavailable"
UNRECOGNIZED = "unrecognized"
RECOVERABLE = frozenset({QUOTA, UNAVAILABLE, CLI_MISSING})

CHANGED = "changed-state"
PRIVACY = "privacy-exclusion"
UNKNOWN_FREE = "unknown-free-status"
CAPABILITY = "incompatible-capability"
PERMISSION = "permission-mismatch"
REASONS = (UNKNOWN_FREE, PRIVACY, CAPABILITY, PERMISSION, CHANGED)

# Per-integration signatures of a recoverable failure, matched only against
# the last TAIL_BYTES of the attempt's output (research R2, evaluation.md
# item 8). The messages are the CLIs' own, never account details. Codex
# writes a typographic apostrophe (U+2019), Claude an ASCII one.
APOSTROPHE = "['" + chr(0x2019) + "]"
SIGNATURES = {
    "claude": (
        (
            QUOTA,
            re.compile(
                f"You{APOSTROPHE}ve hit your (?:monthly spend )?limit"
                "|usage limit reached"
                r"|Credit balance is too low|Request rejected \(429\)",
                re.IGNORECASE,
            ),
        ),
        (
            UNAVAILABLE,
            re.compile(
                r"API Error: 5\d\d\b|Connection error\.|Request timed out"
                r"|Unable to connect to API|overloaded_error",
                re.IGNORECASE,
            ),
        ),
    ),
    "codex": (
        (
            QUOTA,
            re.compile(
                f"You{APOSTROPHE}ve hit your usage limit"
                r"|Quota exceeded\. Check your plan"
                r"|usage_limit_reached",
                re.IGNORECASE,
            ),
        ),
        (
            UNAVAILABLE,
            re.compile(
                r"unexpected status 5\d\d\b|stream disconnected before completion"
                r"|exceeded retry limit, last status|Connection failed:",
                re.IGNORECASE,
            ),
        ),
    ),
}
NUM_CTX = re.compile(r"^\s*num_ctx\s+(\S+)\s*$", re.MULTILINE)
VERSION_TEXT = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class SettingError(ValueError):
    """An invalid fallback setting; it counts as off."""


class EventError(ValueError):
    """A `codex exec --json` stream that cannot be parsed."""


@dataclass(frozen=True)
class Setting:
    """The operator's fallback setting for one run."""

    model: str
    provider: str = PROVIDER
    digest: str | None = None  # the model's /api/tags digest at opt-in (SEC2-002)


class Refused(NamedTuple):
    """A fallback refusal: one fixed reason and a fixed detail phrase."""

    reason: str
    detail: str


@dataclass
class Events:
    """What a `codex exec --json` stream reported."""

    text: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    complete: bool


# --- Setting -------------------------------------------------------------------


def is_cloud(model: str) -> bool:
    """Whether a model name carries Ollama's `cloud` tag (`:cloud`, `-cloud`)."""
    return any(
        part == "cloud" or part.endswith("-cloud") for part in model.lower().split(":")
    )


def validate_model(text: object) -> str:
    """Return a valid local model name, or raise SettingError with the fixed message."""
    if (
        not isinstance(text, str)
        or text.startswith("-")
        or not ledger.MODEL.fullmatch(text)
    ):
        raise SettingError(MODEL_HINT)
    if is_cloud(text):
        message = (
            f"--local-fallback refuses cloud model {text}: content would leave "
            "this machine"
        )
        raise SettingError(message)
    return text


def setting_path(root: Path, run_id: str) -> Path:
    """`fallback.json` in the run's operator directory (no agent can write it)."""
    return autonomy.run_dir(root, run_id) / SETTING_FILE


def served_digest(model: str) -> str | None:
    """Return the digest Ollama serves `model` under now, or None if unknown."""
    try:
        models = _request(_Budget(PROBE_SECONDS), "/api/tags").get("models")
        digest = next(
            item.get("digest")
            for item in models or []
            if isinstance(item, dict) and model in {item.get("name"), item.get("model")}
        )
    except (OSError, ValueError, StopIteration, _ExpiredError):
        return None
    return digest if isinstance(digest, str) and digest else None


def write_setting(
    root: Path, run_id: str, model: str | None, digest: str | None = None
) -> Setting | None:
    """Write the operator's setting, mode 0600; `None` turns the fallback off.

    `digest` pins the model's identity: the probes refuse a model served under
    another digest (SEC2-002).
    """
    if model is not None:
        validate_model(model)
    data = {
        "version": VERSION,
        "enabled": model is not None,
        "provider": PROVIDER,
        "model": model,
        "digest": digest,
        "set_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "set_by": "operator",
    }
    if model is None:
        # Off keeps the file, and the model it turned off, so the record shows it.
        try:
            previous = _read(setting_path(root, run_id))
            kept = previous.get("model") if isinstance(previous, dict) else None
            data["model"] = validate_model(kept)
        except SettingError:
            del data["model"]
        del data["digest"]
    autonomy.write_json(setting_path(root, run_id), data)
    return Setting(model, digest=digest) if model is not None else None


def _read(path: Path) -> object:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as error:
        message = f"local fallback setting is unreadable: {error.strerror}"
        raise SettingError(message) from error
    with os.fdopen(fd, "rb") as handle:
        data = handle.read(RESPONSE_LIMIT + 1)
    if len(data) > RESPONSE_LIMIT:
        message = "local fallback setting is too large"
        raise SettingError(message)
    try:
        return json.loads(data)
    except ValueError as error:
        message = "local fallback setting is not valid JSON"
        raise SettingError(message) from error


def read_setting(root: Path, run_id: str) -> Setting | None:
    """Return the run's setting; None when absent or off, SettingError if invalid."""
    try:
        path = setting_path(root, run_id)
    except autonomy.AutonomyError as error:
        raise SettingError(str(error)) from error
    if not os.path.lexists(path):
        return None
    data = _read(path)
    if not isinstance(data, dict):
        message = "local fallback setting must be a JSON object"
        raise SettingError(message)
    allowed = SETTING_FIELDS
    required = SETTING_FIELDS - (
        {"model", "digest"} if data.get("enabled") is False else set()
    )
    if not required <= set(data) <= allowed:
        message = "local fallback setting has missing or unknown fields"
        raise SettingError(message)
    if (
        data["version"] != VERSION
        or type(data["enabled"]) is not bool
        or data["provider"] != PROVIDER
        or data["set_by"] != "operator"
        or not isinstance(data["set_at"], str)
    ):
        message = "local fallback setting has an invalid field"
        raise SettingError(message)
    try:
        datetime.fromisoformat(data["set_at"])
    except ValueError as error:
        message = "local fallback setting has an invalid set_at"
        raise SettingError(message) from error
    if "model" in data:
        validate_model(data["model"])
    if not isinstance(data.get("digest"), str | None):
        message = "local fallback setting has an invalid digest"
        raise SettingError(message)
    if not data["enabled"]:
        return None
    return Setting(data["model"], digest=data.get("digest"))


def describe(root: Path, run_id: str) -> str | None:
    """`on (ollama MODEL)` or `off`; None when the operator never set one.

    An invalid setting counts as off, as the wrapper treats it.
    """
    try:
        if not os.path.lexists(setting_path(root, run_id)):
            return None
        setting = read_setting(root, run_id)
    except (SettingError, autonomy.AutonomyError, OSError):
        return "off"
    return f"on ({PROVIDER} {setting.model})" if setting else "off"


# --- Cause ---------------------------------------------------------------------


def classify(  # noqa: PLR0911, PLR0913 - one ordered decision table
    integration: str,
    exit_code: int,
    blocked: bool,  # noqa: FBT001 - the attempt's own observation
    contained: bool,  # noqa: FBT001 - the attempt's own observation
    tail: bytes | tuple[bytes, ...],
    *,
    cli_found: bool,
) -> str:
    """Return the normalized cause of one finished primary attempt (data-model.md).

    Reserved wrapper codes and the blocking status come first; only then is
    the last TAIL_BYTES of each output stream (stdout, stderr) matched against
    the integration's signatures. Anything unmatched is `unrecognized`, which
    never falls back.
    """
    if not cli_found:
        return CLI_MISSING
    if blocked or exit_code == EXIT_BLOCKED:
        return "blocked"
    if exit_code == 0:
        return "success"
    if exit_code == EXIT_TAMPERED or not contained:
        return "tampered"
    if exit_code == EXIT_LIMIT:
        return "limit"
    if exit_code == EXIT_INTERRUPTED:
        return "interrupted"
    if exit_code == EXIT_AUTH:
        return "auth"
    streams = tail if isinstance(tail, tuple) else (tail,)
    text = "\n".join(s[-TAIL_BYTES:].decode("utf-8", "replace") for s in streams)
    for cause, pattern in SIGNATURES.get(integration, ()):
        if pattern.search(text):
            return cause
    return UNRECOGNIZED


# --- Worktree state evidence -----------------------------------------------------


def _drafts_listing(root: Path, feature: str) -> list[str] | None:
    directory = autonomy.drafts_dir(root, feature)
    if not os.path.lexists(directory):
        return []
    if directory.is_symlink() or not directory.is_dir():
        return None
    return sorted(path.name for path in directory.iterdir())


def state_evidence(root: Path, feature: str | None) -> dict | None:
    """Tree, reviews, drafts, ignored paths and refs; None when any is unknown."""
    if feature is None or not autonomy.FEATURE.fullmatch(feature):
        return None
    try:
        pieces = {
            "tree": autonomy.tree_digest(
                root, (f"{feature}/reviews", f"{feature}/autonomous/drafts")
            ),
            "reviews": autonomy.reviews_digest(root, feature),
            "drafts": _drafts_listing(root, feature),
            "ignored": autonomy.ignored_digest(root),
            "refs": autonomy.refs_digest(root),
        }
    except (autonomy.AutonomyError, OSError, ValueError):
        return None
    if any(value is None for value in pieces.values()):
        return None
    return pieces


def changed_state(before: dict | None, after: dict | None) -> Refused | None:
    """Refuse when either evidence is unknown or the two differ (#23 R3)."""
    if before is None or after is None:
        return Refused(CHANGED, "worktree state could not be checked")
    if before != after:
        return Refused(CHANGED, "worktree state changed")
    return None


# --- Invocation ------------------------------------------------------------------


def codex_prompt(prompt: str) -> str:
    """`/speckit-x rest` -> `$speckit-x rest`, the form Codex's skills use."""
    if not prompt.startswith("/"):
        return prompt
    command, space, rest = prompt[1:].partition(" ")
    return f"${command.replace('.', '-')}{space}{rest}"


def fallback_argv(codex: str, prompt: str, model: str) -> list[str]:
    """Return the canonical headless Codex profile plus five local-provider tokens.

    No base-URL key (Codex refuses one, DEC-0003) and no primary argument.
    """
    import agent  # noqa: PLC0415 - agent imports this module

    return [
        codex,
        *agent.permission_args("codex", ["exec", prompt]),
        "--oss",
        "--local-provider",
        PROVIDER,
        "-m",
        model,
        "--json",
    ]


def fallback_env(env: dict[str, str], codex_home: Path) -> dict[str, str]:
    """No secret, endpoint override or proxy, and the wrapper's private Codex home."""
    kept = {
        name: value
        for name, value in autonomy.confined_env(env, None).items()
        if name.upper() not in PROXY_VARIABLES
    }
    for name in ENDPOINT_VARIABLES:
        kept.pop(name, None)
    kept |= BLACKHOLE
    kept["CODEX_HOME"] = str(codex_home)
    return kept


def permission_mismatch(  # noqa: PLR0913 - the comparison's every input
    argv: list[str],
    env: dict[str, str],
    codex_home: Path,
    *,
    codex: str,
    prompt: str,
    model: str,
) -> bool:
    """Return True unless argv and env are exactly the ones the wrapper builds.

    An allowlist, not a denylist: any added, removed, reordered or changed
    token, any secret-named variable, another CODEX_HOME or an endpoint
    override is a mismatch (research R6).
    """
    if argv != fallback_argv(codex, prompt, model):
        return True
    if env.get("CODEX_HOME") != str(codex_home):
        return True
    if any(name in env for name in ENDPOINT_VARIABLES):
        return True
    if any(env.get(name) != value for name, value in BLACKHOLE.items()):
        return True
    names = set(env) - set(BLACKHOLE)
    if any(name.upper() in PROXY_VARIABLES for name in names):
        return True
    return set(autonomy.confined_env(env, None)) - set(BLACKHOLE) != names


# --- Probes ----------------------------------------------------------------------


class _Budget:
    """The probes' one shared deadline."""

    def __init__(self, seconds: float) -> None:
        self.deadline = _now() + seconds

    def left(self) -> float:
        return self.deadline - _now()


class _ExpiredError(Exception):
    """The probes' budget ran out."""


def _now() -> float:
    return time.monotonic()


def _request(budget: _Budget, path: str, body: dict | None = None) -> dict:
    """One loopback request to OLLAMA_ENDPOINT, never through a proxy."""
    left = budget.left()
    if left <= 0:
        raise _ExpiredError
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(  # noqa: S310 - fixed loopback http URL
        OLLAMA_ENDPOINT + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with opener.open(request, timeout=min(REQUEST_SECONDS, left)) as response:
            raw = response.read(RESPONSE_LIMIT + 1)
    except OSError as error:  # URLError and timeouts included
        if budget.left() <= 0:
            raise _ExpiredError from error
        raise
    if budget.left() <= 0:
        raise _ExpiredError
    if len(raw) > RESPONSE_LIMIT:
        message = "response too large"
        raise ValueError(message)
    found = json.loads(raw)
    if not isinstance(found, dict):
        message = "response is not an object"
        raise ValueError(message)  # noqa: TRY004 - an invalid answer, as bad JSON
    return found


def _version(text: object) -> tuple[int, int, int] | None:
    match = VERSION_TEXT.match(text) if isinstance(text, str) else None
    return tuple(int(n) for n in match.groups()) if match else None  # type: ignore[return-value]


def _remote(entry: dict) -> bool:
    return bool(entry.get("remote_host") or entry.get("remote_model"))


def _real_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def skill_installed(root: Path, command: str) -> bool:
    """Whether the project's Codex skill for a command is a regular file in root."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", command):
        return False
    base = root / ".agents"
    for path in (base, base / "skills", base / "skills" / command):
        if not _real_dir(path):
            return False
    skill = base / "skills" / command / "SKILL.md"
    return skill.is_file() and not skill.is_symlink()


def _skills_empty(home: Path) -> bool:
    """Whether the operator's `~/.agents/skills` is absent or an empty directory."""
    path = home / ".agents" / "skills"
    if not os.path.lexists(path):
        return True
    if path.is_symlink() or not path.is_dir():
        return False
    try:
        return next(path.iterdir(), None) is None
    except OSError:
        return False


def _layers_absent(root: Path) -> bool:
    """Whether no Codex configuration layer outside the private home exists.

    System files (`/etc/codex`) and any entry under a project `.codex`; an
    unreadable location counts as present.
    """
    try:
        if os.path.lexists(CODEX_SYSTEM_DIR) and (
            CODEX_SYSTEM_DIR.is_symlink()
            or not CODEX_SYSTEM_DIR.is_dir()
            or next(CODEX_SYSTEM_DIR.iterdir(), None) is not None
        ):
            return False
        project = root / ".codex"
        return not os.path.lexists(project) or (
            project.is_dir()
            and not project.is_symlink()
            and next(project.iterdir(), None) is None
        )
    except OSError:
        return False


def _codex_supports_oss(codex: str, env: dict[str, str], budget: _Budget) -> bool:
    left = budget.left()
    if left <= 0:
        raise _ExpiredError
    try:
        result = subprocess.run(  # noqa: S603 - trusted codex, argument list
            [codex, "exec", "--help"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=left,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        raise _ExpiredError from error
    except OSError:
        return False
    usage = result.stdout + result.stderr
    return result.returncode == 0 and all(
        flag in usage for flag in (b"--oss", b"--local-provider", b"--json")
    )


def probe(  # noqa: PLR0913 - the step's every input
    setting: Setting,
    *,
    root: Path,
    autonomous: bool,
    codex: str | None,
    prompt: str,
    env: dict[str, str],
) -> Refused | None:
    """Run research R5 checks 5 to 11 and 11a in order; the first refusal or None.

    `env` is the environment `fallback_env` built for the attempt. The checks
    share one PROBE_SECONDS budget; any error or unknown answer refuses. Only
    the model name is sent, and only to OLLAMA_ENDPOINT.
    """
    budget = _Budget(PROBE_SECONDS)
    try:
        return _checks(
            setting,
            root=root,
            autonomous=autonomous,
            codex=codex,
            prompt=prompt,
            env=env,
            budget=budget,
        )
    except _ExpiredError:
        return Refused(CAPABILITY, "eligibility checks timed out")
    except Exception:  # noqa: BLE001 - any unknown answer refuses
        return Refused(CAPABILITY, "eligibility check failed")


def _checks(  # noqa: C901, PLR0911, PLR0912, PLR0913 - the ordered checks of R5
    setting: Setting,
    *,
    root: Path,
    autonomous: bool,
    codex: str | None,
    prompt: str,
    env: dict[str, str],
    budget: _Budget,
) -> Refused | None:
    model = setting.model
    # 5. The probes check exactly the endpoint Codex will use (PD-0013 F-001).
    if any(name in env for name in ENDPOINT_VARIABLES):
        return Refused(PRIVACY, "endpoint override in the environment")
    # 6. The server answers and is recent enough for Codex.
    try:
        found = _version(_request(budget, "/api/version").get("version"))
    except (OSError, ValueError, urllib.error.URLError):
        return Refused(CAPABILITY, "server not answering")
    if found is None:
        return Refused(CAPABILITY, "ollama version unknown")
    if found < MIN_OLLAMA_VERSION:
        return Refused(CAPABILITY, "ollama older than 0.13.4")
    # 7. The model is installed, by exact name, with a size and digest.
    try:
        models = _request(budget, "/api/tags").get("models")
    except (OSError, ValueError, urllib.error.URLError):
        return Refused(CAPABILITY, "server not answering")
    entry = next(
        (
            item
            for item in models or []
            if isinstance(item, dict) and model in {item.get("name"), item.get("model")}
        ),
        None,
    )
    if entry is None:
        return Refused(UNKNOWN_FREE, f"model {model} is not installed")
    size, digest = entry.get("size"), entry.get("digest")
    if type(size) is not int or size <= 0 or not isinstance(digest, str) or not digest:
        return Refused(UNKNOWN_FREE, f"model {model} has no size or digest")
    # 8. Neither remote nor cloud.
    if is_cloud(model) or _remote(entry):
        return Refused(PRIVACY, f"model {model} is remote or cloud")
    try:
        shown = _request(budget, "/api/show", {"model": model})
    except (OSError, ValueError, urllib.error.URLError):
        return Refused(CAPABILITY, "server not answering")
    if _remote(shown):
        return Refused(PRIVACY, f"model {model} is remote or cloud")
    # 8b. The model is the one the operator opted in with, not a same-name
    # replacement made through the unauthenticated local API (SEC2-002).
    if setting.digest is None:
        return Refused(CAPABILITY, "model not pinned at opt-in")
    if digest != setting.digest:
        return Refused(CAPABILITY, "model changed since opt-in")
    # 9. A trusted codex with --oss, and the project's Codex skill.
    if codex is None:
        return Refused(CAPABILITY, "codex is not installed")
    with tempfile.TemporaryDirectory(prefix="ballast-probe-") as scratch:
        probe_env = {**env, "CODEX_HOME": scratch}
        if not _codex_supports_oss(codex, probe_env, budget):
            return Refused(CAPABILITY, "codex lacks --oss or --local-provider")
        translated = codex_prompt(prompt)
        if translated.startswith("$"):
            command = translated[1:].split(maxsplit=1)[0] if translated[1:] else ""
            if not skill_installed(root, command):
                return Refused(CAPABILITY, f"codex skill {command} is not installed")
        # 10. Codex's sandbox starts under the step's own confinement.
        left = budget.left()
        if left <= 0:
            raise _ExpiredError
        started = (
            autonomy.codex_sandbox_nests(root, env=probe_env, codex=codex, timeout=left)
            if autonomous
            else autonomy.codex_sandbox_starts(root, codex, env=probe_env, timeout=left)
        )
        if budget.left() <= 0:
            raise _ExpiredError
        if not started:
            return Refused(CAPABILITY, "codex sandbox does not start")
    # 11. No other Codex configuration layer; no user skills.
    if not _layers_absent(root):
        return Refused(PERMISSION, "codex configuration layer outside the private home")
    if not _skills_empty(Path.home()):
        return Refused(PERMISSION, "user skills directory is not empty")
    # 11a. The served context fits Codex's prompt (DEC-0004).
    parameters = shown.get("parameters")
    match = NUM_CTX.search(parameters) if isinstance(parameters, str) else None
    if match is None or not match.group(1).isdigit():
        return Refused(CAPABILITY, "served context unknown")
    if int(match.group(1)) < MIN_SERVED_CONTEXT:
        return Refused(CAPABILITY, "served context below 16384")
    return None


# --- Events and records --------------------------------------------------------------


def parse_events(lines: Iterable[bytes | str]) -> Events:  # noqa: C901 - one event table
    """Return the agent message text and summed usage of a `codex exec --json` stream.

    `complete` holds only when every started turn completed with usage and
    none failed. An item of type `error` is a warning, not a failure.
    """
    texts: list[str] = []
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    started = completed = 0
    failed = False
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            message = "codex --json printed a line that is not JSON"
            raise EventError(message) from error
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            message = "codex --json printed an event without a type"
            raise EventError(message)
        kind = event["type"]
        if kind == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    texts.append(text)
        elif kind == "turn.started":
            started += 1
        elif kind == "turn.failed":
            failed = True
        elif kind == "turn.completed":
            usage = event.get("usage")
            if not isinstance(usage, dict) or any(
                type(usage.get(name)) is not int or usage[name] < 0 for name in totals
            ):
                continue
            completed += 1
            for name in totals:
                totals[name] += usage[name]
    return Events(
        text="\n".join(texts) + ("\n" if texts else ""),
        input_tokens=totals["input_tokens"],
        cached_tokens=totals["cached_input_tokens"],
        output_tokens=totals["output_tokens"],
        complete=completed > 0 and completed == started and not failed,
    )


def event_id(step: str, attempt: int, kind: str) -> str:
    """Return the fixed ledger event ID of one fallback record."""
    return f"fallback:{step}:{attempt}:{kind}"


def usage_file(events: Events, *, exited: bool) -> bytes:
    """Bytes of the fallback step's `usage.json`."""
    data = {
        "counter_source": "codex-exec-json",
        "input_tokens": events.input_tokens,
        "cached_tokens": events.cached_tokens,
        "output_tokens": events.output_tokens,
        "complete": events.complete and exited,
    }
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def usage_data(  # noqa: PLR0913 - the event's every field
    usage: bytes,
    *,
    stage: str,
    step: str,
    model: str,
    attempt: int,
    cause_id: str,
) -> dict:
    """Return the fallback `usage` event's data, from the bytes of `usage.json`."""
    counts = json.loads(usage)
    return {
        "invocation_id": step,
        "stage": stage,
        "scope": "invocation",
        "counter_source": "codex-exec-json",
        "counter_digest": hashlib.sha256(usage).hexdigest(),
        "input_tokens": counts["input_tokens"],
        "output_tokens": counts["output_tokens"],
        "cached_tokens": counts["cached_tokens"],
        "complete": counts["complete"],
        "provider": PROVIDER,
        "model": model,
        "step_id": step,
        "attempt": attempt,
        "cause_id": cause_id,
    }


def record(
    root: Path, run_id: str, feature: str | None, events: list[tuple[str, dict, str]]
) -> list[str]:
    """Append (kind, data, event_id) records to the run's ledger; return problems.

    `route` events have source `runner`, `usage` events `client-counter`.
    A repeated event ID with the same content adds nothing (AC-014). A
    failure is reported, never raised: the step's own result stands.
    """
    problems = []
    for kind, data, identifier in events:
        source = "client-counter" if kind == "usage" else "runner"
        try:
            if feature is None:
                message = "the run's feature directory is unknown"
                raise ledger.LedgerError(message)  # noqa: TRY301 - reported below
            ledger.append(
                root, ledger.new_event(run_id, feature, kind, source, data, identifier)
            )
        except (ledger.LedgerError, OSError) as error:
            problems.append(f"{kind} {identifier}: {error}")
    return problems
