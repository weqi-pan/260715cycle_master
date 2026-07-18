# backend/app/config.py
from .paths import DATABASE_PATH, STORY_DATA_DIR

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
