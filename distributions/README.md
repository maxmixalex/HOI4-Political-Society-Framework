# Installable builds

[`psf-0.2.0.zip`](psf-0.2.0.zip) contains the reusable PSF mod, the vanilla political society example, both launcher descriptors, installation instructions, licenses and the generated API registry. Unpack it into the HOI4 user-data `mod` directory as described by `INSTALL.md` inside the archive, and enable both mods. Replace the previous folders; the install names have not changed. Version 0.2.0 fixes the GUI/GFX byte-order-mark startup failure in 0.1.0.

This snapshot is built from the accompanying source with:

```sh
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
python -m psf pack --root dist --output distributions/psf-0.2.0.zip
```

The package is deterministic and the GitHub Actions workflow publishes fresh builds from each validated commit. Static verification is recorded separately from an actual HOI4 engine launch, which has not been performed in this environment.

安装包包含框架、原版示例、启动器描述文件和安装说明。需要在同一游玩集中同时启用两个模组，并开始新战役。这里的校验不代表已经在实际 HOI4 引擎中完成加载验收。
