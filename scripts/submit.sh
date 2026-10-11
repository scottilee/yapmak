#!/usr/bin/env bash
# The Sunday submission in one command (SUBMISSION.md steps 2-5):
#
#   scripts/submit.sh <hidden-1 dir> <hidden-2 dir> [--push] [--branch NAME] [--fast] [--deadline SECONDS]
#
#   1. commits the two input directories unchanged
#   2. runs build 1, then build 2 (sequential; a failed build 1 does not stop build 2)
#   3. scans the generated artifacts for credentials, commits them ("Hidden brief builds")
#   4. writes submission/form.json from submission/config.json ({"team", "repo"}) with that commit hash, commits it
#   5. --push pushes the branch (needs remote origin); otherwise prints the push command
#
# Input dirs: every file except the OpenAPI JSON is a brief document, read in sorted file-name order (name them
# 01-..., 02-... when order matters). The OpenAPI file is the .json whose top level has "paths".
# --branch NAME   do everything on a new branch (rehearsals) instead of the current one
# --fast          rehearsal of the mechanics only: skips extraction (--policy tests/fixtures/brief_a.policy.json)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

push=0; branch=""; fast=0; deadline=1800; dirs=()
while [ $# -gt 0 ]; do
  case "$1" in
    --push) push=1 ;;
    --branch) branch="$2"; shift ;;
    --fast) fast=1 ;;
    --deadline) deadline="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) dirs+=("$1") ;;
  esac
  shift
done
[ "${#dirs[@]}" = "2" ] || { echo "usage: scripts/submit.sh <hidden-1 dir> <hidden-2 dir> [--push] [--branch NAME] [--fast]" >&2; exit 2; }
[ -f .env ] || { echo "no .env" >&2; exit 2; }
[ -f submission/config.json ] || { echo "submission/config.json missing: {\"team\": \"...\", \"repo\": \"https://github.com/...\"}" >&2; exit 2; }
set -a; . ./.env; set +a
log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
# git identity: required for commits; fall back to the team name so a fresh machine cannot stall the submission
if [ -z "$(git config user.email)" ] || [ -z "$(git config user.name)" ]; then
  team=$($PY -c "import json;print(json.load(open('submission/config.json'))['team'])")
  export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-$(git config user.name)}"; export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-$team}"
  export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-$(git config user.email)}"; export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-submission@localhost}"
  export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
  echo "WARN incomplete git identity; committing as '$GIT_AUTHOR_NAME <$GIT_AUTHOR_EMAIL>' (git config --global user.name/user.email to change)"
fi

inputs() {   # <dir> -> "briefs,comma,separated<TAB>openapi"
  $PY - "$1" <<'EOF'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
files = sorted(p for p in d.iterdir() if p.is_file() and not p.name.startswith("."))
def is_api(p):
    if p.suffix not in (".json", ".yaml", ".yml"):
        return False
    try:
        doc = json.loads(p.read_text()) if p.suffix == ".json" else __import__("yaml").safe_load(p.read_text())
    except Exception:
        return False
    return isinstance(doc, dict) and "paths" in doc
api = [p for p in files if is_api(p)]
if len(api) != 1:
    sys.exit(f"{d}: expected exactly one OpenAPI file (JSON or YAML with top-level 'paths'), found {[p.name for p in api]}")
briefs = [p for p in files if p not in api]
if not briefs:
    sys.exit(f"{d}: no brief documents")
print(",".join(str(p) for p in briefs) + "\t" + str(api[0]))
EOF
}

if [ -n "$branch" ]; then git checkout -b "$branch"; log "on branch $branch"; fi
for d in "${dirs[@]}"; do [ -d "$d" ] || { echo "not a directory: $d" >&2; exit 2; }; done

# 1. commit the inputs unchanged
git add -- "${dirs[0]}" "${dirs[1]}"
if git diff --cached --quiet -- "${dirs[0]}" "${dirs[1]}"; then log "inputs already committed"; else git commit -q -m "Hidden brief inputs (unchanged)" -- "${dirs[0]}" "${dirs[1]}"; log "committed inputs: $(git rev-parse --short HEAD)"; fi

# 2. the two builds, sequentially (only artifacts written from here on are committed; stale files from earlier runs are not)
run_start=$(mktemp); touch "$run_start"
cmds=(); status=()
for i in 1 2; do
  d="${dirs[$((i - 1))]}"
  IFS=$'\t' read -r briefs openapi < <(inputs "$d")
  if [ "$fast" = "1" ]; then
    cmd="source .env && $PY build.py --policy tests/fixtures/brief_a.policy.json --openapi tools/openapi.json --slot hidden-$i"   # mechanics only: practice policy + practice API
  else
    cmd="source .env && $PY build.py --briefs '$briefs' --openapi '$openapi' --slot hidden-$i --deadline $deadline"
  fi
  cmds+=("$cmd")
  log "build $i: $cmd"
  if bash -c "$cmd" 2>&1 | tee "traces/hidden-$i.build.log"; then status+=("ok"); log "build $i finished"; else status+=("FAILED"); log "build $i FAILED (see traces/hidden-$i.build.log); continuing"; fi
done

# 3. scan + commit the outputs
arts=()
for i in 1 2; do for f in out/hidden-$i.workflow.json traces/hidden-$i.jsonl out/hidden-$i.policy.json out/hidden-$i.audit.json out/hidden-$i.candidate.json; do
  if [ -f "$f" ]; then if [ "$f" -nt "$run_start" ]; then arts+=("$f"); else log "skipping $f: not written by this run (stale)"; fi; fi
done; done
rm -f "$run_start"
[ "${#arts[@]}" -gt 0 ] || { log "no artifacts produced; nothing to commit"; exit 1; }
$PY scripts/check_artifacts.py "${arts[@]}" || { log "artifact scan FAILED: fix before committing (never commit credentials)"; exit 1; }
git add -- "${arts[@]}"
if git diff --cached --quiet -- "${arts[@]}"; then log "artifacts unchanged since the last commit"; else git commit -q -m "Hidden brief builds" -- "${arts[@]}"; fi
commit=$(git rev-parse HEAD); log "artifacts committed: $commit"

# 4. the form
$PY - "$commit" "${cmds[0]}" "${cmds[1]}" <<'EOF'
import json, sys
commit, c1, c2 = sys.argv[1:4]
cfg = json.load(open("submission/config.json"))
form = {"team": cfg["team"], "repo": cfg["repo"], "commit": commit,
        "run_command": c1 + " && " + c2,
        "workflows": {"hidden-1": "out/hidden-1.workflow.json", "hidden-2": "out/hidden-2.workflow.json"},
        "traces": {"hidden-1": "traces/hidden-1.jsonl", "hidden-2": "traces/hidden-2.jsonl"}}
json.dump(form, open("submission/form.json", "w"), indent=2); open("submission/form.json", "a").write("\n")
print(json.dumps(form, indent=2))
EOF
git add submission/form.json
git diff --cached --quiet -- submission/form.json || git commit -q -m "Submission form" -- submission/form.json
log "form committed: $(git rev-parse --short HEAD) (form.commit = $commit, the artifacts commit)"

# 5. push
cur=$(git rev-parse --abbrev-ref HEAD)
if [ "$push" = "1" ]; then
  pushed=0
  for attempt in 1 2 3; do
    if git push -u origin "$cur"; then log "pushed $cur"; pushed=1; break; fi
    log "push attempt $attempt failed; retrying in 30 s"; sleep 30
  done
  if [ "$pushed" != "1" ]; then log "PUSH FAILED (authentication or remote); the commits exist locally — fix the remote/credentials and run: git push -u origin $cur"; exit 1; fi
else
  log "not pushed; run: git push -u origin $cur"
fi
printf '\nbuild 1: %s   build 2: %s\nsubmit commit %s   form: submission/form.json\n' "${status[0]}" "${status[1]}" "$commit"
[ "${status[0]}" = "ok" ] && [ "${status[1]}" = "ok" ]
