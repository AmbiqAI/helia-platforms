# Architecture decision records

One file per decision, numbered in order of acceptance, never renumbered.
A record states the context, the decision, and the consequences, in that
order, and is immutable once accepted; a later record supersedes it.

Design proposals that are still being argued live in `docs/rfcs/`. When an
RFC section is decided, the decision gets a record here and the RFC links
to it. Source inventories that decisions cite live in `docs/research/`.

Use `0000-template.md`. Status values: Proposed, Accepted, Superseded by
NNNN, Rejected.

| ADR | Title | Status |
|---|---|---|
| 0001 | Design documents live in this repository | Accepted |
| 0002 | Ship the catalogue as YAML data with a generated JSON Schema and a stdlib dataclass runtime | Accepted |
| 0003 | Record provenance per fact with a closed status vocabulary | Accepted |
| 0004 | Version the schema separately and ship data corrections as patches | Accepted |
| 0005 | Gate PyPI publication and choose the path to public | Accepted |
| 0006 | Check the catalogue against committed source snapshots | Accepted |
| 0007 | Model an FVP's memories as its own list, not as substitutions | Proposed |
| 0008 | Mark a Soc's memory controllers in a list of their own | Proposed |
| 0009 | Spell catalog in American English in every name and document | Proposed |
