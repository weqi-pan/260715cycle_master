"""
故事数据模型模块。

定义与故事剧本直接相关的两张核心表：
    - StoryNode: 故事节点（主节点 A-H、特殊节点 J/K、子节点 S1-S20）
    - Choice: 分支选项（从某个节点指向下一个节点的可选路径）

这两个模型是整个图引擎的数据基础。引擎加载时将它们映射为
GraphBundle / ChoiceData 对象，供条件求值和状态推进使用。
"""

# backend/app/models/story.py
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base


class StoryNode(Base):
    """
    故事节点 ORM 模型。

    代表莫比乌斯环上的一个叙事位置。每个节点包含：
        - 基础信息：id（A-H/J-K/S1-S20）、name、position（0-200 环面坐标）
        - 叙事内容：content（正文文本）、speaker（当前说话人）
        - 视觉/音效配置：background、color_palette、ambient、atmosphere
        - 跨循环持久化配置：crossing_config（跨面道具）、warp_config（跃迁配置）
        - 子节点关系：parent_node_id（子节点指向其父主节点）

    节点类型（node_type）：
        - "main":     主节点 A-H，构成环形骨架
        - "special":  特殊节点 J（捷径）、K（跃迁枢纽）
        - "sub":      子节点 S1-S20，散落在主节点之间
        - "normal":   普通节点（预留）
    """

    __tablename__ = "story_nodes"

    # ── 主键 ─────────────────────────────────────────────────
    id = Column(String, primary_key=True)  # 节点唯一标识，如 "A", "B", "S1"

    # ── 基础信息 ─────────────────────────────────────────────
    name = Column(String, nullable=False)  # 中文名称，如 "荔湾广场正门"
    position = Column(Float, nullable=False)  # 环面坐标 0-200
    node_type = Column(String, nullable=False, default="normal")  # main | special | sub | normal
    time_label = Column(String, nullable=True)  # 时间标签（1650年 / 1993年 / 现在 等）

    # ── 叙事内容 ─────────────────────────────────────────────
    content = Column(Text, nullable=False)  # 节点正文（支持 {{变量}} 模板语法）
    speaker = Column(String, nullable=True)  # 当前说话人 ID
    background = Column(String, nullable=True)  # 背景图资源文件名
    cycle_variants_json = Column(Text, nullable=True, default="{}")  # 循环变体内容 JSON
    gender_variant_json = Column(Text, nullable=True)  # 性别变体内容 JSON

    # ── 视觉/氛围 ─────────────────────────────────────────────
    color_palette = Column(String, nullable=True)  # 色调主题名
    ambient = Column(String, nullable=True)  # 环境音效资源文件名
    dialogue_lines_json = Column(Text, nullable=True)  # 角色对话行 JSON [{speaker, text}]
    atmosphere_json = Column(Text, nullable=True, default="[]")  # 氛围效果列表 JSON
    sensory = Column(Text, nullable=True)  # 感官描述文本

    # ── 拓扑/层级关系 ─────────────────────────────────────────
    parent_node_id = Column(String, nullable=True)  # 子节点指向父节点的 id（仅子节点使用）
    trigger_condition = Column(String, nullable=True)  # 子节点触发的条件表达式

    # ── 特殊配置 ─────────────────────────────────────────────
    crossing_config_json = Column(Text, nullable=True)  # 跨面道具配置（用于 A↔E 莫比乌斯扭转面）
    warp_config_json = Column(Text, nullable=True)  # 跃迁配置（用于 K 节点）
    shortcut_config_json = Column(Text, nullable=True)  # 捷径配置（用于 J 节点）

    # ── NPC/道具/场景 ─────────────────────────────────────────
    npc_item_mapping_json = Column(Text, nullable=True)  # NPC 可赠予/交易道具映射 JSON
    scene_items_json = Column(Text, nullable=True)  # 场景中可拾取的道具 JSON

    # ── ORM 关系 ─────────────────────────────────────────────
    # 一对多：一个节点可以有多个分支选项
    choices = relationship(
        "Choice",
        back_populates="from_node",
        foreign_keys="Choice.from_node_id",
    )


class Choice(Base):
    """
    分支选项 ORM 模型。

    代表从某个节点出发的一条可选路径。每条 choice 包含：
        - 基础信息：id、from_node_id（来源节点）、next_node_id（目标节点）
        - 显示文本：text（完整文本）、short_text（缩略文本/按钮文字）
        - 条件控制：condition（条件表达式字符串）
        - 效果：effects_json（选中后触发的效果列表）
        - 显示控制：priority（排序优先级）、hint（提示文字）、is_hidden_when_locked

    后端引擎在加载节点时自动加载其所有 choices，并在每次请求时
    根据当前 GameState 评估 condition 是否满足，过滤出可用选项。
    """

    __tablename__ = "choices"

    # ── 主键 ─────────────────────────────────────────────────
    id = Column(String, primary_key=True)  # 选项唯一标识

    # ── 拓扑关系 ─────────────────────────────────────────────
    from_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)  # 来源节点 id
    next_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)  # 目标节点 id

    # ── 显示文本 ─────────────────────────────────────────────
    text = Column(String, nullable=False)  # 完整选项文本，如 "推开沉重的铁门，走进黑暗"
    short_text = Column(String, nullable=True)  # 缩略文本，用于按钮或快捷显示

    # ── 条件与效果 ───────────────────────────────────────────
    condition = Column(String, nullable=True)  # 条件表达式，为空表示始终可选
    effects_json = Column(Text, nullable=False, default="[]")  # 效果列表 JSON

    # ── 显示控制 ─────────────────────────────────────────────
    priority = Column(Integer, default=99)  # 排序优先级（数字越小越靠前）
    hint = Column(String, nullable=True)  # 鼠标悬停提示
    is_hidden_when_locked = Column(Integer, default=0)  # 条件不满足时是否完全隐藏（0=否, 1=是）
    transition_text = Column(Text, nullable=True)  # 选项选中后的过渡旁白
    choice_group = Column(String, nullable=True)  # 互斥选项组名（同组选项互斥）

    # ── ORM 关系 ─────────────────────────────────────────────
    from_node = relationship(
        "StoryNode",
        back_populates="choices",
        foreign_keys=[from_node_id],
    )

    # ── 复合索引 ─────────────────────────────────────────────
    # 加速 "从某个节点查询其所有选项" 的频繁操作
    __table_args__ = (
        Index("idx_choices_from", "from_node_id"),
    )
