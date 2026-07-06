# CHANGELOG — Mapeamentos de Marca (Dashboard de Compras)

Toda mudança de `curva_marcas.json`, `marca_ids.json`, `fornecedor_marcas.json`, `BRAND_KEYWORDS`
ou `_ignorar_no_dashboard`/`_transito_sem_marca_ok` entra AQUI como entrada datada — nunca mais no
CLAUDE.md global (que estava virando um ledger de 40KB). O histórico até 01/07/2026 está preservado
em RUNBOOK_COMPRAS.md (bullets de `fornecedor_marcas.json` / `marca_ids.json`).

Formato: `## AAAA-MM-DD — <Marca>` + o que mudou em cada arquivo + NF/fornecedor que motivou.

<!-- novas entradas abaixo -->

## 2026-07-06 — Truss (fornecedor novo)
`fornecedor_marcas.json`: adicionado `por_cnpj["41282461000181"] = "Truss"` (BROKER CARAJAS
DISTRIBUIDORA LTDA). Truss já existia em `marca_ids.json` (código 376) e na curva — só faltava
esse fornecedor específico. Motivo: NF 14275 (loja L4, 20 produtos, todos Truss por descrição)
tinha dado entrada no ERP mas não aparecia na tela de precificação (dashboard-equipe) por falta de
marca mapeada ao fornecedor. Confirmado por descrição de produto (100% "TRUSS ...").
