# Changelog

## [0.5.0](https://github.com/Hugo-Grellier/ballast/compare/v0.4.2...v0.5.0) (2026-10-05)


### Features

* **agent:** let confined Claude steps read files and report uncovered checks ([#52](https://github.com/Hugo-Grellier/ballast/issues/52)) ([e26906d](https://github.com/Hugo-Grellier/ballast/commit/e26906db4b3e5bae97e154443700b95bcaeb8743))
* **run:** synchronize stale feature branches before run start and resume ([#54](https://github.com/Hugo-Grellier/ballast/issues/54)) ([f683454](https://github.com/Hugo-Grellier/ballast/commit/f68345460ea2a00f0699d161f8cd4b2d568e0cda))

## [0.4.2](https://github.com/Hugo-Grellier/ballast/compare/v0.4.1...v0.4.2) (2026-10-05)


### Bug Fixes

* **agent:** run agent git through a guard and match whole subcommands ([#47](https://github.com/Hugo-Grellier/ballast/issues/47)) ([706dc11](https://github.com/Hugo-Grellier/ballast/commit/706dc1138e324d04b18c3065c8548abd8b57e71f))
* **cli:** treat temp directories as agent-writable in doctor and the shim ([#49](https://github.com/Hugo-Grellier/ballast/issues/49)) ([bcf77f3](https://github.com/Hugo-Grellier/ballast/commit/bcf77f32d9c1cd0cfffe074cfc9a279e6ef5d86a))
* **launcher:** refuse an operator state directory agents can write ([#48](https://github.com/Hugo-Grellier/ballast/issues/48)) ([fcc498e](https://github.com/Hugo-Grellier/ballast/commit/fcc498e2b1cef24a0ae0e605ff5f58d9fe398b54))

## [0.4.1](https://github.com/Hugo-Grellier/ballast/compare/v0.4.0...v0.4.1) (2026-10-05)


### Bug Fixes

* **launcher:** run the intake helper from the pinned standard as `ballast intake` ([#42](https://github.com/Hugo-Grellier/ballast/issues/42)) ([dd3d4cc](https://github.com/Hugo-Grellier/ballast/commit/dd3d4cc563c79262db6121b426915d86470df9c2))
* **workflow:** refuse unregistered human intent approvals in gated runs ([#43](https://github.com/Hugo-Grellier/ballast/issues/43)) ([ed9fd6f](https://github.com/Hugo-Grellier/ballast/commit/ed9fd6fc920ee5485421e77c05d4e39ee70ccb1e))

## [0.4.0](https://github.com/Hugo-Grellier/ballast/compare/v0.3.0...v0.4.0) (2026-10-04)


### Features

* **run:** run eligible features to a Draft PR with provisional Autonomous decisions ([#39](https://github.com/Hugo-Grellier/ballast/issues/39)) ([9d4c866](https://github.com/Hugo-Grellier/ballast/commit/9d4c866a7969c856cc05e7d7d941f1ab5ee71e81))

## [0.3.0](https://github.com/Hugo-Grellier/ballast/compare/v0.2.0...v0.3.0) (2026-10-04)


### Features

* **run:** open and reuse one issue-linked Draft PR at the end of ballast run ([#33](https://github.com/Hugo-Grellier/ballast/issues/33)) ([ec9551c](https://github.com/Hugo-Grellier/ballast/commit/ec9551c2e0f3ecd793a0c391c52bb10914590ec4))


### Bug Fixes

* **launcher:** start run.py with -I -S like every other workflow tool ([#31](https://github.com/Hugo-Grellier/ballast/issues/31)) ([0675e0a](https://github.com/Hugo-Grellier/ballast/commit/0675e0af7ca9532e2ec6565e4255b0e871e23eed))

## [0.2.0](https://github.com/Hugo-Grellier/ballast/compare/v0.1.0...v0.2.0) (2026-10-04)


### Features

* **cli:** install Ballast in one command and diagnose readiness ([#30](https://github.com/Hugo-Grellier/ballast/issues/30)) ([c766441](https://github.com/Hugo-Grellier/ballast/commit/c7664413963014af46d75d9ec9bc3af1e87e9dcd))


### Bug Fixes

* **agent:** stop systemd-run expanding $ in agent prompts ([#28](https://github.com/Hugo-Grellier/ballast/issues/28)) ([ef1ffe6](https://github.com/Hugo-Grellier/ballast/commit/ef1ffe6a5dd1967755a14ec9f58dc57be41eec7d))
* **ledger:** report archived runs without PyYAML ([#10](https://github.com/Hugo-Grellier/ballast/issues/10)) ([42102c6](https://github.com/Hugo-Grellier/ballast/commit/42102c69ac885484d4c8ff31078e033c84d25039))
* **setup:** keep Spec Kit bug reports and assessments tracked ([#8](https://github.com/Hugo-Grellier/ballast/issues/8)) ([23dfb36](https://github.com/Hugo-Grellier/ballast/commit/23dfb36a982e0f2dea8b49494dd5ce6685c16f0f))


### Documentation

* define Ballast 1.0 scope and roadmap ([#25](https://github.com/Hugo-Grellier/ballast/issues/25)) ([ba42067](https://github.com/Hugo-Grellier/ballast/commit/ba4206774fbd00595efb1006e530704af89de098))
* drop the duplicated changelog heading ([#5](https://github.com/Hugo-Grellier/ballast/issues/5)) ([4cb80aa](https://github.com/Hugo-Grellier/ballast/commit/4cb80aa8c21c3b56448c4c4cc224806df93fefdc))

## 0.1.0 (2026-10-02)


### Features

* backport the LoreForge agent-first profile as a versioned standard ([#1](https://github.com/Hugo-Grellier/ballast/issues/1)) ([cc14b21](https://github.com/Hugo-Grellier/ballast/commit/cc14b214b79e2be4054722e02033934bcdd12471))
* rename the standard to Ballast ([#4](https://github.com/Hugo-Grellier/ballast/issues/4)) ([d488fa5](https://github.com/Hugo-Grellier/ballast/commit/d488fa57e74d00f1c1a84471453e224c1eaaf8d4))


### Bug Fixes

* **release:** start releases at 0.1.0 ([#3](https://github.com/Hugo-Grellier/ballast/issues/3)) ([76a33a6](https://github.com/Hugo-Grellier/ballast/commit/76a33a6e3151ea1991237e609bf7312e19353300))


### Documentation

* add initial specs, AGENTS template and LoreForge backport plan ([b45492c](https://github.com/Hugo-Grellier/ballast/commit/b45492c8eaef3ea9ff4822e279c1af82527fa2f7))
