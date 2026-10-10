#!/usr/bin/env bash
# Sunday 16:30 pre-flight: everything the two hidden builds need, checked before the briefs open.
#
#   scripts/preflight.sh [--with-build]      # --with-build also runs the ~20 s rehearsal build (--policy fixture) on slot rehearsal-a
#
# Prints PASS/WARN/FAIL per check and exits 1 if any check FAILS. Read-only apart from the optional rehearsal build.
set -u
cd "$(dirname "$0")/.."
fail=0; warn=0
pass() { printf 'PASS  %s\n' "$*"; }
warnf() { printf 'WARN  %s\n' "$*"; warn=$((warn + 1)); }
failf() { printf 'FAIL  %s\n' "$*"; fail=$((fail + 1)); }

now_utc=$(date -u +%H:%M); printf 'Pre-flight at %s UTC (briefs open 17:00 UTC, submission closes 20:00 UTC)\n' "$now_utc"

# 1. repo + tree
head=$(git rev-parse --short HEAD 2>/dev/null) || { failf "not a git repository"; }
dirty=$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')
if [ "$dirty" = "0" ]; then pass "git tree clean at $head"; else warnf "git tree has $dirty modified tracked file(s) at $head: commit or stash before 17:00 (git status)"; fi
if [ -n "$(git config user.email)" ] && [ -n "$(git config user.name)" ]; then pass "git identity set (user.name and user.email)"; else warnf "git identity incomplete (user.name='$(git config user.name)', email $([ -n "$(git config user.email)" ] && echo set || echo missing)): commits fail with 'Author identity unknown'; submit.sh falls back to the team name, or run git config --global user.name 'Your Name'"; fi
git remote get-url origin >/dev/null 2>&1 && pass "git remote origin: $(git remote get-url origin)" || warnf "no git remote 'origin': submit.sh can commit but not push; add the GitHub remote"

# 2. venv + imports
if [ -x .venv/bin/python ]; then
  if .venv/bin/python -c "import policy, compile, extract, freya, bankcal, claude_agent_sdk" 2>/dev/null; then pass "venv imports (pipeline + claude_agent_sdk)"; else failf "venv exists but imports fail: uv pip install --python .venv/bin/python -r requirements.txt"; fi
else failf "no .venv: uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt"; fi

# 3. .env + keys
if [ -f .env ]; then
  set -a; . ./.env; set +a
  [ -n "${FREYA_API_KEY:-}" ] && pass "FREYA_API_KEY set" || failf "FREYA_API_KEY missing in .env"
  [ -n "${FREYA_BANK_TEAM_KEY:-}" ] && pass "FREYA_BANK_TEAM_KEY set" || failf "FREYA_BANK_TEAM_KEY missing in .env"
else failf "no .env (cp env.example .env and fill the keys)"; fi

# 4. Claude credentials for the extractor (same env treatment as extract._prepare_env)
if command -v claude >/dev/null 2>&1; then
  key="${ANTHROPIC_API_KEY:-}"; keyopt=()
  case "$key" in sk-ant-*) ;; *) keyopt=(-u ANTHROPIC_API_KEY) ;; esac
  if command -v timeout >/dev/null 2>&1; then to=(timeout 90); else to=(); warnf "GNU timeout not installed (macOS: brew install coreutils); running claude -p without a time limit"; fi
  out=$("${to[@]}" env -u CLAUDECODE -u CLAUDE_CODE_CHILD_SESSION "${keyopt[@]}" claude -p "say OK" 2>&1 | tail -1)
  case "$out" in *OK*|*ok*|*Ok*) pass "claude -p answers (${out:0:40})" ;; *) failf "claude -p failed: ${out:0:120} -> run 'claude' then /login, or put a real ANTHROPIC_API_KEY in .env" ;; esac
else failf "claude CLI not on PATH: npm install -g @anthropic-ai/claude-code"; fi

# 5. offline tests
if [ -x .venv/bin/python ]; then
  t=$(.venv/bin/python -m pytest tests/ -q 2>&1 | tail -1)
  case "$t" in *passed*|*"no tests"*) case "$t" in *failed*|*error*) failf "pytest: $t" ;; *) pass "pytest: $t" ;; esac ;; *) failf "pytest: $t" ;; esac
fi

# 6. platform + bank mock health, no simulation running
if [ -x .venv/bin/python ] && [ -n "${FREYA_API_KEY:-}" ]; then
  pyout=$(.venv/bin/python - <<'EOF'
import json, os, sys, urllib.request
sys.path.insert(0, ".")
import freya
try:
    ws = freya.workspace_id(); print(f"PASS  Freya API reachable (workspace {ws[:8]}…)")
    r = freya.api("GET", "/api/v2/simulations", workspaceId=ws, limit=20)
    sims = r.get("simulations") or r.get("items") or r
    live = [s for s in sims if str(s.get("status", "")).lower() in ("running", "in_progress", "pending", "queued", "starting")]
    print(("WARN  " if live else "PASS  ") + (f"{len(live)} simulation(s) still running: {[s.get('id') for s in live]} (wait or DELETE /api/v2/simulations/<id>)" if live else "no simulation running in the workspace"))
except Exception as e:
    print(f"FAIL  Freya API: {str(e)[:160]}")
try:
    req = urllib.request.Request("https://freya-bank-mock.freyavoice.workers.dev/v1/practice/sessions", data=json.dumps({"case": "PUB-01"}).encode(),
                                 headers={"content-type": "application/json", "x-team-key": os.environ.get("FREYA_BANK_TEAM_KEY", ""), "user-agent": "freya-bank-scorer/0.1"}, method="POST")
    s = json.loads(urllib.request.urlopen(req, timeout=30).read()); print("PASS  bank mock healthy (practice session created)")
except Exception as e:
    print(f"WARN  bank mock: {str(e)[:120]} (hidden builds do not need it; the public self-test does)")
EOF
)
  printf '%s\n' "$pyout"
  fail=$((fail + $(printf '%s\n' "$pyout" | grep -c '^FAIL' || true)))
  warn=$((warn + $(printf '%s\n' "$pyout" | grep -c '^WARN' || true)))
fi

# 7. slot registry
if [ -f .freya-agents.json ]; then pass ".freya-agents.json present ($(.venv/bin/python -c "import json;print(','.join(sorted(json.load(open('.freya-agents.json')))))" 2>/dev/null | cut -c1-120))"; else warnf ".freya-agents.json missing: hidden-1/hidden-2 will be created as new workflows (fine, but note it)"; fi

# 8. submission config
if [ -f submission/config.json ] && .venv/bin/python -c "import json,sys;c=json.load(open('submission/config.json'));sys.exit(0 if c.get('team') and c.get('repo') and '<' not in c['team']+c['repo'] else 1)" 2>/dev/null; then pass "submission/config.json has team and repo"; else warnf "submission/config.json missing or still a placeholder (team, repo): submit.sh needs it"; fi

# 9. optional rehearsal build
if [ "${1:-}" = "--with-build" ]; then
  if .venv/bin/python build.py --policy tests/fixtures/brief_a.policy.json --openapi tools/openapi.json --slot rehearsal-a >"${TMPDIR:-/tmp}/preflight-build.log" 2>&1; then pass "rehearsal build (policy fixture, slot rehearsal-a) green"; else failf "rehearsal build failed: see ${TMPDIR:-/tmp}/preflight-build.log"; fi
fi

printf '\n%d warning(s), %d failure(s)\n' "$warn" "$fail"
[ "$fail" = "0" ] || exit 1
