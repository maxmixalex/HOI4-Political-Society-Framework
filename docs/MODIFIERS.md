# 政治团体属性修正

PSF 为每个注册的政治团体、每个基础属性及每条自定义政治光谱生成 **原生自定义 modifier**，同时提供支持到期与独立撤销的命名修正来源。所有生成键、有效值变量与命名来源 ID 均列入 `psf-registry.json` 的 `modifiers` 节点。

## 三种不同的操作

| 操作 | 例子 | 撤销时发生什么 |
| --- | --- | --- |
| 一次性改变基础值 | 事件提高支持率 5 点 | 基础值已经改变；之后由另一个事件决定如何变化 |
| 持续加成 `add` / `factor` | 协议有效期间，影响力额外增加 10 点或 20% | 加成消失；基础值和期间发生的事件变化保留 |
| 持续变化 `daily` | 每天提高满意度 0.1 点 | 此后停止增长，已经累积的增长保留 |

支持率、影响力、满意度的范围均为 **0–100**。光谱坐标的范围为 **−100–100**。`support = 5` 表示该组织独立支持度增加 5 点；它不是 `0.05`，也不是在各政党合计选票中强制增加五个百分点。支持率饼图对所有已开始活动且 `electoral = true` 的组织归一化，其中可以包括地下或受压制的政党；选举只对合法的参选组织归一化。

这些 API 在目标组织所属的**国家作用域**使用。组织并非 HOI4 新增的一种引擎 scope。跨档案调用生成的命名 effect 会被作用域检查拦住，不会凭空创建外国组织。

## 1. 一次性改变

已有的 effect 名保持兼容：

```text
GER = {
    set_temp_variable = { psf_amount = 5 }
    psf_add_ger_spd_support = yes

    set_temp_variable = { psf_amount = -8 }
    psf_add_ger_industry_influence = yes

    set_temp_variable = { psf_amount = 12 }
    psf_add_ger_spd_satisfaction = yes

    # 新增：沿任一自定义政治光谱作相对位移。
    set_temp_variable = { psf_amount = -10 }
    psf_add_ger_spd_position_economy = yes

    # 绝对定位仍使用 psf_position。
    set_temp_variable = { psf_position = -40 }
    psf_set_ger_spd_position_economy = yes
}
```

`psf_set_<group>_<support|influence|satisfaction>` 使用 `psf_amount`，直接设定基础值。`psf_add_<group>_position_<axis>` 使用 `psf_amount`，相对改变基础立场；`psf_set_<group>_position_<axis>` 使用 `psf_position`，直接设定基础立场。

一次性属性、光谱和组织状态 API，以及命名修正来源 API，在修改前处理尚未导入的原版支持率变化，完成后重算并同步原版投影。

多个修改可以放进 `psf_begin_transaction = yes` / `psf_commit_transaction = yes`，最后集中重算并同步。`begin` 在进入批次之前导入原版变化；`commit` 刷新并导出。批次作为单层配对使用。临时参数应在相邻的调用前赋值，避免复用别的 effect 留下的临时数值。

若在批次中调用 `psf_hold_election = yes`，选举入口会先重算，再读取当前制度是否允许选举及各党的有效支持率。此前同一批次的属性、命名来源或制度变更会参与本次投票；选举本身不会替调用者结束批次，后续仍须调用 `psf_commit_transaction = yes`。

框架没有发明 `psf_add_group_support = { GROUP = ... AMOUNT = ... }` 一类参数语法。所附原版脚本和规则使用 `scripted_effect = yes`；需要声明式单行调用时可使用下面的命名修正来源。

## 2. 直接写进国家精神、人物特质或动态修正

每个属性生成以下三个原生键：

```text
psf_<group>_<attribute>_add
psf_<group>_<attribute>_factor
psf_<group>_<attribute>_daily
```

`attribute` 为 `support`、`influence`、`satisfaction` 或 `position_<axis>`。

原版示例的 125 个团体、3 项属性、9 条光谱共生成 **4,500 个**带中英文本地化的 modifier 定义。例如，国家精神的 `modifier` 块可以直接写：

```text
modifier = {
    psf_ger_spd_support_add = 5
    psf_ger_spd_influence_factor = 0.20
    psf_ger_spd_satisfaction_daily = 0.10
    psf_ger_spd_position_economy_add = -10
    psf_ger_spd_position_authority_daily = -0.02
}
```

- `add = 5`：有效期内增加 5 点。
- `factor = 0.20`：加成后数值乘以 1.20。各来源的 factor 相加；不是按添加顺序逐个相乘。
- `daily = 0.10`：每次每日更新，基础值增加 0.10。
- 光谱上的 factor 对坐标本身缩放。−40 乘以 1.20 得到 −48；如果希望明确往光谱左端或右端移动，应使用 `add` 或 `daily`。

将上述 `modifier` 块放进自己的国家精神后，可以用标准 `add_ideas`、`add_timed_idea`、`remove_ideas` 管理生命周期。也可将这些键直接放进 `common/dynamic_modifiers/*.txt` 的定义中，由引擎从变量取得数值：

```text
my_psf_organization_campaign = {
    enable = { has_country_flag = psf_initialized }
    psf_ger_spd_support_daily = my_campaign_daily_gain
    psf_ger_spd_influence_add = my_campaign_institutional_access
}
```

这些定义使用引擎真实的 `common/modifier_definitions` 扩展，再由 PSF 用 `modifier@<key>` 读取；不会把未知单词直接塞进引擎的国家数值系统。此写法在提供的原版 `common/modifier_definitions/modifier_definitions.txt` 注释中有直接说明，所附 CWT 也对定义、值和变量读取进行验证。

引擎管理原生 idea / trait / dynamic modifier 的叠加和到期。PSF 在每日更新读入当前总值；需要同一次事件中立刻更新数值和原版投影时，在更换原生来源前先导入已有变化，随后刷新和导出：

```text
psf_import_popularity = yes
# 在这里添加、移除或改变原生 idea / trait / dynamic modifier。
psf_refresh = yes
psf_export_popularity = yes
```

导出入口也会先处理尚未确认的原版差值，避免直接导出覆盖它们。显式把导入放在更换来源之前，还能保证这份原版变化按变更前的组织分类与倍率分配。`psf_import_popularity` 导入成功后立即记录原版快照，因此连续调用、再调用其他 API 或随后导出都不会重复累计同一份变化；在批次内显式导入也会保留批次状态。`bridge_mode = export` 不导入原版变化，`none` 不作原版投影。

原生 dynamic modifier 的变量更新周期由 HOI4 决定。改变其输入变量后，需要立即刷新原生 modifier 时，应按游戏支持的 `force_update_dynamic_modifier` 用法刷新来源，再调用 PSF 的重算。PSF 自己的 `psf_refresh` 不替代引擎的动态修正刷新。

PSF 自有的合法性修正由框架负责同步：`psf_add_legitimacy` 会即时通知界面更新；稳定度或政治点数修正值变化时，框架调用 `force_update_dynamic_modifier = yes`，不必等待下一次每日结算。数值没有变化的重复刷新不会再次强制刷新国家内所有动态修正。这一处理只管理合法性输入的变化，内容作者仍应按上面的顺序刷新自行维护的动态来源。

## 3. 声明命名修正来源

在 manifest 顶层增加 `modifiers`。它们由 PSF 保存独立的活动状态和剩余天数，不占用国家精神栏位。例如：

```json
{
  "modifiers": [
    {
      "id": "labor_compact",
      "name": {
        "english": "Labour compact",
        "simp_chinese": "劳工协定"
      },
      "description": {
        "english": "Negotiated access to institutions and continuing membership activity.",
        "simp_chinese": "协商取得的制度参与渠道，以及持续的会员活动。"
      },
      "duration_days": 90,
      "groups": ["eng_tuc", "eng_labour"],
      "attributes": {
        "influence": { "add": 8, "factor": 0.10 },
        "support": { "daily": 0.04 },
        "satisfaction": { "add": 12 }
      },
      "positions": {
        "economy": { "daily": -0.02 }
      }
    }
  ]
}
```

这是 manifest 的片段，合并到现有 manifest 后重新编译即可。`groups` 可省略，表示该来源可用于所有已注册团体；指定时只生成这些团体的调用入口。`duration_days` 省略或设为 `-1` 表示永久；正整数表示每日结算次数。零、其他负数、未知团体、未知光谱维度和空属性块均被校验拒绝。

使用一行明确命名的调用即可施加或移除：

```text
ENG = {
    psf_add_eng_tuc_modifier_labor_compact = yes
    psf_remove_eng_tuc_modifier_labor_compact = yes
}
```

使用其他持续时间，无须重新定义来源：

```text
ENG = {
    set_temp_variable = { psf_days = 30 }
    psf_add_timed_eng_tuc_modifier_labor_compact = yes
}
```

运行时定时入口要求 `psf_days > 0`，使用引擎的 `round_temp_variable` 取整，并限制在 1–36,500 次每日结算内。实际寿命和 tooltip 都读取归一化后的 `psf_modifier_days`；调用者传入的 `psf_days` 保持原值。需要永久来源时使用其声明为永久的默认入口。不同的命名来源独立叠加；对同一团体重复施加同一来源只刷新它的持续时间，不会叠加第二份。

查询和移除全部命名来源：

```text
if = {
    limit = { psf_eng_tuc_has_modifier_labor_compact = yes }
    # 这里可执行后续内容。
}

psf_clear_eng_tuc_modifiers = yes
```

`psf_clear_<group>_modifiers` 只移除 PSF 命名来源。原生国家精神或特质依然由内容作者用对应原生 effect 管理；不会误删承载其他效果的国家精神。

事件数据同样支持：

```json
{"op": "add_modifier", "group": "eng_tuc", "modifier": "labor_compact"}
```

以及 `remove_modifier`。编译器检查场景所属国家、组织 ID、来源 ID 和来源允许的目标列表。

## 4. 计算次序与到期

每次重算使用：

```text
effective = clamp((base + sum(add)) * max(0, 1 + sum(factor)), min, max)
```

原生 modifier 总值和所有活动命名来源参与同一个求和。加成不写回基础值。比如支持率基础值为 95、临时 `add = 20` 时显示 100；期间事件让基础值减少 10，则基础值成为 85，显示仍为 100；移除来源后正确得到 85。

影响力最后再应用活动状态系数：

```text
effective_influence = modified_influence * activity_factor
```

未活动组织的系数为 0；地下和受压制状态使用 manifest 中的对应系数。禁止、解禁不会二次叠加基础修正，也不会丢失基础影响力。

每日入口 `psf_daily_modifiers = yes` 在国家作用域中运行：

1. 先导入尚未处理的原版意识形态支持变化（仅双向桥接模式）。
2. 对已开始活动的团体，累加所有原生及命名来源的 `daily`，写入基础值并限幅。
3. 正时长来源减一天，归零时移除；永久来源不递减。
4. 重算有效值、政治分类、联盟、图表和国家总览。
5. 输出原版政党兼容投影并保存其快照，避免下一次导入把 PSF 自身的改变再次施加。

因此，一个持续 3 次每日结算且 `daily = 2` 的命名来源恰好累计三次，共 +6；第三次结算后其 `add` / `factor` 消失。未活动组织不累计 `daily`，但日历时长仍正常递减。查禁或地下组织已经在政治活动状态中，仍会按其来源累积变化。

框架已安装 `on_daily` 接口。集成作者不要再额外套 `every_country` 或重复调用每日入口，否则会重复结算。若自行合并多个 on_actions 文件，只保留一次这一入口。

## 5. 变量和数值 ID 接口

| 名称 | 含义 |
| --- | --- |
| `psf_g_<group>_<attribute>` | 基础值；旧版 API 兼容 |
| `psf_g_<group>_modified_<attribute>` | 加成和 factor 后的属性 |
| `psf_g_<group>_effective_influence` | 加成和活动状态折减后的最终影响力 |
| `psf_g_<group>_modifier_add_<attribute>` | 原生加命名来源的 add 总量 |
| `psf_g_<group>_modifier_factor_<attribute>` | 实际总倍率，包含初始 1，最低为 0 |
| `psf_g_<group>_modifier_count` | 活动的 PSF 命名来源数量 |
| `psf_m_<group>_<modifier>_active` | 命名来源活动状态，0 或 1 |
| `psf_m_<group>_<modifier>_days` | 剩余每日结算次数；永久为 −1 |

源活动状态和剩余时间使用国家持久变量；加载存档不重新初始化它们。基础值命名保持不变，旧接口仍可查询基础值。界面和默认阈值 trigger 读取有效值；需要对基础值做条件判断时，可以直接使用原生 `check_variable`。

通用数值接口适用于自动生成的脚本：

```text
set_temp_variable = { psf_group = <registry中的团体numeric_id> }
set_temp_variable = { psf_modifier = <registry中的修正numeric_id> }
psf_add_group_modifier = yes
# psf_add_timed_group_modifier 还读取 psf_days。
# psf_remove_group_modifier 移除相同二元组。
```

`psf_group_has_modifier` 用同样的临时目标参数查询。稳定数值 ID 由源 ID 派生，声明顺序不会改变它们；发现冲突时编译器要求显式设置 `numeric_id`。常规手写脚本优先使用名字明确的团体入口。

## 验证边界与依据

实现对照了所提供的原版 `common/modifier_definitions/modifier_definitions.txt`、真实使用 `modifier@` 的原版 scripted effects、on_actions 定义以及附带的 CWT 规则。官方 Wiki 的 [Modifiers](https://hoi4.paradoxwikis.com/Modifiers)、[Variables](https://hoi4.paradoxwikis.com/Variables)、[Effects](https://hoi4.paradoxwikis.com/Effect)、[On actions](https://hoi4.paradoxwikis.com/On_actions) 是开发者入口；本轮访问相关 Wiki 页面受到站点 401 限制，语法结论以提供的原版文件为直接依据，没有把无法读取的网页当成已确认来源。

回归测试执行实际生成的 Clausewitz 脚本，覆盖叠加、限幅后撤销、正时长到期、重复刷新、永久变化、读档状态、跨国隔离、任意维度、原版桥接与完整本地化。它们验证这些脚本的受支持语义，不等同于已经启动 HOI4 引擎进行验证。
