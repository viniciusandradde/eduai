#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sanidade do banco autoral REAL (conteudo_olimpiadas/). Gate de qualidade:
nenhum lote de questões entra sem esta suíte verde."""
import pytest
import olimpiadas as oli


@pytest.fixture(scope='module')
def banco():
    oli.carregar()      # valida tudo (levanta ValueError se inconsistente)
    return oli


def test_carrega_e_valida(banco):
    assert banco.QUESTOES and banco.SIMULADOS and banco.ESTRATEGIAS and banco.NIVELAMENTO


def test_totais_do_mvp(banco):
    por_trilha = {t: [q for q in banco.QUESTOES.values() if q["trilha"] == t] for t in banco.TRILHAS}
    assert len(por_trilha["P"]) == 52
    assert len(por_trilha["E"]) == 52
    assert len(por_trilha["B"]) == 58
    assert len(banco.QUESTOES) == 162


def test_unidades_composicao(banco):
    """Cada eixo de cada trilha: 6 questões de prática (2×3, 2×4, 2×5 pts)."""
    for t in banco.TRILHAS:
        for eixo in banco.EIXO_IDS:
            qs = banco.questoes_da_unidade(t, eixo)
            assert len(qs) == 6, f"{t}/{eixo}: {len(qs)} questões de unidade"
            valores = sorted(q["valor_pontos"] for q in qs)
            assert valores == [3, 3, 4, 4, 5, 5], f"{t}/{eixo}: {valores}"
            assert [q["valor_pontos"] for q in qs] == valores   # ordenadas fácil→difícil


def test_simulados_oficiais(banco):
    assert set(banco.SIMULADOS) == {"sim_p_1", "sim_e_1", "sim_b_1"}
    for sid, s in banco.SIMULADOS.items():
        comp, ajuste = banco.COMPOSICAO[s["trilha"]]
        assert s["ajuste"] == ajuste
        assert s["duracao_seg"] == 6000                      # 100 minutos oficiais
        assert len(s["questoes"]) == sum(comp.values())
        eixos = {banco.QUESTOES[q]["eixo"] for q in s["questoes"]}
        assert eixos == set(banco.EIXO_IDS), f"{sid} não varre os 4 eixos"
        valores = [banco.QUESTOES[q]["valor_pontos"] for q in s["questoes"]]
        assert valores == sorted(valores), f"{sid} não está em blocos 3→4→5"


def test_nivelamento_12_questoes(banco):
    ids = banco.NIVELAMENTO["questoes"]
    assert len(ids) == 12
    for t in banco.TRILHAS:
        bloco = [banco.QUESTOES[q] for q in ids if banco.QUESTOES[q]["trilha"] == t]
        assert len(bloco) == 4
        assert sorted(q["valor_pontos"] for q in bloco) == [3, 4, 4, 5]
    assert set(banco.NIVELAMENTO["regras"]["idade_base"]) == {"8", "9", "10", "11", "12", "13"}


def test_estrategias_completas(banco):
    ids = [e["id"] for e in banco.ESTRATEGIAS]
    assert sorted(ids) == sorted(["desenhar", "regressiva", "testar_alternativas",
                                  "casos_pequenos", "tabela_lista", "padroes", "eliminacao"])
    for e in banco.ESTRATEGIAS:
        assert len(e["aula"].split()) >= 60, f"aula de {e['id']} curta demais"
        assert e["nome"] and e["emoji"]
    usadas = {q["estrategia_alvo"] for q in banco.QUESTOES.values()}
    assert usadas == set(ids), "todas as 7 estratégias devem ser exercitadas no banco"


def test_bncc_por_faixa(banco):
    """Habilidade BNCC compatível com a faixa da trilha (EF03/04 → P, etc.)."""
    faixas = {"P": ("EF03", "EF04"), "E": ("EF05", "EF06"), "B": ("EF07", "EF08")}
    for q in banco.QUESTOES.values():
        assert q["habilidade_bncc"].startswith(faixas[q["trilha"]]), \
            f"{q['id']}: BNCC {q['habilidade_bncc']} fora da faixa da trilha {q['trilha']}"


def test_gabarito_espalhado(banco):
    """Anti-vício: em cada trilha, nenhuma posição de gabarito domina (>50%)."""
    for t in banco.TRILHAS:
        qs = [q for q in banco.QUESTOES.values() if q["trilha"] == t]
        for pos in range(5):
            n = sum(1 for q in qs if q["gabarito"] == pos)
            assert n <= len(qs) / 2, f"trilha {t}: gabarito {pos} aparece {n}/{len(qs)} vezes"
