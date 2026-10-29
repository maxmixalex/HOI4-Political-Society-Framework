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
mods are the `psf-mods` artifact. Any engine error or warning, unexpected nonzero exit,
missing report, empty output, or toolchain hash mismatch fails the job.
The wrapper also rejects scripts over 2 MiB: the supplied CLI silently skips
larger files during discovery. The compiler must split complete top-level
definitions into smaller files so no generated effects escape validation.

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

To check against a complete, licensed installation instead:

```sh
python tools/ci/validate.py --root dist --vanilla '/path/to/Hearts of Iron IV' --self-test
```

This replaces the bundled script-symbol cache and skips synthetic import
declarations, resolving against your real installation instead.

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

The negative examples are valid enough to reach semantic validation where
appropriate; a brace counter alone cannot pass them. JSON results are retained
in `build/validation/selftest*.json`.

## Limits

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
