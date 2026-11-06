#!/bin/bash
# Run from a normal macOS Terminal session, outside the agent's process sandbox.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p .build/fixtures
pagemark_fixture_dir=$(mktemp -d "$PWD/.build/fixtures/probe.XXXXXX")
pagemark_check_dir=$(mktemp -d "$PWD/.build/check.XXXXXX")
printf '%s\n' 'pagemark-disposable-sandbox-fixture' > "$pagemark_fixture_dir/unselected.txt"
printf '%s\n' 'Checking the signed Pagemark app. No print job will be submitted.'
# Each invocation retains its reports; the well-known paths contain only the
# latest run, including an empty editor report if the runtime phase fails.
for pagemark_report in runtime-probe editor-probe; do
  : > ".build/$pagemark_report.json"
  : > ".build/$pagemark_report.stderr"
done

run_probe() {
  local mode="$1" name="$2"
  local started probe_pid status
  local args=("$mode")
  if [ "$mode" = '--probe-runtime' ]; then
    args+=(--denied-file "$pagemark_fixture_dir/unselected.txt")
  fi
  started=$(/bin/date '+%Y-%m-%d %H:%M:%S')
  dist/Pagemark.app/Contents/MacOS/Pagemark "${args[@]}" \
    > "$pagemark_check_dir/$name.json" 2> "$pagemark_check_dir/$name.stderr" &
  probe_pid=$!
  if wait "$probe_pid"; then
    status=0
  else
    status=$?
  fi
  cp "$pagemark_check_dir/$name.json" ".build/$name.json"
  cp "$pagemark_check_dir/$name.stderr" ".build/$name.stderr"
  cat ".build/$name.json"
  cat ".build/$name.stderr"
  if [ "$status" -ne 0 ]; then
    printf '\n%s\n' "FAIL: $name exited with status $status (PID $probe_pid)."
    # Run in the user's Terminal; the agent execution sandbox cannot read the
    # unified log. Limit collection to this test and its process identifier.
    if /usr/bin/log show --style compact --start "$started" \
      --predicate "process == \"Pagemark\" OR (process == \"sandboxd\" AND eventMessage CONTAINS \"Pagemark\") OR eventMessage CONTAINS \"$probe_pid\"" \
      > "$pagemark_check_dir/launch-diagnostics.log" \
      2> "$pagemark_check_dir/diagnostics.stderr"; then
      cp "$pagemark_check_dir/launch-diagnostics.log" .build/launch-diagnostics.log
      printf '%s\n' 'macOS startup diagnostics saved to .build/launch-diagnostics.log.'
    else
      printf '%s\n' 'macOS log collection was unavailable; the probe reports are retained.'
    fi
  fi
  return "$status"
}

printf '\n%s\n' 'Phase 1: bundled runtime and sandbox.'
if run_probe --probe-runtime runtime-probe; then
  printf '\n%s\n' 'Phase 1 passed. Phase 2: native application and editor.'
  if run_probe --probe-editor editor-probe; then
    pagemark_probe_status=0
    printf '\n%s\n' 'PASS: both phases passed. Opening the editor preview.'
    /usr/bin/open "$PWD/dist/Pagemark.app" || pagemark_probe_status=$?
  else
    pagemark_probe_status=$?
  fi
else
  pagemark_probe_status=$?
fi
printf '%s\n' "Reports retained in $pagemark_check_dir"
printf '%s\n' 'Latest results: .build/runtime-probe.{json,stderr} and .build/editor-probe.{json,stderr}.'
if [ -t 0 ]; then
  read -r -p 'Press Return to close this check. ' || true
fi
exit "$pagemark_probe_status"

