# Changelog

## [2.2.0](https://github.com/Hugo-Grellier/ballast/compare/v2.1.0...v2.2.0) (2026-10-22)


### Features

* **admission:** require an approved spec delta before an R1/R2 implement dispatch ([#291](https://github.com/Hugo-Grellier/ballast/issues/291)) ([03de61e](https://github.com/Hugo-Grellier/ballast/commit/03de61e4851d934bc556245075c8e7d16c613ef1))
* **coordinate:** record coordinator-direct implementation and review as tracked executions ([#250](https://github.com/Hugo-Grellier/ballast/issues/250)) ([a57eb9d](https://github.com/Hugo-Grellier/ballast/commit/a57eb9d2a99e5ee5ff34f58a6b192e0e8b453b40))
* **merge:** MERGE / HUMAN / BLOCK verdict replaces the blanket human merge ([#300](https://github.com/Hugo-Grellier/ballast/issues/300)) ([5e51a22](https://github.com/Hugo-Grellier/ballast/commit/5e51a22e09edac2f73476272b425094bee1a4a9c))
* **policy:** merge R0 PRs once an independent review and CI approve the exact head ([#252](https://github.com/Hugo-Grellier/ballast/issues/252)) ([61f4d71](https://github.com/Hugo-Grellier/ballast/commit/61f4d71261f79859c947913bd892e8f1c371f20c))
* **qualification:** scripted local and live qualification without automated deletion ([#259](https://github.com/Hugo-Grellier/ballast/issues/259)) ([e1399df](https://github.com/Hugo-Grellier/ballast/commit/e1399dfce7bfec3256cba1ca65603f0b10be6ff8))
* **queue:** close a finished queue so the clone can start a new one ([#253](https://github.com/Hugo-Grellier/ballast/issues/253)) ([d6ee394](https://github.com/Hugo-Grellier/ballast/commit/d6ee3941c2ebef19b7d74d85459a144aabaff910))
* **queue:** stack PRs for overlapping leaf issues with a recorded merge order ([#276](https://github.com/Hugo-Grellier/ballast/issues/276)) ([9234bbf](https://github.com/Hugo-Grellier/ballast/commit/9234bbfd9a177a8463032910de50d0e1fa8c5f21))
* **review:** fall back to a recorded coordinator review after a Codex quota pause ([#284](https://github.com/Hugo-Grellier/ballast/issues/284)) ([c126a87](https://github.com/Hugo-Grellier/ballast/commit/c126a87a55e2ade98e60ed20f8759e86964c0c10))
* run the helpers from a pinned tag and copy the workflow docs into adopters ([#286](https://github.com/Hugo-Grellier/ballast/issues/286)) ([d2f41e2](https://github.com/Hugo-Grellier/ballast/commit/d2f41e2173c9271803090b466b34dabef5a02460))
* **specs:** check a PR's spec change against the approved delta and its scenario tests ([#299](https://github.com/Hugo-Grellier/ballast/issues/299)) ([a87ba98](https://github.com/Hugo-Grellier/ballast/commit/a87ba98c59486904185b24037dedd6943790e103))
* **specs:** living spec format and a scenario-to-test checker in CI ([#285](https://github.com/Hugo-Grellier/ballast/issues/285)) ([9d35827](https://github.com/Hugo-Grellier/ballast/commit/9d358274021b1297c67bde18cc3f7e0af5602bb6))
* **tools:** check PR bodies against the PR template locally and in CI ([#243](https://github.com/Hugo-Grellier/ballast/issues/243)) ([700c468](https://github.com/Hugo-Grellier/ballast/commit/700c468d003ecf0016b3967759ea344c9d6cb9cb))
* **worker:** give each worker a private scratch dir for TMPDIR and the uv cache ([#287](https://github.com/Hugo-Grellier/ballast/issues/287)) ([4fe173a](https://github.com/Hugo-Grellier/ballast/commit/4fe173a0424c0a714a6fba459c6dc845efb6fb2a))


### Bug Fixes

* **admission:** let a coordinator close a finished queue left by an ended coordinator ([#282](https://github.com/Hugo-Grellier/ballast/issues/282)) ([c36092b](https://github.com/Hugo-Grellier/ballast/commit/c36092bb6dda1f63ff8b47d3799325c4c1789150))
* **admission:** let the queue coordinator stop a claim stranded under another coordinator ([#238](https://github.com/Hugo-Grellier/ballast/issues/238)) ([0edee07](https://github.com/Hugo-Grellier/ballast/commit/0edee07ba81a28db9568f5e95e5ccfe4ec787ad9))
* **admission:** refund an attempt the operator cancelled ([#280](https://github.com/Hugo-Grellier/ballast/issues/280)) ([b0717de](https://github.com/Hugo-Grellier/ballast/commit/b0717de77720877b84b9b99e9d45b662f8bb0a41))
* **dashboard:** keep dependency selection within budget under GitHub latency ([#244](https://github.com/Hugo-Grellier/ballast/issues/244)) ([508bb45](https://github.com/Hugo-Grellier/ballast/commit/508bb45ed76fb04c55ef7193b649d2e34bc89c5c))
* **progress:** reject remaining secret and path shapes in public summaries ([#245](https://github.com/Hugo-Grellier/ballast/issues/245)) ([348c948](https://github.com/Hugo-Grellier/ballast/commit/348c9484ca270ef714e426ae7b0880f5878f63b0))
* **queue:** refuse missing parent objects and retire settled claims ([#289](https://github.com/Hugo-Grellier/ballast/issues/289)) ([9cb56da](https://github.com/Hugo-Grellier/ballast/commit/9cb56dac27d5e021754bd1d82568fb0a9164877a))
* **worker:** keep the Codex client out of group-wide signals so stops settle cleanly ([#246](https://github.com/Hugo-Grellier/ballast/issues/246)) ([bce49d4](https://github.com/Hugo-Grellier/ballast/commit/bce49d42c2e2697331e56d674dad442d571220b8))
* **worker:** settle a cancelled worker once a surviving tool command exits ([#278](https://github.com/Hugo-Grellier/ballast/issues/278)) ([65d04ed](https://github.com/Hugo-Grellier/ballast/commit/65d04edc65fa11e070e968a816965d08dd3f0243))
* **worktree:** refuse . and .. as repository owner or name ([#237](https://github.com/Hugo-Grellier/ballast/issues/237)) ([e6f4df7](https://github.com/Hugo-Grellier/ballast/commit/e6f4df74e7d4413e454c1854ff5e1583db4c4b35))
* **worktree:** scrub inherited GIT_* variables from helper Git calls ([#262](https://github.com/Hugo-Grellier/ballast/issues/262)) ([d0c0de0](https://github.com/Hugo-Grellier/ballast/commit/d0c0de0727a0a0555cd80fe3fb1805bdc2225edd))


### Documentation

* **adr:** ADR-0027 spec approval, living specs and a computed merge verdict ([#271](https://github.com/Hugo-Grellier/ballast/issues/271)) ([392205d](https://github.com/Hugo-Grellier/ballast/commit/392205d31247bdebe8395c22db072dcf8b56b3eb))
* **pair-review:** define repair-round scope, nonblocking findings and CI evidence ([#247](https://github.com/Hugo-Grellier/ballast/issues/247)) ([130c7fe](https://github.com/Hugo-Grellier/ballast/commit/130c7fe4b17e05c0b9d0bbf03e6b7fd166dbc073))
* **review:** define how check evidence reaches read-only review workers ([#277](https://github.com/Hugo-Grellier/ballast/issues/277)) ([fa6d614](https://github.com/Hugo-Grellier/ballast/commit/fa6d6143cf3effd11530777fe0410454ac72287d))
* **specs:** bootstrap living specs from current behavior ([#298](https://github.com/Hugo-Grellier/ballast/issues/298)) ([2bc2ed7](https://github.com/Hugo-Grellier/ballast/commit/2bc2ed701ef8738a20c4df3533cf8ea63c45daea))
* **templates:** adopter spec gate, migration guide and project/workflow slot ([#303](https://github.com/Hugo-Grellier/ballast/issues/303)) ([ca31508](https://github.com/Hugo-Grellier/ballast/commit/ca3150840b937c1000f28ac6d06ab3bc106c91b3))
* **workers:** forbid clone-wide git state such as stash in issue worktrees ([#261](https://github.com/Hugo-Grellier/ballast/issues/261)) ([6231dc6](https://github.com/Hugo-Grellier/ballast/commit/6231dc68fa0ae0731604b319ee297396544b8b8c))
* **workflow:** guidance for dispatching agent-native subagents as workers ([#236](https://github.com/Hugo-Grellier/ballast/issues/236)) ([26b646e](https://github.com/Hugo-Grellier/ballast/commit/26b646eb0c0f5fd1f5c740a87f48bbadb64b96a3))
* **workflow:** record R2 human approvals durably and link them from the PR ([#251](https://github.com/Hugo-Grellier/ballast/issues/251)) ([6314f94](https://github.com/Hugo-Grellier/ballast/commit/6314f9405d52fc19a5838e02f59ec012ab951756))

## [2.1.0](https://github.com/Hugo-Grellier/ballast/compare/v2.0.0...v2.1.0) (2026-10-15)


### Features

* add portable local execution dashboard ([#191](https://github.com/Hugo-Grellier/ballast/issues/191)) ([ad6928a](https://github.com/Hugo-Grellier/ballast/commit/ad6928ab794aff787c7d52b1f551af57ca70a9d7))
* **dashboard:** rework the local execution dashboard UI/UX ([#194](https://github.com/Hugo-Grellier/ballast/issues/194)) ([87abfea](https://github.com/Hugo-Grellier/ballast/commit/87abfea3825f84dfd0b8db1c657a29cc0c964c07))


### Bug Fixes

* **admission:** require the queue coordinator on every queue mutation ([#216](https://github.com/Hugo-Grellier/ballast/issues/216)) ([8071fdf](https://github.com/Hugo-Grellier/ballast/commit/8071fdfa01df5b2b25a434b99d9d201a044da08b))
* **coordinate:** evaluate queue dependencies in batched GraphQL queries ([#213](https://github.com/Hugo-Grellier/ballast/issues/213)) ([cbd0342](https://github.com/Hugo-Grellier/ballast/commit/cbd03423ef773eba98d3860d57b1c78f40410948))
* **coordinate:** publish only a head with a completed independent review ([#217](https://github.com/Hugo-Grellier/ballast/issues/217)) ([a83f393](https://github.com/Hugo-Grellier/ballast/commit/a83f393cf492ffccfa3ae7ca3707dca709337cf0))
* **dashboard:** keep Git subprocesses out of the admission lock ([#209](https://github.com/Hugo-Grellier/ballast/issues/209)) ([063af65](https://github.com/Hugo-Grellier/ballast/commit/063af65fbb3b95da5ddb91bb64d07e54cfd102a8))
* **progress:** narrow the sensitive-text filter and accept SHA-256 revisions ([#210](https://github.com/Hugo-Grellier/ballast/issues/210)) ([adc8922](https://github.com/Hugo-Grellier/ballast/commit/adc89222402d9504c815657181eced6e80eb2ec1))
* **worker:** name checkout survivors and keep completed output ([#196](https://github.com/Hugo-Grellier/ballast/issues/196)) ([2f6d0ff](https://github.com/Hugo-Grellier/ballast/commit/2f6d0ff64efb1408769ebe34cdd9f328c9afa130))
* **worker:** report fixed blocking reasons instead of a generic failure ([#215](https://github.com/Hugo-Grellier/ballast/issues/215)) ([9e0b93f](https://github.com/Hugo-Grellier/ballast/commit/9e0b93fe777f84759e2f00e345aee8ebe817bf1a))
* **worker:** settle a timed-out or terminated worker through the interrupt path ([#230](https://github.com/Hugo-Grellier/ballast/issues/230)) ([4645074](https://github.com/Hugo-Grellier/ballast/commit/4645074f44d76bba9d1dd8d733db0aecd5cc157b))
* **worktree:** accept the ssh:// GitHub origin form ([#211](https://github.com/Hugo-Grellier/ballast/issues/211)) ([25729e2](https://github.com/Hugo-Grellier/ballast/commit/25729e2d880c900f824e8d7376b77e4f674cbb74))


### Documentation

* **migration:** explain how adopters pick up template changes ([#214](https://github.com/Hugo-Grellier/ballast/issues/214)) ([440c20e](https://github.com/Hugo-Grellier/ballast/commit/440c20ea0c2658357fa9623556770f28e635bb2c))
* **research:** Claude Code as a verified Ballast worker backend ([#226](https://github.com/Hugo-Grellier/ballast/issues/226)) ([123d50c](https://github.com/Hugo-Grellier/ballast/commit/123d50ce75cc776e9f4298d37089badc43e9ccb2))

## [2.0.0](https://github.com/Hugo-Grellier/ballast/compare/v1.1.0...v2.0.0) (2026-10-15)


### ⚠ BREAKING CHANGES

* Ballast 2.0 has no installer, trusted launcher or ballast run. Projects pinned to v1.x keep working; see docs/migration.md.

### Features

* migrate to Ballast 2.0 and retire the v1 standard ([#187](https://github.com/Hugo-Grellier/ballast/issues/187)) ([b3263c0](https://github.com/Hugo-Grellier/ballast/commit/b3263c0b3a805ce19dee83ca6a127bda3651b4cb))
* **v2:** add bounded queue ownership and recoverable execution ([#184](https://github.com/Hugo-Grellier/ballast/issues/184)) ([af4e739](https://github.com/Hugo-Grellier/ballast/commit/af4e739271123ef1425b3b8e2150f7d3698632bd))
* **v2:** establish portable workflow foundation and routing qualification ([#176](https://github.com/Hugo-Grellier/ballast/issues/176)) ([b2a77da](https://github.com/Hugo-Grellier/ballast/commit/b2a77dafe74570581f10aae507376e6e60a90f35))
* **v2:** execute standalone issues with verified worker routing ([#181](https://github.com/Hugo-Grellier/ballast/issues/181)) ([db3c97e](https://github.com/Hugo-Grellier/ballast/commit/db3c97e33b3b1a705febca2a0a48646ee9325f70))


### Documentation

* drop the Orca adapter from 2.0 and record release evidence ([#190](https://github.com/Hugo-Grellier/ballast/issues/190)) ([413d7fc](https://github.com/Hugo-Grellier/ballast/commit/413d7fca9e43ee01a91ea0da4392da9c80a544fc))

## [1.1.0](https://github.com/Hugo-Grellier/ballast/compare/v1.0.0...v1.1.0) (2026-10-14)


### Features

* **review:** declare UI states per feature in specs/&lt;feature&gt;/ui-states.toml ([#145](https://github.com/Hugo-Grellier/ballast/issues/145)) ([09fb427](https://github.com/Hugo-Grellier/ballast/commit/09fb427a0ab30a5506a0e6d530abd9ef9aa19b20))
* **workflow:** human gates are decisions, not command relays ([#162](https://github.com/Hugo-Grellier/ballast/issues/162)) ([68ef048](https://github.com/Hugo-Grellier/ballast/commit/68ef048256ac578c31407f24f4fef05389523db0))
* **workflow:** let an eligible Autonomous run mark its PR ready ([#155](https://github.com/Hugo-Grellier/ballast/issues/155)) ([d215a63](https://github.com/Hugo-Grellier/ballast/commit/d215a632b3bf074ec2cb9bea1eb673a29cf8f818))


### Bug Fixes

* **run:** make the [checks] test command pass inside an Autonomous run ([#163](https://github.com/Hugo-Grellier/ballast/issues/163)) ([578a93a](https://github.com/Hugo-Grellier/ballast/commit/578a93a6638aa9f04527ebfc35d0ff402130da18))


### Documentation

* **adr:** Autonomous runs stop only for in-run authority changes ([#157](https://github.com/Hugo-Grellier/ballast/issues/157)) ([617df9c](https://github.com/Hugo-Grellier/ballast/commit/617df9c1eab920db9874e66fe4bb5e0f83df2a08))
* **research:** measure Ballast run token cost against a sandboxed Ralph loop ([#161](https://github.com/Hugo-Grellier/ballast/issues/161)) ([0bddeb8](https://github.com/Hugo-Grellier/ballast/commit/0bddeb8ceb6b2f74b5390d2a0cfad5929ad1eca4))

## [1.0.0](https://github.com/Hugo-Grellier/ballast/compare/v0.10.0...v1.0.0) (2026-10-11)


### Bug Fixes

* **run:** remove Chat step friction found in the 1.0 pilot ([#132](https://github.com/Hugo-Grellier/ballast/issues/132)) ([7bbe966](https://github.com/Hugo-Grellier/ballast/commit/7bbe9661b729aec3a2736b272a97b241b08a6e87))
* **workflow:** name the allowed verification commands in the tasks template ([#131](https://github.com/Hugo-Grellier/ballast/issues/131)) ([7a93146](https://github.com/Hugo-Grellier/ballast/commit/7a931469e03fd56bab80e213be342c65a40d1719))


### Documentation

* **adr:** accept ADR-0017 and ADR-0018 for the 1.0 release ([#125](https://github.com/Hugo-Grellier/ballast/issues/125)) ([47f2ad6](https://github.com/Hugo-Grellier/ballast/commit/47f2ad67ba06e9706343958456b2df3caa657656))
* describe the 1.0 status in the README ([#130](https://github.com/Hugo-Grellier/ballast/issues/130)) ([7ee95a4](https://github.com/Hugo-Grellier/ballast/commit/7ee95a41335992d459cc975e64e4c4e981f04f4b))
* license Ballast under MIT ([#129](https://github.com/Hugo-Grellier/ballast/issues/129)) ([f5ca1f4](https://github.com/Hugo-Grellier/ballast/commit/f5ca1f443059dbb7458f6bb85bf78476a59979cc))


### Maintenance

* release 1.0.0 ([#128](https://github.com/Hugo-Grellier/ballast/issues/128)) ([b7dfdb0](https://github.com/Hugo-Grellier/ballast/commit/b7dfdb0f41b8adda793de4c7bb2ca10dc9d40672))

## [0.10.0](https://github.com/Hugo-Grellier/ballast/compare/v0.9.0...v0.10.0) (2026-10-07)


### Features

* **workflow:** record per-criterion checks from the agent-proposed manifest in Autonomous runs ([#122](https://github.com/Hugo-Grellier/ballast/issues/122)) ([4fc8624](https://github.com/Hugo-Grellier/ballast/commit/4fc8624e70161b6f0318f7be16d2bcb19da54fa7))


### Bug Fixes

* **run:** publish the acceptance packet for Chat runs and refresh it with checkpoint ([#119](https://github.com/Hugo-Grellier/ballast/issues/119)) ([308471d](https://github.com/Hugo-Grellier/ballast/commit/308471da7c7e54bb3b16368675b7836cb4851504))
* **workflow:** defer operator-only tasks to the PR and let a criterion map to no test ([#121](https://github.com/Hugo-Grellier/ballast/issues/121)) ([88d73eb](https://github.com/Hugo-Grellier/ballast/commit/88d73eb698baf6b2cde7034d8acdcfc13d56de10))
* **workflow:** name the one recovery after a tamper block and warn before uv creates .venv ([#120](https://github.com/Hugo-Grellier/ballast/issues/120)) ([f91b9cb](https://github.com/Hugo-Grellier/ballast/commit/f91b9cb425e10b2a6610ba6305ca434ce909c297))


### Documentation

* **adr:** accept ADR-0006 to ADR-0016 for the 1.0 release ([#116](https://github.com/Hugo-Grellier/ballast/issues/116)) ([bd09afe](https://github.com/Hugo-Grellier/ballast/commit/bd09afee8d86afc73b85d8b979c181f3dfd51a92))

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
