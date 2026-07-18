# backend/app/engine/condition_eval.py
import re
from app.schemas.game import GameState


class ConditionEvaluator:
    """Parse condition expression strings and evaluate them against a GameState."""

    def check(self, condition: str | None, state: GameState) -> bool:
        """null/empty string means no constraint, always returns True."""
        if condition is None or condition.strip() == "":
            return True
        return self.evaluate(condition, state)

    def evaluate(self, condition: str, state: GameState) -> bool:
        condition = condition.strip()

        # -- and --
        if condition.startswith("and:"):
            inner = condition[4:]
            parts = self._split_top_level(inner)
            return all(self.evaluate(p, state) for p in parts)

        # -- or --
        if condition.startswith("or:"):
            inner = condition[3:]
            parts = self._split_top_level(inner)
            return any(self.evaluate(p, state) for p in parts)

        # -- not --
        if condition.startswith("not:"):
            inner = condition[4:]
            return not self.evaluate(inner, state)

        # -- has_item --
        if condition.startswith("has_item:"):
            item_id = condition[9:]
            return any(item.get("id") == item_id for item in state.inventory)

        # -- has_flag --
        if condition.startswith("has_flag:"):
            flag_name = condition[9:]
            return bool(state.flags.get(flag_name))

        # -- flag:NAME=VALUE --
        m = re.match(r"^flag:([^=]+)=(.+)$", condition)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            actual = state.flags.get(flag_name)
            return str(actual) == expected

        # -- attr:NAME OP VALUE --
        m = re.match(r"^attr:(\w+)(>=|<=|>|<|==|!=)(.+)$", condition)
        if m:
            attr_name, op, raw_val = m.group(1), m.group(2), m.group(3)
            attr_val = state.player_attributes.get(attr_name, 0)
            try:
                cmp_val = int(raw_val)
            except ValueError:
                cmp_val = float(raw_val)
            if op == ">=": return attr_val >= cmp_val
            if op == "<=": return attr_val <= cmp_val
            if op == ">":  return attr_val > cmp_val
            if op == "<":  return attr_val < cmp_val
            if op == "==": return attr_val == cmp_val
            if op == "!=": return attr_val != cmp_val

        # -- cycle --
        m = re.match(r"^cycle>=(\d+)$", condition)
        if m:
            return state.cycle_count >= int(m.group(1))

        # -- half_cycle --
        m = re.match(r"^half_cycle>=(\d+)$", condition)
        if m:
            return state.half_cycle_count >= int(m.group(1))

        # -- at_node --
        m = re.match(r"^at_node:(.+)$", condition)
        if m:
            return state.current_node_id == m.group(1)

        raise ValueError(f"Unknown condition expression: {condition}")

    # ── Human-readable condition descriptions ──

    # Static maps for translating internal IDs to Chinese text.
    # Extended at runtime via update_maps() when story data is loaded.
    FLAG_NAMES: dict[str, str] = {
        "know_secret_tunnel": "知晓地下密道",
        "taoist_chant": "掌握道法口诀",
        "river_crossed": "渡过珠江",
        "timeline_mapped": "整理完时间线",
        "buddha_protection": "获得佛陀庇佑",
        "memory_synthesis": "记忆融会贯通",
        "zhang_trust": "获得张天民信任",
        "qing_exposed": "被清兵发现",
        "helped_ergou": "帮助过李二狗",
        "ghost_lady_seen": "见过白衣女子",
        "wuying_cooperated": "与吴应执合作",
        "zhang_notebook_full": "获得完整笔记",
        "knew_previous_tenant": "知晓上任租客",
        "knew_missing_worker": "发现失踪工人",
        "found_chen_shuisheng_identity": "发现陈水生身份",
        "ergou_debt_paid": "恩债已还",
        "porcelain_matched": "拼合青花瓷片",
        "heard_banxian_ramble": "听过沈半仙疯话",
        "saw_subway_looper": "发现地铁循环者",
        "heard_eyewitness": "听到目击证词",
        "saw_2014_girl": "看到2014跳楼女孩",
        "elevator_to_b1": "发现B1电梯路径",
        "drank_river_water": "喝了白鹅潭的水",
        "lake_reflection_seen": "看到湖中倒影",
        "respected_wish": "尊重了许愿",
        "heard_firefighter_story": "听到消防员故事",
        "found_rooftop_memorial": "发现天台纪念物",
        "saw_loop_boundary": "看到循环边界",
        "ghost_lady_met": "白衣女子进入房间",
        "bed_entity_encountered": "遇到床底黑影",
        "b_recorded_wall_sound": "录制了墙中之声",
        "exploring_surroundings": "在周边探索过",
        "found_lion_inscription": "发现铜狮刻字",
        "checked_rental_info": "查看过租房信息",
        "A_note_from_H_exists": "上一轮留下了纸条",
        "b_hid_under_blanket": "蒙头躲过一次",
        "yan_yan_accompany": "燕妍同行",
        "li_mingchen_story_heard": "听过李氏家族故事",
    }

    ITEM_NAMES: dict[str, str] = {
        "item_amulet": "阿六的护身符",
        "item_tunnel_map": "密道地图",
        "item_sutra": "慧觉经文残片",
        "item_beads": "菩提子念珠",
        "item_talisman": "镇魂符纸",
        "item_notebook_page": "张天民笔记(单页)",
        "item_notebook_full": "张天民笔记(完整)",
        "item_old_key": "锈蚀铜钥匙",
        "item_lion_inscription": "铜狮底座拓片",
        "item_qing_coin": "清代顺治通宝",
        "item_warning_note": "警告便签",
        "item_old_newspaper": "1993年旧报纸",
        "item_broken_mirror": "八卦铜镜碎片",
        "item_incense_stub": "香炉残香",
        "item_merit_stele_photo": "功德碑照片",
        "item_old_photo": "糖水铺老照片",
        "item_porcelain_shard": "青花瓷碎片",
        "item_old_doorplate": "第十二甫旧门牌",
        "item_black_jade": "墨玉吊坠",
        "item_graffiti_photo": "消防栓涂鸦照片",
        "item_hardhat": "施工安全帽",
        "item_river_porcelain": "明代青花碗底残片",
        "item_shamian_doorplate": "沙面法文老门牌",
        "item_river_lantern_note": "河灯感谢纸条",
        "item_scholar_diary": "陈伯陶日记",
        "item_family_tree": "陈氏家族谱系图",
        "item_rainbow_stone": "老榕树下雨花石",
        "item_loop_newspaper": "循环报纸",
        "item_joss_paper": "冥纸残片",
        "item_jade_pendant": "李氏传家玉佩",
        "item_chen_letter": "陈伯陶回信",
        "item_shrine_incense": "路边神龛香灰",
        "item_milk_tea_receipt": "便利店奶茶收据",
        "item_ferry_ticket": "珠江轮渡旧船票",
        "item_fossil_pipe": "石化烟斗",
        "item_photo_negative": "老照相馆底片",
        "item_bridge_coin": "天桥许愿硬币",
        "item_anshen_herb": "安神药包",
        "item_rooftop_tile": "天台红瓦片",
        "item_denim_rag": "一块破布",
    }

    ATTR_NAMES: dict[str, str] = {
        "sanity": "理智",
        "courage": "勇气",
        "insight": "灵感",
    }

    @classmethod
    def update_maps(cls, flags: dict[str, str] = None, items: dict[str, str] = None):
        """Extend the flag/item name maps at runtime (called after story import)."""
        if flags:
            cls.FLAG_NAMES.update(flags)
        if items:
            cls.ITEM_NAMES.update(items)

    @classmethod
    def describe_condition(cls, condition: str | None) -> str:
        """Convert a condition expression into human-readable Chinese text."""
        if condition is None or condition.strip() == "":
            return ""

        cond = condition.strip()

        # and: → "需要 A 并且 B"
        if cond.startswith("and:"):
            inner = cond[4:]
            parts = cls._split_top_level_static(inner)
            descs = [cls.describe_condition(p) for p in parts if cls.describe_condition(p)]
            return "需要" + "，并且".join(descs)

        # or: → "需要 A 或 B"
        if cond.startswith("or:"):
            inner = cond[3:]
            parts = cls._split_top_level_static(inner)
            descs = [cls.describe_condition(p) for p in parts if cls.describe_condition(p)]
            return "需要" + "，或".join(descs)

        # not: → "不能…"
        if cond.startswith("not:"):
            inner = cond[4:]
            inner_desc = cls.describe_condition(inner)
            if inner_desc.startswith("需要"):
                inner_desc = inner_desc[2:]  # strip "需要"
            return f"不能{inner_desc}"

        # has_item
        if cond.startswith("has_item:"):
            item_id = cond[9:]
            name = cls.ITEM_NAMES.get(item_id, item_id)
            return f"持有「{name}」"

        # has_flag
        if cond.startswith("has_flag:"):
            flag_name = cond[9:]
            name = cls.FLAG_NAMES.get(flag_name, flag_name)
            return f"「{name}」"

        # flag:NAME=VALUE
        m = re.match(r"^flag:([^=]+)=(.+)$", cond)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            name = cls.FLAG_NAMES.get(flag_name, flag_name)
            return f"「{name}」达到{expected}"

        # attr
        m = re.match(r"^attr:(\w+)(>=|<=|>|<|==|!=)(.+)$", cond)
        if m:
            attr_name, op, val = m.group(1), m.group(2), m.group(3)
            name = cls.ATTR_NAMES.get(attr_name, attr_name)
            op_text = {"==": "等于", "!=": "不等于", ">=": "≥", "<=": "≤", ">": ">", "<": "<"}[op]
            return f"{name}{op_text}{val}"

        # cycle
        m = re.match(r"^cycle>=(\d+)$", cond)
        if m:
            return f"完成至少{m.group(1)}次完整循环"

        # half_cycle
        m = re.match(r"^half_cycle>=(\d+)$", cond)
        if m:
            return f"完成至少{m.group(1)}次半循环"

        # at_node
        m = re.match(r"^at_node:(.+)$", cond)
        if m:
            node_id = m.group(1)
            return f"当前在节点 {node_id}"

        return condition

    @staticmethod
    def _split_top_level_static(text: str) -> list[str]:
        """Static version of _split_top_level for use in describe_condition."""
        parts = []
        depth = 0
        current: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            remaining = text[i:]
            if remaining.startswith("and:") or remaining.startswith("or:"):
                depth += 1
                prefix = "and:" if remaining.startswith("and:") else "or:"
                current.extend(prefix)
                i += len(prefix)
                continue
            if ch == ",":
                if depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    current.append(ch)
                i += 1
                continue
            current.append(ch)
            i += 1
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    def _split_top_level(self, text: str) -> list[str]:
        """Split at top-level commas, respecting and:/or: nesting.

        When and:/or: is encountered the nesting depth increases,
        so commas inside a sub-expression are not treated as split
        points for the containing expression.
        """
        parts = []
        depth = 0
        current: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            remaining = text[i:]

            # Enter sub-expression when we see and:/or:
            if remaining.startswith("and:"):
                depth += 1
                current.extend("and:")
                i += 4
                continue

            if remaining.startswith("or:"):
                depth += 1
                current.extend("or:")
                i += 3
                continue

            if ch == ",":
                if depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    # Comma inside sub-expression -- keep it as part of token
                    current.append(ch)
                i += 1
                continue

            current.append(ch)
            i += 1

        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]
