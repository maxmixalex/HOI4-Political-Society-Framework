# Political society interface

PSF replaces the political party wheel and native ideology/party labels in the domestic politics and diplomacy views. The replacement has a compact national summary and an optional sidebar. The sidebar is closed until the player opens **Organizations** or **Spectrum**; it occupies map space immediately to the right of the existing 550-pixel native window.

## Views

| View | Display and interaction |
| --- | --- |
| National summary | Actual regime, governing alliance, government support, effective influence, legitimacy, and organization count. Tooltips distinguish the institution from the government's political program. |
| Organizations | Full profile roster, including explicitly labelled inactive organizations. Rows show the short name, badge, support, effective influence, satisfaction and activity status. Select any row for details. |
| Organization details | Full name, large badge, organization kind, legal status, ideology derived by the runtime, description, live values and every configured issue position. Domestic-only actions activate, ban or legalize the group. |
| Spectrum | One-dimensional issue charts for every axis declared by the content pack. Icons read live position variables, not baked opening coordinates. Each organization gets a separate thin horizontal lane, so identical positions and later changes cannot completely hide another group's icon. Only the horizontal coordinate carries political meaning. Hovering explains the axis and both endpoints; clicking opens the organization. |
| Alliances | All declared alliances and the reserved transitional cabinet, live government/opposition/electoral role, cohesion and current members. Membership strings respond to script changes without rebuilding the mod. |

Long lists, descriptions and charts use the game's existing `right_vertical_slider`, mouse wheel input and smooth scrolling. The sidebar is 414×590 logical pixels. The combined native view plus sidebar needs approximately 966 logical pixels of horizontal room. Very large game UI scaling can therefore require a higher display resolution.

The lobby cannot show initialized PSF runtime state before the campaign starts. Both the interesting-country selection information and map-selection details remove the old party/ideology information and show a concise PSF notice. This is intentionally a static pregame notice; it is not represented as a live political simulation.

## Native window safety

`psf/ui.py::patch_native` makes conservative edits to the supplied native GUI definitions. Obsolete widgets get native `hide = yes` and move horizontally off-screen as a fallback if engine code subsequently calls `show`. Their original Y positions are retained so the diplomacy scrollbar does not gain a giant negative vertical extent:

- `countrypoliticsview.gui`: move `chart_explanation`, `political_pie_chart`, the old ideology strip, and the ideology/election text off-screen. Keep the `ruling_party_info` container itself because it also contains faction and balance-of-power controls. Add the summary and sidebar mounts.
- `countrydiplomacyview.gui`: move the ideology icon and obsolete party/pie containers off-screen. Preserve the leader, national focus, diplomatic actions, intelligence and relation widgets. Add mounts in the actual native layout.
- `frontendgamesetupview.gui`: move the political wheel and both sets of native ideology/party fields off-screen; preserve all named widgets and their original ancestry.

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

The default 24×24 and 64×64 badges are original deterministic TGA artwork produced using the Python standard library. Their shape reflects `icon` (`party`, `union`, `business`, `military`, `religious`, `civic`, `faction`); color is stable for each organization ID. They are symbolic framework badges, not claimed reproductions of historical organization logos.

To supply authored graphics, define `small_icon` and `large_icon` as existing `GFX_...` sprite identifiers in the organization's data and provide their `.gfx`/texture assets in the content mod. Small icons should use a 24×24 logical canvas and large icons 64×64. The chart scales the small icon to 16×16 to keep separate lanes usable.

The UI generates complete English and Simplified Chinese `psf_ui_*` localization with UTF-8 BOM. Framework content owns the `psf_group_*`, `psf_axis_*`, `psf_ideology_*`, `psf_regime_*` and `psf_alliance_*` keys. Descriptions and tooltips use those keys rather than hardcoded country names. Localization definitions derive organization ideology, legal status, regime, coalition role and membership from current variables.

An organization can be both legally prohibited and operationally underground. The status tooltip distinguishes that combination from ordinary clandestine activity; moving underground does not silently imply legalization.

Displayed organization influence is `psf_g_<id>_effective_influence`. A tooltip also exposes baseline `psf_g_<id>_influence`, so banning a group visibly lowers usable power while legalizing it restores institutional access. Support remains independently recorded.

## Verification

`python -m unittest tests.test_ui -v` covers retained native widget identities/ancestry, unchanged faction/balance-of-power controls, both pregame information panels, hard failure on a changed native tree, stable numeric IDs, explicit comparisons, foreign-country action isolation, live spectrum positions and overlapping-position click access, authored icon overrides, TGA dimensions, and bilingual key parity.

`python tools/ui/audit_layout.py <compiled-content-mod> --svg <output.svg>` checks all summary bounds, native control boundaries, sidebar and scrollbar viewports, and hidden-widget vertical extents. The optional SVG is an explicitly labelled geometric projection of the emitted coordinates, not a game screenshot. In the supplied native layout, the political summary ends at Y=382 before the native management strip begins at Y=383; the diplomatic summary ends at Y=86 before the focus area at Y=88.

The real Rust cwtools validator validates the generated GUI, scripted GUI, scripted localization and references together with the framework. Static validation and these tests cannot certify engine rendering. A release check in HOI4 should still confirm the politics view, a foreign diplomacy view, tooltips, scrollbars, both lobby routes, and organization operations at the user's chosen resolution/UI scale. No screenshot in this repository should be interpreted as a completed engine render unless it is explicitly identified as one.
