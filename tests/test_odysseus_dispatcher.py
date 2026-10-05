import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers.cli_loader import load_script

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CLIS = [
    "backup", "calendar", "contacts", "docs", "gallery", "logs", "mail", "memory",
    "notes", "personal", "research", "signature", "skills", "tasks", "theme", "webhook",
]


def test_is_runnable_subcommand_requires_executable_file(tmp_path):
    cli = load_script("maven")
    sub = tmp_path / "maven-demo"
    sub.write_text("#!/bin/sh\n")
    sub.chmod(0o644)

    assert cli._is_runnable_subcommand(sub) is False

    sub.chmod(0o755)
    assert cli._is_runnable_subcommand(sub) is True


def _fake_scripts(tmp_path, monkeypatch, names):
    cli = load_script("maven")
    for n in names:
        p = tmp_path / n
        p.write_text('#!/bin/sh\n"""x — demo."""\n')
        p.chmod(0o755)
    monkeypatch.setattr(cli, "SCRIPTS_DIR", tmp_path)
    return cli


def test_resolve_prefers_maven_and_falls_back_to_legacy(tmp_path, monkeypatch):
    cli = _fake_scripts(tmp_path, monkeypatch, ["maven-a", "odysseus-a", "odysseus-b"])
    if os.name == "nt":
        pytest.skip("exec bit is not meaningful on Windows")
    assert cli._resolve_subcommand("a").name == "maven-a"
    assert cli._resolve_subcommand("b").name == "odysseus-b"
    assert cli._resolve_subcommand("zzz") is None
    assert cli._resolve_subcommand("../a") is None


def test_dispatch_execs_maven_subcommand(tmp_path, monkeypatch):
    cli = _fake_scripts(tmp_path, monkeypatch, ["maven-demo"])
    monkeypatch.setattr(cli, "_is_runnable_subcommand", lambda p: p.exists())
    calls = []
    monkeypatch.setattr(cli.os, "execv", lambda py, argv: calls.append(argv))
    cli.main(["demo", "--flag", "x"])
    assert calls and calls[0][1].endswith("maven-demo")
    assert calls[0][2:] == ["--flag", "x"]


def test_dispatch_unknown_subcommand(capsys):
    cli = load_script("maven")
    assert cli.main(["definitely-not-a-cli"]) == 1
    assert "maven: unknown subcommand" in capsys.readouterr().err


@pytest.mark.parametrize("name", CLIS)
def test_maven_x_dispatches(name):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "maven"), name, "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert f"maven-{name}" in r.stdout
    assert r.returncode == 0


@pytest.mark.parametrize("name", CLIS)
def test_legacy_shim_reexecs_maven_with_same_args(name):
    shim = SCRIPTS / f"odysseus-{name}"
    assert 'with_name("maven-%s")' % name in shim.read_text(encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(shim), "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert f"maven-{name}" in r.stdout
    assert r.returncode == 0
