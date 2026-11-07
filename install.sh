#!/usr/bin/env bash
# Установка агента «FinEx» (сопровождение ликвидации фондов FinEx).
#   ./install.sh                 -> Hermes Agent: отдельный профиль "finex" (команда `finex chat`)
#   ./install.sh hermes-default  -> Hermes Agent: только навык в основной профиль
#   ./install.sh openclaw        -> OpenClaw: навык ~/.openclaw/skills/finex-liquidation
#   ./install.sh claude          -> Claude Code: навык ~/.claude/skills/finex-liquidation + субагент finex
#   ./install.sh codex           -> Codex CLI: навык ~/.codex/skills/finex-liquidation
#   ./install.sh all             -> всё, что установлено
# Hermes: каталог берётся из HERMES_HOME, на Windows — %LOCALAPPDATA%/hermes, иначе ~/.hermes.
# Данные (портфель, документы, новости) — в ~/finex-desk (переменная FINEX_DESK), вне репозитория.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$HERE/skills/finance/finex-liquidation"
TARGET="${1:-hermes}"

PY="$(command -v python3 || command -v python || command -v py || true)"
if [[ -n "${HERMES_HOME:-}" ]]; then HH="$HERMES_HOME"
elif [[ -n "${LOCALAPPDATA:-}" && -d "$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || echo "$LOCALAPPDATA")/hermes" ]]; then
  HH="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || echo "$LOCALAPPDATA")/hermes"
else HH="$HOME/.hermes"; fi

copy_skill() {
  mkdir -p "$(dirname "$1")"
  rm -rf "$1"
  cp -r "$SKILL_SRC" "$1"
  chmod +x "$1/scripts/"*.py
  echo "Навык -> $1"
}

install_hermes() {
  local home="$HH/profiles/finex"
  if [[ ! -d "$home" ]]; then
    echo "Создаю профиль Hermes 'finex' (копия текущих ключей/модели)..."
    hermes profile create finex --clone
  fi
  cp "$HERE/SOUL.md" "$home/SOUL.md"
  echo "SOUL.md -> $home/SOUL.md"
  copy_skill "$home/skills/finance/finex-liquidation"
  echo "Hermes: запустите 'finex chat'"
}

install_hermes_default() {
  copy_skill "$HH/skills/finance/finex-liquidation"
  echo "Hermes: новая сессия или /reset"
}

install_openclaw() {
  copy_skill "$HOME/.openclaw/skills/finex-liquidation"
  echo "OpenClaw: перезапустите gateway/сессию. Характер агента: добавьте $HERE/SOUL.md в SOUL.md workspace"
  echo "  или создайте отдельного агента с workspace = эта папка (там есть AGENTS.md и SOUL.md)."
}

install_claude() {
  copy_skill "$HOME/.claude/skills/finex-liquidation"
  mkdir -p "$HOME/.claude/agents"
  cp "$HERE/agents/claude-code/finex.md" "$HOME/.claude/agents/"
  echo "Субагент -> $HOME/.claude/agents/finex.md. Перезапустите Claude Code; скажите «что нового по FinEx»"
}

install_codex() {
  copy_skill "$HOME/.codex/skills/finex-liquidation"
  echo "Codex: перезапустите сессию или работайте из этой папки (AGENTS.md)"
}

case "$TARGET" in
  hermes) install_hermes ;;
  hermes-default) install_hermes_default ;;
  openclaw) install_openclaw ;;
  claude) install_claude ;;
  codex) install_codex ;;
  all)
    command -v hermes >/dev/null && install_hermes || echo "Hermes не найден — пропускаю"
    [[ -d "$HOME/.openclaw" ]] && install_openclaw || echo "OpenClaw не найден — пропускаю"
    [[ -d "$HOME/.claude" ]] && install_claude || echo "Claude Code не найден — пропускаю"
    [[ -d "$HOME/.codex" ]] && install_codex || echo "Codex не найден — пропускаю"
    ;;
  *) echo "Неизвестная цель: $TARGET (hermes|hermes-default|openclaw|claude|codex|all)"; exit 1 ;;
esac

mkdir -p "${FINEX_DESK:-$HOME/finex-desk}"
echo "Хранилище: ${FINEX_DESK:-$HOME/finex-desk}"
if [[ -n "$PY" ]]; then "$PY" -m pip install --user --quiet pypdf 2>/dev/null || echo "Для чтения PDF: pip install pypdf"
else echo "Python не найден: установите Python 3.9+ и pypdf"; fi
