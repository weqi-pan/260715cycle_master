"""
游戏引擎核心模块（Engine Layer）。

实现完整的游戏流程控制——从接收玩家选择到返回下一帧画面的全过程。
这是后端最核心的模块，所有游戏逻辑都在这里汇聚。

处理流程（process_choice 方法，9 步）：

    ① 选项解析      — 区分常规选项和特殊路由选项
    ② 条件校验      — 确认选项的 condition 当前满足
    ③ 记录访问      — 将当前节点加入 visited_nodes
    ④ 应用效果      — 执行 effects 列表（道具/标记/属性变更）
    ⑤ 节点跳转      — 切换到目标节点
    ⑥ 循环检测      — 回到 A = cycle_count + 1
    ⑦ 持久化检查    — 查找目标节点遗留的道具/危险
    ⑧ 可用选项解析  — 评估目标节点的所有选项
    ⑨ 构建 Frame    — 组装完整帧数据返回

数据流：
    state (from client) + choice_id
        → engine.process_choice()
        → Frame (node + updated state + available choices)
"""

# backend/app/engine/engine.py
from .graph import GraphBundle, ChoiceData
from .condition_eval import ConditionEvaluator
from .special_router import SpecialRouter
from ..schemas.game import GameState, Frame, NodeData, ChoiceResult, PersistentFound


class GameEngine:
    """
    游戏引擎——莫比乌斯环状态机的执行器。

    核心职责：
        1. 处理玩家选择，推进游戏状态
        2. 管理跨循环持久化（道具遗留/发现）
        3. 检测循环完成事件
        4. 解析并返回下一帧的完整数据

    属性:
        evaluator:      ConditionEvaluator 实例，用于条件求值
        special_router: SpecialRouter 实例，用于特殊路由（跃迁等）

    用法:
        engine = GameEngine()
        frame = engine.process_choice(graph, node_id, choice_id, state)

    设计理念：
        - 状态由前端持有（Stateful API），引擎无状态
        - 每次 process_choice 是纯函数：输入 state + choice → 输出 Frame
        - 条件和效果在数据层用字符串定义，引擎只负责求值和执行
    """

    def __init__(self):
        """初始化引擎，创建条件求值器和特殊路由器。"""
        self.evaluator = ConditionEvaluator()
        self.special_router = SpecialRouter(self.evaluator)

    # ============================================================
    # 核心入口：process_choice
    # ============================================================

    def process_choice(
        self,
        graph: dict[str, GraphBundle],
        node_id: str,
        choice_id: str,
        state: GameState,
        save_id: str | None = None,
    ) -> Frame:
        """
        处理玩家的一次选择，返回下一帧完整画面。

        这是引擎的唯一公共入口。9 步处理流水线：

        ① 选项解析   — 区分常规选项（查 bundle.choices）vs 特殊路由（以 "__" 开头）
        ② 条件校验   — 如果有 condition 表达式，必须在当前 state 下满足
        ③ 记录访问   — 首次访问的节点追加到 visited_nodes
        ④ 应用效果   — 遍历执行 effects 列表中的每一条效果
        ⑤ 节点跳转   — state.current_node_id 更新为 choice.next_node_id
        ⑥ 循环检测   — 如果跳转到 A 且有访问记录 → cycle_count + 1
        ⑦ 持久化检查 — 查找新节点是否有遗留道具、跨面道具、遗留危险
        ⑧ 可用选项   — 解析新节点的全部可用选项（常规 + 特殊路由）
        ⑨ 构建 Frame — 组装所有数据为 Frame 对象返回

        参数:
            graph:    完整图字典 {node_id: GraphBundle}
            node_id:  玩家当前所在节点 ID
            choice_id: 玩家选择的选项 ID（普通选项或 "__" 前缀的特殊路由）
            state:    当前游戏状态（前端持有并传入）
            save_id:  (预留) 存档 ID，用于持久化节点状态的读写
        返回:
            Frame 对象（下一帧的完整画面数据）
        抛出:
            ValueError: 选项不存在或条件不满足
        """
        bundle = graph[node_id]

        # ① 选项解析 — 区分常规选项与特殊路由选项
        if choice_id.startswith("__"):
            # 特殊路由：跃迁入口/出口等，由 SpecialRouter 解析
            choice = self.special_router.resolve(choice_id, bundle, graph, state)
        else:
            # 常规选项：从当前节点的 choices 列表中查找
            choice = self._find_choice(bundle, choice_id)

        # ② 条件校验 — 确保选项的 condition 在当前的 GameState 下满足
        if choice.condition and not self.evaluator.evaluate(choice.condition, state):
            raise ValueError(f"Condition not met: {choice.condition}")

        # ③ 记录已访问节点 — 用于循环检测和 visited_nodes 追踪
        if node_id not in state.visited_nodes:
            state.visited_nodes.append(node_id)

        # ④ 应用效果 — 执行 effects 列表中的变更
        #   同时收集场景特效（notify/shake/flash）到 scene_effects
        #   互斥选项组：如果选项有 group 字段，自动锁定同组其他选项
        scene_effects: list[dict] = []
        all_effects = list(choice.effects)
        if getattr(choice, 'choice_group', None):
            all_effects.append({"type": "set_flag", "target": f"_group_{choice.choice_group}_chosen", "value": True})
        for effect in all_effects:
            if effect.get("type") in ("notify", "shake", "flash"):
                scene_effects.append(effect)
        self._apply_effects(all_effects, state, node_id)

        # ⑤ 节点跳转 — 将玩家移动到选项指向的目标节点
        next_bundle = graph[choice.next_node_id]
        state.current_node_id = next_bundle.id

        # ⑥ 循环检测 — 回到起点 A = 一次完整循环完成
        cycle_event = None
        if next_bundle.id == "A" and len(state.visited_nodes) > 0:
            state.cycle_count += 1          # 完整循环计数 +1
            state.visited_nodes = []        # 清空本轮访问记录（开始新一轮）
            cycle_event = {
                "type": "cycle_complete",
                "cycle_count": state.cycle_count,
                "half_cycle_count": state.half_cycle_count,
            }

        # ⑦ 持久化检查 — 查找新节点是否有遗留道具、跨面道具、危险
        persistent = PersistentFound()

        # 查找目标节点的直接遗留状态
        node_state = state.persistent_nodes.get(next_bundle.id, {})
        persistent.items = node_state.get("items", [])

        # A↔E 跨面道具：A 和 E 位于莫比乌斯环的扭转面，部分道具可跨面共享
        if next_bundle.id in ("A", "E"):
            mirror_id = "E" if next_bundle.id == "A" else "A"
            mirror_state = state.persistent_nodes.get(mirror_id, {})
            mirror_items = mirror_state.get("items", [])
            # 仅标记了 cross_surface=True 的道具可以跨面出现
            persistent.cross_surface_items = [
                i for i in mirror_items if i.get("cross_surface")
            ]

        persistent.dangers = node_state.get("dangers", [])

        # ⑧ 解析可用选项 — 评估新节点的所有选项（静态 + 特殊路由）
        available = self.resolve_available_choices(graph, next_bundle.id, state)

        # ⑨ 构建 Frame — 组装完整帧数据
        return Frame(
            node=NodeData(
                id=next_bundle.id,
                name=next_bundle.name,
                node_type=next_bundle.node_type,
                position=next_bundle.position,
                time_label=next_bundle.time_label,
                # content 需要解析 cycle_variants 和 {{变量}} 模板
                content=self._resolve_content(next_bundle, state),
                speaker=next_bundle.speaker,
                background=next_bundle.background,
                ambient=next_bundle.ambient,
                dialogue_lines=next_bundle.dialogue_lines,
            ),
            state=state,
            available_choices=available,
            persistent_found=persistent,
            cycle_event=cycle_event,
            transition_text=choice.transition_text,
            scene_effects=scene_effects,
        )

    # ============================================================
    # 可用选项解析
    # ============================================================

    def resolve_available_choices(
        self, graph: dict[str, GraphBundle], node_id: str, state: GameState
    ) -> list[ChoiceResult]:
        """
        解析指定节点在当前状态下所有可用的选项。

        包括：
            1. 静态分支选项（来自数据库 choices 表）
               - 评估每个选项的 condition，不可用的跳过
            2. 特殊路由选项（来自 SpecialRouter）
               - 如 K 跃迁入口/出口

        排序规则：
            特殊选项优先于静态选项，同类内部按 priority 升序。

        参数:
            graph:   完整图字典
            node_id: 目标节点 ID
            state:   当前游戏状态
        返回:
            可用的 ChoiceResult 列表
        """
        bundle = graph[node_id]
        results: list[ChoiceResult] = []

        # ── 静态分支选项 ─────────────────────────────────────
        for c in bundle.choices:
            available = self.evaluator.check(c.condition, state)
            if not available:
                continue  # 条件不满足的选项不显示
            # 互斥选项组：如果同组已有选项被选中，则隐藏
            if c.choice_group and state.flags.get(f"_group_{c.choice_group}_chosen"):
                continue
            results.append(ChoiceResult(
                id=c.id,
                text=c.text,
                short_text=c.short_text,
                next_node_id=c.next_node_id,
                available=True,
                reason=None,
                source="static",
            ))

        # ── 注入特殊路由选项 ─────────────────────────────────
        specials = self.special_router.get_available(bundle, graph, state)
        results.extend(specials)

        # ── 排序：特殊选项 > 静态选项，同 source 内部按 priority ──
        results.sort(key=lambda r: (
            0 if r.source != "static" else 1,  # 特殊选项排前面
            next((c.priority for c in bundle.choices if c.id == r.id), 99)
        ))
        return results

    # ============================================================
    # 内部辅助方法
    # ============================================================

    def _find_choice(self, bundle: GraphBundle, choice_id: str) -> ChoiceData:
        """
        在节点的选项列表中查找指定 ID 的选项。

        参数:
            bundle:    节点数据
            choice_id: 选项 ID
        返回:
            ChoiceData 对象
        抛出:
            ValueError: 选项不存在
        """
        for c in bundle.choices:
            if c.id == choice_id:
                return c
        raise ValueError(f"Choice '{choice_id}' not found in node '{bundle.id}'")

    def _apply_effects(self, effects: list[dict], state: GameState, node_id: str):
        """
        批量执行效果列表。

        遍历 effects 中的每条效果，根据 type 分发到对应处理逻辑。
        对 GameState 的修改是就地（in-place）的。

        支持的效果类型：
            - add_item:     向背包添加道具
            - remove_item:  从背包移除指定道具
            - set_flag:     设置标记值
            - remove_flag:  移除标记
            - heal:         属性恢复（上限 100）
            - damage:       属性损伤（下限 0）
            - set_attr:     属性直接赋值
            - leave_item:   在当前节点遗留道具（跨循环持久化）
            - leave_danger: 在当前节点遗留危险（跨循环持久化）
            - notify/shake/flash: 场景特效（仅前端渲染，不改变状态）

        参数:
            effects:  效果列表
            state:    当前游戏状态（就地修改）
            node_id:  当前节点 ID（用于 leave_item / leave_danger）
        """
        for effect in effects:
            etype = effect.get("type")     # 效果类型
            target = effect.get("target", "")  # 效果目标
            value = effect.get("value")    # 效果值

            if etype == "add_item":
                # 向背包添加道具（name 字段用于 UI 显示，映射为中文名）
                item_name = ConditionEvaluator.ITEM_NAMES.get(target, target)
                state.inventory.append({"id": target, "name": item_name, "count": value})

            elif etype == "remove_item":
                # 从背包移除指定 ID 的道具
                state.inventory = [i for i in state.inventory if i.get("id") != target]

            elif etype == "set_flag":
                # 设置标记（任意值，通常为 bool）
                state.flags[target] = value

            elif etype == "remove_flag":
                # 移除标记（pop 不存在的 key 不报错）
                state.flags.pop(target, None)

            elif etype == "heal":
                # 恢复属性值，不超过上限 100
                attr = state.player_attributes.get(target, 0)
                state.player_attributes[target] = min(attr + value, 100)

            elif etype == "damage":
                # 属性损伤，不低于下限 0
                attr = state.player_attributes.get(target, 100)
                state.player_attributes[target] = max(attr - value, 0)

            elif etype == "set_attr":
                # 属性直接赋值
                state.player_attributes[target] = value

            elif etype == "leave_item":
                # 在当前节点遗留道具（下次访问该节点时可发现）
                pd = state.persistent_nodes.setdefault(
                    node_id, {"items": [], "dangers": []}
                )
                pd["items"].append({"id": target, "name": value or target})

            elif etype == "leave_danger":
                # 在当前节点遗留危险（下次访问该节点时触发危险剧情）
                pd = state.persistent_nodes.setdefault(
                    node_id, {"items": [], "dangers": []}
                )
                pd["dangers"].append({"id": target, "name": value or target})

            elif etype in ("notify", "shake", "flash"):
                # 场景特效：不改变状态，仅在 scene_effects 列表中传递给前端
                pass

    def _resolve_content(self, bundle: GraphBundle, state: GameState) -> str:
        """
        解析节点的实际显示内容。

        处理两种模板机制：
            1. cycle_variants（循环变体）：
               根据当前循环次数选择不同的文本内容。
               支持精确匹配 "cycle_3" 和范围匹配 "cycle_5+"（≥5 次后使用）

            2. {{变量}} 模板替换：
               在正文中内嵌的占位符，运行时替换为实际值。
               支持的变量：
                   {{cycle_count}}       → 当前循环次数
                   {{half_cycle_count}}  → 半循环次数
                   {{attr:sanity}}       → 当前理智值

        参数:
            bundle: 节点数据
            state:  当前游戏状态
        返回:
            解析后的最终文本内容
        """
        variants = bundle.cycle_variants or {}
        content = bundle.content

        # ── 第一步：循环变体匹配 ─────────────────────────────
        # 优先精确匹配当前循环次数（如 cycle_2）
        for key in [f"cycle_{state.cycle_count}", f"cycle_{state.cycle_count}+"]:
            if key in variants and variants[key]:
                content = variants[key]
                break
        else:
            # 其次匹配范围变体（如 cycle_5+ 匹配 cycle_count ≥ 5）
            for key in sorted(variants.keys()):
                if key.endswith("+") and state.cycle_count >= int(
                    key.replace("cycle_", "").replace("+", "")
                ):
                    if variants[key]:
                        content = variants[key]

        # ── 第二步：{{变量}} 模板替换 ────────────────────────
        content = content.replace("{{cycle_count}}", str(state.cycle_count))
        content = content.replace("{{half_cycle_count}}", str(state.half_cycle_count))
        for attr_name, attr_val in state.player_attributes.items():
            content = content.replace(f"{{{{attr:{attr_name}}}}}", str(attr_val))

        return content
