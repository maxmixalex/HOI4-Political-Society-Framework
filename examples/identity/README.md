# Country identity authoring example

This deliberately fictional example uses the United Kingdom's existing engine
country tag to demonstrate an independent governing group, a PSF country name,
and one flag in all three engine sizes. It is an authoring fixture, not a
historical replacement for the vanilla example.

```sh
python -m psf compile examples/identity/manifest.json --output build/identity-example
```

The three original geometric flags in `flags/` are PSF artwork under the
repository's MIT license. The compiler writes identical flag bytes for the
unqualified cosmetic tag and each of the four engine ideology suffixes. This
prevents the compatibility ideology from choosing another flag behind PSF.

See [the identity guide](../../docs/IDENTITY.md) for conditional identities,
manual overrides and integration with another mod's cosmetic tags. The example
requires explicit history integration when used as an independent content mod;
the bundled vanilla pack includes its own history integration.
