# PSF 0.4.0 validation

Validated on 2026-10-30 with the pinned Rust CWTools 2.3.0, the supplied HOI4
rules, native script snapshots and vanilla symbol cache. User-provided game
screenshots and logs informed the repairs. The supplied vanilla, Kaiserreich,
The New Order and Pax Britannica scripts provided the native widget, scope,
asset and initialization references.

**The final static gate reports zero new errors and zero new warnings.** The
unmodified CWTools report still contains **366 errors and 117 warnings**, with
engine exit code 1. Those raw diagnostics are retained and accounted for below;
this release does not claim that the binary itself returned a clean report.
There was no available HOI4 process, so no new engine launch or successful game
render is claimed.

## Final release gates

| Gate | Result |
| --- | --- |
| Full Python regression suite | 213 tests passed in 218.806 seconds; exit 0 |
| Raw Rust CWTools result | 366 errors, 117 warnings; engine exit 1 |
| Declared external stock textures | 272 missing-texture occurrences across 14 exact paths |
| Matched original country-history diagnostics | 94 errors, 117 warnings, 83 informational diagnostics |
| New diagnostics after the verified classifications | 0 errors, 0 warnings; wrapper exit 0 |
| Exact country-history reconstruction | All 364 generated native histories verified |
| Engine-loader preflight | 449 text files, including 3 native GUI files; 0 errors |
| Generated script discovery | 446 staged files; 252 declared stock-localisation imports |
| Positive and negative validation controls | All 16 passed against the real binary and reconstruction gate |
| Emitted GUI geometry and binding audit | 19,729 checks; 339 independently owned windows; 0 failures |
| Installer integrity | Archive CRC check passed |
| Independent rebuild | Isolated installed-wheel build matched all 788 output files: 0 missing, 0 extra, 0 changed |
| Independent installer reproducibility | Isolated-wheel packing produced a byte-identical ZIP: 3,173,703 bytes and the same SHA-256 |
| Actual HOI4 rendering and startup | Not performed in this environment |

The final validation reports are in `build/validation-0.4.0/`. The layout audit
is `build/layout-0.4.0.json`. Reports preserve the distinction between the
binary's raw exit and the wrapper's result after explicit dependency and
original-source matching.

The independently installed wheel is 673,474 bytes and includes all 364 native
country histories, the native ideology source, three GUI sources and two
bookmark sources. Its actual vanilla and identity-example compilations ran
under Python `-I`; the imported `psf.*` modules came from the isolated
installation. This checks packaged resources and import provenance as well as
the byte-for-byte output comparison against the release build. Packing the
independently generated vanilla output through that isolated installation also
reproduced the official installer byte for byte.

## How the raw CWTools diagnostics are accounted for

### 272 occurrences are declared original-game texture dependencies

The supplied script archive includes native GFX declarations but omits the DDS
payloads. The current default icon aliases refer to 14 distinct paths already
declared in those original files. Their 272 CW113 occurrences are recorded in
`stock-texture-dependencies.json`, with exact source paths and declaration
provenance. The dependency manifest also declares the native unknown and
anarchism fallback paths; those are not additional used-path occurrences in
this build.

This classification accepts only the exact declared missing-file message,
path and GFX source. A typo or a new missing PSF texture remains an error. No
placeholder DDS, forged binary cache, relaxed filepath rule or changed severity
is used. `stock_texture_payloads_bundled` is false. The record establishes a
dependency on the installed game; it does not establish that the texture exists
or renders correctly in a particular user's installation.

### 294 diagnostics are reproduced on original country histories

Strict mode preserves 364 complete native country-history files and adds PSF
initialization calls. Validating those files exposes diagnostics already
present in the supplied original scripts and validation environment. Their
matched totals are **94 errors + 117 warnings + 83 informational diagnostics**.
Some concern missing original-game references in the available archive/cache;
others concern the validator's interpretation of original script. They must
not collectively be called false positives or dismissed as harmless.

Before comparing diagnostics, the gate verifies the complete filename
inventory, pinned original hashes, combined source hash and exact generated
bytes against `bootstrap.patch_history(original)`. It also accounts explicitly
for BOM normalization and the exact-hash Norway repairs: a missing final brace
and preservation of an empty pre-MtG branch as comments. An additional change
to an original statement or a bootstrap call fails reconstruction.

The same real CWTools binary then runs twice in the same complete staged PSF
environment. The baseline run substitutes the verified originals without PSF
bootstrap insertions; all other effects, variables, GUI, localisation, rules
and lookup data stay the same. A diagnostic is inherited only if its relative
filename, code, severity, complete message, mapped source line and original
surrounding-line hash match one for one. Insertion lines have no source mapping.
Repeated messages elsewhere do not qualify merely because they look similar.

`cwtools.json` retains the full generated-file report;
`native-history-baseline.json` retains the full baseline report;
`inherited-native-history-diagnostics.json` records each matched diagnostic and
its source proof. Generated histories are restored after the baseline run.
The baseline itself also exits 1; its errors have not been relabeled as a clean
engine run.

After these two documented classifications, this build has **0 new errors and
0 new warnings**. New unresolved PSF diagnostics still fail the gate, including
new warnings. See [the CI documentation](../tools/ci/README.md) for the exact
classification contract and the complete-installation validation path.

## What the regression and control suites exercise

The generated-script interpreter executes emitted Clausewitz effects. It is a
strict test harness for the supported subset, not an emulator for HOI4's
renderer or complete engine.

- Runtime coverage includes immediate history/bootstrap initialization,
  elections, transactions, source expiry, modifiers, native-mechanic
  cancellation, direct organization governments, alliances and caretakers.
- Identity coverage includes actual cosmetic-tag effects, regime selection,
  three flag sizes and all native ideology variants, external-tag ownership,
  missing assets and deterministic output.
- UI coverage executes visibility through navigation, closing, selection and
  country changes; checks direct callback ownership; enforces domestic `ROOT`
  versus foreign `THIS` data scope; and prevents foreign political mutations.
- Color and image coverage inspects exact generated TGA pixels, all pie sectors
  and frames, the four-pixel inset, independent RGB keys and native icon aliases.
  Hex and RGB-array colors produce the same artwork.
- Frontend coverage executes temporary party-name preparation and restoration
  for both name forms, multiple countries and 1936/1939. It checks direct and
  alliance government data, large ideology and small party artwork, independent
  dual pies and completely unchanged history descriptions. Compat mode retains
  the complete native frontend when no history binding is installed.
- Content and localisation coverage checks scenario choices, dates, modifier
  settlement/expiry and starting-bookmark overrides; static aliases resolve at
  compile time while live country expressions remain live.

The 16 validation controls cover four script/value/syntax cases; six
sprite/localisation/trigger/equipment cases; two stock-texture cases; and four
native-history baseline/tamper cases. They include a real original PRC history
with exact PSF insertions, a new unknown effect on an insertion line, a changed
bootstrap value, and a changed original state assignment. The latter changes
must not disappear into the inherited-diagnostic classification. The valid
texture control retains its raw missing-file error as a declared dependency;
the misspelled texture control remains a failing unresolved error.

Separate engine-loader checks reject BOM-contaminated GUI/GFX roots, unsupported
launcher version syntax, absent native windows and incorrectly named generated
GFX roots. These checks exist because the script validator is more tolerant
than the engine loader in some of these cases.

## Package

| Field | Value |
| --- | --- |
| File | `distributions/psf-0.4.0.zip` |
| Compressed size | 3,173,703 bytes |
| Archive entries | 788 |
| Uncompressed size | 60,258,671 bytes |
| SHA-256 | `3ca5180dc2aebda4a943f1d6a5b92a9929e2340817dfd05ccfa9542c9b32a8ae` |

The installer contains the framework and vanilla-example mod folders, two
launcher descriptors, bilingual installation instructions, notices, generated
scripts/assets and the author API registry. The build contains **125 groups,
17 declared alliances, 40 scenarios, 20 named modifier sources and 20 country
identities**. It generates **4,500 organization modifier keys, 9,009 scripted
effects and 2,943 scripted triggers**. There are no compiler-invented transition
cabinets.

## Reproduction and in-game boundary

```sh
python -m unittest discover -s tests -q
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
python tools/ui/audit_layout.py dist/psf_vanilla_example
python -m psf pack --root dist --output distributions/psf-0.4.0.zip
```

With a complete licensed game installation, pass `--vanilla` to the validator
as described in the CI documentation. That replaces the script-only lookup
cache and disables missing-stock-texture classification; a missing DDS in that
installation is a normal unresolved error. Original-history matching still
requires independently supplied originals with the compilation hashes.

`docs/assets/ui-layout.svg` projects emitted GUI coordinates; it is not a game
screenshot. The final audit places the domestic summary's lower edge at y=382,
before the preserved native row at y=383, and the diplomatic summary's lower
edge at y=246, before the native focus area at y=248. The native panel and
sidebar require at least 966×668 logical pixels; GUI scaling affects the area
available. Static geometry cannot establish font baselines, texture rendering,
mouse scrolling, animation behavior or the engine's first-frame startup order.
Those remain part of the in-game smoke test, including the frontend's temporary
party-name restoration and the exact installed game snapshot.

For upgrades, move both previous PSF mod directories aside before copying the
current directories and descriptors. Do not overlay a new build onto stale
generated GUI chunks. Enable both mods in the same playset and start a new
campaign; this package does not claim a tested migration of older content
registries or saves.
