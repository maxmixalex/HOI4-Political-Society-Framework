# Architecture and political model

PSF compiles a schema-validated political registry into ordinary HOI4 effects, triggers, on-actions, decisions, localization and scripted GUI. There is no runtime Python service. The game executes generated Clausewitz script. The compiler entry point is [`psf/compiler.py`](../psf/compiler.py); the model and defaults are in [`psf/model.py`](../psf/model.py).

## Build layers

The framework output, `psf`, contains generic initialization predicates, legitimacy effects and the legitimacy dynamic modifier. The dependent content output contains the declared organizations and institutions, generated registry operations, scheduled updates, example events, UI and their translations. Its descriptor depends on the framework's exact name, `Political Society Framework`.

One generated registry is authoritative in a playset. Independent packs cannot both define the same dispatcher names, such as `psf_refresh`, and expect their contents to merge. Content authors combine declarations and compile one registry; additional hand-written integrations call that registry's APIs from their own event, focus or decision scripts.

Compilation validates before emitting into a temporary staging directory. It replaces the compiler-owned output directories only after generation succeeds. The package includes a machine-readable ID/API registry and file hashes. The pack command refuses files changed since compilation and uses fixed ZIP timestamps for reproducibility.

## Country state and organization identity

A country receives one profile. Authored country tags have priority, followed by one of four fallback templates selected by initial native ruling ideology. Initialization is guarded by `psf_initialized`; daily, weekly and monthly updates can initialize newly encountered countries without overwriting an already initialized country's state.

Each organization keeps:

| Field | Meaning |
| --- | --- |
| Identity and localized text | Full name, short name and description |
| Kind | Party, union, institution, association or another declared kind |
| Positions | Base and modified values for every declared political axis, bounded −100…100 |
| Derived ideology | Closest authored ideology prototype, recomputed when positions change |
| Support | Base and modified independent public approval, 0…100 |
| Baseline influence | Institutional resources, 0…100 |
| Modified influence | Baseline influence with currently active add/factor modifiers |
| Effective influence | Modified influence reduced by current legal access |
| Satisfaction | Base and modified acceptance of the present government, 0…100 |
| Named modifier sources | Per-group active flag and remaining daily ticks; −1 means permanent |
| Activity and prohibition | Inactive, legal, underground or suppressed activity; a separate statutory prohibition bit |
| Electoral eligibility | Whether this organization participates in the abstract ballot |
| Alliance memberships | Independent membership bits for every alliance in its profile |

An employer association can have low support and high influence. A worker can support a party and a union simultaneously. Therefore support and baseline influence do not form a compulsory national 100% distribution. The national government's displayed support is a relative electoral-party approval indicator; its displayed influence is its share of total effective institutional influence. Neither converts every organization into an exclusive slice of a political pie.

### Attribute modifiers and daily updates

Each group receives native custom modifier definitions for `add`, `factor` and `daily` on its three metrics and all declared axes. The engine combines sources such as national spirits and traits; PSF reads the resulting values using `modifier@token`. Named sources in the manifest provide a separate persistent, individually removable layer without occupying the national-spirit display.

On refresh, the runtime derives `modified = clamp((base + sum(add)) * max(0, 1 + sum(factor)), bounds)`. It never subtracts a previously clamped bonus from the base on expiration. All political classification, influence aggregation, ballot weighting and threshold APIs read the derived values. Explicit score and axis effects write the base. Daily drift writes the base and remains after a source ends. Inactive groups do not accumulate drift; their timed agreements still expire with the calendar.

The country-scoped `on_daily` calls `psf_daily_modifiers` once. In bidirectional bridge mode this first captures genuine native support changes, then applies daily drift and expiration, refreshes derived state and exports/captures the new projection. Native support deltas account for active support factors, so reading back the projection does not amplify its own changes. The supplied hook does not nest `every_country` inside the per-country update.

Repeated application of the same `(group, modifier)` refreshes its duration. Different source IDs stack additively in their add and factor channels. Permanent sources end only when explicitly removed. Full API and lifecycle examples are in [MODIFIERS](MODIFIERS.md).

The support pie normalizes the modified support of active electoral organizations only, so overlapping party and union support does not manufacture additional votes. The influence pie includes all active groups, using their status-adjusted effective influence. Both cache 180 sector frames after a model refresh and use the same group colors as the list and spectrum.

### Stable identifiers

Readable IDs determine generated variable and API names. Numeric IDs default to the first four bytes of SHA-256 reduced modulo 900,000, plus one; authors can set `numeric_id` explicitly. Numeric IDs are used for selections and identity comparisons. File order is not organization identity.

Save state still depends on readable IDs and declared axes. The bootstrap recognizes added organizations, alliances and group coordinates and initializes only their missing records at the current campaign date. Existing zero values, membership choices, dissolved alliances and modifier timers are preserved. A rename creates a new set of variable names; removals, renames, changed numeric IDs and transfers of existing state require an author's explicit migration or a new campaign. The compiler does not create synthetic cabinet alliances. A profile may contain zero alliances and an independent governing organization.

## Political spectrum and classification

For group coordinates \(x_d\), prototype coordinates \(p_{k,d}\), and positive axis weights \(w_d\), classification chooses the smallest weighted Manhattan distance:

\[
D_k = \frac{\sum_d w_d |x_d-p_{k,d}|}{\sum_d w_d}.
\]

All groups and prototypes must provide every axis. Equal distances retain the earlier prototype in the manifest, giving deterministic tie-breaking. The selected prototype is a descriptive category and a native-engine compatibility mapping; it is not an exclusive party slot.

A ruling coalition's coordinates are the effective-influence-weighted mean of its legal members. Unions, military institutions and associations can contribute when they are members of the political governing agreement. Their participation need not mean they provide cabinet ministers. A cabinet with no positive effective influence becomes a caretaker: its displayed membership count, support, satisfaction and leading organization are cleared. The organizations' underlying support remains intact.

Each refresh also caches the institution's declared coordinates and both institution/government marker positions for the spectrum page. An institution may leave an axis unspecified; the corresponding `psf_ui_institution_defined_<axis>` flag is zero and its marker is hidden. A missing policy is therefore not presented as a centrist policy. These values refresh on a regime or government change without waiting for a daily tick.

## Activity state machine

The activity states are numeric. Statutory prohibition is stored independently in `psf_g_<group>_prohibited`:

| State | Value | Effective influence multiplier, by default |
| --- | ---: | ---: |
| Inactive | 0 | 0 |
| Legal | 1 | 1 |
| Underground | 2 | 0.35 |
| Suppressed following a ban | 3 | 0.12 |

Activation changes inactive → legal and clears any retained prohibition. Legalization changes underground/suppressed → legal, clears statutory prohibition and adds eight satisfaction. Banning is available to active organizations outside the government that are not already in the suppressed activity state; it imposes suppression, reduces satisfaction by 15 and legitimacy by three. A prohibited underground network can therefore face another crackdown. Support and baseline influence are retained. Repeating an already-completed transition has no additional effect.

An explicit underground operation can change a legal or banned group to underground. Suppressed groups with at least ten support move underground on the monthly update, representing a surviving organization adapting to repression. Their statutory prohibition remains in force; only legalization clears it. A group can therefore be both banned and underground. Their effective influence is still below legal access. Inactive organizations do not receive monthly satisfaction changes.

Entering an illegal state removes the organization's governing membership. Opposition and electoral cooperation can remain clandestine. Joining the governing agreement requires legal status. Membership in one agreement does not automatically remove membership in another.

Implementation: [`runtime.group_effects`](../psf/runtime.py).

## Alliances and governing agreements

`government` is either an object containing `group`, an object containing `alliance`, or `null` for a caretaker. Omitting it preserves compatibility with an authored initial alliance whose `kind` is `government`; zero such alliances is also valid. The runtime keeps `psf_governing_group` and `psf_governing_alliance` mutually exclusive. Several non-governing alliances can coexist, including overlapping opposition and electoral agreements. Changing the selected government does not dissolve them.

An alliance has an active flag, role, independent electoral-pact flag, member set and cohesion. A government support agreement can become an opposition agreement after another alliance forms a government. Electoral identity can persist through a change of governing role.

Alliance coordinates and satisfaction are weighted by member effective influence. Its internal gap is the weighted mean distance of members from that alliance's mean position, divided by two to map the maximum 200-coordinate difference onto 0…100.

For a governing alliance, the commitment input is members' satisfaction with the government. For a non-governing alliance it is shared disapproval, `100 − satisfaction`. The default monthly cohesion change is:

\[
\Delta C = \frac{commitment-50}{30} - 0.035\,gap.
\]

This makes a dissatisfied, ideologically coherent opposition capable of remaining united. With cohesion below 20, a government member whose satisfaction is below 20 can defect; an opposition member highly satisfied with the government can instead leave its opposition agreement. Cohesion below five dissolves the agreement. Dissolving the government costs eight legitimacy and creates a caretaker state. The AI can negotiate cohesion or form a new cabinet from available legal institutions.

The model does not calculate parliament seats, constituency boundaries or proportional-representation allocation. These can be supplied by a content integration using PSF organizations and alliance APIs.

## Elections

Only legal groups marked `electoral: true` enter the ballot. Their support is normalized for that election:

\[
vote_i = 100\frac{support_i}{\sum_{j\in legal\ electoral}support_j}.
\]

Civil associations do not create additional votes. Electoral pacts sum the votes of their eligible members, counting each member once inside the pact. The largest party is recorded separately from the winning pact, so election reporting can explain why the largest individual party and the governing agreement differ. Equal party totals and equal pact totals use the lowest stable numeric ID, making declaration reordering independent of the result. A pact retains precedence when its combined total exactly equals the strongest individual party. A winning party can govern directly without a generated alliance; a winning pact governs through its existing identity. Other alliances keep their activity and independent memberships.

The default term is 48 monthly updates, configurable by `settings.term_months`. A profile can override it with `election_term_months` and seed `election_months_elapsed`; starting-bookmark overrides accept both fields. A country therefore need not start a fresh term on 1 January 1936. These are abstract monthly intervals, not a reconstruction of the exact historical election day. The example seeds major democratic profiles where dates are available and uses Spain's declared 36-month opening term. Authored election-related events are separate political-content choices, not an exact electoral-calendar simulator.

A snap-election decision is available after six elapsed months under an electoral institution, costs 100 political power and has a 180-day cooldown. Changing government does not automatically change the institution's `elections` setting.

## Institutional mismatch and legitimacy

A regime declares a **subset** of political axes that describe its actual institutional commitments. For example, the vanilla example uses head of state, distribution of authority and civil liberties. It does not make the current economic policy an immutable constitutional feature.

With government coordinates \(g_d\) and institutional coordinates \(r_d\), the mismatch is:

\[
M = \frac{\sum_{d\in regime} w_d |g_d-r_d|}{2\sum_{d\in regime}w_d}.
\]

Thus mismatch is 0…100. The same socialist economic platform can coexist with a republican or hereditary head of state; the latter does not overwrite the party's economic coordinate. A mismatch creates a continuing cost, while other sources of legitimacy can compensate.

Default monthly legitimacy change is:

\[
\Delta L = 0.8 - 0.04M + \frac{government\ satisfaction-50}{100} - caretaker.
\]

`caretaker` contributes an additional loss of one while the country lacks an effective governing agreement. Legitimacy remains bounded 0…100. Public consultation costs 50 political power and grants six legitimacy, with a 60-day decision cooldown. Constitutional reform costs 150 political power and eight legitimacy, requires at least 35 legitimacy and changes actual institutions independently of group positions.

The dynamic modifier uses bounded effects:

- Stability factor: `(legitimacy − 60) / 500`, bounded −0.12…+0.08.
- Political-power factor: `(legitimacy − 60) / 400`, bounded −0.15…+0.10.

These are maintained as dynamic modifier values; a periodic update does not repeatedly add permanent stability to the country.

## Update cadence

| Lifecycle | Work |
| --- | --- |
| Startup | Initialize countries once, apply eligible starting-bookmark overrides, classify organizations and calculate derived state |
| Weekly | Initialize new countries; import/export compatible native popularity changes in bidirectional mode; deliver eligible one-time example events |
| Monthly | Update active-group satisfaction; underground adaptation; alliance cohesion and defections; legitimacy; electoral clock; AI governance; native popularity projection |
| Native government change | In bidirectional mode, interpret the new compatibility category and form a corresponding PSF cabinet where a declared organization can represent it |
| Release hooks | Attempt initialization for released countries; regular updates provide an additional initialization path |
| Direct API mutation | Recalculate derived values immediately, unless a batch transaction is active |

Dated events are delivered on the first eligible weekly pulse after their date. Initialization marks already-past scenario dates as consumed, avoiding a burst of 1936 events at the 1939 bookmark. Later-bookmark overrides only apply at initialization, not whenever an existing campaign reaches their date.

Transactions group compatible mutations and recalculate once at commit. They are a refresh optimization, not rollback, nested transactions, database isolation or an authorization boundary. Operations such as forming a government require an immediate refresh. Government-membership predicates, bans and deactivation use current legal status and the selected government's actual membership rather than cached UI flags. This preserves sequential membership changes within an event while avoiding unnecessary complete chart recalculation for each change.

## Native ideology compatibility

The vanilla example uses strict mechanics and an export-only projection. This is separate from the bridge direction: `mechanics_mode` controls native political numerical effects and rules, while `bridge_mode` controls data synchronization. See [NATIVE_MECHANICS](NATIVE_MECHANICS.md) for the exact removals and retained engine boundaries. Country appearance has a separate [identity adapter](IDENTITY.md).

The engine's `democratic`, `fascism`, `communism` and `neutrality` categories remain available to original content. An ideology prototype names one of these categories as `engine_ideology`.

| Bridge mode | Behavior |
| --- | --- |
| `bidirectional` | Project PSF party support and government classification; import native popularity deltas and government changes |
| `export` | Project PSF support and explicit government changes; do not import native political changes |
| `none` | Leave the native compatibility state to the integrating mod |

Projection aggregates declared active electoral parties by their current derived ideology, then normalizes the aggregate to native percentages. Underground and banned supporters remain politically relevant even though their parties cannot enter a legal ballot. Native delta import uses `party_popularity_100@…`, distributes compatible changes across the relevant declared organizations and retains engine snapshots to avoid importing the framework's own export again.

If the active electoral organizations have zero total support, the native four-slot interface receives 100% in the current engine-government slot as a compatibility placeholder (neutrality if that engine slot is unknown). The engine cannot express an empty electorate. PSF's actual support values, government support, organization shares and neutral empty pie remain zero; this placeholder never becomes PSF approval. Strict mode disables the native ruling-party popularity stability contribution and cancels external popularity-stability modifiers, so the placeholder does not grant that native bonus. `compat` intentionally retains native mechanics and is not a complete replacement mode. The next positive PSF electorate replaces the placeholder during the same update.

The projection is lossy. Four native values cannot encode multiple parties, association memberships or nine-dimensional positions. A native script saying “add democratic popularity” cannot specify which of several democratic parties should benefit; PSF distributes a compatibility delta rather than inventing that missing intent. A profile with no compatible declared organization cannot preserve arbitrary changes to an otherwise unrepresented native category. Authors should call organization-specific effects for precise behavior.

An external `set_politics` operation also cannot describe a same-category switch from one PSF party to another. Use an independent-group or governing-alliance effect for that change. The framework does not rewrite foreign-policy, national-focus or war goals to guess what a party ought to do. These remain content-author decisions.

## UI integration and compatibility

The native patcher preserves engine-owned widget names and ancestry, hides obsolete political widgets and attaches explicitly scoped scripted-GUI roots to the native politics and diplomacy tokens. Domestic values use ROOT, foreign values use THIS. The diplomacy token starts inside the native country-info region, so its extra vertical offset is accounted for. No invented instance suffix is used. The global political-chart sprite is not replaced because other interfaces use it for unrelated distributions.

Country selection uses the engine's existing selected-country party-name binding. Country history prepares a temporary, date-specific PSF presentation in a dedicated political region in both selection panels. The ordinary historical introduction and the bookmark definitions remain unchanged. Campaign bootstrap restores ordinary party names without applying a day of simulation. The front end does not use an unsupported scripted-GUI context. See [BOOKMARKS](BOOKMARKS.md).

The complete native GUI overrides need a compatibility patch when another mod replaces the same files. Strict vanilla integration also preserves and patches the original country-history files and replaces the four native ideology groups' mechanical bodies. A matching installed game's interface directory can be supplied as the source; the compiler reads its sibling history and ideology directories. Load order does not merge conflicting layouts or history. See [UI](UI.md) and [NATIVE_MECHANICS](NATIVE_MECHANICS.md).

## Verification boundaries

Schema validation checks data shape, ranges, identifiers, dates, cross-country references and axis coverage. Generated-script tests execute the emitted supported subset and reject unknown operations; they do not emulate the full HOI4 engine. UI tests preserve native hierarchy and verify generated scopes and references. The actual pinned Rust CWTools engine checks generated artifacts against the supplied rules and vanilla identifiers, including negative controls that must fail.

These layers provide distinct evidence. None launches HOI4, measures game-frame performance, certifies the rendered result or establishes save compatibility. The current repository does not claim that such an engine playtest has taken place. See [the CI documentation](../tools/ci/README.md) for the exact dependency snapshots and omitted original assets.
