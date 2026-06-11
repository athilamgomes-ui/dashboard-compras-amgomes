#!/bin/bash
# atualizar_compras.sh — pipeline completo do dashboard de compras via Playwright headless.
# Substitui a coleta via Chrome MCP (que falhava em background — WebSocket morto).
#
# Etapas:
#   1. Coleta Microvix (saldos+vendas+trânsito, notas lançadas, NFes pendentes SEFAZ)
#      → compras_raw.json   [Playwright headless, ~2min, independente da extensão Chrome]
#   2. build_dashboard.py   → dados.json + dados.js (consolida, sugestões, chegadas, lançamentos)
#   3. compute_diff.py      → injeta _diff vs execução anterior
#   4. git add/commit/push  → GitHub Pages
#
# Exit codes: 0=ok; 10=coleta falhou (preserva dados anteriores); 20=build falhou.
set -uo pipefail

SCRIPTS="/Users/elkgomes/Desktop/claude/dashboard-equipe/scripts"
COMPRAS="/Users/elkgomes/Desktop/claude/compras"
NODE="$(command -v node)"
TS="$(date '+%Y-%m-%d %H:%M')"

echo "=== [1/4] Coleta Microvix (Playwright headless) ==="
cd "$SCRIPTS" || exit 20
# Retry: o login do ERP Microvix às vezes fica instável (NAV_FAIL / timeout 30s
# navegando no v4/home). Tentar até 4x com intervalo crescente antes de desistir —
# evita pular um dia inteiro por causa de lentidão transitória do servidor.
COLETA_OK=0
for TENT in 1 2 3 4; do
  echo "--- coleta tentativa $TENT/4 ---"
  if "$NODE" coleta_compras.mjs all; then COLETA_OK=1; break; fi
  echo "coleta falhou (tentativa $TENT). Aguardando antes de retry..."
  sleep $((TENT * 30))
done
if [ "$COLETA_OK" -ne 1 ]; then
  echo "ERRO: coleta falhou após 4 tentativas. Dados anteriores PRESERVADOS (compras_raw.json não sobrescrito em falha)."
  exit 10
fi

# Sanity: compras_raw.json precisa ter saldos não-vazios das 4 lojas
if ! python3 - <<'PY'
import json,sys
raw=json.load(open('/Users/elkgomes/Desktop/claude/compras/compras_raw.json'))
s=raw.get('saldos',{})
ok=all(s.get(l) for l in ('L1','L3','L4','L5'))
prod=sum(len(b['prods']) for l in s.values() for b in l.values())
print(f"sanity: produtos={prod} lojas_ok={ok}")
sys.exit(0 if ok and prod>1000 else 1)
PY
then
  echo "ERRO: compras_raw.json incompleto (alguma loja vazia). Abortando build para não corromper dashboard."
  exit 10
fi

echo "=== [2/4] build_dashboard.py ==="
cd "$COMPRAS" || exit 20
python3 build_dashboard.py || { echo "ERRO: build_dashboard.py falhou"; exit 20; }

echo "=== [3/4] compute_diff.py ==="
python3 compute_diff.py || echo "WARN: compute_diff.py falhou (segue sem diff)"

echo "=== [4/4] git push ==="
git add dados.json dados.js
git -c user.email="athilamgomes-ui@users.noreply.github.com" -c user.name="athilamgomes-ui" \
  commit -m "atualização $TS (Playwright headless)" && git push origin main || echo "WARN: git push falhou"

echo "=== OK ($TS) ==="
exit 0
