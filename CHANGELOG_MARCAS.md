# CHANGELOG — Mapeamentos de Marca (Dashboard de Compras)

Toda mudança de `curva_marcas.json`, `marca_ids.json`, `fornecedor_marcas.json`, `BRAND_KEYWORDS`
ou `_ignorar_no_dashboard`/`_transito_sem_marca_ok` entra AQUI como entrada datada — nunca mais no
CLAUDE.md global (que estava virando um ledger de 40KB). O histórico até 01/07/2026 está preservado
em RUNBOOK_COMPRAS.md (bullets de `fornecedor_marcas.json` / `marca_ids.json`).

Formato: `## AAAA-MM-DD — <Marca>` + o que mudou em cada arquivo + NF/fornecedor que motivou.

<!-- novas entradas abaixo -->

## 2026-08-20 — BTH e Kamaleão (código de marca p/ precificação L3)
As duas chegaram em Itaituba (L3) e apareciam SEM "preço atual" na precificação porque faltava o código de marca.
- `marca_ids.json`: **BTH=443** · **Kamaleao=944** (Athila informou).
- `fornecedor_marcas.json`: `por_cnpj["27206583000168"]="BTH"` (fornecedor "Ado Administradora de Marcas", NF 3404 — NF 100% BTH/Brotherhood). Kamaleão já estava mapeado (KAMALEAO COLOR / CNPJ 31768865000126).
- Descoberta: BTH e Kamaleão JÁ estão precificados no ERP com o MESMO preço em Altamira e Itaituba (não era 1ª vez). Gerado `.txt` de referência (preços de Altamira) p/ os itens NOVOS (frascos ROUXINOL/IGUANA/PAVÃO=50,06; sachês novos=31,00; KIT AURA ROUGE e Gel Cola 500g ficaram fora, sem referência).


## 2026-08-19 — Auditoria de cobertura: faixas de sobra, chegada recente, histórico e de-para
Athila auditou o dashboard e apontou 7 defeitos. O que mudou:

**1. Faixas de Excesso e Morto** (`build_dashboard.py` `FAIXAS`/`classifica_cobertura`,
`dashboard_compras.html` `STATUS`/`classifica`). Antes só existia falta (Crítico &lt;60 /
Atenção 60–90 / OK &gt;90) — marca com 400 dias vinha VERDE como "OK" e o dashboard **nunca
enxergava sobra**. Agora: OK 90–180 · **Excesso 180–360** · **Morto &gt;360**. Novo KPI
"Excesso / Morto" e campo `excesso_un` (unidades acima de 180 dias) = base do plano de queima.
Hoje: 38 marca×loja em sobra, ~5.000 un.

**2. "Chegou agora"** (`historico_entregas[*].recem_chegou`, faixa `RECEM`). A cobertura
divide saldo NOVO por venda VELHA: uma marca que recebeu dentro da janela de 60 dias aparece
com cobertura inflada. Ex.: Nathydras L1 recebeu 508 un e marcava 786 dias. Marcas com entrada
nos últimos 60 dias ganham selo azul "chegou agora" e **não são classificadas como sobra** até
o giro pós-chegada aparecer. 44 marca×loja nessa situação.

**3. "sem histórico — 1º pedido" em TODAS as curva S** — bug real. `janelaPedido()` e
`calcularPrazoMedio()` liam `DATA.chegadas_mes`, que é uma **janela de 45 dias**: qualquer marca
cuja última entrega tivesse mais de 45 dias caía no fallback de primeiro pedido. Criado
`historico_entregas` (marca×loja, **ano inteiro**: última entrega, prazo médio, nº de entregas,
un recebidas em 60d), consumido pelo front. Caiu de **33 → 3** (as 3 restantes — ProBelle,
Felps e Japinha em L5 — realmente não têm entrega no ano).

**4. Santa Clara — lixas** (`EXCLUIR_PRODUTOS` em `build_dashboard.py`). Copiado o tratamento do
dashboard de VENDAS (`coleta_top_marcas.mjs`): produtos `\bLIXA` saem da marca, porque são
comprados em pacote e saem por unidade (troco de loja) e o ERP carrega milhares de unidades
inexistentes. Cobertura: **L1 827→259d · L4 561→407d · L5 203→94d** (L3 já estava em 97d).
⚠️ L4 continua alto: sobra saldo fantasma em códigos antigos que NÃO são lixa (ex.
"CLIPS PLAS CAB REFIL S CLARA" com 2.930 un) — isso é inventário, não dashboard.

**5. De-para de marcas duplicadas** (`ALIASES`). Varredura de grupos ERP parecidos com marcas da
curva encontrou **NATHY** separado de **NATHYDRAS** — 819 un de saldo invisíveis (L1 487, L4 180,
L5 117, L3 35). Também **LIZZ**→Lizze (grafia truncada, poucas un). Apice/Apse **já estava
resolvido** desde antes (alias existente, funcionando). Sobre L'Oréal, ver a nota abaixo.

**6. Elseve entrou na curva B (L3/L5).** Tem grupo próprio no ERP e saldo, mas não estava em
`curva_marcas.json` — cobertura nunca era lida.

**7. README** reescrito: dizia que a coleta "usa o Chrome MCP (sessão do seu Chrome principal)",
contrariando a regra nº 1 do CLAUDE.md. Agora documenta Playwright headless + perfil persistente
+ Keychain, o comando único `atualizar_compras.sh`, as faixas novas e o remédio do zumbi
`chrome-headless-shell`.

### Nota — L'Oréal NÃO estava "colado numa marca só"
Investigado: no ERP os grupos **já são separados**. `LOREAL` contém só L'Oréal **Professionnel**
(Absolut Repair, Serie Expert, Curl Expression, Nutrioil, Vitamino Color), fornecedores FOCO
(R$14.052) + Bortman (R$5.429) = **R$19.481**, e **está** na curva B nas 4 lojas — a cobertura é
lida (L4 990 dias, hoje marcada "chegou agora"). O lado **Paris** são outros grupos: `ELSEVE`
(R$1.623) e `GARNIER` (R$339), via Okajima — Elseve entrou na curva agora, Garnier tem 9 un e
ficou de fora. O gasto de Okajima (R$15.387) é majoritariamente **não-L'Oréal**: Risque 19%,
Colorama 18%, OX 11%, Elseve 11%, Garnier 2% e **39% (R$6.063) em produtos sem grupo de marca no
saldo do ERP** — esse é o valor realmente sem leitura, e a causa é cadastro no ERP, não de-para.

## 2026-08-07 — Loreal (novo fornecedor FOCO)
Athila informou: **FOCO DISTRIBUICAO E LOGISTICA LTDA = marca Loreal (código 387 no ERP)**. A marca
já estava 100% mapeada (`marca_ids.json` Loreal=[387], curva B nas 4 lojas, fornecedor BORTMAN E CIA
já apontando p/ Loreal) — faltava só o fornecedor novo.
- `fornecedor_marcas.json`: `por_nome_substring["FOCO DISTRIBUICAO E LOGISTICA"]="Loreal"`.
- Reconciliação após recoleta: 🔴 curva NÃO refletida = 0; chegada nova **L4 Loreal R$8461** (NF do FOCO já resolvida com marca).

## 2026-08-04 — Franca Plus (multi-marca) + keywords viram FONTE ÚNICA
Franca Plus (CNPJ 56927323000180) = distribuidora multi-marca **Nathydras + Varcare**. Motivada pela
precificação: a NF 926 L1 (R$18k, 59 itens) precisava ter a marca de CADA item detectada p/ puxar
preço do ERP e a margem certa.
- `fornecedor_marcas.json`: `por_cnpj["56927323000180"]="Varcare+Nathydras"` + `por_nome_substring["FRANCA PLUS"]` idem (padrão multi-marca com '+', igual Colorama+Elseve).
- **`BRAND_KEYWORDS` saiu de dentro do `build_dashboard.py` para `marca_keywords.json` (fonte ÚNICA, 55 marcas).** Agora `build_dashboard.py`, `reconcilia_transito.py` E o coletor de precificação `coleta_precificacao.mjs` leem do MESMO arquivo. **Editar SÓ o JSON** (chaves com `_` ignoradas; termos com `\b` são regex). Rebuild offline idêntico ao anterior (fora timestamp); reconcilia OK, Franca fora de "sem marca".
- Termos novos em `marca_keywords.json` p/ produtos Franca que as keywords não cobriam: Nathydras += `MATIZADOR ALHO`,`MASCARA MATIZADORA ALHO`; Varcare += `AMINOFLUID`,`S.O.S. AMINO`,`SOS AMINO`.
- `marca_ids.json` já tinha Varcare=249, Nathydras=885; curva já tinha os dois.
Precificação (repo dashboard-equipe): a marca de cada item é resolvida no coletor — 1º pelo relatório
de preços do ERP (fonte da verdade, já traz o preço atual), 2º por descrição (produto novo ainda sem
preço no ERP). NF 926: 39/41 resolvidos (2 restantes = embalagem: CAIXA KIT MSA, BOBINA SHRINK).

## 2026-08-04c — Bauny (código informado pelo Athila)
Athila informou: **Bauny = marca 1078 no ERP**, fornecedor **FFE E FRAIHA DISTRIBUIDORA LTDA**
(CNPJ 45998443000151). Estava caindo no banner "trânsito sem marca" com 4 NFes pendentes
(5071/5072 em L3, 5078/5079 em L5). Mapeado:
- `marca_ids["Bauny"] = [1078]`
- `fornecedor_marcas.por_cnpj["45998443000151"] = "Bauny"` + `BRAND_KEYWORDS['Bauny']=['BAUNY']`
  (redundância proposital: **100% dos itens das 4 NFes já trazem "BAUNY" na descrição**, então a
  keyword sozinha resolveria; o CNPJ cobre eventual item futuro sem a marca no nome).
- `curva_marcas.json`: **curva B nas 4 lojas** — diferente dos casos anteriores de hoje (onde
  restringi às lojas com evidência de compra), aqui a marca **já tinha estoque nas 4** (L1 21,
  L3 19, L4 14, L5 50 produtos no ERP), ou seja, todas já vendem Bauny.

Pós-rebuild: 124 produtos consolidados, 4 sugestões de compra geradas (L1 28un, L3 17un, L4 7un,
L5 25un), trânsito refletido em L3 (258un) e L5 (252un). Banner caiu de 11 para 9 itens.
Rebuild offline (compras_raw.json das 13:42), sem re-raspar o Microvix.

## 2026-08-04b — Becorel→Igora, Franca Plus (keywords), Mundial (linhas infantis), Okajima (resíduo)
Athila apontou que Franca, Becorel, Mundial e Okajima continuavam no banner "trânsito sem marca"
mesmo já tendo tido entradas anteriores — ou seja, a marca era conhecida e o mapeamento é que
faltava. Todos os 4 eram o MESMO tipo de falha: a marca existe e já tem histórico, mas a
**descrição da NFe pendente não traz o nome da marca** (usa abreviação ou nome de linha), e o
fornecedor ou não estava mapeado ou é multi-marca. Corrigidos:

- **Becorel** ("BECOREL BELEZA COMERCIO DE COSMETICOS") → **Igora**. Fornecedor especializado, todas
  as 4 notas lançadas do histórico batem 100% no grupo IGORA ROYAL do ERP. A descrição pendente
  abrevia para **"I. ROYAL 1-0 60ML"**, que NÃO casa com o keyword `IGORA` — por isso ficava órfã
  apesar de Igora já ser curva A nas 4 lojas. Resolvido por
  `fornecedor_marcas.por_nome_substring["BECOREL"]="Igora"`. Recuperou 3 NFes (L1 142968 R$6005,
  L4 142995 R$5930, L5 142977 R$3784, L3 142900 R$2572).
- **Franca Plus** → keywords de linha de produto para o split **Nathydras/Varcare** (curva B
  adicionada na entrada anterior de hoje). A NFe pendente descreve só a linha, sem a marca:
  `Nathydras` = ALHO THERAPY / MASCARA-SHAMPOO-SELANTE-CONDICIONADOR ALHO / MATIZADORA ACAI;
  `Varcare` = S.O.S. INVERSOR / S.O.S. MOISTURE / LISO PERFEITO / NUTRITION / HUMECTANT COMPLEX.
  Keywords conferidas contra o cadastro real do ERP. NF 932 (L3, 824un) e 931 (L5, 336un) saíram
  do banner — resta só embalagem (BOBINA SHRINK 36un, CAIXA KIT MSA 12un), que é insumo, não revenda.
- **Mundial Distribuidora** (multi-marca Impala + Mundial) → keywords para as linhas licenciadas e
  infantis que não trazem "MUNDIAL" na descrição: `TIRESMALT` (removedor; mesmo prefixo de EAN
  7896111 dos Impala = mesmo fabricante), `KIT BARBIE`, `KIT HOT WHEELS`, `GIZ PARA COLORIR`,
  `INFANTIL BARBIE`, `KIT INFANTIL MAQUIAGEM`, `KIT INFANTIL BRILHO LABIAL`. ⚠️ As duas últimas
  são levemente ambíguas — algumas variantes de personagem (FROZEN-maquiagem, MOANA-brilho) estão
  no grupo IMPALA no ERP, a maioria em MUNDIAL; optei pela maioria. `Impala` vem ANTES de `Mundial`
  no dict, então qualquer descrição com "IMPALA" literal continua ganhando. Resolveu NFs 771795
  (L3), 771796 (L4), 771741 (L5) — restam 6un de um conjunto Barbie ambíguo.
- **Okajima** (multi-marca) → o grosso já casava em Risque/Colorama; o resíduo eram 28un de
  **desodorante Tabu** e **Bozzano**, marcas que não compramos para curva. Adicionadas como
  **rótulo-only** (`BRAND_KEYWORDS` + `_marcas_sem_cadastro_erp`, padrão Elseve): são reconhecidas
  e param de cair em "sem marca", mas não geram sugestão de compra. NFs 1183612 e 1213501 (L3) limpas.

Pós-rebuild: banner caiu de 19 para 11 itens; reconciliação `curva NÃO refletida: 0`,
`sem marca: 5` (só os 3 fornecedores realmente novos + o que já estava pendente de decisão).
Rebuild offline (compras_raw.json das 13:42), sem re-raspar o Microvix.

**Continuam pendentes de decisão do Athila:** Ado Administradora de Marcas (→Brotherhood, marca já
existe no ERP mas falta o código), JF Comercio (necessaires sem GTIN, SKU novo), FOCO Distribuição
(LP Curl Expression), FFE e Fraiha (linha Bauny), A M Gomes Import (bolsas), além dos 3 da entrada
anterior (DVT, Nova Chance/Cor e Charme, Fabio Porto).

## 2026-08-04 — Nathydras/Varcare, Inoar, Raavi, Maria Margarida, Real Love (notas JÁ LANÇADAS sem marca)
Athila pediu auditoria: marcas em "trânsito sem classificação" cujo produto já tinha CHEGADO e a
NFe já estava lançada no ERP (não era mais problema de trânsito pendente — era `attribute_nota()`
em `build_dashboard.py` retornando `[]` silenciosamente, então a NF simplesmente não contava em
`compras_mensais_rs`). Descoberto rodando um cruzamento do código interno ERP (`c` de cada item da
nota lançada) contra `saldos_raw.json` completo (todas as ~300 marcas por loja, não só as
curva-tracked) — alta confiança porque o código interno pós-lançamento é o MESMO espaço de ID
usado no relatório de saldo. 14 notas de 2026 caíram nesse buraco; 5 fornecedores resolvidos:

- **Franca Plus** (fornecedor "FRANCA PLUS COMERCIO DE COSMETICOS LTDA") → **split multi-marca
  Nathydras + Varcare** (linha capilar "Alho"/"S.O.S.", descrições NÃO trazem o nome da marca).
  `marca_ids.json` já tinha os códigos (Varcare=249, Nathydras=885, anotados 26/07 como "split
  pendente"); faltava só a curva. Adicionado **curva B em L1, L3, L5** (evidência de compra: NF
  822/823 lançadas L1 mar/2026; NF 932/931 ainda pendentes em trânsito L3/L5 — sem evidência em
  L4, não adicionei lá). NÃO mapeei fornecedor→marca única (é multi-marca) — a atribuição correta
  passa a ser 100% por código ERP (`codigo_to_marca`), que só funciona depois que a nota é
  LANÇADA. As 2 NFs ainda pendentes (932 L3, 931 L5) continuam no banner "sem marca" até chegarem
  e serem lançadas — isso é esperado, não é bug.
- **Alekosmetica** ("ALEKOSMETICA COM.DE COSMETICOS LTDA") → **Inoar**. Código ERP descoberto
  headless: **347**. `marca_ids["Inoar"]=[347]`, curva B em L3 (única loja com histórico: NF 70845
  R$5905 + NF 70899 R$736, jan/2026). `fornecedor_marcas.por_nome_substring["ALEKOSMETICA"]="Inoar"`.
- **DEDC** ("DEDC - DISTRIB DO ESPIRITO SANTO DE COSMETICOS EIRELI") → **Raavi**. Código ERP: **386**.
  `marca_ids["Raavi"]=[386]`, curva B em L3 (NF 46100 R$4167, mar/2026, 100% do valor bateu por
  código). `fornecedor_marcas.por_nome_substring["DEDC - DISTRIB DO ESPIRITO SANTO"]="Raavi"`.
- **C & D Comercio** ("C & D COMERCIO DE COSMETICOS VESTUARIOS E ACESSORIOS LTDA") → **Maria
  Margarida**. Código ERP: **1101**. `marca_ids["Maria Margarida"]=[1101]`, curva B em L5 (NF
  39616 R$5787, jan/2026). `fornecedor_marcas.por_nome_substring["C & D COMERCIO DE COSMETICOS"]="Maria Margarida"`.
- **Real Love** ("REAL LOVE COSMETICOS E ACESSORIO") → **Real Love** (marca com o mesmo nome do
  fornecedor). Código ERP: **362**. `marca_ids["Real Love"]=[362]`, curva B em L4 e L5 (NF 48780
  L4 R$598 + NF 49031 L5 R$892, mar/2026). `fornecedor_marcas.por_nome_substring["REAL LOVE COSMETICOS"]="Real Love"`.

Pós-rebuild: os 4 fornecedores de marca única saíram completamente da lista de "notas sem marca";
Franca Plus lançada (L1) também resolveu — apareceu em `compute_diff.py` como chegada nova
"L1 Nathydras R$18006". Reconciliação de trânsito (pendentes) segue OK (curva não refletida = 0).

**Ficaram PENDENTES de decisão (não mapeei — baixa confiança ou categoria ambígua):**
- **DVT Comercio** ("DVT COMERCIO, IMPORTACAO E EXPORTACAO LTDA") — só ~9% do valor da NF 371607
  (L1, jan/2026) bateu com uma marca conhecida (Talge). Nota: DVT já está mapeado por CNPJ
  (`07439329000100`→Talge, 13/07/2026) mas esse mapeamento só vale para NFes PENDENTES (que têm
  CNPJ na XML); notas já LANÇADAS não carregam CNPJ, só o nome do fornecedor — por isso o fallback
  de nota lançada não pega. Precisa decidir: DVT vende só Talge (aí falta o substring de nome) ou
  é fornecedor multi-marca (aí o 9% é o correto e o resto é outra coisa)?
- **Nova Chance Variedades** e **Cor e Charme** → candidato "King Bolsas" (bolsas/acessórios,
  100% do valor bate por código). Não mapeei porque não está claro se é revenda de cosmético
  (deveria virar marca/curva) ou categoria a excluir do dashboard (`_ignorar_no_dashboard`).
- **Fabio Porto do Nascimento** → candidato "Phallebeuty", só ~50-75% do valor bate. Fornecedor
  provavelmente multi-marca; precisaria de keyword de descrição por produto, não fornecedor único.


## 2026-07-26 — Impala + CBB (fornecedores novos, NFes de 21–24/07)
Três fornecedores caíram no banner "sem marca" com as entradas da semana. Mapeados 2 de 3:
- **Impala** (esmaltes) — forn **MUNDIAL DISTRIBUIDORA** (CNPJ 12744404000500), multimarca. NFs 771795 (L3, 1.716un), 771796 (L4, 2.646un), 771741 (L5, 723un) são 100% "ESMALTE IMPALA...". `marca_ids["Impala"]=[22]` + `BRAND_KEYWORDS['Impala']=['IMPALA']`. NÃO mapeei o fornecedor MUNDIAL (multimarca; a keyword resolve estas NFes e evita atribuir errado outras marcas da Mundial). Impala saiu do banner. **Curva: B nas 4 lojas** (definido pelo Athila 26/07 — volume ~5k un). Agora reflete como curva OK e gera sugestão de reposição.
- **CBB** — forn **CBB INDUSTRIA E COMERCIO** (CNPJ 33468006000147), marca-única. NF 2681 (L3, 306un). A marca CBB já existia (`marca_ids[1104]`, curva nas 4 lojas, keyword `\bCBB\b`), mas as descrições dos produtos NÃO trazem "CBB" (são "CONDICIONADOR NUTRY HOURSE", "MÁSCARA CAPILAR DE VERNIZ"...), então adicionei `por_cnpj["33468006000147"]="CBB"` — fallback do fornecedor marca-única. NF 2681 entrou como curva OK.
- **Varcare (249) + Nathydras (885)** — forn **FRANCA PLUS** (CNPJ 56927323000180), multimarca. Códigos registrados em `marca_ids`, mas **mapeamento de detecção PENDENTE**: as descrições da NF 932/931 são por LINHA de produto ("ALHO THERAPY", "S.O.S.", "NUTRITION", "LISO PERFEITO") e não carregam os nomes das marcas — só um "KIT NATHYDRAS" explícito. Preciso que o Athila diga qual linha é Varcare e qual é Nathydras antes de mapear (evitar atribuição errada). NF 932/931 seguem no banner até lá.
Rebuild offline (compras_raw.json 26/07 09:15), sem re-raspar Microvix. Sem-marca 8→4 (sobram Franca×2, Ado, JF).

## 2026-07-23 — Depilflax (faltava p/ a PRECIFICAÇÃO)
Marca **Depilflax** (fornecedor **Maystar Cosmética do Brasil**, CNPJ `11384984000178`, cód. forn.
ERP 1032). No dashboard de **Compras** já estava OK (curva A em L1/L3/L4, saldos coletados por nome).
O buraco era só na **precificação**: a NF 41124 (L1, lançada 22/07, R$7.950,34, 31 itens de cera/
depilatório) **não aparecia p/ precificar** porque o coletor descarta NF sem marca mapeada
(`coleta_precificacao.mjs` linha 449 `if(!marcaForn) continue`) e a Maystar não estava em
`fornecedor_marcas.json`. Mudanças:
- `marca_ids.json`: `"Depilflax": [957]` (código do grupo de Marca no ERP; confirmado — o relatório
  de preços filtrado por 957 retornou 78 produtos e casou 31/31 itens da NF por EAN).
- `fornecedor_marcas.json`: `por_cnpj["11384984000178"]="Depilflax"` + `por_nome_substring["MAYSTAR
  COSMETICA"]="Depilflax"` (redundância CNPJ+nome).
NÃO mexi em `curva_marcas.json`/`BRAND_KEYWORDS` (Compras já mapeada; descrições já contêm
"DEPILFLAX"). Re-rodei só o coletor de **precificação** (headless) → NF 41124 entrou no L1 com os 31
itens, custo e preço atual do ERP completos. Config lida do disco pelo cron; publicação afeta só
`precificacao_dados.json` (repo dashboard-equipe).

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
