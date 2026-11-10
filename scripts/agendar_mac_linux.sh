#!/usr/bin/env bash
# Liga a automação no cron (Mac/Linux). Rode dentro da pasta do kit, com o .venv instalado:
#   bash scripts/agendar_mac_linux.sh            (para desligar: bash scripts/agendar_mac_linux.sh --remover)
# No Mac, dê "Acesso Total ao Disco" ao cron se a pasta estiver em Documentos ou na Mesa.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$KIT/.venv/bin/paginas"
LOG="$KIT/saida/automacao.log"
LIMPO="$(crontab -l 2>/dev/null | grep -v "paginas-nicho-kit" || true)"
if [ "${1:-}" = "--remover" ]; then echo "$LIMPO" | crontab -; echo "Automação desligada."; exit 0; fi
[ -x "$BIN" ] || { echo "Não achei $BIN. Instale o kit primeiro (README)."; exit 1; }
mkdir -p "$KIT/saida" "$KIT/clipes/entrada"
CLAUDE_DIR="$(dirname "$(command -v claude 2>/dev/null || echo /usr/local/bin/claude)")"
CMD="cd \"$KIT\" && PATH=\"$CLAUDE_DIR:\$PATH\" \"$BIN\""
{ echo "$LIMPO"
  echo "*/15 * * * * $CMD ciclo >> \"$LOG\" 2>&1 # paginas-nicho-kit"
  echo "10 7 * * * $CMD claude radar >> \"$LOG\" 2>&1 # paginas-nicho-kit"
  echo "40 7 * * 1 $CMD claude pauta >> \"$LOG\" 2>&1 # paginas-nicho-kit"
  echo "10 8 * * * $CMD claude traducao >> \"$LOG\" 2>&1 # paginas-nicho-kit"
  echo "30 23 * * * $CMD metricas >> \"$LOG\" 2>&1 # paginas-nicho-kit"
} | sed '/^$/d' | crontab -
echo "Agendado (ciclo a cada 15 min, radar 07:10, pauta segunda 07:40, métricas 23:30)."
