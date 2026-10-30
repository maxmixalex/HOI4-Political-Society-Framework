# Vanilla Political Societies / 原版政治社会示例

The vanilla example is a complete declarative content pack for PSF. Its source is [`examples/vanilla/manifest.json`](../examples/vanilla/manifest.json). It demonstrates the framework using historical organization names, authored political positions, independent public support and institutional influence, competing alliances, and alternative political choices.

本示例以可校验的声明式数据构建，使用历史组织名称、作者设定的政治立场、相互独立的民众支持与制度影响、竞争性联盟及可选择的政治事件，展示 PSF 的完整使用方式。

## Content coverage

| Profile | Organizations | Declared alliances | Institutional regime | Main demonstration |
| --- | ---: | ---: | --- | --- |
| Germany / 德国 | 10 | 2 | One-party republic / 一党共和国 | Prohibited and underground opposition; dissolved parties can resume activity; industry and officers have influence beyond public support |
| Britain / 英国 | 9 | 3 | Constitutional monarchy / 君主立宪制 | Three-party governing agreement; Labour and Liberals coexist; unions retain a separate organization |
| France / 法国 | 10 | 3 | Parliamentary republic / 议会共和国 | An electoral alliance and a government are distinct; one party can join both; a movement can create a successor party |
| United States / 美国 | 10 | 3 | Presidential republic / 总统共和国 | Democrats and Republicans are separate parties within overlapping ideology space; progressive caucus, unions and manufacturers bargain independently |
| Soviet Union / 苏联 | 8 | 2 | Soviet party-state / 苏维埃党国体制 | Non-electoral factions, security institutions, military leadership, managers and unions have distinct interests |
| Italy / 意大利 | 9 | 2 | Corporatist monarchy / 法团君主制 | A ruling party coexists with crown, officers, employers and official syndicates; institutional preference differs from the actual constitution |
| Japan / 日本 | 9 | 3 | Imperial constitutional order / 帝国宪制 | Two parliamentary parties coexist with court, navy and rival army factions |
| China / 中国 | 10 | 2 | Authoritarian republic / 威权共和国 | A state party, internal factions, regional military networks and civic organizations remain separate actors |
| Spain / 西班牙 | 12 | 4 | Parliamentary republic / 议会共和国 | Electoral cooperation, worker organizations outside party politics, monarchists and a distinct 1939 starting arrangement |
| Poland / 波兰 | 10 | 3 | Authoritarian republic / 威权共和国 | Civilian and military governing circles; democratic opposition; an initially inactive organization begins activity |
| Generic democratic | 7 | 0 | Parliamentary republic | A single governing organization, distinct opposition parties, organized labor, business, military and an inactive civic association |
| Generic fascist | 7 | 0 | One-party republic | A single governing organization with different initial legal access and governing preferences |
| Generic communist | 7 | 0 | Soviet party-state | A single governing organization; overlapping public support and party-state institutions |
| Generic non-aligned | 7 | 0 | Authoritarian republic | A single governing organization; institutional bargaining outside competitive party government |

There are **125 declared organizations, 27 declared alliances, nine axes, 11 ideology prototypes, nine regime definitions, and 50 dated scenarios with 120 choices**. The pack also declares **23 named modifier sources** and generates **4,500 native group/attribute modifier keys**. Seventeen existing alliances retain their original membership and ten proposed agreements start empty. The compiler creates no additional working-cabinet alliances; the four generic profiles govern through a single organization and require no alliance.

Every country outside the ten authored profiles receives an abstract fallback selected from its initial native ideological compatibility state. The four generic profiles are reusable templates, not four extra countries. They provide playable political organizations for minor countries, releasable nations and new countries initialized by the framework. They do not claim to identify every minor country's historical parties or exact constitutional structure.

十个定制国家以外的国家会根据原版初始政治兼容状态获得通用模板。通用模板确保小国、可释放国家及新初始化国家也有可操作的政治组织，但不声称其通用组织名称就是这些国家的真实历史政党，也不声称通用国体准确对应所有国家。

## What the numbers mean

**Every numerical score is an authored game value.** None is a historical election result, a measured membership share, a polling estimate, or a scholarly claim that political positions can be placed objectively at a particular coordinate. The bundle deliberately includes groups with modest popular support and substantial influence, such as employers, security bodies and military institutions.

- `support` is the organization's independent public support score. A person may support a party, a trade union and a religious association at the same time. These scores therefore do not sum to 100.
- `influence` is an institutional power score. It is also independent, rather than a share of a compulsory national pie.
- `satisfaction` is acceptance of the current government. Shared policy positions do not guarantee satisfaction, and governing organizations can become dissatisfied.
- An alliance's `cohesion` is an authored initial condition. It represents the viability of the agreement and is separate from its members' individual attitudes.
- Spectrum positions run from −100 to +100. Coordinates are preferences; a group's current legal status does not change its underlying positions.

所有数值都是游戏设计参数。支持率不是互斥的选票分配，影响力不是必须加总为 100 的饼图份额，满意度也不是意识形态相近程度的同义词。任何数值都不应被引用为历史民调或真实选举结果。

## Nine configurable axes

| Axis | −100 endpoint | +100 endpoint |
| --- | --- | --- |
| `economy` | Collective ownership / 集体所有 | Private enterprise / 私营经济 |
| `culture` | Reform / 革新 | Tradition / 传统 |
| `society` | Egalitarian / 平等主义 | Hierarchical / 等级主义 |
| `nation` | Civic and plural / 公民与多元 | Exclusive and ethnic / 排他与族裔 |
| `religion` | Secular state / 世俗国家 | Confessional state / 宗教国家 |
| `authority` | Plural and distributed / 多元分权 | Concentrated / 集中集权 |
| `foreign_policy` | Cooperation / 合作 | Expansion / 扩张 |
| `liberties` | Protected rights / 权利保障 | Security discretion / 安全优先 |
| `head_of_state` | Elected or republican / 选举或共和 | Hereditary / 世袭 |

The last axis makes monarchy–republic preference independent of economic organization. A communist organization can support a monarchy in an alternate scenario without being reclassified as a conservative merely because of that single coordinate. The institutional mismatch calculation uses the axes declared on the regime. In this example, regime definitions constrain head of state, authority and liberties. They do not treat a market economy or a traditional culture as a constitutional requirement.

The `workers_monarchy` regime is explicitly fictional. It is supplied as a usable alternate institution for the monarchist–socialist combinations described in the project brief. It is not presented as the actual 1936 government of any country.

`workers_monarchy` 是明确标注的架空制度，用于展示世袭元首与劳动者政治代表制度可以同时存在，不是任何国家的真实 1936 年初始国体。

This fictional regime also demonstrates an explicit `native_policy` rather
than inheriting diplomatic permissions from an ideology slot. Its authored
tension thresholds are 75% for war justification, 60% for joining a faction,
and 25% for lend-lease, volunteers and guarantees. War justification is limited
to countries that generated tension; lowering tension is permitted;
collaboration governments are disabled. These are chosen game rules, not
historical or constitutional findings about any real monarchy. Other regimes
continue to use their existing policy defaults.

该架空制度还展示了独立的 `native_policy`：制造战争借口、加入阵营、租借法案、
志愿军与独立保障的紧张度门槛分别为 75%、60%、25%、25%、25%；战争借口仅针对
制造紧张度的国家，允许降低紧张度，禁止建立合作政府。这些都是作者指定的玩法规则，
不从“君主制”名称推导现实政治结论，也不修改其他政体的默认规则。

## Parties, factions and associations

Seven organization kinds appear in the example:

- Parties / 政党
- Trade unions / 工会与劳动联合组织
- Employers' associations / 雇主与工商协会
- Military institutions / 军事机构
- Religious associations / 宗教社团
- Civic organizations / 公民与社会组织
- Factions / 党团、内部派系与机构集团

Only groups marked `electoral: true` participate as electoral organizations. Military and employer influence does not turn their organizations into ballot parties. Legal parties, underground parties, prohibited groups and inactive organizations all use the same underlying data structure.

Organization labels sometimes aggregate networks rather than identify a single incorporated body: for example, Chinese rural notables, Soviet enterprise directors and a generic military establishment. These are intentional abstractions. The USA's industrial organizing movement is named broadly enough to cover its transition from a committee to a congress without incorrectly giving the later formal name to its 1936 organization.

## Government agreements and cabinet membership

A PSF government alliance is a **political support agreement**, not a list of cabinet ministers. It can include an organization supporting a government from outside its ministries. This is essential when a trade union or a parliamentary party provides support but does not enter the cabinet.

The France example therefore includes the Radicals in both the initial cabinet agreement and the Popular Front electoral agreement. The event transferring governing support to the Popular Front does not assert that Communist Party representatives or CGT officers became ministers. The historical PCF provided external parliamentary support to the Blum cabinet; the French National Assembly's documentation distinguishes this explicitly.[1]

PSF 的执政联盟代表政治支持协议，不等于内阁部长名单。法共或工会加入执政支持协议，不意味着它们的代表被设定为内阁部长。该抽象允许同一个组织同时参与选举联盟与政府支持协议。

The initial January snapshots are compact political models, rather than a day-by-day reconstruction of all cabinet members. In particular, France's initial cabinet support agreement, Spain's caretaker centre and China's regional military networks aggregate politically relevant support relationships. Full historical cabinet rosters are outside this example's data model.

## Dated scenarios and alternatives

Each authored profile contains five one-time scenarios, including government-mandate negotiations in September 1939 and coordination settlements in October 1939. Their dates provide the earliest eligibility for a 1936 campaign; delivery occurs on the first weekly framework pulse after that date. Some coincide with a historical electoral or organizational milestone; others are explicitly authored opportunities for bargaining. Their choices are not scripts claiming that every offered action historically occurred.

| Country | Date | Scenario | Mechanics exercised |
| --- | --- | --- | --- |
| Germany | 1936-04-01 | Independent labor petition | Ban or legalize; influence and satisfaction trade-offs |
| Germany | 1937-02-01 | Reconstitution of the Centre | Activate an inactive party; retain ideological identity |
| Britain | 1936-06-01 | Review of the National Government pact | Coalition renewal or a member's withdrawal |
| Britain | 1937-03-01 | Trade union bargaining | Influence without government membership |
| France | 1936-05-03 | Popular Front governing agreement | Electoral alliance becomes governing support |
| France | 1936-07-07 | A movement becomes a party | Activate a successor organization; prohibition alternative |
| United States | 1936-04-15 | Labor relations under the New Deal | Support, influence and satisfaction trade-offs |
| United States | 1937-02-15 | Progressive agreement | Join or leave a governing agreement |
| Soviet Union | 1936-09-01 | Party and professional institutions | Military influence; supervision or consultation |
| Soviet Union | 1937-06-01 | Rural representatives | Broad support with limited influence; legitimacy concessions |
| Italy | 1936-08-01 | Party and crown | Institutional compromise and conflicting satisfaction |
| Italy | 1937-05-01 | Catholic autonomy | Social association influence and acceptance |
| Japan | 1936-03-01 | Rival military currents | Ban a faction; change influence without creating a party |
| Japan | 1937-05-01 | Cabinet political base | Alternative military or parliamentary coalition expansion |
| China | 1936-12-20 | Domestic political truce | Legalize rival networks without organizational merger |
| China | 1938-06-01 | Constitutional association | A new civic political organization begins activity |
| Spain | 1936-02-16 | Electoral agreement seeks office | Form a governing alliance or a different coalition |
| Spain | 1936-04-01 | Union autonomy | Improve satisfaction without forced membership |
| Poland | 1936-10-01 | Opposition negotiations | Negotiate with distinct opposition groups |
| Poland | 1937-02-21 | Camp of National Unity | A new organization begins activity and joins government |

### Added negotiation scenarios and modifiers (0.2.0)

The third scenario for each authored country is an explicitly fictional negotiation opportunity in September 1937. These dates are gameplay scheduling, not historical assertions. Each choice applies a real named source to a specific organization; its immediate effects and daily changes feed the same support, influence, satisfaction and spectrum calculations used by the interface and government model.

| Country / group | First agreement | Alternative | Eligible date |
| --- | --- | --- | --- |
| Germany / industrial employers | Employers' roundtable | Negotiation breakdown | 1937-09-01 |
| Britain / TUC | Ninety-day labor compact | Negotiation breakdown | 1937-09-02 |
| France / CGT | Permanent independent charter | Sixty-day public campaign | 1937-09-03 |
| United States / NAM | Employers' roundtable | Negotiation breakdown | 1937-09-04 |
| Soviet Union / army | Professional review | Temporary assurances | 1937-09-05 |
| Italy / Catholic associations | Permanent organizing network | Civic outreach | 1937-09-06 |
| Japan / navy | Diplomatic consultation | Professional review | 1937-09-07 |
| China / rural associations | Equal membership charter | Civic outreach | 1937-09-08 |
| Spain / UGT | Labor compact | Civil guarantees | 1937-09-09 |
| Poland / presidential circle | Shared authority pledge | Institutional compromise | 1937-09-10 |

The sixteen source definitions include temporary score offsets, proportional bonuses, accumulated daily growth, daily decline, all nine spectrum axes, permanent organizational agreements and time-limited policy positions. `public_campaign` accumulates 0.05 support per active day for 60 pulses; its gains remain when the campaign ends. `labor_compact` grants 12 temporary satisfaction and accumulates 0.02 institutional influence per active day for 90 pulses. `independent_organization` remains until removed by the author's explicit scripted effect. Changing legality does not erase a source; inactive organizations stop daily drift, while the calendar duration continues to expire.

新增的十场协商均为明确的架空玩法机会，不将日期与选项冒充史实。具名修正直接参与实际数值计算：临时加成到期撤销，每日变化写入基础值，常设协议直到明确撤销才结束。所有十六项修正都可由作者在 manifest 中调整，或通过其生成的 effect 在自己的事件、国策和决议中调用；框架不自动替换这些内容。

Historical examples can be disabled through the framework's example-events game rule. Framework decisions remain available. Dates before a campaign's initial bookmark are excluded, so the 1939 bookmark does not immediately replay the 1936–1938 sequence.

本示例事件可通过开局规则关闭。关闭历史示例事件不会移除框架的通用决议。1939 年开局不会补播开局日期之前的 1936—1938 年事件。

## 后期协商：1939 年的协调安排（0.3.1）

十个定制国家各新增一场三选一的后期协商，最早触发日期分别为 1939 年 10 月 1—10 日，仍由每周更新派发。它们在 1939 剧本初始化时尚未过期，因此也可在后期开局中触发。所有新增事件明确标注为架空政治协商，日期不代表史实，也不假设特定战争、领土或政权更替已经发生。

| 方案 | 真实游戏效果 | 取舍 |
| --- | --- | --- |
| 共同委员会 | 工商或生产组织与社会团体获得 180 天 `production_council`；各有影响力加成、满意度加成及每日支持增长 | 共享制度参与权；若社会团体此前遭查禁，会明确恢复合法活动 |
| 集中协调授权 | 指定行政、执政党或军方团体获得 120 天 `executive_coordination`；被排除的社会团体获得 90 天 `excluded_from_consultation` | 集中组织的影响力提高，权力与自由度立场偏向集中和安全优先；社会团体的满意度逐日下降 |
| 独立代表权章程 | 社会团体恢复合法活动并获得永久 `independent_civic_charter`；集中组织基础影响力降低 4 点 | 为独立组织提供参与保障，同时削弱集中权力；不会强制把该组织加入执政联盟 |

这三种安排会撤销同一协商链中互相冲突的修正，避免换选项或作者重新触发时留下两套相反的授权。它们不清除无关的组织修正。永久章程通过对应的 `psf_remove_<group>_modifier_independent_civic_charter` 撤销；临时委员会到期后取消加成，但保留期间累积的基础支持。

各国参与者使用已有的稳定团体 ID：德国的工商组织、军官团与独立工会；英国的工商联合会、保守党与 TUC；法国的工商联合会、民主联盟与 CGT；美国的制造商协会、民主党与 CIO；苏联的工业管理者、安全机构与合作社；意大利的工商组织、军队与天主教社团；日本的工商界、统制派与社会大众党；中国的工商网络、中央军官与乡村社团；西班牙的卡洛斯派、军队与 UGT；波兰的工商组织、军方集团与工会。

These ten fictional negotiations extend play beyond the later opening bookmark. Their three choices implement shared consultation, concentrated authority, or independent representation through real timed/permanent sources, daily changes, legality changes and legitimacy trade-offs. They preserve organization identities and coalition memberships. Political participation does not imply cabinet membership.

## 政府授权：独立执政、政治协议与看守政府（0.4.1）

新增的十场政府授权情景统一以 **1939-09-01** 为日期门槛，由之后的首个每周更新派发。
1939-08-14 开局不会将它们标记为已经发生。每场均提供三种实际改变政治状态的选择：
授权一个现有组织独立执政、明确邀请三个现有组织达成新协议并执政，或清空政治授权、
进入看守状态。组织并不需要先加入联盟才能单独取得执政权。

这十场情景、十项拟议协议与所有授权结果均为**架空玩法**，不是对 1939 年真实事件的
复述，也不假定特定战争、领土变化或宪法程序已经发生。总统制国家使用行政与国会
支持的叙事，党国体制使用机构职责分配，君主制国家使用宫廷与内阁授权；没有把每个
国家都套入议会组阁模板。政治支持协议仍不等于部长名单。

| 国家 | 单独授权的组织 | 新协议的另两方 |
| --- | --- | --- |
| 德国 | 纳粹党 | 工业集团、军官团 |
| 英国 | 保守党 | 工党、自由党 |
| 法国 | 激进党 | 工人国际法国支部、民主联盟 |
| 美国 | 民主党 | 国会进步派、共和党 |
| 苏联 | 联共（布） | 国有企业管理者、工会中央理事会 |
| 意大利 | 国家法西斯党 | 王室、工业联合会 |
| 日本 | 民政党 | 政友会、宫廷与重臣 |
| 中国 | 国民党 | 地方军事网络、商会 |
| 西班牙 | 统一传统主义长枪党组织 | 军官集团、传统主义共融 |
| 波兰 | 总统派 | 军方集团、民族团结营 |

每项新协议初始没有成员，也不执政；只有玩家明确选择协商方案才会填入成员并赋予
执政身份。原有联盟不会被删除，原联盟与新协议可以同时存在。同样，从协议执政改成
独立组织执政或看守状态，只改变执政身份，不清除任何既存联盟的成员。
从 1936 年开始的游戏若尚未激活西班牙统一组织或波兰民族团结营，相应选择会明确
执行激活与合法化，并通过该方案的实际影响力来源保证新参与者具备有效政治权重。
它不会在日历走到 1939 年时强行覆盖初始数据。

| 具名来源 | 期限 | 实际效果 |
| --- | --- | --- |
| `independent_executive_mandate` / 单独行政授权 | 90 天 | 授权组织影响力 +8、影响力系数 +5%、满意度 +6、权力立场 +8 |
| `negotiated_governing_support` / 协商执政支持 | 120 天 | 三个签署组织各获得影响力 +5、满意度 +10、权力立场 −6 |
| `caretaker_assurances` / 过渡行政保障 | 60 天 | 三个参与组织各获得影响力 −3、满意度 +8、自由度立场 −6；不授予执政权 |

三个方案仅撤销本条授权链中互相冲突的来源，保留其他事件和作者添加的修正。重复
执行不会叠加同名加成。来源到期撤销临时数值，不自动解散政治协议或撤销独立组织的
执政身份；政府更替仍由政治操作决定。

The ten fictional mandate scenarios add thirty fully executable choices.
Every new agreement starts dormant, and no initial organization score, legal
status, government, existing alliance or 1939 override was changed. Tests
execute every emitted choice, repeat it to detect stacked gains, switch from
agreement to independent and caretaker government while preserving all
memberships, exercise initially inactive participants, and run the actual
weekly scheduler with the example-events rule enabled and disabled. A separate
expiry check verifies that a temporary mandate bonus expires without removing
the independent government.

## 1939 starting overrides

Every authored profile includes a 1939 override. These are starting-bookmark data, not scheduled changes that overwrite a player's campaign when the calendar reaches 1939.

The overrides include the emergence of France's Social Party and Poland's Camp of National Unity; a different Spanish governing bloc; increased military influence in Japan; changes to industrial organizing in the USA; and altered institutional power in Germany and the Soviet Union. Spain's override deliberately distinguishes the unified authoritarian organization from the separate 1936 parties and labor organizations.

The overrides use the same group IDs, so scenario authors and integrations do not need a second set of organization identifiers for the 1939 bookmark. An inactive group may become active, a legal group may be prohibited, and alliance membership may change while the underlying identity remains stable.

1939 覆盖只用于初始化相应剧本，不会在从 1936 年开始的游戏运行到 1939 年时强行覆盖玩家已经形成的政治局势。

## Electoral starting clocks

The example seeds elapsed electoral months for Britain (2), France (44), the USA (38), Japan (0) and Spain (35) at the 1936 bookmark. Britain, France, the USA and Japan use the supplied native 48-month term; Spain uses its supplied 36-month opening term. Later-bookmark values are 45, 39, 33, 19 and 0 months respectively. France's later value models elapsed time since the May 1936 election; its supplied 1939 history block does not refresh the older election date. Spain's authoritarian 1939 institution disables framework elections.

These are month-resolution starting conditions, not claims of exact-day delivery. The standalone political scenarios and the automatic ballot are separate mechanisms.

## Suggested demonstration sessions

1. **Britain:** inspect Conservative, Labour and Liberal coordinates. Compare business support with business influence. Open the National Government agreement and withdraw a small partner; observe the resulting change in governing strength and cohesion.
2. **Germany:** inspect underground SPD and KPD separately. Permit the Centre to resume activity. Compare legalization with a direct support increase; the two actions change different parts of political state.
3. **France:** inspect the Radicals' simultaneous coalition and electoral relationships. Let the Popular Front scenario occur and compare the governing composition before and after the choice.
4. **Italy:** compare the ruling party's preferred head-of-state coordinate with the crown's and with the actual corporatist monarchy. Reform institutions or obtain concessions and observe legitimacy separately from ideology.
5. **Poland:** inspect the initially inactive Camp of National Unity, then let the 1937 event create an active organization. Its entry into government is a separate effect from activation.
6. **A minor country:** verify that the fallback supplies a government, two opposition organizations, labor, business and military actors, and an inactive civic association. Use it as the starting point for a new bespoke profile.

These are manual acceptance paths for the in-game build. They are not a claim that automated script validation has rendered or executed the game UI.

## Extension guidance

To add a country, copy an existing profile, choose a unique profile ID and tag, and give every organization and alliance a globally unique ID. All positions should declare the currently configured axes. Provide both `english` and `simp_chinese` strings for parity with this content pack.

To add an organization during a campaign, declare it with `status: inactive`, give it the intended long-term positions and descriptive identity, then use an `activate` effect. Activation, legalization, popularity, influence and coalition entry are separate operations; the Poland event demonstrates how to combine them deliberately.

To model a party split, declare both organizations and use an event to activate the successor, transfer suitable support and influence, and alter alliance membership. No new native ideology group is needed. The framework's score operations are bounded, so content should use modest increments and explicit transfer logic when conservation is desired.

To give the communist party a monarchical preference, change only its `head_of_state` position or use the appropriate spectrum effect from an integration. Do not rename its native ideological compatibility slot to create the appearance of a new party. A governing party's preferences and the regime definition remain independent inputs to legitimacy.

## Sources and provenance

The supplied vanilla archive is the primary compatibility reference: `history/countries/*.txt` provides native country tags, initial ruling ideologies, election permissions and the presence of 1939 history blocks. The supplied KR, TNO and PB script archives are framework implementation references; this example does not copy their country political content.

The historical organizational examples below were checked against institutional archives and official historical material. These sources support organization names, relationships or dated milestones; they do **not** supply the numerical spectrum or power values.

1. French National Assembly, [1935–1936: Adoption of the Popular Front program and electoral victory](https://www.assemblee-nationale.fr/dyn/histoire-et-patrimoine/troisieme-republique/adoption-et-publication-du-programme-du-rassemblement-populaire-victoire-du-front-populaire), and [1936 legislative elections](https://www.assemblee-nationale.fr/dyn/histoire/il-y-a-90-ans-le-front-populaire-et-les-lois-sociales-de-la-republique/les-elections-legislatives-des-26-avril-et-3-mai-1936). Supports electoral cooperation among distinct parties and PCF support without cabinet participation.
2. UK House of Commons Library, [Hung parliaments](https://researchbriefings.files.parliament.uk/documents/SN04951/SN04951.pdf), section 3.2. Supports the continuing organizational identities of National Labour and Liberal Nationals inside the National Government.
3. German Historical Museum, [One-party state](https://www.dhm.de/lemo/kapitel/ns-regime/etablierung-der-ns-herrschaft/einparteienstaat) and [Destruction of the trade unions](https://www.dhm.de/lemo/kapitel/ns-regime/etablierung-der-ns-herrschaft/zerschlagung-der-gewerkschaften). Supports the distinction between suppression, dissolution and the regime's official labor organization.
4. US National Archives, [National Labor Relations Act (1935)](https://www.archives.gov/milestone-documents/national-labor-relations-act), and US National Labor Relations Board, [1937: Act held constitutional](https://www.nlrb.gov/about-nlrb/who-we-are/our-history/1937-act-held-constitutional). Supports the example's labor–employer conflict and organized manufacturers' opposition.
5. US Library of Congress, [Labor unions during the Great Depression and New Deal](https://www.loc.gov/classroom-materials/united-states-history-primary-source-timeline/great-depression-and-world-war-ii-1929-1945/labor-unions-during-great-depression-and-new-deal/). Provides primary-source context for organized labor as an actor distinct from a political party.
6. Japan National Diet Library, [Transformation of the proletarian political parties](https://www.ndl.go.jp/modern/e/cha4/description09.html) and [Chronological table](https://www.ndl.go.jp/modern/e/utility/chronology.html). Supports the Social Mass Party's existence and the February 1936 institutional crisis.
7. US Department of State historical documents, [Tokyo dispatch, 5 March 1936](https://history.state.gov/historicaldocuments/frus1936v04/d759). A contemporary diplomatic report distinguishes Seiyukai opposition to the Okada cabinet from Minseito support.
8. Polish State Archives, [Adam Koc's declaration of 21 February 1937 and the establishment of the Camp of National Unity](https://www.szukajwarchiwach.gov.pl/en/jednostka/-/jednostka/20273194?refererPlid=20136), reference 12/27/0/5/881. Provides the organizational milestone used by the Polish formation event.
9. Spain's official gazette, [20 April 1937, decree of unification](https://www.boe.es/gazeta/dias/1937/04/20/pdfs/BOE-1937-182.pdf). Provides the primary legal record behind the distinction between the 1936 organizations and the unified organization represented in the 1939 override.

The example favors transparent, editable gameplay approximations over an implicit claim of complete historical reconstruction. A content author can replace any profile, score, axis, regime, event or date through the manifest.
