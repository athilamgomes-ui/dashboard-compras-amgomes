# CHANGELOG — Mapeamentos de Marca (Dashboard de Compras)

Toda mudança de `curva_marcas.json`, `marca_ids.json`, `fornecedor_marcas.json`, `BRAND_KEYWORDS`
ou `_ignorar_no_dashboard`/`_transito_sem_marca_ok` entra AQUI como entrada datada — nunca mais no
CLAUDE.md global (que estava virando um ledger de 40KB). O histórico até 01/07/2026 está preservado
em RUNBOOK_COMPRAS.md (bullets de `fornecedor_marcas.json` / `marca_ids.json`).

Formato: `## AAAA-MM-DD — <Marca>` + o que mudou em cada arquivo + NF/fornecedor que motivou.

<!-- novas entradas abaixo -->

## 2026-07-14 — Adesivos de Unha (rótulo-only)
Fornecedor pessoa-física **Marcelo Ribeiro da Silva** = adesivos para unhas (revenda avulsa,
sem grupo de Marca no ERP). Antes estava em `_transito_sem_marca_ok` (genérico, suprimido do
banner). O usuário pediu para ESPECIFICAR. Mudanças em `fornecedor_marcas.json`:
- `por_nome_substring["MARCELO RIBEIRO DA SILVA"] = "Adesivos de Unha"` (novo rótulo).
- removido de `_transito_sem_marca_ok.por_nome_substring` (lista ficou vazia).
- "Adesivos de Unha" adicionado a `_marcas_sem_cadastro_erp.marcas` (rótulo-only: aparece em
  "Chegadas do mês", NÃO vira sugestão de compra por não ter grupo de Marca no ERP).
NÃO alterei `marca_ids.json` nem `curva_marcas.json` (não há grupo no ERP). Motivo: NF 61 (L3,
29/06, 272 un) caía no banner "trânsito sem marca". Pós-rebuild: `sem marca: 0`, NF 61 aparece
como `['Adesivos de Unha']` (fora de curva = só rótulo). Rebuild offline (compras_raw.json 08:57),
sem re-raspar o Microvix.

## 2026-07-06 — Truss (fornecedor novo)
`fornecedor_marcas.json`: adicionado `por_cnpj["41282461000181"] = "Truss"` (BROKER CARAJAS
DISTRIBUIDORA LTDA). Truss já existia em `marca_ids.json` (código 376) e na curva — só faltava
esse fornecedor específico. Motivo: NF 14275 (loja L4, 20 produtos, todos Truss por descrição)
tinha dado entrada no ERP mas não aparecia na tela de precificação (dashboard-equipe) por falta de
marca mapeada ao fornecedor. Confirmado por descrição de produto (100% "TRUSS ...").

## 2026-07-13 — Talge (fornecedor novo)
`fornecedor_marcas.json`: `por_cnpj["07439329000100"] = "Talge"` (DVT COMERCIO IMPORTACAO E
EXPORTACAO LTDA). `marca_ids.json`: `Talge = [243]` (código informado pelo usuário). Motivo:
NF 371607 (L1, 15 produtos, R$2.772) lançada 13/07 não aparecia na precificação por falta de
mapeamento. Após mapear: 15/15 preços associados.
