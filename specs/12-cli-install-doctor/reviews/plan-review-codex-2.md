REJECT

| Round 1 finding | Status | Evidence |
| --- | --- | --- |
| Release publication | RESOLVED | [plan.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/plan.md:69) adds a step ID, job outputs, and a `needs` gate using the [documented Release Please outputs](https://github.com/googleapis/release-please-action#outputs). |
| Checkout execution during install | RESOLVED | [install.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/install.md:13) sets a fixed `PATH` before resolving download and checksum tools and calls Python by absolute path. |
| Checkout execution during doctor | NOT RESOLVED | [research.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/research.md:54) launches `true` through `systemd-run`; filtering the path used to find `systemd-run` does not constrain that child command’s inherited `PATH`. |
| Python isolation | RESOLVED | [standard-manifest.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/standard-manifest.md:19) now specifies `-I -S` for the setup probe. |
| Prerequisite evidence | NOT RESOLVED | [research.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/research.md:51) probes only the standard archive; [tools/setup](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/tools/setup:227) also fetches other archives and a pinned Spec Kit package. |
| Suitable upgrade remedy | NOT RESOLVED | [research.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/research.md:66) assumes `minimum` names an existing release; a project can pin a commit containing a raised minimum before that release exists. |
| Earlier-version regression seam | RESOLVED | [plan.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/plan.md:76) now requires command-level v0.1.0 regressions for `setup`, `trust`, `run`, and `ledger`. |
| Issue reconciliation | NOT RESOLVED | [spec.md](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/spec.md:145) asserts reconciliation, but Issue #12’s body and comments were inaccessible in this review, so parity remains unverified. |

### New critical/high findings

| Severity | Label | Location | Concrete failure path and fix |
| --- | --- | --- | --- |
| High | Spec violation | [install.md: Install line](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/install.md:13) | The line permanently replaces the caller’s `PATH`. If `~/.local/bin` was on it, installation succeeds but `ballast --version` is unavailable in that shell. Scope the safe `PATH` to tool calls and preserve the caller’s path for the install report. |
| High | Security boundary | [install.md: Install line](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/install.md:13) | `mktemp -d` can use caller supplied `TMPDIR`. With `TMPDIR` inside the checkout, the verified CLI is executed from that writable checkout, violating AC-006 and allowing a swap after verification. Require and verify a temporary location outside working trees. |
| High | Integrity verification | [install.md: Install line](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/install.md:13) | `sha256sum -c` can succeed when the checksum file names a different file; a checksum for `/dev/null`, for example, passes while `ballast` remains unchecked. Require exactly one checksum entry naming `ballast` before executing it. |
| High | Bounded execution | [research.md: R10](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/research.md:79) | A three second `urlopen` socket timeout does not bound DNS resolution or the whole probe. A stalled resolver can keep the thread pool open and prevent doctor from reporting. Enforce a wall-clock deadline outside the network worker and test an unresponsive resolver path. |

### Medium items for implementation

- Probe or clearly mark as unverified the other endpoints that [setup fetches](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/tools/setup:227); one archive `HEAD` cannot establish setup readiness.
- For commit pins, select a **published** CLI release satisfying `minimum`, and test the interval before that release is published.
- Treat v0.1.0 setup freshness as inconclusive when only installed files are present; file presence does not prove the stamp is current.