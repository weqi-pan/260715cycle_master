"""
游戏运行时 API 路由。

提供游戏核心交互所需的所有 REST 端点。

端点列表：
    GET  /api/game/start              — 开始新游戏（初始化状态 + 加载起始节点 A）
    POST /api/game/choose/{node_id}   — 在当前节点选择分支，推进到下一帧

数据流：
    前端                             后端
    ────                             ────
    GET /api/game/start ──────────→ 加载图 → 创建初始 GameState → 返回起始 Frame
    POST /choose/A {choice,state} → 引擎 process_choice() → 返回下一 Frame
    POST /choose/B {choice,state} → 引擎 process_choice() → 返回下一 Frame
    ...（前端持有 state，每次请求回传）
"""

# backend/app/routers/game.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..engine.graph import GraphLoader
from ..engine.engine import GameEngine
from ..schemas.game import Frame, ChooseRequest, GameState, NodeData

router = APIRouter(prefix="/api/game", tags=["game"])

# ── 模块级单例 ──────────────────────────────────────────────
# GraphLoader 和 GameEngine 都是无状态对象，创建一次即可复用
loader = GraphLoader()
engine = GameEngine()


def _get_graph(db: Session):
    """
    每次请求重新加载完整的图结构。

    当前采用全量加载策略（Phase 1），因为数据量小（< 500 节点），
    每次从 SQLite 查询全量数据的延迟在 1ms 以内。
    后续可在 GraphLoader 中引入缓存优化。

    参数:
        db: 数据库会话
    返回:
        {node_id: GraphBundle} 字典
    """
    return loader.load_all(db)


def _start_frame(graph: dict, state: GameState) -> Frame:
    """
    构造起始帧（新游戏或加载存档后进入游戏时使用）。

    与 process_choice 不同，_start_frame 不需要 choice_id——
    它直接将玩家放置在节点 A，并解析 A 的所有可用选项。

    参数:
        graph: 完整图字典
        state: 初始游戏状态
    返回:
        起始 Frame（节点 A + 初始状态 + 可用选项）
    """
    bundle = graph["A"]
    state.current_node_id = "A"
    available = engine.resolve_available_choices(graph, "A", state)
    return Frame(
        node=NodeData(
            id=bundle.id,
            name=bundle.name,
            node_type=bundle.node_type,
            position=bundle.position,
            time_label=bundle.time_label,
            content=engine._resolve_content(bundle, state),
            speaker=bundle.speaker,
            background=bundle.background,
        ),
        state=state,
        available_choices=available,
    )


# ============================================================
# 端点实现
# ============================================================

@router.get("/start", response_model=Frame)
def start_game(db: Session = Depends(get_db)):
    """
    开始新游戏。

    创建初始 GameState（所有属性默认值），加载图结构，
    返回起始节点 A 的完整 Frame。

    返回:
        Frame: 包含节点 A 的数据、初始 GameState 和可用选项列表

    前端调用时机:
        - 用户点击"新游戏"
        - 用户加载存档后（由前端构造 GameState 调用 choose 而非此接口）
    """
    graph = _get_graph(db)
    state = GameState(current_node_id="A")
    return _start_frame(graph, state)


@router.post("/choose/{node_id}", response_model=Frame)
def choose_action(node_id: str, req: ChooseRequest, db: Session = Depends(get_db)):
    """
    玩家选择分支选项。

    接收玩家在当前节点的选择 ID 和客户端当前的 GameState，
    引擎处理后返回下一帧完整画面。

    路径参数:
        node_id: 玩家当前所在节点 ID（如 "A", "B", "S5"）

    请求体:
        choice_id: 玩家选择的选项 ID（如 "A_choice_1" 或 "__warp_K_enter"）
        state:     客户端当前游戏状态

    返回:
        Frame: 下一帧的完整数据（新节点 + 更新后的状态 + 可用选项）

    错误:
        400 Bad Request — choice_id 不存在或条件不满足

    前端调用时机:
        - 每次玩家在选项列表中做出选择时
        - 加载存档后进入游戏时（前端将存档还原为 GameState 后调用此接口）
    """
    graph = _get_graph(db)
    state = req.state  # 使用客户端传入的状态（Stateful API）
    try:
        frame = engine.process_choice(graph, node_id, req.choice_id, state)
        return frame
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
