# backend/app/models/story.py
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base


class StoryNode(Base):
    __tablename__ = "story_nodes"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    position = Column(Float, nullable=False)
    node_type = Column(String, nullable=False, default="normal")
    time_label = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    background = Column(String, nullable=True)
    cycle_variants_json = Column(Text, nullable=True, default="{}")
    color_palette = Column(String, nullable=True)
    ambient = Column(String, nullable=True)
    atmosphere_json = Column(Text, nullable=True, default="[]")
    sensory = Column(Text, nullable=True)
    gender_variant_json = Column(Text, nullable=True)
    parent_node_id = Column(String, nullable=True)
    trigger_condition = Column(String, nullable=True)
    crossing_config_json = Column(Text, nullable=True)
    warp_config_json = Column(Text, nullable=True)
    shortcut_config_json = Column(Text, nullable=True)
    npc_item_mapping_json = Column(Text, nullable=True)
    scene_items_json = Column(Text, nullable=True)

    choices = relationship("Choice", back_populates="from_node",
                           foreign_keys="Choice.from_node_id")


class Choice(Base):
    __tablename__ = "choices"

    id = Column(String, primary_key=True)
    from_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    text = Column(String, nullable=False)
    short_text = Column(String, nullable=True)
    next_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    condition = Column(String, nullable=True)
    effects_json = Column(Text, nullable=False, default="[]")
    priority = Column(Integer, default=99)
    hint = Column(String, nullable=True)
    is_hidden_when_locked = Column(Integer, default=0)
    transition_text = Column(Text, nullable=True)

    from_node = relationship("StoryNode", back_populates="choices",
                             foreign_keys=[from_node_id])

    __table_args__ = (
        Index("idx_choices_from", "from_node_id"),
    )
