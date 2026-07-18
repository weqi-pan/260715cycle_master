# backend/app/engine/condition_eval.py
import re
from app.schemas.game import GameState


class ConditionEvaluator:
    """Parse condition expression strings and evaluate them against a GameState."""

    def check(self, condition: str | None, state: GameState) -> bool:
        """null/empty string means no constraint, always returns True."""
        if condition is None or condition.strip() == "":
            return True
        return self.evaluate(condition, state)

    def evaluate(self, condition: str, state: GameState) -> bool:
        condition = condition.strip()

        # -- and --
        if condition.startswith("and:"):
            inner = condition[4:]
            parts = self._split_top_level(inner)
            return all(self.evaluate(p, state) for p in parts)

        # -- or --
        if condition.startswith("or:"):
            inner = condition[3:]
            parts = self._split_top_level(inner)
            return any(self.evaluate(p, state) for p in parts)

        # -- not --
        if condition.startswith("not:"):
            inner = condition[4:]
            return not self.evaluate(inner, state)

        # -- has_item --
        if condition.startswith("has_item:"):
            item_id = condition[9:]
            return any(item.get("id") == item_id for item in state.inventory)

        # -- has_flag --
        if condition.startswith("has_flag:"):
            flag_name = condition[9:]
            return bool(state.flags.get(flag_name))

        # -- flag:NAME=VALUE --
        m = re.match(r"^flag:([^=]+)=(.+)$", condition)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            actual = state.flags.get(flag_name)
            return str(actual) == expected

        # -- attr:NAME OP VALUE --
        m = re.match(r"^attr:(\w+)(>=|<=|>|<|==|!=)(.+)$", condition)
        if m:
            attr_name, op, raw_val = m.group(1), m.group(2), m.group(3)
            attr_val = state.player_attributes.get(attr_name, 0)
            try:
                cmp_val = int(raw_val)
            except ValueError:
                cmp_val = float(raw_val)
            if op == ">=": return attr_val >= cmp_val
            if op == "<=": return attr_val <= cmp_val
            if op == ">":  return attr_val > cmp_val
            if op == "<":  return attr_val < cmp_val
            if op == "==": return attr_val == cmp_val
            if op == "!=": return attr_val != cmp_val

        # -- cycle --
        m = re.match(r"^cycle>=(\d+)$", condition)
        if m:
            return state.cycle_count >= int(m.group(1))

        # -- half_cycle --
        m = re.match(r"^half_cycle>=(\d+)$", condition)
        if m:
            return state.half_cycle_count >= int(m.group(1))

        # -- at_node --
        m = re.match(r"^at_node:(.+)$", condition)
        if m:
            return state.current_node_id == m.group(1)

        raise ValueError(f"Unknown condition expression: {condition}")

    def _split_top_level(self, text: str) -> list[str]:
        """Split at top-level commas, respecting and:/or: nesting.

        When and:/or: is encountered the nesting depth increases,
        so commas inside a sub-expression are not treated as split
        points for the containing expression.
        """
        parts = []
        depth = 0
        current: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            remaining = text[i:]

            # Enter sub-expression when we see and:/or:
            if remaining.startswith("and:"):
                depth += 1
                current.extend("and:")
                i += 4
                continue

            if remaining.startswith("or:"):
                depth += 1
                current.extend("or:")
                i += 3
                continue

            if ch == ",":
                if depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    # Comma inside sub-expression -- keep it as part of token
                    current.append(ch)
                i += 1
                continue

            current.append(ch)
            i += 1

        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]
