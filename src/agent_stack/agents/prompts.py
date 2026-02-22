"""Prompt loader — reads agent system prompts from the prompts/ directory."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def load_prompt(stage: str) -> str:
    """Load the markdown prompt file for a given pipeline stage.

    Raises ``FileNotFoundError`` if the prompt file does not exist.
    """
    path = PROMPTS_DIR / f"{stage}.md"
    text = path.read_text(encoding="utf-8")
    logger.debug("Prompt loaded — stage=%s path=%s", stage, path)
    return text
