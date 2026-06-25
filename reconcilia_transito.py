#!/usr/bin/env python3
"""Reconciliação de trânsito — RODA APÓS build_dashboard.py.

Para CADA NFe pendente do ERP (compras_raw.json), confere se a quantidade está
refletida no trânsito do dashboard (dados.json) na marca×loja certa, e classifica
toda divergência por motivo. É o autocheck que torna o dashboard confiável: novos
fornecedores não mapeados ou marcas de curva com trânsito sumido aparecem AUTOMÁTICO
a cada execução, em vez de serem descobertos um a um pelo gerente.

Reusa as MESMAS regras de detecção do build_dashboard.py (extraídas da fonte, não
duplicadas) para nunca divergir do que o dashboard realmente faz.

Saída: relatório no stdout + arquivo divergencias_transito.json (consumível pelo
dashboard se um dia quiser exibir). Sempre exit 0 — é diagnóstico, não bloqueia o pipeline.
"""
import json, re, sys, unicodedata
from datetime import datetime
import os

BASE = os.path.dirname(os.path.abspath(__file__))
def _p(f): return os.path.join(BASE, f)

raw = json.load(open(_p('compras_raw.json')))
dados = json.load(open(_p('dados.json')))
forn_marcas = json.load(open(_p('fornecedor_marcas.json')))
curva = json.load(open(_p('curva_marcas.json')))
ANO = datetime.now().year
EMP_TO_LOJA = {1:'L1',3:'L3',4:'L4',10:'L5'}

# --- Regras de detecção: extraídas da FONTE do build_dashboard.py (single source of truth) ---
_src = open(_p('build_dashboard.py')).read()
def _grab_dict(name):
    m = re.search(name + r' = \{(.*?)\n\}', _src, re.S)
    return eval('{'+m.group(1)+'\n}')
def _grab_set(name):
    m = re.search(name + r' = \{(.*?)\}', _src, re.S)
    return eval('{'+m.group(1)+'}')
BRAND_KEYWORDS = _grab_dict('BRAND_KEYWORDS')
EXCL_CFOP = _grab_set('EXCL_CFOP')
EXCL_NAT_RE = re.compile(r'^(REMESSA|AMOSTRA|BONIFIC|DEVOLU|RETORNO|TRANSFER|CONSIGNAC)', re.I)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().upper()
    return re.sub(r'\s+',' ',s).strip()

def marca_por_descricao(desc):
    d = norm(desc)
    for marca, kws in BRAND_KEYWORDS.items():
        for kw in kws:
            if kw.startswith('\\b'):
                if re.search(kw, d): return marca
            elif norm(kw) in d: return marca
    return None

def forn_brand_raw(nfe):
    cnpj = str(nfe.get('DadosEmitente',{}).get('Documento','')).replace('.','').replace('/','').replace('-','')
    v = forn_marcas.get('por_cnpj',{}).get(cnpj)
    if v is None:
        nome = (nfe.get('DadosEmitente',{}).get('Nome') or '').upper()
        for substr, marca in forn_marcas.get('por_nome_substring',{}).items():
            if substr.upper() in nome: v = marca; break
    return v

def keep_nfe(nfe):
    if EXCL_NAT_RE.match(nfe.get('NaturezaOperacao','') or ''): return False
    cfops = [str(p.get('CFOP','')) for p in (nfe.get('Produtos') or [])]
    if cfops and all(c in EXCL_CFOP for c in cfops): return False
    return True

ignorar = forn_marcas.get('_ignorar_no_dashboard',{}).get('por_nome_substring',[])
def is_ignorado(nome):
    n = (nome or '').upper()
    return any(s.upper() in n for s in ignorar)

curva_brands = set()
for lj in ('L1','L3','L4','L5'):
    for cv in ('S','A','B'):
        curva_brands.update(curva[lj][cv])

docs_lancados = {str(n['doc']).lstrip('0') for n in raw['notas'] if n.get('doc')}

# trânsito pendente refletido no dashboard, por (marca, loja)
dash_pend = {}
for mk in dados['marcas']:
    for lj in ('L1','L3','L4','L5'):
        tp = sum(p[lj].get('transito_pend',0) for p in mk['produtos'])
        if tp > 0: dash_pend[(mk['marca'], lj)] = tp

R = {'sem_marca':[], 'fora_curva':[], 'curva_nao_refletida':[], 'ok':[]}
esperado_curva = {}  # (marca,loja) -> un esperadas (curva)

for emp_s, blk in raw['pendentes'].items():
    loja = EMP_TO_LOJA.get(int(emp_s))
    if not loja: continue
    for nfe in blk.get('NFes',[]):
        de = nfe.get('DataEmissao')
        if not de: continue
        try: dt = datetime.fromisoformat(de.replace('Z','+00:00'))
        except: continue
        if dt.year != ANO or not keep_nfe(nfe): continue
        nome = nfe.get('DadosEmitente',{}).get('Nome') or ''
        if is_ignorado(nome): continue
        num = str(nfe.get('NumeroNFe') or nfe.get('Numero') or '').lstrip('0')
        if num and num in docs_lancados: continue  # já lançada → chegou
        prods = nfe.get('Produtos') or []
        qt = round(sum((p.get('QuantidadeComercial',0) or 0) for p in prods))
        forn_v = forn_brand_raw(nfe)
        is_multi = bool(forn_v) and '+' in forn_v
        forn_single = forn_v if (forn_v and not is_multi) else None
        marcas, sem = {}, 0
        for p in prods:
            mm = marca_por_descricao(p.get('DescricaoProduto',''))
            if not mm and not is_multi and forn_single: mm = forn_single
            q = p.get('QuantidadeComercial',0) or 0
            if mm: marcas[mm] = marcas.get(mm,0)+q
            else: sem += q
        info = {'loja':loja,'nf':num or '(s/nº)','forn':nome[:34],'qt':qt,'data':de[:10],
                'marcas':{k:round(v) for k,v in marcas.items()},'sem_un':round(sem)}
        curva_det = [m for m in marcas if m in curva_brands]
        if not marcas:
            R['sem_marca'].append(info)
        elif not curva_det:
            R['fora_curva'].append(info)
        else:
            for m in curva_det:
                esperado_curva[(m,loja)] = esperado_curva.get((m,loja),0)+marcas[m]
            R['ok'].append(info)

# Conferir: cada (marca curva, loja) esperada bate com o trânsito pendente do dashboard?
for (m,loja),esp in sorted(esperado_curva.items()):
    refl = dash_pend.get((m,loja),0)
    if refl + 0.5 < esp * 0.8:  # tolerância: matching fuzzy pode não pegar 100%
        R['curva_nao_refletida'].append({'marca':m,'loja':loja,'esperado_un':round(esp),'refletido_un':round(refl)})

# ---- Relatório ----
print("=== RECONCILIAÇÃO DE TRÂNSITO (pendentes ERP × dashboard) ===")
print(f"✅ curva em trânsito OK: {len(R['ok'])} NFes | "
      f"⚠️ fora da curva: {len(R['fora_curva'])} | "
      f"❌ sem marca: {len(R['sem_marca'])} | "
      f"🔴 curva NÃO refletida: {len(R['curva_nao_refletida'])}")

if R['curva_nao_refletida']:
    print("\n🔴 CURVA COM TRÂNSITO NÃO REFLETIDO (investigar matching/detecção):")
    for x in R['curva_nao_refletida']:
        print(f"   {x['loja']} {x['marca']:18} esperado {x['esperado_un']}un, refletido {x['refletido_un']}un")

if R['sem_marca']:
    print("\n❌ FORNECEDOR SEM MARCA (mapear em fornecedor_marcas.json se for revenda de curva):")
    for x in sorted(R['sem_marca'], key=lambda r:-r['qt']):
        print(f"   {x['loja']} NF {x['nf']:>9} {x['data']} {x['qt']:>5}un  {x['forn']}")

if R['fora_curva']:
    print("\n⚠️ DETECTADA MAS FORA DE QUALQUER CURVA (só rótulo, não vira sugestão):")
    for x in sorted(R['fora_curva'], key=lambda r:-r['qt']):
        print(f"   {x['loja']} NF {x['nf']:>9} {x['data']} {x['qt']:>5}un  {list(x['marcas'])}")

json.dump(R, open(_p('divergencias_transito.json'),'w'), ensure_ascii=False, indent=1)
print(f"\n→ divergencias_transito.json gravado ({len(R['sem_marca'])+len(R['fora_curva'])+len(R['curva_nao_refletida'])} itens a revisar)")
sys.exit(0)
