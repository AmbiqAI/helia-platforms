# 0010. State facts with their sources; leave what to do with them to consumers

Date: 2026-10-30
Status: Accepted

## Context

helia-platforms exists so that heliaAOT, helia-profiler, neuralspotx and
other tools read one description of Ambiq silicon, parts, boards and
add-ons instead of each keeping its own. ADR 0002 gives it a schema and a
loader, ADR 0003 a source for every value, and ADR 0006 a check against the
SDKs it describes.

A reviewer's audit of the loader and the `Target` queries on 2026-10-29
(#141), at the head of the apollo510b, apollo510L/apollo330P, apollo4 and
apollo3 pull requests (#125 to #128), counted 171 load-time rules: 98 check
structure, 28 provenance and 35 that two facts do not contradict each
other. Ten encoded what someone may do, such as which supplier may own an
image slot on which core. Most of those ten, and the `guidance` filter
inside `memories()`, `placement_ranges()` and `usable_nvm()`, arrived
through review findings of the form "an overlay can express X", forwarded
as fixes, and each new rule drew edge-case findings in the next round. The
owner's concern in round 3 of that review was that the package was
drifting from a source of knowledge into policy.

## Decision

helia-platforms states facts about Ambiq silicon, parts, boards and
add-ons, each with its source (ADR 0003). It answers "what is", not "what
to do".

1. The loader rejects data that cannot be parsed, that references what does
   not exist, or that contradicts itself: a slot past the end of its
   region, two regions at one address, an add-on on an interface the board
   already populates, a mode the board's interface does not have. It does
   not reject a combination of facts because a consumer might misuse it.
   Who supplies an image and who programs a core are both recorded; whether
   a combination is allowed is the flashing tool's question.
2. Queries restate facts or derive them by arithmetic over facts. Where a
   query applies a filter or a point of view, the filter is a named
   parameter with a documented default. `memories()`, `placement_ranges()`
   and `usable_nvm()` take `include_discouraged`, default `False`, and
   `usable_nvm()` is documented as the customer's view. `guidance` is the
   catalog's advice and is reported as such.
3. A fact lives in a data file with a provenance record, never as a
   constant in code.
4. Built-in data stays complete and cannot be shadowed (ADR 0002 section
   1): a built-in region has a base, every region of a built-in Soc has an
   access entry, and an overlay cannot redefine a built-in entry or extend
   the source register or the release allow-list. These rules protect the
   facts; they are not policy.
5. In review, a finding that an overlay "can express" something is a defect
   only if the data would then contradict itself. A review asks for a new
   rule only under point 1.

## Consequences

- The image-slot supplier check ("supplier is customer, but only the
  vendor programs") is gone, removed with the apollo510L and apollo330P
  data (#127).
- `include_discouraged` is added to the three queries (#141).
- apollo3's and apollo3p's J-Link `-cpufreq` moves from a constant in
  `_pages.py` to `sdk.jlink_cpufreq_mhz` in the Soc data, with a record,
  and `check-sources` compares `NSX_SEGGER_CPUFREQ` with it (#141).
- RFC 0002's rule list is regenerated from the loader (#141).
- Still to follow: `AddOn.modes` is redefined as the modes the add-on's
  wiring uses, with `Target.interfaces` reporting the board's and the
  add-on's modes side by side (#139). Whether linker windows,
  `Target.budget()` and the `windows` command belong in this package is
  proposed on #73.
- Harder: a consumer that wants a "usable" set must intersect or filter
  for itself. The queries give it the inputs.
- CONTRIBUTING gains a "Scope" section with points 1, 2 and 5, which
  reviewers read.
