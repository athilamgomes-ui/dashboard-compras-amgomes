#!/usr/bin/env python3
"""
Consolida dados brutos do Microvix (saldos+vendas, notas lançadas, NFes pendentes SEFAZ)
e gera dados.json para o dashboard de compras.

CORREÇÃO BUG 2026-05-21:
- Etapa 3.7 reescrita: zera trânsito para marcas com NF lançada NO ERP nos últimos 30 dias
  (data de lançamento, não emissão), independente do mês de emissão.
- chegadas_mes inclui TODAS as NFs lançadas nos últimos 30 dias (data Lcto recente),
  mesmo se a emissão foi em mês anterior — pois para o gerente, "chegou ontem" significa
  "lançada ontem", não "emitida ontem".
"""
import json, os, sys, re, unicodedata
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path('/Users/elkgomes/Desktop/claude/compras')
RAW = ROOT / 'compras_raw.json'

def norm(s):
    if not s: return ''
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper().strip()

def load_json(p):
    return json.loads(Path(p).read_text())

raw = load_json(RAW)

# Compat: parser JS antigo gravava 'data_lcto' nas notas; canonizar para 'data_lancamento'.
for n in raw.get('notas', []):
    if 'data_lcto' in n and not n.get('data_lancamento'):
        n['data_lancamento'] = n.pop('data_lcto')
curva = load_json(ROOT / 'curva_marcas.json')
marca_ids = load_json(ROOT / 'marca_ids.json')
forn_marcas = load_json(ROOT / 'fornecedor_marcas.json')

# Fornecedores não-revenda — NF deles deve ser excluída do dashboard inteiramente
IGNORAR_SUBSTRINGS = [s.upper() for s in (forn_marcas.get('_ignorar_no_dashboard') or {}).get('por_nome_substring', [])]
def fornecedor_ignorado(nome):
    if not nome: return False
    up = str(nome).upper()
    return any(s in up for s in IGNORAR_SUBSTRINGS)

HOJE = datetime.now()
ANO = HOJE.year
MES = HOJE.month
LOJAS = ['L1','L3','L4','L5']
EMP_TO_LOJA = {1:'L1', 3:'L3', 4:'L4', 10:'L5'}

# ============ ETAPA 3: Mesclar saldos das 4 lojas ============
saldos = raw['saldos']  # {L1:{brandName:{prods:[]}}, ...}

# Aliases para curva → grupos ERP
ALIASES = {
    'CINCO': ['CINCO','5 CINCO'],
    'MIRRA': ['MIRRA','MIRRAS'],
    'YAMA': ['YAMA','YAMÁ'],
    'APICE': ['APICE','APSE'],
    'OTIMO': ['OTIMO','ÓTIMO'],
}

def find_brand_groups(curva_name, all_groups):
    cn = norm(curva_name)
    aliases = ALIASES.get(cn, [cn])
    matches = []
    for g in all_groups:
        gn = norm(g)
        for a in aliases:
            if gn == a or gn.startswith(a+' ') or gn.endswith(' '+a) or a in gn.split(' '):
                matches.append(g)
                break
    return matches

# Coletar TODAS as marcas mencionadas em qualquer loja
all_groups = set()
for loja in LOJAS:
    all_groups.update(saldos[loja].keys())

# Curva geral: união de todas marcas em curva_marcas.json
curva_all = set()
for loja in LOJAS:
    for cv in ('S','A','B'):
        for m in curva.get(loja,{}).get(cv,[]):
            curva_all.add(m)

# Para cada marca da curva, somar produtos das lojas
marcas_out = []
for marca_name in sorted(curva_all):
    groups = set()
    for loja in LOJAS:
        groups.update(find_brand_groups(marca_name, saldos[loja].keys()))
    if not groups:
        # Marca sem grupo (sem match no ERP) → ainda criar para preservar
        marcas_out.append({
            'marca': marca_name,
            'lojas': {l: {'compras_periodo':0,'vendas_60d':0,'saldo_atual':0,'transito':0} for l in LOJAS},
            'compras_mensais_rs': {l:{} for l in LOJAS},
            'produtos': []
        })
        continue
    # Mesclar produtos por codigo
    prod_by_code = {}  # codigo → {codigo, descricao, referencia, L1:{vendas,saldo,transito}, ...}
    lojas_tot = {l: {'compras_periodo':0,'vendas_60d':0,'saldo_atual':0,'transito':0} for l in LOJAS}
    for loja in LOJAS:
        for g in find_brand_groups(marca_name, saldos[loja].keys()):
            for p in saldos[loja][g]['prods']:
                cod = p['c']
                if cod not in prod_by_code:
                    prod_by_code[cod] = {
                        'codigo': cod, 'descricao': p['d'], 'referencia': p['r'],
                        'L1':{'vendas':0,'saldo':0,'transito':0},
                        'L3':{'vendas':0,'saldo':0,'transito':0},
                        'L4':{'vendas':0,'saldo':0,'transito':0},
                        'L5':{'vendas':0,'saldo':0,'transito':0},
                    }
                prod_by_code[cod][loja] = {'vendas':p['v'], 'saldo':p['s'], 'transito':p['t']}
                lojas_tot[loja]['vendas_60d'] += p['v']
                lojas_tot[loja]['saldo_atual'] += p['s']
                lojas_tot[loja]['transito'] += p['t']
    marcas_out.append({
        'marca': marca_name,
        'lojas': lojas_tot,
        'compras_mensais_rs': {l:{} for l in LOJAS},
        'produtos': list(prod_by_code.values())
    })

# Map: codigo ERP → marca (para usar em Etapa 3.5 lookup)
codigo_to_marca = {}
for mk in marcas_out:
    for p in mk['produtos']:
        codigo_to_marca[str(p['codigo'])] = mk['marca']

# ============ ETAPA 3.5: Notas lançadas → compras_mensais_rs ============
notas = raw['notas']
# Filtrar para ano corrente apenas
notas = [n for n in notas if n.get('ano') == ANO]
print(f"Etapa 3.5: {len(notas)} notas no ano {ANO}", file=sys.stderr)

# Para cada nota, identificar marca por código de cada item
# e somar valor total da nota (rateado se multi-marca)
def marca_por_fornecedor_nome(forn_str):
    """Lookup substring no fornecedor_marcas.json (por_nome_substring).
    forn_str vem como '410-A M COMERCIO DE COSMETICOS LTDA ME' (com prefixo numérico)."""
    if not forn_str: return None
    up = str(forn_str).upper()
    for substr, marca in forn_marcas.get('por_nome_substring', {}).items():
        if substr.upper() in up:
            return marca
    return None

def attribute_nota(nota):
    """Retorna [(marca, valor_marca)] da nota.
    Estratégia: (1) match por código ERP nos itens; (2) fallback por fornecedor."""
    if not nota['itens']:
        return []
    soma_marca = {}
    soma_total = 0
    for it in nota['itens']:
        m = codigo_to_marca.get(str(it.get('c','')))
        soma_total += it.get('v',0)
        if m:
            soma_marca[m] = soma_marca.get(m, 0) + it.get('v',0)
    valor_nota = nota.get('valor', 0)
    if not soma_marca:
        # Fallback: fornecedor → marca (para NFs cujos produtos não casam por código ERP)
        m_forn = marca_por_fornecedor_nome(nota.get('forn',''))
        if m_forn:
            return [(m_forn, valor_nota)]
        return []
    if len(soma_marca) == 1:
        m = list(soma_marca.keys())[0]
        return [(m, valor_nota)]
    # Multi-marca: rateio proporcional
    if soma_total <= 0:
        return list(soma_marca.items())
    return [(m, valor_nota * v / soma_total) for m,v in soma_marca.items()]

marca_idx = {m['marca']: m for m in marcas_out}
for n in notas:
    if not n.get('loja'): continue
    mes_str = str(n['mes'])
    for marca, valor in attribute_nota(n):
        if marca in marca_idx:
            cm = marca_idx[marca]['compras_mensais_rs'][n['loja']]
            cm[mes_str] = cm.get(mes_str, 0) + valor

# ============ ETAPA 3.6: NFes pendentes ============
pendentes_by_emp = raw['pendentes']  # {"1":{NFes:[...]}, "3":{...}, ...}

BRAND_KEYWORDS = {
    'Marco Boni': ['MARCO BONI','MARCOBONI'],
    'Itallian': ['ITALLIAN'],
    'Hair Extrattus': ['HAIR EXTRATTUS','EXTRATTUS'],
    'Beauty Color': ['BEAUTY COLOR','BEAUTYCOLOR'],
    'Santa Clara': ['SANTA CLARA'],
    'Truss': ['TRUSS'],
    'CBB': ['\\bCBB\\b'],
    'Natum': ['NATUM'],
    'ProBelle': ['PROBELLE','PRO BELLE'],
    'Widi Care': ['WIDI CARE','WIDICARE'],
    'Yama': ['YAMA','YAMÁ'],
    'Apice': ['APICE','APSE'],
    'Cadiveu': ['CADIVEU'],
    'Della&Delle': ['DELLA E DELLE','DELLA&DELLE','DELLA DELLE'],
    'Lizze': ['LIZZE'],
    'Felps': ['FELPS'],
    'Mirra': ['MIRRA'],
    'Gama': ['GAMA'],
    'Mundial': ['MUNDIAL'],
    'Kamaleao': ['KAMALEAO','KAMALEÃO',' KC '],
    'Risque': ['RISQUE'],
    'Igora': ['IGORA'],
    'Colorama': ['COLORAMA', 'ESM COL'],
    'Elseve': ['ELSEVE'],
    'Vizzela': ['VIZZELA'],
    'Latika': ['LATIKA'],
    'Otimo': ['OTIMO','ÓTIMO'],
    'Mari Maria': ['MARI MARIA'],
    'Bruna Tavares': ['BRUNA TAVARES'],
    'Cinco': ['5 CINCO','CINCO'],
    'Belliz': ['BELLIZ'],
    'Mutari': ['MUTARI'],
    'Kiss': ['KISS'],
    'Depilflax': ['DEPILFLAX'],
    'Depil Bella': ['DEPIL BELLA'],
    'Repos': ['REPOS'],
    'ZGY': ['ZGY'],
    'Dafu': ['DAFU'],
    'MQ': ['\\bMQ\\b'],
    'Let me be': ['LET ME BE'],
}

EXCL_CFOP = {
    '5152','6152','5910','6910','5911','6911','5912','6912','5913','6913','5914','6914',
    '5915','6915','5917','6917','5918','6918','1411','2411','3411','5201','6201','5202','6202',
    '5208','6208','5209','6209','5210','6210','5410','6410','5411','6411','5412','6412','5413','6413',
}
EXCL_NAT_RE = re.compile(r'^(REMESSA|AMOSTRA|BONIFIC|DEVOLU|RETORNO|TRANSFER|CONSIGNAC)', re.I)

def detect_marca_nfe(nfe):
    """Detecta marca da NFe pendente. Retorna (marca|None, fonte)"""
    # 1) Descrição: majority rule
    cont = {}
    for p in (nfe.get('Produtos') or []):
        d = norm(p.get('DescricaoProduto',''))
        for marca, kws in BRAND_KEYWORDS.items():
            for kw in kws:
                if kw.startswith('\\b'):
                    if re.search(kw, d):
                        cont[marca] = cont.get(marca,0)+1
                        break
                else:
                    if norm(kw) in d:
                        cont[marca] = cont.get(marca,0)+1
                        break
    # 2) Fornecedor por CNPJ tem precedência
    cnpj = str(nfe.get('DadosEmitente',{}).get('Documento','')).replace('.','').replace('/','').replace('-','')
    if cnpj in forn_marcas.get('por_cnpj', {}):
        return (forn_marcas['por_cnpj'][cnpj], 'cnpj')
    # 3) Substring no nome
    nome = (nfe.get('DadosEmitente',{}).get('Nome') or '').upper()
    for substr, marca in forn_marcas.get('por_nome_substring',{}).items():
        if substr.upper() in nome:
            return (marca, 'nome')
    # 4) Descrição majority
    if cont:
        m = max(cont, key=cont.get)
        return (m, 'descricao')
    return (None, None)

def marca_por_descricao(desc):
    """Detecta marca de UM produto pela descrição (keywords). Retorna marca|None."""
    d = norm(desc)
    for marca, kws in BRAND_KEYWORDS.items():
        for kw in kws:
            if kw.startswith('\\b'):
                if re.search(kw, d): return marca
            else:
                if norm(kw) in d: return marca
    return None

def forn_brand_raw(nfe):
    """String de marca mapeada para o fornecedor (ou None). Ex 'Lizze', 'Vertix+Ricca'."""
    cnpj = str(nfe.get('DadosEmitente',{}).get('Documento','')).replace('.','').replace('/','').replace('-','')
    v = forn_marcas.get('por_cnpj', {}).get(cnpj)
    if v is None:
        nome = (nfe.get('DadosEmitente',{}).get('Nome') or '').upper()
        for substr, marca in forn_marcas.get('por_nome_substring',{}).items():
            if substr.upper() in nome:
                v = marca; break
    return v

def forn_brand_info(nfe):
    """Marca do fornecedor. Retorna (marca_unica|None, is_multi).
    is_multi=True quando o fornecedor é multi-marca (label com '+', ex 'Colorama+Elseve')
    — nesse caso NÃO atribuir todos os produtos a uma marca só; detectar por produto."""
    v = forn_brand_raw(nfe)
    if v is None:
        return (None, False)
    return (None, True) if '+' in v else (v, False)

def detect_marca_produto(prod, forn_single, is_multi):
    """Marca de UM produto: (1) descrição; (2) se não casou e fornecedor é single-brand,
    usa a marca do fornecedor. Multi-marca sem match de descrição → None (órfão)."""
    m = marca_por_descricao(prod.get('DescricaoProduto',''))
    if m: return m
    if not is_multi and forn_single: return forn_single
    return None

def keep_nfe(nfe):
    nat = nfe.get('NaturezaOperacao','') or ''
    if EXCL_NAT_RE.match(nat): return False
    cfops = [str(p.get('CFOP','')) for p in (nfe.get('Produtos') or [])]
    if cfops and all(c in EXCL_CFOP for c in cfops): return False
    return True

# Filtrar pendentes do ano corrente
pendentes_log = {}
all_pendentes = []  # [(loja, nfe)]
for emp_s, data in pendentes_by_emp.items():
    emp = int(emp_s)
    loja = EMP_TO_LOJA.get(emp)
    if not loja: continue
    nfes = (data or {}).get('NFes') or []
    raw_count = len(nfes)
    # Filtrar ano corrente e regras
    kept = []
    for n in nfes:
        de = n.get('DataEmissao')
        if not de: continue
        try:
            dt = datetime.fromisoformat(de.replace('Z','+00:00'))
        except:
            continue
        if dt.year != ANO: continue
        if not keep_nfe(n): continue
        kept.append(n)
        all_pendentes.append((loja, n))
    pendentes_log[loja] = {'raw':raw_count, 'kept':len(kept)}
print(f"Etapa 3.6 pendentes: {pendentes_log}", file=sys.stderr)

# Para cada pendente: detecção PER-PRODUTO (uma NFe pode ter várias marcas — ex.
# distribuidores como Okajima: Colorama+Elseve+Risque). Cada produto é atribuído à
# sua marca; compras_mensais_rs e trânsito somam por marca separadamente. O label
# da chegada combina as marcas curva detectadas (ex "Colorama+Risque").
def add_transito_produto(mk, loja, prod_nfe, qty):
    desc_nfe = norm(prod_nfe.get('DescricaoProduto',''))
    tokens_nfe = set(desc_nfe.split())
    best, best_score = None, 0
    for p in mk['produtos']:
        tokens_erp = set(norm(p.get('descricao','')).split())
        if not tokens_nfe or not tokens_erp: continue
        overlap = len(tokens_nfe & tokens_erp)
        score = overlap / max(len(tokens_nfe), len(tokens_erp))
        if score >= 0.5 and overlap >= 3 and score > best_score:
            best, best_score = p, score
    if best:
        best[loja]['transito'] = best[loja].get('transito',0) + qty
    else:
        cprod = str(prod_nfe.get('CProd',''))
        novo = next((p for p in mk['produtos'] if p.get('referencia')==cprod and p.get('_origem')=='NFe pendente'), None)
        if not novo:
            novo = {
                'codigo': f'NF-{cprod}', 'descricao': prod_nfe.get('DescricaoProduto',''), 'referencia': cprod,
                'L1':{'vendas':0,'saldo':0,'transito':0}, 'L3':{'vendas':0,'saldo':0,'transito':0},
                'L4':{'vendas':0,'saldo':0,'transito':0}, 'L5':{'vendas':0,'saldo':0,'transito':0},
                '_origem': 'NFe pendente'
            }
            mk['produtos'].append(novo)
        novo[loja]['transito'] += qty

pendentes_processadas = []
for loja, nfe in all_pendentes:
    forn_single, is_multi = forn_brand_info(nfe)
    valor_total = sum(p.get('ValorBruto',0) or 0 for p in (nfe.get('Produtos') or []))
    if not valor_total:
        valor_total = nfe.get('ValorTotalNota', 0) or 0
    de = nfe.get('DataEmissao')
    try:
        mes_str = str(datetime.fromisoformat(de.replace('Z','+00:00')).month)
    except:
        mes_str = None
    # Agrupar produtos por marca detectada
    por_marca = {}  # marca -> {valor, prods:[(prod,qty)]}
    for prod_nfe in (nfe.get('Produtos') or []):
        m = detect_marca_produto(prod_nfe, forn_single, is_multi)
        qty = prod_nfe.get('QuantidadeComercial', 0) or 0
        val = prod_nfe.get('ValorBruto', 0) or 0
        g = por_marca.setdefault(m, {'valor':0, 'prods':[]})
        g['valor'] += val
        if qty > 0: g['prods'].append((prod_nfe, qty))
    # Atribuir por marca: compras_mensais_rs + trânsito (só marcas da curva)
    marcas_detectadas = []
    for m, g in por_marca.items():
        if not m: continue
        marcas_detectadas.append(m)
        if m not in marca_idx: continue  # ex Elseve: rótulo só, não está na curva
        if mes_str:
            cm = marca_idx[m]['compras_mensais_rs'][loja]
            cm[mes_str] = cm.get(mes_str, 0) + g['valor']
        mk = marca_idx[m]
        for prod_nfe, qty in g['prods']:
            add_transito_produto(mk, loja, prod_nfe, qty)
    # Label da chegada: marcas curva primeiro (ordenadas), depois não-curva; máx 3
    curva_det = [m for m in marcas_detectadas if m in marca_idx]
    fora_det = [m for m in marcas_detectadas if m not in marca_idx]
    ordenadas = sorted(set(curva_det)) + sorted(set(fora_det))
    # Fallback do label: se nenhum produto foi detectado por descrição, usar o label
    # combinado do fornecedor (ex Belliz → 'Vertix+Ricca') só para exibição na chegada.
    label = '+'.join(ordenadas[:3]) if ordenadas else forn_brand_raw(nfe)
    pendentes_processadas.append({'loja':loja, 'nfe':nfe, 'marca':label, 'valor':valor_total})

# Recalcular brand-level transito após pendentes
for mk in marcas_out:
    for loja in LOJAS:
        mk['lojas'][loja]['transito'] = sum(p[loja]['transito'] for p in mk['produtos'])

# ============ NOVA ETAPA 3.7: Zerar trânsito baseado em LANÇAMENTO recente ============
# Para cada (marca × loja): se há NF lançada (data_lancamento) nos últimos 30 dias, zerar trânsito
CUTOFF = HOJE - timedelta(days=30)

# Mapa (marca, loja) → True se houve lançamento recente
lanc_recente = {}  # {(marca, loja): [{nota_meta}]}
for n in notas:
    if not n.get('data_lancamento') or not n.get('loja'): continue
    try:
        dt_lcto = datetime.fromisoformat(n['data_lancamento'])
    except:
        continue
    if dt_lcto < CUTOFF: continue
    for marca, valor in attribute_nota(n):
        if marca in marca_idx:
            key = (marca, n['loja'])
            lanc_recente.setdefault(key, []).append({
                'doc': n['doc'], 'data_lancamento': n['data_lancamento'], 'data_emissao': n['data'],
                'valor': valor, 'forn': n['forn']
            })

zerados = []
for (marca, loja), lst in lanc_recente.items():
    mk = marca_idx[marca]
    old = mk['lojas'][loja]['transito']
    if old > 0:
        mk['lojas'][loja]['transito'] = 0
        for p in mk['produtos']:
            if loja in p:
                p[loja]['transito'] = 0
        zerados.append({'marca':marca, 'loja':loja, 'transito_zerado':old, 'gatilho':lst[0]['doc']})

# Etapa adicional: zerar tb se há lançamento NO MÊS CORRENTE em compras_mensais_rs (regra original)
mes_str_cur = str(MES)
for mk in marcas_out:
    for loja in LOJAS:
        v = mk['compras_mensais_rs'][loja].get(mes_str_cur, 0)
        if v > 0 and mk['lojas'][loja]['transito'] > 0:
            old = mk['lojas'][loja]['transito']
            mk['lojas'][loja]['transito'] = 0
            for p in mk['produtos']:
                if loja in p:
                    p[loja]['transito'] = 0
            zerados.append({'marca':mk['marca'], 'loja':loja, 'transito_zerado':old, 'gatilho':'compras_mensais_rs'})

print(f"Etapa 3.7: {len(zerados)} (marca×loja) zerados", file=sys.stderr)

# ============ ETAPA 4: Sugestões ============
curva_order = {'S':0,'A':1,'B':2}
sugestoes = []
for loja in LOJAS:
    for cv in ('S','A','B'):
        for marca in curva.get(loja,{}).get(cv,[]):
            mk = marca_idx.get(marca)
            if not mk: continue
            lj = mk['lojas'][loja]
            vd = lj['vendas_60d'] / 60.0
            estoque = lj['saldo_atual'] + lj['transito']
            cob = estoque/vd if vd > 0 else 9999
            alvo = vd * 75
            sug = max(0, alvo - estoque)
            sugestoes.append({
                'loja':loja, 'marca':marca, 'curva':cv,
                'venda_60d':lj['vendas_60d'], 'saldo_atual':lj['saldo_atual'],
                'transito':lj['transito'],
                'cobertura_dias':round(cob,1), 'sugestao_compra':round(sug)
            })
sugestoes.sort(key=lambda s: (curva_order.get(s['curva'],9), s['cobertura_dias']))

# ============ CHEGADAS DO MÊS (corrigido) ============
# Inclui:
# A) NFs lançadas nos últimos 30 dias (data_lancamento recente) — independente do mês de emissão.
# B) NFes pendentes com emissão no mês corrente (mantém comportamento).
chegadas = {'mes':MES, 'ano':ANO, 'L1':[],'L3':[],'L4':[],'L5':[]}
# A) lançadas nos últimos 45 dias (data de lançamento no ERP), independente do mês de emissão.
CUTOFF_CHEGADAS = HOJE - timedelta(days=45)
nfs_lancadas_keys = set()  # para dedup vs pendentes
for n in notas:
    if not n.get('data_lancamento'): continue
    try:
        dt_lcto = datetime.fromisoformat(n['data_lancamento'])
    except:
        continue
    # Incluir SOMENTE se a NF foi recebida (lançada no ERP) nos últimos 45 dias.
    if dt_lcto < CUTOFF_CHEGADAS:
        continue
    if not n.get('loja'): continue
    # Pular fornecedores não-revenda (postos, embalagens, peças, etc — fornecedor_marcas.json _ignorar_no_dashboard)
    if fornecedor_ignorado(n.get('forn','')):
        continue
    # Marca majoritária
    attrs = attribute_nota(n)
    if attrs:
        marca = max(attrs, key=lambda x: x[1])[0]
    else:
        marca = '(sem marca)'
    chegadas[n['loja']].append({
        'marca': marca, 'valor': n['valor'], 'nf': n['doc'],
        'data': n['data'], 'data_lancamento': n['data_lancamento'],
        'origem': 'lancada', 'fornecedor': n['forn']
    })
    nfs_lancadas_keys.add((n['loja'], n['doc']))

# B) pendentes nos últimos 45 dias (por data de emissão).
# Mesma janela das lançadas — evita o card vir poluído com NFs antigas presas no SEFAZ
# (a API retorna até 90 dias, mas o card só mostra 45d).
for item in pendentes_processadas:
    loja = item['loja']
    nfe = item['nfe']
    de = nfe.get('DataEmissao')
    try:
        dt = datetime.fromisoformat(de.replace('Z','+00:00')).replace(tzinfo=None)
    except:
        continue
    # incluir se emitida nos últimos 45 dias
    if dt < CUTOFF_CHEGADAS:
        continue
    # Pular fornecedores não-revenda (postos, embalagens, peças, etc)
    if fornecedor_ignorado(nfe.get('DadosEmitente',{}).get('Nome','')):
        continue
    nf_num = str(nfe.get('Numero') or '')
    if (loja, nf_num) in nfs_lancadas_keys:
        continue  # já apareceu como lancada
    chegadas[loja].append({
        'marca': item['marca'] or '(sem marca)',
        'valor': round(item['valor'],2),
        'nf': nf_num,
        'data': de[:10] if de else '',
        'origem': 'pendente',
        'fornecedor': nfe.get('DadosEmitente',{}).get('Nome','')
    })

for loja in LOJAS:
    chegadas[loja].sort(key=lambda x: x.get('data_lancamento') or x.get('data',''), reverse=True)

# ============ LANÇAMENTOS DE MERCADO (curva S) ============
# Cruza lancamentos.json (lista curada de produtos novos das marcas S) com nossa base de
# produtos. Lançamentos que NÃO temos cadastrados viram entradas com flag '_lancamento'
# nos `produtos[]` da marca — assim aparecem no drilldown do dashboard e nos pedidos.
LANCAMENTOS_PATH = ROOT / 'lancamentos.json'
lancamentos_log = {'total_marcas': 0, 'adicionados': [], 'ja_existentes': []}
if LANCAMENTOS_PATH.exists():
    try:
        lanc_data = load_json(LANCAMENTOS_PATH)
        qtd_loja = int(lanc_data.get('_qtd_sugerida_por_loja', 12) or 12)
        marcas_lanc = lanc_data.get('marcas', {}) or {}
        lancamentos_log['total_marcas'] = sum(1 for v in marcas_lanc.values() if v)
        for marca_nome, lista in marcas_lanc.items():
            if not lista: continue
            mk = marca_idx.get(marca_nome)
            if not mk: continue
            existentes_norm = [norm(p.get('descricao','')) for p in mk['produtos']]
            for item in lista:
                nome_lanc = item.get('nome','').strip()
                if not nome_lanc: continue
                nome_norm = norm(nome_lanc)
                # Match fuzzy ≥40% tokens em algum produto existente
                tokens_lanc = set(t for t in nome_norm.split() if len(t) >= 3)
                ja_tem = False
                for desc_norm in existentes_norm:
                    tokens_ex = set(desc_norm.split())
                    if not tokens_lanc: break
                    overlap = len(tokens_lanc & tokens_ex)
                    if overlap >= 2 and overlap / len(tokens_lanc) >= 0.4:
                        ja_tem = True; break
                if ja_tem:
                    lancamentos_log['ja_existentes'].append(f"{marca_nome}: {nome_lanc}")
                    continue
                # Adiciona como produto sintético (mesma estrutura, com flag)
                novo = {
                    'codigo': f"LANC-{marca_nome[:3].upper()}-{len(mk['produtos'])+1:03d}",
                    'descricao': nome_lanc,
                    'referencia': item.get('categoria',''),
                    'L1': {'vendas': 0, 'saldo': 0, 'transito': 0},
                    'L3': {'vendas': 0, 'saldo': 0, 'transito': 0},
                    'L4': {'vendas': 0, 'saldo': 0, 'transito': 0},
                    'L5': {'vendas': 0, 'saldo': 0, 'transito': 0},
                    '_lancamento': True,
                    '_lancamento_qtd_sugerida': qtd_loja,
                    '_lancamento_fonte': item.get('fonte',''),
                    '_lancamento_url': item.get('url',''),
                    '_lancamento_obs': item.get('obs',''),
                    '_lancamento_categoria': item.get('categoria',''),
                    '_lancamento_descoberto_em': item.get('descoberto_em','')
                }
                mk['produtos'].append(novo)
                lancamentos_log['adicionados'].append(f"{marca_nome}: {nome_lanc}")
        print(f"Lançamentos: {len(lancamentos_log['adicionados'])} novos / {len(lancamentos_log['ja_existentes'])} já cadastrados", file=sys.stderr)
    except Exception as e:
        print(f"warn: falha ao processar lancamentos.json: {e}", file=sys.stderr)

# ============ MONTAR SAÍDA ============
saida = {
    'gerado_em': HOJE.isoformat() + 'Z',
    'periodo': {
        'venda_ini': (HOJE - timedelta(days=60)).strftime('%d/%m/%Y'),
        'venda_fim': HOJE.strftime('%d/%m/%Y'),
        'compra_ini': f'01/01/{ANO}',
        'compra_fim': HOJE.strftime('%d/%m/%Y'),
        'ano': ANO
    },
    'marcas': marcas_out,
    'sugestoes': sugestoes,
    'chegadas_mes': chegadas,
    'curva': curva,
    '_meta': {
        'unidade': 'peças',
        'marcas_com_match': sum(1 for m in marcas_out if m['produtos']),
        'sugestoes_total': len(sugestoes),
        'sugestao_total_pecas': sum(s['sugestao_compra'] for s in sugestoes),
        'criticas': sum(1 for s in sugestoes if s['cobertura_dias'] < 60 and s['sugestao_compra']>0),
        'transito_zerado_count': len(zerados),
        'pendentes_log': pendentes_log,
        'notas_processadas': len(notas),
        'bug_fix_2026_05_21': 'Etapa 3.7 agora zera trânsito baseado em data_lancamento (lançamento ERP) últimos 30 dias, não só mês corrente emissão. Chegadas inclui lançadas recentes independente de mês emissão.'
    }
}

OUT = ROOT / 'dados.json'
OUT.write_text(json.dumps(saida, ensure_ascii=False))
(ROOT / 'dados.js').write_text('window.DADOS = ' + json.dumps(saida, ensure_ascii=False) + ';\n')

print(json.dumps({
    'marcas': len(saida['marcas']),
    'marcas_com_match': saida['_meta']['marcas_com_match'],
    'sugestoes': len(sugestoes),
    'criticas': saida['_meta']['criticas'],
    'transito_zerado': len(zerados),
    'chegadas': {l: len(chegadas[l]) for l in LOJAS},
    'chegadas_lancadas': {l: sum(1 for c in chegadas[l] if c['origem']=='lancada') for l in LOJAS}
}, ensure_ascii=False, indent=2))
