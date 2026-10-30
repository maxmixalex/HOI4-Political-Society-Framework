# PSF 0.3.1 validation

Validated on 2026-10-30 against the repository's pinned Rust CWTools 2.3.0, supplied HOI4 rules, bundled native GUI/bookmark sources and vanilla symbol cache. Five user-provided screenshots and the 767-line error log were used to identify the actual defects. The supplied KR and Pax Britannica scripted GUIs were also checked for the diplomacy-specific native attachment.

## Results

| Gate | Result |
| --- | --- |
| Full Python regression suite | 155 tests passed |
| Rust CWTools on both generated mods together | 0 errors, 0 warnings |
| CWTools positive and negative semantic controls | All controls passed |
| Raw engine-loader preflight | 80 text files and 3 native GUI files passed |
| Emitted GUI geometry and binding audit | 18,779 checks passed; 338 independently owned windows |
| Two independent builds | Every recorded generated file matched byte for byte |
| Two independently packed installers | ZIP bytes matched; archive CRC check passed |
| Patch whitespace check | Passed |
| Actual HOI4 process | Not available; no new engine launch or rendering result is claimed |

The negative controls reject unknown effects, invalid values, malformed syntax, missing sprites, missing new localization, and invalid scripted-localization triggers. Separate raw-byte checks reject BOM-contaminated GUI/GFX roots, unsupported launcher version syntax, absent native windows and incorrectly named generated GFX roots. These controls matter because the script validator is more tolerant than the engine loader in some of these cases.

## What the regressions execute

The generated-script interpreter executes initialization, elections, alliances, transactions and modifier lifecycles. It is a test harness for emitted script semantics; it does not emulate the HOI4 renderer or its full engine.

- UI tests execute the emitted visibility conditions across navigation, closing, detail selection and country changes. Button/frame/position bindings must belong directly to the window that declares them.
- Color tests inspect generated TGA pixels, including all chart sectors/frames, default badges, independent color keys and dated bookmark values. Hex and RGB-array spellings produce the same bytes.
- Text tests require static UI aliases to resolve at build time while preserving live variable and scripted-text references. Unknown aliases and cycles fail the build.
- Bookmark tests preserve native country order, DLC conditions and original history references; every embedded color image is 12×12 pixels. Oversized charts are no longer inserted into normal text lines.
- Content tests execute all thirty new choices, preserve organization identity and alliance membership, replace conflicting settlement sources, and verify expiry retains accumulated daily support. Both the old-event exclusion and the new-event availability at the 1939 bookmark are checked.
- Runtime tests cover immediate legitimacy refresh, stable values avoiding redundant native refreshes, transaction-time election rules and vote values, and spectrum-marker changes at source expiry and axis limits.

## Package

- File: `distributions/psf-0.3.1.zip`
- Size: 2,573,204 bytes
- Entries: 740
- SHA-256: `d45fbac8440756d3ae31f3a01f594f38913330134b6083a679bc1346d4663308`
- Contents: two mod folders, two launcher descriptors, bilingual installation instructions, notices, generated scripts/assets and the author API registry.

The example contains 125 organizations, 21 declared alliances plus 14 generated transition cabinets, 9 axes, 11 ideology prototypes, 9 institutions, 40 scenarios, 90 choices and 20 named modifier sources. It generates 4,500 native organization modifier keys, 9,202 scripted effects and 3,130 scripted triggers.

## Reproduction

```sh
python -m unittest discover -s tests -q
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
python tools/ui/audit_layout.py dist/psf_vanilla_example
python -m psf pack --root dist --output distributions/psf-0.3.1.zip
```

The layout projection at `docs/assets/ui-layout.svg` is generated from emitted GUI coordinates. It is explicitly a geometric view, not a game screenshot. Current native panel plus sidebar geometry requires at least 966×668 logical pixels; GUI scaling affects the available logical area. Native font rendering, window animations, mouse scrolling and compatibility with a different installed GUI snapshot still require an actual engine run.

For upgrades, replace the two PSF mod directories as complete directories before copying the current descriptors. Do not leave stale generated GUI files in an existing installation. The package asks for a new campaign; it does not claim a tested migration of saves created with older content registries.
