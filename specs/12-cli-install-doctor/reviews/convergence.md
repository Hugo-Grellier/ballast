# Feature #12 spec reconciliation

The reported verification baseline is **192 tests passed** and **ruff clean**. This review uses the uncommitted implementation and tests; the sandbox’s inability to create temporary directories is not treated as a test failure. DEC-0002 defers real release checks for SC-001 and SC-002 to its documented post-release checklist.

| Criterion | Implementation evidence | Test evidence |
| --- | --- | --- |
| AC-001 | `README.md:20–37`; `tools/ballast:60,893–903` | `tests/test_ballast.py:240` |
| AC-002 | `.github/workflows/release-please.yml:32–46`; `tools/ballast:210–253` | `tests/test_release_workflow.py:45`; `tests/test_ballast.py:240` |
| AC-003 | `README.md:26`; `tools/ballast:71–82` | `tests/test_ballast.py:261` |
| AC-004 | `tools/ballast:219–253` | `tests/test_ballast.py:240,296,362` |
| AC-005 | `tools/ballast:264–278` | `tests/test_ballast.py:252` |
| AC-006 | `README.md:26`; `tools/ballast:71–82,210–217` | `tests/test_ballast.py:380` — **partial** |
| AC-007 | `tools/ballast:468–540,838–890` | `tests/test_doctor.py:231` |
| AC-008 | `tools/ballast:468–540,838–863` | `tests/test_doctor.py:256` |
| AC-009 | `tools/ballast:405–441` | `tests/test_doctor.py:293,304,313` |
| AC-010 | `tools/ballast:444–463` | `tests/test_doctor.py:337` |
| AC-011 | `tools/ballast:569–572,769–770` | `tests/test_doctor.py:354` |
| AC-012 | `tools/ballast:347–365,553–608,680–754` | `tests/test_doctor.py:190–209,363` |
| AC-013 | `tools/ballast:98–119,757–774` | `tests/test_doctor.py:548` |
| AC-014 | `tools/ballast:775–788`; `tools/setup:340–354` | `tests/test_doctor.py:573,583`; `tests/test_setup.py:157` |
| AC-015 | `tools/ballast:725–754`; `tools/spec_workflow/launcher.py:239–244` | `tests/test_doctor.py:583`; `tests/test_spec_workflow.py:998` |
| AC-016 | `tools/ballast:642–677,791–792` | `tests/test_doctor.py:619` |
| FR-001 | `README.md:20–26`; `tools/ballast:204–261` | `tests/test_ballast.py:240` |
| FR-002 | `.github/workflows/release-please.yml:32–46`; `README.md:26` | `tests/test_release_workflow.py:45`; `tests/test_ballast.py:261` |
| FR-003 | `README.md:26`; `tools/ballast:71–82,210–217` | `tests/test_ballast.py:380` — **partial** |
| FR-004 | `tools/ballast:221–259` | `tests/test_ballast.py:240,261,362` |
| FR-005 | `tools/ballast:219–237,264–278` | `tests/test_ballast.py:252,296` |
| FR-006 | `tools/ballast:897–899` | `tests/test_ballast.py:118` |
| FR-007 | `tools/ballast:71–82`; `README.md:24–28`; `.github/workflows/release-please.yml:35–46` | `tests/test_ballast.py:221,240,261`; `tests/test_release_workflow.py:45` |
| FR-008 | `tools/ballast:376–540,569–608` | `tests/test_doctor.py:256,293,304,313,325,337` |
| FR-009 | `tools/ballast:290–298,826–863` | `tests/test_doctor.py:256,371` |
| FR-010 | `tools/ballast:628–811` | `tests/test_doctor.py:548–713` |
| FR-011 | `tools/ballast:347–365,553–608,680–754` | `tests/test_doctor.py:190–209,363`; `tests/test_setup.py:157`; `tests/test_spec_workflow.py:998` |
| FR-012 | `tools/ballast:321–344,680–693,866–903` | `tests/test_doctor.py:427–489,635–713` |
| FR-013 | `tools/ballast:838–890` | `tests/test_doctor.py:231,256,313` |
| FR-014 | `tools/ballast:453–463` | `tests/test_doctor.py:337` |
| FR-015 | `tools/ballast:866–890` | `tests/test_doctor.py:371` |
| FR-016 | `tools/ballast:347–369,569–608` | `tests/test_doctor.py:390,399` |
| FR-017 | `README.md:20–50` | `tests/test_ballast.py:221`; `tests/test_doctor.py:491` |
| FR-018 | `tools/ballast:466–540`; `README.md:39–46` | `tests/test_doctor.py:491` |
| FR-019 | `tools/ballast:114–119,911–922`; `tools/setup:242` | `tests/test_ballast.py:480,501`; `tests/test_setup.py:174` |

## Actionable gaps

1. **Implementation wrong — AC-006, FR-003.** The install line calls `curl -fsSL` twice (`README.md:26`; `tools/ballast:75–76`). Curl reads its default configuration unless `-q` is its first argument. `CURL_HOME`, `XDG_CONFIG_HOME` or `HOME` can point to a Git working tree, so the line can read configuration from a working tree despite its fixed `PATH`. Add `-q` to both calls and test with a planted curl configuration inside a checkout. The current isolation test plants executables but no curl configuration.

2. **New knowledge discovered — SC-004 evidence.** `tests/test_ballast.py:261–294` covers a truncated asset served successfully and an unknown version, but does not interrupt a download. `quickstart.md:21` treats truncation as interruption. Add a transfer that writes partial output and exits unsuccessfully, then assert the previous command remains byte-identical and runnable.

3. **Specification stale — doctor timing contract.** `contracts/doctor-cli.md:48` promises that each probe reports inconclusive within 3 seconds, while `research.md` R10 and `tools/ballast:89,590–608` deliberately allow 5 seconds for the network group. State the 3-second per-request and 5-second group limits in the contract, or change the implementation to meet the current wording.

4. **New knowledge discovered — missing-interpreter edge case.** `spec.md:84` requires both the install command and installed command to name the required Python version when `/usr/bin/python3` is absent. The install line (`README.md:26`) invokes that interpreter without a preceding check; an installed Python script cannot print its own message when its shebang interpreter is absent. Add an install-line check and resolve the installed-command expectation in the spec or architecture.

The real release asset, clean-account install and README-only setup remain the documented post-release checks in `decisions.md` DEC-0002 and `tasks.md:273–278`; they are not claimed as completed here.

- Verdict: PARTIAL
## Re-check

**The curl configuration gap is closed** for AC-006/FR-003. Both downloads put `-q` first in the [README install line](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/README.md:26), [INSTALL_LINE](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/tools/ballast:75), and [install contract](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/specs/12-cli-install-doctor/contracts/install.md:15). The [checkout isolation test](/home/hugo/orca/workspaces/agentic-repo-standard/feat-cli-install-ballast-in-one-command-and-diag/tests/test_ballast.py:403) plants `.curlrc` in the checkout, points curl’s configuration paths there, and checks that its sentinel was untouched. You report 192 tests passing outside the sandbox and this test failing when `-q` is removed. This verdict covers the one requested gap.

- Verdict: CONVERGED