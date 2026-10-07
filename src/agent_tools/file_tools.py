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
