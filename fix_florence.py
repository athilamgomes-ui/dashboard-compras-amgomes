#!/usr/bin/env python3
"""Corrige atribuição: FLORENCE INDUSTRIAL E COMERCIAL → Marco Boni nas 3 NFs reportadas."""
import json
from pathlib import Path

ROOT = Path('/Users/elkgomes/Desktop/claude/compras')
d = json.loads((ROOT/'dados.json').read_text())

ALVO = [('L1','679575'), ('L3','679564'), ('L4','679728')]
MARCA = 'Marco Boni'

# Mapear marca → idx
marca_idx = {m['marca']: m for m in d['marcas']}
mk = marca_idx.get(MARCA)
if not mk:
    raise SystemExit(f"Marca {MARCA} não encontrada")

# Corrigir chegadas_mes
moved = []
for loja, nf in ALVO:
    for x in d['chegadas_mes'][loja]:
        if str(x.get('nf','')) == nf:
            old = x['marca']
            x['marca'] = MARCA
            moved.append({'loja':loja, 'nf':nf, 'valor':x['valor'], 'old':old, 'new':MARCA})
            # Somar em compras_mensais_rs da Marco Boni (NF é maio)
            cm = mk['compras_mensais_rs'][loja]
            cm['5'] = cm.get('5', 0) + x['valor']
            break

# Reordenar chegadas por data (mantém)
for loja in ('L1','L3','L4','L5'):
    d['chegadas_mes'][loja].sort(key=lambda x: x.get('data_lcto') or x.get('data',''), reverse=True)

# Salvar
(ROOT/'dados.json').write_text(json.dumps(d, ensure_ascii=False))
(ROOT/'dados.js').write_text('window.DADOS = ' + json.dumps(d, ensure_ascii=False) + ';\n')

print(json.dumps({'moved':moved}, ensure_ascii=False, indent=2))
