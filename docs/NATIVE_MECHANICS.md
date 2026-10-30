# Native politics and immediate initialization

PSF 0.4.1 has two integration modes. `compat` keeps the installed game's native
political mechanics and is the default for new integrations. The bundled
vanilla example uses `mechanics_mode: "strict"` and `bridge_mode: "export"`:
PSF support, influence, government and actual institutions are authoritative,
while the four native ideology IDs remain available to existing game scripts.

This is an engine-compatible replacement of the principal numeric political
mechanics. It is not a claim that every vanilla focus, event, decision, peace
conference or espionage condition has been rewritten. The exact boundary is
described below, including what still depends on a native compatibility slot.

## What strict mode changes

### Native popularity no longer supplies the normal stability bonus

The supplied original `common/defines/00_defines.lua` contains
`NCountry.BASE_STABILITY_PARTY_POPULARITY_FACTOR = 0.15`. Strict mode sets it to
zero. Some original ideas, leader traits and dynamic modifiers independently
add `party_popularity_stability_factor`; merely changing the define would not
remove those sources.

The generated `psf_native_political_policy` dynamic modifier cancels that
additional coefficient. Each refresh reads the total through
`modifier@party_popularity_stability_factor` and calculates:

```
new PSF offset = previous PSF offset - observed total
```

The observed total includes the previous PSF offset. Subtracting the total
from that previous offset prevents an alternating-sign feedback bug. A forced
native dynamic-modifier update before and after the calculation keeps the
sample and the resulting coefficient current. The test suite executes changes
from +20% to +35%, removal to zero, and a -15% source with repeated refreshes.
PSF's separate legitimacy-based stability and political-power modifiers remain.

The supported modifier accessor and immediate update effect are in the pinned
[CWTools modifier rules](../tools/ci/vendor/rules/modifiers.cwt) and
[effect rules](../tools/ci/vendor/rules/effects.cwt). The calculation tests
execute emitted Clausewitz effects; they do not substitute for a game launch.

### Native ideology definitions retain identities, share mechanics

The adapter overrides the original `common/ideologies/00_ideologies.txt` under
its original filename. It preserves all subtype IDs and their definitions,
native colors, and dynamic faction-name lists. Existing character subtypes and
`has_government` conditions can therefore still resolve. Its source is retained
in [native_ideologies](../psf/assets/native_ideologies/00_ideologies.txt).

All four groups receive the same mechanical definition:

- Their original numeric country and faction modifiers are removed. This
  removes the fascist major-war justification discount, different intelligence
  disclosures, neutrality drift defense, and ideology-specific tension,
  embargo and faction-trade bonuses.
- The four AI ideology styles become the same neutral AI style. Desired-unit
  multiplier becomes 1.0 and the core-state-return threshold becomes zero.
- War and faction effects on world tension use the same 1.0 multiplier.
- Declaring war on the same native ideology and guaranteeing another native
  ideology are permitted equally. Puppet, volunteer and force-government
  capabilities are common. Collaboration and exile-host capability are also
  common rather than privileges of a specific native label.
- Boosting native ideology is disabled through the common ideology rules and
  `can_be_boosted = no`. Existing native event or espionage scripts may still
  change a four-slot percentage; the export bridge does not import that change
  into PSF support and restores the projected percentages on its next refresh.

The adapter rejects a source with additional, missing or renamed native
ideology groups. A total conversion should select `compat` and provide its own
integration instead of silently replacing its ideological system.

### Actual institutions select diplomacy constraints

The generated dynamic policy reads `psf_elections_enabled`, which is derived
from the authored PSF regime. It does not read the native ruling-party slot or
the currently governing organization's ideological classification.

These are explicit policy defaults for this adapter, not an inference that all
real electoral governments had identical foreign policies:

| World-tension threshold | PSF electoral regime | PSF non-electoral regime |
| --- | ---: | ---: |
| Justify a war goal | 100% | 50% |
| Join a faction | 80% | 40% |
| Lend-lease | 50% | 50% |
| Send volunteers | 50% | 40% |
| Guarantee independence | 25% | 40% |

Electoral regimes additionally require a threatening target for war-goal
justification, permit lowering tension, and disallow creating collaboration
governments. The other policy does the reverse. Other ideas or game rules can
still impose their own restrictions. The values use the original democratic
and neutral thresholds as a recognizable baseline; the selector is now PSF's
actual constitution. Each regime may override individual values with
`native_policy`; unspecified fields retain the documented defaults. The five
threshold keys in the table accept fractions from 0 to 1, and the three rule
keys accept Boolean values. Unknown keys, out-of-range thresholds and strings
such as `"yes"` fail authoring validation. A regime change resets every policy
field before applying its overrides, so old rules cannot leak into its successor.

For example, a fictional electoral institution can declare:

```json
"native_policy": {
  "generate_wargoal_tension": 0.75,
  "join_faction_tension": 0.6,
  "lend_lease_tension": 0.25,
  "send_volunteers_tension": 0.25,
  "guarantee_tension": 0.25,
  "can_only_justify_war_on_threat_country": true,
  "can_lower_tension": true,
  "can_create_collaboration_government": false
}
```

These are authored game rules, not historical claims or a fixed property of an
ideological category. The vanilla example's fictional `workers_monarchy`
demonstrates the override.

The native election scheduler is disabled. PSF's election timer, electoral
pacts, eligible organizations and legal ballots still operate according to the
PSF regime. Thus a native four-slot election cannot independently install a
second government between PSF election cycles.

### Global ideology affinity bonuses are neutralized

The adapter writes only the following known define overrides from the supplied
original snapshot:

| Original mechanism | Strict behavior |
| --- | --- |
| `NCountry.BASE_STABILITY_PARTY_POPULARITY_FACTOR` | 0 |
| `NTrade.PARTY_SUPPORT_TRADE_FACTOR` | 0 |
| Same/different-ideology relation-maintenance costs | Both 0.3 |
| `NDiplomacy.IDEOLOGY_JOIN_FACTION_MIN_LEVEL` | 0 |
| Three ideology-based embargo AI weights | 0 |
| Same-ideology equipment-purchase and market-access acceptance | 0 |
| Same-ideology naval-blockade reluctance | 0 |
| Wrong-ideology faction penalty and same-ideology major bonus | 0 |
| Same-ideology lend-lease and volunteer AI desires, including civil wars | 0 |

The adapter additionally clears the neutral-ideology faction penalty, neutral
threat paranoia, communist non-neighbor preference, democratic military-access
bonus, all eight ideology-specific call/join ally weights, and the complete
27-entry befriend/ally/antagonize matrix. Both market scripted-ideology acceptance
factors become zero. Diplomatic and operative native ideology boosting supplies
no drift. The common base diplomatic and military calculations remain.

The exact 61 names and namespaces are enumerated in
[mechanics.py](../psf/mechanics.py). A build report records which source ideology
definition was patched and its SHA-256. No claim is made that later game
versions will retain every define unchanged.

### Generic party opinion and peace-conference prices

The strict adapter also overrides the original opinion and generic peace-cost
files under their original filenames. `same_ruling_party`, `similar_ruling_party`
and `different_party_types` all have zero value, removing the automatic +20,
+10 and -10 relationship differences. All thirteen original generic
`category = ideology` peace-cost entries are disabled and their multiplier is
neutralized. Annexation, liberation, puppeting and forced-government prices
therefore no longer acquire these generic native ideology discounts or surcharges.

Other original statements are preserved, including core-state rules,
war-related prices and explicitly scripted diplomatic events. The compiler
uses the supplied originals or the matching `--vanilla` installation and records
source hashes plus every changed definition. Unexpected source structure fails
the build rather than silently patching a different rule.

## What remains native

The four engine groups are compatibility identities. Strict mode projects the
current PSF government's classified position to one of them; a caretaker has
no new classification to project. Existing country leaders and vanilla
`has_government`, party-popularity, subtype, flag and cosmetic conditions can
still select vanilla story branches. Focus/event effects can still recruit
leaders, start civil wars, create puppets, change diplomatic relations, add
ideas, or set a native government. PSF does not translate every such story
choice into authored organization membership changes.

The strict government-change hook restores PSF's projection, with a recursion
guard. That protects the PSF government, but it does not undo all the other
effects of a vanilla event. Country-specific peace-conference prices/AI (such as
Yalta outcomes), occupation rules that directly inspect ideology, hard-coded
native behavior not exposed by the
available rules, and scripted ideology-dependent AI strategies also remain
integration work. The export bridge prevents native popularity drift from
silently becoming PSF support; it does not remove those scripts from the game.
For example, the original `NAI.DEMOCRATIC_AI_FACTION_KICKING_PLAYER_THREAT_DIFFERENCE`
still belongs to a hardcoded democratic-faction/player-expulsion branch. It is
not set to zero speculatively: zero could lower a threshold rather than disable
the branch. Its behavior needs an engine-backed integration decision.

For a curated story overhaul, call `psf_govern_group_<id>`,
`psf_govern_<alliance>`, regime changes, and organization effects from the
overhaul's events. Do not describe hiding the native widgets as removal of
these mechanical dependencies. The `compat` mode is available when a content
pack deliberately needs the native behavior.

## Initialization without advancing a day

The strict vanilla adapter bundles the user-supplied original country-history
snapshot: 364 files, about 1.8 MB. Each original filename and every original
statement is preserved. The compiler inserts `psf_history_bootstrap = yes` at
the root boundary and at the end of every top-level dated block, followed by
the frontend preparation effect. It does not replace a complete history with
a small second file containing only a PSF call. One exact supplied source,
`NOR - Norway.txt` (SHA-256
`f26704f9311af80a35a72d7620f0e991eb0682f038ded4c663f293b4f60ca3a1`),
was already missing its last dated block's closing brace. The output adds that
one brace and records the known source repair. That same exact source has a
pre-Man-the-Guns conditional with no effects; the output preserves its lines
as comments, eliminating the empty-branch diagnostic without changing behavior.
The bundled original remains unchanged; other unbalanced input files are
rejected rather than guessed at.

Generated history uses UTF-8 without a BOM, matching the script preflight
requirement. The 336 originals carrying a BOM retain their original bundle
bytes and source hashes; each build-report entry records `source_had_bom` and
`encoding_normalized`. Restoring that encoding marker and reversing only the
documented insertions/known repairs recovers each original byte for byte.

The history-specific entry point may rebuild initial PSF state. This matters
when a later bookmark changes a fallback country's native government after
the root history has run. The final applicable history boundary must select
the corresponding fallback. Authored profile date overrides apply to the
selected start date. This happens before the first daily update; it also gives
native frontend fields country-scoped data during setup.

`psf_bootstrap` is the separate, non-destructive runtime entry point. It
initializes a previously uninitialized country, or migrates and rebuilds an
existing PSF country. Repeated calls refresh charts, identity, government,
native policy and the UI revision. They do not advance the date, apply daily
drift, consume modifier duration, rerun an election, or reset authored support
and satisfaction. The politics UI calls it when opening the organization or
spectrum view, allowing an upgraded save to rebuild without waiting a day.
The startup and release hooks provide additional coverage; `on_startup` is
not presented as a universal save-load callback.

The runtime migration preserves a saved government's recognized alliance.
An old automatically generated transition cabinet, removed in 0.4, becomes a
direct government of its strongest still-legal governing organization. The
legacy private cabinet variables can remain harmlessly in the save; the new
UI and model no longer invent or display that alliance.

## Snapshot limits and verification

The supplied archive did not identify its exact HOI4 build. The bundled
history is therefore a specific source snapshot, not a version-independent
history patch. The compiler's existing `--vanilla /path/to/game/interface`
option also selects the sibling `history/countries` and `common/ideologies`
directories for strict integration. This lets a licensed installation supply
matching originals. A mismatching snapshot can overwrite changes from another
game version or mod; use `compat` or rebuild from the intended installation.

The test suite checks byte-for-byte preservation after removing only PSF's
insertions, every bundled filename, both root/date scheduling orders in the
script interpreter, immediate fallback selection, cosmetic and chart refresh,
government migration, alliance coexistence and offset cancellation. Pinned
CWTools checks emitted scripting against the available original symbols and
rules. The actual HOI4 executable is not available in this environment, so
frontend rendering, engine callback timing and the complete campaign still
require an in-game acceptance run. Static or interpreter checks are not
described as that acceptance run.

## Inherited source diagnostics are not all rule false positives

The original history snapshot and the pinned CWTools rules/cache have specific
differences. These were checked against the supplied source bytes; none should
be fixed by changing vanilla gameplay just to obtain a clean diagnostic count.

| Diagnostic area | Directly checked source and rule evidence |
| --- | --- |
| PRC missing root `capital` | `PRC - ComChina.txt` starts with DLC-dependent `set_capital` blocks selecting state 622 or 1032. The pinned `history/country_history.cwt` requires a root `capital` property and does not account for that alternative. Adding a fixed capital would change the source's DLC behavior. |
| Austrian template lock reported as a Boolean mismatch | `AUS - Austria.txt` uses `{ is_locked = yes desc = ... }`. The pinned `effects_new.cwt` both documents and defines this block form alongside the Boolean form. The source should retain its explanatory lock reason. |
| `obsolete` reported as `false` instead of `yes` | ARG, CZE and HUN source designs explicitly use `obsolete = no`; the rule currently permits only literal `yes`. Changing the designs to obsolete would alter availability and production. |
| `optional_assets` and operative `female` | The original USA and other country histories contain these fields. The equipment-variant rule has no `optional_assets` entry; the operative rule lists `gender` rather than the source's `female`. This is an API/schema representation mismatch, not proof that either representation was tested in the actual game here. |
| Empty conditionals | Original country files contain deliberate condition-only ship-variant sections, for example POR's pre-Man-the-Guns branch. Those branches have no gameplay effects. They remain original-source diagnostics unless covered by the explicitly recorded NOR repair. |
| Missing `AZR_1936` | Azerbaijan's original history already references this OOB. The supplied archive has no entry with that name. This is an unresolved source dependency, not a verified rule false positive. Do not manufacture an army merely to satisfy the validator. |
| Missing PRC portraits | Original PRC history already references `GFX_portrait_PRC_mo_xiong`, `GFX_portrait_PRC_xiong_xianghui` and `GFX_portrait_PRC_li_kenong`; their definitions are absent from the supplied interface GFX files. A complete matching installation must resolve these asset dependencies. |

Representative original input SHA-256 values, before BOM normalization:

```text
PRC - ComChina.txt        658b54d7fe97fbeb87ceb35c6a42fecfd828b79335e2926e9077a181f7a9fa23
AUS - Austria.txt        7c8bd87f0cce2bd261f9e68b0c2bda45b5c0f4541e95d352e80d07a47294f67f
USA - USA.txt            73a96e416be9b14d696af8094a1505af7616521cc991f291e716d85abab9bec4
AZR - Azerbaijan.txt     f04f12f8457d2e20af1bc2eee4726d9ab24189c84f67eca2c861bc440b6b11fc
CZE - Czechoslovakia.txt a5a42f7e68ce0feac9700245605026dee7a168e6a6ccfdf1ed879d979ce43cfc
ARG - Argentina.txt      320308448fd0eae381009a535b3b600baf4b00dc53adeee60d1f808b2c9caf48
HUN - Hungary.txt        ebddf2be4581bac4c466cedb6b97d103b15a1dd08e11d4f35b5146a842ffe7ca
```

The build report records every input hash. Baseline comparison must retain the
raw diagnostics and match an inherited diagnostic to the unchanged source and
mapped source location. A passing PSF diagnostic delta is not a claim that the
raw report contains no errors, or that missing original assets are known safe.

To rebuild and validate against a complete licensed installation, use the
interface directory for compilation and the game root for CWTools:

```bash
.venv/bin/python -m psf compile examples/vanilla/manifest.json --output build/installed-game --vanilla "/path/to/Hearts of Iron IV/interface"
.venv/bin/python tools/ci/validate.py --root build/installed-game --reports build/installed-game-validation --vanilla "/path/to/Hearts of Iron IV"
```

Keep the generated and original-source diagnostic reports. Matching game/DLC
assets can resolve omitted symbols; they cannot by themselves correct a
validator rule mismatch. An actual game launch remains necessary to validate
the installed version's behavior.
