"""
图加载模块（Graph Layer）。

提供将数据库中的故事节点和选项映射为运行时数据对象的功能。
这是引擎的数据入口层——在每次 API 请求时从数据库加载完整的图结构。

核心类：
    - GraphBundle:   一个节点 + 其所有选项的聚合包
    - ChoiceData:    单个分支选项的运行时表示
    - GraphLoader:   从数据库加载完整图结构的加载器

设计原则：
    - 每次请求重新加载全图（当前数据量小，简单正确优先）
    - JSON 字段在加载时解析为 Python dict/list，后续逻辑不碰字符串
    - GraphBundle 存储原始字段的解析版本，不是 ORM 对象
"""

# backend/app/engine/graph.py
import json
from sqlalchemy.orm import Session
from ..models.story import StoryNode as StoryNodeModel, Choice as ChoiceModel


class GraphBundle:
    """
    单个故事节点的完整运行时数据。

    将数据库中的 StoryNode ORM 对象 + 其关联的 Choice 列表，
    打包为一个方便引擎使用的纯数据对象。

    属性说明：
        - id:       节点唯一标识（如 "A", "B", "S5"）
        - name:     中文名称（如 "荔湾广场正门"）
        - position: 环面坐标 0-200
        - node_type: main | special | sub | normal
        - time_label: 时间标签（1650年 / 1993年 / 现在 等）
        - content:  节点正文文本
        - speaker:  当前说话人 ID
        - background: 背景图资源文件名
        - cycle_variants: 循环变体内容字典（已解析 JSON）
        - color_palette: 色调主题
        - ambient: 环境音效资源文件名
        - atmosphere: 氛围效果列表（已解析 JSON）
        - sensory: 感官描述文本
        - gender_variant: 性别变体内容（已解析 JSON）
        - parent_node_id: 父节点 ID（仅子节点使用）
        - trigger_condition: 子节点触发条件表达式
        - crossing_config: 跨面道具配置（已解析 JSON）
        - warp_config: 跃迁配置（已解析 JSON）
        - shortcut_config: 捷径配置（已解析 JSON）
        - npc_item_mapping: NPC 道具映射（已解析 JSON）
        - scene_items: 场景道具（已解析 JSON）
        - choices: 该节点的所有分支选项列表（ChoiceData 对象）
    """

    def __init__(self, node: StoryNodeModel, choices: list[ChoiceModel]):
        # ── 基础信息 ─────────────────────────────────────────
        self.id = node.id
        self.name = node.name
        self.position = node.position
        self.node_type = node.node_type
        self.time_label = node.time_label

        # ── 叙事内容 ─────────────────────────────────────────
        self.content = node.content
        self.speaker = node.speaker
        self.background = node.background

        # ── JSON 字段解析（传入原始字符串，safe_json 自动处理 null） ──
        self.cycle_variants = self._safe_json(node.cycle_variants_json, {})
        self.color_palette = node.color_palette
        self.ambient = node.ambient
        self.dialogue_lines = self._safe_json(node.dialogue_lines_json, [])
        self.atmosphere = self._safe_json(node.atmosphere_json, [])
        self.sensory = node.sensory
        self.gender_variant = self._safe_json(node.gender_variant_json, None)
        self.parent_node_id = node.parent_node_id
        self.trigger_condition = node.trigger_condition
        self.crossing_config = self._safe_json(node.crossing_config_json, None)
        self.warp_config = self._safe_json(node.warp_config_json, None)
        self.shortcut_config = self._safe_json(node.shortcut_config_json, None)
        self.npc_item_mapping = self._safe_json(node.npc_item_mapping_json, None)
        self.scene_items = self._safe_json(node.scene_items_json, None)

        # ── 构建 ChoiceData 列表 ─────────────────────────────
        self.choices: list[ChoiceData] = []
        for c in choices:
            self.choices.append(ChoiceData(
                id=c.id,
                from_node_id=c.from_node_id,
                text=c.text,
                short_text=c.short_text,
                next_node_id=c.next_node_id,
                condition=c.condition,
                effects=self._safe_json(c.effects_json, []),
                priority=c.priority,
                hint=c.hint,
                is_hidden_when_locked=bool(c.is_hidden_when_locked),
                transition_text=c.transition_text,
                choice_group=c.choice_group,
            ))

    @staticmethod
    def _safe_json(raw: str | None, default):
        """
        安全 JSON 解析。

        对 None 或格式错误的 JSON 返回默认值而非抛出异常。
        确保数据库中的脏数据不会导致整个引擎崩溃。

        参数:
            raw:     原始 JSON 字符串，可能为 None
            default: 解析失败时返回的默认值
        返回:
            解析后的 Python 对象，或 default
        """
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default


class ChoiceData:
    """
    单个分支选项的运行时数据。

    对应数据库中的 Choice ORM 对象，将 JSON 字段（effects_json）
    预解析为 Python list 后供引擎使用。
    """

    def __init__(self, id, from_node_id, text, short_text, next_node_id,
                 condition, effects, priority, hint, is_hidden_when_locked, transition_text,
                 choice_group=None):
        self.id = id                              # 选项唯一标识
        self.from_node_id = from_node_id           # 来源节点 ID
        self.text = text                           # 完整显示文本
        self.short_text = short_text               # 缩略文本
        self.next_node_id = next_node_id           # 目标节点 ID
        self.condition = condition                 # 条件表达式（None = 始终可选）
        self.effects = effects                     # 效果列表（已解析 JSON）
        self.priority = priority                   # 排序优先级
        self.hint = hint                           # 鼠标悬停提示
        self.is_hidden_when_locked = is_hidden_when_locked  # 条件不满足时是否隐藏
        self.transition_text = transition_text     # 过渡旁白
        self.choice_group = choice_group           # 互斥选项组（同组只能选一个）


class GraphLoader:
    """
    图结构加载器。

    从数据库加载所有 StoryNode 和 Choice，构建为
    以 node_id 为键的 GraphBundle 字典。

    用法:
        loader = GraphLoader()
        graph = loader.load_all(db_session)
        # graph["A"] → GraphBundle for node A
        # graph["A"].choices → [ChoiceData, ...]

    性能说明:
        当前实现每次请求全量加载。在节点数 < 500 的场景下足够快。
        后续如有大量节点，可引入缓存或按需加载优化。
    """

    def load_all(self, session: Session) -> dict[str, GraphBundle]:
        """
        加载完整故事图为字典 {node_id: GraphBundle}。

        步骤:
            1. 查询所有节点和选项
            2. 按 from_node_id 对选项分组
            3. 遍历节点，为每个节点创建 GraphBundle（包含分组后的选项）

        参数:
            session: SQLAlchemy 数据库会话
        返回:
            {node_id: GraphBundle} 字典
        """
        # 全量查询所有节点和选项
        nodes = session.query(StoryNodeModel).all()
        choices = session.query(ChoiceModel).all()

        # 按 from_node_id 分组选项
        choices_by_node: dict[str, list[ChoiceModel]] = {}
        for c in choices:
            choices_by_node.setdefault(c.from_node_id, []).append(c)

        # 构建图字典
        graph: dict[str, GraphBundle] = {}
        for node in nodes:
            node_choices = choices_by_node.get(node.id, [])
            # 按优先级排序（数字小的靠前）
            node_choices.sort(key=lambda c: c.priority)
            graph[node.id] = GraphBundle(node, node_choices)

        return graph
