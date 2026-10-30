# Country-selection previews

PSF displays compact organization rows with support and influence percentages in
the native **interesting-country selection history panel**. The vanilla example supplies
**20 date-specific snapshots** for ten countries and both stock bookmarks,
bound to **28 existing country/DLC history variants**.

The countries are China, France, Germany, Italy, Japan, Poland, the Soviet Union,
Spain, the United Kingdom and the United States. Their actual stock bookmark
dates are `1936.1.1.12` and `1939.8.14.12`. Country entries without a declared
PSF country profile are unchanged; generic fallback data is not presented as
an authored country snapshot.

## Native binding and preserved history

`psf/bookmarks.py` reads each existing `common/bookmarks/*.txt` country entry
and replaces only its `history` localisation reference. For example, the
generated key contains this structure:

```text
Support / Influence
£psf_bookmark_key_example_party£ Example Party 50.0% / 40.0%

$GER_GATHERING_STORM_DESC$
```

The exact generated sprite and localisation keys are recorded in
`psf_bookmark_manifest.json`; the example above illustrates the structure and
uses an illustrative organization and percentages.
The original `GER_GATHERING_STORM_DESC` remains owned by the installed game.
PSF references it through localisation substitution and does not replace its
translated text. Original DLC conditions, country order, ideas, focuses,
portraits and every other bookmark field are retained.

The engine already selects the `history` field for the current country and
bookmark. The existing `history` textbox keeps its native identity and ancestry,
with a 160-pixel viewport and the stock `standardtext_slider`. The adapter does
not add a hypothetical frontend scripted-GUI country context.

## Fix for overlapping history text

The previous implementation inserted a 140×63 dual-pie texture into an ordinary
16-pixel text row. The supplied game screenshot showed the image overlapping
both the metric labels and the first paragraph of the original history. Text
icons do not provide an independently sized GUI container, so adding empty
lines would leave the rendering dependent on the icon's baseline behavior.

The history adapter now inserts only **12×12 color keys**. Each organization
uses one ordinary line containing its short name and both percentages. The
native textbox controls wrapping and scrolling; every image is smaller than
the text font's nominal 16-pixel height. The original history begins after one
blank separator line. There are no large inline charts to extend into adjacent
lines. Short labels are conservatively bounded to 22 Latin-width columns
(wide CJK characters count as two); longer labels end with an ellipsis. Full
organization names remain available in the campaign interface.

The campaign's political and diplomatic panels retain their separate native
support and influence pies. `charts.bookmark_artwork` can still produce a full
dual-pie snapshot for an appropriately sized custom GUI widget or offline use;
the standard history adapter does not generate or embed those large textures.

Text-icon definitions use ordinary `spriteType` entries with
`legacy_lazy_load = no`, matching the supplied `interface/texticons.gfx`.
Localisation refers to each sprite without its `GFX_` prefix, using the normal
`£icon_name£` notation. The color keys use the exact organization `color` values
and are shared between dates and DLC variants.

## What the snapshots show

`psf/charts.py::bookmark_values` applies every `start_overrides` entry whose
date is at or before the selected bookmark. Support includes active electoral
organizations; influence includes active organizations after the configured
underground/banned influence penalties. Both metrics normalize their own total;
the row's color key matches that organization's campaign pie sectors and badge.
An organization with zero shares in both metrics is omitted from the compact
table. Non-electoral organizations can still appear with an influence share
and zero electoral support.

These are the declared starting political society values, including the
date-specific overrides. They are not a campaign simulation, and they cannot
predict later events or externally supplied native modifiers. A snapshot with
no nonzero organization shares shows an explicit empty-state line before the
original history. The generated report records each snapshot's normalized
support/influence values, original history key, replacement key, row labels,
color-key sprites and textures, and DLC variant.

## Separate map-selection panel

The map-selection right-hand `gamesetup_country_details` panel is a different
native window. The supplied definition has no `history` binding, and its
political pie is tied to the engine's ideology categories. The bookmark adapter
does **not** make that panel display arbitrary PSF organization data. PSF hides
its obsolete ideology/party wheel and labels and retains a concise notice.
The 20 snapshots described here appear in the interesting-country history
panel only.

Both bookmark files are full native-file overrides, as required by the game's
file replacement rules. A mod changing the same bookmark files needs a merged
adapter, in addition to the interface compatibility work described in
[UI.md](UI.md). Adjusting load order alone cannot preserve both sets of edits.

## Source provenance and verification

The bundled source snapshots come from the user-supplied original game script
archive. They remain Paradox Interactive material, excluded from PSF's MIT
grant. `psf/assets/native_bookmarks/sources.json` records these exact hashes:

| Original game path | SHA-256 |
| --- | --- |
| `common/bookmarks/the_gathering_storm.txt` | `31d22ba3fdd6160be56f198f0ec078c09156d3fdcfadced809f73226f698422f` |
| `common/bookmarks/blitzkrieg.txt` | `54f6f23dec5a066dca37125f69a29b8cc0400b4c0d598ff6e6ba71bd82dcf25d` |

The runtime bindings are visible in the supplied
`interface/frontendgamesetupview.gui`: the `history` textbox belongs to
`gamesetup_interesting_countries_window`; the separate
`gamesetup_country_details` contains the hardcoded political pie.
`tools/ci/stock-bookmark-imports.json` records the original bookmark
localisation dependencies and their source lines for script-only validation;
those synthetic validation declarations are never shipped in the mod.

Run the regression suite with:

```sh
python -m unittest discover -s tests -p 'test_bookmarks.py' -v
```

It compares the entire native bookmark structure before and after the change,
checks all 28 history variants, verifies original-prose substitution and DLC
gates, and proves that the 1939 overrides change the displayed data while
retaining the organization's color. Pixel checks inspect every generated
front-end texture's dimensions and RGB values; text-structure checks enforce
one font-sized icon per organization line and a separate original-history
paragraph, including long names and the zero-total case.
CWTools checks the resulting bookmark, sprite and localisation references.
Neither check constitutes a completed HOI4 render or launch test; the generated
report explicitly retains `runtime_render_tested: false`.
