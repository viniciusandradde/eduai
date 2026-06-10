#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — Edu Help (FAQ roteirizado, offline).
Carrega a base de conhecimento curada (eduhelp.json) e responde dúvidas do
aluno por casamento de palavras-chave. Sem IA externa: determinístico, grátis
e seguro para criança. Os valores das regras (limite diário, tempo do Tux,
XP por nível, limiares de estrela) são interpolados com a config real.
"""
import json, re, unicodedata
from pathlib import Path

KB_PATH = Path(__file__).parent / 'eduhelp.json'


def _norm(s):
    """Minúsculas + sem acento, para casar pergunta e palavras-chave."""
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _tokens(s):
    return set(re.findall(r'[a-z0-9]+', _norm(s)))


def _carregar():
    try:
        kb = json.loads(KB_PATH.read_text(encoding='utf-8'))
    except Exception:
        kb = {"saudacao": "Oi! Eu sou o Edu 🐧", "fallback": "Tente uma destas:", "entradas": []}
    for e in kb.get("entradas", []):
        # separa palavras-chave em tokens (1 palavra) e frases (2+ palavras)
        kws, phrs = set(), []
        for p in e.get("palavras", []):
            pn = _norm(p)
            if ' ' in pn:
                phrs.append(pn)
            else:
                kws |= {t for t in re.findall(r'[a-z0-9]+', pn)}
        e["_kw"] = kws
        e["_phr"] = phrs
        e["_chip"] = _norm(e.get("chip", ""))
    return kb


KB = _carregar()


def _interpolar(texto, cfg):
    cfg = cfg or {}
    repl = {
        "{limite}":   str(cfg.get("limite", 2)),
        "{tux_min}":  str(cfg.get("tux_min", 60)),
        "{xp_nivel}": str(cfg.get("xp_nivel", 200)),
        "{est1}":     str(cfg.get("est1", 40)),
        "{est2}":     str(cfg.get("est2", 70)),
        "{est3}":     str(cfg.get("est3", 90)),
    }
    for k, v in repl.items():
        texto = texto.replace(k, v)
    return texto


def _chip(e):
    return {"id": e["id"], "texto": e.get("chip", "")}


def sugestoes(cfg=None, por_grupo=2):
    """Chips iniciais agrupados (Como funciona / Matérias / Dicas)."""
    grupos = {}
    for e in KB.get("entradas", []):
        grupos.setdefault(e.get("grupo", "Outros"), []).append(e)
    ordem = ["Como funciona", "Matérias", "Dicas"]
    saida = []
    for titulo in ordem:
        itens = grupos.get(titulo, [])
        if itens:
            saida.append({"titulo": titulo, "chips": [_chip(e) for e in itens[:por_grupo]]})
    return {"saudacao": KB.get("saudacao", ""), "grupos": saida}


def _por_id(eid):
    return next((e for e in KB.get("entradas", []) if e["id"] == eid), None)


def _score(e, qn, qtok):
    """Tokens valem 1; frases (2+ palavras) e o chip exato valem 3."""
    s = len(e["_kw"] & qtok)
    s += 3 * sum(1 for ph in e["_phr"] if ph and ph in qn)
    if e["_chip"] and e["_chip"] in qn:
        s += 3
    return s


def responder(pergunta, cfg=None):
    """Casa a pergunta com a melhor entrada da KB; senão devolve fallback."""
    raw = (pergunta or "").strip()
    # atalho: clique num chip manda o id exato
    melhor = _por_id(raw) if raw else None
    if melhor is None and raw:
        qn = _norm(raw)
        qtok = _tokens(raw)
        score = 0
        for e in KB.get("entradas", []):
            s = _score(e, qn, qtok)
            if s > score:
                melhor, score = e, s
    if melhor is None:
        # fallback: 3 sugestões variadas
        entradas = KB.get("entradas", [])
        amostra = [entradas[i] for i in (0, len(entradas) // 2, len(entradas) - 1)] if entradas else []
        return {"resposta": KB.get("fallback", "Tente reformular."),
                "sugestoes": [_chip(e) for e in amostra]}
    # follow-ups: outros chips do mesmo grupo
    grupo = melhor.get("grupo")
    relacionados = [e for e in KB.get("entradas", []) if e.get("grupo") == grupo and e["id"] != melhor["id"]]
    return {"resposta": _interpolar(melhor.get("resposta", ""), cfg),
            "sugestoes": [_chip(e) for e in relacionados[:3]]}
