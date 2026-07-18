# backend/import_story.py
"""将 story_data/ 下的 JSON 文件导入 SQLite 数据库。"""
import json
import os
from sqlalchemy import text
from app.database import SessionLocal, init_db
from app.models.story import StoryNode, Choice
from app.config import STORY_DATA_DIR


def import_all():
    init_db()

    # 清空已有故事数据
    with SessionLocal() as session:
        session.execute(text("DELETE FROM choices"))
        session.execute(text("DELETE FROM node_persistent_state"))
        session.execute(text("DELETE FROM saves"))
        session.execute(text("DELETE FROM story_nodes"))
        session.commit()

    with SessionLocal() as session:
        _import_nodes(session)
        _import_choices(session)
        session.commit()
        _verify(session)


def _import_nodes(session):
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
            cycle_variants_json=json.dumps(data.get("cycle_variants", {}), ensure_ascii=False),
            color_palette=data.get("color_palette"),
            atmosphere_json=json.dumps(data.get("atmosphere", []), ensure_ascii=False),
            sensory=data.get("sensory"),
            gender_variant_json=json.dumps(data.get("gender_variant"), ensure_ascii=False) if data.get("gender_variant") else None,
            # Note: JSON files use "parent_node" key (not "parent_node_id")
            parent_node_id=data.get("parent_node"),
            trigger_condition=data.get("trigger_condition"),
            crossing_config_json=json.dumps(data.get("crossing_config"), ensure_ascii=False) if data.get("crossing_config") else None,
            warp_config_json=json.dumps(data.get("warp_config"), ensure_ascii=False) if data.get("warp_config") else None,
            shortcut_config_json=json.dumps(data.get("shortcut_config"), ensure_ascii=False) if data.get("shortcut_config") else None,
            npc_item_mapping_json=json.dumps(data.get("npc_item_mapping"), ensure_ascii=False) if data.get("npc_item_mapping") else None,
            scene_items_json=json.dumps(data.get("scene_items"), ensure_ascii=False) if data.get("scene_items") else None,
        )
        session.add(node)
        count += 1
    print(f"[import_nodes] Imported {count} nodes")


def _import_choices(session):
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
    print(f"[import_choices] Imported {count} choices")


def _verify(session):
    node_count = session.query(StoryNode).count()
    choice_count = session.query(Choice).count()
    print(f"[verify] Database has {node_count} nodes, {choice_count} choices")

    # 引用完整性检查
    bad_choices = session.execute(text("""
        SELECT c.id, c.next_node_id FROM choices c
        WHERE c.next_node_id NOT IN (SELECT id FROM story_nodes)
    """)).fetchall()
    if bad_choices:
        print(f"[verify] WARNING: {len(bad_choices)} choices point to non-existent nodes:")
        for bc in bad_choices:
            print(f"  {bc[0]} -> {bc[1]}")
    else:
        print("[verify] All choice targets valid OK")

    # from_node_id 引用完整性检查
    bad_from = session.execute(text("""
        SELECT c.id, c.from_node_id FROM choices c
        WHERE c.from_node_id NOT IN (SELECT id FROM story_nodes)
    """)).fetchall()
    if bad_from:
        print(f"[verify] WARNING: {len(bad_from)} choices have from_node_id pointing to non-existent nodes:")
        for bc in bad_from:
            print(f"  {bc[0]} from {bc[1]}")
    else:
        print("[verify] All choice from_node_id targets valid OK")


if __name__ == "__main__":
    import_all()
