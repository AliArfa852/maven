"""Every route refuses anonymous callers unless it is on the reviewed public list.

The app builds its auth exemptions by hand (AUTH_EXEMPT_EXACT, prefixes and
patterns in app.py). A route added under an exempt prefix, or an exemption
widened by mistake, would be open to anyone on the network. This walks the
real route table of the real app with authentication on and no session, and
compares what answers against the list below. Adding a public route means
adding it here on purpose.

Runs in a subprocess: app.py reads AUTH_ENABLED and the data folder at import.
The lifespan is not started (no background jobs), and nothing is sent with a
session, so handlers behind the middleware never run.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (method, path template) that may answer without a session. Each one either
# serves the login page and its assets, or checks its own credential.
PUBLIC = {
    ("GET", "/login"),
    ("POST", "/api/auth/setup"),        # refuses once an account exists
    ("POST", "/api/auth/signup"),       # refuses unless an Admin opened sign-up
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/status"),        # says whether you are signed in
    ("GET", "/api/auth/policy"),        # password rules + monitoring notice
    ("GET", "/api/auth/features"),      # which UI features are on
    ("GET", "/api/auth/settings"),      # scrubbed copy for non-admins (no keys)
    ("GET", "/api/auth/integrations/presets"),  # catalogue, api_key stripped
    ("GET", "/api/health"),
    ("GET", "/api/version"),
    ("POST", "/api/tasks/{task_id}/webhook/{token}"),  # the path token is the credential
}

PROBE = textwrap.dedent(
    """
    import json, re
    import bcrypt
    from pathlib import Path
    import os

    data = Path(os.environ["MAVEN_AI_DATA_DIR"])
    (data / "auth.json").write_text(json.dumps({"users": {"admin": {
        "password_hash": bcrypt.hashpw(b"pw-123456789", bcrypt.gensalt(4)).decode(),
        "is_admin": True}}}))

    from fastapi.routing import APIRoute
    from starlette.routing import Mount
    from fastapi.testclient import TestClient
    import app as app_module

    def walk(routes):
        # FastAPI >= 0.140 keeps included routers as _IncludedRouter wrappers;
        # effective_candidates() yields their routes with the final path.
        for r in routes:
            if hasattr(r, "effective_candidates"):
                yield from walk(r.effective_candidates())
            else:
                yield r

    def methods_of(r):
        m = getattr(r, "methods", None)
        if m is None and getattr(r, "starlette_route", None) is not None:
            m = getattr(r.starlette_route, "methods", None)
        return m

    client = TestClient(app_module.app, follow_redirects=False)  # no lifespan: no `with`
    answered = []
    seen = set()
    for route in walk(app_module.app.routes):
        if isinstance(route, Mount) or not methods_of(route):
            continue
        path = route.path
        concrete = re.sub(r"{[^}:]+(:path)?}", "x", path)
        for method in sorted(methods_of(route)):
            if method in ("HEAD", "OPTIONS") or (method, path) in seen:
                continue
            seen.add((method, path))
            r = client.request(method, concrete)
            refused = r.status_code == 401 or (
                r.status_code in (302, 303, 307) and "/login" in r.headers.get("location", ""))
            if not refused:
                answered.append([method, path, r.status_code])
    print("RESULT=" + json.dumps({"answered": answered, "checked": len(seen)}))
    """
)


def test_anonymous_callers_only_reach_the_public_routes(tmp_path):
    env = os.environ.copy()
    env.update({
        "AUTH_ENABLED": "true",
        "LOCALHOST_BYPASS": "false",
        "MAVEN_AI_DATA_DIR": str(tmp_path),
        "DATABASE_URL": f"sqlite:///{tmp_path / 'app.db'}",
        "CHROMADB_CONNECT_TIMEOUT": "0.01",
        "CHROMADB_HOST": "127.0.0.1",
        "CHROMADB_PORT": "9",
        "MAVEN_AI_DISABLE_MCP": "1",
        "OPENAI_API_KEY": "",
        "PYTHONPATH": str(ROOT),
        "PYTHON_DOTENV_DISABLED": "1",
    })
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stderr[-3000:]
    line = next(l for l in result.stdout.splitlines() if l.startswith("RESULT="))
    payload = json.loads(line.removeprefix("RESULT="))

    assert payload["checked"] > 300, "route table looks empty; did the app import change?"
    answered = {(m, p) for m, p, _status in payload["answered"]}
    unexpected = sorted(answered - PUBLIC)
    statuses = {(m, p): st for m, p, st in payload["answered"]}
    assert not unexpected, (
        "These routes answer without a session. Protect them, or add them to "
        "PUBLIC with a reason: " + ", ".join(f"{m} {p} -> {statuses[(m, p)]}" for m, p in unexpected)
    )
    gone = sorted(PUBLIC - answered)
    assert not gone, f"Listed as public but now refuse anonymous callers (update PUBLIC): {gone}"
