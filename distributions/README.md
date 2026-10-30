# Installable builds

[`psf-0.4.0.zip`](psf-0.4.0.zip) contains the reusable PSF framework, the vanilla
political-society example, both launcher descriptors, bilingual installation
instructions, licenses and the generated API registry. Unpack it into the HOI4
user-data `mod` directory as described by `INSTALL.md` inside the archive, and
enable both mods in the same playset. Move the two previous PSF folders aside
first: overlaying files can leave obsolete generated GUI chunks loaded. The
installation folder names have not changed. Start a new campaign.

## What changed in 0.4.0

This release corrects domestic data scope, diplomacy attachment and pie bounds;
uses native interface artwork and scrolling sidebars; and supplies actual
large and small party/ideology icons with independent custom overrides. Exact
authored RGB colors remain consistent across support, influence and color keys.

The strict vanilla adapter initializes politics in country history, removes the
principal native ideology/popularity mechanics, and makes PSF institutions
control the replacement policy. Governments can be individual organizations or
authored alliances. Country identities support conditional names and three
sizes of custom flags. The bundled name identities inherit installed-game flags
unless the author supplies flag artwork.

Both selection routes receive separate political information through the
native selected-country binding. Historical descriptions are unchanged, and no
framework explanation replaces the country's information. Compat mode preserves
the original frontend when no history preparation hook is installed. The
previous BOM/loader repair is retained.

## Release artifact

| Field | Value |
| --- | --- |
| Version | 0.4.0 |
| Size | 3,173,703 bytes |
| Entries | 788 |
| Uncompressed size | 60,258,671 bytes |
| SHA-256 | `3ca5180dc2aebda4a943f1d6a5b92a9929e2340817dfd05ccfa9542c9b32a8ae` |

The archive CRC check, **213 Python regressions**, all **16 validation
controls** and **19,729 geometry/binding checks** passed. An independently
installed-wheel build matched all 788 generated files, and packing that output
reproduced the installer byte for byte. The final static gate has **0 new errors and
0 new warnings**. Raw CWTools output remains **366 errors and 117 warnings**:
272 occurrences concern 14 declared original-game texture dependencies; the
original-history comparison matches another 94 errors, 117 warnings and 83
informational diagnostics. All 364 generated native histories are verified
against their exact reconstruction. Missing native references are not
collectively dismissed as false positives. See [validation](../docs/VALIDATION.md)
for the complete accounting, regression/control results and reproducibility
record.

Build and validate the installer from source with:

```sh
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
python -m psf pack --root dist --output distributions/psf-0.4.0.zip
```

The workflow also builds release artifacts from validated commits. Static
validation is separate from an actual HOI4 launch, which was not available in
this environment. The package does not claim verified rendering, first-frame
initialization order or compatibility with every installed game snapshot.

安装包包含框架、原版示例、两个启动器描述文件及双语安装说明。升级时先移走旧的
`psf/`、`psf_vanilla_example/`，再复制新目录与两个 `.mod`；在同一游玩集中同时启用
两个模组，并开始新战役。0.4.0 修复国内数据作用域、外交双饼与侧栏布局，提供原版
大小图标、独立组织政府、历史阶段初始化和国名／国旗接口；选国政治信息已从历史
简介中移出。兼容模式没有前端绑定时保留完整原版布局。

本轮静态门禁没有新增错误或警告，但保留并公开原始 CWTools 诊断及其来源分类。
未进行实际 HOI4 引擎加载或渲染验收；原版脚本缺失引用也没有被一概称为误报。
