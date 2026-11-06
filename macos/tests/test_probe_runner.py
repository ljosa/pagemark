"""The check must keep successful results and stop on either phase's failure."""
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("failed_phase", ["runtime", "editor", None])
def test_check_script_retains_reports_and_opens_only_after_both_pass(tmp_path, failed_phase):
    root = Path(__file__).resolve().parents[1]
    tools = tmp_path / "tools"
    tools.mkdir()
    fake_log = tools / "log"
    fake_open = tools / "open"
    fake_log.write_text('#!/bin/bash\nprintf "%s\\n" "test startup diagnostics"\n')
    fake_open.write_text('#!/bin/bash\ntouch .build/opened\n')
    for program in (fake_log, fake_open):
        program.chmod(0o755)
    # Substitute only the external macOS services. The production shell control
    # flow and the subprocess exit statuses are exercised without opening apps.
    script = (root / "tools/check_sandbox.command").read_text()
    script = script.replace("/usr/bin/log", '"' + str(fake_log) + '"')
    script = script.replace("/usr/bin/open", '"' + str(fake_open) + '"')
    checker = tools / "check_sandbox.command"
    checker.write_text(script)
    binary = tmp_path / "dist/Pagemark.app/Contents/MacOS/Pagemark"
    binary.parent.mkdir(parents=True)
    binary.write_text('''#!/bin/bash
case "$1" in
  --probe-runtime) phase=runtime ;;
  --probe-editor) phase=editor ;;
  *) exit 90 ;;
esac
printf '%s\n' "$phase" >> .build/invocations
printf '%s\n' "checkpoint: $phase" >&2
if [ "$phase" = "''' + str(failed_phase) + '''" ]; then
  exit 134
fi
printf '{"phase": "%s", "passed": true}\n' "$phase"
''')
    binary.chmod(0o755)
    build = tmp_path / ".build"
    build.mkdir()
    (build / "editor-probe.json").write_text("stale result")
    result = subprocess.run(["/bin/bash", str(checker)], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True)
    assert result.returncode == (134 if failed_phase else 0), result.stderr
    assert (build / "invocations").read_text().splitlines() == (
        ["runtime"] if failed_phase == "runtime" else ["runtime", "editor"])
    assert (build / "opened").exists() is (failed_phase is None)
    if failed_phase != "runtime":
        assert '"passed": true' in (build / "runtime-probe.json").read_text()
    else:
        assert (build / "editor-probe.json").read_text() == ""
    if failed_phase:
        assert "PASS:" not in result.stdout
        assert "test startup diagnostics" in (build / "launch-diagnostics.log").read_text()
        assert "checkpoint: " + failed_phase in (build / (failed_phase + "-probe.stderr")).read_text()
    archived = list(build.glob("check.*"))
    assert len(archived) == 1
    assert (archived[0] / "runtime-probe.stderr").exists()
