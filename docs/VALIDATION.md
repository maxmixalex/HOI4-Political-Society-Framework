# PSF 0.4.2 validation

This release was checked against the user-supplied original-game, Kaiserreich,
The New Order and Pax Britannica scripts and pinned Rust CWTools 2.3.0.
All retained 0.4.0/0.4.1 work is included. Original screenshots informed the
native attachment corrections; offline geometry previews are not game captures.

**All three script gates have zero new errors and zero new warnings.** The
vanilla and native-modifier integration runs still have **367 raw errors and
123 raw warnings**; the smaller coalition workshop has **119 raw errors and
123 raw warnings**. Each raw engine exits 1. Exact source/dependency comparisons
explain the inherited diagnostics below; raw diagnostics were not rewritten.

**HOI4 itself was not available for launch or interaction.** The actual native
attachment origin, DDS pixels, fonts/texticons, first-frame ordering, scrollbars
and mouse input remain outside these source and execution-model checks.

## Completed release gates

| Gate | Observed result |
| --- | --- |
| Final Python test inventory | 264 distinct tests passed: a full 261-test run (223.355 seconds) plus three subsequently added regression cases |
| Real CWTools positive/negative controls | 20 passed |
| Vanilla script gate | 0 new errors, 0 new warnings; 461 discovered staged files |
| Native idea/trait/dynamic-modifier integration | 0 new errors, 0 new warnings; 467 discovered staged files |
| Playable coalition workshop | 0 new errors, 0 new warnings; 408 discovered staged files |
| Loader preflight | Vanilla 464 / integration 470 / workshop 411 text files; 3 native GUI roots each; 0 errors |
| Exact country-history reconstruction | All 364 supplied histories matched their preserving transform |
| Exact generic political reconstruction | All 3 snapshots matched; 3 opinion, 13 peace and 4 occupation definitions changed |
| Native GUI geometry and bindings | 34,372 checks, 339 windows, 0 failures |
| Vanilla ZIP CRC | All 803 entries passed |
| Workshop ZIP CRC | All 614 entries passed |
| Version-based CI distribution entrypoint | Explicitly selects both current-version installers; builds/validates workshop and checks both CRCs/source equality |
| Installed-wheel reproduction | Vanilla 803 / workshop 614 files matched; 0 missing, extra or changed; both ZIPs byte-identical |
| HOI4 launch/gameplay | Not performed |

The final three added regressions verify complete decision-category splitting,
actual coalition decision availability/cost/cooldown, and native source coverage
in package-data declarations. Independent reviews also executed cross-version
record expansion, all 14 native cancellation channels, country isolation,
role changes, identity ownership/release and strict/compat boundaries.

Release checks found and fixed two additional integration defects. The expanded
alliance decisions exceeded the existing 1 MB budget in one file; the compiler
now splits complete category definitions, with AST equality and duplicate-ID
checks. The first installed wheel omitted the new occupation-law snapshot;
its package-data entry and a regression for every bundled native snapshot are
now present. Neither gate was relaxed. The largest generated common script is
899,961 bytes, below the 1 MB project budget and the tool's 2 MiB discovery cap.

Reports are in `build/validation-0.4.2/`,
`build/validation-native-integration-0.4.2/`,
`build/validation-coalitions-0.4.2/`, `build/layout-0.4.2.json` and
`build/wheel-verification-0.4.2.json`. Earlier evidence is preserved in
[0.4.1 validation](history/VALIDATION_0.4.1.md) and
[0.4.0 validation](history/VALIDATION_0.4.0.md).

## Raw diagnostic accounting

### Original texture payloads

The supplied scripts reference original DDS files that were not included in
the script archive. The vanilla/integration runs have 272 such errors over
14 exact declared paths; the workshop has 24 over 10 paths. Only the exact
missing-texture diagnostic/path of a proven original GFX declaration qualifies.
A typo, unknown path or missing payload under a full `--vanilla` installation
still fails. No placeholder textures or invented cache entries were introduced.

### Original country histories

The same staged environment is checked with emitted histories and independently
verified originals. Exact source pins, full transformed-file reconstruction,
original-line mapping, surrounding text, diagnostic identity and multiplicity
must agree. The originals account for **94 errors, 117 warnings and 83
informational diagnostics**. New bootstrap statements cannot inherit a source
error. The raw reports and matched occurrences are retained.

### Original generic politics and occupation laws

The supplied generic peace source retains one error on its unchanged
`peace_action_type = take_state` statement. The new occupation snapshot adds
six inherited warnings in `common/occupation_laws/occupation_laws.txt`:

- Three CW100 original-localisation references: one
  `resource_sabotage_decrease_tooltip` and two
  `factory_sabotage_decrease_tooltip` occurrences.
- Three CW251 redundant `AND` blocks in unchanged original definitions.

The occupation source's independent SHA-256 pin is
`b0e776a177eb7ceb186178d873cb6955fad5a9c56cd299292a62e00397f9c823`.
All three generic source files are reconstructed before any baseline comparison.
Every line in each rewritten definition is excluded, including unchanged-looking
lines inside it. Matching checks the exact original file/line, nearby text,
code, severity, message and occurrence count. There is no category-wide waiver.
`inherited-native-politics-diagnostics.json` retains this proof.

## Behavior and presentation coverage

The strict interpreter executes the emitted Clausewitz subset and rejects
unsupported operations. It is not a complete HOI4 emulator.

- Country-history initialization and later bookmark overrides prepare data
  before a daily update. Runtime bootstrap refreshes without drifting scores
  or decrementing source timers.
- A genuinely older registry gains a new group, alliance and global spectrum
  axis. Existing explicit zero/inactive/dissolved states, memberships, cabinet,
  source durations and a second country's state survive. Repeat entry is
  idempotent; unchanged structural revisions avoid daily field scans.
- An empty electorate clears stale engine popularity while the visible PSF
  shares, government support and empty chart remain zero. Strict mode grants no
  native popularity-stability bonus. Monthly calculations preserve the outer
  transaction and use membership changes already made in that transaction.
- Domestic text/images use the player scope; foreign values use the selected
  country. Equal country revisions do not prevent diplomacy refresh. Both
  selection routes retain historical descriptions and use a separate political
  region. Native label/value font sizes, fixed title/close controls, scrolling
  body placement and large/small icon dimensions are checked.
- Four occupation-law gates follow PSF institutions. Fourteen native modifier
  channels are cancelled in strict mode, including removal/restoration of the
  cancellation dynamic modifier and repeated/cross-country refreshes. Host
  authors must explicitly migrate native rules when switching strict/compat in
  an existing campaign; it is not a transparent hot-toggle.
- The workshop executes independent party government, three coexisting pacts,
  role conversion, an election, membership changes, pact dissolution/rebuild,
  coalition formation and cosmetic identity release/resume. Decision costs,
  cooldowns, current office and legal electoral eligibility are checked.

Domestic summary bottom remains Y=382 before management at Y=383. Foreign
summary bottom is native-window Y=246 before the focus area at Y=248. The pie
fill is inset within the 63-pixel rim. Important-country politics reaches
Y=711 within the native 717-pixel window. These are script-coordinate facts,
not measurements of rendered game pixels.

## Distributions and independent rebuild

| Field | Vanilla example | Coalition workshop |
| --- | --- | --- |
| Installer | `psf-0.4.2.zip` | `psf-coalition-workshop-0.4.2.zip` |
| ZIP bytes | 3,584,938 | 872,349 |
| Entries | 803 | 614 |
| Uncompressed bytes | 67,643,404 | 5,455,333 |
| SHA-256 | `0eeb8692c03abedac8352b99e3837d364cf2fe06b9e7a60387f091ea0c742dc4` | `78ba5222a4f6fd1c6dca83cffa32edc53656298a49286d784afbc6100231aa21` |

The `hoi4_psf-0.4.2-py3-none-any.whl` compiler is 692,941 bytes
(SHA-256 `61ca5f60a756514b2086a53c2825de93e46a9b2b2c91c7c6766bd2e7ca5f0cbd`).
It was installed into an isolated location. Compilation ran under Python `-I` outside the repository, asserting
that every imported PSF module came from that installation. The installed
occupation-law source was checked against the exact independent pin. The vanilla,
identity and workshop examples compiled from the installed code; default and
workshop output files and ZIP bytes matched the source builds exactly.

The two downloadable content packs are alternatives. Each includes its own
framework and full registry; enable only one content pack at a time.
The fictional workshop is not inserted into the default historical example.

```sh
python -m unittest discover -s tests -v
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --reports build/validation-0.4.2 --self-test
python tools/ui/audit_layout.py dist/psf_vanilla_example --report build/layout-0.4.2.json
python -m psf pack --root dist --output build/psf-0.4.2.zip
cmp distributions/psf-0.4.2.zip build/psf-0.4.2.zip
python examples/coalitions/build.py --output build/coalitions
python tools/ci/validate.py --root build/coalitions --reports build/validation-coalitions-0.4.2
python -m psf pack --root build/coalitions --output build/psf-coalition-workshop-0.4.2.zip
cmp distributions/psf-coalition-workshop-0.4.2.zip build/psf-coalition-workshop-0.4.2.zip
python tools/ci/verify_distributions.py
```

Original story conditions, country-specific peace logic and hardcoded branches
remain documented in [NATIVE_MECHANICS](NATIVE_MECHANICS.md). These checks do not
establish total replacement of all native political behavior or a successful
engine launch.
