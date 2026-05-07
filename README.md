# Dashboard de Compras — Grupo A.M. Gomes

Monitora cobertura de estoque (60 dias + 15 lead time) e sugere compras das
marcas curva A e B nas 4 lojas: L1, L3, L4, L5.

## Estrutura

```
compras/
├── dashboard_compras.html   # dashboard (abrir no navegador)
├── dados.json               # gerado pelo agente Claude (consumido pelo dashboard)
├── curva_marcas.json        # marcas A/B por loja — EDITÁVEL
├── README.md                # este arquivo
└── logs/                    # logs do agente
```

A skill que extrai os dados está em:
`~/.claude/scheduled-tasks/dashboard-compras-update/SKILL.md`

## Como atualizar os dados

**Opção 1 — Manualmente, agora:**
No Claude Code, peça:
> "Roda o agente dashboard-compras-update"

(Mesmo padrão do `dashboard-amgomes-update` que você já usa para o financeiro.)

**Opção 2 — Agendado 12h e 18h:**
Configure via MCP `scheduled-tasks` do Claude Code. Use o mesmo método
que está sendo usado hoje para `dashboard-amgomes-update`.

## Pré-requisito para o agente funcionar

O Chrome principal precisa estar com o Microvix logado em
`https://linx.microvix.com.br/v4/home/index.asp` no momento da execução.
A skill usa o Chrome MCP (sessão do seu Chrome principal).

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

Cores no dashboard:
- 🔴 Crítico: cobertura < 60 dias
- 🟡 Atenção: 60–90 dias
- 🟢 OK: > 90 dias
