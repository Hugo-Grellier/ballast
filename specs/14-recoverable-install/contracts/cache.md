# Contract: the per-machine standard cache (`ballast` CLI)

Layout under `$XDG_DATA_HOME/ballast/standard/` (refused inside the checkout or an agent temp root, as today):

```text
<ref>/                     the extracted standard version (unchanged layout)
<ref>/.ballast-cache.json  its content record, published by the same rename
.locks/<ref>.lock          per-version fetch lock
.fetch-<ref>+<random>/     an extraction in progress; never read
.damaged-<ref>+<random>/   a damaged copy being removed; never read
```

## Record

```json
{
  "schema": 1,
  "ref": "v0.6.0",
  "fetched": "2026-10-06T12:00:00+00:00",
  "files": {
    "tools/setup": {"sha256": "<hex>", "exec": true},
    "tools/spec-kit/link": {"link": "target"}
  }
}
```

Paths are relative to `<ref>/`, sorted, excluding the record itself and `__pycache__` (Python may write bytecode next to a module it imports).

## Fetch (only `setup` and `preview` fetch)

1. Take `LOCK_EX` on `.locks/<ref>.lock`, waiting up to 600 s with `ballast: waiting for another fetch of <ref>` printed once; on timeout refuse (exit 2) naming the lock.
2. Under the lock, if `<ref>/` verifies, use it: no download.
3. Remove `.fetch-<ref>+*` and `.damaged-<ref>+*` left by dead fetches of this version (safe: only this version's lock holder creates them; `+` cannot occur in a ref, so another version's fetch is never touched).
4. Download the archive and extract it into `.fetch-<ref>+<random>/`; write the record; `rename` the tree to `<ref>/`.
5. Any failure: delete `.fetch-<random>/`, exit 1 with `ballast: cannot fetch standard <ref>: <cause>; the cache and the checkout are unchanged. Next: check network access (ballast doctor), then rerun the command`.

## Verify (before `setup` and `preview` use a cached version)

Compare the tree with the record: a missing record, or any missing, added or altered file, link or executable bit is damage. On damage, under the lock, rename the tree to `.damaged-<random>/`, delete it, and fetch again; print `ballast: the cached standard <ref> was damaged (<first path>); fetched it again`. When that fetch fails, refuse (exit 2): `ballast: the cached standard <ref> is damaged at <path> and could not be fetched again: <cause>`.

`BALLAST_STANDARD_DIR` bypasses the cache entirely: nothing is fetched or verified (spec Edge Cases).

## Not fetched, for other commands

`ballast run|ledger|trust|intake` with an unfetched pin refuses as today, and when `installation.json` names an installed ref other than the pin it adds: `installed <A>, pinned <B>: restore ref = "<A>" in ballast.toml, or fix the cause and rerun ballast setup` (AC-008).
