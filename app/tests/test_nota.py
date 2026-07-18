#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de nota do simulado (Anexo A do PRD) — fixtures inline, sem conteúdo real."""
import olimpiadas as oli


def _questao(qid, valor, eixo="numeros", gabarito=0):
    return {"id": qid, "trilha": "E", "eixo": eixo, "valor_pontos": valor, "uso": "simulado",
            "enunciado": f"Enunciado {qid}", "alternativas": ["A", "B", "C", "D", "E"],
            "gabarito": gabarito, "solucao_passo_a_passo": "1) conta. 2) resposta.",
            "distratores_explicados": {str(i): "erro comum" for i in range(5) if i != gabarito},
            "estrategia_alvo": "desenhar", "habilidade_bncc": "EF05MA01"}


def _monta(trilha="E"):
    comp, ajuste = oli.COMPOSICAO[trilha]
    questoes, ids = {}, []
    n = 0
    for valor, qtd in comp.items():
        for _ in range(qtd):
            qid = f"t-{valor}-{n}"; n += 1
            questoes[qid] = _questao(qid, valor, eixo=oli.EIXO_IDS[n % 4])
            ids.append(qid)
    sim = {"id": f"sim_{trilha.lower()}", "trilha": trilha, "ajuste": ajuste,
           "duracao_seg": 6000, "questoes": ids}
    return sim, questoes


def _ids_por_valor(sim, questoes, valor):
    return [q for q in sim["questoes"] if questoes[q]["valor_pontos"] == valor]


def test_caso_aceite_prd_49():
    """Critério de aceite do PRD (Anexo A): 10 acertos de 3 pts, 5 erros de 4 pts,
    resto em branco, ajuste da trilha E → 30 − 5,0 + 24 = 49,0."""
    qs = {}
    ids = []
    for i in range(10):
        qid = f"a3-{i}"; qs[qid] = _questao(qid, 3); ids.append(qid)
    for i in range(5):
        qid = f"e4-{i}"; qs[qid] = _questao(qid, 4); ids.append(qid)
    for i in range(9):
        qid = f"b5-{i}"; qs[qid] = _questao(qid, 5); ids.append(qid)
    sim = {"id": "sim_aceite", "trilha": "E", "ajuste": 24, "duracao_seg": 6000, "questoes": ids}
    respostas = {f"a3-{i}": qs[f"a3-{i}"]["gabarito"] for i in range(10)}
    respostas.update({f"e4-{i}": (qs[f"e4-{i}"]["gabarito"] + 1) % 5 for i in range(5)})
    assert oli.calcular_nota(sim, respostas, qs) == 49.0


def test_tudo_certo_maximo():
    for trilha, esperado in (("P", 120.0), ("E", 120.0), ("B", 150.0)):
        sim, qs = _monta(trilha)
        respostas = {qid: qs[qid]["gabarito"] for qid in sim["questoes"]}
        assert oli.calcular_nota(sim, respostas, qs) == esperado
        assert oli.nota_maxima(sim, qs) == esperado


def test_tudo_errado_zera_exato():
    """Propriedade do ajuste oficial: errar todas dá exatamente 0."""
    for trilha in ("P", "E", "B"):
        sim, qs = _monta(trilha)
        respostas = {qid: (qs[qid]["gabarito"] + 1) % 5 for qid in sim["questoes"]}
        assert oli.calcular_nota(sim, respostas, qs) == 0.0


def test_tudo_branco_da_ajuste():
    for trilha in ("P", "E", "B"):
        sim, qs = _monta(trilha)
        assert oli.calcular_nota(sim, {}, qs) == float(sim["ajuste"])


def test_branco_explicito_igual_nao_visitada():
    sim, qs = _monta("E")
    explicito = {qid: None for qid in sim["questoes"]}
    assert oli.calcular_nota(sim, explicito, qs) == oli.calcular_nota(sim, {}, qs)


def test_penalidades_exatas():
    sim, qs = _monta("E")
    for valor, pena in ((3, -0.75), (4, -1.0), (5, -1.25)):
        qid = _ids_por_valor(sim, qs, valor)[0]
        nota = oli.calcular_nota(sim, {qid: (qs[qid]["gabarito"] + 1) % 5}, qs)
        assert nota == round(sim["ajuste"] + pena, 2)


def test_relatorio_chute_branco_eixo_valor():
    sim, qs = _monta("E")
    tres = _ids_por_valor(sim, qs, 3)
    respostas = {tres[0]: qs[tres[0]]["gabarito"],            # 1 acerto
                 tres[1]: (qs[tres[1]]["gabarito"] + 1) % 5,  # 1 chute (erro)
                 tres[2]: None}                               # 1 branco explícito
    rel = oli.montar_relatorio(sim, respostas, "2026-07-18T10:00:00", "2026-07-18T11:00:00", [40.0], qs)
    assert rel["acertos"] == 1 and rel["chutes"] == 1 and rel["brancos"] == 22
    assert rel["por_valor"][3]["acertos"] == 1 and rel["por_valor"][3]["erros"] == 1
    assert rel["nota"] == oli.calcular_nota(sim, respostas, qs)
    assert rel["tempo_total_seg"] == 3600 and rel["tempo_medio_seg"] == 150
    assert rel["delta"] == round(rel["nota"] - 40.0, 2)
    assert sum(e["total"] for e in rel["por_eixo"].values()) == 24
    erro_det = next(d for d in rel["questoes"] if d["status"] == "erro")
    assert erro_det["distrator_explicado"]


def test_sugerir_trilha_por_idade():
    vazio = {}
    assert oli.sugerir_trilha(8, vazio) == "P"
    assert oli.sugerir_trilha(9, vazio) == "P"
    assert oli.sugerir_trilha(10, vazio) == "E"
    assert oli.sugerir_trilha(11, vazio) == "E"
    assert oli.sugerir_trilha(12, vazio) == "B"
    assert oli.sugerir_trilha(13, vazio) == "B"
    assert oli.sugerir_trilha(0, vazio) == "E"


def test_sugerir_trilha_ajusta_pelo_desempenho():
    # sobe: 10 anos (base E) mas ≥75% no bloco B
    assert oli.sugerir_trilha(10, {"E": (3, 4), "B": (3, 4)}) == "B"
    # desce: 12 anos (base B) mas <40% no bloco B
    assert oli.sugerir_trilha(12, {"B": (1, 4), "E": (2, 4)}) == "E"
    # mantém: desempenho mediano
    assert oli.sugerir_trilha(10, {"E": (2, 4), "B": (2, 4)}) == "E"
    # P não desce; B não sobe
    assert oli.sugerir_trilha(8, {"P": (0, 4)}) == "P"
    assert oli.sugerir_trilha(13, {"B": (4, 4)}) == "B"


def test_sanitizar_questao_remove_segredos():
    q = _questao("x-1", 3)
    s = oli.sanitizar_questao(q)
    for campo in oli.CAMPOS_SECRETOS:
        assert campo not in s
    assert s["enunciado"] and len(s["alternativas"]) == 5


def test_corrigir_erro_traz_distrator():
    q = _questao("x-1", 3, gabarito=2)
    qs = {"x-1": q}
    ok = oli.corrigir("x-1", 2, qs)
    assert ok["correto"] and "distrator_explicado" not in ok
    err = oli.corrigir("x-1", 4, qs)
    assert not err["correto"] and err["distrator_explicado"] == "erro comum"
    assert oli.corrigir("x-1", 9, qs) is None
    assert oli.corrigir("nao-existe", 1, qs) is None


def test_validar_pega_defeitos():
    import pytest
    estr = [{"id": "desenhar", "nome": "Desenhe", "emoji": "✏️", "aula": "..."}]
    niv = {"questoes": []}
    ok = _questao("e-num-001", 3)
    oli.validar([ok], [], estr, niv)                       # banco válido não levanta
    quebrada = dict(ok, alternativas=["A", "B", "C"])
    with pytest.raises(ValueError, match="5 alternativas"):
        oli.validar([quebrada], [], estr, niv)
    sem_dist = dict(ok, distratores_explicados={"1": "x"})
    with pytest.raises(ValueError, match="distratores"):
        oli.validar([sem_dist], [], estr, niv)
    with pytest.raises(ValueError, match="composição"):
        oli.validar([ok], [{"id": "s1", "trilha": "E", "ajuste": 24, "duracao_seg": 6000,
                            "questoes": ["e-num-001"]}], estr, niv)
