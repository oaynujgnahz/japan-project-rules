#!/usr/bin/env bash
# japan-project-rules installer
# Usage: ./install.sh <path-to-CMPF-SRC> [--dry-run] [--no-skills]
# Copies the local-only rule set (and tools/*-xlsx) into a CMPF-SRC checkout, hides it from git via
# .git/info/exclude (never .gitignore), installs Cursor skills, and checks tools.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$KIT_DIR/payload"
DRY=0; SKILLS=1; TARGET=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-skills) SKILLS=0 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) TARGET="$a" ;;
  esac
done

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
run()   { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }

[ -n "$TARGET" ] || { red "Usage: ./install.sh <path-to-CMPF-SRC> [--dry-run] [--no-skills]"; exit 1; }
TARGET="$(cd "$TARGET" && pwd)"
[ -d "$TARGET/.git" ] || { red "Not a git checkout: $TARGET"; exit 1; }
# [CMPF] 用 pom.xml 中的 carbon-parent 判断目标是否为 CMPF-SRC；将来由项目配置的识别条件替换
[ -f "$TARGET/pom.xml" ] && grep -q 'carbon-parent' "$TARGET/pom.xml" \
  || yellow "Warning: $TARGET does not look like CMPF-SRC (carbon-parent not found in pom.xml). Continuing."

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/.rules-backup/$TS"
echo "Target : $TARGET"
[ "$DRY" = 1 ] && yellow "Dry run: nothing will be changed."

# 1. Copy payload (back up files that differ)
echo; echo "== 1/4 Copy rules"
copied=0; backed=0
while IFS= read -r -d '' src; do
  case "$src" in
    "$KIT_DIR/tools/"*) rel="${src#$KIT_DIR/}" ;;
    *) rel="${src#$PAYLOAD/}" ;;
  esac
  dst="$TARGET/$rel"
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then continue; fi
  if [ -f "$dst" ]; then
    run mkdir -p "$(dirname "$BACKUP/$rel")"
    run cp -p "$dst" "$BACKUP/$rel"
    backed=$((backed+1))
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp -p "$src" "$dst"
  copied=$((copied+1))
done < <(find "$PAYLOAD" "$KIT_DIR/tools" -type f ! -name '.DS_Store' ! -name '*.pyc' ! -path '*/__pycache__/*' -print0)
# [CMPF] mvn8 是 CMPF-SRC 专用的 Java 8 Maven 包装脚本；中文注释 hook 属对日项目要求
run chmod +x "$TARGET/mvn8" "$TARGET/.cursor/hooks/check-no-chinese-comments.py"
green "  copied/updated: $copied file(s); backed up: $backed (→ ${BACKUP#$TARGET/})"

# 2. Hide from git (local only)
echo; echo "== 2/4 Hide rule files from git (.git/info/exclude)"
EXCL="$TARGET/.git/info/exclude"
BEGIN="# >>> japan-project-rules (local only, do not commit) >>>"
END="# <<< japan-project-rules <<<"
# [CMPF] /mvn8、/e2e/、/scripts/ 是 CMPF-SRC 特有条目；将来由项目配置的本地专用清单替换
ENTRIES="/AGENTS.md
/mvn8
/.cursor/
/.github/pull_request_template.md
/docs/
/e2e/
/scripts/
/tools/design-xlsx/
/tools/unit-test-xlsx/
/.rules-backup/"
if [ "$DRY" = 1 ]; then
  echo "  [dry-run] write block to $EXCL"
else
  mkdir -p "$(dirname "$EXCL")"; touch "$EXCL"
  tmp="$(mktemp)"
  awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$EXCL" > "$tmp"
  { cat "$tmp"; echo "$BEGIN"; echo "$ENTRIES"; echo "$END"; } > "$EXCL"
  rm -f "$tmp"
fi
# [CMPF] mvn8、e2e 是 CMPF-SRC 特有文件和目录
tracked="$(cd "$TARGET" && git ls-files -- AGENTS.md mvn8 .cursor .github/pull_request_template.md e2e | head -5)"
if [ -n "$tracked" ]; then
  red "  Some rule files are TRACKED by git in this checkout (exclude does not hide them):"
  echo "$tracked" | sed 's/^/    /'
else
  green "  rule files are untracked and now hidden from git status"
fi

# 3. Skills
echo; echo "== 3/4 Install Cursor skills (~/.cursor/skills)"
if [ "$SKILLS" = 1 ]; then
  for s in "$KIT_DIR"/skills/*/; do
    name="$(basename "$s")"; dst="$HOME/.cursor/skills/$name"
    if [ -d "$dst" ] && diff -rq "$s" "$dst" >/dev/null 2>&1; then
      echo "  $name: up to date"; continue
    fi
    if [ -d "$dst" ]; then run mv "$dst" "$dst.bak.$TS"; echo "  $name: old version → $name.bak.$TS"; fi
    run mkdir -p "$HOME/.cursor/skills"
    run cp -R "$s" "$dst"
    green "  $name: installed"
  done
else
  echo "  skipped (--no-skills)"
fi

# 4. Environment check
echo; echo "== 4/4 Environment check"
ok=1
# [CMPF] Java 8 + Maven（./mvn8）检查属 CMPF 技术栈；将来由项目配置的环境检查替换
mv_out="$(cd "$TARGET" && ./mvn8 -v 2>&1 || true)"
if echo "$mv_out" | grep -q 'Java version: 1\.8'; then
  green "  Java 8 + Maven: OK ($(echo "$mv_out" | grep -m1 'Java version' | sed 's/,.*//'))"
else
  red "  ./mvn8 failed: install Java 8 / Maven, or set JAVA8_HOME / MAVEN_BIN (see ./mvn8 -v)"; ok=0
fi
command -v python3 >/dev/null && green "  python3: OK (Chinese-comment hook)" || { red "  python3 not found (needed by .cursor/hooks)"; ok=0; }
if command -v python3 >/dev/null; then
  if python3 -c 'import openpyxl' 2>/dev/null; then green "  openpyxl: OK (tools/*-xlsx)"; else yellow "  openpyxl missing: python3 -m pip install openpyxl  (needed by tools/design-xlsx, tools/unit-test-xlsx)"; fi
  if python3 -c 'import PIL' 2>/dev/null; then green "  Pillow: OK"; else yellow "  Pillow missing: python3 -m pip install pillow  (only when a 画面設計書 contains images)"; fi
fi
# [CMPF] frontend 期望 Node v16.14.0 属 CMPF 技术栈；将来由项目配置替换
if command -v node >/dev/null; then
  v="$(node -v)"; green "  node: $v (frontend expects v16.14.0)"
else
  yellow "  node not found (needed for frontend build / e2e)"
fi

echo
[ "$ok" = 1 ] && green "Done." || yellow "Done with warnings (see above)."
cat <<MSG

Next:
  - Open $TARGET in Cursor; rules under .cursor/rules apply automatically.
  - Optional MCP: cp .cursor/mcp.json.example .cursor/mcp.json and fill a READ-ONLY account.
  - Optional e2e: cd e2e && npm install && npx playwright install chromium
  - Never commit the rule files (they are client-invisible by design).
MSG
