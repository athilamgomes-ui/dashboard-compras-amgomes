# Dashboard de Compras — Grupo A.M. Gomes

**Acesso da equipe:** https://athilamgomes-ui.github.io/dashboard-compras-amgomes/dashboard_compras.html

Monitora cobertura de estoque (60 dias + 15 lead time) e sugere compras das
marcas curva S, A e B nas 4 lojas: L1, L3, L4, L5. Atualizado automaticamente
seg–sáb às 18:30 (cron + GitHub push).

## Estrutura

```
compras/
├── dashboard_compras.html   # dashboard (abrir no navegador)
├── dados.json / dados.js    # gerado por build_dashboard.py — NÃO editar na mão
├── atualizar_compras.sh     # ⭐ o único comando de atualização
├── build_dashboard.py       # único escritor de dados.json
├── reconcilia_transito.py   # autocheck: NFe pendente sem marca aparece no banner
├── curva_marcas.json        # marcas S/A/B por loja — EDITÁVEL
├── marca_ids.json           # marca → código no ERP — EDITÁVEL
├── fornecedor_marcas.json   # fornecedor → marca — EDITÁVEL
├── CHANGELOG_MARCAS.md      # toda mudança de mapeamento entra aqui, datada
├── README.md                # este arquivo
└── logs/                    # logs do agente
```

Runbook completo: `RUNBOOK_COMPRAS.md`. Para mapear marca nova, use a skill `mapear-marca`
(faz curva + código + keywords + fornecedor + recoleta + reconciliação + commit de uma vez).

## Como atualizar os dados

**Um comando só — sempre este:**

```bash
bash /Users/elkgomes/Desktop/claude/compras/atualizar_compras.sh
```

Faz tudo: coleta → `build_dashboard.py` → `compute_diff.py` → `reconcilia_transito.py`
→ commit + push. Leva ~3 min. Exit codes: `0`=ok · `10`=coleta falhou (preserva o dado
anterior) · `20`=build falhou (restaura) · `30`=lock.

O agente **nunca** edita `dados.json`/`dados.js` na mão — `build_dashboard.py` é o único
escritor. Para mudar marca/curva, edite os `.json` de configuração e rode o script.

**Agendado:** task MCP `dashboard-compras-update`, seg–sáb 18:30 (o launchd
`com.amgomes.dashboard` acorda o Claude Desktop antes).

## ⚠️ Pré-requisito da coleta — Playwright headless, NUNCA Chrome MCP

A coleta roda em **Playwright headless** (`dashboard-equipe/scripts/coleta_compras.mjs`),
autenticando sozinha pelo perfil persistente `~/.claude/microvix-profile` + credenciais no
Keychain (`microvix-cron`). **Não precisa de Chrome aberto nem de sessão logada** — roda em
background, inclusive com a máquina sem ninguém na frente.

**É PROIBIDO usar Chrome MCP / `claude-in-chrome` / `Control_Chrome` para o Microvix**
(regra nº 1 do `~/.claude/CLAUDE.md`): em background o WebSocket morre e cada chamada trava
300 s. Foi assim que as 4 sessões mais caras de jun/2026 queimaram centenas de erros.
Histórico completo em `HISTORICO_CHROME_MCP.md`.

Se a coleta travar em cascata, procure um `chrome-headless-shell` zumbi segurando o perfil:

```bash
pkill -f chrome-headless-shell; rm -f ~/.claude/microvix-profile/Singleton*
```

## Editar marcas curva A/B

Edite `curva_marcas.json` direto. As chaves por loja são `L1`, `L3`, `L4`, `L5`.
O dashboard recarrega na hora — não precisa rodar o agente de novo.

## Fórmulas

```
venda_diária = vendas_60d / 60
estoque_total = saldo_atual + estoque_em_trânsito
cobertura_dias = estoque_total / venda_diária
estoque_alvo = venda_diária × (60 + 15)
sugestão_compra = max(0, estoque_alvo − estoque_total)
```

Faixas de cobertura no dashboard (05/08/2026 — antes só existiam as 3 primeiras, então
sobra nunca aparecia: uma marca com 400 dias vinha VERDE como "OK"):

| Faixa | Cobertura | Leitura |
|---|---|---|
| 🔴 Crítico | < 60 dias | comprar já |
| 🟡 Atenção | 60–90 dias | programar compra |
| 🟢 OK | 90–180 dias | saudável |
| 🟣 Excesso | 180–360 dias | **queimar** — não comprar |
| ⚫ Morto | > 360 dias | **queimar/liquidar** |
| 🔵 Chegou agora | recebeu nos últimos 60 dias | cobertura **inflada** (estoque novo ÷ venda velha) — não classificar como sobra ainda |

`excesso_un` = unidades acima de 180 dias de cobertura — é a base do plano de queima.

**Exclusões por marca** (`EXCLUIR_PRODUTOS` em `build_dashboard.py`): as lixas Santa Clara
são compradas em pacote e saem por unidade (troco de loja), então o saldo do ERP carrega
milhares de unidades inexistentes. São excluídas da marca — mesmo tratamento do dashboard
de Vendas (`coleta_top_marcas.mjs`).
