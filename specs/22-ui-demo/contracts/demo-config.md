# Contract: the `[demo]` table of `ballast.toml`

This table is protected configuration: agents cannot change it, and the operator runs `ballast trust` after editing it (FR-001, FR-002). It is parsed by `demo.demo_config(root)`, and every rule violation maps to one fixed reason ([data-model.md](../data-model.md#democonfig-from-demo-in-protected-ballasttoml)).

```toml
[demo]
retention_days = 14        # optional, 1-90; GitHub applies a lower repository limit
timeout_minutes = 15       # optional, 1-60; enforced by `timeout` around the command (the job's own 65-minute limit is only a backstop)

[[demo.scenarios]]         # 1-20
name = "login-journey"     # [A-Za-z0-9._-]{1,64}, unique
command = "npm run demo:login"          # one line; run as `bash -c` at the repository root
video = "demo-output/login.webm"        # the one file the command writes, relative path
environment = "Chromium 1280x720, seeded fixtures"   # 1-80 characters, shown in the packet
```

## Obligations on the project (documented, not enforced)

- The command uses only seeded, nonsensitive data and fake accounts. The job has no secrets, and the video is readable by anyone with read access to the repository. On a public repository that means everyone (AC-009).
- The command installs its own browser or recorder. Ballast chooses, installs and downloads none (FR-016).
- The same command, run at the captured commit in a clean checkout, reproduces the journey locally (AC-007, SC-004).

## Results of the table's state

| State | `ballast run demo` | Packet |
| --- | --- | --- |
| absent | `refused (not-configured)`: add a `[demo]` table and run `ballast trust` | `Demo captures: not configured.` |
| invalid | `refused (config-invalid)` with the reason | `Demo captures: configuration invalid (<reason>).`; the rest publishes |
| valid, scenario not declared | `refused (unknown-scenario)`: names the declared scenarios | unchanged |
| valid | dispatch | one line per declared scenario |
