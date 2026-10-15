# 0009. Spell catalog in American English in every name and document

Date: 2026-10-12
Status: Accepted

## Context

ADRs 0002 to 0006 and the RFCs used the British spelling "catalogue", and
the code followed them: the module `helia_platforms.catalogue`, the class
`Catalogue`, ADR 0004's `catalogue_digest` and `Catalogue.identity()`, and
ADR 0004 section 5's entry-point group `helia_platforms.catalogues`. The
owner review of the open roadmap PRs
([#79](https://github.com/AmbiqAI/helia-platforms/issues/79#issuecomment-6133650011))
asked for American English before any consumer adopts these names. Nothing
is published yet (release PR #27 is unmerged), so no released name changes.

## Decision

Every public name and every current document spells it "catalog":

| Accepted ADRs write | The package and documents use |
|---|---|
| `helia_platforms.catalogue` (module) | `helia_platforms.catalog` |
| `Catalogue`, `Catalogue.identity()`, `Catalogue.sources` | `Catalog`, `Catalog.identity()`, `Catalog.sources` |
| `catalogue_digest` (ADR 0004 points 1 to 3, and the identity record) | `catalog_digest` |
| `CatalogueIdentity` (RFC 0002) | `CatalogIdentity` |
| entry-point group `helia_platforms.catalogues` (ADR 0004 section 5) | `helia_platforms.catalogs` |

ADRs 0001 to 0006 are immutable and keep their text; read their names
through this table. File names of ADRs and RFCs keep their spelling, so
existing links resolve. No alias for the old names is kept, since none was
released.

## Consequences

Code, tests, CLI text, package metadata, the JSON Schema title, the RFCs,
the research notes and the contributor documents change together in one
commit. A private catalog package must register under
`helia_platforms.catalogs`. New text uses "catalog"; a review that finds
"catalogue" outside an accepted ADR or a file name treats it as a typo.
