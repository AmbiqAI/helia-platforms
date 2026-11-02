# Changelog

## 0.1.0 (2026-11-02)


### ⚠ BREAKING CHANGES

* **data:** max_outstanding in a characterization is now max_outstanding_reads.
* add the apollo4p and apollo4l built-in data ([#126](https://github.com/AmbiqAI/helia-platforms/issues/126))
* add the apollo510L and apollo330P built-in data ([#127](https://github.com/AmbiqAI/helia-platforms/issues/127))
* treat neuralspotx as a consumer, not a source ([#18](https://github.com/AmbiqAI/helia-platforms/issues/18)) (#135)

### Features

* add apollo510, its parts, apollo510_evb and the source register as built-in data ([#100](https://github.com/AmbiqAI/helia-platforms/issues/100)) ([e486f0a](https://github.com/AmbiqAI/helia-platforms/commit/e486f0a6bd57889286e4176a2eb7e935ce03ac3b))
* add check-sources, which compares the built-in data with the snapshots ([#109](https://github.com/AmbiqAI/helia-platforms/issues/109)) ([fbbe8c5](https://github.com/AmbiqAI/helia-platforms/commit/fbbe8c5866cbd1ebc0b3fee15b2a473c8942796d))
* add the apollo3 and apollo3p built-in data ([#128](https://github.com/AmbiqAI/helia-platforms/issues/128)) ([3e822b1](https://github.com/AmbiqAI/helia-platforms/commit/3e822b1513cbca457ecc0771362ffe4c4dea05ae))
* add the apollo4p and apollo4l built-in data ([#126](https://github.com/AmbiqAI/helia-platforms/issues/126)) ([93b3f2c](https://github.com/AmbiqAI/helia-platforms/commit/93b3f2c746115d5851679fb2414495fa379d60a5))
* add the apollo510L and apollo330P built-in data ([#127](https://github.com/AmbiqAI/helia-platforms/issues/127)) ([a42a086](https://github.com/AmbiqAI/helia-platforms/commit/a42a08601a07fddb276f84e66bc70d52d907481c))
* add the JSON export, its release-status filter and its schema ([#108](https://github.com/AmbiqAI/helia-platforms/issues/108)) ([db9b3ed](https://github.com/AmbiqAI/helia-platforms/commit/db9b3ed3ce5ef7bb331aa4bf9570bdb4b682a92f))
* add the list and show CLI commands ([#105](https://github.com/AmbiqAI/helia-platforms/issues/105)) ([b8edd67](https://github.com/AmbiqAI/helia-platforms/commit/b8edd67a945b5ce6d513ec63f148075a08dbbaa4))
* add the Markdown pages and the release assets to export ([#111](https://github.com/AmbiqAI/helia-platforms/issues/111)) ([42aaf9d](https://github.com/AmbiqAI/helia-platforms/commit/42aaf9d548c8c95b3259b5b7651603781cd7cfd3))
* apply clock caps, FVP memory maps and subset limits when realizing an Implementation ([#82](https://github.com/AmbiqAI/helia-platforms/issues/82)) ([e78bfaf](https://github.com/AmbiqAI/helia-platforms/commit/e78bfaf531cb30ae0f96dc90f14220bdd9d7a620))
* carry an FPGA Implementation on a Board of category fpga ([#104](https://github.com/AmbiqAI/helia-platforms/issues/104)) ([#132](https://github.com/AmbiqAI/helia-platforms/issues/132)) ([8a92d25](https://github.com/AmbiqAI/helia-platforms/commit/8a92d256c7994d580862d7fb11db055336b2d7e5))
* compute catalog_digest and the overlay source hash (ADR 0004) ([#95](https://github.com/AmbiqAI/helia-platforms/issues/95)) ([aaaac3f](https://github.com/AmbiqAI/helia-platforms/commit/aaaac3fed21fe2051d3c0e64ef2f2f2840156037))
* **data:** add atomiq110, its FPGA Implementation and the FPGA board ([#68](https://github.com/AmbiqAI/helia-platforms/issues/68)) ([#133](https://github.com/AmbiqAI/helia-platforms/issues/133)) ([2827be5](https://github.com/AmbiqAI/helia-platforms/commit/2827be568491af985677f5260bc7a73957dc1872))
* **data:** add the apollo510b built-in data ([#125](https://github.com/AmbiqAI/helia-platforms/issues/125)) ([b687ce0](https://github.com/AmbiqAI/helia-platforms/commit/b687ce06bfd1a44a12345a6681cede0dab395fd4))
* enforce RFC 0002's remaining semantic validation rules ([#84](https://github.com/AmbiqAI/helia-platforms/issues/84)) ([1de168c](https://github.com/AmbiqAI/helia-platforms/commit/1de168c64cef35013cd6ddf5dac1bf38e81e6085))
* extract and commit the ADR 0006 source snapshots, with their CI jobs ([#86](https://github.com/AmbiqAI/helia-platforms/issues/86)) ([2ecd326](https://github.com/AmbiqAI/helia-platforms/commit/2ecd32621b7359e17027503cbb0ba7a5e097f872))
* load the ADR 0002 file format into a frozen runtime model ([#49](https://github.com/AmbiqAI/helia-platforms/issues/49)) ([af7482b](https://github.com/AmbiqAI/helia-platforms/commit/af7482b7dfe82aa28d7e41a0029d4e8626bc7f6b))
* load the packaged data and side-load private catalogues in builtin() ([#85](https://github.com/AmbiqAI/helia-platforms/issues/85)) ([d0d0153](https://github.com/AmbiqAI/helia-platforms/commit/d0d0153e36f700666d1c45d31ebe950e9f0f7562))
* record the applied sources in Catalog.identity() (ADR 0004) ([#97](https://github.com/AmbiqAI/helia-platforms/issues/97)) ([26202a0](https://github.com/AmbiqAI/helia-platforms/commit/26202a0fbf99ad7506d4a029c07ee33bc81c3797))
* resolve names to a Target and answer RFC 0002's queries on it ([#98](https://github.com/AmbiqAI/helia-platforms/issues/98)) ([9bc06b5](https://github.com/AmbiqAI/helia-platforms/commit/9bc06b5a9a7e67b32d4cfd52e158c863e3011e6a))
* state the catalog's scope as facts, not policy (ADR 0010) ([#148](https://github.com/AmbiqAI/helia-platforms/issues/148)) ([0735a9d](https://github.com/AmbiqAI/helia-platforms/commit/0735a9d3f539a163936fb2935c501dcf3f6353a4))
* treat neuralspotx as a consumer, not a source ([#18](https://github.com/AmbiqAI/helia-platforms/issues/18)) ([#135](https://github.com/AmbiqAI/helia-platforms/issues/135)) ([b414aa9](https://github.com/AmbiqAI/helia-platforms/commit/b414aa9d6bba579a08dc0589f76f8ea8083960a3))
* use typer for the CLI ([#25](https://github.com/AmbiqAI/helia-platforms/issues/25)) ([c0c29a4](https://github.com/AmbiqAI/helia-platforms/commit/c0c29a4468a7b3471e9e6a562b9357eb422542ed)), closes [#23](https://github.com/AmbiqAI/helia-platforms/issues/23)
* validate provenance records against the source register and gate unverified values ([#99](https://github.com/AmbiqAI/helia-platforms/issues/99)) ([53073ca](https://github.com/AmbiqAI/helia-platforms/commit/53073ca1a73965fc3280d4952b8b27b3e84c0552))


### Bug Fixes

* close false negatives in the local-paths hook ([#54](https://github.com/AmbiqAI/helia-platforms/issues/54)) ([4c7bfce](https://github.com/AmbiqAI/helia-platforms/commit/4c7bfce5b385f09b9e77c7da1baed76197e2347d))
* fold case in Target's name lookups and print whole trace clocks as int ([#107](https://github.com/AmbiqAI/helia-platforms/issues/107)) ([4fbd16a](https://github.com/AmbiqAI/helia-platforms/commit/4fbd16a24eacae42cac247ec97a16f3ab6995cb4))
* give the pairs a subset's access_removed lists their records ([#113](https://github.com/AmbiqAI/helia-platforms/issues/113)) ([93dee1d](https://github.com/AmbiqAI/helia-platforms/commit/93dee1d6e668101872c02e0217b077fd77a5dfdd))
* leave external devices with no base out of placement_ranges ([#119](https://github.com/AmbiqAI/helia-platforms/issues/119)) ([510cd89](https://github.com/AmbiqAI/helia-platforms/commit/510cd8924ba398cb2e7941234bd9470e3041d61b))
* read atomiq110's XSPI apertures as external memory in check-sources ([#123](https://github.com/AmbiqAI/helia-platforms/issues/123)) ([3c9cb83](https://github.com/AmbiqAI/helia-platforms/commit/3c9cb8311bf1df15a4605a9fb6aa2438345ec888))
* stop allow-list reasons being cut off at an unquoted # ([#146](https://github.com/AmbiqAI/helia-platforms/issues/146)) ([e4aa7f8](https://github.com/AmbiqAI/helia-platforms/commit/e4aa7f89aedd6b5e40f2209a9ff7edc4231a383b))
* stop the JSON Schema accepting a wrapped value inside a {value, provenance} wrapper ([#140](https://github.com/AmbiqAI/helia-platforms/issues/140)) ([#143](https://github.com/AmbiqAI/helia-platforms/issues/143)) ([0326aed](https://github.com/AmbiqAI/helia-platforms/commit/0326aedc1bae52e9885b8ffc935274050ec251f3))


### Documentation

* accept ADRs 0002 to 0006 and apply their RFC edits ([#50](https://github.com/AmbiqAI/helia-platforms/issues/50)) ([847c9e8](https://github.com/AmbiqAI/helia-platforms/commit/847c9e8325bc9c214f23c0f080db78b9ae3c9eeb))
* accept ADRs 0007, 0008 and 0009 ([#101](https://github.com/AmbiqAI/helia-platforms/issues/101)) ([455d20b](https://github.com/AmbiqAI/helia-platforms/commit/455d20bc6c45783667eb3a5972bf9b035368d115))
* accept RFC 0002 and RFC 0003 ([#124](https://github.com/AmbiqAI/helia-platforms/issues/124)) ([0bd3808](https://github.com/AmbiqAI/helia-platforms/commit/0bd38081176bb92b3b8ed43a13ab0aaa601eb743))
* add per-path CODEOWNERS entries and a fact-change PR template ([#52](https://github.com/AmbiqAI/helia-platforms/issues/52)) ([669aafb](https://github.com/AmbiqAI/helia-platforms/commit/669aafb64540019810860f064646baf12f02d0ec))
* budget heliaAOT from physical RAM and usable NVM in RFC 0002 ([#37](https://github.com/AmbiqAI/helia-platforms/issues/37)) ([1ff670d](https://github.com/AmbiqAI/helia-platforms/commit/1ff670d78155b63fdd078c4504afbf3607745dc1))
* check helia-profiler capacities against link environments in RFC 0002 ([#92](https://github.com/AmbiqAI/helia-platforms/issues/92)) ([d2f1cd9](https://github.com/AmbiqAI/helia-platforms/commit/d2f1cd9fa65e8b93224becd09708943cfa3d6dc9))
* complete the PSRAM pending corrections in RFC 0002 ([#34](https://github.com/AmbiqAI/helia-platforms/issues/34)) ([3baa5b0](https://github.com/AmbiqAI/helia-platforms/commit/3baa5b064d7e47df6e0bb83653205f746fb123e9))
* correct the atomiq110_fpga_turbo trace clock in RFC 0002 ([#33](https://github.com/AmbiqAI/helia-platforms/issues/33)) ([60ec9a3](https://github.com/AmbiqAI/helia-platforms/commit/60ec9a3f3f281ba4138b72f235338c873deb3ff6))
* fix RFC 0002 and RFC 0003 text that later decisions made stale ([#110](https://github.com/AmbiqAI/helia-platforms/issues/110)) ([b723246](https://github.com/AmbiqAI/helia-platforms/commit/b723246129c3b51bbc11d388c8c209908d7c02cf))
* propose ADR 0002, ship the catalogue as YAML data with a generated JSON Schema and a stdlib dataclass runtime ([#39](https://github.com/AmbiqAI/helia-platforms/issues/39)) ([e1fe49d](https://github.com/AmbiqAI/helia-platforms/commit/e1fe49da33daebf85918fc62c274992dd023ade8))
* propose ADR 0003, record provenance per fact with a closed status vocabulary ([#40](https://github.com/AmbiqAI/helia-platforms/issues/40)) ([8e0dccc](https://github.com/AmbiqAI/helia-platforms/commit/8e0dccc0dd006f97b3df27e13a378cc61f181f02))
* propose ADR 0004, version the schema separately and ship value corrections as patches ([#41](https://github.com/AmbiqAI/helia-platforms/issues/41)) ([2060e92](https://github.com/AmbiqAI/helia-platforms/commit/2060e92f478f95285316f72de536723887d2bdbd))
* propose ADR 0005, gate PyPI publication and choose the path to public ([#42](https://github.com/AmbiqAI/helia-platforms/issues/42)) ([98d5129](https://github.com/AmbiqAI/helia-platforms/commit/98d512901cc952e49f6b3ebbd752a0b96665899e))
* propose ADR 0006, check the catalogue against committed source snapshots ([#43](https://github.com/AmbiqAI/helia-platforms/issues/43)) ([4bc4dea](https://github.com/AmbiqAI/helia-platforms/commit/4bc4deadd831a8b117cfaf5b9ba9a252a058a674))
* propose RFC 0003, the JSON export and generated catalogue pages ([#55](https://github.com/AmbiqAI/helia-platforms/issues/55)) ([edac308](https://github.com/AmbiqAI/helia-platforms/commit/edac308a9873011b2a14da9478883d05a1e421b8))
* re-pin RFC 0003's [#49](https://github.com/AmbiqAI/helia-platforms/issues/49) citations to its merge commit and fix the sources key ([#94](https://github.com/AmbiqAI/helia-platforms/issues/94)) ([ea12b9f](https://github.com/AmbiqAI/helia-platforms/commit/ea12b9fd1371b8334a1cbc7ed44988d6e6d42348))
* record that the pypi environment exists ([#112](https://github.com/AmbiqAI/helia-platforms/issues/112)) ([2353280](https://github.com/AmbiqAI/helia-platforms/commit/2353280af344d43c2a2a9b5c713e435e113a98c2))
* rewrite HANDOFF.md for the current state ([#81](https://github.com/AmbiqAI/helia-platforms/issues/81)) ([e2cdec1](https://github.com/AmbiqAI/helia-platforms/commit/e2cdec154022ade4967dd39bfdf48d541142b044))
* rewrite the README for the first PyPI release ([#147](https://github.com/AmbiqAI/helia-platforms/issues/147)) ([153b945](https://github.com/AmbiqAI/helia-platforms/commit/153b945284fa9ea60a5bb311a46d16ab927502b9))
* RFC 0002 platform model and API, with consumer research ([#24](https://github.com/AmbiqAI/helia-platforms/issues/24)) ([c3d3e78](https://github.com/AmbiqAI/helia-platforms/commit/c3d3e78b0f11c03850661e5b25bdaf53b9765b5d)), closes [#22](https://github.com/AmbiqAI/helia-platforms/issues/22) [#3](https://github.com/AmbiqAI/helia-platforms/issues/3) [#4](https://github.com/AmbiqAI/helia-platforms/issues/4) [#8](https://github.com/AmbiqAI/helia-platforms/issues/8) [#9](https://github.com/AmbiqAI/helia-platforms/issues/9) [#10](https://github.com/AmbiqAI/helia-platforms/issues/10) [#20](https://github.com/AmbiqAI/helia-platforms/issues/20)
* type trace_clock_mhz as int or float and drop the heliaAOT PSRAM capability from RFC 0002 ([#118](https://github.com/AmbiqAI/helia-platforms/issues/118)) ([86ec119](https://github.com/AmbiqAI/helia-platforms/commit/86ec11920f1a3003ebd44f81394b8545c1a1727e))
* verify RFC 0001 appendix D and J against pinned sources ([#38](https://github.com/AmbiqAI/helia-platforms/issues/38)) ([5b1a97d](https://github.com/AmbiqAI/helia-platforms/commit/5b1a97dfea7eb4f03e49e4492db33ec3ab97dba2))
