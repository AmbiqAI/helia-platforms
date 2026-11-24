# Changelog

## [0.3.0](https://github.com/AmbiqAI/helia-platforms/compare/v0.2.0...v0.3.0) (2026-11-24)


### ⚠ BREAKING CHANGES

* **data:** resolving apollo4p_evb_disp_shield_rev2 or AMAP4PDISP no longer gives the MSPI1 flash region (flash0) or the flash capability, and its mspi0 offers hex-ddr instead of octal-ddr. Pass addons=["apollo4p_disp_shield"] on apollo4p_evb for the octal setting.
* an overlay that writes `port` on an access entry no longer loads; remove the key.

### Features

* **data:** model the Display Kit's two GPIO34 settings, with hex as the default ([#182](https://github.com/AmbiqAI/helia-platforms/issues/182)) ([9715cc6](https://github.com/AmbiqAI/helia-platforms/commit/9715cc6199e027f7a6cbeb065bafa7483f9e11cb))
* **data:** model the fitted eMMC on apollo510_evb, apollo510b_evb and the Apollo4 Plus Display Kit ([#184](https://github.com/AmbiqAI/helia-platforms/issues/184)) ([c40f86e](https://github.com/AmbiqAI/helia-platforms/commit/c40f86ea0e9f60b5ee59343bcc59ac67268748e3))
* **data:** record the BLE controller's reset pad on the Apollo4 Blue parts ([#170](https://github.com/AmbiqAI/helia-platforms/issues/170)) ([35ce183](https://github.com/AmbiqAI/helia-platforms/commit/35ce18342d5d080b2f3cd1cf99a73a1e5f17a107)), closes [#157](https://github.com/AmbiqAI/helia-platforms/issues/157)
* **data:** record the Cortex-M55 PMU's counters and events, and define what a missing cache size means ([#171](https://github.com/AmbiqAI/helia-platforms/issues/171)) ([34da346](https://github.com/AmbiqAI/helia-platforms/commit/34da346fd3abeaaed54312b0ecd51c0011b12f6b)), closes [#158](https://github.com/AmbiqAI/helia-platforms/issues/158)
* **data:** record the D-cache line, the hex DDR DMA address alignment and the deep-sleep DMA restriction ([#176](https://github.com/AmbiqAI/helia-platforms/issues/176)) ([da37de0](https://github.com/AmbiqAI/helia-platforms/commit/da37de0f911cff4b6c3589077b9bce4545c501d4)), closes [#175](https://github.com/AmbiqAI/helia-platforms/issues/175)
* **data:** record whether each Soc's SDK HAL provides am_hal_pwrctrl_rss_pwroff() ([#183](https://github.com/AmbiqAI/helia-platforms/issues/183)) ([d7f54c1](https://github.com/AmbiqAI/helia-platforms/commit/d7f54c1a57531cf83e9024de19913eadd2b75600))
* let an add-on require a board revision with fits_revisions ([#181](https://github.com/AmbiqAI/helia-platforms/issues/181)) ([fe4c964](https://github.com/AmbiqAI/helia-platforms/commit/fe4c964eb2d077b7b46082e81690546cfdf1a6bb))
* name each identity source's full label so a consumer can match it to entries ([#179](https://github.com/AmbiqAI/helia-platforms/issues/179)) ([943f140](https://github.com/AmbiqAI/helia-platforms/commit/943f1400899f5e41181444bded8e7177fc27174f))
* remove the deprecated Access.port key from the file format ([#174](https://github.com/AmbiqAI/helia-platforms/issues/174)) ([c08793f](https://github.com/AmbiqAI/helia-platforms/commit/c08793fd90f1a98753646c194feafd9cf996deb4)), closes [#159](https://github.com/AmbiqAI/helia-platforms/issues/159)


### Bug Fixes

* **data:** record that atomiq110's NPU access to ITCM and DTCM keeps the CM55 awake ([#178](https://github.com/AmbiqAI/helia-platforms/issues/178)) ([3a12877](https://github.com/AmbiqAI/helia-platforms/commit/3a128772153daa01bdf4f033ae04f530fc933247))
* **data:** use 32 MB HBLRAM for AT110 planning; preserve FPGA exclusion ([#180](https://github.com/AmbiqAI/helia-platforms/issues/180)) ([9b1b30b](https://github.com/AmbiqAI/helia-platforms/commit/9b1b30b41ba03c14e02b42ed37fa8576bf2d9f6f))

## [0.2.0](https://github.com/AmbiqAI/helia-platforms/compare/v0.1.0...v0.2.0) (2026-11-08)


### ⚠ BREAKING CHANGES

* record the NPU's AXI port classes and its crossbar reach, and drop Access.port ([#163](https://github.com/AmbiqAI/helia-platforms/issues/163))

### Features

* answer where an application may go with Target.application_ranges(), and keep linker windows with the consumers ([#164](https://github.com/AmbiqAI/helia-platforms/issues/164)) ([da5519b](https://github.com/AmbiqAI/helia-platforms/commit/da5519b8a420df1c63c16875c9e2ccd7d6da79b2))
* **data:** record the Apollo5 DMA boundaries ([#155](https://github.com/AmbiqAI/helia-platforms/issues/155)) ([f9eb648](https://github.com/AmbiqAI/helia-platforms/commit/f9eb648452651ff6629eceadd808bed2bcd74429)), closes [#153](https://github.com/AmbiqAI/helia-platforms/issues/153)
* keep based_on on loaded entries and walk it with Catalog.lineage() ([#162](https://github.com/AmbiqAI/helia-platforms/issues/162)) ([19ce920](https://github.com/AmbiqAI/helia-platforms/commit/19ce920ac8ece5da6d7cc999a6fb7982d5a82b09)), closes [#134](https://github.com/AmbiqAI/helia-platforms/issues/134)
* record the DMA boundary of a memory region (ADR 0011) ([#154](https://github.com/AmbiqAI/helia-platforms/issues/154)) ([0977344](https://github.com/AmbiqAI/helia-platforms/commit/0977344e9bf87e1986c2c8f4452037b58907f9a5)), closes [#153](https://github.com/AmbiqAI/helia-platforms/issues/153)
* record the NPU's AXI port classes and its crossbar reach, and drop Access.port ([#163](https://github.com/AmbiqAI/helia-platforms/issues/163)) ([4276cfc](https://github.com/AmbiqAI/helia-platforms/commit/4276cfcda08552ff0a68725d7dfdb8032f339746))

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
