"""Registry-dispatched tools get the user and the chat.

Found end to end: execute_tool_block's generic registry branch called the
handler with neither, so create_file saved files with no owner (a non-admin
could not download their own file) and the chat-scoped tools saw no chat.
"""

import pytest

from src.agent_tools import ToolBlock
import src.tool_execution as te


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["create_file", "analyze_data", "search_chat_files"])
async def test_registry_tools_receive_owner_and_session(monkeypatch, tool):
    import src.agent_tools as agent_tools

    seen = {}

    async def fake(content, ctx):
        seen.update(owner=ctx.get("owner"), session_id=ctx.get("session_id"))
        return {"response": "ok", "exit_code": 0}

    monkeypatch.setitem(agent_tools.TOOL_HANDLERS, tool, fake)
    monkeypatch.setattr(te, "_owner_is_admin", lambda owner: False)
    _desc, result = await te.execute_tool_block(
        ToolBlock(tool, '{"query": "x", "operation": "describe", "format": "csv", "spec": {"rows": [["a"]]}}'),
        session_id="chat-1", owner="alice", security_context=te.NO_TOOL_SECURITY_CONTEXT,
    )
    assert result.get("exit_code") == 0, result
    assert seen == {"owner": "alice", "session_id": "chat-1"}
