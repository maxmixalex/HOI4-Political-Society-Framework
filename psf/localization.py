"""Bilingual generated labels, policy descriptions and state-aware event text."""
from __future__ import annotations

from pathlib import Path

from .model import profiles
from .script import block, check, emit, quoted

LANGUAGES = ("english", "simp_chinese")


def write_localization(output: Path, stem: str, content: dict[str, dict[str, str]]) -> None:
    for language, entries in content.items():
        path = output / "localisation" / language / f"{stem}_l_{language}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("l_" + language + ":\n" + "\n".join(" " + key + ":0 " + quoted(value) for key, value in sorted(entries.items())) + "\n", encoding="utf-8-sig")


def core_localization() -> dict[str, dict[str, str]]:
    pairs = {
        "psf_political_legitimacy": ("Political legitimacy", "政治合法性"),
        "psf_political_legitimacy_desc": ("Public acceptance and the relationship between the government's program and the country's institutions affect political power and stability.", "民众认可程度以及政府主张与实际制度之间的关系，影响政治点与稳定度。"),
        "psf_no_winner": ("No electoral mandate", "尚无选举授权"),
        "psf_effect_legitimacy": ("Legitimacy changes by [?psf_amount|1] (bounded to 0–100).", "合法性变动[?psf_amount|1]点（限于0至100）。"),
    }
    return {lang: {key: value[i] for key, value in pairs.items()} for i, lang in enumerate(LANGUAGES)}


def content_localization(manifest: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {lang: {} for lang in LANGUAGES}
    def add(key: str, english: str, chinese: str):
        out["english"][key] = english
        out["simp_chinese"][key] = chinese
    def label(key: str, value: dict[str, str]):
        for language in LANGUAGES:
            out[language][key] = value[language]
    for kind, items in (("axis", manifest["axes"]), ("ideology", manifest["ideologies"]), ("regime", manifest["regimes"]),
                         ("group", [g for p in profiles(manifest) for g in p["groups"]]), ("alliance", [a for p in profiles(manifest) for a in p["alliances"]])):
        for item in items:
            for field, suffix in (("name", "name"), ("description", "desc"), ("short_name", "short_name"), ("left", "left"), ("right", "right")):
                if field in item:
                    label("psf_" + kind + "_" + item["id"] + "_" + suffix, item[field])
    pairs = {
        "psf_government_category": ("Political society: government", "政治社会：政府"),
        "psf_government_category_desc": ("Institutions: [PSFUIRegime]\nGovernment: [PSFUIGovernment]\nLegitimacy: [?psf_legitimacy|1]/100\nMonthly change: [?psf_legitimacy_change|2]\nInstitutional mismatch: [?psf_alignment_gap|1]/100", "实际制度：[PSFUIRegime]\n执政联盟：[PSFUIGovernment]\n合法性：[?psf_legitimacy|1]/100\n每月变化：[?psf_legitimacy_change|2]\n制度偏离：[?psf_alignment_gap|1]/100"),
        "psf_groups_category": ("Political society: organizations", "政治社会：政治团体"),
        "psf_groups_category_desc": ("Select an organization in the politics sidebar to see its policy actions here. Support, institutional influence and satisfaction are independent values. Banning suppresses influence; it does not erase supporters.", "在政治界面侧栏选择一个团体，即可在这里处理该团体的政治事务。支持率、制度影响力和满意度分别记录。查禁压低影响力，不会凭空消除其支持者。"),
        "psf_alliances_category": ("Political society: alliances", "政治社会：政治联盟"),
        "psf_alliances_category_desc": ("Negotiate cabinet agreements and electoral or opposition pacts. Select an organization in the sidebar for membership actions. Disagreement and dissatisfaction can lead to withdrawals and collapse.", "组织执政、选举与反对派联盟。在侧栏选择政治团体后可办理加入与退出。立场分歧和不满会导致成员退出，乃至联盟瓦解。"),
        "psf_institutions_category": ("Political society: institutions", "政治社会：政治制度"),
        "psf_institutions_category_desc": ("Actual institutions do not automatically change with the governing parties. Constitutional reform costs political capital and initially disrupts legitimacy; long-term alignment can improve it.", "实际制度不会随着执政党更替自动改变。制度改革需要政治资源，并会暂时扰动合法性；长期立场趋于一致则有助于恢复认可。"),
        "psf_public_consultation": ("Public consultation and confidence building", "开展公众协商"),
        "psf_public_consultation_desc": ("Spend 50 political power to gain 6 legitimacy. Available every 60 days. This can compensate for institutional mismatch without changing the regime.", "花费50政治点，提高6点合法性，冷却60天。可以在不改变国体的情况下弥补部分制度偏离。"),
        "psf_snap_election": ("Call an early election", "举行提前选举"),
        "psf_snap_election_desc": ("Available after six months under an electoral constitution. Legal electoral parties compete with current support; civil organizations have no extra votes. Electoral pacts combine member ballots. The winning pact or party forms a cabinet. Cost: 100 political power.", "采用允许选举的制度并经过六个月后可用。合法参选政党依当前支持率竞争，社会团体不会增加选票。选举联盟合计成员得票，由胜出的联盟或政党组阁。花费100政治点。"),
        "psf_open_society_view": ("Select the political society sidebar", "打开政治社会侧栏"),
        "psf_open_society_view_desc": ("Enable the organization sidebar. Open the country's politics tab to view it.", "开启团体侧栏；打开本国政治面板即可查看。"),
        "psf_event_1_title": ("The ballot has been counted", "选举结果揭晓"),
        "psf_event_1_desc": ("The largest individual electoral party is [PSFRuntimeGetWinner]. The government is [PSFUIGovernment].\n\nVotes were normalized among legal electoral organizations. An electoral alliance may form the government even when a different party holds the largest individual vote.\n\nThe country's institutions remain [PSFUIRegime].", "单个政党中得票最多的是[PSFRuntimeGetWinner]。现执政联盟为[PSFUIGovernment]。\n\n选票在合法参选组织之间归一分配。选举联盟可能凭合计票数组阁，而不是由单党得票第一者组阁。\n\n国家实际制度仍为[PSFUIRegime]。"),
        "psf_event_2_title": ("An alliance changes course", "政治联盟出现变动"),
        "psf_event_2_desc": ("An alliance has lost members or dissolved after prolonged internal disagreements.\n\nThe society sidebar shows the surviving memberships and the government's current support. A caretaker government can be replaced through a new cabinet agreement.", "长期内部矛盾导致某个政治联盟出现成员退出或解散。\n\n政治社会侧栏可以查看当前成员关系以及政府支持情况。如进入看守状态，可以重新达成执政协定。"),
        "psf_acknowledge": ("Continue", "继续"),
        "psf_rule_group": ("Political Society Framework", "政治社会框架"),
        "psf_rule_events": ("Vanilla political society events", "原版政治社会事件"),
        "psf_rule_enabled": ("Enabled", "启用"),
        "psf_rule_disabled": ("Disabled", "关闭"),
        "psf_rule_events_enabled_desc": ("Enable the example's dated political events and alternative choices. PSF does not replace national focus trees or conduct foreign policy.", "启用示例模组按日期触发的政治事件及替代选择。PSF不会接管国策树或外交政策。"),
        "psf_rule_events_disabled_desc": ("Run the society framework and player policies without the example's dated events.", "保留政治社会框架与玩家政治行动，关闭示例中的定时事件。"),
    }
    for key, pair in pairs.items():
        add(key, *pair)
    verbs = {
        "ban": ("Ban", "查禁", "Suppress effective influence to the banned factor and reduce satisfaction by 15 and legitimacy by 3. Support persists. Groups with at least 10 support can go underground on the next monthly update.", "将有效影响力压低至查禁系数，满意度降低15，合法性降低3。支持率保留；支持率至少为10的团体可在下次月度更新转入地下。"),
        "legalize": ("Legalize", "解禁", "Restore legal access to institutions and add 8 satisfaction. Baseline influence and support are recorded independently.", "恢复合法的制度参与渠道，提高8点满意度。基础影响力与支持率分别保留。"),
        "activate": ("Authorize activity for", "允许开始活动：", "An inactive organization begins legal political activity with its declared constituency and resources.", "尚未活动的组织以其预先声明的支持者与资源开始合法政治活动。"),
        "negotiate": ("Negotiate with", "与其协商：", "Add 10 satisfaction toward the present government; 60-day cooldown.", "对现政府满意度提高10点；冷却60天。"),
        "campaign": ("Campaign for", "开展支持动员：", "Add 4 popular support; 60-day cooldown. This is approval, not an additional vote from nonparty organizations.", "支持率提高4点；冷却60天。社会组织的支持率不额外算作选票。"),
        "empower": ("Increase institutional access for", "扩大制度参与：", "Add 4 baseline influence; 90-day cooldown. This does not automatically increase popular support.", "基础影响力提高4点；冷却90天。不会自动增加民众支持率。"),
    }
    for p in profiles(manifest):
        for g in p["groups"]:
            gid = g['id']
            short = '$psf_group_' + gid + '_short_name$'
            for action, en, zh in (
                ('ban', 'Prohibit', '查禁'), ('legalize', 'Restore legal activity for', '恢复合法活动：'),
                ('activate', 'Begin political activity for', '开始政治活动：'), ('underground', 'Move into underground activity:', '转入地下活动：'),
                ('deactivate', 'End political activity for', '停止政治活动：')):
                add(f'psf_effect_{action}_{gid}', en + ' ' + short, zh + short)
            for metric, en, zh in (('support','popular support','支持率'),('influence','institutional influence','基础影响力'),('satisfaction','satisfaction with government','对政府满意度')):
                add(f'psf_effect_add_{gid}_{metric}', short + ': ' + en + ' changes by [?psf_amount|1].', short + '：' + zh + '变动[?psf_amount|1]。')
                add(f'psf_effect_set_{gid}_{metric}', short + ': set ' + en + ' to [?psf_amount|1].', short + '：' + zh + '调整至[?psf_amount|1]。')
            for axis in manifest['axes']:
                add(f"psf_effect_position_{gid}_{axis['id']}", short + ': $psf_axis_' + axis['id'] + '_name$ position becomes [?psf_position|0].', short + '：$psf_axis_' + axis['id'] + '_name$立场调整至[?psf_position|0]。')
            for action, (english, chinese, edesc, cdesc) in verbs.items():
                key = f"psf_policy_{action}_{g['id']}"
                add(key, english + " " + g["short_name"]["english"], chinese + g["short_name"]["simp_chinese"])
                add(key + "_desc", g["name"]["english"] + "\n\n" + edesc, g["name"]["simp_chinese"] + "\n\n" + cdesc)
        for a in p["alliances"]:
            aid = a["id"]
            aname = '$psf_alliance_' + aid + '_name$'
            add('psf_effect_govern_' + aid, aname + ' forms the government; the constitution remains separate.', aname + '组织政府；实际制度独立保留。')
            add('psf_effect_dissolve_' + aid, 'Dissolve ' + aname + ' and remove its memberships.', '解散' + aname + '并清除其成员关系。')
            add('psf_effect_cohesion_' + aid, aname + ': cohesion changes by [?psf_amount|1].', aname + '：凝聚力变动[?psf_amount|1]。')
            add("psf_policy_govern_" + aid, "Form government: " + a["name"]["english"], "组织政府：" + a["name"]["simp_chinese"])
            add("psf_policy_govern_" + aid + "_desc", "At least one legal member must possess influence. Form a cabinet with this alliance. Its positions determine the governing political tendency; the constitution remains unchanged. Cost: 100 political power.", "至少有一个合法成员拥有影响力。由该联盟组阁，其立场决定政府的政治倾向；实际制度保持原样。花费100政治点。")
            add("psf_policy_dissolve_" + aid, "Dissolve " + a["name"]["english"], "解散：" + a["name"]["simp_chinese"])
            add("psf_policy_dissolve_" + aid + "_desc", "End this agreement and remove all its memberships. Dissolving the governing alliance creates a caretaker government and costs 8 legitimacy.", "终止该联盟并清除其全部成员关系。解散执政联盟会进入看守状态，并降低8点合法性。")
            add("psf_policy_mediate_" + aid, "Mediate disputes: " + a["name"]["english"], "调解分歧：" + a["name"]["simp_chinese"])
            add("psf_policy_mediate_" + aid + "_desc", "Add 10 alliance cohesion; 60-day cooldown. Differences in political positions still matter on future monthly updates.", "联盟凝聚力提高10点；冷却60天。立场分歧仍会影响之后每月的凝聚力变化。")
            for g in p["groups"]:
                for action, english, chinese in (("join", "Join", "加入"), ("leave", "Leave", "退出")):
                    add(f"psf_effect_{action}_{aid}_{g['id']}", '$psf_group_' + g['id'] + '_short_name$: ' + english.lower() + ' ' + aname, '$psf_group_' + g['id'] + '_short_name$' + chinese + aname)
                    key = f"psf_policy_{action}_{aid}_{g['id']}"
                    add(key, g["short_name"]["english"] + ": " + english + " " + a["name"]["english"], g["short_name"]["simp_chinese"] + "：" + chinese + a["name"]["simp_chinese"])
                    add(key + "_desc", "Change this organization's membership of this alliance. Other memberships remain independent. An illegal organization cannot join the governing cabinet.", "改变该团体在此联盟中的成员身份，其他联盟成员关系独立保留。非法组织不能加入执政内阁。")
    for r in manifest["regimes"]:
        add('psf_effect_regime_' + r['id'], 'Actual institutions become $psf_regime_' + r['id'] + '_name$; organization positions are unchanged.', '实际制度调整为$psf_regime_' + r['id'] + '_name$；团体政治立场保留。')
        key = "psf_policy_regime_" + r["id"]
        add(key, "Constitutional reform: " + r["name"]["english"], "制度改革：" + r["name"]["simp_chinese"])
        add(key + "_desc", r["description"]["english"] + "\n\nRequires 35 legitimacy, costs 150 political power and 8 legitimacy. The ruling organizations retain their own political beliefs.", r["description"]["simp_chinese"] + "\n\n需要至少35点合法性，花费150政治点并降低8点合法性。执政团体仍保留自身政治主张。")
    for scenario in manifest["scenarios"]:
        label("psf_scenario_" + scenario["id"] + "_title", scenario["title"])
        label("psf_scenario_" + scenario["id"] + "_desc", scenario["description"])
        for option in scenario["options"]:
            label("psf_scenario_" + scenario["id"] + "_" + option["id"], option["label"])
    return out


def dynamic_localization(manifest: dict) -> str:
    entries = [block("text", block("trigger", check("psf_winning_group", g["_index"])), "localization_key = psf_group_" + g["id"] + "_name") for p in profiles(manifest) for g in p["groups"]]
    return emit([block("defined_text", "name = PSFRuntimeGetWinner", entries, block("text", "localization_key = psf_no_winner"))]) + "\n"
