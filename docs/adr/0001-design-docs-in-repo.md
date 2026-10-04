# 0001. Design documents live in this repository

Date: 2026-10-04
Status: Accepted

## Context

The founding design arrived as a draft numbered in heliaAOT's RFC series.
The handbook's guidance is that product RFCs and ADRs live in the product
repository; heliaAOT keeps `mkdocs/rfcs/` and helia-ml keeps `docs/adr/`.
This repository will be public later, so its design record should be
readable without access to internal systems, and the facts it catalogues
need dated, revision-pinned source inventories that can be re-run.

## Decision

Three directories under `docs/`:

- `docs/rfcs/`: design proposals, numbered per this repository starting
  at 0001. An RFC is a living draft until accepted; its decided sections
  become ADRs.
- `docs/adr/`: accepted decisions, immutable, numbered in order of
  acceptance.
- `docs/research/`: source inventories, each naming the repository,
  revision and date it was read, so a later reader can re-verify.

`HANDOFF.md` at the root carries current state for whoever picks the work
up next. Issue drafts and other transient planning notes go in `tasks/`,
which is not committed.

## Consequences

The teammate's draft is imported as RFC 0001 with a provenance header and
is not edited in place; revisions are new sections or a new RFC. Reviews
of an RFC are separate files beside it. A docs site can be generated from
these directories later without moving anything.
