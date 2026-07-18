"""
特殊路由处理器。

管理莫比乌斯环上除静态分支选项以外的特殊跳转逻辑。
当前实现仅包含 K 节点（跃迁枢纽）的路由逻辑。
J 节点（捷径）的路由逻辑后续扩展。

跃迁枢纽（K 节点）的工作机制：
    1. 入口检测：当玩家在任意非 K 节点，且满足 warp_config.entry_condition
       时，引擎在可用选项中注入 "__warp_K_enter" 特殊选项
    2. 内部跳转：当玩家在 K 节点内部时，引擎根据 warp_config.warp_targets
       为每个目标节点生成 "__warp_K_exit_{target}" 选项
    3. 跃迁代价：从 K 跳转到目标时，sanity_max 属性 -1（"消耗理智上限"）
"""

# backend/app/engine/special_router.py
from .graph import GraphBundle, ChoiceData
from ..schemas.game import ChoiceResult, GameState


class SpecialRouter:
    """
    特殊路由处理器。

    在引擎的 resolve_available_choices() 中被调用，为满足条件的节点
    注入特殊路由选项（如跃迁入口、跃迁出口）。

    属性:
        evaluator: ConditionEvaluator 实例，用于检查特殊路由的触发条件
    """

    def __init__(self, evaluator):
        """
        初始化特殊路由处理器。

        参数:
            evaluator: ConditionEvaluator 实例
        """
        self.evaluator = evaluator

    # ============================================================
    # 获取可用特殊选项
    # ============================================================

    def get_available(
        self,
        bundle: GraphBundle,
        graph: dict[str, GraphBundle],
        state: GameState,
    ) -> list[ChoiceResult]:
        """
        获取当前节点可用的所有特殊路由选项。

        引擎在 resolve_available_choices() 中将此方法的返回值
        追加到常规选项列表的末尾。

        当前支持的特殊路由：
            - K 入口：在任意非 K 节点，满足条件时可进入跃迁枢纽
            - K 出口：在 K 节点内部，显示所有可跃迁的目标节点

        参数:
            bundle: 当前节点数据
            graph:  完整图字典
            state:  当前游戏状态
        返回:
            可用的特殊选项列表（ChoiceResult 类型，source 字段标记来源）
        """
        results: list[ChoiceResult] = []

        # ── K 跃迁入口 ───────────────────────────────────────
        # 条件：K 节点存在、有 warp_config、当前不在 K 内部、
        #       且满足 entry_condition 条件
        warp_node = graph.get("K")
        if warp_node and warp_node.warp_config and bundle.id != "K":
            entry_cond = warp_node.warp_config.get("entry_condition")
            if entry_cond and self.evaluator.check(entry_cond, state):
                entry_text = warp_node.warp_config.get("entry_text", "踏入跃迁裂隙")
                results.append(ChoiceResult(
                    id="__warp_K_enter",
                    text=entry_text,
                    next_node_id="K",
                    available=True,
                    source="special_warp",  # 标记为跃迁来源
                ))

        # ── K 内部跃迁出口 ───────────────────────────────────
        # 当玩家在 K 节点内部时，为 warp_targets 中每个目标节点
        # 生成一个跃迁选项
        if bundle.id == "K" and warp_node and warp_node.warp_config:
            targets = warp_node.warp_config.get("warp_targets", [])
            for target_id in targets:
                if target_id in graph:
                    target = graph[target_id]
                    results.append(ChoiceResult(
                        id=f"__warp_K_exit_{target_id}",
                        text=f"跃迁至{target.name}（{target.id}）",
                        next_node_id=target_id,
                        available=True,
                        source="special_warp",
                    ))

        return results

    # ============================================================
    # 解析特殊选项
    # ============================================================

    def resolve(
        self,
        choice_id: str,
        bundle: GraphBundle,
        graph: dict[str, GraphBundle],
        state: GameState,
    ) -> ChoiceData:
        """
        将特殊选项 ID 解析为完整的 ChoiceData 对象。

        当引擎 process_choice() 接收到一个以 "__" 开头的 choice_id 时，
        调用此方法将其解析为具体的数据结构（效果、目标节点等）。

        当前支持的特殊 choice_id：
            - __warp_K_enter:            进入跃迁枢纽 K
            - __warp_K_exit_{target_id}: 从 K 跃迁到指定目标节点

        参数:
            choice_id: 特殊选项 ID（以 "__" 开头）
            bundle:    当前节点数据
            graph:     完整图字典
            state:     当前游戏状态
        返回:
            解析后的 ChoiceData 对象
        抛出:
            ValueError: 无法识别的特殊选项 ID
        """
        # ── 进入跃迁枢纽 ─────────────────────────────────────
        if choice_id == "__warp_K_enter":
            return ChoiceData(
                id=choice_id,
                from_node_id=bundle.id,
                text="踏入跃迁裂隙",
                short_text="跃迁",
                next_node_id="K",
                condition=None,
                effects=[],
                priority=0,  # 高优先级，置于选项列表最前
                hint=None,
                is_hidden_when_locked=False,
                transition_text="灰白色的虚空在你周围展开。脚下暗红色的光脉在缓慢搏动。",
            )

        # ── 离开跃迁枢纽 ─────────────────────────────────────
        if choice_id.startswith("__warp_K_exit_"):
            target_id = choice_id.replace("__warp_K_exit_", "")
            return ChoiceData(
                id=choice_id,
                from_node_id="K",
                text=f"跃迁至{target_id}",
                short_text=f"→{target_id}",
                next_node_id=target_id,
                condition=None,
                effects=[
                    # 跃迁消耗：理智上限 -1（不可逆属性损伤）
                    {"type": "set_attr", "target": "sanity_max", "value": -1}
                ],
                priority=10,
                hint="消耗san值上限-1",
                is_hidden_when_locked=False,
                transition_text=f"暗红色的光吞没了一切。再睁开眼时——你已到达{target_id}。",
            )

        # ── 无法识别的特殊选项 ───────────────────────────────
        raise ValueError(f"Unknown special choice: {choice_id}")
