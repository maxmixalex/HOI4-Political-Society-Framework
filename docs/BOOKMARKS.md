# Country-selection politics

Country selection displays the selected country's governing organization,
regime, both party and ideology artwork, and separate support and influence pies in its native
political information area. This works through the existing `party` binding in
both the interesting-country panel and the map-selection details panel. The
original history description contains no political statistics, generated
charts, or framework explanations.

This automatic frontend binding is enabled by the strict vanilla adapter,
which also supplies the necessary country-history preparation. In `compat`
mode the compiler retains the complete original country-selection layout;
it does not hide native fields when no history hook supplies the replacement.
Compiled snapshot metadata records `binding_enabled` separately from the
available artwork.

The vanilla example covers ten authored countries and both stock bookmarks:
`1936.1.1.12` and `1939.8.14.12`. The coverage report lists **20 country/date
snapshots** across **28 existing country/DLC variants**. Fallback profiles also
receive compiled presentations for countries without an authored profile.

## Binding to the selected country

The front end has no established scripted-GUI country context that PSF can
safely assume. It does have native `leader` and `party` fields that the engine
updates as the player selects countries. Native country history already uses
`set_party_name`, including both short and long localisation keys. PSF uses
that existing connection:

1. A preserved native history file initializes the PSF profile at its root and
   relevant date boundaries, then calls `psf_prepare_frontend`.
2. Preparation assigns a compiled presentation key to the four native party
   slots' short and long names. All four slots receive the same selected
   profile/date presentation, so the display does not depend on which native
   ideology slot currently projects the government.
3. The native `party` textbox displays the governing organization's small icon
   and name, the actual regime, and a separate artwork row containing the
   party's large icon, the PSF ideology's large icon and a 140×63
   support/influence image. Party and regime values use native yellow
   emphasis; labels remain ordinary text.
4. `psf_finish_frontend` restores ordinary short and long party names. Campaign
   startup and `psf_bootstrap`, including opening the campaign political
   interface, call this idempotent restoration.

Presentation names are temporary selection state. Ordinary party names use
actual electoral organizations matching each engine ideology projection. An
empty projection has a neutral “No electoral organization” name; it does not
create an organization, cabinet, or alliance. The original engine-owned leader
name and portrait remain bound to the selected country. Preparation only marks
a preview active after matching and writing a known profile. Restoration only
clears that marker after a known profile has supplied normal names; temporarily
missing content cannot silently discard the pending restoration.

The game's exact startup rendering order still needs a live engine check.
`on_startup` may occur after the first paused frame; the GUI bootstrap also
restores names when a campaign political interface is opened. Script tests
verify the actual emitted prepare/finish effects and both name forms, not a
claim that every engine window has already rendered those effects.

## Independent layout and unchanged history

`psf/frontend.py::patch_native` preserves all native widget names and ancestry.
It hides the old four-slot ideology icon, wheel and redundant ideology,
government and election text fields. The `party_label` uses the native
`RULING_PARTY` localisation, with the native leader fields retained. No visible
“PSF” banner or implementation explanation replaces the country's politics.

The interesting-country political region is 305×234 pixels at `(35,477)`;
its 305×170 party field starts at `(0,62)`, after explicitly bounded leader
and ruling-party label/value rows. Its bottom remains inside the native
717-pixel window. The neighboring native portrait and
its frame move right by 60 pixels to x=349 and x=340. The country title starts
at x=477 with a 305-pixel width, retaining its original right edge. The native
focus and spirit anchors, historical description and country-selection
controls keep their original positions. The map-selection information region remains
inside the native 492×301 panel: its party field is 350×170 at `(110,34)`,
with the leader row below and the native spirit grid at y=230. Explicit
clipping contains the presentation within these political regions. Text rows
use a native 18-point font and compact labels; the artwork row has its own
reserved space below them. Two author-supplied 64-pixel identity sprites and
the dual pies have 37 pixels of combined spacing budget in the narrower
305-pixel column. Wide Latin glyphs (including W/M), uppercase text and CJK
use a conservative proportional-width budget, so an all-uppercase party name
cannot move later presentation rows by wrapping. Original default-artwork dimensions remain an external game
asset dependency; they are not inferred from an absent DDS payload.

This is distinct from the earlier history-inline implementation. PSF no longer
writes `common/bookmarks/*.txt`, creates replacement history keys, or appends
statistics to original descriptions. The original historical text remains
fully owned by the installed game and its selected DLC variant. The native
history textbox simply gains a 160-pixel scrolling viewport.

No live HOI4 render was performed in the headless development environment.
Geometry checks establish parent bounds, preserved bindings, image dimensions,
and separate text/image structure; actual font baselines, external custom art,
and the engine's first-frame order remain part of the in-game smoke test.

## Data and artwork

Every profile has a base presentation and one presentation for each distinct
`start_overrides` boundary. For a selected date, all preceding overrides are
applied cumulatively, including group status, support, influence, positions,
regime, and an explicitly selected governing group or alliance.

Support includes active electoral organizations. Influence includes active
organizations with the configured underground/banned penalties. Each metric
normalizes its own total. Both pies use the same exact authored organization
RGB values as the campaign charts and color keys. The 63-pixel pie canvases
reserve a four-pixel transparent inset around a 27-pixel fill radius.

The governing organization follows the campaign rule: among legal government
members, prefer a party or electoral organization and select the greatest
effective influence; use the lowest stable numeric ID to break ties. Only when
no such party exists does an ordinary governing organization represent the
government. A zero-weight or absent government has an explicit caretaker
presentation. A strong court or army does not replace its coalition's party
merely because its influence is greater. The displayed ideology is the closest
archetype to the government's influence-weighted positions.

All groups and archetypes have separate native-artwork large and small sprites,
with independent authored overrides. The frontend consumes the government's
party small sprite and both party and ideology large sprites; campaign politics
and diplomacy also use both large identities. Default artwork represents broad political
families or organization types, not a claim to reproduce every historical
party emblem. See [AUTHORING.md](AUTHORING.md#custom-icons) for custom sprites.

## Files, compatibility and verification

`psf_bookmark_manifest.json` reports original source hashes and history keys,
DLC coverage, normalized metrics, and the selected compiled presentation.
Its `frontend` section lists every generated state, texture and sprite;
`history_overridden` and `runtime_render_tested` are both explicitly false.
The generated interface definitions are in `interface/psf_frontend.gfx`, and
translations are in each language's `psf_frontend` localisation file.

The original bookmark snapshots used for coverage come from the user-supplied
Paradox Interactive game script archive. Their provenance is recorded in
`psf/assets/native_bookmarks/sources.json`. They are excluded from PSF's MIT
grant. Their hashes are:

| Original game path | SHA-256 |
| --- | --- |
| `common/bookmarks/the_gathering_storm.txt` | `31d22ba3fdd6160be56f198f0ec078c09156d3fdcfadced809f73226f698422f` |
| `common/bookmarks/blitzkrieg.txt` | `54f6f23dec5a066dca37125f69a29b8cc0400b4c0d598ff6e6ba71bd82dcf25d` |

This adapter does not introduce a bookmark-file load-order conflict. The native
GUI and country-history adapters still require merging when another mod
changes the same files; use that mod's native source tree for compilation.
Changing load order alone cannot merge two incompatible native UI definitions.

Run the focused regression suites with:

```sh
python -m unittest discover -s tests -p 'test_frontend.py' -v
python -m unittest discover -s tests -p 'test_bookmarks.py' -v
python -m unittest discover -s tests -p 'test_charts.py' -v
```

They execute emitted selection/name-restoration effects across authored and
fallback profiles and both dates; cover direct governments, alliances and
caretakers; verify original histories are never overridden; inspect generated
image dimensions and exact pie colors; and check reproducible output. The UI
suite checks native identities, ancestry, separate political bounds and hidden
obsolete controls. CWTools validates script, GUI, sprite and localisation
references. These checks complement the in-game smoke test rather than
standing in for one.
