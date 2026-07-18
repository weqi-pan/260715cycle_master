"""
可视化编辑器 Pydantic Schema 模块。

定义前端编辑器与后端编辑器 API 之间交互的数据结构。

编辑器 API（/api/editor/*）独立于游戏运行时 API（/api/game/*），
使用自己的 Schema 定义 为了保证编辑器可以独立演进，不耦合游戏运行时的数据结构。
"""

# backend/app/schemas/editor.py
from pydantic import BaseModel
from typing import Optional
from .game import Effect  # 复用游戏 Schema 中的 Effect 定义


class NodeCreate(BaseModel):
    """
    创建/更新节点请求体。

    编辑器中新建或修改一个故事节点时使用的数据结构。
    字段数量比完整的 StoryNode 模型精简，复杂配置
    （如 warp_config、crossing_config）在初期通过 JSON 编辑器直接编辑。

    字段说明：
        - id: 节点唯一标识（如 "A", "B", "S15"）
        - name: 中文名称
        - position: 环面坐标 0-200
        - node_type: main | special | sub | normal
        - time_label: 时间标签（可选）
        - content: 正文文本（支持 {{变量}} 模板）
        - speaker: 当前说话人 ID（可选）
        - background: 背景图资源文件名（可选）
    """
    id: str
    name: str
    position: float
    node_type: str = "normal"
    time_label: Optional[str] = None
    content: str
    speaker: Optional[str] = None
    background: Optional[str] = None


class ChoiceCreate(BaseModel):
    """
    创建/更新分支选项请求体。

    编辑器中新建或修改一个分支选项时使用的数据结构。

    字段说明：
        - id: 选项唯一标识
        - from_node_id: 来源节点 ID（选项属于哪个节点）
        - text: 完整显示文本
        - short_text: 缩略文本（按钮文字）
        - next_node_id: 目标节点 ID（选择后跳转到哪个节点）
        - condition: 条件表达式（为空表示始终可选）
        - effects: 选中后触发的效果列表
        - priority: 排序优先级（数字越小越靠前）
        - hint: 鼠标悬停提示
        - is_hidden_when_locked: 条件不满足时是否完全隐藏
    """
    id: str
    from_node_id: str
    text: str
    short_text: Optional[str] = None
    next_node_id: str
    condition: Optional[str] = None
    effects: list[Effect] = []
    priority: int = 99
    hint: Optional[str] = None
    is_hidden_when_locked: bool = False
