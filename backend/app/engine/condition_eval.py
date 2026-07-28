"""
条件表达式求值器。

解析并执行故事剧本中使用的条件表达式字符串，判断玩家是否满足某个选项的解锁条件。

支持的表达式语法：

    【逻辑组合】
        and:A,B,C           — 所有子条件都满足
        or:A,B,C            — 任一子条件满足
        not:condition       — 条件取反

    【道具与标记】
        has_item:item_id    — 持有指定道具
        has_flag:flag_name  — 指定标记为真
        flag:NAME=VALUE     — 标记等于指定值

    【属性比较】
        attr:NAME>=VALUE    — 属性比较（支持 >= <= > < == !=）

    【循环/位置】
        cycle>=N            — 循环次数 ≥ N
        half_cycle>=N       — 半循环次数 ≥ N
        at_node:NODE_ID     — 当前在指定节点

    嵌套规则：
    and:/or: 内部用逗号分隔子条件；嵌套逻辑组必须写在括号中，
    例如 or:A,(and:B,C),(and:D,E)，避免前缀表达式产生歧义。
"""

# backend/app/engine/condition_eval.py
import operator
import re

from app.schemas.game import GameState
from app.schemas.story_v3 import (
    AllCondition,
    AnyCondition,
    AtNodeCondition,
    AttributeCompareCondition,
    ConditionV3,
    CounterCompareCondition,
    FlagEqualsCondition,
    ItemCondition,
    NotCondition,
)
from app.domain.items import ITEM_NAMES as CANONICAL_ITEM_NAMES


_COMPARE_OPERATORS = {
    "lt": operator.lt,
    "lte": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "gte": operator.ge,
    "gt": operator.gt,
}


class ConditionEvaluator:
    """
    条件表达式求值器。

    核心职责：
        1. 解析条件表达式字符串
        2. 根据当前 GameState 求值，返回 True/False
        3. 提供 describe_condition() 将表达式翻译为人类可读的中文描述

    用法:
        evaluator = ConditionEvaluator()
        ok = evaluator.check("has_item:item_amulet", state)
        desc = evaluator.describe_condition("and:has_item:item_old_key,has_flag:know_secret_tunnel")
        # → "需要持有「锈蚀铜钥匙」，并且「知晓地下密道」"

    设计决策：
        - 使用前缀语法（如 "has_item:"）而非 JSON 结构，使编辑器中的条件字段更简洁
        - 条件表达式中不直接写物品/标记的中文名，而是引用 ID，
          由 describe_condition() 通过静态映射表翻译为中文供 UI 显示
    """

    # ============================================================
    # 条件求值（evaluate / check）
    # ============================================================

    def check(self, condition: ConditionV3 | None, state: GameState) -> bool:
        """Recursively evaluate a typed v3 condition against runtime state."""

        if condition is None:
            return True
        if isinstance(condition, str):
            # Temporary compatibility for v2 callers until the runtime cutover.
            if condition.strip() == "":
                return True
            return self.evaluate(condition, state)
        if isinstance(condition, AttributeCompareCondition):
            return _COMPARE_OPERATORS[condition.operator](
                state.player_attributes[condition.attribute],
                condition.value,
            )
        if isinstance(condition, FlagEqualsCondition):
            actual = state.flags.get(condition.flag)
            return (
                type(actual) is type(condition.value)
                and actual == condition.value
            )
        if isinstance(condition, ItemCondition):
            present = any(
                item.get("id") == condition.item_id
                and item.get("count", item.get("quantity", 1)) > 0
                for item in state.inventory
            )
            return present is condition.present
        if isinstance(condition, CounterCompareCondition):
            counters = {
                "completed_cycles": state.cycle_count,
                "current_cycle": state.cycle_count + 1,
                "half_cycles": state.half_cycle_count,
            }
            return _COMPARE_OPERATORS[condition.operator](
                counters[condition.counter],
                condition.value,
            )
        if isinstance(condition, AtNodeCondition):
            return state.current_node_id == condition.node_id
        if isinstance(condition, AllCondition):
            return all(self.check(item, state) for item in condition.conditions)
        if isinstance(condition, AnyCondition):
            return any(self.check(item, state) for item in condition.conditions)
        if isinstance(condition, NotCondition):
            return not self.check(condition.condition, state)
        raise TypeError(f"Unsupported v3 condition: {type(condition).__name__}")

    def evaluate(self, condition: str, state: GameState) -> bool:
        """
        递归求值条件表达式。

        按照表达式前缀分发给对应的处理逻辑：
            and:/or: → 逻辑组合（递归子条件）
            not:     → 取反
            has_item:/has_flag:/flag: → 道具和标记检查
            attr:    → 属性比较
            cycle>= / half_cycle>=    → 循环次数检查
            at_node: → 当前位置检查

        参数:
            condition: 条件表达式字符串（不含前后空白）
            state:     当前游戏状态
        返回:
            条件是否满足
        抛出:
            ValueError: 无法识别的条件表达式
        """
        condition = self._strip_outer_group(condition.strip())

        # ── and: 逻辑与 ──────────────────────────────────────
        # 格式: and:子条件1,子条件2,子条件3
        # 所有子条件都满足才返回 True
        if condition.startswith("and:"):
            inner = condition[4:]  # 去掉 "and:" 前缀
            parts = self._split_top_level(inner)
            return all(self.evaluate(p, state) for p in parts)

        # ── or: 逻辑或 ───────────────────────────────────────
        # 格式: or:子条件1,子条件2,子条件3
        # 任一子条件满足即返回 True
        if condition.startswith("or:"):
            inner = condition[3:]  # 去掉 "or:" 前缀
            parts = self._split_top_level(inner)
            return any(self.evaluate(p, state) for p in parts)

        # ── not: 逻辑非 ──────────────────────────────────────
        if condition.startswith("not:"):
            inner = condition[4:]
            return not self.evaluate(inner, state)

        # ── has_item: 持有道具 ────────────────────────────────
        # 格式: has_item:item_amulet
        # 检查背包中是否存在指定道具 ID
        if condition.startswith("has_item:"):
            item_id = condition[9:]
            return any(item.get("id") == item_id for item in state.inventory)

        # ── has_flag: 标记为真 ────────────────────────────────
        # 格式: has_flag:know_secret_tunnel
        # 检查指定标记是否为真值
        if condition.startswith("has_flag:"):
            flag_name = condition[9:]
            return bool(state.flags.get(flag_name))

        # ── flag:NAME=VALUE 标记等于指定值 ────────────────────
        # 格式: flag:trust_level=5
        m = re.match(r"^flag:([^=]+)=(.+)$", condition)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            actual = state.flags.get(flag_name)
            return str(actual) == expected

        # ── attr:NAME OP VALUE 属性比较 ──────────────────────
        # 格式: attr:sanity>=50 或 attr:courage<3
        # 支持 >= <= > < == != 六种比较运算符
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

        # ── cycle/half_cycle 数值比较 ────────────────────────
        # 支持 v1 的 cycle>=3，也支持 v2 的完整比较运算符。
        m = re.match(r"^(cycle|half_cycle)(>=|<=|>|<|==|!=)(\d+)$", condition)
        if m:
            counter_name, op, raw_value = m.groups()
            actual = (
                state.cycle_count
                if counter_name == "cycle"
                else state.half_cycle_count
            )
            expected = int(raw_value)
            if op == ">=": return actual >= expected
            if op == "<=": return actual <= expected
            if op == ">": return actual > expected
            if op == "<": return actual < expected
            if op == "==": return actual == expected
            if op == "!=": return actual != expected

        # ── at_node:NODE_ID 当前位置检查 ──────────────────────
        # 格式: at_node:E
        # 检查玩家当前是否在指定节点
        m = re.match(r"^at_node:(.+)$", condition)
        if m:
            return state.current_node_id == m.group(1)

        # ── 无法识别的表达式 ─────────────────────────────────
        raise ValueError(f"Unknown condition expression: {condition}")

    # ============================================================
    # 人类可读中文描述（describe_condition）
    # ============================================================

    # ── 标记名称映射表 ───────────────────────────────────────
    # Key: 数据库中使用的英文 ID
    # Value: UI 中显示的中文描述
    # 运行时可通过 update_maps() 扩展
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

    # ── 道具名称映射表 ───────────────────────────────────────
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
    ITEM_NAMES = dict(CANONICAL_ITEM_NAMES)

    # ── 属性名称映射表 ───────────────────────────────────────
    ATTR_NAMES: dict[str, str] = {
        "sanity": "理智",
        "courage": "勇气",
        "insight": "灵感",
    }

    @classmethod
    def update_maps(cls, flags: dict[str, str] = None, items: dict[str, str] = None):
        """
        运行时扩展标记/道具名称映射。

        当故事数据（story_data）导入后，如果定义了新的标记或道具，
        调用此方法将其中文名称注册到求值器，确保 describe_condition()
        可以正确翻译。

        参数:
            flags: 新增的标记 ID → 中文名称映射
            items: 新增的道具 ID → 中文名称映射
        """
        if flags:
            cls.FLAG_NAMES.update(flags)
        if items:
            cls.ITEM_NAMES.update(items)

    @classmethod
    def describe_condition(cls, condition: str | None) -> str:
        """
        将条件表达式翻译为人类可读的中文描述。

        用于编辑器 UI 和游戏中选择项的附加说明。

        示例:
            "has_item:item_old_key" → "持有「锈蚀铜钥匙」"
            "and:has_flag:zhang_trust,attr:courage>=5" → "需要「获得张天民信任」，并且勇气≥5"
            "not:has_item:item_talisman" → "不能持有「镇魂符纸」"

        参数:
            condition: 条件表达式字符串（可为 None）
        返回:
            中文描述字符串，空条件返回 ""
        """
        if condition is None or condition.strip() == "":
            return ""

        cond = cls._strip_outer_group(condition.strip())

        # ── and: 逻辑与 → "需要A，并且B，并且C" ──────────────
        if cond.startswith("and:"):
            inner = cond[4:]
            parts = cls._split_top_level_static(inner)
            descs = [cls.describe_condition(p) for p in parts if cls.describe_condition(p)]
            return "需要" + "，并且".join(descs)

        # ── or: 逻辑或 → "需要A，或B，或C" ────────────────────
        if cond.startswith("or:"):
            inner = cond[3:]
            parts = cls._split_top_level_static(inner)
            descs = [cls.describe_condition(p) for p in parts if cls.describe_condition(p)]
            return "需要" + "，或".join(descs)

        # ── not: 逻辑非 → "不能…" ────────────────────────────
        if cond.startswith("not:"):
            inner = cond[4:]
            inner_desc = cls.describe_condition(inner)
            if inner_desc.startswith("需要"):
                inner_desc = inner_desc[2:]  # 去掉 "需要" 前缀使语句更流畅
            return f"不能{inner_desc}"

        # ── has_item → "持有「道具名」" ──────────────────────
        if cond.startswith("has_item:"):
            item_id = cond[9:]
            name = cls.ITEM_NAMES.get(item_id, item_id)
            return f"持有「{name}」"

        # ── has_flag → "「标记名」" ───────────────────────────
        if cond.startswith("has_flag:"):
            flag_name = cond[9:]
            name = cls.FLAG_NAMES.get(flag_name, flag_name)
            return f"「{name}」"

        # ── flag:NAME=VALUE → "「标记名」达到VALUE" ────────────
        m = re.match(r"^flag:([^=]+)=(.+)$", cond)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            name = cls.FLAG_NAMES.get(flag_name, flag_name)
            return f"「{name}」达到{expected}"

        # ── attr → "属性名≥/≤/==/!=值" ──────────────────────
        m = re.match(r"^attr:(\w+)(>=|<=|>|<|==|!=)(.+)$", cond)
        if m:
            attr_name, op, val = m.group(1), m.group(2), m.group(3)
            name = cls.ATTR_NAMES.get(attr_name, attr_name)
            op_text = {"==": "等于", "!=": "不等于", ">=": "≥", "<=": "≤", ">": ">", "<": "<"}[op]
            return f"{name}{op_text}{val}"

        # ── cycle>=N → "完成至少N次完整循环" ─────────────────
        m = re.match(r"^cycle>=(\d+)$", cond)
        if m:
            return f"完成至少{m.group(1)}次完整循环"

        # ── half_cycle>=N → "完成至少N次半循环" ───────────────
        m = re.match(r"^half_cycle>=(\d+)$", cond)
        if m:
            return f"完成至少{m.group(1)}次半循环"

        # ── at_node → "当前在节点 X" ─────────────────────────
        m = re.match(r"^at_node:(.+)$", cond)
        if m:
            node_id = m.group(1)
            return f"当前在节点 {node_id}"

        # 未识别的表达式原样返回
        return condition

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _split_top_level_static(text: str) -> list[str]:
        """
        静态版本的顶层逗号分割（供 describe_condition 使用）。

        与 _split_top_level 逻辑相同，但因为 describe_condition 是
        @classmethod，需要静态版本以避免实例方法绑定问题。

        参数:
            text: 待分割的表达式字符串
        返回:
            分割后的子表达式列表（去除空白和空串）
        """
        parts = []
        depth = 0
        current: list[str] = []
        for ch in text:
            if ch == "(":
                depth += 1
                current.append(ch)
                continue
            if ch == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError(f"Unbalanced condition group: {text}")
                current.append(ch)
                continue
            if ch == ",":
                if depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    current.append(ch)
                continue
            current.append(ch)
        if depth != 0:
            raise ValueError(f"Unbalanced condition group: {text}")
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    def _split_top_level(self, text: str) -> list[str]:
        """
        顶层逗号分割（实例方法）。

        在 and:/or: 表达式中，用逗号分隔子条件。但子条件内部的逗号
        （在嵌套的 and:/or: 中）不应被当作分隔符。

        算法：维护括号深度计数器。
            - 遇到左括号 → 深度 +1；右括号 → 深度 -1
            - 遇到逗号 → 深度 0 时分隔，深度 > 0 时保留
            - 括号不配对时立即拒绝表达式

        示例:
            text = "has_item:A,(and:has_flag:B,has_item:C)"
            分割结果 = ["has_item:A", "(and:has_flag:B,has_item:C)"]

        参数:
            text: 待分割的表达式字符串
        返回:
            分割后的子表达式列表（去除空白和空串）
        """
        return self._split_top_level_static(text)

    @staticmethod
    def _strip_outer_group(text: str) -> str:
        """仅当一对括号包住完整表达式时移除外层括号。"""
        while text.startswith("(") and text.endswith(")"):
            depth = 0
            encloses_all = True
            for index, ch in enumerate(text):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and index != len(text) - 1:
                        encloses_all = False
                        break
                    if depth < 0:
                        raise ValueError(f"Unbalanced condition group: {text}")
            if depth != 0:
                raise ValueError(f"Unbalanced condition group: {text}")
            if not encloses_all:
                break
            text = text[1:-1].strip()
        return text
