#!/usr/bin/env python3
"""
Compara dados.json (atual) com dados_anterior.json (snapshot da execução anterior)
e injeta `_diff` em dados.json com:
  - rupturas_novas: marcas S que tinham cobertura>=60 ontem e <60 hoje (por loja)
  - rupturas_resolvidas: marcas S que estavam <60 ontem e >=60 hoje
  - chegadas_novas: NFs em chegadas_mes que não estavam ontem (chave: loja|nf|fornecedor)
  - chegadas_lancadas: NFs que ontem estavam 'pendente' e hoje estão 'lancada'
Depois regenera dados.js e copia dados.json -> dados_anterior.json para próxima rodada.

Uso: python3 compute_diff.py
Roda na pasta /Users/elkgomes/Desktop/claude/compras/
"""
import json, os, sys, shutil
from pathlib import Path

ROOT = Path('/Users/elkgomes/Desktop/claude/compras')
NEW = ROOT / 'dados.json'
PREV = ROOT / 'dados_anterior.json'
JS = ROOT / 'dados.js'

def load(p):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"warn: falha ler {p}: {e}", file=sys.stderr)
        return None

def rupturas_set(dados):
    """Retorna dict {(marca,loja): cobertura} para sugestoes curva S com cobertura<60."""
    out = {}
    for s in dados.get('sugestoes', []):
        if s.get('curva') == 'S' and s.get('cobertura_dias', 9999) < 60:
            out[(s['marca'], s['loja'])] = s['cobertura_dias']
    return out

def chegadas_keys(dados):
    """Retorna dict {(loja,nf,fornecedor): origem} para todas as chegadas_mes."""
    out = {}
    ch = dados.get('chegadas_mes', {}) or {}
    for loja in ('L1','L3','L4','L5'):
        for x in (ch.get(loja) or []):
            key = (loja, str(x.get('nf','')), x.get('fornecedor',''))
            out[key] = x.get('origem','')
    return out

def main():
    new = load(NEW)
    if not new:
        print("erro: dados.json não encontrado ou inválido", file=sys.stderr)
        sys.exit(1)
    prev = load(PREV)

    diff = {
        'comparado_com': None,
        'rupturas_novas': [],
        'rupturas_resolvidas': [],
        'chegadas_novas': [],
        'chegadas_lancadas': [],
    }

    if prev:
        diff['comparado_com'] = prev.get('gerado_em')
        rN = rupturas_set(new)
        rP = rupturas_set(prev)
        for k, cob in rN.items():
            if k not in rP:
                diff['rupturas_novas'].append({
                    'marca': k[0], 'loja': k[1], 'cobertura_dias': round(cob,1)
                })
        for k, cob in rP.items():
            if k not in rN:
                diff['rupturas_resolvidas'].append({
                    'marca': k[0], 'loja': k[1], 'cobertura_anterior': round(cob,1)
                })

        cN = chegadas_keys(new)
        cP = chegadas_keys(prev)
        ch_new = new.get('chegadas_mes', {}) or {}
        for loja in ('L1','L3','L4','L5'):
            for x in (ch_new.get(loja) or []):
                key = (loja, str(x.get('nf','')), x.get('fornecedor',''))
                if key not in cP:
                    diff['chegadas_novas'].append({**x, 'loja': loja})
                elif cP[key] == 'pendente' and x.get('origem') == 'lancada':
                    diff['chegadas_lancadas'].append({**x, 'loja': loja})

        # Sort listas para visualização estável
        diff['rupturas_novas'].sort(key=lambda r: r['cobertura_dias'])
        diff['rupturas_resolvidas'].sort(key=lambda r: r['marca'])
        diff['chegadas_novas'].sort(key=lambda r: r.get('data_emissao',''), reverse=True)
        diff['chegadas_lancadas'].sort(key=lambda r: r.get('data_lancamento',''), reverse=True)
    else:
        diff['comparado_com'] = '(primeira execução — sem snapshot anterior)'

    new['_diff'] = diff

    # Salva dados.json com _diff
    NEW.write_text(json.dumps(new, ensure_ascii=False))
    # Regenera dados.js
    JS.write_text('window.DADOS = ' + json.dumps(new, ensure_ascii=False) + ';\n')
    # Atualiza snapshot anterior pra próxima rodada
    shutil.copy(NEW, PREV)

    # Output resumido pro stdout (Etapa 5.6 lê isso)
    summary = {
        'rupturas_novas': len(diff['rupturas_novas']),
        'rupturas_resolvidas': len(diff['rupturas_resolvidas']),
        'chegadas_novas': len(diff['chegadas_novas']),
        'chegadas_lancadas': len(diff['chegadas_lancadas']),
        'top_rupturas': [f"{r['marca']}/{r['loja']}" for r in diff['rupturas_novas'][:5]],
        'top_chegadas': [f"{c['loja']} {c['marca']} R${c.get('valor',0):.0f}" for c in diff['chegadas_novas'][:5]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
