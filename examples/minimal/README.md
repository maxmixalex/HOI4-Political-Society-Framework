# Minimal complete manifests

`manifest.json`, `manifest.yaml` and `manifest.toml` are three equivalent complete inputs. Each declares two axes, four compatibility prototypes, four simple institutional definitions and four fallback profiles with one organization each. There are no country-specific profiles or scheduled scenarios.

These examples demonstrate authoring syntax and the minimum full-registry structure; they are not a historically representative or politically balanced content pack. Use the vanilla example for the richer political model.

```sh
python -m psf validate examples/minimal/manifest.json
python -m psf validate examples/minimal/manifest.yaml
python -m psf validate examples/minimal/manifest.toml
python -m psf compile examples/minimal/manifest.yaml --output build/minimal
```

All three files must normalize to the same registry. If you edit one for your own project, use one authoritative format rather than maintaining three independent copies.
