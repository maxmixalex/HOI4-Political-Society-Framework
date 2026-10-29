# Release notes

## 0.2.0 — loader repair and organization modifiers

### Startup repair

The supplied `error(9).log` identified a reproducible loader defect in 0.1.0:
five generated GUI/GFX files began with a UTF-8 BOM. HOI4 interpreted that mark
as part of `guiTypes` or `spriteTypes`, rejected the definitions, and subsequently
reported `Undefined GUI_TYPE: frontendgamesetupview` with a crash warning.
The source game templates did not have the BOM; the generator introduced it.

All GUI/GFX, scripts and descriptors now use UTF-8 without BOM. Localization
retains its required BOM. A raw-byte preflight runs before CWTools, checks the
three native root windows, rejects invalid version patterns and oversized script
files, and replaces stale successful reports after failed validation. The old
`supported_version="1.*"` declaration has been removed; the optional target
version can be set explicitly with the compiler's `--supported-version` flag.

The pinned Rust CWTools accepts a BOM-prefixed GUI by itself. A regression
therefore checks the original bytes independently instead of treating a clean
semantic report as proof of engine loader compatibility.

### Framework APIs and content

- Native custom `add`, `factor` and `daily` modifiers for every group metric and
  every declared spectrum axis: 4,500 keys in the vanilla example.
- Named permanent and timed sources with independent removal, idempotent
  reapplication, duration refresh, source restrictions and save-persistent state.
- Separate base and modified values, so removing a clamped bonus preserves
  underlying values and accumulated daily changes.
- Relative one-time movement on every spectrum axis, alongside existing setters.
- Daily updates and public mutation APIs import native changes before
  projecting PSF changes back; each imported native snapshot is acknowledged
  once, including explicit imports inside a transaction. Export also preserves
  pending native movement. Active support multipliers are accounted for to
  prevent feedback amplification.
- Timed-source tooltips show the same rounded and bounded duration used by the
  saved source, while preserving the caller's original duration argument.
- Fresh derived values are checked when forming a government, including when
  an election gives a previously powerless winner its initial mandate.
- Sixteen named sources and ten additional fictional negotiation scenarios;
  the example now has thirty scenarios and sixty choices.
- Copyable native national-spirit, character-trait and dynamic-modifier examples,
  tested together with the actual compiled registry by CWTools.

### Interface

- Separate support and effective-influence pies in politics and diplomacy,
  each using 180 cached sectors and the original 63-pixel overlay.
- Compact native organization rows, right-hand detail/spectrum panels, correct
  nested mount instances and distinct domestic/foreign context windows.
- Modifier source names, remaining days, base values and modified values in
  detail tooltips. Event tooltips show the concrete numerical changes.
- Twenty country/date starting previews through twenty-eight native bookmark
  history bindings, preserving original historical text and DLC conditions.
- Complete generated definitions split into bounded files before validation.

### Verification and remaining runtime boundary

The implementation was checked with generated-script execution tests,
byte/root-window checks, deterministic builds, layout-bound checks and the
pinned Rust CWTools with positive and deliberately invalid controls. The
provided vanilla, Kaiserreich, TNO and Pax Britannica script archives were used
as implementation evidence. The official wiki returned an access challenge;
engine syntax was cross-checked against the original game's bundled comments
and generated effect documentation instead of claiming access to blocked pages.

This environment has not launched the HOI4 executable. Loader safety and
semantic validation are not represented as an engine-rendering or full-campaign
test. Starting previews are in the native important-country history panel;
the map-selection right-hand details panel still has no demonstrated binding
for arbitrary PSF organization arrays. Its old ideology chart is hidden and
replaced with a concise notice, as documented in [BOOKMARKS](BOOKMARKS.md).

Install-folder names stay `psf` and `psf_vanilla_example`. Replace the old
directories and both launcher descriptors, then start a new campaign.
