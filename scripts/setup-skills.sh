#!/usr/bin/env bash
#
# 🧙 EEG_Waveform_Analyzer — Skills 本地安装向导
#
# 交互式脚本，引导你把 40 个 skill（38 Pocock + 2 自定义）装进本地电脑。
# 适合：Claude Code / Cursor / Codex / Gemini CLI / 或任何能读 .agents/skills/ 的 agent。
#
# 用法：
#   bash scripts/setup-skills.sh
#
# 什么这个向导而不是手动复制？
#   - 自动检查 Node.js 版本（npx skills 需要 ≥ 18）
#   - 自动 clone 或更新仓库
#   - 自动 npx skills@latest sync 同步到你的 agent
#   - 自动验证 40 个 skill 全部就位
#   - 每一步都可以 Ctrl-C 暂停、随时重跑（幂等）

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# Wizard library: delightful, consistent UX, identical across every wizard.
# ──────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""
fi

TOTAL_STAGES=0

_STAGE_INDEX=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()
WRITTEN_SECRET=()
SKIPPED=()

_clear() {
  [[ -t 1 ]] || return 0
  if command -v tput >/dev/null 2>&1 && tput clear 2>/dev/null; then return 0; fi
  printf '\033[2J\033[3J\033[H'
}

banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s  %s stages%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"
  printf '%s  This wizard installs 40 AI agent skills (38 Pocock + 2 project custom).\n' "$DIM"
  printf '  You drive the terminal; this script checks, runs commands, and verifies.%s\n\n' "$RESET"
  pause "Ready to start?"
}

stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  printf '\n%s%s▸ Stage %s/%s · %s%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"
}

say()  { printf '  %s\n' "$1"; }
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }

open_url() {
  local url="$1"
  printf '  %s↗ opening%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview     >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open        >/dev/null 2>&1; then open "$url"
    else false; fi
  } >/dev/null 2>&1 || warn "couldn't open a browser, so visit it manually: $url"
}

pause() {
  printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"
  read -r _ || true
}

confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

_existing() {
  [[ -f "$ENV_FILE" ]] || return 1
  local line value sq="'\\''"; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  value="${line#*=}"
  if [[ "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; value="${value//"$sq"/\'}"
  elif [[ "$value" == \"*\" ]]; then
    value="${value:1:${#value}-2}"
    [[ "$value" == *[\\\$\"]* ]] && return 1
  fi
  printf '%s' "$value"
}

ask() {
  local key="$1" prompt="$2" current input s=$'\001' e=$'\002' p rc=0
  current=$(_existing "$key" || true)
  p="  $s$BOLD$e$prompt$s$RESET$e "
  [[ -n "$current" ]] && p+="$s$DIM$e[Enter keeps current]$s$RESET$e "
  read -e -r -p "$p" input || rc=1
  if (( rc )) && [[ -z "$input" ]]; then return 1; fi
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

ask_secret() {
  local key="$1" prompt="$2" current input rc=0
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter keeps current]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -rs input || rc=1
  printf '\n'
  if (( rc )) && [[ -z "$input" ]]; then return 1; fi
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

write_env() {
  local key="$1" value="$2" tmp sq="'\\''"
  [[ -e "$ENV_FILE" ]] || (umask 077 && : > "$ENV_FILE")
  tmp=$(mktemp)
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf "%s='%s'\n" "$key" "${value//\'/$sq}" >> "$tmp"
  cat "$tmp" > "$ENV_FILE"
  rm -f "$tmp"
  printf -v "$key" '%s' "$value"
  WRITTEN_ENV+=("$key")
  printf '  %s✓ wrote%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"
}

set_secret() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if printf '%s' "$value" | gh secret set "$name" >/dev/null 2>&1; then
      WRITTEN_SECRET+=("$name")
      printf '  %s✓ set%s GitHub secret %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub secret $name (set it manually: gh secret set $name)")
  warn "skipped GitHub secret $name: gh not ready; set it later"
}

set_var() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if gh variable set "$name" --body "$value" >/dev/null 2>&1; then
      printf '  %s✓ set%s GitHub variable %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub variable $name")
  warn "skipped GitHub variable $name, gh not ready; set it later"
}

finish() {
  _clear
  printf '\n%s%s  ✓ Setup complete%s\n' "$BOLD" "$GREEN" "$RESET"
  (( ${#WRITTEN_ENV[@]} ))    && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"
  (( ${#WRITTEN_SECRET[@]} )) && note "set ${#WRITTEN_SECRET[@]} GitHub secret(s): ${WRITTEN_SECRET[*]}"
  if (( ${#SKIPPED[@]} )); then
    printf '\n'; warn "still to do by hand:"
    for s in "${SKIPPED[@]}"; do note "  - $s"; done
  fi
  printf '\n'
  note "Next steps:"
  note "  1. Open your AI agent (Claude Code / Cursor / Codex / ...)"
  note "  2. Open this repo as your working directory"
  note "  3. Try: '用 grilling 拷问一下我这个新项目'"
  printf '\n'
}

# ──────────────────────────────────────────────────────────────────────────
# STAGES
# ──────────────────────────────────────────────────────────────────────────

run_wizard() {

TOTAL_STAGES=6

banner "🧙 EEG_Waveform_Analyzer — Skills 本地安装"

# ── Stage 1: Node.js 检查 ───────────────────────────────────────────────
stage "检查 Node.js 环境"
say "npx skills 需要 Node.js ≥ 18。先确认你的环境。"
note "如果 Node.js 未安装或版本太低，向导会给出安装命令。"

NODE_VERSION=""
if command -v node >/dev/null 2>&1; then
  NODE_VERSION=$(node -v | sed 's/v//')
  say "已检测到 Node.js $NODE_VERSION"
  # 比较版本号
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
  if (( NODE_MAJOR >= 18 )); then
    printf '  %s✓%s Node.js 版本满足要求\n' "$GREEN" "$RESET"
  else
    warn "Node.js $NODE_VERSION 太低，需要 ≥ 18"
    echo ""
    echo "  macOS (Homebrew):    brew install node@20 && brew link node@20"
    echo "  macOS (nvm):         curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && nvm install 20"
    echo "  Windows:             winget install OpenJS.NodeJS.LTS"
    echo "  Ubuntu/Debian:       curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
    echo ""
    pause "安装好 Node.js 后，按 Enter 继续"
    # 重检
    NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' || echo "")
    [[ -z "$NODE_VERSION" ]] && { warn "Node.js 仍未检测到。请先安装再重跑向导。"; exit 1; }
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    (( NODE_MAJOR >= 18 )) || { warn "版本仍太低 ($NODE_VERSION)。请安装 ≥ 18。"; exit 1; }
  fi
else
  warn "未检测到 Node.js"
  echo ""
  echo "  请先安装 Node.js ≥ 18，推荐安装方式："
  echo "  macOS (Homebrew):    brew install node@20"
  echo "  macOS (nvm):         curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && nvm install 20"
  echo "  Windows:             winget install OpenJS.NodeJS.LTS"
  echo "  Ubuntu/Debian:       curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
  echo ""
  pause "安装好 Node.js 后，按 Enter 继续"
  NODE_VERSION=$(node -v 2>/dev/null | sed 's/v//' || echo "")
  [[ -z "$NODE_VERSION" ]] && { warn "Node.js 仍未检测到。请先安装再重跑向导。"; exit 1; }
fi

if command -v npx >/dev/null 2>&1; then
  printf '  %s✓%s npx 可用\n' "$GREEN" "$RESET"
else
  warn "npx 未检测到"
  pause "npx 通常随 npm 一起安装。如果缺失，运行 'npm install -g npx' 后继续"
fi

if command -v git >/dev/null 2>&1; then
  printf '  %s✓%s git 可用\n' "$GREEN" "$RESET"
else
  warn "git 未检测到 — 请先安装 git"
  pause "安装 git 后继续"
fi

# ── Stage 2: Clone 仓库 ────────────────────────────────────────────────
stage "Clone 仓库到本地"
say "把 GitHub 仓库拉到本地一个目录。"

REPO_URL="https://github.com/wenze42/EEG_Waveform_Analyzer.git"
open_url "https://github.com/wenze42/EEG_Waveform_Analyzer"

# 让用户选安装目录
DEFAULT_DIR="$HOME/EEG_Waveform_Analyzer"
INSTALL_DIR=""
ask INSTALL_DIR "安装目录路径?" || true
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  say "目录 $INSTALL_DIR 已存在且是 git 仓库。"
  if confirm "要更新它吗（git pull）"; then
    cd "$INSTALL_DIR"
    git pull origin main
    printf '  %s✓%s 已更新\n' "$GREEN" "$RESET"
  else
    warn "跳过 clone，继续使用现有目录"
  fi
elif [[ -d "$INSTALL_DIR" ]]; then
  warn "目录 $INSTALL_DIR 已存在但不是 git 仓库"
  if confirm "要删除它并重新 clone 吗"; then
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    printf '  %s✓%s Clone 完成\n' "$GREEN" "$RESET"
  else
    warn "请手动处理该目录后重跑向导"
    exit 1
  fi
else
  say "正在 clone…"
  git clone "$REPO_URL" "$INSTALL_DIR"
  printf '  %s✓%s Clone 完成 → %s\n' "$GREEN" "$RESET" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
printf '  %s→%s 当前目录: %s\n' "$BLUE" "$RESET" "$INSTALL_DIR"

# ── Stage 3: npx skills sync ───────────────────────────────────────────
stage "同步 40 个 skill 到 AI agent"
say "把仓库里的 skills-lock.json 指向的 40 个 skill 正确链接到"
say "你本地 AI agent（Claude Code / Cursor / Codex / Gemini CLI）的 skills 目录。"
note "如果你还没确定用哪个 agent，可以先跳过 sync，以后再运行。"

if confirm "现在运行 npx skills@latest sync"; then
  if npx --yes skills@latest sync 2>&1 | head -20; then
    printf '  %s✓%s npx skills sync 完成\n' "$GREEN" "$RESET"
  else
    warn "sync 遇到问题，可能是 network 或 agent 未安装"
    note "你可以之后手动运行: npx skills@latest sync"
    pause "继续下一步"
  fi
else
  note "跳过 sync — 以后可以手动运行: npx skills@latest sync"
fi

# ── Stage 4: 验证安装 ──────────────────────────────────────────────────
stage "验证 40 个 skill 就位"

EXPECTED_SKILLS=40
ACTUAL_SKILLS=0
if [[ -d .agents/skills ]]; then
  ACTUAL_SKILLS=$(find .agents/skills -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')
fi

printf '  .agents/skills/SKILL.md 数量: %s / %s\n' "$ACTUAL_SKILLS" "$EXPECTED_SKILLS"

if (( ACTUAL_SKILLS >= EXPECTED_SKILLS )); then
  printf '  %s✓%s 全部 %s 个 skill 就位\n' "$GREEN" "$RESET" "$ACTUAL_SKILLS"
else
  warn "只有 $ACTUAL_SKILLS / $EXPECTED_SKILLS 个 skill"
  note "如果是第一次 clone，可能是 npx skills 自动安装还没完成。"
  note "运行: npx skills@latest add mattpocock/skills --all"
fi

# 检查核心文件
echo ""
say "核心文件检查："
for f in AGENTS.md CONTEXT.md GLOSSARY.md docs/METHODOLOGY.md .agents/skills/dev-gating/SKILL.md .agents/skills/health-scoring/SKILL.md skills-lock.json; do
  if [[ -f "$f" ]]; then
    printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$f"
  else
    printf '  %s✗%s %s (缺失)\n' "$YELLOW" "$RESET" "$f"
  fi
done

# 检查自定义 skill
echo ""
say "自定义 skill 检查："
if grep -q "dev-gating" AGENTS.md 2>/dev/null; then
  printf '  %s✓%s AGENTS.md 包含 dev-gating 路由\n' "$GREEN" "$RESET"
else
  printf '  %s✗%s AGENTS.md 未包含自定义 skill 路由\n' "$YELLOW" "$RESET"
fi

pause "验证完成，按 Enter 继续"

# ── Stage 5: 打开方法论文档 ────────────────────────────────────────────
stage "浏览方法论文档"
say "仓库里有四份核心文档，推荐先读一遍："
echo ""
printf '  %s① %s%s/docs/METHODOLOGY.md%s  — 完整方法论（四失败、门禁、人机分工、插头插座）\n' "$BLUE" "$BOLD" "$RESET" "$RESET"
printf '  %s② %s%sCONTEXT.md%s             — 产品语境 + 避免表\n' "$BLUE" "$BOLD" "$RESET" "$RESET"
printf '  %s③ %s%sGLOSSARY.md%s            — 人机共用词汇表\n' "$BLUE" "$BOLD" "$RESET" "$RESET"
printf '  %s④ %s%sAGENTS.md%s              — 开发门禁硬门槛 + 40 skill 路由表\n' "$BLUE" "$BOLD" "$RESET" "$RESET"
echo ""

if confirm "在浏览器打开 docs/METHODOLOGY.md"; then
  open_url "file://$(pwd)/docs/METHODOLOGY.md"
  note "提示：浏览器渲染 markdown 可能需要插件。用 VS Code / Typora 打开效果更好。"
fi

if confirm "打开 GitHub 仓库（分享/收藏/fork）"; then
  open_url "https://github.com/wenze42/EEG_Waveform_Analyzer"
fi

# ── Stage 6: 快速上手检查 ──────────────────────────────────────────────
stage "快速上手"
say "安装完成。现在你可以："
echo ""
printf '  %s1.%s 在你的 AI agent 里打开这个仓库\n' "$BOLD" "$RESET"
printf '  %s2.%s 试试说: "用 grilling 拷问一下我这个新项目"\n' "$BOLD" "$RESET"
printf '  %s3.%s 或者说: "dev-gating，帮我建立验收矩阵"\n' "$BOLD" "$RESET"
echo ""

note "下次开新项目时，记得："
note "  • 把 CONTEXT.md 改成你新项目的语境和避免表"
note "  • 把 GLOSSARY.md 改成新项目的领域术语"
note "  • 每个项目挑 2-3 个最痛的 skill 先用，别贪多"

echo ""
finish
}

run_wizard "$@"; exit
