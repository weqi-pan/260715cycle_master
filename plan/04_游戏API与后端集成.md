# Phase 3: 游戏 API 与后端集成

> **工期**：2 周（第 7-8 周）  
> **目标**：全部 REST API 端点实现，存档系统完整，后端可独立提供环形 demo 游玩体验  
> **前置**：Phase 2（图引擎）  
> **产出**：FastAPI 全部端点 + 存档 CRUD + 集成测试 + API 文档

---

## 一、API 端点总览

| 方法 | 路径 | 用途 | Phase 3 | 说明 |
|------|------|------|---------|------|
| `GET` | `/api/game/start` | 初始化新游戏 | ✅ | 创建存档 + 返回节点 A 的 Frame |
| `POST` | `/api/game/choose/{node_id}?save_id=X` | 提交选择 | ✅ | 返回下一帧 |
| `GET` | `/api/game/state/{save_id}` | 获取游戏状态 | ✅ | 恢复游戏用 |
| `POST` | `/api/saves` | 创建新存档 | ✅ | |
| `GET` | `/api/saves` | 获取存档列表 | ✅ | |
| `PUT` | `/api/saves/{save_id}` | 手动保存进度 | ✅ | 自动保存也可走此端点 |
| `DELETE` | `/api/saves/{save_id}` | 删除存档 | ✅ | |
| `GET` | `/api/editor/nodes` | 获取所有节点 | ⏳ | Phase 5 |
| `POST` | `/api/editor/nodes` | 创建/更新节点 | ⏳ | Phase 5 |
| `DELETE` | `/api/editor/nodes/{id}` | 删除节点 | ⏳ | Phase 5 |
| `GET` | `/api/editor/choices/{node_id}` | 获取某节点选择 | ⏳ | Phase 5 |
| `POST` | `/api/editor/choices` | 创建/更新选择 | ⏳ | Phase 5 |

---

## 二、任务清单

### 2.1 游戏路由 — `/api/game/*`（Day 1-4）

#### 2.1.1 初始化新游戏 `GET /api/game/start`

```python
# backend/app/routers/game.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.game import Frame
from app.engine.engine import start_new_game
import uuid

router = APIRouter()

@router.get("/start", response_model=Frame)
async def game_start(db: AsyncSession = Depends(get_db)):
    """
    初始化新游戏：
    - 创建新存档
    - 初始化 GameState（cycle=0, inventory=[钥匙], attributes=默认值）
    - 加载节点 A
    - 返回 Frame（含可用选择、状态）
    """
    try:
        save_id = str(uuid.uuid4())
        frame = await start_new_game(db, save_id)
        return frame
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2.1.2 提交选择 `POST /api/game/choose/{node_id}`

```python
@router.post("/choose/{node_id}", response_model=Frame)
async def game_choose(
    node_id: str,
    body: dict,                              # {"choice_id": "...", "save_id": "..."}
    db: AsyncSession = Depends(get_db)
):
    """
    提交玩家的选择：
    - 校验 choice_id 在 node_id 下是否有效
    - 引擎处理选择 → 更新 state
    - 循环检测 → 可能触发 cycle_event
    - 返回下一帧
    """
    choice_id = body.get("choice_id")
    save_id = body.get("save_id")

    if not choice_id or not save_id:
        raise HTTPException(status_code=400, detail="Missing choice_id or save_id")

    try:
        frame = await process_choice(db, node_id, choice_id, save_id)
        return frame
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2.1.3 获取游戏状态 `GET /api/game/state/{save_id}`

```python
@router.get("/state/{save_id}", response_model=GameState)
async def game_state(
    save_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取存档当前的 GameState（前端恢复游戏用）"""
    state = await load_state(db, save_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Save not found")
    return state
```

---

### 2.2 存档路由 — `/api/saves/*`（Day 5-7）

#### 2.2.1 存档 CRUD

```python
# backend/app/routers/saves.py
@router.post("", response_model=SaveSlot)
async def create_save(
    body: SaveCreate,                        # {"save_name": "..."}
    db: AsyncSession = Depends(get_db)
):
    """创建新存档（手动创建，通常用 game/start 自动创建）"""
    pass

@router.get("", response_model=list[SaveSlot])
async def list_saves(db: AsyncSession = Depends(get_db)):
    """获取所有存档列表（用于存档选择界面）"""
    pass

@router.put("/{save_id}", response_model=SaveSlot)
async def update_save(
    save_id: str,
    body: SaveUpdate,
    db: AsyncSession = Depends(get_db)
):
    """手动更新存档（自动保存也走此端点）"""
    pass

@router.delete("/{save_id}")
async def delete_save(
    save_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除存档及其关联的持久化状态"""
    pass
```

#### 2.2.2 存档数据结构

```python
# 存档槽位（存档列表展示）
class SaveSlot(BaseModel):
    id: str
    save_name: str
    created_at: str
    updated_at: str
    current_node_name: str          # 从 story_nodes 关联查询
    cycle_count: int
    half_cycle_count: int

# 完整存档（游戏恢复用）
class SaveFull(BaseModel):
    id: str
    save_name: str
    game_state: GameState           # 完整运行时状态
    persistent_states: list[dict]   # 所有节点的遗留状态
```

#### 2.2.3 状态持久化函数

```python
# backend/app/engine/persistence.py
"""状态加载/保存的辅助函数"""

async def load_state(session: AsyncSession, save_id: str) -> GameState | None:
    """从数据库加载 GameState"""
    result = await session.execute(
        select(Save).where(Save.id == save_id)
    )
    save = result.scalar_one_or_none()
    if save is None:
        return None

    return GameState(
        current_node_id=save.current_node_id,
        cycle_count=save.cycle_count,
        half_cycle_count=save.half_cycle_count,
        inventory=json.loads(save.inventory),
        flags=json.loads(save.flags),
        visited_nodes=json.loads(save.visited_nodes),
        player_attributes=json.loads(save.player_attributes),
        endings_reached=json.loads(save.endings_reached),
    )

async def save_state(session: AsyncSession, save_id: str, state: GameState):
    """将 GameState 写入数据库"""
    save = await session.get(Save, save_id)
    if save:
        save.current_node_id = state.current_node_id
        save.cycle_count = state.cycle_count
        save.half_cycle_count = state.half_cycle_count
        save.inventory = json.dumps([i.model_dump() for i in state.inventory])
        save.flags = json.dumps(state.flags)
        save.visited_nodes = json.dumps(state.visited_nodes)
        save.player_attributes = json.dumps(state.player_attributes)
        save.endings_reached = json.dumps(state.endings_reached)
        save.updated_at = datetime.utcnow().isoformat()
        await session.commit()

async def load_persistent_state(
    session: AsyncSession, save_id: str, node_id: str
) -> PersistentFound:
    """加载某个节点的遗留状态"""
    result = await session.execute(
        select(NodePersistentState)
        .where(NodePersistentState.save_id == save_id)
        .where(NodePersistentState.node_id == node_id)
    )
    ps = result.scalar_one_or_none()
    if ps is None:
        return PersistentFound()

    return PersistentFound(
        items=json.loads(ps.items),
        dangers=json.loads(ps.dangers),
    )

async def save_persistent_state(
    session: AsyncSession, save_id: str, node_id: str,
    items: list, dangers: list
):
    """更新节点的遗留状态"""
    ps = NodePersistentState(
        id=str(uuid.uuid4()),
        save_id=save_id,
        node_id=node_id,
        items=json.dumps([i.model_dump() for i in items]),
        dangers=json.dumps(dangers),
    )
    session.add(ps)
    await session.commit()
```

---

### 2.3 start_new_game 实现（Day 8）

```python
# backend/app/engine/engine.py
async def start_new_game(session: AsyncSession, save_id: str) -> Frame:
    """初始化新游戏"""
    from datetime import datetime
    import uuid

    # 创建存档记录
    now = datetime.utcnow().isoformat()
    save = Save(
        id=save_id,
        save_name=f"新游戏 {now[:10]}",
        created_at=now,
        updated_at=now,
        current_node_id="A",
        cycle_count=0,
        half_cycle_count=0,
        inventory=json.dumps([{
            "id": "item_rent_key", "name": "出租屋钥匙", "cross_surface": False
        }]),
        flags=json.dumps({}),
        visited_nodes=json.dumps(["A"]),
        player_attributes=json.dumps({
            "sanity": 100, "courage": 5, "insight": 3
        }),
        endings_reached=json.dumps([]),
    )
    session.add(save)
    await session.commit()

    # 加载节点 A
    graph = Graph(session)
    node = await graph.get_node("A")
    choices = await graph.get_choices("A")
    router = SpecialRouter(graph)

    state = GameState(
        current_node_id="A",
        cycle_count=0,
        half_cycle_count=0,
        inventory=[ItemBrief(id="item_rent_key", name="出租屋钥匙", cross_surface=False)],
        flags={},
        visited_nodes=["A"],
        player_attributes={"sanity": 100, "courage": 5, "insight": 3},
        endings_reached=[],
    )

    evaluator = ConditionEvaluator(state)

    static_choices = [
        ChoiceResult(
            id=c.id, text=c.text,
            available=evaluator.evaluate(c.condition),
            source="static",
            reason=None if evaluator.evaluate(c.condition) else f"需要: {c.condition}"
        )
        for c in choices
    ]

    special_choices = await router.get_available(node, state)
    all_choices = static_choices + special_choices

    return Frame(
        node=node_to_schema(node),
        state=state,
        available_choices=all_choices,
        persistent_found=PersistentFound(),
        cycle_event=None,
    )
```

---

### 2.4 遗留道具/危险处理（Day 9）

```python
# 在 process_choice() 中添加
# 处理 leave_item / leave_danger 效果

for effect in effects:
    if effect["type"] == "leave_item":
        item_id = effect.get("value") or effect["target"]
        persistent_items = await load_persistent_state(session, save_id, node_id)
        # 添加道具到当前节点的遗留列表
        current_items = persistent_items.items or []
        current_items.append(ItemBrief(
            id=item_id, name=item_id, cross_surface=False
            # name 和 cross_surface 从 items 表查询
        ))
        await save_persistent_state(session, save_id, node_id,
                                     items=current_items,
                                     dangers=persistent_items.dangers)

    elif effect["type"] == "leave_danger":
        danger_id = effect.get("value") or effect["target"]
        persistent_items = await load_persistent_state(session, save_id, node_id)
        current_dangers = persistent_items.dangers or []
        current_dangers.append({"id": danger_id, "triggered": False})
        await save_persistent_state(session, save_id, node_id,
                                     items=persistent_items.items,
                                     dangers=current_dangers)
```

---

### 2.5 集成测试（Day 10-12）

#### 2.5.1 API 测试用例

```python
# backend/tests/test_api/test_game.py
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

class TestGameStart:
    async def test_start_returns_frame(self, client, seeded_db):
        response = await client.get("/api/game/start")
        assert response.status_code == 200
        data = response.json()
        assert data["node"]["id"] == "A"
        assert len(data["available_choices"]) > 0
        assert data["state"]["cycle_count"] == 0

class TestGameChoose:
    async def test_choose_advances_to_next_node(self, client, seeded_db):
        # 1. start
        start_resp = await client.get("/api/game/start")
        start_data = start_resp.json()
        save_id = start_data["state"]["cycle_count"]  # 需要从别处获取
        # 实际实现中 Frame 的 state 不直接暴露 save_id，需要在 start 响应中单独返回

        # 2. choose
        choice_id = start_data["available_choices"][0]["id"]
        resp = await client.post(
            f"/api/game/choose/A",
            json={"choice_id": choice_id, "save_id": save_id}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["id"] != "A"  # 前进到了下一个节点

class TestFullLoop:
    async def test_full_loop_8_nodes(self, client, seeded_db):
        """走完 A→B→C→D→E→F→G→H→A 完整一圈"""
        # ... 依次选择每个节点的第一个选项
        # 验证最终 cycle_count == 1 且回到 A
```

#### 2.5.2 测试场景矩阵

| 场景 | API 调用序列 | 验证点 |
|------|-------------|--------|
| 新游戏启动 | `GET /start` | 返回 A 节点, cycle=0, 有钥匙 |
| 基本推进 | start → choose×8 | 经过全部 8 主节点 |
| 完整循环 | start → choose×9（到回 A） | cycle_count=1, cycle_event 非 null |
| 存档读取 | start → save → 读存档 | state 完全一致 |
| 条件选项不可用 | start → 查看某带条件选项 | available=false, reason 非空 |
| 条件选项满足后可用 | 先满足条件再查看 | available=true |
| K 跃迁 | 满足条件 → 出现 warp 选项 → K → 跳转 | 可跳转到目标主节点 |
| J 捷径 | 满足条件 → E→J→A | half_cycle_count=1 |

---

### 2.6 错误处理与健壮性（Day 13-14）

#### 2.6.1 异常处理规范

```python
# 自定义异常
class GameError(Exception):
    """游戏逻辑异常基类"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

class ConditionNotMetError(GameError):
    def __init__(self, condition: str):
        super().__init__(f"条件不满足: {condition}", 403)

class NodeNotFoundError(GameError):
    def __init__(self, node_id: str):
        super().__init__(f"节点不存在: {node_id}", 404)

class SaveNotFoundError(GameError):
    def __init__(self, save_id: str):
        super().__init__(f"存档不存在: {save_id}", 404)

# 全局异常处理器
@app.exception_handler(GameError)
async def game_error_handler(request, exc: GameError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "type": type(exc).__name__}
    )
```

#### 2.6.2 输入校验

- `node_id` 和 `choice_id` 必须在数据库中存在
- `save_id` 必须有效
- `choice_id` 必须在 `node_id` 的出边集合中
- 条件不满足时返回 "locked" 状态而不是直接拒绝

---

### 2.7 后端入口更新（贯穿）

更新 `main.py`，注册路由：

```python
from app.routers import game, saves
from app.database import init_db

app = FastAPI(...)

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(saves.router, prefix="/api/saves", tags=["saves"])
```

---

## 三、API 文档

FastAPI 自动生成 OpenAPI 文档：

- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`

Phase 3 结束时，所有 game/saves 端点都应在 Swagger UI 中可交互测试。

---

## 四、验收标准

- [ ] `GET /api/game/start` 返回完整 Frame（A 节点 + 状态 + 选项）
- [ ] `POST /api/game/choose/{node_id}` 可连续推进游戏
- [ ] 可在后端通过 API 调用完成 A→B→...→H→A 完整循环
- [ ] `cycle_count` 和 `half_cycle_count` 正确递增
- [ ] `cycle_event` 在回到 A 时正确生成
- [ ] 存档 CRUD（创建/列表/更新/删除）全部正常
- [ ] 存档恢复后 state 完全一致
- [ ] K 跃迁和 J 捷径在满足条件时正确出现
- [ ] 条件不满足的选项标记为 unavailable 并显示原因
- [ ] 全部集成测试通过（≥ 8 个场景）
- [ ] Swagger UI 文档完整可用
- [ ] 异常处理返回规范的 JSON 错误响应

---

## 五、产出物

| 产出 | 路径 |
|------|------|
| 游戏路由 | `backend/app/routers/game.py` |
| 存档路由 | `backend/app/routers/saves.py` |
| 状态持久化 | `backend/app/engine/persistence.py` |
| 集成测试 | `backend/tests/test_api/` |
| API 文档 | Swagger UI 自动生成 |
| 里程碑 tag | `v0.4.0` |
