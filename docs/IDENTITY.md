# Country names and flags

PSF keeps country identity separate from an organization's ideological
classification. Authors can select a country name and flag from the actual
regime, the independent governing group, the governing alliance, or the
government's classified ideology. Matching uses PSF variables, not the four
native ideology names.

## Authoring

Add an ordered `identities` list to a profile. A record contains `id` and
bilingual `name`; optional `adjective` and `definite_name` default to the name.
An optional `when` object accepts `regime`, `group`, `alliance` and `ideology`.
All supplied conditions must match. The first matching record wins. A record
without conditions is a default and must be last. A `group` condition means the
single governing group; it does not mean any member of a coalition.
Consequently a condition cannot specify both `group` and `alliance`; those
government selections are mutually exclusive. If no conditional identity
matches and there is no default, the current appearance is retained. Supply a
final default or call `psf_release_identity` when a return to the base appearance
is intended.

For example, use one identity conditioned on `regime = parliamentary_republic`,
then an unconditional identity for the country's starting name. The vanilla
example supplies twenty records across ten authored countries. Their
alternative constitutional names are game content, not a claim that those
historical transitions actually occurred.

By default the generated cosmetic tag is `PSF_` followed by the uppercase
identity ID. Authors can supply `cosmetic_tag` to integrate an explicitly owned
tag. IDs and tags must be unique. The compiler emits base, definite and adjective
localization for every native ideology, so a change in the compatibility
projection does not choose a different name.

## Flags

An optional `flags` object specifies `large`, `medium` and `small` files relative
to the manifest directory. All three are required together. Files must be
uncompressed, 32-bit TGA with a bottom-left origin:

| Size | Dimensions |
| --- | --- |
| `large` | 82 × 52 |
| `medium` | 41 × 26 |
| `small` | 10 × 7 |

Each supplied image is copied to both the bare cosmetic tag and its
`democratic`, `fascism`, `communism` and `neutrality` variants. A bare cosmetic
flag alone is insufficient when the engine can find an ideology-specific flag.
Missing files, traversal outside the manifest directory, invalid formats and
incorrect dimensions fail compilation before the previous build is replaced.

No flag assets means **inherit the installed game's flag behavior**. The
vanilla example supplies country-name identities but does not redistribute
Paradox's flag textures or invent historical flag artwork. Its inherited flags
may still vary with the native compatibility ideology. To make flags independent
as well, supply the three images. The executable
[identity example](../examples/identity/README.md) includes original fictional
flags and demonstrates this complete path.

## Runtime integration

`psf_apply_identity` runs after a PSF refresh. Selecting an already applied
identity does not reapply the tag or invalidate the UI unnecessarily. Runtime
APIs operate in country scope:

| API | Behavior |
| --- | --- |
| `psf_set_identity_<id> = yes` | Select this profile's identity and hold it manually. |
| `psf_suspend_identity = yes` | Keep the current appearance; pause automatic selection. |
| `psf_resume_identity = yes` | Resume selection from the country's current PSF data. |
| `psf_release_identity = yes` | Remove a currently owned PSF tag and suspend automatic selection. |

`psf_identity` stores the stable numeric ID. Records and asset hashes appear in
the build report and registry. An identity is opt-in: a profile without records
does not change country names or flags.

HOI4 has one cosmetic-tag slot per country. This is shared with formable nations,
occupation and puppet scripts. After PSF applies an identity, a subsequent
non-PSF cosmetic tag suspends automatic updates rather than being overwritten
at the next refresh. `psf_release_identity` also leaves an external tag intact.
Use `psf_resume_identity` when the integration explicitly returns ownership to
PSF. An integration that changes appearance should ideally call
`psf_suspend_identity` before applying its own cosmetic tag. Initial automatic
selection takes ownership of the slot for a profile that opts into identities;
authors should not enable it for a country whose initial cosmetic tag belongs
to an unrelated system.
