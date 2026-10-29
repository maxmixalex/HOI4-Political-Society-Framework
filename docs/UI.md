# Political society interface

PSF replaces the political party wheel and native ideology/party labels in the domestic politics and diplomacy views with **two live pies**, a compact national summary and an optional sidebar. The sidebar is closed until the player opens **Organizations**, **Spectrum**, or a pie; it occupies map space immediately to the right of the existing 550-pixel native window.

## Views

| View | Display and interaction |
| --- | --- |
| National summary | Support and influence pies, actual regime and governing alliance. The domestic summary additionally shows government support, effective influence, legitimacy and organization count. Native tooltips provide the full breakdown and distinguish institutions from the government's political program. |
| Organizations | Full profile roster, including explicitly labelled inactive organizations. Compact 44-pixel rows use the original game's `GFX_tiled_button` chrome and show short name, badge, modified support, effective influence, modified satisfaction and activity status. Select any row for details. |
| Organization details | Full name, large badge, organization kind, legal status, ideology derived by the runtime, description, live values and every configured issue position. Tooltips show base values, modifier-adjusted influence, named modifier sources and remaining days or permanent duration. Domestic-only actions activate, ban or legalize the group. |
| Spectrum | One-dimensional issue charts for every axis declared by the content pack. Icons read live position variables, not baked opening coordinates. Each organization gets a separate thin horizontal lane, so identical positions and later changes cannot completely hide another group's icon. Only the horizontal coordinate carries political meaning. Hovering explains the axis and both endpoints; clicking opens the organization. |
| Alliances | All declared alliances and the reserved transitional cabinet, live government/opposition/electoral role, cohesion and current members. Membership strings respond to script changes without rebuilding the mod. |

Long lists, descriptions and charts use the game's existing `right_vertical_slider`, mouse wheel input and smooth scrolling. The sidebar is 414×590 logical pixels. The combined native view plus sidebar needs approximately 966 logical pixels of horizontal room. Very large game UI scaling can therefore require a higher display resolution.

## Two independent pies

Both domestic politics and foreign diplomacy display two 63-pixel pies with the game's original `GFX_pol_piechart_overlay_63x63` mask. The support pie normalizes active organizations marked `electoral`; overlapping approval of trade unions and other civil organizations does not become additional election votes. The influence pie includes every active organization's effective influence, after modifiers and legal-status suppression. Political support can therefore remain substantial after a ban while the same group's usable institutional influence falls.

`psf/charts.py` partitions the disk into 180 pre-oriented sectors. Every interior pixel belongs to exactly one sector, which avoids the gaps created by rotating narrow antialiased wedge textures. Cropping each sector's frame strip limits texture storage. Frames use the same stable organization colors as badges. A zero total produces a neutral disk and a meaningful no-data tooltip.

`psf_update_charts_<profile>` runs after the runtime has recalculated modifiers and legal status. It caches `psf_pie_support_frames` and `psf_pie_influence_frames`, plus each organization's normalized `*_support_share` and `*_influence_share`. Cumulative boundaries are rounded once using the documented `round_temp_variable`, so independently rounded shares cannot leave gaps or overfill the circle. The 180-sector image is quantized to roughly 0.56 percentage points; native tooltips retain the normalized numeric values. Each summary uses `dirty = psf_ui_revision`, avoiding per-tick reevaluation of the chart frame properties.

## Country selection

The native interesting-country selection screen's **history** field supplies the selected country and bookmark date. The bookmark adapter embeds a real compiled support/influence snapshot there as a text icon, followed by the original history localization. It applies the profile's dated `start_overrides`, including support, influence and activity changes, and the configured influence suppression factors. The stock 1936 and 1939 bookmarks therefore receive their own data. Original country descriptions and bookmark conditions remain intact.

The history textbox retains its engine-owned identity and ancestry, with a 160-pixel viewport and the original `standardtext_slider`; adding the charts does not discard the historical narrative or extend into the selection buttons. This is an opening snapshot, not campaign simulation before the start button is pressed.

The separate map-selection right-hand panel has no equivalent native `history` binding in the supplied interface. Its obsolete ideology/party wheel and labels are hidden, and its concise PSF notice remains. PSF does not invent a frontend country context or claim that this second panel displays the per-country snapshot. See [BOOKMARKS.md](BOOKMARKS.md) for the adapter's precise coverage.

## Native window safety

`psf/ui.py::patch_native` makes conservative edits to the supplied native GUI definitions. Obsolete widgets get native `hide = yes` and move horizontally off-screen as a fallback if engine code subsequently calls `show`. Their original Y positions are retained so the diplomacy scrollbar does not gain a giant negative vertical extent:

- `countrypoliticsview.gui`: move `chart_explanation`, `political_pie_chart`, the old ideology strip, and the ideology/election text off-screen. Keep the `ruling_party_info` container itself because it also contains faction and balance-of-power controls. Add the summary and sidebar mounts.
- `countrydiplomacyview.gui`: move the ideology icon and obsolete party/pie containers off-screen. Preserve the leader, national focus, diplomatic actions, intelligence and relation widgets. Add mounts in the actual native layout.
- `frontendgamesetupview.gui`: move the political wheel and both sets of native ideology/party fields off-screen; preserve all named widgets and their original ancestry.

All generated `.gui` and `.gfx` files use **UTF-8 without BOM**. The engine log supplied for this repair showed the BOM becoming part of `guiTypes`/`spriteTypes`, preventing those root declarations from loading and culminating in `Undefined GUI_TYPE: frontendgamesetupview`. Localization `.yml` retains its required UTF-8 BOM. The two readers' encoding requirements must not be conflated.

Every mount added by PSF is a nested container, so scripted GUI parents use its runtime `_instance` name, as in the supplied TNO scripts. Domestic and diplomatic sidebars also own distinct top-level `window_name` containers. They no longer attach two contexts to a single window. Summary and sidebar definitions are emitted into separate files so validation discovers them all; no GUI is truncated to satisfy a file-size limit.

The patcher tokenizes the real tree, ignores comments and quoted braces, and requires every targeted widget to exist exactly once in its expected parent. It fails on an unexpected game layout rather than silently deleting or replacing a different widget. It verifies that all 1,095 original named widgets retain their type, name and named ancestry. The source snapshot SHA-256 values and exact hidden paths are written to `psf_ui_manifest.json` in the compiled content pack.

PSF does **not** globally replace `GFX_political_chart`: that sprite is also used for unrelated faction-influence charts. Trade-resource pies and other nonparty charts retain their normal behavior.

These complete native GUI files are version-specific overrides. A total conversion or game update that changes them needs a deliberate UI compatibility patch. A content author can pass another native interface directory to `generate_ui(..., vanilla_path=...)`; the same structural checks apply. Shipped source snapshots reside under `psf/assets/native_gui` and are included in the installed Python package. Their underlying source remains Paradox material; the repository's code license does not relicense those game-derived definitions.

## Scope and multiplayer behavior

A domestic view uses `player_context`. Diplomacy uses `selected_country_context`: the target is `THIS`, while `ROOT` is the viewing player. Display values resolve in the target country's context; every UI state assignment is explicitly `ROOT.psf_ui_*`.

Selecting a foreign organization, opening a chart, changing tabs or closing the sidebar never writes foreign political state. All three political mutation buttons require `tag = ROOT` both in their enable trigger **and inside the effect**, together with a valid current status and sufficient political power. Ban also rejects governing organizations. Costs are 50 PP to ban, 25 PP to legalize, and 25 PP to activate. Low-level framework effects stay separate from those player-facing costs.

When the player changes the viewed country while an organization is selected, `psf_ui_selection_is_current` checks the new profile. An invalid old selection falls back to the organization list instead of showing an empty details pane.

All identity, page, membership and status comparisons emit `check_variable = { var = ... value = ... compare = equals }`. This is essential because the engine's default comparison is greater than or equal and PSF identifiers are stable, nonsequential numbers.

UI selection variables are normal country variables owned by the player, as in established scripted-GUI usage. Players controlling the same country share that country's selections; PSF does not claim local per-client selection isolation for cooperative same-country multiplayer.

## Icons and localization

The default 24×24 and 64×64 badges are original deterministic TGA artwork produced using the Python standard library. Their shape reflects `icon` (`party`, `union`, `business`, `military`, `religious`, `civic`, `faction`); color is stable for each organization ID. They are symbolic framework badges, not claimed reproductions of historical organization logos. List backgrounds, buttons, scrollbars and in-game pie overlays use the original game assets.

To supply authored graphics, define `small_icon` and `large_icon` as existing `GFX_...` sprite identifiers in the organization's data and provide their `.gfx`/texture assets in the content mod. Small icons should use a 24×24 logical canvas and large icons 64×64. The chart scales the small icon to 16×16 to keep separate lanes usable.

The UI generates complete English and Simplified Chinese `psf_ui_*` localization with UTF-8 BOM. Framework content owns the `psf_group_*`, `psf_axis_*`, `psf_ideology_*`, `psf_regime_*` and `psf_alliance_*` keys. Descriptions and tooltips use those keys rather than hardcoded country names. Localization definitions derive organization ideology, legal status, regime, coalition role and membership from current variables.

An organization can be both legally prohibited and operationally underground. The status tooltip distinguishes that combination from ordinary clandestine activity; moving underground does not silently imply legalization.

Displayed organization influence is `psf_g_<id>_effective_influence`. A tooltip exposes baseline `psf_g_<id>_influence` and `psf_g_<id>_modified_influence` before the legal-status restriction. Support, satisfaction and spectrum markers read the corresponding `modified_*` values. Applying or removing a temporary source therefore changes the list, details, charts and axis markers together without overwriting base attributes.

For every applicable named source, scripted localization checks its active flag and remaining-day variable. Active timed sources show their localized name and remaining days; permanent sources show "until removed". Inactive sources produce no line. These details are available from the organization's row and details tooltip, alongside the active source count. Native idea/trait modifiers continue to use the engine's own modifier tooltips, with their numerical contributions included in the displayed effective values.

## Verification

`python -m unittest tests.test_ui -v` covers retained native widget identities/ancestry, unchanged faction/balance-of-power controls, both pregame information panels, hard failure on a changed native tree, stable numeric IDs, explicit comparisons, foreign-country action isolation, modified spectrum positions and overlapping-position click access, authored icon overrides, TGA dimensions, bilingual key parity, byte-level root encoding, context ownership and native mount names, both complete pies, pixel coverage without seams and native row chrome.

`python -m unittest discover -s tests -p 'test_charts.py' -v` executes the emitted HOI4 cache effects in the strict script interpreter. It checks support/influence separation, changed modifier and suppression values, stale-array replacement, zero-total safety, fractional allocation, and date-specific country-selection snapshots. Unknown engine commands fail instead of being silently ignored.

`python tools/ui/audit_layout.py <compiled-content-mod> --svg <output.svg>` checks all summary bounds, native control boundaries, sidebar and scrollbar viewports, and hidden-widget vertical extents. The optional SVG is an explicitly labelled geometric projection of the emitted coordinates, not a game screenshot. In the supplied native layout, the political summary ends at Y=382 before the native management strip begins at Y=383; the diplomatic summary ends at Y=86 before the focus area at Y=88.

The real Rust cwtools validator validates the generated GUI, scripted GUI, scripted localization and references together with the framework. Static validation and these tests cannot certify engine rendering. A release check in HOI4 should still confirm the politics view, a foreign diplomacy view, tooltips, scrollbars, both lobby routes, and organization operations at the user's chosen resolution/UI scale. No screenshot in this repository should be interpreted as a completed engine render unless it is explicitly identified as one.

## Contract references

- Supplied original-game `interface/countrypoliticsview.gfx`, `interface/core.gfx`, `interface/countryofficercorpview.gfx`, `interface/popupwindow.gui`, `interface/frontendgamesetupview.gui`, and `documentation/effects_documentation.md` establish the reused assets, native textbox scrollbar and supported variable/array commands.
- Supplied TNO `common/scripted_guis/TNO_Ukraine_GUI.txt` and `TNO_economy.txt` demonstrate `_instance` parents for nested native anchors; KR's `_documentation.md` records scripted-GUI context, properties and dirty-variable behavior.
- [HOI4 Scripted GUI modding](https://hoi4.paradoxwikis.com/Scripted_GUI_modding) and [Interface modding](https://hoi4.paradoxwikis.com/Interface_modding) describe the relevant modding contracts. Direct wiki retrieval was blocked during this repair; code was cross-checked against the supplied engine documentation and [upstream CWTools rules](https://github.com/cwtools/cwtools-hoi4-config/blob/master/Config/common/scripted_guis.cwt).
- [Yard1's scripted GUI pie example](https://github.com/Yard1/HoI4-Scripted-GUI-Pie-Chart) demonstrates native sprite frames driven by a country array. PSF generates its own pre-oriented pixel partition and cached organization weights.
