# Changelog

## [0.9.0](https://github.com/Hugo-Grellier/ballast/compare/v0.8.1...v0.9.0) (2026-10-07)


### Features

* **routing:** qualify one zero-cost provider fallback ([#103](https://github.com/Hugo-Grellier/ballast/issues/103)) ([a9c8e1c](https://github.com/Hugo-Grellier/ballast/commit/a9c8e1cec29aeec4e82bdc790ece1ab67ab3e1f2))
* **setup:** trust a checkout setup just installed without a separate operator command ([#101](https://github.com/Hugo-Grellier/ballast/issues/101)) ([7ae08ed](https://github.com/Hugo-Grellier/ballast/commit/7ae08ed90344ad8eb7906f88388c79a3675f3538))


### Bug Fixes

* **agent:** hide the operator's global Git configuration from confined steps ([#107](https://github.com/Hugo-Grellier/ballast/issues/107)) ([4a28076](https://github.com/Hugo-Grellier/ballast/commit/4a28076c48c17c9aba6c170550fa8c5bbbf32961))
* **agent:** refuse every hidden credential path in the worktree and resolve agent homes ([#108](https://github.com/Hugo-Grellier/ballast/issues/108)) ([09d8596](https://github.com/Hugo-Grellier/ballast/commit/09d8596dac302e1fadc89b5bd51eee229a8588a5))
* **launcher:** do not treat an agent that closes its terminal before exit as interrupted ([#104](https://github.com/Hugo-Grellier/ballast/issues/104)) ([282f7f3](https://github.com/Hugo-Grellier/ballast/commit/282f7f3ec3e51d830eccdcc2eb0a526a0cb0b0a9))
* **run:** harden Chat mode and headless steps (review follow-ups from [#20](https://github.com/Hugo-Grellier/ballast/issues/20)) ([#106](https://github.com/Hugo-Grellier/ballast/issues/106)) ([37d8ace](https://github.com/Hugo-Grellier/ballast/commit/37d8acec8605661d40d66f1cb92db8b9047ab3b5))
* **setup:** do not prepare again an installation that finished before the lock ([#109](https://github.com/Hugo-Grellier/ballast/issues/109)) ([f2bb775](https://github.com/Hugo-Grellier/ballast/commit/f2bb77564da3e4b98d5e85e141d8ba1b27adb9dc))
* **workflow:** close five Autonomous recovery gaps ([#105](https://github.com/Hugo-Grellier/ballast/issues/105)) ([bcac2bd](https://github.com/Hugo-Grellier/ballast/commit/bcac2bd27fe1b84a5921b5760e708ada463155ea))

## [0.8.1](https://github.com/Hugo-Grellier/ballast/compare/v0.8.0...v0.8.1) (2026-10-06)


### Bug Fixes

* **agent:** give each confined step only its own CLI's credentials ([#89](https://github.com/Hugo-Grellier/ballast/issues/89)) ([a386c78](https://github.com/Hugo-Grellier/ballast/commit/a386c78ef12a0ce9930fcb00f7d845e4d9e0f44e))
* **agent:** protect installed skills in headless steps and claim the in-progress marker exclusively ([#96](https://github.com/Hugo-Grellier/ballast/issues/96)) ([0ff3e13](https://github.com/Hugo-Grellier/ballast/commit/0ff3e131a5edd6ac8b6953e3cb25fd6f84235393))
* **workflow:** let check steps run as long as the configured checks ([#99](https://github.com/Hugo-Grellier/ballast/issues/99)) ([51edd7d](https://github.com/Hugo-Grellier/ballast/commit/51edd7d480ac3f95e378b44dd5d4a3fbb6a62d1e))
* **workflow:** require the reviews the engineering review requests ([#93](https://github.com/Hugo-Grellier/ballast/issues/93)) ([e6fce67](https://github.com/Hugo-Grellier/ballast/commit/e6fce67ce69e03903de41b67d09760ab1927a45e))

## [0.8.0](https://github.com/Hugo-Grellier/ballast/compare/v0.7.1...v0.8.0) (2026-10-06)


### Features

* **init:** adapt Ballast to blank and established repositories ([#86](https://github.com/Hugo-Grellier/ballast/issues/86)) ([685e2ca](https://github.com/Hugo-Grellier/ballast/commit/685e2cabe0a62f1c8819299d52b9e9f6ae3f46f9))
* **review:** capture a UI walkthrough on demand and link it to the PR ([#87](https://github.com/Hugo-Grellier/ballast/issues/87)) ([28dd890](https://github.com/Hugo-Grellier/ballast/commit/28dd8908349008df6ee897bc3810fcef440869da))


### Bug Fixes

* **agent:** keep a linked worktree's git pointer and admin files read-only in confined steps ([#85](https://github.com/Hugo-Grellier/ballast/issues/85)) ([1d153b2](https://github.com/Hugo-Grellier/ballast/commit/1d153b2c00a494817c9838748b88fdec19ae3f1b))

## [0.7.1](https://github.com/Hugo-Grellier/ballast/compare/v0.7.0...v0.7.1) (2026-10-06)


### Bug Fixes

* **agent:** give confined Claude steps a login without refresh tokens ([#72](https://github.com/Hugo-Grellier/ballast/issues/72)) ([3f7180f](https://github.com/Hugo-Grellier/ballast/commit/3f7180f23357723ed7e77eafc8b3a3e0ac5e601b))
* **agent:** give confined Codex steps a login without refresh tokens ([#80](https://github.com/Hugo-Grellier/ballast/issues/80)) ([11134f1](https://github.com/Hugo-Grellier/ballast/commit/11134f1a395cdaec7822135459eb17abd981c616))
* **agent:** let confined steps run the project's checks ([#82](https://github.com/Hugo-Grellier/ballast/issues/82)) ([b90ea0f](https://github.com/Hugo-Grellier/ballast/commit/b90ea0f790f67ee701b38cc41281f1b1371c3922))
* **setup:** edit every installed integration's tasks skill by content ([#73](https://github.com/Hugo-Grellier/ballast/issues/73)) ([e401a6d](https://github.com/Hugo-Grellier/ballast/commit/e401a6d88c2d4d253c58053da69dd59ea720bf5a))
* **setup:** name the installed Python prerequisites script in the tasks skill ([#78](https://github.com/Hugo-Grellier/ballast/issues/78)) ([a31c737](https://github.com/Hugo-Grellier/ballast/commit/a31c73799af3cb159b9697be60eda6bfb92d28da))

## [0.7.0](https://github.com/Hugo-Grellier/ballast/compare/v0.6.0...v0.7.0) (2026-10-06)


### Features

* **setup:** make installs and pin updates recoverable ([#64](https://github.com/Hugo-Grellier/ballast/issues/64)) ([1ce1f9a](https://github.com/Hugo-Grellier/ballast/commit/1ce1f9a529bb39c7a50dd7dea4382a34356f690c))
* **setup:** prepare a new worktree on first Ballast use ([#69](https://github.com/Hugo-Grellier/ballast/issues/69)) ([0258627](https://github.com/Hugo-Grellier/ballast/commit/0258627fcb934822dc3eb63f11fbc64ad2ac1481))
* **workflow:** provide trusted interactive Chat mode ([#67](https://github.com/Hugo-Grellier/ballast/issues/67)) ([24820ce](https://github.com/Hugo-Grellier/ballast/commit/24820ce7cb3141d695c52394cc2fc9d6987f02b1))
* **workflow:** reach a reviewed PR with provisional Autonomous decisions ([#71](https://github.com/Hugo-Grellier/ballast/issues/71)) ([60a220a](https://github.com/Hugo-Grellier/ballast/commit/60a220a00a8766fae8b230d311ab18fee88cc799))


### Bug Fixes

* **cli:** escape control characters in the doctor text report ([#62](https://github.com/Hugo-Grellier/ballast/issues/62)) ([bc4ea3e](https://github.com/Hugo-Grellier/ballast/commit/bc4ea3e4d395014ae3e8cccbb5e6a8d1e7e2d142))
* **setup:** escape control characters in setup output ([#70](https://github.com/Hugo-Grellier/ballast/issues/70)) ([0a668c3](https://github.com/Hugo-Grellier/ballast/commit/0a668c39cd5f9960c80bfd6ae70cdb6bc5708baa))
* **setup:** never let checkout git config run a program before trust ([#68](https://github.com/Hugo-Grellier/ballast/issues/68)) ([0d5ff50](https://github.com/Hugo-Grellier/ballast/commit/0d5ff50f5f2312ee8fd51b10c091570904647da6))

## [0.6.0](https://github.com/Hugo-Grellier/ballast/compare/v0.5.0...v0.6.0) (2026-10-05)


### Features

* **discovery:** create a source-backed brief before feature specs ([#57](https://github.com/Hugo-Grellier/ballast/issues/57)) ([36df129](https://github.com/Hugo-Grellier/ballast/commit/36df129d4717fadc60140b3af9c036b60c7fd913))
* **review:** generate a source-linked PR acceptance packet ([#59](https://github.com/Hugo-Grellier/ballast/issues/59)) ([042f884](https://github.com/Hugo-Grellier/ballast/commit/042f884c60daf17cabf78ce52bc2d4e605aada0a))

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
