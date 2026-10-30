# Installable builds

| Package | Intended use |
| --- | --- |
| [psf-0.4.2.zip](psf-0.4.2.zip) | Framework plus the vanilla political-society example |
| [psf-coalition-workshop-0.4.2.zip](psf-coalition-workshop-0.4.2.zip) | Separate fictional coalition workshop: four organizations and three simultaneous pacts |

**Choose one package.** Each ZIP contains the reusable framework, one complete
content registry, both launcher descriptors, bilingual installation notes and
licenses. Do not enable the vanilla and workshop content packs together.

Unpack into the HOI4 user-data `mod` directory and enable the framework and its
chosen content pack in one playset. Move previous `psf/` and old PSF content
folders aside first; overlaying files can leave obsolete GUI chunks loaded.
Start a new campaign. The workshop is intended for the 1936 start and is a
fictional example, not a reconstruction of German history.

## 0.4.2 changes

This distribution includes all retained 0.4.0/0.4.1 development work, including
immediate country data, separate selection politics, native scrolling UI,
custom organization colors, optional government alliances and cosmetic identity.

The current release refines selection typography and large/small icon contracts,
adds scoped colored tooltips, repairs same-transaction monthly membership and
empty-electorate projection, and seeds newly introduced records without resetting
saved political state. Strict mode cancels fourteen native political modifier
channels and replaces four occupation-law ideology gates with PSF institution
conditions. Complete decision categories are split within the file-size budget.

Alliance decisions can switch opposition/electoral cooperation while preserving
members. The separate [workshop](../examples/coalitions/README.md) supplies real
playable government/event/identity transitions. The default vanilla example
retains 125 organizations, 27 alliances, 50 scenarios, 120 choices and 23 named
sources. Original national story conditions and unexposed hardcoded mechanics
still inspect the compatibility projection.

## Artifacts

| Field | Vanilla example | Coalition workshop |
| --- | --- | --- |
| Version | 0.4.2 | 0.4.2 |
| ZIP bytes | 3,584,938 | 872,349 |
| Entries | 803 | 614 |
| Uncompressed bytes | 67,643,404 | 5,455,333 |
| SHA-256 | `0eeb8692c03abedac8352b99e3837d364cf2fe06b9e7a60387f091ea0c742dc4` | `78ba5222a4f6fd1c6dca83cffa32edc53656298a49286d784afbc6100231aa21` |

All 264 distinct final regression tests passed, together with twenty real
validation controls and 34,372 native geometry/binding checks. CRC passed for
both ZIPs. An independently installed compiler wheel reproduced every file and
both installers byte for byte; the new occupation-law snapshot is included in
that installed compiler.

The script gates report **zero new errors and zero new warnings**. Raw CWTools
still reports 367 errors/123 warnings for the vanilla/native-integration builds
and 119 errors/123 warnings for the workshop. Exact original-source and declared
texture dependencies account for these diagnostics; their raw records remain.
See [VALIDATION](../docs/VALIDATION.md) for proof, commands and boundaries.
**No HOI4 executable launch, actual UI rendering or mouse-interaction test was
available.**

安装包二选一。每个包内含框架、对应内容模组、两个启动器描述文件和双语说明。
请先移走旧的 `psf/` 与旧 PSF 内容目录，复制所选包并启用其中两个模组，随后新开
战役。联盟实践包含虚构组织、三个并存联盟和真实事件，不会混入默认原版内容包。
静态检查、生成脚本执行和真实 CWTools 验证均已完成，但没有将它们等同于实机运行。
