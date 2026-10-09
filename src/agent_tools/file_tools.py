"""create_file: build an Excel / Word / PowerPoint / PDF / CSV file for the user.

Thin agent wrapper over src/file_store.create_owned_file. The file is stored as
the requesting user's own upload and reached through its download link.
"""
import asyncio
from typing import Dict

from src.file_builder import FileSpecError
from src.tool_utils import _parse_tool_args

_SPEC_KEYS = ("title", "subtitle", "blocks", "text", "rows", "sheets", "slides")


class CreateFileTool:
    async def execute(self, content: str, ctx: dict) -> Dict:
        from src.file_store import FileStoreUnavailable, create_owned_file

        try:
            args = _parse_tool_args(content)
        except ValueError:
            return {"error": "Invalid JSON arguments", "exit_code": 1}
        fmt = str(args.get("format") or "").strip().lower()
        spec = args.get("spec")
        if not isinstance(spec, dict):
            # Models often put the content fields at the top level.
            spec = {k: args[k] for k in _SPEC_KEYS if k in args}
        try:
            out = await asyncio.to_thread(
                create_owned_file, fmt, spec, args.get("filename") or "", ctx.get("owner"), "agent")
        except FileSpecError as e:
            return {"error": f"Could not create the file: {e}", "exit_code": 1}
        except FileStoreUnavailable as e:
            return {"error": str(e), "exit_code": 1}
        except Exception as e:  # upload store refusals (size, type) arrive as HTTPException
            return {"error": f"Could not save the file: {getattr(e, 'detail', e)}", "exit_code": 1}
        return {
            "response": f"Created [{out['name']}]({out['url']}) ({out['size']:,} bytes).",
            "file": out,
            "exit_code": 0,
        }


class SearchChatFilesTool:
    """search_chat_files: passages from this chat's own documents (src/session_knowledge.py)."""

    async def execute(self, content: str, ctx: dict) -> Dict:
        from src import session_knowledge

        try:
            args = _parse_tool_args(content)
        except ValueError:
            args = {"query": content}
        query = str(args.get("query") or "").strip()
        if not query:
            return {"error": "Need a query", "exit_code": 1}
        session_id = ctx.get("session_id")
        if not session_id:
            return {"error": "No chat is active, so there are no chat files to search", "exit_code": 1}
        passages = await asyncio.to_thread(
            session_knowledge.search, session_id, ctx.get("owner"), query, args.get("k") or 5)
        return {"response": session_knowledge.format_results(passages, query), "exit_code": 0}


TABLE_EXTENSIONS = (".xlsx", ".xlsm", ".csv", ".tsv")


def chat_upload_ids(session_id: str, owner) -> list[tuple[str, str]]:
    """(upload id, name) of files this user attached to this chat, newest first."""
    import json as _json

    from core.database import ChatMessage, Session, SessionLocal
    from src.attachment_refs import attachment_refs_from_metadata

    db = SessionLocal()
    try:
        sess = db.query(Session.owner).filter(Session.id == session_id).first()
        if sess is None or sess[0] != owner:
            return []
        rows = (db.query(ChatMessage.meta_data)
                .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user",
                        ChatMessage.meta_data.isnot(None))
                .order_by(ChatMessage.timestamp.desc()).limit(200).all())
    finally:
        db.close()
    out = []
    for (raw,) in rows:
        try:
            meta = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        except ValueError:
            continue
        for ref in reversed(attachment_refs_from_metadata(meta if isinstance(meta, dict) else {})):
            out.append((ref["attachment_id"], str(ref.get("name") or ref["attachment_id"])))
    return out


def latest_table_upload(session_id: str, owner) -> str | None:
    """Id of the newest spreadsheet attached to this chat by this user."""
    for upload_id, name in chat_upload_ids(session_id, owner):
        if name.lower().endswith(TABLE_EXTENSIONS) or upload_id.lower().endswith(TABLE_EXTENSIONS):
            return upload_id
    return None


class AnalyzeDataTool:
    """analyze_data: exact figures from the user's own Excel/CSV upload (src/data_analysis.py)."""

    async def execute(self, content: str, ctx: dict) -> Dict:
        from src import data_analysis
        from src.tool_utils import get_upload_handler

        try:
            args = _parse_tool_args(content)
        except ValueError:
            return {"error": "Invalid JSON arguments", "exit_code": 1}
        file_id = str(args.get("file_id") or args.get("upload_id") or args.get("id") or "").strip()
        session_id = ctx.get("session_id")
        if not session_id:
            return {"error": "analyze_data works on files attached to a chat; no chat is active", "exit_code": 1}
        attached = await asyncio.to_thread(chat_upload_ids, session_id, ctx.get("owner"))
        if not file_id:
            file_id = next((u for u, n in attached
                            if n.lower().endswith(TABLE_EXTENSIONS) or u.lower().endswith(TABLE_EXTENSIONS)), "")
        if not file_id:
            return {"error": "No spreadsheet is attached to this chat. Ask the user to attach the "
                             ".xlsx or .csv file here.", "exit_code": 1}
        # Only files the user attached to THIS chat: the tool reads what was
        # already shared here, never the rest of their uploads.
        if file_id not in {u for u, _ in attached}:
            return {"error": f"'{file_id}' is not attached to this chat. Attach the file here first.",
                    "exit_code": 1}
        handler = get_upload_handler()
        if handler is None:
            return {"error": "File storage is not ready", "exit_code": 1}
        # Strictly the caller's own uploads: no admin override for agent reads.
        info = await asyncio.to_thread(handler.resolve_upload, file_id, owner=ctx.get("owner"), allow_admin=False)
        if not info or not info.get("path"):
            return {"error": f"No uploaded file '{file_id}' that you can read", "exit_code": 1}

        def work():
            table = data_analysis.load_table(info["path"], info.get("name") or info.get("original_name") or "",
                                             args.get("sheet"), args.get("header_row") or 1)
            return data_analysis.run(table, args)

        try:
            result = await asyncio.to_thread(work)
        except data_analysis.AnalysisError as e:
            return {"error": str(e), "exit_code": 1}
        except Exception as e:
            return {"error": f"Could not read the file: {e}", "exit_code": 1}
        return {"response": data_analysis.to_markdown(result), "result": result, "exit_code": 0}
