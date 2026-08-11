import os
import subprocess
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).parents[1] / "Linlin-Agent.bat"
HELPER = Path(__file__).parents[1] / "scripts" / "windows_launcher.ps1"


def source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_launcher_has_all_requested_commands() -> None:
    text = HELPER.read_text(encoding="utf-8").casefold()
    for command in ("install", "install-training", "run", "install-run", "stop", "verify", "smoke", "help"):
        assert f'"{command}"' in text


def test_launcher_exposes_bounded_optional_training_install() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert "function Install-TrainingDependencies" in text
    assert '"backend") + "[training]"' in text
    assert '"install-training" { Install-TrainingDependencies }' in text


def test_launcher_uses_hidden_owned_processes_and_pid_files() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert "Start-Process" in text
    assert "-WindowStyle Hidden" in text
    assert "session.json" in text
    assert "StartTime.ToUniversalTime" in text
    assert "Stop-Process -Id $process.Id -Force" in text
    assert "$process.WaitForExit(5000)" in text


def test_launcher_opens_dedicated_browser_and_waits_for_close() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert "--app=http://127.0.0.1:$FrontendPort" in text
    assert "--user-data-dir=" in text
    assert "Save-BrowserState $window" in text
    assert "Stop-ProfileBrowserProcesses $state.browser_profile" in text
    assert "Stop-OwnedProcess $state.browser" in text
    assert "$window.WaitForExit()" in text
    assert "finally" in text
    assert "Stop-Linlin" in text


def test_cleanup_is_restricted_to_named_temp_directory() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert 'Join-Path $env:TEMP "Linlin-Agent-launcher"' in text
    assert "(Split-Path $target -Parent) -ne $temp" in text
    assert '(Split-Path $target -Leaf) -ne "Linlin-Agent-launcher"' in text
    assert "for ($attempt = 1; $attempt -le 8; $attempt++)" in text
    assert "Temporary launcher files remain locked" in text


def test_each_run_uses_a_unique_dedicated_browser_profile() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert '"browser-profile-" + [guid]::NewGuid()' in text
    assert "browser_profile" in text


def test_launcher_does_not_hardcode_a_user_profile() -> None:
    text = source() + HELPER.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in text
    assert "$env:USERPROFILE" in text


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher integration")
def test_launcher_executes_real_startup_and_cleanup_smoke() -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(LAUNCHER), "smoke"],
        cwd=LAUNCHER.parent,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Hidden startup and shutdown smoke passed." in result.stdout
    assert not (Path(os.environ["TEMP"]) / "Linlin-Agent-launcher").exists()
