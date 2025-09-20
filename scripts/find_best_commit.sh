#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
RANGE="${1:-origin/main~100..origin/main}"
ARTIFACT_DIR="$ROOT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

if ORIG_REF=$(git symbolic-ref --quiet --short HEAD 2>/dev/null); then
  ORIG_REF="$ORIG_REF"
else
  ORIG_REF=""
fi
ORIG_COMMIT="$(git rev-parse HEAD)"

TMP_DIR="$(mktemp -d)"
cp "$ROOT_DIR/scripts/run_smoke.sh" "$TMP_DIR/run_smoke.sh"
cp "$ROOT_DIR/tools/smoke_score.py" "$TMP_DIR/smoke_score.py"
chmod +x "$TMP_DIR/run_smoke.sh"

STASHED=0
if ! git diff --quiet --ignore-submodules --exit-code || ! git diff --cached --quiet --ignore-submodules --exit-code; then
  git stash push -k -u -m "find-best-smoke" >/dev/null
  STASHED=1
fi

mkdir -p "$ARTIFACT_DIR"

cleanup() {
  set +e
  if [[ -n "$ORIG_REF" ]]; then
    git checkout -f "$ORIG_REF" >/dev/null 2>&1
  else
    git checkout -f "$ORIG_COMMIT" >/dev/null 2>&1
  fi
  if [[ $STASHED -eq 1 ]]; then
    git stash pop >/dev/null 2>&1 || true
  fi
  if [[ -n "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

SCORES_CSV="$ARTIFACT_DIR/scores.csv"
echo "commit,score" >"$SCORES_CSV"

BEST_SCORE=-1
BEST_COMMIT=""

mapfile -t COMMITS < <(git rev-list --first-parent --reverse "$RANGE")

for COMMIT in "${COMMITS[@]}"; do
  git checkout -f "$COMMIT" >/dev/null 2>&1

  set +e
  OUTPUT=$(cd "$ROOT_DIR" && SMOKE_RUNNER_OVERRIDE="$TMP_DIR/smoke_score.py" bash "$TMP_DIR/run_smoke.sh" 2>&1)
  set -e

  SCORE=$(echo "$OUTPUT" | awk -F '=' '/SCORE=/{print $2; exit}' | tr -d '\r')
  if [[ -z "$SCORE" ]]; then
    SCORE=0
  fi

  echo "$COMMIT,$SCORE" >>"$SCORES_CSV"

  if [[ $SCORE -gt $BEST_SCORE ]]; then
    BEST_SCORE=$SCORE
    BEST_COMMIT=$COMMIT
  fi

  if [[ -n "$OUTPUT" ]]; then
    echo "$OUTPUT" >&2
  fi

  if [[ $BEST_SCORE -ge 100 ]]; then
    break
  fi

done

if [[ -z "$BEST_COMMIT" ]]; then
  BEST_COMMIT="$ORIG_COMMIT"
fi

echo "$BEST_COMMIT" >"$ARTIFACT_DIR/best-commit.txt"
echo "Best commit: $BEST_COMMIT"
