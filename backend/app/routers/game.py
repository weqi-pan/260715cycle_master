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
from fastapi import APIRouter, HTTPException
from ..engine.engine import GameEngine
from ..engine.story_v3_repository import StoryV3Repository
from ..engine.story_v2_loader import StoryV2Loader
from ..domain.items import item_definition
from ..engine.turn_store import TurnStore
from ..paths import STORY_BUILD_DIR, STORY_V3_DIR
from ..schemas.game import Frame, ChooseRequest, GameState, NodeData, TurnRequest

router = APIRouter(prefix="/api/game", tags=["game"])

# ── 模块级单例 ──────────────────────────────────────────────
# v3 canonical snapshot 在启动时严格加载；游戏端点仍由后续任务切换。
engine = GameEngine()
story_v3 = StoryV3Repository(STORY_V3_DIR, STORY_BUILD_DIR)
story_v2 = StoryV2Loader()
turns = TurnStore()


def _get_graph():
    """
    从启动时严格校验过的 v2 节点构建完整图结构。
    返回:
        {node_id: GraphBundle} 字典
    """
    return story_v2.load_graph()


def _state_frame(graph: dict, state: GameState) -> Frame:
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
    if state.current_node_id not in graph:
        raise ValueError(f"Node '{state.current_node_id}' not found")
    bundle = graph[state.current_node_id]
    available = engine.resolve_available_choices(graph, bundle.id, state)
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
            ambient=bundle.ambient,
            color_palette=bundle.color_palette,
            dialogue_lines=bundle.dialogue_lines,
            entry_blocks=story_v2.entry_blocks(bundle.id, state, engine.evaluator),
        ),
        state=state,
        available_choices=available,
    )


# ============================================================
# 端点实现
# ============================================================

@router.get("/start", response_model=Frame)
def start_game():
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
    graph = _get_graph()
    state = GameState(current_node_id="A")
    frame = _state_frame(graph, state)
    frame.turn_id = turns.issue(frame.state)
    return frame


@router.post("/resume", response_model=Frame)
def resume_game(state: GameState):
    """根据完整存档状态重建当前节点画面，不推进剧情、不重置到 A。"""
    graph = _get_graph()
    try:
        frame = _state_frame(graph, state)
        frame.turn_id = turns.issue(frame.state)
        return frame
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/choose/{node_id}", response_model=Frame)
def choose_action(node_id: str, req: ChooseRequest):
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
    graph = _get_graph()
    state = turns.consume(req.turn_id)
    if state is None:
        raise HTTPException(status_code=409, detail="Turn is stale or unknown")
    try:
        frame = engine.process_choice(graph, node_id, req.choice_id, state)
        frame.node.entry_blocks = story_v2.entry_blocks(
            frame.node.id, frame.state, engine.evaluator
        )
        frame.result_blocks = story_v2.result_blocks(
            node_id, req.choice_id, frame.state, engine.evaluator
        )
        frame.turn_id = turns.issue(frame.state, req.turn_id)
        return frame
    except ValueError as e:
        turns.restore(req.turn_id, state)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/inventory/discard/{item_id}", response_model=Frame)
def discard_inventory_item(item_id: str, req: TurnRequest):
    """由服务端校验并丢弃一件道具，返回同节点的新 Frame。"""
    state = turns.consume(req.turn_id)
    if state is None:
        raise HTTPException(status_code=409, detail="Turn is stale or unknown")
    try:
        try:
            definition = item_definition(item_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        if not definition["discardable"]:
            raise HTTPException(status_code=400, detail=f"Item cannot be discarded: {item_id}")
        item = next((entry for entry in state.inventory if entry.get("id") == item_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Item not in inventory: {item_id}")
        count = int(item.get("count", 1))
        if count > 1:
            item["count"] = count - 1
        else:
            state.inventory = [entry for entry in state.inventory if entry.get("id") != item_id]
        frame = _state_frame(_get_graph(), state)
        frame.turn_id = turns.issue(frame.state, req.turn_id)
        return frame
    except HTTPException:
        turns.restore(req.turn_id, state)
        raise
    except ValueError as exc:
        turns.restore(req.turn_id, state)
        raise HTTPException(status_code=400, detail=str(exc))
