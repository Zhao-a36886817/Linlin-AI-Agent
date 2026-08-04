from __future__ import annotations

import pytest

from app.providers.tool_parser import ToolParser


def test_parse_native_ollama_tool_call() -> None:
    raw = {
        "message": {
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "calculator",
                        "arguments": {
                            "expression": "1+2",
                        },
                    },
                },
            ],
        },
    }

    assert ToolParser.parse(raw) == [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "calculator",
                "arguments": {
                    "expression": "1+2",
                },
            },
        },
    ]


def test_parse_top_level_tool_calls() -> None:
    raw = {
        "tool_calls": [
            {
                "function": {
                    "name": "calculator",
                    "arguments": '{"expression":"2+3"}',
                },
            },
        ],
    }

    result = ToolParser.parse(raw)

    assert result[0]["id"] == "tool_1"
    assert result[0]["function"]["name"] == "calculator"
    assert result[0]["function"]["arguments"] == {
        "expression": "2+3",
    }


def test_parse_xml_tool_call() -> None:
    raw = {
        "message": {
            "content": """<tool_call>
{"name":"calculator","arguments":{"expression":"3+4"}}
</tool_call>""",
        },
    }

    result = ToolParser.parse(raw)

    assert result == [
        {
            "id": "tool_1",
            "type": "function",
            "function": {
                "name": "calculator",
                "arguments": {
                    "expression": "3+4",
                },
            },
        },
    ]


def test_parse_markdown_json_tool_call() -> None:
    raw = {
        "message": {
            "content": """```json
{"name":"calculator","arguments":{"expression":"4+5"}}
```""",
        },
    }

    result = ToolParser.parse(raw)

    assert result[0]["function"]["name"] == "calculator"
    assert result[0]["function"]["arguments"] == {
        "expression": "4+5",
    }


def test_parse_markdown_without_language() -> None:
    raw = {
        "message": {
            "content": """```
{"name":"calculator","arguments":{"expression":"5+6"}}
```""",
        },
    }

    result = ToolParser.parse(raw)

    assert result[0]["function"]["arguments"] == {
        "expression": "5+6",
    }


def test_parse_plain_json_tool_call() -> None:
    raw = {
        "message": {
            "content": ('{"name":"calculator","arguments":{"expression":"6+7"}}'),
        },
    }

    result = ToolParser.parse(raw)

    assert result[0]["function"]["name"] == "calculator"
    assert result[0]["function"]["arguments"] == {
        "expression": "6+7",
    }


def test_parse_positional_function_call() -> None:
    raw = {
        "message": {
            "content": 'calculator("(25 + 5) * 8")',
        },
    }

    result = ToolParser.parse(raw)

    assert result[0]["function"] == {
        "name": "calculator",
        "arguments": {
            "expression": "(25 + 5) * 8",
        },
    }


def test_parse_keyword_function_call() -> None:
    raw = {
        "message": {
            "content": 'calculator(expression="7+8")',
        },
    }

    result = ToolParser.parse(raw)

    assert result[0]["function"] == {
        "name": "calculator",
        "arguments": {
            "expression": "7+8",
        },
    }


def test_parse_multiple_xml_tool_calls() -> None:
    raw = {
        "message": {
            "content": """<tool_call>
{"name":"calculator","arguments":{"expression":"1+1"}}
</tool_call>
<tool_call>
{"name":"calculator","arguments":{"expression":"2+2"}}
</tool_call>""",
        },
    }

    result = ToolParser.parse(raw)

    assert len(result) == 2
    assert result[0]["id"] == "tool_1"
    assert result[1]["id"] == "tool_2"


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"message": {}},
        {"message": {"content": ""}},
        {"message": {"content": "普通文字回答"}},
        {"message": {"content": "{invalid json}"}},
        {"message": {"tool_calls": "invalid"}},
        {"tool_calls": "invalid"},
    ],
)
def test_parse_returns_empty_for_unsupported_input(
    raw: dict[str, object],
) -> None:
    assert ToolParser.parse(raw) == []


def test_native_tool_calls_take_priority_over_content() -> None:
    raw = {
        "message": {
            "tool_calls": [
                {
                    "function": {
                        "name": "calculator",
                        "arguments": {
                            "expression": "10+20",
                        },
                    },
                },
            ],
            "content": 'calculator("999+999")',
        },
    }

    result = ToolParser.parse(raw)

    assert len(result) == 1
    assert result[0]["function"]["arguments"] == {
        "expression": "10+20",
    }


def test_invalid_native_call_is_ignored() -> None:
    raw = {
        "message": {
            "tool_calls": [
                {
                    "function": {
                        "arguments": {
                            "expression": "1+2",
                        },
                    },
                },
                {
                    "function": {
                        "name": "calculator",
                        "arguments": {
                            "expression": "3+4",
                        },
                    },
                },
            ],
        },
    }

    result = ToolParser.parse(raw)

    assert len(result) == 1
    assert result[0]["function"]["arguments"] == {
        "expression": "3+4",
    }


def test_rejects_non_object_json_arguments() -> None:
    raw = {
        "tool_calls": [
            {
                "function": {
                    "name": "calculator",
                    "arguments": '["1+2"]',
                },
            },
        ],
    }

    assert ToolParser.parse(raw) == []


def test_function_call_rejects_unsafe_expression_arguments() -> None:
    raw = {
        "message": {
            "content": 'calculator(__import__("os"))',
        },
    }

    assert ToolParser.parse(raw) == []
