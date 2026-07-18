"""
故事数据导入脚本。

将 story_data/ 目录下的 JSON 文件批量导入 SQLite 数据库。
这是设计与程序之间的桥梁——编剧用 JSON 编写故事，导入脚本将其
转换为数据库记录供引擎使用。

数据源目录结构:
    story_data/
    ├── 05_nodes/         ← 节点 JSON（每个节点一个文件）
    │   ├── A_起点.json
    │   ├── B_出租屋.json
    │   └── ...
    └── 06_choices/       ← 选项 JSON（每个节点一个文件）
        ├── A_choices.json
        ├── B_choices.json
        └── ...

执行方式:
    python -m backend.import_story
    或
    cd backend && python import_story.py

流程:
    1. init_db() → 确保表结构已创建
    2. 清空已有故事数据（choices → story_nodes，顺序依赖参照完整性）
    3. 从 05_nodes/ 导入所有节点
    4. 从 06_choices/ 导入所有选项
    5. 验证数据完整性（引用完整性检查）
"""

# backend/import_story.py
import json
import os
from sqlalchemy import text
from app.database import SessionLocal, init_db
from app.models.story import StoryNode, Choice
from app.models.save import Save, NodePersistentState  # 确保表已注册到 Base.metadata
from app.config import STORY_DATA_DIR


def import_all():
    """
    一键执行完整导入流程。

    步骤:
        ① 初始化数据库（自动建表）
        ② 清空已有故事数据（保留存档表）
        ③ 导入所有节点（05_nodes/*.json）
        ④ 导入所有选项（06_choices/*.json）
        ⑤ 验证数据完整性
    """
    # ① 初始化数据库 → 确保所有表都存在
    init_db()

    # ② 清空已有故事数据（按外键依赖顺序删除）
    with SessionLocal() as session:
        for tbl in ["choices", "node_persistent_state", "saves", "story_nodes"]:
            try:
                session.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass  # 表可能还不存在（全新数据库）
        session.commit()

    # ③ 导入节点
    with SessionLocal() as session:
        _import_nodes(session)
        _import_choices(session)
        session.commit()
        # ④ 验证完整性
        _verify(session)


def _import_nodes(session):
    """
    从 story_data/05_nodes/ 导入所有节点。

    遍历目录下的每个 .json 文件，读取内容并创建 StoryNode ORM 对象。
    JSON 中的键名与 ORM 字段名的映射关系：
        - parent_node (JSON) → parent_node_id (ORM)
        - cycle_variants → cycle_variants_json
        - crossing_config → crossing_config_json
        - warp_config → warp_config_json
        - shortcut_config → shortcut_config_json
        - npc_item_mapping → npc_item_mapping_json
        - scene_items → scene_items_json

    参数:
        session: 数据库会话
    """
    nodes_dir = os.path.join(STORY_DATA_DIR, "05_nodes")
    count = 0
    for fname in sorted(os.listdir(nodes_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(nodes_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        node = StoryNode(
            id=data["id"],
            name=data["name"],
            position=data["position"],
            node_type=data["node_type"],
            time_label=data.get("time_label"),
            content=data["content"],
            speaker=data.get("speaker"),
            background=data.get("background"),
            # ── JSON 字段：先将 Python 对象序列化为字符串 ──
            cycle_variants_json=json.dumps(data.get("cycle_variants", {}), ensure_ascii=False),
            color_palette=data.get("color_palette"),
            ambient=data.get("ambient"),
            atmosphere_json=json.dumps(data.get("atmosphere", []), ensure_ascii=False),
            sensory=data.get("sensory"),
            gender_variant_json=(
                json.dumps(data.get("gender_variant"), ensure_ascii=False)
                if data.get("gender_variant") else None
            ),
            # Note: JSON 文件中使用 "parent_node" 键（不是 "parent_node_id"）
            parent_node_id=data.get("parent_node"),
            trigger_condition=data.get("trigger_condition"),
            crossing_config_json=(
                json.dumps(data.get("crossing_config"), ensure_ascii=False)
                if data.get("crossing_config") else None
            ),
            warp_config_json=(
                json.dumps(data.get("warp_config"), ensure_ascii=False)
                if data.get("warp_config") else None
            ),
            shortcut_config_json=(
                json.dumps(data.get("shortcut_config"), ensure_ascii=False)
                if data.get("shortcut_config") else None
            ),
            npc_item_mapping_json=(
                json.dumps(data.get("npc_item_mapping"), ensure_ascii=False)
                if data.get("npc_item_mapping") else None
            ),
            scene_items_json=(
                json.dumps(data.get("scene_items"), ensure_ascii=False)
                if data.get("scene_items") else None
            ),
        )
        session.add(node)
        count += 1
    print(f"[import_nodes] 成功导入 {count} 个节点")


def _import_choices(session):
    """
    从 story_data/06_choices/ 导入所有选项。

    遍历目录下的每个 .json 文件，读取内容并创建 Choice ORM 对象。
    每个文件包含一个节点的完整选项列表（数组）。

    参数:
        session: 数据库会话
    """
    choices_dir = os.path.join(STORY_DATA_DIR, "06_choices")
    count = 0
    for fname in sorted(os.listdir(choices_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(choices_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            choices = json.load(f)

        for c in choices:
            choice = Choice(
                id=c["id"],
                from_node_id=c["from_node_id"],
                text=c["text"],
                short_text=c.get("short_text"),
                next_node_id=c["next_node_id"],
                condition=c.get("condition"),
                effects_json=json.dumps(c.get("effects", []), ensure_ascii=False),
                priority=c.get("priority", 99),
                hint=c.get("hint"),
                is_hidden_when_locked=1 if c.get("is_hidden_when_locked") else 0,
                transition_text=c.get("transition_text"),
            )
            session.add(choice)
            count += 1
    print(f"[import_choices] 成功导入 {count} 个选项")


def _verify(session):
    """
    数据完整性验证。

    检查项:
        1. 节点和选项数量统计
        2. next_node_id 引用完整性 —— options 指向的目标节点必须存在
        3. from_node_id 引用完整性 —— options 的来源节点必须存在

    参数:
        session: 数据库会话
    """
    node_count = session.query(StoryNode).count()
    choice_count = session.query(Choice).count()
    print(f"[验证] 数据库中有 {node_count} 个节点，{choice_count} 个选项")

    # ── next_node_id 引用完整性 ──────────────────────────────
    # 检查是否有选项指向不存在的目标节点
    bad_choices = session.execute(text("""
        SELECT c.id, c.next_node_id FROM choices c
        WHERE c.next_node_id NOT IN (SELECT id FROM story_nodes)
    """)).fetchall()
    if bad_choices:
        print(f"[验证] ⚠ 警告: {len(bad_choices)} 个选项指向了不存在的节点:")
        for bc in bad_choices:
            print(f"  {bc[0]} → {bc[1]}")
    else:
        print("[验证] 所有选项的 next_node_id 引用有效 ✓")

    # ── from_node_id 引用完整性 ──────────────────────────────
    # 检查是否有选项的来源节点不存在
    bad_from = session.execute(text("""
        SELECT c.id, c.from_node_id FROM choices c
        WHERE c.from_node_id NOT IN (SELECT id FROM story_nodes)
    """)).fetchall()
    if bad_from:
        print(f"[验证] ⚠ 警告: {len(bad_from)} 个选项的 from_node_id 指向了不存在的节点:")
        for bc in bad_from:
            print(f"  {bc[0]} 从 {bc[1]}")
    else:
        print("[验证] 所有选项的 from_node_id 引用有效 ✓")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    """
    直接执行此脚本以导入故事数据:
        python backend/import_story.py
    或
        cd backend && python import_story.py
    """
    import_all()
