# Installable build

[`psf-0.4.1.zip`](psf-0.4.1.zip) contains the reusable framework, vanilla political
societies, both launcher descriptors, bilingual installation instructions,
licenses and the generated API registry. Unpack into the HOI4 user-data `mod`
directory and enable both mods in one playset. Move the previous `psf/` and
`psf_vanilla_example/` folders aside before copying the new folders; overlaying
files can leave obsolete GUI chunks loaded. Start a new campaign.

## 0.4.1 changes

- Immediate foreign-country refresh even when revision numbers match.
- Independent large party and ideology images in both country-selection routes,
  with historical descriptions kept separate.
- Colored government roles, all current alliance memberships, and institution
  versus government reference rows in the scrollable sidebar.
- Live government membership in transactions, cleared caretaker summaries and
  stable election tie-breaking.
- Strict neutralization of 61 political defines, three generic party-opinion
  differences and thirteen generic ideological peace-price rules.
- Per-regime diplomacy policy and coalition-leader identity conditions.
- Ten fictional negotiations, thirty choices, ten optional agreements and three
  timed sources, preserving all existing organization baselines and governments.

The example now has 125 organizations, 27 declared alliances, 50 scenarios,
120 choices and 23 named sources. Native story conditions and some hardcoded
mechanics still inspect the compatibility projection. Authored identity flags
are independent of native ideology; without artwork, installed-game flags remain.

## Artifact and verification

| Field | Value |
| --- | --- |
| Version | 0.4.1 |
| Size | 3,405,066 bytes |
| Entries | 795 |
| Uncompressed size | 64,873,707 bytes |
| SHA-256 | `f36806a02a8bb0af7e047cbb2265d805de36e82e96def5a7c1f16512961d6523` |

All **244 tests**, **20 real validation controls** and **32,461 geometry/binding
checks** passed. The installed-wheel build matched all 795 files and reproduced
the installer byte for byte. CRC checks passed.

The final gate has **0 new errors and 0 new warnings**. Raw CWTools still reports
**367 errors and 117 warnings**: 272 declared stock-texture dependencies,
94 errors and 117 warnings matched on original histories, plus one error on
unchanged original generic peace code. See [VALIDATION.md](../docs/VALIDATION.md)
for exact source proof and limits. No HOI4 launch or game rendering was available.

```sh
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --self-test
python -m psf pack --root dist --output build/psf-0.4.1.zip
cmp distributions/psf-0.4.1.zip build/psf-0.4.1.zip
```

安装包包含框架、原版示例、两个启动器描述文件和双语说明。升级时先移走旧的
`psf/`、`psf_vanilla_example/`，复制新目录及 `.mod`，启用两个模组并新开战役。
已完成代码、脚本执行、原生布局结构与安装包校验；没有将它们等同于实机运行。
原始诊断与残余原版机制均已明确记录。
