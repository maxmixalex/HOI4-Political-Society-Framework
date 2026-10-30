# Authoring PSF content

PSF takes one declarative registry and generates one content mod that depends on the reusable framework. The authoritative input contract is [`psf/schemas/manifest.schema.json`](../psf/schemas/manifest.schema.json); cross-reference and calendar checks are implemented in [`psf/model.py`](../psf/model.py).

The compiler accepts JSON, YAML and TOML. It rejects duplicate JSON/YAML mapping keys, unknown schema fields, invalid IDs, out-of-range values, incomplete coordinate vectors, invalid dates and references to a different country's organizations. It does not execute arbitrary strings from the manifest as script.

## Start from a complete input

Three equivalent, complete minimal manifests are included:

- [`examples/minimal/manifest.json`](../examples/minimal/manifest.json)
- [`examples/minimal/manifest.yaml`](../examples/minimal/manifest.yaml)
- [`examples/minimal/manifest.toml`](../examples/minimal/manifest.toml)

Each has two axes, four compatibility prototypes, four institutional definitions and four fallback profiles. They validate independently and normalize to the same registry. They demonstrate the file formats, rather than claim to be balanced historical content.

```sh
python -m psf validate examples/minimal/manifest.json
python -m psf validate examples/minimal/manifest.yaml
python -m psf validate examples/minimal/manifest.toml
python -m psf compile examples/minimal/manifest.yaml --output build/minimal
python tools/ci/validate.py --root build/minimal --self-test
```

For a full content starting point, copy the [vanilla manifest](../examples/vanilla/manifest.json). Change its top-level `id` and bilingual name, then replace or extend its profiles. The ID `psf` is reserved for the core framework. A manifest has one authoritative format; the three minimal files are equivalent demonstrations, not a requirement to maintain every edit three times.

The normal author loop is:

```sh
python -m psf validate my_manifest.json
python -m psf compile my_manifest.json --output build/my_mod
python -m psf inspect my_manifest.json --group my_country_reformers
python -m psf pack --root build/my_mod --output artifacts/my_political_mod.zip
```

The named group in the inspection command must exist in your own manifest. For the supplied vanilla input, use `ger_spd`. The same real CWTools gate accepts custom output roots through `python tools/ci/validate.py --root build/my_mod --self-test`; it reads the generated content ID from the build manifest. The [CI guide](../tools/ci/README.md) explains full game dependencies and external-symbol handling.

## Registry structure

| Top-level field | Purpose |
| --- | --- |
| `schema_version` | Currently the string `1.0` |
| `id` | Output content-mod directory and stable content identifier |
| `name` | Bilingual mod name |
| `axes` | Political dimensions, labels, endpoint meanings, descriptions and weights |
| `ideologies` | Coordinate prototypes and native compatibility mappings |
| `regimes` | Actual institutional templates, each using a subset of axes |
| `profiles` | Country-specific political registries selected by `tag` |
| `modifiers` | Optional named permanent/timed attribute sources, with add/factor/daily changes and optional eligible group IDs |
| `fallback_profiles` | Exactly one template for each native compatibility category |
| `scenarios` | Optional dated, one-time events with declared operations |
| `settings` | Optional balance, cadence and bridge overrides |
| `sources`, `notes` | Optional author provenance and bilingual explanatory notes |

Identifiers use lowercase ASCII letters, digits and underscores, begin with a letter and contain at most 63 characters. Group and alliance IDs are globally unique across all profiles. A tag-specific profile uses a three-character country tag; a fallback profile instead uses `engine_ideology`.

Every localization object contains nonempty `english` and `simp_chinese` values. The generated localization uses those two languages and UTF-8 with BOM. More language identifiers are not silently accepted by the present schema; extending language support requires updating the schema and generators together.

## Define a dimension

This is a single `axes` entry from the nine-axis design, not a complete manifest:

```json
{
  "id": "head_of_state",
  "name": {"english": "Head of state", "simp_chinese": "国家元首"},
  "description": {
    "english": "Preference for an elected or hereditary head of state.",
    "simp_chinese": "倾向选举产生或世袭继承的国家元首。"
  },
  "left": {"english": "Elected or republican", "simp_chinese": "选举或共和"},
  "right": {"english": "Hereditary", "simp_chinese": "世袭"},
  "weight": 1
}
```

Adding an axis requires adding its coordinate to every organization and ideology prototype. Regimes need only include it if it describes an actual institutional constraint. Removing an axis requires removing the corresponding declarations as well. The compiler regenerates the required spectrum chart; there is no fixed nine-axis UI limit built into the content data.

Coordinates are −100…100. Weight is positive and defaults are explicit in the supplied examples. Endpoint labels describe the axis; the runtime does not infer that `left` means morally preferable, economically left-wing, or a particular native ideology.

## Define an organization

An organization can be declared before it is politically active. The following complete group record fits the vanilla example's nine-axis profile structure:

```json
{
  "id": "ger_civic_reform",
  "kind": "civic",
  "name": {"english": "Civic Reform Association", "simp_chinese": "公民改革协会"},
  "short_name": {"english": "Civic reform", "simp_chinese": "公民改革派"},
  "description": {
    "english": "An association seeking constitutional participation and civic rights.",
    "simp_chinese": "寻求宪政参与与公民权利的社团。"
  },
  "positions": {
    "economy": 20,
    "culture": -30,
    "society": -40,
    "nation": -65,
    "religion": -45,
    "authority": -70,
    "foreign_policy": -60,
    "liberties": -85,
    "head_of_state": -80
  },
  "support": 8,
  "influence": 0,
  "satisfaction": 20,
  "status": "inactive",
  "electoral": false,
  "icon": "civic"
}
```

Add that record to the Germany profile's `groups`, not the top level. Its independent support score can represent a latent constituency while inactive status prevents effective influence. Activation and the later assignment of institutional resources are separate content choices.

`kind` is an extensible identifier. Native icon defaults support parties, unions, business associations, military organizations, religious bodies and civic organizations. A group's `kind` and icon category need not be the same string; the example uses `trade_union` with `icon: union`.

`electoral` controls ballot participation independently of type. A union can have public support without receiving its own additional electoral votes. Avoid normalizing party and association support together.

### Custom icons

Optional `small_icon` and `large_icon` values name existing `GFX_...` sprites. Provide the corresponding `.gfx` definitions and textures in a hand-written companion mod or your own packaging integration. The compiler references these identifiers; it does not read a filesystem image path from the manifest or copy arbitrary assets automatically.

Both groups and ideology archetypes receive a large native-artwork sprite and a small texticon. Defaults alias stock game textures; the compiler does not draw geometric replacement badges or redistribute Paradox textures. Parties and archetypes follow the closest broad ideological family. Unions, businesses, military, religious and civic organizations use generic native idea artwork. These defaults describe political family or organization type; supply custom icons when a specific historical emblem is needed.

Small defaults use native texticons, typically 20×20. For custom art, use 20×20 texticons and a 64×64 large canvas so both the campaign interface and country-selection presentation remain within their reserved regions. Custom artwork keeps its own colors. The compiler cannot infer an external sprite's texture size from a `GFX_` name; the companion mod owns that dimension contract. A spectrum lane scales small sprites to fit its marker. The generated registry records both sprite names and the exact `£texticon£` token. See [UI.md](UI.md) and [BOOKMARKS.md](BOOKMARKS.md).

### Custom organization colors

Each organization can specify its own `color`. Use either a six-digit hexadecimal string such as `"color": "#C43B45"` or an RGB array such as `"color": [196, 59, 69]`. Both forms produce the same artwork. Keep hex strings quoted in YAML and TOML, where an unquoted `#` starts a comment. Channels are integers from 0 through 255; short hex notation, alpha channels, booleans and out-of-range values are rejected. This field belongs to the organization record, alongside `support` and `influence`.

The specified color is used consistently in the support pie, influence pie, list/detail color keys and the 1936/1939 country-selection snapshots. Custom `small_icon` or `large_icon` artwork retains its own appearance; a separate 8×8 key still identifies the organization's chart color. Two organizations may intentionally use the same RGB value, and colors are independent of engine ideology and coalition membership.

Omitting `color` preserves the previous deterministic color derived from the organization's ID. Existing manifests therefore remain valid and keep their previous colors. Prefer explicit colors in authored country content so identity colors remain deliberate when IDs or organization names change. Colors are compiled into native textures: edit the source record and rebuild the mod to change them. They are not limited to a preset palette and do not rely on an unsupported scripted-GUI `color` property.

## Define alliances and institutions

A profile may have no alliances, one alliance or several independent alliances. Optional `government` selects `{"group":"organization_id"}`, `{"alliance":"alliance_id"}`, or `null` for a caretaker. If omitted, the legacy single `kind: government` alliance is selected; a profile without one starts as a caretaker. Governing groups must be legal, and a governing alliance needs a legal member. Starting-bookmark overrides support the same field. Other alliances may start empty and be assembled during play. Multiple memberships are supported:

```json
{
  "id": "ger_reform_pact",
  "name": {"english": "Reform Agreement", "simp_chinese": "改革协议"},
  "description": {
    "english": "A joint electoral program whose organizations retain their identities.",
    "simp_chinese": "成员保留独立身份的共同选举纲领。"
  },
  "kind": "electoral",
  "members": [],
  "cohesion": 65
}
```

Members must belong to the same profile. An alliance's role can change when it governs; it is not necessary to destroy and recreate all its organizations. Government membership means a political support agreement, not automatically ministerial participation.

A regime defines actual institutions. Its `positions` may constrain only some axes:

```json
{
  "id": "elective_constitution",
  "name": {"english": "Elective constitutional order", "simp_chinese": "选举宪制"},
  "description": {
    "english": "Representative government and protected civil rights.",
    "simp_chinese": "代议政府与受保障的公民权利。"
  },
  "positions": {"head_of_state": -100, "authority": -65, "liberties": -75},
  "elections": true
}
```

Using that regime in a profile does not rewrite its organizations' positions. A monarchist party can govern a republic and accept the resulting legitimacy cost, change its own platform, or pursue institutional reform.

In strict mode, a regime's optional `native_policy` overrides five diplomacy
tension thresholds and three constitutional rules. Missing entries retain the
electoral/non-electoral defaults; unknown fields and invalid values fail the
build. Thresholds are fractions in 0–1 and rules are Booleans. See the complete
[native policy contract and example](NATIVE_MECHANICS.md#actual-institutions-select-diplomacy-constraints).
This keeps constitutional foreign-policy restrictions independent from the
organization's ideology classification.

## Country profiles and fallback coverage

A country profile declares `id`, `tag`, `regime`, `legitimacy`, `groups` and `alliances`. Optional `election_term_months` overrides the manifest-wide term, and `election_months_elapsed` seeds the current interval. The normal default is 48 months and zero elapsed months.

Fallback profiles have the same content fields but use `engine_ideology` instead of `tag`. Supply `democratic`, `fascism`, `communism` and `neutrality` exactly once each. This gives newly initialized countries a usable political model without requiring a historical party catalogue for every releasable tag.

Tags and profile flags are identities. Cosmetic country names do not select a new profile. Where a civil-war, tag-change or national-unification story needs special political content, write an explicit integration that updates the appropriate organization's state or performs a planned migration. Do not rely on a translated country name to select a political registry.

## Starting-bookmark overrides

`start_overrides` belongs inside a profile. It changes initialization for later campaign starts:

```json
{
  "date": "1939.1.1",
  "election_term_months": 48,
  "election_months_elapsed": 45,
  "groups": [
    {"id": "eng_conservative", "support": 41, "satisfaction": 77},
    {"id": "eng_labour", "support": 38}
  ]
}
```

This record fits the existing `eng` profile. The runtime uses chronological order and applies overrides eligible at initialization. It does not overwrite the country when a campaign started in 1936 later reaches 1939. Use scenarios or hand-written events for changes that should occur during an ongoing campaign.

## Dated declarative scenarios

A scenario names a profile, an earliest date, localized text and options. Every option can combine declared operations. This complete scenario fits the supplied Germany profile:

```json
{
  "id": "ger_author_example_centre",
  "profile": "ger",
  "date": "1937.4.1",
  "title": {"english": "Political reorganization", "simp_chinese": "政治重组"},
  "description": {
    "english": "The Centre seeks permission to resume public activity.",
    "simp_chinese": "中央党请求恢复公开活动。"
  },
  "options": [
    {
      "id": "permit",
      "label": {"english": "Permit organization", "simp_chinese": "允许组织活动"},
      "ai_chance": 30,
      "effects": [
        {"op": "activate", "group": "ger_zentrum"},
        {"op": "influence", "group": "ger_zentrum", "value": 12},
        {"op": "satisfaction", "group": "ger_zentrum", "value": 20},
        {"op": "legitimacy", "value": 4}
      ]
    },
    {
      "id": "defer",
      "label": {"english": "Defer the request", "simp_chinese": "暂缓请求"},
      "ai_chance": 70,
      "effects": [{"op": "satisfaction", "group": "ger_zentrum", "value": -5}]
    }
  ]
}
```

Supported operations are `activate`, `ban`, `legalize`, `underground`, `deactivate`, `support`, `influence`, `satisfaction`, `join`, `leave`, `govern`, `dissolve`, `regime`, `legitimacy`, `position` and `cohesion`. Numeric support/influence/satisfaction/legitimacy/cohesion operations add a delta; `position` sets the named coordinate. State-changing operations use the same guards as the public APIs.

A weekly pulse delivers an eligible scenario once. Later bookmarks mark dates already in the past as consumed. The example-events game rule controls this generated schedule. It does not disable the framework's organization actions or prevent a hand-written event from invoking an API.

The scenario schema deliberately does not accept arbitrary HOI4 code. For conditions involving focuses, war, characters, custom flags or another mod's systems, use normal HOI4 scripts and call PSF effects from them.

## Hand-written integrations and composition

The generated interface uses standard `effect_name = yes` calls. Inputs use temporary variables. Named modifier sources provide reusable one-line apply/remove calls, while generated native modifier keys can be placed directly in ideas, country traits and dynamic modifiers; see [MODIFIERS](MODIFIERS.md) and the [validated native integration examples](../examples/native_modifiers/README.md). This country-scoped integration grants a small concession once after an author-controlled flag is set:

```text
my_story_apply_labor_concession = {
    if = {
        limit = {
            psf_has_profile_ger = yes
            has_country_flag = my_story_labor_agreement_signed
            NOT = { has_country_flag = my_story_psf_concession_applied }
        }
        set_country_flag = my_story_psf_concession_applied
        psf_begin_transaction = yes
        psf_legalize_ger_free_unions = yes
        set_temp_variable = { psf_amount = 10 }
        psf_add_ger_free_unions_satisfaction = yes
        set_temp_variable = { psf_amount = 4 }
        psf_add_ger_free_unions_influence = yes
        psf_commit_transaction = yes
        psf_export_popularity = yes
    }
}
```

Put the effect in your own file under `common/scripted_effects/` and invoke it from your event option, decision or focus completion. The custom flags are your content's conditions and idempotency guard. PSF does not decide which national focus should enact the agreement.

Transactions suppress intermediate full refreshes for ordinary organization changes. Always commit in the same branch. They have no rollback or nesting support. Status and membership changes should be committed before an operation whose validity depends on a refreshed governing state. See [API.md](API.md) for direct examples and function-name patterns.

Player-facing political-power costs and cooldowns live in generated decisions/UI. Low-level scripted effects do not secretly charge those costs, allowing authors to decide what an event or focus should cost.

## Localization and presentation

Generated keys follow readable identities:

```text
psf_group_ger_spd_name
psf_group_ger_spd_short_name
psf_group_ger_spd_desc
psf_axis_economy_name
psf_axis_economy_left
psf_axis_economy_right
psf_alliance_fra_popular_front_name
psf_regime_workers_monarchy_name
```

Descriptions, tooltips and title text should be written for players. Build paths, variable IDs and implementation details belong in author documentation, not organization descriptions. Avoid telling a player that a group “uses an engine slot”; explain its political interests instead.

The UI uses declared axes dynamically and reads current variables. Editing an organization's position through an effect moves its spectrum icon without rebuilding the manifest. Long names appear in detail views and tooltips; provide useful short names for roster rows.

## Balance settings

The accepted settings are:

| Setting | Default |
| --- | ---: |
| `bridge_mode` | `bidirectional` |
| `term_months` | 48 |
| `monthly_legitimacy_recovery` | 0.8 |
| `alignment_penalty` | 0.04 |
| `underground_influence_factor` | 0.35 |
| `banned_influence_factor` | 0.12 |
| `monthly_government_satisfaction` | 0.8 |
| `monthly_opposition_satisfaction` | −0.15 |
| `cohesion_gap_penalty` | 0.035 |
| `coalition_fracture_threshold` | 20 |
| `member_defection_satisfaction` | 20 |
| `scenarios_enabled` | `true` |

The [architecture document](ARCHITECTURE.md) explains the formulas that consume these values. `export` bridge mode prevents native changes from being imported; `none` gives an integrating mod responsibility for native political state. Four native ideology values cannot preserve all organization-level information.

## Publishing changes and save compatibility

Use stable readable and numeric IDs. Reordering records preserves hashed identities but can change tie-breaking between equally distant ideology prototypes, so even a reorder can alter classification in a tie. Renaming an organization changes generated API and variable names. Changing axes alters the state schema.

For a new campaign, rebuild and package. For an established save, write a versioned migration that initializes added variables, transfers renamed values if necessary, assigns required new-axis positions, then reclassifies and refreshes. Mark that migration with your own country flag and apply it once. There is no general automatic migration that can infer an author's intent from an edited manifest.

Do not edit generated output as the long-term source. Compilation replaces owned directories, and `pack` verifies their hashes. Keep custom logic/assets in a companion integration or add a deliberate reproducible packaging step to your project.

## Country identity and native icon artwork

See [IDENTITY](IDENTITY.md) for country names, flags, conditional cosmetic tags and external-mod ownership. Both organizations and ideology prototypes accept independent `small_icon` and `large_icon` GFX references. Every declaration receives native-artwork defaults for both sizes and a registered texticon. Defaults represent the type or broad political family; they are not claimed to be historical party emblems. The registry exposes the exact two sprites and texticon token.

The vanilla example explicitly uses `mechanics_mode: strict` and `bridge_mode: export`; the reusable defaults remain `compat` and `bidirectional`. See [NATIVE_MECHANICS](NATIVE_MECHANICS.md) before changing these integration policies.
