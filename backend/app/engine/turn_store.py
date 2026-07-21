"""进程内一次性 Turn 状态仓库，阻止客户端篡改和响应重放。"""

from threading import Lock
from uuid import uuid4

from ..schemas.game import GameState


class TurnStore:
    def __init__(self):
        self._states: dict[str, GameState] = {}
        self._lock = Lock()

    def issue(self, state: GameState, previous_turn_id: str | None = None) -> str:
        with self._lock:
            if previous_turn_id:
                self._states.pop(previous_turn_id, None)
            turn_id = uuid4().hex
            self._states[turn_id] = state.model_copy(deep=True)
            return turn_id

    def get(self, turn_id: str) -> GameState | None:
        with self._lock:
            state = self._states.get(turn_id)
            return state.model_copy(deep=True) if state else None

    def consume(self, turn_id: str) -> GameState | None:
        """原子取出并删除 Turn，保证并发请求只有一个成功。"""
        with self._lock:
            state = self._states.pop(turn_id, None)
            return state.model_copy(deep=True) if state else None

    def restore(self, turn_id: str, state: GameState | None) -> None:
        """业务校验失败时恢复原 Turn，允许玩家修正后重试。"""
        if state is None:
            return
        with self._lock:
            self._states[turn_id] = state.model_copy(deep=True)
