from genesis.generator import build_generation_prompt


def test_prompt_contains_description():
    prompt = build_generation_prompt("A tool that echoes a message.", None, set())
    assert "A tool that echoes a message." in prompt


def test_prompt_contains_name_hint():
    prompt = build_generation_prompt("Echo tool.", "echo_message", set())
    assert "echo_message" in prompt


def test_prompt_contains_rules():
    prompt = build_generation_prompt("Any tool.", None, set())
    assert "TOOL_SCHEMA" in prompt
    assert "handler" in prompt
    assert "ALLOWED IMPORTS" in prompt
    assert "FORBIDDEN" in prompt


def test_prompt_lists_existing_names():
    existing = {"create_tool", "list_tools", "get_weather"}
    prompt = build_generation_prompt("A tool.", None, existing)
    for name in existing:
        assert name in prompt


def test_prompt_no_name_hint_omits_hint_line():
    prompt = build_generation_prompt("A tool.", None, set())
    assert "Suggested tool name:" not in prompt


def test_prompt_with_name_hint_includes_hint_line():
    prompt = build_generation_prompt("A tool.", "my_tool", set())
    assert "Suggested tool name: my_tool" in prompt
