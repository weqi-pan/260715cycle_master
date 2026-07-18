# backend/app/models/save.py
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, Index, UniqueConstraint
from ..database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Save(Base):
    __tablename__ = "saves"

    id = Column(String, primary_key=True, default=generate_uuid)
    save_name = Column(String, nullable=False)
    created_at = Column(String, nullable=False)  # ISO 8601
    updated_at = Column(String, nullable=False)
    current_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    cycle_count = Column(Integer, default=0)
    half_cycle_count = Column(Integer, default=0)
    inventory_json = Column(Text, default="[]")
    flags_json = Column(Text, default="{}")
    visited_nodes_json = Column(Text, default="[]")
    player_attributes_json = Column(Text, default="{}")
    endings_reached_json = Column(Text, default="[]")


class NodePersistentState(Base):
    __tablename__ = "node_persistent_state"

    id = Column(String, primary_key=True, default=generate_uuid)
    save_id = Column(String, ForeignKey("saves.id"), nullable=False)
    node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    items_json = Column(Text, default="[]")
    dangers_json = Column(Text, default="[]")

    __table_args__ = (
        UniqueConstraint("save_id", "node_id"),
        Index("idx_persist_save", "save_id"),
    )
