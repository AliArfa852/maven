"""Asking for an office file must put create_file in front of the model.

Found in an end-to-end run: "make a revenue deck with a chart" selected only
memory/ask_user/update_plan, so the model could not create the file.
"""

import pytest

from src import agent_loop


@pytest.mark.parametrize("prompt", [
    "make a revenue deck with a chart",
    "put this in an excel spreadsheet",
    "export the table as csv",
    "turn this into a powerpoint presentation",
    "can you give me a pdf report of the numbers",
    "make a word doc with these minutes",
    "draw a bar chart of sales by region",
])
def test_file_requests_select_create_file(prompt):
    intent = agent_loop._classify_agent_request([], prompt)
    assert "documents" in intent["domains"], intent
    tools = set()
    for d in intent["domains"]:
        tools |= agent_loop._DOMAIN_TOOL_MAP.get(d, set())
    assert "create_file" in tools
    assert "create_file" in {s["function"]["name"] for s in agent_loop.FUNCTION_TOOL_SCHEMAS
                             if s.get("function", {}).get("name") in tools}


@pytest.mark.parametrize("prompt", ["what's the weather in Paris", "hi there", "remind me to buy milk"])
def test_unrelated_requests_do_not(prompt):
    assert "documents" not in agent_loop._classify_agent_request([], prompt)["domains"]
