# backend/app/config.py
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'cycle_master.db')}"
STORY_DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "story_data")
