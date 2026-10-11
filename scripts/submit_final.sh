#!/usr/bin/env bash
# The final-case submission in one command:
#
#   scripts/submit_final.sh <case_folder> <mock_url> [--push] [--deadline SECONDS] [--reuse]
#
#   --reuse: do not rebuild; commit the artifacts of the last build.py run (out/final.*, traces/final.jsonl, traces/final.build.log)
#            exactly as reviewed, with the run_command taken from the trace's run_start event.
#
#   1. commits the case folder unchanged (the organisers' zip, extracted)
#   2. runs the builder in its final-case form:  build.py <case_folder> <mock_url>   (slot "final")
#   3. scans the generated artifacts for credentials and commits them ("Final case build")
#   4. writes submission.json (team, members, repo from submission/config.json; commit; run_command; workflow; trace; mock_url), commits it
#   5. --push pushes the current branch (3 attempts); otherwise prints the push command
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
push=0; deadline=1800; reuse=0; args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --push) push=1 ;;
    --reuse) reuse=1 ;;
    --deadline) deadline="$2"; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) args+=("$1") ;;
  esac
  shift
done
[ "${#args[@]}" = "2" ] || { echo "usage: scripts/submit_final.sh <case_folder> <mock_url> [--push]" >&2; exit 2; }
folder="${args[0]}"; mock="${args[1]}"
[ -d "$folder" ] || { echo "not a directory: $folder" >&2; exit 2; }
[ -f .env ] || { echo "no .env" >&2; exit 2; }
set -a; . ./.env; set +a
log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
if [ -z "$(git config user.email)" ] || [ -z "$(git config user.name)" ]; then
  team=$($PY -c "import json;print(json.load(open('submission/config.json'))['team'])")
  export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-$(git config user.name)}"; export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-$team}"
  export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-$(git config user.email)}"; export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-submission@localhost}"
  export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
fi

# 1. the inputs, unchanged (converted copies the builder writes under <folder>/_text are committed with the artifacts)
git add -- "$folder"
if git diff --cached --quiet -- "$folder"; then log "inputs already committed"; else git commit -q -m "Final case inputs (unchanged)" -- "$folder"; log "committed inputs: $(git rev-parse --short HEAD)"; fi

# 2. the build
run_start=$(mktemp); touch "$run_start"
cmd="source .env && $PY build.py '$folder' '$mock' --deadline $deadline"
status=ok
if [ "$reuse" = "1" ]; then
  [ -f traces/final.jsonl ] && [ -f out/final.workflow.json ] || { log "--reuse: no previous build (traces/final.jsonl / out/final.workflow.json missing)"; exit 1; }
  cmd=$($PY - <<'EOF3'
import json, shlex
with open("traces/final.jsonl") as f:
    for line in f:
        e = json.loads(line)
        if e.get("event") == "run_start":
            argv = e.get("argv") or []
            print("source .env && .venv/bin/python " + " ".join(shlex.quote(a) for a in argv)); break   # argv[0] is build.py
EOF3
)
  [ -n "$cmd" ] || { log "--reuse: the trace has no run_start event"; exit 1; }
  log "reusing the last build: $cmd"
  touch -d '2000-01-01' "$run_start"
else
  log "build: $cmd"
  if bash -c "$cmd" 2>&1 | tee traces/final.build.log; then log "build finished"; else status=FAILED; log "build FAILED (see traces/final.build.log)"; fi
fi

# 3. scan + commit the artifacts
arts=()
for f in out/final.workflow.json traces/final.jsonl traces/final.build.log out/final.policy.json out/final.audit.json out/final.candidate.json; do
  if [ -f "$f" ] && [ "$f" -nt "$run_start" ]; then arts+=("$f"); fi
done
rm -f "$run_start"
[ "${#arts[@]}" -gt 0 ] || { log "no artifacts produced; nothing to commit"; exit 1; }
$PY scripts/check_artifacts.py "${arts[@]}" || { log "artifact scan FAILED: fix before committing (never commit credentials)"; exit 1; }
git add -- "${arts[@]}" "$folder"
[ -d mock ] && git add -- mock .gitignore 2>/dev/null || true     # the team's mock source travels with the submission commit
if git diff --cached --quiet; then log "artifacts unchanged since the last commit"; else git commit -q -m "Final case build"; fi
commit=$(git rev-parse HEAD); log "artifacts committed: $commit"

# 4. submission.json
$PY - "$commit" "$cmd" "$mock" <<'EOF2'
import json, sys
commit, cmd, mock = sys.argv[1:4]
cfg = json.load(open("submission/config.json"))
# run_command in the organisers' placeholder form (they substitute their own folder and mock URL); the literal command of this
# run is in the trace's run_start.argv and in traces/final.build.log. Needs .env (FREYA_API_KEY, FREYA_BANK_TEAM_KEY) and requirements.txt.
sub = {"team": cfg["team"], "members": cfg.get("members", []), "repo": cfg["repo"], "commit": commit,
       "run_command": "python3 build.py {case_folder} {mock_url}", "workflow": "out/final.workflow.json", "trace": "traces/final.jsonl", "mock_url": mock}
json.dump(sub, open("submission.json", "w"), indent=2, ensure_ascii=False); open("submission.json", "a").write("\n")
print(json.dumps(sub, indent=2, ensure_ascii=False))
EOF2
git add submission.json
git diff --cached --quiet -- submission.json || git commit -q -m "Submission file" -- submission.json
log "submission.json committed: $(git rev-parse --short HEAD) (commit field = $commit, the artifacts commit)"

# 5. push
cur=$(git rev-parse --abbrev-ref HEAD)
if [ "$push" = "1" ]; then
  pushed=0
  for attempt in 1 2 3; do if git push -u origin "$cur"; then log "pushed $cur"; pushed=1; break; fi; log "push attempt $attempt failed; retrying in 30 s"; sleep 30; done
  [ "$pushed" = "1" ] || { log "PUSH FAILED; the commits exist locally — run: git push -u origin $cur"; exit 1; }
else
  log "not pushed; run: git push -u origin $cur"
fi
printf '\nbuild: %s   submission.json written (mock_url %s)\n' "$status" "$mock"
[ "$status" = "ok" ]
