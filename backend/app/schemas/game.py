"""
游戏运行时 Pydantic Schema 模块。

定义前端与后端游戏 API 之间交互的所有数据结构。
核心数据流：

    ┌──────────┐   POST /api/game/choose/{node_id}   ┌──────────┐
    │  前端     │ ── ChooseRequest (choice_id, state) ──→ │  后端     │
    │  播放器   │ ←── Frame (node, state, choices) ─── │  引擎     │
    └──────────┘                                       └──────────┘

Frame 是一帧完整的游戏画面数据，包含当前节点、更新后的游戏状态、
可用的分支选项、持久化道具发现和循环事件。
"""

# backend/app/schemas/game.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from .story_v2 import ContentBlock
from ..domain.npcs import NPC_NAMES
from ..domain.items import item_definition


# ============================================================
# 原子类型
# ============================================================

class Effect(BaseModel):
    """
    效果数据结构。

    当玩家选择一个分支选项后，引擎根据该选项的 effects 列表，
    对 GameState 施加一系列变更。效果类型包括：

        - add_item / remove_item:  道具增减
        - set_flag / remove_flag:  标记设置/移除
        - heal / damage:          属性增减（理智/勇气/灵感）
        - set_attr:               属性直接赋值
        - leave_item / leave_danger: 向当前节点遗留道具/危险（跨循环持久化）
        - notify / shake / flash: 前端场景特效（仅视觉/音效反馈，不改变状态）
    """
    type: str     # 效果类型
    target: str   # 效果目标（道具 ID / 标记名 / 属性名）
    value: Any    # 效果值（类型取决于 type）


# ============================================================
# 游戏状态
# ============================================================

class GameState(BaseModel):
    """
    游戏运行时完整状态。

    这个对象在每次请求间由前端持有并传回（Stateful API 模式）。
    后端不做 session 管理，所有状态随请求体来回传递。

    字段说明：
        - current_node_id:    玩家当前所在的节点 ID
        - cycle_count:        已完成完整循环次数（回到 A 的次数）
        - half_cycle_count:   半循环次数（到达 E 的次数）
        - inventory:          背包道具列表
        - flags:              全局标记字典
        - visited_nodes:      本轮已访问节点列表
        - endings_reached:    已达成的结局 ID 列表
        - player_attributes:  玩家属性（sanity/courage/insight 等）
        - persistent_nodes:   节点级持久化状态（key=node_id, value={items:[], dangers:[]}）
    """
    current_node_id: str
    cycle_count: int = 0
    half_cycle_count: int = 0
    inventory: list[dict] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)
    visited_nodes: list[str] = Field(default_factory=list)
    endings_reached: list[str] = Field(default_factory=list)
    # 玩家属性默认值：理智 100、勇气 5、灵感 3
    player_attributes: dict[str, int] = Field(
        default_factory=lambda: {"sanity": 100, "courage": 5, "insight": 3}
    )
    persistent_nodes: dict[str, dict] = Field(default_factory=dict)
    visit_id: int = 0
    choice_history: dict[str, dict[str, int]] = Field(default_factory=dict)

    @field_validator("inventory")
    @classmethod
    def hydrate_inventory_metadata(cls, inventory: list[dict]) -> list[dict]:
        hydrated = []
        for entry in inventory:
            try:
                metadata = item_definition(str(entry.get("id", "")))
            except ValueError:
                hydrated.append(entry)
                continue
            hydrated.append({**entry, **metadata})
        return hydrated


# ============================================================
# 节点与选项
# ============================================================

class NodeData(BaseModel):
    """
    节点展示数据（精简版，仅包含前端渲染所需的字段）。

    与数据库中的完整 StoryNode 不同，这里去掉了引擎内部使用的字段
    （如 cycle_variants_json、warp_config_json 等），只保留前端需要
    渲染的内容。
    """
    id: str                          # 节点唯一标识
    name: str                        # 节点中文名称
    node_type: str                   # main | special | sub | normal
    position: float                  # 环面坐标 0-200
    time_label: Optional[str] = None  # 时间标签
    content: str                     # 正文内容（已解析 {{变量}} 模板）
    speaker: Optional[str] = None    # 当前说话人
    speaker_avatar: Optional[str] = None  # 说话人头像资源路径
    background: Optional[str] = None  # 背景图资源路径
    ambient: Optional[str] = None    # 环境音效资源路径
    color_palette: Optional[str] = None  # 场景色调提示
    dialogue_lines: list[dict] = Field(default_factory=list)  # 角色对话行 [{speaker, text}]
    entry_blocks: list[ContentBlock] = Field(default_factory=list)


class ChoiceResult(BaseModel):
    """
    分支选项展示数据。

    引擎在每次返回 Frame 时，评估当前节点所有选项的 condition，
    将可用的选项作为 ChoiceResult 列表返回给前端。
    """
    id: str                          # 选项 ID
    text: str                        # 完整显示文本
    short_text: Optional[str] = None  # 缩略文本（按钮）
    next_node_id: str = Field(min_length=1)  # 目标节点 ID（前端判断是否场景切换）
    available: bool = True            # 是否可选（条件满足）
    reason: Optional[str] = None     # 不可选时的人读原因
    source: str = "static"           # 选项来源: "static" | "special_shortcut" | "special_warp"


class PersistentFound(BaseModel):
    """
    持久化道具/危险发现报告。

    当引擎将玩家推进到一个节点时，检查该节点是否有上一轮循环遗留的
    道具或危险。如果有，通过本结构告知前端以触发对应的 UI 展示。
    """
    items: list[dict] = Field(default_factory=list)              # 遗留的可拾取道具
    cross_surface_items: list[dict] = Field(default_factory=list)  # 跨面共享道具（A↔E 莫比乌斯扭转）
    dangers: list[dict] = Field(default_factory=list)            # 遗留的危险


# ============================================================
# Frame（一帧完整画面）
# ============================================================

class Frame(BaseModel):
    """
    游戏画面帧。

    每次引擎处理一个节点跳转后，返回一帧完整数据。
    前端播放器根据 Frame 渲染完整的游戏画面。

    字段说明：
        - node:              当前节点数据（正文/说话人/背景）
        - state:              更新后的游戏状态
        - available_choices:  当前可用的分支选项列表
        - persistent_found:   节点遗留的道具/危险
        - cycle_event:        循环事件（回到 A 完成一次循环时触发）
        - transition_text:    选项过渡旁白（选择后、到达新节点前的文字）
        - scene_effects:      场景特效列表（notify/shake/flash）
    """
    node: NodeData
    state: GameState
    available_choices: list[ChoiceResult] = Field(default_factory=list)
    persistent_found: PersistentFound = Field(default_factory=PersistentFound)
    cycle_event: Optional[dict] = None
    transition_text: Optional[str] = None
    scene_effects: list[dict] = Field(default_factory=list)
    result_blocks: list[ContentBlock] = Field(default_factory=list)
    speaker_names: dict[str, str] = Field(default_factory=lambda: dict(NPC_NAMES))
    turn_id: str = ""


# ============================================================
# 请求体
# ============================================================

class ChooseRequest(BaseModel):
    """
    选择分支请求体。

    前端将玩家在当前节点的选择 ID 和完整的游戏状态一并发送给后端。
    后端引擎根据 choice_id 找到对应选项，应用效果后返回下一帧。
    """
    choice_id: str         # 玩家选择的分支选项 ID
    turn_id: str = Field(min_length=1)  # 服务端签发的一次性 Turn ID


class TurnRequest(BaseModel):
    """仅依赖服务端权威状态的动作请求。"""
    turn_id: str = Field(min_length=1)


class SaveGameRequest(BaseModel):
    """
    存档请求体（预留）。

    用于创建或覆盖存档时，将存档 ID 和当前状态一并提交。
    """
    save_id: str           # 存档 ID
    state: GameState       # 要保存的游戏状态
