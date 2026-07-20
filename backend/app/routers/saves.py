"""
存档管理 API 路由。

提供游戏进度的完整 CRUD 操作。存档将 GameState 的每个字段
序列化为 JSON 存入 SQLite，加载时反序列化还原。

端点列表：
    GET    /api/saves/               — 列出所有存档
    POST   /api/saves/               — 创建新存档
    PUT    /api/saves/{save_id}      — 更新已有存档
    DELETE /api/saves/{save_id}      — 删除存档
    GET    /api/saves/load/{save_id} — 加载存档（返回完整 GameState）

存档数据结构：
    每个存档包含：
        - 元信息：id、save_name、created_at、updated_at
        - 进度：current_node_id、cycle_count、half_cycle_count
        - 状态快照（JSON 字符串）：背包、标记、属性、已访问节点、结局
"""

# backend/app/routers/saves.py
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.save import Save, NodePersistentState
from ..schemas.game import GameState

router = APIRouter(prefix="/api/saves", tags=["saves"])


def _now() -> str:
    """返回当前时间的 ISO 8601 格式字符串。"""
    return datetime.now().isoformat()


def _replace_persistent_nodes(db: Session, save_id: str, state: GameState) -> None:
    """用 GameState 中的快照替换该存档的节点遗留状态。"""
    db.query(NodePersistentState).filter(
        NodePersistentState.save_id == save_id
    ).delete(synchronize_session=False)
    for node_id, node_state in state.persistent_nodes.items():
        db.add(NodePersistentState(
            save_id=save_id,
            node_id=node_id,
            items_json=json.dumps(node_state.get("items", []), ensure_ascii=False),
            dangers_json=json.dumps(node_state.get("dangers", []), ensure_ascii=False),
        ))


# ============================================================
# 端点实现
# ============================================================

@router.get("/")
def list_saves(db: Session = Depends(get_db)):
    """
    列出所有存档。

    按最后更新时间降序排列，最新的存档排在最前。
    返回精简信息（不含完整 GameState），用于存档选择界面。

    返回:
        {
            "saves": [
                {
                    "id": "abc12345",
                    "save_name": "自动存档-第3轮",
                    "created_at": "2026-07-18T10:30:00",
                    "updated_at": "2026-07-18T11:45:00",
                    "current_node_id": "C",
                    "cycle_count": 3
                },
                ...
            ]
        }
    """
    saves = db.query(Save).order_by(Save.updated_at.desc()).all()
    return {
        "saves": [
            {
                "id": s.id,
                "save_name": s.save_name,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "current_node_id": s.current_node_id,
                "cycle_count": s.cycle_count,
            }
            for s in saves
        ]
    }


@router.post("/")
def create_save(name: str, state: GameState, db: Session = Depends(get_db)):
    """
    创建新存档。

    将当前 GameState 的所有字段序列化为 JSON 存入数据库。
    存档 ID 使用 UUID 的前 8 位，保证唯一性的同时便于显示。

    查询参数:
        name:  存档名称（如 "手动存档-荔湾广场"）
    请求体:
        state: 当前游戏状态（JSON body）

    返回:
        {"id": "abc12345", "save_name": "...", "created_at": "..."}

    注意:
        当前不限制存档数量。后续可考虑设置上限（如 10 个槽位）。
    """
    sid = str(uuid.uuid4())[:8]  # UUID 前 8 位作为存档 ID
    now = _now()
    save = Save(
        id=sid,
        save_name=name,
        created_at=now,
        updated_at=now,
        current_node_id=state.current_node_id,
        cycle_count=state.cycle_count,
        half_cycle_count=state.half_cycle_count,
        # 将 Python 对象序列化为 JSON 字符串存储
        inventory_json=json.dumps(state.inventory, ensure_ascii=False),
        flags_json=json.dumps(state.flags, ensure_ascii=False),
        visited_nodes_json=json.dumps(state.visited_nodes, ensure_ascii=False),
        player_attributes_json=json.dumps(state.player_attributes, ensure_ascii=False),
        endings_reached_json=json.dumps(state.endings_reached, ensure_ascii=False),
    )
    db.add(save)
    db.flush()
    _replace_persistent_nodes(db, sid, state)
    db.commit()
    return {"id": sid, "save_name": name, "created_at": now}


@router.put("/{save_id}")
def update_save(save_id: str, state: GameState, db: Session = Depends(get_db)):
    """
    覆盖更新已有存档。

    常用于自动存档或手动覆盖存档。将传入的 GameState
    完整覆盖数据库中对应存档的所有字段。

    路径参数:
        save_id: 要更新的存档 ID
    请求体:
        state:   新的游戏状态

    返回:
        {"status": "ok"}

    错误:
        404 — 存档不存在
    """
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")

    # 更新进度字段
    save.current_node_id = state.current_node_id
    save.cycle_count = state.cycle_count
    save.half_cycle_count = state.half_cycle_count

    # 重新序列化状态字段
    save.inventory_json = json.dumps(state.inventory, ensure_ascii=False)
    save.flags_json = json.dumps(state.flags, ensure_ascii=False)
    save.visited_nodes_json = json.dumps(state.visited_nodes, ensure_ascii=False)
    save.player_attributes_json = json.dumps(state.player_attributes, ensure_ascii=False)
    save.endings_reached_json = json.dumps(state.endings_reached, ensure_ascii=False)
    save.updated_at = _now()

    _replace_persistent_nodes(db, save_id, state)

    db.commit()
    return {"status": "ok"}


@router.delete("/{save_id}")
def delete_save(save_id: str, db: Session = Depends(get_db)):
    """
    删除指定存档。

    路径参数:
        save_id: 要删除的存档 ID

    返回:
        {"status": "ok"}

    错误:
        404 — 存档不存在
    """
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")
    db.query(NodePersistentState).filter(
        NodePersistentState.save_id == save_id
    ).delete(synchronize_session=False)
    db.delete(save)
    db.commit()
    return {"status": "ok"}


@router.get("/load/{save_id}")
def load_save(save_id: str, db: Session = Depends(get_db)):
    """
    加载存档——返回完整 GameState。

    将数据库中存储的 JSON 字符串反序列化为 Python 对象，
    打包为 GameState 返回。前端收到后可以直接传给
    POST /api/game/choose/{node_id} 继续游戏。

    路径参数:
        save_id: 要加载的存档 ID

    返回:
        GameState: 完整的游戏状态对象

    错误:
        404 — 存档不存在

    注意:
        当前不加载 persistent_nodes（节点级持久化状态）。
        后续在 NodePersistentState 表完善后补充。
    """
    save = db.query(Save).filter(Save.id == save_id).first()
    if not save:
        raise HTTPException(404, "Save not found")

    # 从 JSON 字符串反序列化各字段
    persistent_nodes = {
        row.node_id: {
            "items": json.loads(row.items_json or "[]"),
            "dangers": json.loads(row.dangers_json or "[]"),
        }
        for row in db.query(NodePersistentState).filter(
            NodePersistentState.save_id == save_id
        ).all()
    }

    return GameState(
        current_node_id=save.current_node_id,
        cycle_count=save.cycle_count,
        half_cycle_count=save.half_cycle_count,
        inventory=json.loads(save.inventory_json),
        flags=json.loads(save.flags_json),
        visited_nodes=json.loads(save.visited_nodes_json),
        endings_reached=json.loads(save.endings_reached_json),
        player_attributes=json.loads(save.player_attributes_json),
        persistent_nodes=persistent_nodes,
    )
