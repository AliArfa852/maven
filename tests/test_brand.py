"""Tests for src/brand.py: constants, env alias shim, DATA_DIR wiring."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src import brand
from src.brand import BRAND_NAME, apply_env_aliases

ROOT = Path(__file__).resolve().parent.parent


def test_constants():
    assert brand.BRAND_NAME == "Maven"
    assert brand.BRAND_SLUG == "maven"
    assert brand.ENV_PREFIX == "MAVEN_AI_"
    assert brand.LEGACY_ENV_PREFIX == "ODYSSEUS_"
    assert brand.UPSTREAM_NAME == "Odysseus"
    assert brand.UPSTREAM_URL == "https://github.com/odysseus-dev/odysseus"
    assert brand.SOURCE_URL.startswith("https://")


def test_legacy_only():
    env = {"ODYSSEUS_FOO": "legacy"}
    apply_env_aliases(env)
    assert env == {"ODYSSEUS_FOO": "legacy", "MAVEN_AI_FOO": "legacy"}


def test_new_only():
    env = {"MAVEN_AI_FOO": "new"}
    apply_env_aliases(env)
    assert env == {"ODYSSEUS_FOO": "new", "MAVEN_AI_FOO": "new"}


def test_both_set_new_wins():
    env = {"MAVEN_AI_FOO": "new", "ODYSSEUS_FOO": "old"}
    apply_env_aliases(env)
    assert env["MAVEN_AI_FOO"] == "new"
    assert env["ODYSSEUS_FOO"] == "new"


def test_empty_new_value_still_wins():
    env = {"MAVEN_AI_FOO": "", "ODYSSEUS_FOO": "old"}
    apply_env_aliases(env)
    assert env["MAVEN_AI_FOO"] == ""
    assert env["ODYSSEUS_FOO"] == ""


def test_idempotent():
    env = {"MAVEN_AI_A": "1", "ODYSSEUS_A": "2", "ODYSSEUS_B": "3", "OTHER": "x"}
    apply_env_aliases(env)
    first = dict(env)
    apply_env_aliases(env)
    assert env == first


def test_unrelated_untouched():
    env = {"PATH": "/bin", "ODYSSEUS": "bare", "MAVEN_AI_": "bare2", "FOO": "x"}
    apply_env_aliases(env)
    assert env == {"PATH": "/bin", "ODYSSEUS": "bare", "MAVEN_AI_": "bare2", "FOO": "x"}


def test_never_prints_values(capsys):
    apply_env_aliases({"ODYSSEUS_SECRET": "s3cr3t-value"})
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def _data_dir_in_subprocess(extra_env):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MAVEN_AI_", "ODYSSEUS_"))}
    env.update(extra_env)
    r = subprocess.run(
        [sys.executable, "-c", "from src.constants import DATA_DIR; print(DATA_DIR)"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr[-500:]
    return r.stdout.strip().splitlines()[-1]


def test_data_dir_honours_new_name(tmp_path):
    assert _data_dir_in_subprocess({"MAVEN_AI_DATA_DIR": str(tmp_path)}) == str(tmp_path)


def test_data_dir_honours_legacy_name(tmp_path):
    assert _data_dir_in_subprocess({"ODYSSEUS_DATA_DIR": str(tmp_path)}) == str(tmp_path)


def test_data_dir_new_wins(tmp_path):
    new, old = tmp_path / "new", tmp_path / "old"
    got = _data_dir_in_subprocess(
        {"MAVEN_AI_DATA_DIR": str(new), "ODYSSEUS_DATA_DIR": str(old)})
    assert got == str(new)


def test_js_brand_parity():
    js = ROOT / "static" / "js" / "brand.js"
    assert js.exists(), "static/js/brand.js must exist (S-1 stage 4: hard requirement)"
    text = js.read_text(encoding="utf-8")
    m = re.search(r"name\s*:\s*[\"']([^\"']+)[\"']", text)
    assert m, "brand.js declares no name"
    assert m.group(1) == BRAND_NAME


def test_maven_env_prefers_new_name_and_falls_back_to_legacy():
    assert brand.maven_env("MAVEN_AI_X", "d", environ={"MAVEN_AI_X": "new", "ODYSSEUS_X": "old"}) == "new"
    assert brand.maven_env("MAVEN_AI_X", "d", environ={"ODYSSEUS_X": "old"}) == "old"
    assert brand.maven_env("MAVEN_AI_X", "d", environ={}) == "d"
    # Set-but-empty new name still wins (D-0-3), same as apply_env_aliases.
    assert brand.maven_env("MAVEN_AI_X", "d", environ={"MAVEN_AI_X": "", "ODYSSEUS_X": "old"}) == ""
    with pytest.raises(ValueError):
        brand.maven_env("ODYSSEUS_X")
