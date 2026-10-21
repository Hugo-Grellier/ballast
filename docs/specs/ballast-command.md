# Ballast command

Covers: tools/cli.py

`tools/cli.py` is the `ballast` console script: `ballast COMMAND ARGS` runs one
shipped helper the way `python3 -I -S tools/X.py` does.

### Requirement: Allow-listed helpers
The command SHALL accept only `coordinate`, `dashboard`, `merge-check`,
`worker` and `worktree`, each mapped to a shipped helper, and SHALL refuse
anything else with a usage line and exit 2.

#### Scenario: Entry point and mapping
- WHEN the package is installed
- THEN its only script is `ballast = tools.cli:main`, with no dependency, and every command names an existing helper
- Test: tests/test_package.py::CommandTests::test_entry_point_names_the_dispatcher
- Test: tests/test_package.py::CommandTests::test_documented_commands_map_to_shipped_helpers

#### Scenario: Unknown or missing command
- WHEN no command, an unlisted one, a path or `--help` is given
- THEN it exits 2 with the usage line on stderr and nothing on stdout
- Test: tests/test_package.py::CommandTests::test_unknown_or_missing_command_is_refused

### Requirement: Isolated re-exec
The command SHALL replace itself with the helper under the same interpreter
with `-I -S` and the remaining arguments, so the helper gets its own exit code
and loads no module from `PYTHONPATH` or site packages.

#### Scenario: Isolation
- WHEN a planted module shadows one the helper imports
- THEN the helper does not load it and runs with its arguments
- Test: tests/test_package.py::CommandTests::test_helper_runs_isolated_with_its_arguments

#### Scenario: Interpreter flags
- WHEN the helper runs
- THEN it has the isolated and no-site flags, no `site` module, and exactly the remaining arguments
- Test: tests/test_package.py::CommandTests::test_helper_process_has_isolated_and_no_site_flags
