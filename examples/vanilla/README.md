# Vanilla Political Societies

`manifest.json` is the editable source of the vanilla example. It contains the axes, ideology prototypes, regimes, ten historical country profiles, four abstract fallback profiles, and twenty alternative-choice scenarios. English and Simplified Chinese strings are supplied together with each definition.

Read [the content guide](../../docs/EXAMPLE.md) for coverage, score semantics, starting-bookmark behavior, demonstrations and historical sources.

Compile from the repository root:

```sh
python -m psf compile examples/vanilla/manifest.json --output dist
```

This produces the framework and vanilla example outputs. Use the repository's installation instructions to load both mods together.

## Authoring conventions

- Every profile, group, alliance, axis, ideology, regime and scenario ID is stable and unique within its namespace.
- Group and alliance IDs are globally unique so reusable scripted effects can identify them without relying on list order.
- All group coordinates are explicit. Each axis is bounded from −100 to +100.
- Support, influence and satisfaction are independent scores from 0 to 100.
- Initial groups with `status: inactive` are declared content ready for activation, not missing implementations.
- `start_overrides` apply when initializing later bookmarks; they are not timed campaign events.
- Scenario effects operate on PSF political state. They do not rewrite national focus trees, diplomatic rules, borders or military units.
- Numerical values are authored gameplay parameters, not historical measurements.
