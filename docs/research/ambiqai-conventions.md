# AmbiqAI conventions: source inventory

- **Source:** aitg-handbook checkout (GitHub `AmbiqAI/aitg-handbook`); helia-sdlc checkout (local directory, not a git repo); GitHub org `AmbiqAI` via `gh`
- **Revision:** aitg-handbook `main` at `8ceb2a2`; helia-sdlc unversioned (not a git repository); GitHub state as of 2026-10-04
- **Read on:** 2026-10-04
- **Method:** Inventory from a read of the handbook and helia-sdlc plus `gh` queries; eight citations and two GitHub facts re-checked on 2026-10-04 (results under Open questions, "Citation checks").

## What it is

This note records the conventions a new AmbiqAI repo such as helia-platforms is expected to follow: where governance lives, how design records are numbered, how GitHub projects and labels are laid out, and what repo settings the sibling helia repos actually use. It is a convention inventory, not a platform-data source, so the "Platform model" and "Registered entries" sections describe records and repos instead of SoCs.

| Surface | Role | Source |
| --- | --- | --- |
| GitHub | Engineering system: issues, PRs, projects, releases | `src/content/docs/process/tools-and-systems.mdx:18-20`, `:32-34` |
| aitg-handbook | Internal governance, status, process, records | `tools-and-systems.mdx:76-81` |
| HELIA AI Developer Hub | Public products, setup, integration guidance, examples | `tools-and-systems.mdx:81` |
| Cross-system handoff | Engineering scope, evidence, release: linked GitHub issue, PR, Project item, Release. Internal declarations: Handbook record. External guidance: Developer Hub, after internal approval | `tools-and-systems.mdx:100-105` |

## Platform model (types, fields, data files)

### Handbook SDLC pages (`src/content/docs/sdlc/`)

| Page | Topic |
| --- | --- |
| `agent-practices.mdx` | Agent practices |
| `governance.mdx` | Governance and ownership |
| `versioning.mdx` | SemVer and prerelease rules (`:22`, `:78`) |
| `gates.mdx` | Risk tiers and release classes |
| `taxonomy.mdx` | Controlled taxonomy |
| `demos-and-models.mdx` | Demos and models (present; not in the prior summary) |

| Classification | Values | Source |
| --- | --- | --- |
| Risk tiers | A Exploratory, B Evaluation, C Production dependency | `gates.mdx:25-27` |
| Release classes | L0 Documentation or metadata, L1 Routine compatible release, L2 Public or declaration-changing, L3 GA or production dependency | `gates.mdx:42-45` |

### Decision records

| Location | Content | Source |
| --- | --- | --- |
| `src/content/docs/decisions/` | `index.mdx` plus 0001-0007, all handbook policy decisions (handbook stack, ownership, dual front door, structured content boundaries, licensing tiers, helia-rt 1.18.0 withdrawal, helia-rt license field of use) | directory listing |
| `decisions/index.mdx:24-25` | "Start from the repository's `templates/decision-record.md`. Every record names its review trigger, affected policy, and any decision it supersedes." | handbook |

### helia-sdlc

| Item | Content |
| --- | --- |
| `aitg-sdlc-handoff/` | 12 numbered files (`00_README.md` to `11_AGENT_STARTER_PROMPT.md`) plus `templates/` |
| `aitg-sdlc-handoff/templates/` | `compatibility-matrix.md`, `demo-readiness-checklist.md`, `deprecation-and-eol-plan.md`, `product-record.md`, `release-notes.md`, `release-readiness-review.md` |
| Other top level | `AGENT_PRACTICE_PLAN.md`, `SDLC_DOCS_STRATEGY.md`, `confluence-drafts/` |
| Repo scaffolding | No cookiecutter, no reusable workflows |

## Registered entries (table)

### Per-repo design records

| Repo | Location | Series | Note |
| --- | --- | --- | --- |
| helia-aot | `mkdocs/rfcs/` | RFC 0002, 0003 | 0001 absent; confirmed 2026-10-04 |
| helia-ml | `docs/adr/` | ADR 0001-0076 | 71 numbered files on 2026-10-04, so the range has gaps or merged numbers |
| helia-estimator | none | none | |
| helia-profiler | none | none | |
| aitg-handbook | `src/content/docs/decisions/` | 0001-0007 | Handbook policy only |

RFC numbering is per repo. The teammate's "RFC 0005" draft is not present in any repo read.

### GitHub projects

| Project | Number | Status options | Custom fields | Standard fields |
| --- | --- | --- | --- | --- |
| heliaAOT | 14 | Backlog, Ready, In progress, In review, Done | Priority (P0, P1, P2); Size (XS, S, M, L, XL) | Assignees, Labels, Milestone, Repository, Reviewers, Parent issue, Sub-issues progress |
| heliaPROFILER | 37 | identical to heliaAOT | identical | identical |
| helia-estimator | not identified | | | |

### Labels (`gh label list`, 2026-10-04)

| Label | helia-aot | helia-profiler | helia-estimator |
| --- | --- | --- | --- |
| GitHub defaults (bug, documentation, duplicate, enhancement, good first issue, help wanted, invalid, question, wontfix) | yes | yes | yes |
| `autorelease: pending`, `autorelease: tagged` (with a space after the colon) | yes | yes | no |
| `refactor` | yes | no | no |
| `priority:P0`, `priority:P1`, `priority:P2` | yes | yes | no |
| `priority:P3` | yes | yes | no |
| `agent-generated` | no | no | no |

### Repo settings (from the prior read unless noted)

| Setting | helia-aot | helia-profiler | helia-platforms |
| --- | --- | --- | --- |
| Visibility | private | public | private (confirmed via `gh`) |
| License | custom (`LICENSE.md`) | Apache-2.0 | none (empty repo) |
| Discussions | on | off | not read |
| Delete branch on merge | on | off | not read |
| Branch protection | none | `main` requires 1 review | n/a (no default branch, confirmed via `gh`) |
| release-please | `release-please-config.json`: `draft: true`, `prerelease: true` | `release-please-config.json`: `include-v-in-tag: true`, `extra-files` for version file and `uv.lock` | n/a |
| Issue / PR templates, CODEOWNERS, dependabot or renovate, `SECURITY.md`, `CODE_OF_CONDUCT` | none | none | n/a |
| Issues / projects enabled | | | yes / yes (confirmed via `gh`) |
| Empty | | | yes (confirmed via `gh`) |

| Convention | Observed |
| --- | --- |
| `CONTRIBUTING.md` | Only in helia-ml (present on 2026-10-04) |
| Branch names | `fix/###-slug`, `docs/###-slug`, `###-slug` |
| Repo names | All use the `helia-` prefix |

## Consumers / name resolution

Not applicable to this source. The equivalent question is which record wins: GitHub for engineering state, the handbook for internal declarations, the Developer Hub for public guidance (`tools-and-systems.mdx:100-105`).

## Facts it carries that the others do not

| Fact | Source |
| --- | --- |
| Risk tiers and release classes that set the evidence required per release | `gates.mdx:25-27`, `:42-45` |
| Decision-record template and required parts (review trigger, affected policy, supersession) | `decisions/index.mdx:24-25` |
| Product record, release readiness, and compatibility matrix templates | `helia-sdlc/aitg-sdlc-handoff/templates/` |
| Project field layout shared by heliaAOT and heliaPROFILER | GitHub projects 14 and 37 |

## Tooling to mirror

| Area | Convention seen in siblings |
| --- | --- |
| Release automation | release-please with `.release-please-manifest.json` (helia-aot, helia-profiler) |
| Labels | GitHub defaults plus `autorelease: *` and `priority:P0`-`P3` (helia-aot, helia-profiler) |
| Project | Status / Priority / Size layout of heliaAOT #14 and heliaPROFILER #37 |
| Design records | Per-repo numbered RFCs or ADRs in the product repo |
| Not established anywhere | Issue and PR templates, CODEOWNERS, dependency bots, `SECURITY.md`, `CODE_OF_CONDUCT`, `agent-generated` label |

## Open questions

| # | Question |
| --- | --- |
| 1 | The prior summary states the handbook guidance that product RFCs and ADRs live in the product repo. This read did not locate that sentence in the handbook; `decisions/index.mdx` only covers handbook decision records. Confirm the source. |
| 2 | Which project board does helia-estimator use, if any? |
| 3 | Should helia-platforms create the `agent-generated` label? It exists in none of the three sibling repos. |
| 4 | Should helia-platforms adopt the `priority:*` and `refactor` labels? helia-estimator has none of them and helia-profiler lacks `refactor`. |
| 5 | Branch protection, discussions, and delete-branch-on-merge differ between helia-aot and helia-profiler. Which pattern does helia-platforms follow? This is a settings decision for a human. |
| 6 | `helia-platforms/docs/rfcs/0001-platform-catalogue*.md` appeared during this session (not written by this note's author) and cite "RFC 0005: platform SSOT" (`0005-platform-ssot.md`, dated 2026-09-30) as their origin. The 0005 file itself is still not in any repo. |

### Citation checks (2026-10-04)

| Citation given | Result |
| --- | --- |
| `src/content/docs/sdlc/` pages agent-practices, governance, versioning, gates, taxonomy | Match, plus `demos-and-models.mdx` not listed in the prior summary. |
| `gates.mdx` risk tiers A/B/C | Match (lines 25-27). |
| `gates.mdx` release classes L0-L3 | Match (lines 42-45). |
| `versioning.mdx` SemVer and prerelease rules | Match (SemVer table at 22-53; "Prerelease identities and metadata" at 78). |
| `tools-and-systems.mdx`: GitHub authoritative for engineering, Handbook internal, Developer Hub public | Match (18-20, 76-81, 100-105). |
| `decisions/` 0001-0007 | Match, plus `index.mdx`. |
| helia-sdlc `aitg-sdlc-handoff` has 11 files | Mismatch. 12 numbered files (00-11) plus a `templates/` directory of 6 files (18 files total). helia-sdlc is not a git repository. |
| helia-ml `docs/adr/` 0001-0076 | Partial match. First is 0001, last is 0076, but only 71 numbered files. |
| Labels: autorelease, refactor, priority P0-P3 across the three repos; estimator lacks P3 | Mismatch (via `gh`). Names are `autorelease: pending` / `autorelease: tagged`. helia-profiler has no `refactor`. helia-estimator has only the GitHub defaults. |
| helia-platforms private, empty, no default branch, issues and projects enabled | Match (via `gh`). |
