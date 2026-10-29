# Political Society Framework（PSF）

**PSF 为《钢铁雄心 IV》提供独立于原版四类意识形态槽位的政治团体框架。** 政党、工会、工商协会、军方集团、宗教社团与党内派系可以共同存在；两个立场相近的政党仍是两个独立组织。

框架以经过 JSON Schema 和语义检查的数据文件为源，生成原生 HOI4 脚本、界面、本地化及可复用接口。仓库同时提供适用于原版的政治社会示例内容。

**直接安装：** [下载 PSF 0.1.0 安装包](distributions/psf-0.1.0.zip)。包内包含框架、原版示例、两个启动器描述文件和中英文安装说明；无需先安装 Python。

> **验证边界：** 这里提供实际生成的模组和执行真实 Rust CWTools 的 CI，并通过测试执行生成脚本的受支持语义。开发环境未运行 HOI4 游戏客户端，因此不将静态校验、脚本测试或界面结构检查描述为已完成的游戏内实测。原版界面快照具有版本依赖；`supported_version="1.*"` 是启动器描述符，不是所有 1.x 版本的兼容保证。

## 已实现的系统

- **政治团体：** 全名、短名、描述、大小图标、类型、独立支持率、基础与有效影响力、对当前政府的满意度。
- **可配置政治光谱：** 内容作者声明维度、两端含义与权重。组织立场决定其最接近的意识形态原型；多个组织可以得到相同分类。
- **组织活动状态：** 尚未活动、合法、地下、遭查禁。查禁削弱制度影响，不会删除支持者或改变组织的内在立场。
- **政治联盟：** 执政、反对派与选举合作；成员关系相互独立，同一组织可参与多个协议。月度凝聚力变化、成员退出和解散都已实现。
- **政府与制度：** 执政集团的主张和实际国体分别记录。制度偏离影响合法性，公众协商可以弥补部分损失。合法性以动态修正作用于稳定度和政治点获取。
- **选举与行动：** 合法参选组织按当前支持进行抽象选举，选举联盟合计成员得票；通用决议处理组织活动、协商、支持动员、制度参与、联盟与制度改革。
- **替代界面：** 政治与外交面板中的原版政党饼图及意识形态/政党信息让位于国家总览、政治团体侧栏、联盟信息与逐维政治光谱。国家选择界面的两条信息路径也处理了旧政治信息。
- **作者工具：** JSON、YAML、TOML 输入；严格校验；确定性编译与打包；稳定 ID 注册表；生成的 scripted effects、triggers 和双语本地化。

原版四类意识形态仍存在于游戏引擎中，作为外交、人物、国策和其他硬编码行为的兼容接口。PSF 替代的是政治社会的数据模型、玩法和显示，不声称通过脚本删除引擎底层机制。默认桥接会投影 PSF 政党支持并接收可解释的原版变化；详见[架构与兼容性](docs/ARCHITECTURE.md)。

## 原版示例内容

示例包含 **125 个政治组织、21 个声明联盟、9 个政治维度、11 个意识形态原型、9 种制度、20 个日期事件和 40 个选项**。编译器另外为每个档案生成可用于选举和政府更替的过渡内阁协议。

德国、英国、法国、美国、苏联、意大利、日本、中国、西班牙和波兰有定制的 1936 档案及 1939 开局覆盖。其他国家使用四套通用模板之一，确保它们也拥有可操作的政治组织。所有名称、描述、事件与选项均有英文和简体中文。

数值是公开可编辑的游戏设计参数，不是历史民调。通用模板提供覆盖，不冒充每个小国的完整历史政党名录。详见[示例内容指南](docs/EXAMPLE.md)。

## 安装编译工具

需要 **Python 3.11 或更新版本**。编译器可在 Python 支持的平台运行；仓库附带的 CWTools 可执行文件及完整 CI 校验需要 **Linux x86-64**，Windows 可在 WSL2 中执行该校验。

```sh
git clone https://github.com/maxmixalex/HOI4-Political-Society-Framework.git
cd HOI4-Political-Society-Framework
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Windows PowerShell 可用以下方式建立和直接调用环境，无须依赖激活脚本：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m psf validate examples/vanilla/manifest.json
```

## 校验、构建与打包

```sh
python -m psf validate examples/vanilla/manifest.json
python -m psf compile examples/vanilla/manifest.json --output dist
python -m unittest discover -s tests -v
python tools/ci/validate.py --root dist --self-test
python -m psf pack --root dist --output artifacts/psf-vanilla-example.zip
```

`psf` 也作为命令安装，等同于 `python -m psf`。检查某个组织的稳定 ID 和数据：

```sh
python -m psf inspect examples/vanilla/manifest.json --group ger_spd
```

构建输出包括：

| 输出 | 用途 |
| --- | --- |
| `dist/psf/` 与 `dist/psf.mod` | 通用框架与启动器描述符 |
| `dist/psf_vanilla_example/` 与相应 `.mod` | 依赖框架的原版内容模组与 UI |
| `dist/psf-registry.json` | 稳定 ID、变量、effect 与 trigger 名称 |
| `dist/build-manifest.json` | 文件 SHA-256、内容计数与构建来源 |
| `dist/psf_vanilla_example/psf_ui_manifest.json` | 原版 UI 输入哈希、修改路径和结构检查信息 |

`pack` 校验构建后的文件哈希；编译后直接修改了产物时需要重新编译再打包。生成目录由编译器管理，长期修改应放在源 manifest 或独立的手写集成模组里。

## 在启动器中加载

解压打包结果，将以下两个目录和两个 `.mod` 文件放入 HOI4 的用户 `mod` 目录，例如 Windows 的 `Documents/Paradox Interactive/Hearts of Iron IV/mod/`，或 Linux 的 `~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/`：

- `psf/`
- `psf.mod`
- `psf_vanilla_example/`
- `psf_vanilla_example.mod`

在同一个播放集中启用 **Political Society Framework** 和 **PSF — Vanilla Political Societies**。示例描述符声明对框架的依赖，内容需要在框架之后生效。启动新游戏；首次游戏内验证建议从原版 1936 年开局开始。

在本国政治面板打开团体或光谱侧栏。选中团体后，政治社会决议分类会显示该组织的行动。查看外国外交面板可以检查其政治社会；外国面板中的选择与浏览不会授权修改对方的政治状态。

本仓库不提供已经验证的旧存档迁移。已有的 PSF 存档不会在加载时自动重置组织数值；内容 ID、维度和状态结构发生变化时，应提供显式迁移或使用新存档。

## 真正的 CWTools CI

[GitHub Actions 工作流](.github/workflows/cwtools.yml) 在 push、pull request 和手动运行时完成测试、双模组编译、重复构建比较以及 Rust CWTools 语义校验。校验器、完整 HOI4 CWT 规则和原版符号缓存均按 SHA-256 固定；校验失败、警告、空报告或工具链哈希不符会使任务失败。

负面对照验证该门禁确实拒绝未知 effect、非法布尔值、未闭合脚本、缺失 sprite 和新的未定义 PSF 本地化。原版脚本快照未包含翻译文件；已有原版 UI 本地化引用通过明确记录的外部依赖声明处理，新 PSF 键不会被放行。完整说明见[校验工具说明](tools/ci/README.md)。

有完整的游戏安装时，可以直接对照本机版本：

```sh
python -m psf compile examples/vanilla/manifest.json \
  --output dist --vanilla '/path/to/Hearts of Iron IV/interface'
python tools/ci/validate.py --root dist \
  --vanilla '/path/to/Hearts of Iron IV' --self-test
```

两个 `--vanilla` 参数分别要求 **interface 目录**和**游戏根目录**。编译器拒绝不符合预期的原版控件树，不会用一个缺失硬编码控件的简化窗口悄悄覆盖它。

## 模组兼容与作者入口

政治 UI 覆盖以下原版文件：

- `interface/countrypoliticsview.gui`
- `interface/countrydiplomacyview.gui`
- `interface/frontendgamesetupview.gui`

同时覆盖这些文件的模组需要专门的兼容补丁；不能仅通过调整加载顺序保证双方界面完整。KR、TNO、PB 的脚本用于理解可行实现，不代表本版本已成为这些总转换模组的即插即用补丁。

每个播放集使用一个编译后的 PSF 内容注册表。要组合多份政治内容，应在源数据层合并档案并重新编译，避免多个生成注册表争用同名运行时接口。

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | 数据模型、计算公式、更新周期、原版桥接与验证边界 |
| [AUTHORING](docs/AUTHORING.md) | Schema、完整 JSON/YAML/TOML 示例、定义组织与事件、图标与迁移规则 |
| [API](docs/API.md) | 实际生成的 effects、triggers、变量与本地化示例 |
| [EXAMPLE](docs/EXAMPLE.md) | 国家覆盖、场景、设计解释和历史资料 |
| [UI](docs/UI.md) | 政治/外交侧栏、原版控件保留、作用域与分辨率 |
| [CWTools](tools/ci/README.md) | 真正校验、固定工具链、负面对照与原版依赖 |

## License

原创编译器、框架逻辑、示例数据、文档及程序化图标采用 [MIT License](LICENSE)。原版 GUI 定义、原版符号来源和第三方工具保留各自权利与许可；详情见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。

## English summary

PSF models political organizations independently of HOI4's native ideology slots. Declarative JSON, YAML or TOML manifests compile into a reusable framework mod and one dependent content mod, including generated effects, triggers, bilingual localization and native scripted UI. Organizations have multidimensional positions, independent support and influence, government satisfaction, legal status and multiple alliance memberships. Actual institutions remain separate from the governing coalition's political preferences.

The vanilla example supplies ten authored country profiles, four generic fallback templates, 125 organizations and twenty alternative-choice scenarios. The repository includes real pinned Rust CWTools validation and semantic negative controls. Native ideology categories remain as a compatibility projection; the game executable has not been run in the development environment, so static validation is not represented as an in-game rendering or playtest result.
