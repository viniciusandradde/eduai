#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ciclo de vida do simulado no DB: timer com relógio injetado, autosave,
branco reversível, retomada e recompensas idempotentes."""
import json
from datetime import datetime, timedelta

import db

T0 = datetime(2026, 7, 18, 10, 0, 0)


def _inicia(aid, dur=6000):
    s = db.oli_simulado_iniciar(aid, "sim_e_1", "E", dur, agora=T0)
    assert s["id"] and not s.get("erro")
    return s


def test_iniciar_retomar_e_um_por_vez(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    s = _inicia(aid)
    assert db.oli_sim_restante(s, T0) == 6000
    retomado = db.oli_simulado_iniciar(aid, "sim_e_1", "E", 6000, agora=T0 + timedelta(seconds=60))
    assert retomado["id"] == s["id"]
    outro = db.oli_simulado_iniciar(aid, "sim_p_1", "P", 6000, agora=T0)
    assert outro["erro"] == "outro_aberto" and outro["aberto"]["id"] == s["id"]


def test_salvar_branco_reversivel_e_marcadas(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    s = _inicia(aid)
    t = T0 + timedelta(seconds=100)
    r = db.oli_simulado_salvar(aid, s["id"], "q1", resposta=2, marcadas=["q1"], agora=t)
    assert r["ok"] and r["restante_seg"] == 5900
    r = db.oli_simulado_salvar(aid, s["id"], "q1", branco=True, agora=t)
    assert r["ok"]
    row = db.oli_simulado_aberto(aid)
    assert row["respostas"]["q1"]["r"] is None and row["respostas"]["q1"]["branco"] == 1
    assert row["marcadas"] == ["q1"]
    r = db.oli_simulado_salvar(aid, s["id"], "q1", resposta=4, agora=t)   # branco → resposta de novo
    assert db.oli_simulado_aberto(aid)["respostas"]["q1"]["r"] == 4
    r = db.oli_simulado_salvar(aid, s["id"], "q1", limpar=True, agora=t)  # limpar remove
    assert "q1" not in db.oli_simulado_aberto(aid)["respostas"]


def test_timer_expira_com_tolerancia(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    s = _inicia(aid, dur=6000)
    dentro = T0 + timedelta(seconds=6000 + db.OLI_TOLERANCIA_SEG - 1)
    assert db.oli_simulado_salvar(aid, s["id"], "q1", resposta=1, agora=dentro)["ok"]
    fora = T0 + timedelta(seconds=6000 + db.OLI_TOLERANCIA_SEG + 1)
    r = db.oli_simulado_salvar(aid, s["id"], "q2", resposta=1, agora=fora)
    assert r.get("expirado")
    row = db.oli_simulado_aberto(aid)
    assert "q2" not in row["respostas"]           # nada salvo depois de expirar
    assert db.oli_sim_expirado(row, fora) and not db.oli_sim_expirado(row, dentro)
    assert db.oli_sim_restante(row, fora) == 0


def test_enviar_recompensa_uma_vez(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    s = _inicia(aid)
    antes = db.get_aluno(aid)
    r1 = db.oli_simulado_enviar(aid, s["id"], 49.0, json.dumps({"nota": 49.0}), auto=1)
    assert r1["ok"] and r1["xp_ganho"] == 49 and r1["moedas_ganhas"] == db.OLI_MOEDAS_SIMULADO
    r2 = db.oli_simulado_enviar(aid, s["id"], 99.0, "{}")
    assert r2.get("ja_enviado") and r2["nota"] == 49.0
    depois = db.get_aluno(aid)
    assert depois["xp"] == antes["xp"] + 49
    assert depois["moedas"] == antes["moedas"] + db.OLI_MOEDAS_SIMULADO
    perfil = db.oli_perfil_get(aid)
    assert perfil["saltos"] == 49
    hist = db.oli_simulados_do_aluno(aid)
    assert len(hist) == 1 and hist[0]["nota"] == 49.0 and hist[0]["auto"] == 1
    assert db.oli_simulado_aberto(aid) is None
    fechado = db.oli_simulado_get(aid, s["id"])
    assert fechado["detalhe"] == {"nota": 49.0}
    r = db.oli_simulado_salvar(aid, s["id"], "q1", resposta=1)
    assert r["erro"] == "ja_enviado"


def test_nota_negativa_nao_da_xp_negativo(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    s = _inicia(aid)
    antes = db.get_aluno(aid)
    r = db.oli_simulado_enviar(aid, s["id"], -3.5, "{}")
    assert r["ok"] and r["xp_ganho"] == 0 and r["saltos_ganhos"] == 0
    assert db.get_aluno(aid)["xp"] == antes["xp"]


def test_registrar_resposta_pratica(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    r1 = db.oli_registrar_resposta(aid, "e-num-001", "E", "numeros", acertou=False, pontos=3)
    assert not r1["primeira_vez_certa"] and r1["xp_ganho"] == 0
    r2 = db.oli_registrar_resposta(aid, "e-num-001", "E", "numeros", acertou=True, pontos=3)
    assert r2["primeira_vez_certa"] and r2["saltos_ganhos"] == 3 and r2["xp_ganho"] == 6
    r3 = db.oli_registrar_resposta(aid, "e-num-001", "E", "numeros", acertou=True, pontos=3)
    assert not r3["primeira_vez_certa"] and r3["xp_ganho"] == 0   # repetir não farma XP
    prog = db.oli_progresso_list(aid, "E")
    assert len(prog) == 1 and prog[0]["acertou"] == 1 and prog[0]["tentativas"] == 3
    assert db.oli_perfil_get(aid)["saltos"] == 3
    assert db.atividades_hoje(aid) == 0            # não consome o limite diário de leitura


def test_perfil_trilha_e_medalha(novo_aluno):
    aid = novo_aluno()["aluno"]["id"]
    assert db.oli_perfil_get(aid) is None
    p = db.oli_perfil_set_trilha(aid, "E", "nivelamento", json.dumps({"acertos": 7}))
    assert p["trilha"] == "E" and p["origem"] == "nivelamento"
    p2 = db.oli_perfil_set_trilha(aid, "B", "pais")
    assert p2["trilha"] == "B" and p2["origem"] == "pais"
    assert json.loads(p2["nivelamento_json"]) == {"acertos": 7}   # ajuste dos pais preserva diagnóstico
    m1 = db.medalha_conceder(aid, "oli_nivelado")
    assert m1 and m1["emoji"] == "🦘"
    assert db.medalha_conceder(aid, "oli_nivelado") is None       # idempotente
