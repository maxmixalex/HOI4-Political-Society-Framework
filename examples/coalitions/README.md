# Playable coalition workshop

This optional, fictional content pack demonstrates a party governing directly
while three independent political agreements coexist. It is an authoring
example, not a reconstruction of German history. The default country is GER;
`--country` can select another existing three-letter country tag. Start a new
1936 campaign with only this content pack and the generated PSF framework.

```sh
python examples/coalitions/build.py --output build/coalitions
python tools/ci/validate.py --root build/coalitions
```

Install the generated `psf` and `psf_coalition_workshop` directories together
with their `.mod` descriptors, following the generated `INSTALL.md`.
Do not enable this pack together with the vanilla example: both declare the
framework's complete registry. The builder consumes the minimal example through
the normal loader and prints only the output location.

## Starting society

| Organization | Role | Electoral participation |
| --- | --- | --- |
| Civic Assembly | Independent governing party | Yes |
| Labour League | Opposition party | Yes |
| Local Reform Party | Opposition party | Yes |
| Industrial Council | Business association | No |

The Reform Agreement joins Civic Assembly and Local Reform Party. The Labour
and Industry Forum joins Labour League and Industrial Council. The Joint
Electoral List joins Labour League and Local Reform Party. All three exist at
once; none starts as the governing alliance. The business association has public
support and influence but adds no electoral votes.

## Playable choices

The Alliance decisions expose **Coordinate opposition** and **Form electoral
pact**. Converting an agreement preserves members and cohesion. It changes
whether eligible members combine their ballots. The governing alliance must
leave office before conversion; a separate party government can remain in
office while other pacts change. Each decision costs 30 political power and has
a 30-day cooldown.

Membership actions remain available after selecting an organization in the
political sidebar. An organization can join and leave one agreement without
disturbing its other memberships. Dissolving a pact clears only that pact;
joining it again reactivates it. Forming a government with the Reform Agreement
and then appointing Civic Assembly alone demonstrates both government models.

The first weekly content update after 15 January 1936 presents Parliamentary
negotiations: retain the independent cabinet, form the reform coalition, or
resign. This is an ordinary generated event with real government effects.
The PSF content-events game rule controls whether it fires.

## Country identity

The country is named Civic Administration under an independent Civic Assembly
cabinet, Reform Administration under the Reform Agreement, and Parliamentary
Administration otherwise. Names follow PSF government selection through owned
cosmetic tags. The example inherits the installed game's flags; the separate
[identity example](../identity/README.md) supplies fixed fictional flag assets.

Country-scope authored events can call:

```text
psf_set_ws_labor_front_role_electoral = yes
psf_set_ws_labor_front_role_opposition = yes
psf_govern_ws_reform = yes
psf_govern_group_ws_civic = yes
psf_release_identity = yes
psf_resume_identity = yes
```

`psf_release_identity` removes the exact currently owned PSF tag and holds the
base appearance until automatic selection is resumed. It preserves an external
formable/puppet cosmetic tag. Fallback profiles with no identity records never
take ownership of that slot. Regression tests execute the generated decisions,
compare electoral outcomes, switch governments, dissolve and rebuild a pact,
and verify identity release/resume and an identity-free country's external tag.
