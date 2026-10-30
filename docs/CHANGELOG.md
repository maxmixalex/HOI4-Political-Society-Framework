# Release notes

## 0.4.1 — immediate foreign refresh, government transitions and deeper native isolation

Foreign summaries no longer use a data-only dirty value: switching between two
countries with equal revisions must refresh their pictures, labels and chart
frames immediately. Both country-selection routes now include independent large
party and ideology icons, with a wider important-country political column and
native portrait/title positions adjusted to fit. Historical text stays separate.
Party and regime labels retain the native presentation, with colored values.

The sidebar adds colored governing roles and every current alliance membership.
Spectrum pages compare organizations with actual institutions and the governing
program; undefined constitutional axes and caretaker programs do not display
invented midpoint positions. Existing native title/frame/scrollbar artwork and
the inset 63-pixel pie overlay are retained, with explicit gutter and geometry
checks. Closing uses the native close-button sound.

Transaction permissions now read current government membership. Leaving office
then banning/deactivating an organization works within one event; a member that
just joined the government is immediately protected. A zero-influence caretaker
government clears stale support/member summaries. Equal election results use
stable numeric IDs rather than declaration order.

Strict mode now neutralizes 61 original political defines, all three generic
party-opinion differences and thirteen generic ideological peace-price entries.
Regimes can override five diplomatic tension thresholds and three constitutional
rules through `native_policy`, with full reset when institutions change.
Original story conditions, country-specific peace logic and unexposed engine
branches still read the compatibility projection; complete eradication is not
claimed. New exact-source reconstruction and real positive/negative controls
keep inherited original-source diagnostics separate from PSF defects.

Country identities can follow the leading party inside an alliance through
`when.leader`. External cosmetic selections are protected even when they select
another PSF-authored tag; releasing ownership only removes the recorded tag.

Ten additional fictional political settlements offer thirty executable choices:
independent government, an explicitly negotiated multi-organization agreement,
or a caretaker. Ten optional agreements and three timed modifier sources bring
the example to 27 alliances, 50 scenarios, 120 choices and 23 named sources.
The existing 125 organization baselines and initial governments are preserved.

The release is validated by generated-script execution, native layout checks,
the pinned Rust CWTools and deterministic packaging. No HOI4 engine launch is
claimed; current evidence and source-diagnostic accounting are in VALIDATION.md.

## 0.4.0 — immediate country data, native presentation and independent government

Repairs the second set of in-game screenshots: domestic localized values and
chart frames now use the explicit player scope; foreign data uses the selected
country, with the native diplomacy container's vertical offset accounted for.
The filled pie stays inside the original rim. Sidebars use original title,
frame and button artwork, actual scrolling backgrounds, reserved scrollbar
space, compact alliance cards and colored value/status tooltips.

Country selection keeps its original historical text. A separate political
region uses the native selected-country party binding for dated PSF pies,
governing party and regime; the old ideology icon and explanatory framework
copy are removed. Preview names are restored to normal native party names on
campaign bootstrap. Organizations and ideology prototypes have independent
large/small native-artwork sprites, texticons and author-supplied overrides.

Government may be a single organization, an authored alliance or a caretaker.
Multiple alliances can coexist without being dissolved by a government change.
The compiler no longer invents transition cabinets. The four vanilla fallback
templates use independent governing organizations. A leading party is derived
separately from coalition identity, so strong military or court members do not
replace a governing party in its display slot.

The vanilla example opts into strict native mechanics with an export-only
bridge. The adapter removes the ordinary native popularity stability bonus,
cancels additional popularity coefficients, unifies the four ideology slots'
mechanical differences, adjusts seventeen native defines and derives five
diplomatic thresholds from PSF institutions. Native elections are disabled;
PSF's election clock remains active. Original focus/event and some hardcoded
conditions still use the compatibility projection; this is documented rather
than described as removal of every ideology-dependent game script.

All 364 supplied country-history files initialize PSF before daily advancement,
including dated starts. Original statements and filenames are preserved; one
exactly identified malformed Norway source receives a recorded closing-brace
repair. Campaign bootstrap is idempotent and does not apply daily drift or
expire timed sources.

The country-identity adapter emits cosmetic-tag names and optional three-size
flags from PSF regime/government conditions. Four native ideology flag variants
receive identical authored pixels. External cosmetic tags are respected after
they take ownership. Twenty name identities and an executable fictional flag
example demonstrate the authoring path. The vanilla example inherits installed
game flags until the author supplies its own images.

CWTools keeps its raw diagnostics. Proven references to original game textures
are reported explicitly as external dependencies when only the script snapshot
is available; unknown or misspelled textures fail. A complete `--vanilla`
validation does not apply this external-resource exception. No HOI4 engine
launch is claimed by the static or interpreter checks.

## 0.3.1 — native UI placement, organization colors and later campaigns

- Bind political and diplomatic summaries and sidebars to native window tokens; use the diplomacy-specific token confirmed in the supplied KR/PB scripts so the panel does not leak into intelligence views.
- Split pages and organization details into independently visible scripted GUI windows. Keep bound buttons, chart slices and spectrum markers directly under their owning windows rather than relying on deep child visibility or property lookups.
- Correct dynamic localization wrappers and expand static UI text references at build time. Separate list columns, detail metrics and scrollable descriptions; keep charts on opaque, correctly sized backgrounds.
- Replace oversized inline bookmark charts with font-height color legends and both support/influence values. Retain native chart containers in politics and diplomacy.
- Accept per-organization `color` as `#RRGGBB` or RGB bytes, normalize it in the model and registry, and use it for both pies, default emblems, independent swatches and bookmark previews. All 125 example organizations now declare colors; old manifests retain their deterministic fallback.
- Refresh legitimacy's GUI dirty value and native dynamic modifier immediately. Elections called inside a transaction now read the updated support and institutional rules. Spectrum markers use clamped effective positions, including source expiry.
- Add ten fictional post-bookmark negotiations with thirty choices and four real named sources. The example now has forty scenarios, ninety choices and twenty named sources while retaining 4,500 native organization modifier keys.
- Extend regression coverage to the actual reported window bindings, exclusive pages, localization references, emitted image pixels, 1939 choices and modifier expiry. Static checks and CWTools remain distinct from a game-engine rendering test.

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
- Floating-point totals use `math.fsum()` so Python 3.11 and 3.12 produce the
  same bookmark reports and weight divisors, preserving the package byte check.

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
