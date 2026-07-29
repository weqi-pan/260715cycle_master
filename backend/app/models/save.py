"""
存档持久化模型模块。

定义与玩家进度持久化相关的两张表：
    - Save: 存档主表（玩家在某时刻的完整游戏状态快照）
    - NodePersistentState: 节点级持久化状态（跨循环遗留的道具和危险）

核心设计理念——跨循环持久化：
    循环是无限的，但玩家的行为具有"记忆效应"：
    - 在第一轮循环中在节点 A 留下的线索纸条，第二轮回到 A 时可以被找到
    - 在第一轮循环中未解决的床底黑影，第二轮回到同一节点时它还在那里
    - 莫比乌斯扭转面 A↔E 之间的部分道具可以跨面共享
"""

# backend/app/models/save.py
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, Index, UniqueConstraint
from ..database import Base


def generate_uuid():
    """生成全局唯一的存档标识符。"""
    return str(uuid.uuid4())


class Save(Base):
    """
    存档 ORM 模型。

    每次手动/自动存档时，将当前 GameState 的完整快照序列化为 JSON
    存入对应字段。读取存档时反序列化还原为 GameState 对象。

    字段说明：
        - id: 存档唯一 ID（UUID）
        - save_name: 用户可见的存档名称（如 "自动存档-第3轮"）
        - created_at / updated_at: ISO 8601 时间戳
        - current_node_id: 当前所在节点 ID
        - cycle_count: 已完成完整循环次数（回到 A 的次数）
        - half_cycle_count: 半循环计数（到达 E 的次数）
        - inventory_json: 背包道具 JSON
        - flags_json: 全局标记 JSON（如 "know_secret_tunnel": true）
        - visited_nodes_json: 本轮已访问节点列表 JSON
        - player_attributes_json: 玩家属性 JSON（理智/勇气/灵感）
        - endings_reached_json: 已达成的结局列表 JSON
    """

    __tablename__ = "saves"

    # ── 主键 ─────────────────────────────────────────────────
    id = Column(String, primary_key=True, default=generate_uuid)

    # ── 元信息 ───────────────────────────────────────────────
    save_name = Column(String, nullable=False)  # 存档名称
    created_at = Column(String, nullable=False)  # 创建时间（ISO 8601）
    updated_at = Column(String, nullable=False)  # 最后更新时间（ISO 8601）

    # ── 游戏进度 ─────────────────────────────────────────────
    # Story content is published independently; the application validates this
    # identifier against the active compiled story revision.
    current_node_id = Column(String, nullable=False)  # 当前节点
    cycle_count = Column(Integer, default=0)  # 完整循环次数
    half_cycle_count = Column(Integer, default=0)  # 半循环次数

    # ── 状态快照（JSON 序列化） ───────────────────────────────
    inventory_json = Column(Text, default="[]")  # 背包道具
    flags_json = Column(Text, default="{}")  # 全局标记
    visited_nodes_json = Column(Text, default="[]")  # 本轮已访问节点
    player_attributes_json = Column(Text, default="{}")  # 玩家属性
    endings_reached_json = Column(Text, default="[]")  # 已达成的结局
    visit_id = Column(Integer, default=0)  # 当前节点访问实例 ID
    choice_history_json = Column(Text, default="{}")  # 选项重复策略记录
    entry_attributes_json = Column(Text, default="{}")
    interaction_history_json = Column(Text, default="{}")
    once_marks_json = Column(Text, default="{}")


class NodePersistentState(Base):
    """
    节点级持久化状态 ORM 模型。

    记录某个存档下、某个具体节点中遗留的可交互状态。
    这些状态在玩家离开节点后保留，下次（包括下一轮循环）回到该节点时恢复。

    字段说明：
        - save_id: 所属存档 ID
        - node_id: 关联的节点 ID
        - items_json: 遗留的道具列表 JSON
        - dangers_json: 遗留的危险列表 JSON
    """

    __tablename__ = "node_persistent_state"

    # ── 主键 ─────────────────────────────────────────────────
    id = Column(String, primary_key=True, default=generate_uuid)

    # ── 外部引用 ─────────────────────────────────────────────
    save_id = Column(String, ForeignKey("saves.id"), nullable=False)  # 所属存档
    # Node IDs belong to the compiled story revision, not the save database.
    node_id = Column(String, nullable=False)  # 关联节点

    # ── 状态数据（JSON 序列化） ───────────────────────────────
    items_json = Column(Text, default="[]")  # 遗留道具列表
    dangers_json = Column(Text, default="[]")  # 遗留危险列表

    # ── 约束 ─────────────────────────────────────────────────
    # 同一存档下，同一节点只能有一条持久化状态记录
    __table_args__ = (
        UniqueConstraint("save_id", "node_id"),
        Index("idx_persist_save", "save_id"),
    )
