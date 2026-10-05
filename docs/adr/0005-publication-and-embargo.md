# 0005. Gate PyPI publication and choose the path to public

Date: 2026-10-05
Status: Proposed

## Context

Review item 3.1 (`docs/rfcs/0001-platform-catalogue-review.md:236-247`)
asks for a publication decision: a `release_status` per entity, a
publish-time filter, a test that no embargoed entry reaches a built wheel,
an interim distribution path, and PyPI only after the repository is public.
RFC 0002 at `c3d3e78` has since defined `release_status` and the export
filter (`docs/rfcs/0002-model-and-api.md:357-370`), defaulted overlay
entries to `embargoed` (`:461`), and ruled that unreleased SoCs never
enter this repository, so the filter is defence in depth
(`docs/rfcs/0002-private-silicon.md:7-13`).

Facts this record rests on, read on 2026-10-05:

| Fact | Source |
|---|---|
| helia-platforms, helia-aot and helia-estimator are private; helia-profiler, neuralspotx and nsx-ambiq-sdk are public | `gh repo view <repo> --json visibility` |
| helia-aot publishes every release to public PyPI from its private repository, through a trusted publisher in environment `pypi` | `AmbiqAI/helia-aot` at `1fd91daf`, `.github/workflows/release.yml:84-109`; PyPI lists `helia-aot` 0.26.0 |
| helia-profiler publishes to PyPI the same way, after a job that installs the built wheel and resolves its dependencies from PyPI; its CI runs `uv sync --locked` on pull requests | `AmbiqAI/helia-profiler` at `ed2f0a15`, `.github/workflows/publish.yml:103-167`, `.github/workflows/ci.yml:7`, `:52` |
| helia-aot, helia-profiler and neuralspotx are owned on PyPI by the organization `AITG` | `ownership.organization` in `https://pypi.org/pypi/<name>/json` |
| helia-estimator pins private helia-aot to a commit through `[tool.uv.sources]`, with PyPI as its index | `AmbiqAI/helia-estimator` at `c401807b`, `pyproject.toml:87-96` |
| `[tool.uv.sources]` is not written into a built wheel's metadata; a consumer's wheel carries only `Requires-Dist: helia-platforms>=...` | built a test project with `uv_build` and read `METADATA` |
| PyPI rejects an upload whose `Requires-Dist` is a direct URL reference | `pypi/warehouse` at `99e93777`, `warehouse/forklift/metadata.py:101-127` |
| PyPI refuses a filename that was used by a deleted file, so a published version cannot be replaced | `pypi/warehouse` at `99e93777`, `warehouse/forklift/legacy.py:1148-1161` |
| The name `helia-platforms` is unclaimed on PyPI. A pending trusted publisher does not reserve it, and anyone can register one; one registered from a PyPI organization creates the project owned by that organization | `https://pypi.org/pypi/helia-platforms/json` returns 404; PyPI docs, "Creating a PyPI project with a Trusted Publisher"; PyPI blog, 2025-11-10, "Trusted Publishers coming to orgs" |
| This repository has no `pypi` environment (only `copilot`); a workflow run that references a missing environment creates it with no protection | `gh api repos/AmbiqAI/helia-platforms/environments`; GitHub docs, "Managing environments for deployment" |
| AmbiqAI is on the Team plan, where environment required reviewers exist only for public repositories | `gh api orgs/AmbiqAI`; GitHub docs, "Deployments and environments" |
| The only rule on this repository's `main` is the organization's Copilot review ruleset. helia-aot's and helia-profiler's `main` rulesets add `pull_request` (1 and 0 required approvals, no code-owner review), `non_fast_forward` and `deletion` | `gh api repos/AmbiqAI/<repo>/rules/branches/main`; rulesets 6476665 and 17572183 |
| `uv build` at `c3d3e78` puts only `PKG-INFO`, `pyproject.toml`, `README.md`, `LICENSE.md` and `src/` in the sdist | `tar tzf` of the built sdist |
| Commits `f7b2f533` and `c0c29a44` on `main` contain maintainers' home-directory paths in `HANDOFF.md` and five research notes; the current tree has none | `git grep` over `git rev-list --all` |
| Making a repository public makes its Actions history and logs visible to everyone; commits stay reachable through pull request refs after a force-push, and GitHub Support removes those only for sensitive data; anyone with read access can see a comment's edit history | GitHub docs, "Setting repository visibility", "Removing sensitive data from a repository", "Tracking changes in a comment" |

Release PR #27 is open. Merging it makes `release_created` true, and the
`publish` job (`.github/workflows/release.yml:27-43`) would then run in an
auto-created, unprotected `pypi` environment. It fails as long as no
trusted publisher on PyPI names this repository. Anyone can register a
pending publisher naming this repository, `release.yml` and `pypi`, so an
ungated merge could publish into a PyPI project someone else owns.

## Decision

**1. Release status and the filter.** As RFC 0002 at `c3d3e78` specifies
(`docs/rfcs/0002-model-and-api.md:357-370`), with three additions:
built-in entries also default to `embargoed` when the field is omitted,
and a built-in entry that is not `public` is rejected (enforced by the
loader, ADR 0002 (#7)); the Core and Npu entities carry no status, and a
Core or Npu entry is dropped from exports when no exported Soc references
it; and, pending open question 4, the rule that unreleased entries stay
out of this repository covers every entity kind, including a new board or
add-on for a released SoC. The wheel is not filtered: an embargoed
built-in entry breaks the repository rule, so the build fails instead of
hiding it.

The test is `tests/test_distributions.py`, run in CI and in the release
build before any upload. It builds the wheel and sdist and asserts that
their file lists match an expected file list (the wheel:
`helia_platforms/**` and its `.dist-info`; the sdist: the five paths
listed in Context). It then installs the wheel into a fresh environment
with `HELIA_PLATFORMS_PATH` unset and asserts that every entry in
`builtin(include_plugins=False)` has effective status `public` and that
the filtered export equals the unfiltered one. The file-list half is a
follow-up issue that can land now; the catalogue half lands with the
loader.

Reason: the repository rule is the control; the default and the test catch
a mistake before it becomes a PyPI file that cannot be replaced.

**2. Distribution: the owner's choice.** Two paths remain.

- Public first (review 3.1): no PyPI upload until the repository is
  public. Cost: helia-aot and helia-profiler cannot adopt the package
  until an audit of unknown length (point 3) finishes.
- PyPI from the private repository, as helia-aot already does. The wheel
  and sdist are the same either way, the test in point 1 guards their
  content either way, and a published version is permanent either way.
  Cost: installers cannot read the source, the research notes the
  provenance cites, or the issue tracker until the repository is public.

Recommendation: public first, falling back to PyPI from the private
repository if the audit is not finished when adoption is otherwise ready.
Reason: adoption already waits on catalogue code, the parity tests (#13)
and the profiler maintainers' sign-off (#15), so the audit runs in
parallel and costs nothing unless it outlasts that work.

Either way, until the package is on PyPI:

- Releases stay git tags and GitHub releases in this repository.
- helia-estimator and helia-npu, which are private and not on PyPI, pin a
  tag through `[tool.uv.sources]`, as helia-estimator already pins
  helia-aot to a commit.
- helia-profiler is public, so a pin to this private repository would put
  a read token in a public repository's CI and break `uv sync --locked`
  for outside contributors. Its adoption runs only on same-repository
  branches with a scoped read token and never merges to `main`.
- helia-aot's `main` cannot take the dependency either: every release ships
  `main`, and its PyPI wheel would carry a requirement that public
  installers cannot resolve.
- The JSON Schema ships in the wheel, and `helia-platforms export
  --schema` writes it. It has no public URL until the repository is
  public; ADR 0002 (#7) and ADR 0004 (#12) defer its hosting to this
  record. Its `$id` is a `tag:` URI that need not resolve (ADR 0002 (#7)), so
  after the cutover the copy at each release tag is enough.

On either path, the first PyPI upload waits for an audit of
`src/helia_platforms/data/`: the source register's document ids and
SHA256s, provenance notes and `verified_by` logins. These ship in the
wheel, so the audit cannot wait for the repository audit in point 3 (see
ADR 0003 (#6), open question 1).

This deviates from review 3.1, which proposed adjusting consumers'
PyPI-dependent smoke tests for the interim; keeping the dependency off
those two consumers' `main` makes the adjustment unnecessary. The parity
tests run in this repository and need no consumer to depend on it.

Rejected: a private index (public helia-profiler users still cannot
install from it, and helia-estimator, the consumer that already pins a
private dependency, uses PyPI as its index); vendoring the data into
consumers (restores the copies this package exists to remove).

**3. Before the repository goes public.** If the owner chooses to make the
repository public, all of the following hold first, each recorded in one
tracking issue:

- #31 (closes #26) is merged and the local-path check passes on the tree.
- A full-history gitleaks scan is clean; today only the pre-commit hook
  runs gitleaks, and it does not scan history.
- An audit of `docs/research/`, `docs/rfcs/`, `HANDOFF.md`, the Actions
  logs, and every issue and PR body, comment and comment edit history
  decides keep, reduce or remove for: material from the internal
  datasheet library,
  including preliminary revisions (`docs/research/datasheets.md:5`,
  `:338`); the internal AmbiqSuite repository
  (`docs/research/ambiqsuite.md:3`); the internal handbook and helia-sdlc
  (`docs/research/ambiqai-conventions.md:3-6`); verbatim text from private
  helia-aot (`docs/research/helia-aot-278.md`).
- Anything that must not be public is removed from history. A force-push
  does not remove commits reachable through pull request refs, so the
  alternative is a fresh public repository created from a clean snapshot.
- The home-directory paths in `f7b2f533` and `c0c29a44` are accepted.
  Recommendation: accept; they show user names and directory layout, not
  credentials, GitHub Support would not remove the pull-request copies of
  non-sensitive data, and a rewrite breaks the commit links in #27.
- The owner confirms that every SoC, Part, Board and Implementation named
  in the tree is announced, and confirms `LICENSE.md` for public
  distribution.
- `main` has a repository ruleset with `pull_request` (one required
  approval and code-owner review), `non_fast_forward` and `deletion`.
  helia-aot and helia-profiler have the same three rules, but neither
  requires code-owner review and helia-profiler requires no approval.

The repository owner (`@apage224`, the sole entry in
`.github/CODEOWNERS:1`) signs off the checklist and decides the
visibility; an organization admin changes it.

**4. Release workflow.** The publish gate (#36) lands now,
before #27 merges: the `publish` job runs only when the repository
variable `HELIA_PLATFORMS_PYPI_PUBLISH` is `true`. The name is specific to
this repository so that an organization-level variable cannot open it. The
gate lands first because of the pending-publisher risk in Context. #27 can
then merge whenever a private 0.1.0 tag is wanted; it uses no PyPI
version. Also now: pin every action by commit SHA, as the siblings do, and
move `uv build` and the test from point 1 into a `build` job whose
distributions `publish` downloads rather than rebuilds, as helia-profiler
does. The `unverified` gate of ADR 0003 (#6), section 4, runs as a
required check on pull requests to `main`, the release-please PR
included, because a job in `release.yml` can block only the upload, not
the tag.

Before the first publish: create the `pypi` environment with a "selected
branches and tags" deployment policy naming `main` (the siblings'
protected-branches policy depends on `main`'s rules, which here are only
the Copilot review ruleset), plus a required reviewer once the repository
is public; finish the data audit in point 2; register the pending trusted
publisher from the `AITG` PyPI organization (project `helia-platforms`,
owner `AmbiqAI`, repository `helia-platforms`, workflow `release.yml`,
environment `pypi`) immediately before the first publish, or transfer the
project to `AITG` right after it; then set the variable.

## Consequences

- Under either path, helia-aot and helia-profiler ship no release that
  depends on this package until it is on PyPI.
- Private consumers' CI needs a token with read access to this repository.
- The first PyPI version will be later than the first git tag.
- Every overlay author who wants an entry exported must declare `public`.
- On acceptance, RFC 0002 needs three edits: the private-silicon rule
  widened to every entity kind (if open question 4 agrees), the
  `embargoed` default extended to built-in entries, and the Core and Npu
  drop rule in the export filter.

## Open questions

1. Must product or legal review datasheet-derived and AmbiqSuite-derived
   content before the repository goes public, in addition to the owner?
2. Which token or GitHub App gives private consumers' CI read access to
   this repository while it is private?
3. Public first, or PyPI from the private repository (point 2)? The owner
   decides.
4. Does the owner confirm the widened rule in point 1 (no unreleased
   board, add-on or memory device for a released SoC in this repository)?
5. Who in the `AITG` PyPI organization registers the pending publisher?
   Whether an `AITG` member can do so for this project is unverified.
