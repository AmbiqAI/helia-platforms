# RFCs

Design RFCs for helia-platforms. Numbering restarts at 0001 in this
repository (ADR 0001).

| Document | Status | Reading order |
| --- | --- | --- |
| [0001-platform-catalogue.md](0001-platform-catalogue.md): the catalog, its data and the rollout plan | Draft | 1 |
| [0001-platform-catalogue-appendix.md](0001-platform-catalogue-appendix.md): data, sources and line-level detail for RFC 0001 | Under revision | Reference, as needed |
| [0001-platform-catalogue-review.md](0001-platform-catalogue-review.md): weaknesses of RFC 0001 and proposed revisions, with the owner direction | Review | 2 |
| [0002-model-and-api.md](0002-model-and-api.md): the platform model and the API the package exposes | Draft | 3 |
| [0002-multicore.md](0002-multicore.md): multiple cores and accelerators, the access matrix, image slots and clock domains (part of RFC 0002) | Draft | 4 |
| [0002-private-silicon.md](0002-private-silicon.md): side-loading private and future silicon from private packages and overlay files (part of RFC 0002) | Draft | 5 |
| [0002-migration.md](0002-migration.md): RFC 0002's migration and output changes per consumer, pending data corrections, parity tests and the helia-aot#278 mapping | Draft | 6 |
| [0003-export-and-pages.md](0003-export-and-pages.md): the JSON export of the filtered catalog, its schema, the one publishable path and the generated per-SoC and per-board pages; resolved per-target records are deferred | Draft | 7 |

RFC 0001 proposed the catalog and was imported from a heliaAOT draft.
The review lists its weaknesses and records the owner direction. RFC 0002
builds on both and on helia-aot#278, and defines the model and API. RFC
0001 stands until RFC 0002 is accepted; on acceptance, the sections listed
in RFC 0002's "Changes relative to RFC 0001" table are superseded, and RFC
0001's appendix remains the reference for the data and its sources.

RFC 0003 designs the JSON export and the Markdown pages that RFC 0002
names in its export section.
