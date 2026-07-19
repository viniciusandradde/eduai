#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera simulados.json e nivelamento.json a partir das questões das trilhas
(app/conteudo_olimpiadas/trilha_*.json). Determinístico: ordena blocos por
valor (3→4→5, como a prova oficial) e por id dentro do bloco."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / 'app'
sys.path.insert(0, str(APP))
import olimpiadas as oli  # noqa: E402

BASE = APP / 'conteudo_olimpiadas'
NOMES_SIM = {"P": "Simulado Oficial P #1", "E": "Simulado Oficial E #1", "B": "Simulado Oficial B #1"}


def main():
    questoes = []
    for nome in ('trilha_p.json', 'trilha_e.json', 'trilha_b.json'):
        questoes.extend(json.loads((BASE / nome).read_text(encoding='utf-8'))["questoes"])

    simulados = []
    for t in oli.TRILHAS:
        comp, ajuste = oli.COMPOSICAO[t]
        ids = []
        for valor in sorted(comp):
            bloco = sorted(q["id"] for q in questoes
                           if q["trilha"] == t and q["uso"] == "simulado" and q["valor_pontos"] == valor)
            assert len(bloco) == comp[valor], f"trilha {t} valor {valor}: {len(bloco)} != {comp[valor]}"
            ids.extend(bloco)
        simulados.append({"id": f"sim_{t.lower()}_1", "trilha": t, "nome": NOMES_SIM[t],
                          "duracao_seg": 6000, "ajuste": ajuste, "questoes": ids})

    niv_ids = []
    for t in oli.TRILHAS:
        bloco = sorted((q for q in questoes if q["trilha"] == t and q["uso"] == "nivelamento"),
                       key=lambda q: (q["valor_pontos"], q["id"]))
        assert len(bloco) == 4, f"trilha {t}: {len(bloco)} questões de nivelamento"
        niv_ids.extend(q["id"] for q in bloco)
    nivelamento = {"questoes": niv_ids,
                   "regras": {"idade_base": {"8": "P", "9": "P", "10": "E", "11": "E", "12": "B", "13": "B"}}}

    (BASE / 'simulados.json').write_text(
        json.dumps({"simulados": simulados}, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    (BASE / 'nivelamento.json').write_text(
        json.dumps(nivelamento, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

    estr = json.loads((BASE / 'estrategias.json').read_text(encoding='utf-8'))["estrategias"]
    oli.validar(questoes, simulados, estr, nivelamento)
    print(f"OK: {len(questoes)} questões, {len(simulados)} simulados, {len(niv_ids)} de nivelamento")


if __name__ == '__main__':
    main()
