# Political Society Framework（PSF）

**PSF 为《钢铁雄心 IV》提供独立于原版四类意识形态槽位的政治团体框架。** 政党、工会、工商协会、军方集团、宗教社团与党内派系可以共同存在；两个立场相近的政党仍是两个独立组织。

框架以经过 JSON Schema 和语义检查的数据文件为源，生成原生 HOI4 脚本、界面、本地化及可复用接口。仓库同时提供适用于原版的政治社会示例内容。

**直接安装：** [下载 PSF 0.4.0 安装包](distributions/psf-0.4.0.zip)。包内包含框架、原版示例、两个启动器描述文件和中英文安装说明；无需先安装 Python。

> **验证边界：** 这里提供实际生成的模组、HOI4 加载格式检查和执行真实 Rust CWTools 的 CI，并通过测试执行生成脚本的受支持语义。开发环境未运行 HOI4 游戏客户端，因此不将静态校验、脚本测试或界面结构检查描述为已完成的游戏内实测。原版界面快照具有版本依赖；其版本号未随脚本提供，因此默认省略可选的 `supported_version`。作者可用 `--supported-version 1.19.*` 指定自己核实的目标版本。

**0.2.0 修复了 0.1.0 的启动故障：** GUI/GFX 的 UTF-8 BOM 会令引擎拒绝整个文件，进而缺失 `frontendgamesetupview`。现在这些文件使用无 BOM UTF-8，只有本地化 YML 使用 BOM；构建在调用 CWTools 前检查原始字节和必需的原生窗口。请替换原来的同名模组目录与描述符。

**0.3.1 修复界面挂接与页面重叠：** 政治、外交界面挂接游戏原生窗口，每页和团体详情独立控制显隐；修正文本引用、列表列宽、光谱标记和书签历史栏的大图重叠。团体可声明任意 `#RRGGBB` 或 `[R,G,B]` 颜色，支持率、影响力、列表色块及开局预览保持一致。新增十场后期协商和四种持续修正，1939 开局也有后续内容。

**0.4.0 针对实机反馈修复：** 本国动态文本和饼图显式使用玩家作用域；外交页修正原生父窗口的坐标偏移，饼图收进原版覆盖层；侧栏采用原版框体、标题和滚动结构。选国政治区与历史简介分离，不再放置框架说明。新增严格原版机制隔离、国家历史阶段初始化、可选联盟政府、原版大小图标及由 PSF 政体驱动的国名／国旗接口。

## 已实现的系统

- **政治团体：** 全名、短名、描述、大小图标、自定义 RGB 颜色、类型、独立支持率、基础与有效影响力、对当前政府的满意度。颜色独立于意识形态、联盟和活动状态。
- **可配置政治光谱：** 内容作者声明维度、两端含义与权重。组织立场决定其最接近的意识形态原型；多个组织可以得到相同分类。
- **组织活动状态：** 尚未活动、合法、地下、遭查禁。查禁削弱制度影响，不会删除支持者或改变组织的内在立场。
- **政治联盟：** 执政、反对派与选举合作；成员关系相互独立，同一组织可参与多个协议。月度凝聚力变化、成员退出和解散都已实现。
- **国家形象：** [cosmetic tag 适配](docs/IDENTITY.md)可按政体、执政团体、联盟或意识形态选择国名和国旗。大小图标与图表颜色独立配置。
- **政府与制度：** 执政集团的主张和实际国体分别记录。制度偏离影响合法性，公众协商可以弥补部分损失。合法性以动态修正作用于稳定度和政治点获取。
- **选举与行动：** 合法参选组织按当前支持进行抽象选举，选举联盟合计成员得票；通用决议处理组织活动、协商、支持动员、制度参与、联盟与制度改革。
- **替代界面：** 政治与外交面板中的原版政党饼图及意识形态/政党信息让位于国家总览、政治团体侧栏、联盟信息与逐维政治光谱。国家选择界面的两条信息路径也处理了旧政治信息。
- **作者工具：** JSON、YAML、TOML 输入；严格校验；确定性编译与打包；稳定 ID 注册表；生成的 scripted effects、triggers 和双语本地化。
- **团体属性修正：** 每个团体的支持、影响、满意度和每条光谱维度都有原生 `add`、`factor`、`daily` modifier。可从民族精神、特质和动态修正接入，也可声明具名的永久或限时修正，分别叠加、刷新、撤销。一次性变化与持续加成分别维护基础值与实际值，完整接口见 [MODIFIERS](docs/MODIFIERS.md)。

原版四类意识形态仍作为人物、国策、事件与硬编码行为的兼容投影。原版示例现在显式启用 `mechanics_mode = strict` 与单向 `bridge_mode = export`，中和原生党派支持率及意识形态的主要数值／规则影响，由 PSF 制度与数据负责政治玩法。它不会把整个原版国策与事件中的意识形态条件全部改写；这些剧情判断仍读取兼容投影。通用框架默认保留 `compat` 以供整合作者选择，详见[机制隔离说明](docs/NATIVE_MECHANICS.md)。

## 原版示例内容

示例包含 **125 个政治组织、17 个声明联盟、9 个政治维度、11 个意识形态原型、9 种制度、40 个日期事件和 90 个选项**，以及 **20 种具名修正、4,500 个按团体及属性生成的原生 modifier**。所有示例团体均有显式颜色。政府可以由单一组织执政、由一个联盟执政，或者处于看守状态；编译器不再生成虚构的过渡联盟。四个通用模板直接采用单一执政组织。另有 20 个可按政体切换的国家名称形象记录。

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
| `dist/psf_vanilla_example/psf_bookmark_manifest.json` | 国家选择预览、日期、原版剧本输入哈希与保留的历史介绍键 |

`pack` 校验构建后的文件哈希；编译后直接修改了产物时需要重新编译再打包。生成目录由编译器管理，长期修改应放在源 manifest 或独立的手写集成模组里。

## 在启动器中加载

解压打包结果，将以下两个目录和两个 `.mod` 文件放入 HOI4 的用户 `mod` 目录，例如 Windows 的 `Documents/Paradox Interactive/Hearts of Iron IV/mod/`，或 Linux 的 `~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/`：

- `psf/`
- `psf.mod`
- `psf_vanilla_example/`
- `psf_vanilla_example.mod`

在同一个播放集中启用 **Political Society Framework** 和 **PSF — Vanilla Political Societies**。示例描述符声明对框架的依赖，内容需要在框架之后生效。启动新游戏；首次游戏内验证建议从原版 1936 年开局开始。

**旧版升级：** 先移走旧的 `psf/`、`psf_vanilla_example/`，再复制本包的同名目录与两个 `.mod`。只覆盖文件可能残留旧的 GUI 分块，使新旧窗口同时加载；不需要改动其他模组。

在本国政治面板打开团体或光谱侧栏。选中团体后，政治社会决议分类会显示该组织的行动。查看外国外交面板可以检查其政治社会；外国面板中的选择与浏览不会授权修改对方的政治状态。

本仓库不提供已经验证的旧存档迁移。已有的 PSF 存档不会在加载时自动重置组织数值；内容 ID、维度和状态结构发生变化时，应提供显式迁移或使用新存档。

## 真正的 CWTools CI

[GitHub Actions 工作流](.github/workflows/cwtools.yml) 在 push、pull request 和手动运行时完成测试、双模组编译、重复构建比较以及 Rust CWTools 语义校验。校验器、完整 HOI4 CWT 规则和原版符号缓存均按 SHA-256 固定；新增代码诊断、未声明资源缺失、新增警告、空报告或工具链哈希不符会使任务失败。原始 CWTools 报告完整保留；仅在没有完整游戏安装时，把与已固定原版 GFX 声明逐项相符的纹理路径记录为外部资源依赖，而不伪造纹理文件或将其宣称为实机通过。

严格模式的 364 个国家历史文件先通过固定源哈希与逐字节重建，再对原始历史和加入 PSF 后的历史分别运行同一工具。只有文件、原文位置、上下文及完整诊断一对一对应的既有问题才会单列为原版继承诊断；新增的 PSF 初始化语句不会继承这些诊断。源包缺失引用与规则表示差异均保留原始证据，不能将“PSF 新增诊断为零”等同于“原始报告没有错误”。

负面对照验证该门禁确实拒绝未知 effect、非法布尔值、未闭合脚本、缺失 sprite、拼错的纹理路径和新的未定义 PSF 本地化。原版脚本快照未包含翻译文件；已有原版 UI 本地化引用通过明确记录的外部依赖声明处理，新 PSF 键不会被放行。完整说明见[校验工具说明](tools/ci/README.md)。

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

选国的两个原生面板均通过当前国家的 `party` 文本绑定显示独立政治区；按开局日期生成 PSF 饼图、执政党与政体。原版剧本、DLC 条件和历史简介保持不变，历史加载阶段准备预览，进入战役后恢复普通党名。严格模式还覆盖所供快照中的原始国家历史与意识形态定义，整合其他模组时应合并这些初始化入口。具体范围见 [BOOKMARKS](docs/BOOKMARKS.md) 和 [机制隔离](docs/NATIVE_MECHANICS.md)。

每个播放集使用一个编译后的 PSF 内容注册表。要组合多份政治内容，应在源数据层合并档案并重新编译，避免多个生成注册表争用同名运行时接口。

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | 数据模型、计算公式、更新周期、原版桥接与验证边界 |
| [AUTHORING](docs/AUTHORING.md) | Schema、完整 JSON/YAML/TOML 示例、定义组织与事件、图标与迁移规则 |
| [API](docs/API.md) | 实际生成的 effects、triggers、变量与本地化示例 |
| [MODIFIERS](docs/MODIFIERS.md) | 民族精神/特质接入、限时与永久修正、日变化、叠加与撤销 |
| [原生接入示例](examples/native_modifiers/README.md) | 经真实 CWTools 验证的民族精神、人物特质与动态修正文件 |
| [EXAMPLE](docs/EXAMPLE.md) | 国家覆盖、场景、设计解释和历史资料 |
| [UI](docs/UI.md) | 政治/外交侧栏、原版控件保留、作用域与分辨率 |
| [BOOKMARKS](docs/BOOKMARKS.md) | 国家选择页的剧本快照、原描述保留及前端覆盖范围 |
| [CWTools](tools/ci/README.md) | 真正校验、固定工具链、负面对照与原版依赖 |

## License

原创编译器、框架逻辑、示例数据、文档及程序化图标采用 [MIT License](LICENSE)。原版 GUI 定义、原版符号来源和第三方工具保留各自权利与许可；详情见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。

## English summary

PSF models political organizations independently of HOI4's native ideology slots. Declarative JSON, YAML or TOML manifests compile into a reusable framework mod and one dependent content mod, including generated effects, triggers, bilingual localization and native scripted UI. Organizations have multidimensional positions, independent support and influence, government satisfaction, legal status and multiple alliance memberships. Actual institutions remain separate from the governing coalition's political preferences.

The vanilla example supplies ten authored country profiles, four generic fallback templates, 125 organizations, forty alternative-choice scenarios, twenty named modifier sources and 4,500 native organization modifier keys. The repository includes loader-byte/root-window checks, real pinned Rust CWTools validation and semantic negative controls. Native ideology categories remain as a compatibility projection; the game executable has not been run in the development environment, so static validation is not represented as an in-game rendering or playtest result.
