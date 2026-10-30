# CWTools validation

Run from the repository root on Linux x86-64 or WSL2:

```sh
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
```

The workflow builds both mods, runs the Python tests, checks that compiling a
second time gives byte-identical mod directories, and executes the actual Rust
CWTools engine with the supplied Hearts of Iron IV CWT rules. The framework is
layered first and the dependent content pack second. `content_id` is read from
the generated `build-manifest.json`, so the same command validates custom
framework packs as well as the vanilla example. Reports are available
as the `cwtools-diagnostics` Actions artifact; successfully checked launcher
mods are the `psf-mods` artifact. Any unresolved code error or warning, unexpected
nonzero exit, missing report, empty output, or toolchain hash mismatch fails the
job. Exact, evidenced native texture dependencies and diagnostics reproduced
on unmodified original history are reported separately as described below.
Their original diagnostics are retained and are never described as a clean
raw engine report.
The wrapper also rejects scripts over 2 MiB: the supplied CLI silently skips
larger files during discovery. The compiler must split complete top-level
definitions into smaller files so no generated effects escape validation.

## HOI4 loader preflight

Before CWTools runs, the wrapper inspects the original bytes of every shipped
text file in both mod layers, including the outer launcher `.mod` descriptors.
It rejects UTF-8 BOMs in scripts, GUI/GFX files and descriptors; requires a BOM
and matching language header in localisation `.yml`; and rejects damaged UTF-8
or NUL bytes. GUI files must have the `guiTypes` root, and each of the three
overridden native interface files must still define its independent engine
window. A comment or nested window with the same name cannot satisfy that
check. Descriptor `supported_version` patterns must include all three parts,
such as `1.17.*`; `1.*` is rejected.

Generated `psf_*.gfx` sprite files must begin with the exact `spriteTypes` root,
after comments and whitespace. The CWT sprite index deliberately accepts any
root to import vanilla sprites from `bitmapfonts`, so this generator-specific
check catches misspellings and a BOM before the root even after a leading
comment. It does not reject legitimate alternative roots in third-party GFX
files. The supplied log's `psf_society.gfx` failure is checked independently of
the GUI-window failure that follows it.

This is a separate check because a tolerant parser is not the game loader.
The supplied `error(9).log` reports five BOM-prefixed `guiTypes`/`spriteTypes`
tokens and then `Undefined GUI_TYPE: frontendgamesetupview`, explicitly
warning that the game will likely crash. A successful CWT run alone did not
detect that failure. The byte-level regression tests deliberately corrupt an
otherwise valid compiled build and prove it is rejected **before** invoking
CWTools. Preflight diagnostics are retained as `engine-preflight.json`.

The relevant format references are the Paradox-hosted
[Modding guide](https://hoi4.paradoxwikis.com/Modding),
[Interface modding](https://hoi4.paradoxwikis.com/Interface_modding), and
[Localisation](https://hoi4.paradoxwikis.com/Localisation). The supplied native
GUI templates use plain UTF-8; generated translations use UTF-8 with BOM.
These byte checks do not claim a game launch or rendered UI verification.

For a quick loader-only check:

```sh
python tools/ci/validate.py --root dist --preflight-only
```

## Pinned inputs

`toolchain.lock.json` records SHA-256 hashes of every executable, rule file,
license and external-symbol declaration used by this check.

* `vendor/cwtools-linux-x86_64` is the supplied Rust CLI, reporting version
  **2.3.0**, under MIT. Its embedded upstream is
  [MillenniumDawn/cwtools](https://github.com/MillenniumDawn/cwtools), which has
  migrated to [cwtools-vscode](https://github.com/MillenniumDawn/cwtools-vscode).
  The supplied archive contains no build commit, so this project pins the exact
  executable rather than claiming a reproducible source build.
* `vendor/rules` is the supplied MIT snapshot of
  [cwtools/cwtools-hoi4-config](https://github.com/cwtools/cwtools-hoi4-config).
  Its per-file hashes identify the exact snapshot even though the original ZIP
  does not record its upstream commit. An evidence-backed indexing correction
  is recorded in `patches/sprite-types-in-bitmapfonts.patch`: stock `core.gfx`
  declares sprites such as `SandboxFloaterBackground` inside the `bitmapfonts`
  root. The patch indexes known sprite declaration types under any top-level
  root. It does not make arbitrary names valid, and a missing-sprite negative
  control checks this. `patches/scripted-localisation-path.patch` also includes
  the engine's actual `common/scripted_localisation` folder alongside the
  rules' legacy `common/scripted_loc` path; a negative control verifies that
  triggers inside those definitions are semantically checked.
  Finally, `patches/explicit-equipment-category-trigger-aliases.patch` expands
  the 38 native equipment category trigger aliases from `script_enums.txt`.
  The CLI's enum-key alias otherwise behaves as an unrestricted fallback and
  even accepts `always = perhaps`. The expansion preserves the real category
  names and scope constraints while making unknown triggers fail correctly.
* `vendor/vanilla-symbols.cwv` was produced by this CLI's `cache-vanilla` command
  from the supplied base-game script archive. It indexes 141,690 type instances
  and 5,481 file paths. The cache contains identifiers and source positions,
  variable/value-set names and paths; it contains no original script bodies,
  translated prose, audio, textures or game executable.

The upstream cache representation is documented in
[`vanilla_cache.rs`](https://github.com/MillenniumDawn/cwtools/blob/fd9e326cbc2feeac120164020351a5a815e147c2/cwtools-rs/crates/index/src/vanilla_cache.rs).
The binary uses cache format 8; newer upstream releases may require rebuilding
the symbol cache. No download of a moving `latest` tool occurs during CI.

## Stock UI imports

The supplied base-game archive contains scripts, including stock `.gui` files,
but omits localisation payloads. `stock-ui-imports.json` records the exact
localisation keys already referenced by the three imported stock GUI files,
together with original file hashes and line references. Validation adds these
**external dependency declarations** only to its temporary merged workspace.
They are never packaged in either mod and do not replace any game translation.
They establish known imports, not proof of the omitted translation files.
`psf_*` keys are forbidden in this list. Missing new PSF translations still
produce actual CWTools diagnostics; there is no `ignore-code`, ignored-error
baseline, allow-empty flag, or conversion of errors into warnings.

`stock-bookmark-imports.json` similarly records the original bookmark names,
descriptions and country-history localisation keys, with their source lines
and source-file hashes. The current frontend leaves historical prose separate
from its political presentation and retains the game's historical text keys.
These imports are pinned in the same toolchain lock and remain validation-only.

## Native texture dependencies

The source archive also omits original DDS textures. `stock-texture-imports.json`
records only exact paths already declared in supplied native `.gfx` files,
together with each original file's SHA-256, sprite name, line and declaration.
The metadata itself is pinned by `toolchain.lock.json`. Its sixteen paths cover
the fourteen default icon textures plus the two native unknown/anarchism
fallbacks. No DDS placeholder is created, no binary cache is forged, and no
CWT filepath rule or severity is changed.

The engine's complete original output remains in `cwtools.json`. In the absence
of `--vanilla`, the wrapper separates only error-code `CW113` with the exact
native missing-file message, an exact declared texture path and a `.gfx` source
into `stock-texture-dependencies.json`. Everything else remains a normal code
diagnostic. A case mismatch, typo or new missing PSF texture therefore fails.
Only the engine's ordinary diagnostic exit 1 can become a dependency-only
validation result; crashes, empty discovery and other statuses still fail.

`summary.json` reports `raw_engine_errors` and `raw_engine_exit_code` separately
from unresolved `errors`, `warnings` and the wrapper's `exit_code`. It also
records the number of external dependency occurrences and unique paths,
`stock_texture_payloads_bundled = false`, and `runtime_launch_tested = false`.
A successful wrapper result means that the remaining code passed this static
check with these declared game dependencies. It does not prove that the absent
textures exist in a particular installation or render correctly.

To check against a complete, licensed installation instead:

```sh
python tools/ci/validate.py --root dist --vanilla '/path/to/Hearts of Iron IV' --self-test
```

This replaces the bundled script-symbol cache, skips synthetic localization
declarations and disables stock-texture classification. A missing texture in
generated GFX remains an unresolved engine error, even for a declared path.

## Original country-history baseline

Strict mode preserves 364 supplied native country histories and adds bootstrap
calls. Importing those complete files also exposes their existing diagnostics:
some reflect CWT limitations, while others concern native resources omitted
from the supplied script archive. They must not be described collectively as
false positives or silently assigned to new PSF code.

`native-history-imports.json` pins every original bundled file's SHA-256 and is
itself pinned in the toolchain lock. Before validation,
`tools/ci/native_history.py` verifies the complete output filename inventory,
each original hash, the combined source hash, and every generated file's exact
bytes against `bootstrap.patch_history(original)`. Any additional change to a
bootstrap call or original statement fails before baseline classification.
For builds compiled from an explicit installation, that same `--vanilla`
installation must independently provide originals matching the compilation
hashes; generated files cannot serve as their own originals.

The wrapper then runs the real binary twice in the **same complete staged PSF
environment**. The first run validates generated histories. For the second,
only those verified history files are swapped for their originals without PSF
bootstrap calls. Both runs retain the same PSF effects, variables, GUI,
localization, rules and lookup source. The baseline applies only the compiler's
documented BOM normalization and exact-hash Norway repairs: the missing final
brace and the commented-out empty pre-MtG branch. It does not invent or simplify
other source statements. Generated histories are restored even if the baseline
engine run fails.

`cwtools.json` and `native-history-baseline.json` retain both full raw reports.
The classifier maps only unchanged complete generated lines to the baseline
and then to the original source. A diagnostic can be inherited only when its
relative filename, code, severity, complete message, mapped source line and
original surrounding-line SHA-256 all match a baseline diagnostic, one for
one. PSF insertion lines have no original mapping. Repeated messages elsewhere
in a file, new unknown effects, and changed original statements do not qualify.
The CLI report does not contain columns, so the implementation records the
exact available line and source-context proof rather than inventing columns.

`inherited-native-history-diagnostics.json` records both matching diagnostics
and their source proof. Summary fields separately count
`inherited_native_history_errors`, `inherited_native_history_warnings` and
`inherited_native_history_info`, as well as the verified source-file count and
baseline exit code. `validation_errors`/`validation_warnings` describe the
remaining new diagnostics; `raw_engine_errors`/`raw_engine_warnings` remain the
actual binary's totals. Baseline comparison also works with `--vanilla`; it
never exempts new generated script and does not claim the original game files
are free of errors or compatible with every game version.

## Proving the gate does work

`--self-test` feeds positive and negative controls to the exact
same binary and full ruleset used for the build:

| Control | Required result |
| --- | --- |
| Existing effect with a valid value | Exit 0, no errors |
| Unknown effect inside a valid scripted effect | Nonzero, CW263 |
| Non-boolean `elections_allowed` | Nonzero, value error |
| Unclosed script clause | Nonzero, parse error |
| Known stock sprite declared under `bitmapfonts` | Exit 0, no errors |
| Nonexistent sprite reference | Nonzero, CW500 |
| Undefined new PSF localisation key | CW100 warning; the wrapper fails warnings too |
| Unknown trigger in `common/scripted_localisation` | Nonzero, CW263 |
| `always = perhaps` trigger | Nonzero, CW240 |
| Valid native equipment category trigger | Exit 0, no errors |
| Exact declared native texture path, with no DDS payload supplied | Raw CW113/nonzero retained; one explicit external dependency |
| Misspelled variant of that native texture path | Raw CW113/nonzero retained; unresolved error, no dependency classification |
| Actual PRC source plus exact PSF history insertions | Real baseline/generated reports agree on original statements; inherited diagnostics retain source proof |
| New unknown effect on a PSF insertion line | Real CWTools error remains new and fails after baseline comparison |
| Bootstrap call changed from `yes` to `no` | Exact-byte reconstruction fails before invoking the engine |
| Original native `state` assignment changed | Exact-byte reconstruction fails before invoking the engine |

The negative examples are valid enough to reach semantic validation where
appropriate; a brace counter alone cannot pass them. JSON results are retained
in `build/validation/selftest*.json`.

## Limits

### Original generic political source diagnostics

Strict mode also preserves complete original generic opinion and peace-cost
files while changing three party-opinion definitions and thirteen ideological
peace-cost definitions. `native_politics.py` pins both original files
independently, verifies the full generated transform and changed-definition
inventory, and uses the same staged CWTools environment for a source baseline.
External originals require the exact installation supplied at compilation.

Only matching diagnostics on untouched original definitions can be inherited.
Every line within a rewritten definition is excluded even if its text happens
to be unchanged or repeated elsewhere. A mismatch in file, line, diagnostic
code, severity, full message, source context or occurrence count remains new.
`inherited-native-politics-diagnostics.json` records the separate evidence.

The supplied generic peace file already contains `peace_action_type = take_state`
in `defensive_war_take_state`; the pinned rules diagnose that original value.
The raw diagnostic and engine exit remain visible. It is not described as
harmless or suppressed by loosening an enum, and the original gameplay statement
is not rewritten to get a clean report. New PSF errors and warnings still fail.

Four additional real controls check exact original reproduction, rejected
PSF-override tampering, rejected unrelated-source tampering, and an inserted
invalid peace trigger. Together with the existing sixteen controls, `--self-test`
runs twenty positive and negative gates.

### Engine boundary

CWTools checks script syntax, CWT semantics, available identifiers,
localisation references and the supplied GUI rules. It does not run HOI4 or
render a GUI, prove save compatibility, simulate an election, or guarantee that
the game's hardcoded UI will instantiate a modified hierarchy. The script-only
base snapshot cannot verify absent graphics files or translations. The pinned
rules accept some numeric `variable_field` identifiers without checking their
runtime assignment; the compiler's own schema/reference checks and model tests
cover PSF's declarations. An in-game smoke test remains a distinct check and is
never reported as completed by this job.

## Updating the toolchain

Replace a binary and rules snapshot together only after inspecting their
provenance and licenses. Regenerate the cache with the new CLI and rule set:

```sh
tools/ci/vendor/cwtools-linux-x86_64 cache-vanilla \
  --game hoi4 --vanilla '/path/to/Hearts of Iron IV' \
  --rules tools/ci/vendor/rules --output tools/ci/vendor/vanilla-symbols.cwv
```

Update the lock hashes intentionally in the same change, run all controls, and
review changed diagnostics. Do not delete rules, broaden import declarations,
or ignore errors just to turn the job green.
