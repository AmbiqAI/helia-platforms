# 0005. Gate PyPI publication and choose the path to public

Date: 2026-10-05
Status: Accepted; amended 2026-10-29 (#77)

## Amendment, 2026-10-29: PyPI from the private repository (#77)

The owner decided on 2026-10-29, for the 0.1.0 release:

- **Path (point 2, open question 3):** PyPI from the private repository,
  starting with 0.1.0. This repository stays private; point 3 still
  applies if the code goes public later.
- **Review (open question 1):** the owner's audit of
  `src/helia_platforms/data/` (point 2) is the only review before an
  upload. No product or legal review is required.
- **Token (open question 2):** not needed once 0.1.0 is on PyPI, since
  private consumers install from PyPI like the public ones.
- **Widened rule (open question 4):** confirmed. No unreleased Soc,
  Implementation, Part, Board, AddOn or MemoryDevice enters this
  repository, including a new board or add-on for a released Soc.
- **Trusted publisher (open question 5):** an owner of the `AITG` PyPI
  organization added it, as point 4 describes.

Of point 4's steps before the first publish, the required reviewer on
`pypi` does not apply while the repository is private (Context: the Team
plan offers none). The data audit stays a precondition, and the variable
is set to `true` after it. Point 4's other changes are made: every action
is pinned by commit SHA, and a `build` job builds and tests the
distributions that `publish` downloads and uploads.

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
| Maintainers' local home-directory paths are in `HANDOFF.md` and research notes in `f7b2f533` and `c0c29a44` on `main`, and in `6201f4de` and `3f966f3d`, reached only from `refs/pull/24/head` and `refs/pull/25/head` respectively; `6201f4de` also names an internal source location. The atomiq110 energy coefficients from helia-estimator are in `docs/research/helia-estimator.md` (`f7b2f533:56-70`) in those four commits and in `0a63a1f2`. The branches of #24 and #25 are deleted; their heads are those two pull request refs. `c3d3e78` contains neither the paths nor the coefficients | `git grep` over `git rev-list --all` after fetching `refs/pull/*/head`; `gh pr view <n> --json headRefOid` |
| A repository variable overrides an organization variable of the same name, but an organization variable shared with the repository applies when no repository variable exists. Neither a repository variable nor a shared organization variable exists here | GitHub docs, "Variables reference", configuration variable precedence; `gh api repos/AmbiqAI/helia-platforms/actions/variables` and `.../actions/organization-variables` |
| A pending publisher is invalidated if someone else creates the project first | PyPI docs, "Creating a PyPI project with a Trusted Publisher" |
| Making a repository public makes its Actions history and logs visible to everyone; commits stay reachable through pull request refs after a force-push, and GitHub Support removes those only for sensitive data; anyone with read access can see a comment's edit history | GitHub docs, "Setting repository visibility", "Removing sensitive data from a repository", "Tracking changes in a comment" |

Release PR #27 is open. Merging it makes `release_created` true, and the
`publish` job (`.github/workflows/release.yml:27-43`) would then run in an
auto-created, unprotected `pypi` environment. It fails as long as no
trusted publisher on PyPI names this repository. Anyone can register a
pending publisher naming this repository, `release.yml` and `pypi`, so an
ungated merge could publish into a PyPI project someone else owns.

While the name is unclaimed, anyone can also upload `helia-platforms` at
a high version such as 99.0. A consumer's wheel carries only
`Requires-Dist: helia-platforms>=...`, and an installer that does not read
`[tool.uv.sources]`, such as pip installing a consumer's wheel or git URL,
would then install that upload. `uv sync` in the consumer's own
repository reads `[tool.uv.sources]` and installs the pinned tag.

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

On either path, the first PyPI upload with catalogue content waits for
an audit of `src/helia_platforms/data/`: the source register's document
ids and SHA256s, provenance notes and `verified_by` logins. These ship in
the wheel, so the audit cannot wait for the repository audit in point 3
(see ADR 0003 (#6), open question 1).

This deviates from review 3.1, which proposed adjusting consumers'
PyPI-dependent smoke tests for the interim; keeping the dependency off
those two consumers' `main` makes the adjustment unnecessary. The parity
tests run in this repository and need no consumer to depend on it.

Rejected: a private index (public helia-profiler users still cannot
install from it, and helia-estimator, the consumer that already pins a
private dependency, uses PyPI as its index); vendoring the data into
consumers (restores the copies this package exists to remove).

The name is not claimed on PyPI yet: nothing is uploaded, not even a
placeholder, until the owner chooses a path. Until then a consumer
installs this package only through `uv sync --locked` with a tag pinned in
`[tool.uv.sources]`, and no consumer release or documented `pip install`
depends on it. That keeps the 99.0 risk in Context from reaching anyone,
because pip never resolves `helia-platforms` from PyPI. The cost is that
someone else can take the name first; claiming it is part of the first
publication (point 4).

**3. Going public.** If the owner chooses to make the code public, it
goes public as a fresh repository built from a squashed, audited snapshot
of this repository's `main`, and this repository stays private. A
force-push leaves commits reachable through pull request refs (Context),
so rewriting this repository's history in place cannot remove them. The
fresh repository starts with no issues, pull requests or Actions logs.
Before it is created, all of the following hold, each recorded in one
tracking issue:

- #31 (closes #26) is merged and the local-path check passes on the
  snapshot.
- The inventory runs over every commit in `git rev-list --all` after
  fetching `refs/pull/*/head`, so it covers pull request heads and the
  commits of deleted branches as well as `main`. It names at least the
  local home-directory paths in `f7b2f533`, `c0c29a44`, `6201f4de` and
  `3f966f3d`, the internal source location in `6201f4de`, and the
  atomiq110 energy coefficients from helia-estimator in
  `docs/research/helia-estimator.md` (`f7b2f533:56-70` and the other
  commits listed in Context), and confirms that the snapshot contains
  none of them.
- gitleaks finds nothing in the snapshot, and every secret it finds in
  the inventory's commits has been revoked; today only the pre-commit
  hook runs gitleaks, and it does not scan history.
- An audit of the snapshot's `docs/research/`, `docs/rfcs/` and
  `HANDOFF.md` decides keep, reduce or remove for: material from the
  internal datasheet library, including preliminary revisions
  (`docs/research/datasheets.md:5`, `:338`); the internal AmbiqSuite
  repository (`docs/research/ambiqsuite.md:3`); the internal handbook and
  helia-sdlc (`docs/research/ambiqai-conventions.md:3-6`); verbatim text
  from private helia-aot (`docs/research/helia-aot-278.md`). Issues, pull
  requests, comments and Actions logs stay in this private repository.
- Issue references such as `(#7)` in the snapshot become links to this
  repository or are removed, because the fresh repository numbers its
  issues from 1.
- The owner confirms that every SoC, Part, Board and Implementation named
  in the snapshot is announced, and confirms `LICENSE.md` for public
  distribution.
- The fresh repository's `main` has a repository ruleset with
  `pull_request` (one required approval and code-owner review),
  `non_fast_forward` and `deletion`. helia-aot and helia-profiler have the
  same three rules, but neither requires code-owner review and
  helia-profiler requires no approval.
- The `pypi` environment, its deployment policy and the
  `HELIA_PLATFORMS_PYPI_PUBLISH` variable from point 4 exist on the fresh
  repository, since creating a repository copies none of them, and the
  PyPI trusted publisher names the fresh repository.

The repository owner (`@apage224`, the first owner on every line of
`.github/CODEOWNERS`) signs off the checklist and decides whether to go
public; an organization admin creates the fresh repository.

**4. Release workflow.** The publish gate (#36) lands now, before #27
merges: the `publish` job runs only when the variable
`HELIA_PLATFORMS_PYPI_PUBLISH` is `true`. The name is specific to this
repository so that an organization variable meant for another repository
does not open the gate. An organization variable with this exact name
that is shared with this repository would still open it when no
repository variable exists (Context), so the repository variable is
created now with value `false`, which overrides any organization value
(tracked in #45).
The gate lands first because of the pending-publisher risk in Context.

Also now, tracked in #45: create the `pypi` environment with a "selected
branches and tags" deployment policy naming only `main`, so that a job on
another branch cannot deploy to it and the trusted publisher, which names
`pypi`, accepts uploads only from `main`. Until then the gate exists only
in workflow content. The siblings' protected-branches policy is not
enough here, because that policy depends on the rules on `main`, and this
repository's `main` has only the Copilot review ruleset.
Done 2026-10-19 (#45): the `pypi` environment has that policy, with `main`
its only branch rule, and the repository variable is `false`
(`gh api repos/AmbiqAI/helia-platforms/environments/pypi`,
`gh variable list`). Repository admins can still bypass the policy.

#27 can then merge whenever a private 0.1.0 tag is wanted; it uses no
PyPI version. Also now: pin every action by commit SHA, as the siblings
do, and move `uv build` and the test from point 1 into a `build` job
whose distributions `publish` downloads rather than rebuilds, as
helia-profiler does. The `unverified` gate of ADR 0003 (#6), section 4,
runs as a required check on pull requests to `main`, because a job in
`release.yml` can block only the upload, not the tag. Release-please's
pull requests run no workflows, so a maintainer merges them by bypass
(ADR 0003 (#6), section 4).

Before the first publish with catalogue content: add a required reviewer
to `pypi` once a public repository exists; finish the data audit in point
2; add the trusted publisher (owner `AmbiqAI`, repository
`helia-platforms`, workflow `release.yml`, environment `pypi`) from the
`AITG` PyPI organization, which creates the project under `AITG` if the
name is still free; then set the variable to `true`.

## Consequences

- Under either path, helia-aot and helia-profiler ship no release that
  depends on this package until it is on PyPI.
- Private consumers' CI needs a token with read access to this repository.
- The first PyPI version with catalogue content will be later than the
  first git tag.
- Until the first publish, the name `helia-platforms` can be taken by
  someone else on PyPI.
- Going public creates a new repository. This repository's issues, pull
  requests and commit links stay private.
- Every overlay author who wants an entry exported must declare `public`.
- On acceptance, RFC 0002 needs three edits: the private-silicon rule
  widened to every entity kind (if open question 4 agrees), the
  `embargoed` default extended to built-in entries, and the Core and Npu
  drop rule in the export filter.

## Open questions

1. Must product or legal review datasheet-derived and AmbiqSuite-derived
   content before the repository goes public, in addition to the owner?
2. Which token gives private consumers' CI read access to this
   repository while it is private, without an organization-level GitHub
   App?
3. Public first, or PyPI from the private repository (point 2)? The owner
   decides.
4. Does the owner confirm the widened rule in point 1 (no unreleased
   board, add-on or memory device for a released SoC in this repository)?
5. Who in the `AITG` PyPI organization adds the trusted publisher at the
   first publish?
