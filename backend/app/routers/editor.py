"""
可视化编辑器 API 路由。

提供故事节点和分支选项的完整 CRUD 操作，供前端 Cytoscape.js
图编辑器使用。编辑器 API 独立于游戏运行时 API，使用自己的端点前缀。

端点列表：

    节点管理：
        GET    /api/editor/nodes            — 列出所有节点
        POST   /api/editor/nodes            — 创建或更新节点（upsert）
        DELETE /api/editor/nodes/{node_id}  — 删除节点（级联删除关联选项）

    选项管理：
        GET    /api/editor/choices/_all     — 列出所有选项（用于边渲染）
        GET    /api/editor/choices/{node_id}— 列出指定节点的选项
        POST   /api/editor/choices          — 创建或更新选项（upsert）
        DELETE /api/editor/choices/{choice_id}— 删除单个选项

设计决策：
    - save_node 和 save_choice 采用 upsert 模式（存在则更新，否则创建），
      简化前端编辑器逻辑——无需区分新建和编辑模式
    - DELETE node 时级联删除与该节点相关的所有 choices，
      避免孤儿选项导致引用完整性错误
"""

# backend/app/routers/editor.py
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.story import StoryNode, Choice

router = APIRouter(prefix="/api/editor", tags=["editor"])


# ============================================================
# 节点管理
# ============================================================

@router.get("/nodes")
def list_nodes(db: Session = Depends(get_db)):
    """
    列出所有故事节点。

    按环面坐标（position）→ 节点 ID 排序，保证图中节点显示有序。

    返回:
        {
            "nodes": [
                {
                    "id": "A", "name": "荔湾广场正门", "position": 0.0,
                    "node_type": "main", "time_label": null,
                    "content": "...", "speaker": null, "background": "bg_lwgc.jpg"
                },
                ...
            ]
        }

    注意:
        返回的是精简字段集，不含 cycle_variants 等复杂 JSON 配置。
        编辑器如需编辑复杂字段，应单独请求节点详情（后续扩展）。
    """
    nodes = db.query(StoryNode).order_by(StoryNode.position, StoryNode.id).all()
    return {
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "position": n.position,
                "node_type": n.node_type,
                "time_label": n.time_label,
                "content": n.content,
                "speaker": n.speaker,
                "background": n.background,
            }
            for n in nodes
        ]
    }


@router.post("/nodes")
def save_node(data: dict, db: Session = Depends(get_db)):
    """
    创建或更新节点（upsert）。

    如果 data.id 已存在 → 更新该节点的所有字段
    如果 data.id 不存在 → 创建新节点

    请求体 (JSON):
        {
            "id": "A",
            "name": "荔湾广场正门",
            "position": 0.0,
            "node_type": "main",
            "content": "你站在荔湾广场的正门前...",
            ...（更多可选字段见 StoryNode 模型）
        }

    返回:
        {"status": "created" | "updated", "id": "..."}

    错误:
        400 — 缺少 id 字段
    """
    node_id = data.get("id")
    if not node_id:
        raise HTTPException(400, "Missing node id")

    # 查找已存在的节点
    existing = db.query(StoryNode).filter(StoryNode.id == node_id).first()
    if existing:
        # ── 更新已有节点 ─────────────────────────────────────
        for k, v in data.items():
            if k != "id" and hasattr(existing, k):
                setattr(existing, k, v)
        db.commit()
        return {"status": "updated", "id": node_id}
    else:
        # ── 创建新节点 ───────────────────────────────────────
        node = StoryNode(
            id=node_id,
            name=data.get("name", ""),
            position=data.get("position", 0.0),
            node_type=data.get("node_type", "normal"),
            time_label=data.get("time_label"),
            content=data.get("content", ""),
            speaker=data.get("speaker"),
            background=data.get("background"),
            # 复杂 JSON 字段序列化
            cycle_variants_json=json.dumps(data.get("cycle_variants", {}), ensure_ascii=False),
            color_palette=data.get("color_palette"),
            atmosphere_json=json.dumps(data.get("atmosphere", []), ensure_ascii=False),
            sensory=data.get("sensory"),
        )
        db.add(node)
        db.commit()
        return {"status": "created", "id": node_id}


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str, db: Session = Depends(get_db)):
    """
    删除节点（级联删除关联选项）。

    删除节点时，同时删除：
        - 以该节点为来源的所有 options（from_node_id = node_id）
        - 以该节点为目标的所有 options（next_node_id = node_id）

    这确保删除节点后不会留下孤儿选项导致引用完整性错误。

    路径参数:
        node_id: 要删除的节点 ID

    返回:
        {"status": "deleted"}
    """
    # 先删除所有关联选项（from_node_id 或 next_node_id 匹配的）
    db.query(Choice).filter(
        (Choice.from_node_id == node_id) | (Choice.next_node_id == node_id)
    ).delete()
    # 再删除节点本身
    db.query(StoryNode).filter(StoryNode.id == node_id).delete()
    db.commit()
    return {"status": "deleted"}


# ============================================================
# 选项管理
# ============================================================

@router.get("/choices/_all")
def list_all_choices(db: Session = Depends(get_db)):
    """
    列出数据库中所有分支选项。

    此端点专为编辑器图渲染设计——Cytoscape 需要一次性获取
    所有边（edge）数据以绘制完整图。

    返回:
        {
            "choices": [
                {
                    "id": "A_choice_1",
                    "from_node_id": "A",  → 边的起点
                    "next_node_id": "B",  → 边的终点
                    "text": "...", "condition": "...", "effects": [...], ...
                },
                ...
            ]
        }
    """
    choices = db.query(Choice).order_by(Choice.priority).all()
    return {"choices": [_choice_to_dict(c) for c in choices]}


@router.get("/choices/{node_id}")
def list_choices(node_id: str, db: Session = Depends(get_db)):
    """
    列出指定节点的所有选项。

    用于编辑器中选中某个节点后展示其关联的选项列表。

    路径参数:
        node_id: 节点 ID

    返回:
        {"choices": [...]}
    """
    choices = (
        db.query(Choice)
        .filter(Choice.from_node_id == node_id)
        .order_by(Choice.priority)
        .all()
    )
    return {"choices": [_choice_to_dict(c) for c in choices]}


@router.post("/choices")
def save_choice(data: dict, db: Session = Depends(get_db)):
    """
    创建或更新选项（upsert）。

    如果 data.id 已存在 → 更新该选项的所有字段
    如果 data.id 不存在 → 创建新选项

    请求体 (JSON):
        {
            "id": "A_choice_1",
            "from_node_id": "A",
            "text": "推开沉重的铁门",
            "next_node_id": "B",
            "condition": "has_item:item_old_key",
            "effects": [{"type": "set_flag", "target": "entered_b", "value": true}],
            "priority": 1,
            "hint": "需要锈蚀铜钥匙",
            "is_hidden_when_locked": false,
            "transition_text": "铁门在身后轰然关闭..."
        }

    返回:
        {"status": "created" | "updated"}

    错误:
        400 — 缺少 id 字段
    """
    choice_id = data.get("id")
    if not choice_id:
        raise HTTPException(400, "Missing choice id")

    existing = db.query(Choice).filter(Choice.id == choice_id).first()
    if existing:
        # ── 更新已有选项 ─────────────────────────────────────
        existing.from_node_id = data.get("from_node_id", existing.from_node_id)
        existing.text = data.get("text", existing.text)
        existing.short_text = data.get("short_text", existing.short_text)
        existing.next_node_id = data.get("next_node_id", existing.next_node_id)
        existing.condition = data.get("condition", existing.condition)
        existing.effects_json = json.dumps(data.get("effects", []), ensure_ascii=False)
        existing.priority = data.get("priority", existing.priority)
        existing.hint = data.get("hint", existing.hint)
        existing.is_hidden_when_locked = 1 if data.get("is_hidden_when_locked") else 0
        existing.transition_text = data.get("transition_text", existing.transition_text)
        db.commit()
        return {"status": "updated"}
    else:
        # ── 创建新选项 ───────────────────────────────────────
        choice = Choice(
            id=choice_id,
            from_node_id=data.get("from_node_id", ""),
            text=data.get("text", ""),
            short_text=data.get("short_text"),
            next_node_id=data.get("next_node_id", ""),
            condition=data.get("condition"),
            effects_json=json.dumps(data.get("effects", []), ensure_ascii=False),
            priority=data.get("priority", 99),
            hint=data.get("hint"),
            is_hidden_when_locked=1 if data.get("is_hidden_when_locked") else 0,
            transition_text=data.get("transition_text"),
        )
        db.add(choice)
        db.commit()
        return {"status": "created"}


@router.delete("/choices/{choice_id}")
def delete_choice(choice_id: str, db: Session = Depends(get_db)):
    """
    删除指定选项。

    路径参数:
        choice_id: 要删除的选项 ID

    返回:
        {"status": "deleted"}
    """
    db.query(Choice).filter(Choice.id == choice_id).delete()
    db.commit()
    return {"status": "deleted"}


# ============================================================
# 辅助函数
# ============================================================

def _choice_to_dict(c: Choice) -> dict:
    """
    将 Choice ORM 对象转换为前端友好的字典格式。

    处理 JSON 字段的反序列化（effects_json → effects list），
    以及 bool 字段的类型转换（is_hidden_when_locked: int → bool）。

    参数:
        c: Choice ORM 实例
    返回:
        字典表示
    """
    return {
        "id": c.id,
        "from_node_id": c.from_node_id,
        "text": c.text,
        "short_text": c.short_text,
        "next_node_id": c.next_node_id,
        "condition": c.condition,
        "effects": json.loads(c.effects_json),  # 反序列化效果列表
        "priority": c.priority,
        "hint": c.hint,
        "is_hidden_when_locked": bool(c.is_hidden_when_locked),  # int → bool
        "transition_text": c.transition_text,
    }
