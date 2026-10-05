"""Rename-completeness guard (Sprint S-1): "Odysseus" may only survive in
deliberately-kept categories. Everything else must say Maven (src/brand.py).

Method: for every tracked text file outside human-owned paths, each line is
scanned case-insensitively for ``odysseus``. Allowed spans (SPAN_ALLOW) are
blanked out of the line first; whole-line contexts (comments, docstrings,
mythology, per-file exceptions) are skipped. Any line that still contains
``odysseus`` is a leftover and fails the test. Failures print file:line: text.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Human-owned paths: the fleet may not edit these, so they are not scanned.
# NOTE .env.example is a KNOWN GAP (decision D-1c-5): agents are denied access
# to it by .claude/settings.json, so its ODYSSEUS_* names cannot be reviewed here.
EXCLUDED_PREFIXES = (
    "specs/", ".github/", "website/", "assets/", "swift/", "integrations/",
    "licenses/", "config/",
    "companion/",  # human-owned optional band
)
EXCLUDED_FILES = {
    "LICENSE", "SECURITY.md", "THREAT_MODEL.md", "ROADMAP.md", "Odysseus.spec",
    "odysseus-ui.service", "setup.py", "build-macos-app.sh",
    "build-windows-portable.ps1", "start-macos.sh", "launch-windows.ps1",
    "update_windows.bat", "install-service.sh",
    ".env.example",  # KNOWN GAP D-1c-5 (blocked for agents)
}

_I = re.IGNORECASE

# ---- SPAN categories: matched text is removed from the line, then re-checked.
SPAN_ALLOW = [
    # credit and legal text kept by contract (AGPL notices, attribution)
    ("credit_contributors", re.compile(r"Odysseus contributors", _I)),
    # historical credit about the upstream project (S-1 ruling)
    ("credit_upstream", re.compile(r"upstream Odysseus('s)?", _I)),
    ("credit_based_on", re.compile(r"(based on|modified version of|fork of|forked from|derived from|renamed from)\W{1,3}(the\W+)?(original\W+)?odysseus", _I)),
    # upstream project URL / org / published image name
    ("upstream_url", re.compile(r"odysseus-dev(/odysseus)?", _I)),
    # env var names (legacy prefix still honoured by the src/brand.py alias shim)
    ("env_var_names", re.compile(r"\bODYSSEUS_[A-Z0-9_]+")),
    # X-Odysseus-* headers are wire contract
    ("x_odysseus_headers", re.compile(r"X-Odysseus[A-Za-z0-9_\-]*", _I)),
    # odysseus:// URI scheme (attachment links persisted in user data)
    ("odysseus_scheme", re.compile(r"odysseus://", _I)),
    # model ids and LoRA minimal prompts (D-1c-7: weights were trained on them)
    ("model_ids", re.compile(r"odysseus-qwen3[\w.\-]*", _I)),
    # vector collection names (renaming would orphan data)
    ("collection_names", re.compile(r"odysseus_(memories|rag|tool_index)", _I)),
    # on-disk paths/dirs load-bearing for running servers and existing installs;
    # also mounted-root and plugin-dir path segments and the human-owned asset name
    ("on_disk_paths", re.compile(
        r"(\.cache/odysseus|\.config/odysseus[\w\-]*|/odysseus[\w.\-/]*|\.odysseus[\w.\-]*"
        r"|\.cache\" / \"odysseus|Path\(\"odysseus\"\)|assets/branding/odysseus[\w.\-]*)", _I)),
    # endpoint paths kept so existing clients keep working (compose-from-odysseus)
    ("legacy_endpoints", re.compile(r"[\w\-]+-from-odysseus\w*", _I)),
    # storage / cookie / event / DOM-id keys: odysseus-x, odysseus:x, odysseus_x, odysseus.x (lowercase only)
    ("storage_event_keys", re.compile(r"odysseus[-:_.][\w\-:.]+")),
    # internal identifiers: window.__odysseus*, _odysseus*, camel/snake names containing odysseus
    ("internal_identifiers", re.compile(r"[\w$]+odysseus[\w$]*|odysseus[\w$]+", _I)),
    # docker compose service names (F-1: compose names/interpolation kept)
    ("compose_service_names", re.compile(
        r"(compose\s+(exec|logs|restart|up|run|stop)\b[^\n]*?\s|\[\"services\"\]\[\")odysseus\b"
        r"|SERVICE = \"odysseus\"", _I)),
    # reserved hostnames / mail domains in fixtures and Message-IDs (odysseus.local, .example ...)
    ("fixture_hostnames", re.compile(r"odysseus(\.(local|example|invalid|test)\b|%2e|%40|\\\\local)", _I)),
    # back-compat matching of reminders sent before the rename
    ("legacy_reminder_subject", re.compile(r"Reminder \(Odysseus\):", _I)),
    # User-Agent strings are left (D-1c-3: wire identity)
    ("user_agent_strings", re.compile(
        r"(User-Agent[\"']?\s*[:=,]\s*[\"']|_USER_AGENT\"?,\s*\"|_EDITOR_VERSION\"?,\s*\")Odysseus[\w /.]*|\"Odysseus/\d[\d.]*\"", _I)),
    # legacy CLI-name regex in the maven dispatcher (also accepts old odysseus-<x> names)
    ("legacy_cli_names_code", re.compile(r"\(\?:maven\|odysseus\)", _I)),
    # companion pairing protocol identity (wire field, not UI text)
    ("companion_wire_name", re.compile(r"\"name\": \"odysseus\"")),
    # agent-intent log tags tied to the LoRA minimal-prompt paths (D-1c-7)
    ("lora_log_tags", re.compile(r"\[agent(-intent)?\] odysseus ", _I)),
]

# ---- LINE categories: whole line skipped when its regex matches.
LINE_ALLOW = [
    # mythology / persona content, not branding
    ("mythology_persona", re.compile(r"Odysseus'?s (ten-year )?journey|king of Ithaca|Ithaca|son of Laertes", _I)),
    # explicit marker used on legacy shims
    ("legacy_alias_doc", re.compile(r"legacy alias", _I)),
    # compose service key (F-1: compose service/interpolation names kept)
    ("compose_service_key", re.compile(r"^\s*odysseus:\s*$")),
    # lines that themselves say they are the legacy fallback (old odysseus-<x> CLI names)
    ("legacy_marker", re.compile(r"legacy.*odysseus|odysseus.*legacy", _I)),
    # reminder persona table entries (preset/persona content)
    ("reminder_persona", re.compile(r"""^\s*["']odysseus["']\s*[:,\]]|^\s*\[\s*['"]odysseus['"],\s*['"]Odysseus['"]""")),
]

# Whole-file categories (path regexes).
FILE_ALLOW = [
    # src/brand.py holds the legacy alias constants by design
    ("brand_module", re.compile(r"^src/brand\.py$")),
    # legacy CLI shim filenames: scripts/odysseus, scripts/odysseus-<x>, completions
    ("legacy_cli_shims", re.compile(r"^scripts/(_completion/)?odysseus[\w.\-]*$")),
    # tests that deliberately exercise legacy names / the rename itself
    ("legacy_behaviour_tests", re.compile(r"^tests/(test_brand\w*\.py|.*odysseus.*\.py)$")),
]

# Test fixture data (tests/ only): inputs, not product output. Hostnames and
# mounted root paths are handled by SPAN_ALLOW; these cover free-text fixtures.
TEST_FIXTURE = [
    # system-prompt strings passed in as input
    ("test_system_prompt_fixture", re.compile(r"You are Odysseus\.")),
    # quoted bare tokens, query strings, exe names and sample sentences used as inputs
    ("test_sample_text_fixture", re.compile(
        r"""["']odysseus["']|odysseus (changelog|pr \d+)|Odysseus\.exe|C:\\Odysseus|alt="Odysseus"|"""
        r"built-in Odysseus calendar|start with `odysseus-`|odysseus startup|Odysseus runs on|outside Odysseus|Start Odysseus", _I)),
]

# Per-file exceptions: (path regex, line regex, reason). Keep tiny.
LINE_EXCEPTIONS = [
    # LoRA minimal prompts: odysseus-qwen3 finetunes were trained on this exact text (D-1c-7)
    (re.compile(r"^src/agent_loop\.py$"),
     re.compile(r"You are Odysseus\.|Odysseus will answer Done|Use Odysseus tool-call format"),
     "D-1c-7 LoRA minimal prompts"),
    # preset persona is a king-of-Ithaca character, left pending a human call (chat-core report)
    (re.compile(r"^static/js/presets\.js$"), re.compile(r"id: 'odysseus'|name: 'Odysseus'"),
     "preset persona, human call pending"),
    # integrations/ is human-owned and ships a plugin named odysseus; these snippets must match it
    (re.compile(r"^static/js/settings\.js$"),
     re.compile(r"\"name\": \"odysseus\"|plugins/odysseus|!= \"odysseus\"|plugin add odysseus|skills/odysseus"),
     "snippets for the human-owned integrations/ plugin"),
    # dispatcher's legacy-prefix tuple
    (re.compile(r"^scripts/maven$"), re.compile(r"_PREFIXES = "), "legacy odysseus-<x> prefix"),
    # npm lockfile package name, generated
    (re.compile(r"^package-lock\.json$"), re.compile(r"\"name\": \"odysseus\""), "npm lockfile name"),
    # container user/group created by the image entrypoint; renaming breaks volume ownership
    (re.compile(r"^docker/entrypoint\.sh$"), re.compile(r"odysseus"), "container user/group name"),
]


def _tracked_text_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8")
        if rel in EXCLUDED_FILES or rel.startswith(EXCLUDED_PREFIXES):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        text = _read_text(path)
        if text is None:
            continue  # binary (NUL-byte sniff), never "decode failed"
        yield rel, text


def _read_text(path):
    """UTF-8 text of ``path`` (undecodable bytes become U+FFFD, never a skip),
    or None only when a NUL byte in the first 8 KiB marks it binary."""
    data = Path(path).read_bytes()
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def _before(line, rx):
    """Text of ``line`` before the first match of ``rx`` (whole line if none)."""
    m = re.search(rx, line)
    return line[:m.start()] if m else line


def _comment_only(rel, line, state):
    """True if every odysseus mention on the line is in a comment/docstring
    context (left by contract, D-1c-3).

    Also advances ``state`` (docstring / block-comment tracking), so it must be
    called for every line of a file, not only lines containing the word.
    """
    stripped = line.strip()
    if stripped.startswith("//"):
        return True  # plain JS comments, and JS embedded in python/html strings
    if rel.endswith(".py"):
        n = len(re.findall(r'"""|\'\'\'', line))
        if state.get("doc"):
            if n % 2 == 1:
                state["doc"] = False
            return True
        # statement-level docstrings only (not `X = """prompt"""`)
        if re.match(r'\s*[rbuRBU]*("""|\'\'\')', line):
            if n % 2 == 1:
                state["doc"] = True
            return True
        if stripped.startswith("#"):
            return True
        return "odysseus" not in _before(line, r"\s#").lower() and bool(re.search(r"\s#", line))
    if rel.endswith((".js", ".mjs", ".ts", ".css", ".html")):
        if state.get("block"):
            if "*/" in line:
                state["block"] = False
            return True
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                state["block"] = True
            return True
        if stripped.startswith("*"):
            return True
        if rel.endswith(".html"):
            if state.get("html"):
                if "-->" in line:
                    state["html"] = False
                return True
            if stripped.startswith("<!--"):
                if "-->" not in stripped:
                    state["html"] = True
                return True
        if re.search(r"(^|\s)//", line):
            return "odysseus" not in _before(line, r"(^|\s)//").lower()
        return False
    if rel.endswith(".md"):
        if state.get("html"):
            if "-->" in line:
                state["html"] = False
            return True
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                state["html"] = True
            return True
        return False
    if rel.endswith((".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".service", ".txt")) \
            or "." not in rel.rsplit("/", 1)[-1]:
        if stripped.startswith("#"):
            return True
        return "odysseus" not in _before(line, r"\s#").lower() and bool(re.search(r"\s#", line))
    return False


def find_unallowed():
    bad = []
    for rel, text in _tracked_text_files():
        bad.extend(_scan_text(rel, text))
    return bad


def _scan_text(rel, text):
    bad = []
    if "odysseus" not in text.lower():
        return bad
    if any(rx.search(rel) for _, rx in FILE_ALLOW):
        return bad
    state = {}
    for no, line in enumerate(text.splitlines(), 1):
        comment = _comment_only(rel, line, state)  # always advance state
        if "odysseus" not in line.lower() or comment:
            continue
        if any(rx.search(line) for _, rx in LINE_ALLOW):
            continue
        if any(prx.search(rel) and lrx.search(line) for prx, lrx, _ in LINE_EXCEPTIONS):
            continue
        if rel.startswith("tests/") and any(rx.search(line) for _, rx in TEST_FIXTURE):
            continue
        rest = line
        for _, rx in SPAN_ALLOW:
            rest = rx.sub(" ", rest)
        if "odysseus" in rest.lower():
            bad.append(f"{rel}:{no}: {line.strip()[:160]}")
    return bad


def test_no_unallowed_odysseus_left():
    bad = find_unallowed()
    assert not bad, (
        f"{len(bad)} unallowed 'odysseus' line(s); user-visible text must say Maven "
        "(src/brand.py), or add a documented allow category.\n" + "\n".join(bad[:50])
    )


def test_human_owned_paths_not_scanned():
    # sanity: the exclusion list is honoured and the scan sees real files
    seen = {rel for rel, _ in _tracked_text_files()}
    assert "src/brand.py" in seen
    assert not any(r.startswith(EXCLUDED_PREFIXES) or r in EXCLUDED_FILES for r in seen)



def test_scanner_reports_leftover_in_file_with_non_utf8_bytes(tmp_path):
    f = tmp_path / "note.txt"
    f.write_bytes(b"caf\xe9 \x93quoted\x94\nWelcome to Odysseus today\n")
    text = _read_text(f)
    assert text is not None, "non-UTF-8 bytes must not mark a file binary/skipped"
    assert _scan_text("docs/note.txt", text) == ["docs/note.txt:2: Welcome to Odysseus today"]
    nul = tmp_path / "blob.bin"
    nul.write_bytes(b"\x00\x01Odysseus")
    assert _read_text(nul) is None
