from collections import deque
from typing import List, Tuple

class ConversationMemory:
    """
    Lightweight conversation memory module.
    Maintains a rolling window of conversation history.
    """
    def __init__(self, max_turns: int = 6):
        # each turn is user + assistant, so 2 * max_turns
        self._history = deque(maxlen=max_turns * 2)

    def add_user(self, text: str) -> None:
        """Appends a user message to the memory."""
        self._history.append(("user", text))

    def add_assistant(self, text: str) -> None:
        """Appends an assistant message to the memory."""
        self._history.append(("assistant", text))

    def format_history(self) -> str:
        """
        Formats the history as a string.
        Returns empty string if history is empty.
        """
        if not self._history:
            return ""
            
        lines = []
        for role, text in self._history:
            if role == "user":
                lines.append(f"Human: {text}")
            elif role == "assistant":
                lines.append(f"Assistant: {text}")
                
        return "\n".join(lines) + "\n"

    def get_history(self) -> List[Tuple[str, str]]:
        """Returns a list copy of the deque contents."""
        return list(self._history)

    def clear(self) -> None:
        """Clears the deque."""
        self._history.clear()

    def __len__(self) -> int:
        """Returns the number of messages (not turns)."""
        return len(self._history)
