"""Tests for the prompt loader."""

from agent_stack.agents.prompts import PROMPTS_DIR, load_prompt


def test_prompts_dir_exists():
    assert PROMPTS_DIR.exists()


def test_load_fetch_prompt():
    prompt = load_prompt("fetch")
    assert "Fetch" in prompt
    assert len(prompt) > 0


def test_load_all_prompts():
    stages = ["fetch", "review", "draft", "edit", "publish"]
    for stage in stages:
        prompt = load_prompt(stage)
        assert isinstance(prompt, str)
        assert len(prompt) > 50, f"Prompt for {stage} seems too short"


def test_prompt_files_exist():
    stages = ["fetch", "review", "draft", "edit", "publish"]
    for stage in stages:
        path = PROMPTS_DIR / f"{stage}.md"
        assert path.exists(), f"Missing prompt file: {path}"
