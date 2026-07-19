#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — módulo Olimpíadas de Matemática (estilo Canguru).
Loader/validador do banco autoral (conteudo_olimpiadas/), motor de nota do
simulado (regras oficiais: −25% por erro, branco 0, ajuste +24/+30),
sugestão de trilha do nivelamento e montagem de unidades/relatórios.
Gabaritos nunca saem daqui sem passar por sanitizar_questao().
"""
import json
from pathlib import Path

BASE_OLI = Path(__file__).parent / 'conteudo_olimpiadas'

TRILHAS = ("P", "E", "B")
TRILHA_NOMES = {"P": "Trilha P — 3º/4º ano", "E": "Trilha E — 5º/6º ano", "B": "Trilha B — 7º/8º ano"}
VALORES = (3, 4, 5)
PENALIDADE = 0.25          # erro desconta 25% do valor da questão
TOLERANCIA_SEG = 30        # margem de rede para o autoenvio
COMPOSICAO = {             # trilha -> (questões por valor, ajuste final)
    "P": ({3: 8, 4: 8, 5: 8}, 24),
    "E": ({3: 8, 4: 8, 5: 8}, 24),
    "B": ({3: 10, 4: 10, 5: 10}, 30),
}
EIXOS = [
    {"id": "numeros",   "nome": "Números Engenhosos",      "emoji": "🔢"},
    {"id": "geometria", "nome": "Geometria e Visualização", "emoji": "📐"},
    {"id": "logica",    "nome": "Lógica e Dedução",         "emoji": "🧩"},
    {"id": "contagem",  "nome": "Contagem e Padrões",       "emoji": "🎲"},
]
EIXO_IDS = [e["id"] for e in EIXOS]
USOS = ("unidade", "simulado", "nivelamento")
CAMPOS_SECRETOS = ("gabarito", "solucao_passo_a_passo", "distratores_explicados")

# Índices globais — preenchidos por carregar() no boot do app (e no test_banco)
QUESTOES: dict = {}       # id -> questão completa
SIMULADOS: dict = {}      # id -> definição do simulado
ESTRATEGIAS: list = []
NIVELAMENTO: dict = {}


# ── Validação (mesmas regras da suíte test_banco) ─────────────
def validar(questoes, simulados, estrategias, nivelamento):
    """Levanta ValueError com mensagem clara se o banco estiver inconsistente."""
    ids, enunciados = set(), set()
    estrategia_ids = {e["id"] for e in estrategias}
    for q in questoes:
        qid = q.get("id", "?")
        def erro(msg):
            raise ValueError(f"questão {qid}: {msg}")
        if not qid or qid in ids:
            erro("id vazio ou duplicado")
        ids.add(qid)
        if q.get("trilha") not in TRILHAS:
            erro(f"trilha inválida: {q.get('trilha')}")
        if q.get("eixo") not in EIXO_IDS:
            erro(f"eixo inválido: {q.get('eixo')}")
        if q.get("valor_pontos") not in VALORES:
            erro(f"valor_pontos inválido: {q.get('valor_pontos')}")
        if q.get("uso") not in USOS:
            erro(f"uso inválido: {q.get('uso')}")
        if not (q.get("enunciado") or "").strip():
            erro("enunciado vazio")
        if q["enunciado"] in enunciados:
            erro("enunciado duplicado")
        enunciados.add(q["enunciado"])
        alts = q.get("alternativas")
        if not isinstance(alts, list) or len(alts) != 5:
            erro("precisa de exatamente 5 alternativas")
        if len({str(a) for a in alts}) != 5:
            erro("alternativas repetidas")
        g = q.get("gabarito")
        if not isinstance(g, int) or not (0 <= g <= 4):
            erro(f"gabarito inválido: {g}")
        if not (q.get("solucao_passo_a_passo") or "").strip():
            erro("solucao_passo_a_passo vazia")
        dist = q.get("distratores_explicados") or {}
        esperados = {str(i) for i in range(5) if i != g}
        if set(dist.keys()) != esperados:
            erro(f"distratores_explicados deve cobrir exatamente os índices {sorted(esperados)}")
        if any(not (v or "").strip() for v in dist.values()):
            erro("explicação de distrator vazia")
        if q.get("estrategia_alvo") not in estrategia_ids:
            erro(f"estrategia_alvo desconhecida: {q.get('estrategia_alvo')}")
        if not (q.get("habilidade_bncc") or "").strip():
            erro("habilidade_bncc vazia")
    por_id = {q["id"]: q for q in questoes}

    sim_ids = set()
    for s in simulados:
        sid = s.get("id", "?")
        def serro(msg):
            raise ValueError(f"simulado {sid}: {msg}")
        if not sid or sid in sim_ids:
            serro("id vazio ou duplicado")
        sim_ids.add(sid)
        trilha = s.get("trilha")
        if trilha not in TRILHAS:
            serro(f"trilha inválida: {trilha}")
        comp, ajuste = COMPOSICAO[trilha]
        if s.get("ajuste") != ajuste:
            serro(f"ajuste deve ser {ajuste}")
        if not isinstance(s.get("duracao_seg"), int) or s["duracao_seg"] <= 0:
            serro("duracao_seg inválida")
        qids = s.get("questoes") or []
        if len(qids) != len(set(qids)):
            serro("questões repetidas")
        contagem = {v: 0 for v in VALORES}
        for qid in qids:
            q = por_id.get(qid)
            if not q:
                serro(f"questão inexistente: {qid}")
            if q["trilha"] != trilha:
                serro(f"questão {qid} é da trilha {q['trilha']}")
            if q["uso"] != "simulado":
                serro(f"questão {qid} não tem uso='simulado'")
            contagem[q["valor_pontos"]] += 1
        if contagem != comp:
            serro(f"composição {contagem} difere do oficial {comp}")

    niv = nivelamento.get("questoes") or []
    if len(niv) != len(set(niv)):
        raise ValueError("nivelamento: questões repetidas")
    por_trilha = {t: 0 for t in TRILHAS}
    for qid in niv:
        q = por_id.get(qid)
        if not q:
            raise ValueError(f"nivelamento: questão inexistente: {qid}")
        if q["uso"] != "nivelamento":
            raise ValueError(f"nivelamento: questão {qid} não tem uso='nivelamento'")
        por_trilha[q["trilha"]] += 1
    if niv and set(por_trilha.values()) != {4}:
        raise ValueError(f"nivelamento: precisa de 4 questões por trilha, veio {por_trilha}")


def carregar(base=None):
    """Lê conteudo_olimpiadas/, valida tudo e preenche os índices globais."""
    base = Path(base or BASE_OLI)
    questoes = []
    for nome in ("trilha_p.json", "trilha_e.json", "trilha_b.json"):
        data = json.loads((base / nome).read_text(encoding='utf-8'))
        questoes.extend(data["questoes"])
    simulados = json.loads((base / 'simulados.json').read_text(encoding='utf-8'))["simulados"]
    estrategias = json.loads((base / 'estrategias.json').read_text(encoding='utf-8'))["estrategias"]
    nivelamento = json.loads((base / 'nivelamento.json').read_text(encoding='utf-8'))
    validar(questoes, simulados, estrategias, nivelamento)
    QUESTOES.clear(); QUESTOES.update({q["id"]: q for q in questoes})
    SIMULADOS.clear(); SIMULADOS.update({s["id"]: s for s in simulados})
    ESTRATEGIAS[:] = estrategias
    NIVELAMENTO.clear(); NIVELAMENTO.update(nivelamento)
    return QUESTOES


# ── Sanitização e correção ────────────────────────────────────
def sanitizar_questao(q):
    """Versão da questão que pode ir ao cliente (sem gabarito/solução/distratores)."""
    return {k: v for k, v in q.items() if k not in CAMPOS_SECRETOS}


def estrategia_de(eid):
    return next((e for e in ESTRATEGIAS if e["id"] == eid), None)


def corrigir(qid, resposta, questoes=None):
    """Corrige uma resposta (0–4). Retorna None se a questão não existe."""
    q = (questoes or QUESTOES).get(qid)
    if not q:
        return None
    try:
        r = int(resposta)
    except (TypeError, ValueError):
        return None
    if not (0 <= r <= 4):
        return None
    correto = (r == q["gabarito"])
    out = {"correto": correto, "gabarito": q["gabarito"],
           "resposta_certa": q["alternativas"][q["gabarito"]],
           "solucao": q["solucao_passo_a_passo"],
           "valor_pontos": q["valor_pontos"],
           "estrategia": q["estrategia_alvo"]}
    if not correto:
        out["distrator_explicado"] = (q.get("distratores_explicados") or {}).get(str(r), "")
    return out


# ── Motor de nota (Anexo A do PRD) ────────────────────────────
def calcular_nota(simulado, respostas, questoes=None):
    """Acerto +valor; erro −25% do valor; branco/não visitada 0; + ajuste final.
    `respostas`: dict qid -> int (0–4) ou None (branco)."""
    qs = questoes or QUESTOES
    nota = float(simulado["ajuste"])
    for qid in simulado["questoes"]:
        q = qs[qid]
        r = respostas.get(qid)
        if r is None:
            continue
        if int(r) == q["gabarito"]:
            nota += q["valor_pontos"]
        else:
            nota -= PENALIDADE * q["valor_pontos"]
    return round(nota, 2)


def nota_maxima(simulado, questoes=None):
    qs = questoes or QUESTOES
    return round(simulado["ajuste"] + sum(qs[qid]["valor_pontos"] for qid in simulado["questoes"]), 2)


def montar_relatorio(simulado, respostas, iniciado_ts, enviado_ts, anteriores=None, questoes=None):
    """Relatório pós-simulado (RF-05): nota, por eixo, por valor, chute vs. branco,
    tempo médio, evolução e detalhe por questão (com solução — pós-envio)."""
    from datetime import datetime
    qs = questoes or QUESTOES
    nota = calcular_nota(simulado, respostas, qs)
    por_eixo = {e: {"acertos": 0, "erros": 0, "brancos": 0, "total": 0} for e in EIXO_IDS}
    por_valor = {v: {"acertos": 0, "erros": 0, "brancos": 0, "total": 0} for v in VALORES}
    detalhe = []
    acertos = erros = brancos = 0
    for i, qid in enumerate(simulado["questoes"]):
        q = qs[qid]
        r = respostas.get(qid)
        if r is None:
            status = "branco"; brancos += 1
        elif int(r) == q["gabarito"]:
            status = "acerto"; acertos += 1
        else:
            status = "erro"; erros += 1
        chave = {"acerto": "acertos", "erro": "erros", "branco": "brancos"}[status]
        por_eixo[q["eixo"]][chave] += 1; por_eixo[q["eixo"]]["total"] += 1
        por_valor[q["valor_pontos"]][chave] += 1; por_valor[q["valor_pontos"]]["total"] += 1
        detalhe.append({"n": i + 1, "id": qid, "eixo": q["eixo"], "valor_pontos": q["valor_pontos"],
                        "enunciado": q["enunciado"], "alternativas": q["alternativas"],
                        "resposta": r, "status": status, "gabarito": q["gabarito"],
                        "solucao": q["solucao_passo_a_passo"], "estrategia": q["estrategia_alvo"],
                        "distrator_explicado": ((q.get("distratores_explicados") or {}).get(str(r), "")
                                                if status == "erro" else "")})
    total = len(simulado["questoes"])
    try:
        seg = (datetime.fromisoformat(enviado_ts) - datetime.fromisoformat(iniciado_ts)).total_seconds()
        tempo_total = int(max(0, min(seg, simulado["duracao_seg"])))
    except (TypeError, ValueError):
        tempo_total = 0
    evolucao = list(anteriores or [])
    delta = round(nota - evolucao[-1], 2) if evolucao else None
    return {"nota": nota, "nota_max": nota_maxima(simulado, qs), "ajuste": simulado["ajuste"],
            "total": total, "acertos": acertos, "chutes": erros, "brancos": brancos,
            "por_eixo": por_eixo, "por_valor": por_valor,
            "tempo_total_seg": tempo_total,
            "tempo_medio_seg": (tempo_total // total) if total else 0,
            "evolucao": evolucao, "delta": delta, "questoes": detalhe}


# ── Nivelamento (RF-01) ───────────────────────────────────────
def sugerir_trilha(idade, acertos_por_trilha):
    """Trilha base pela idade, ajustada ±1 nível pelo desempenho do diagnóstico.
    `acertos_por_trilha`: {"P": (acertos, total), ...}."""
    idade = int(idade or 0)
    if idade and idade <= 9:
        base = "P"
    elif idade >= 12:
        base = "B"
    else:
        base = "E"          # 10–11 e idade desconhecida
    i = TRILHAS.index(base)

    def pct(t):
        a, tot = acertos_por_trilha.get(t, (0, 0))
        return (a / tot) if tot else None      # None = sem dados desse bloco
    acima = pct(TRILHAS[i + 1]) if i < len(TRILHAS) - 1 else None
    if acima is not None and acima >= 0.75:
        return TRILHAS[i + 1]
    aqui = pct(base)
    if i > 0 and aqui is not None and aqui < 0.40:
        return TRILHAS[i - 1]
    return base


def corrigir_nivelamento(respostas, questoes=None):
    """Corrige o diagnóstico completo. Retorna acertos por trilha e total."""
    qs = questoes or QUESTOES
    acertos_por_trilha = {t: [0, 0] for t in TRILHAS}
    acertos = 0
    for qid in NIVELAMENTO.get("questoes", []):
        q = qs[qid]
        acertos_por_trilha[q["trilha"]][1] += 1
        r = respostas.get(qid)
        try:
            ok = r is not None and int(r) == q["gabarito"]
        except (TypeError, ValueError):
            ok = False
        if ok:
            acertos_por_trilha[q["trilha"]][0] += 1
            acertos += 1
    return {"acertos": acertos, "total": len(NIVELAMENTO.get("questoes", [])),
            "por_trilha": {t: tuple(v) for t, v in acertos_por_trilha.items()}}


# ── Unidades da trilha (RF-02) ────────────────────────────────
def questoes_da_unidade(trilha, eixo):
    qs = [q for q in QUESTOES.values()
          if q["trilha"] == trilha and q["eixo"] == eixo and q["uso"] == "unidade"]
    return sorted(qs, key=lambda q: (q["valor_pontos"], q["id"]))


def montar_unidades(trilha, progresso_rows):
    """Resumo das 4 unidades (eixos) da trilha com progresso do aluno.
    `progresso_rows`: iterável de dicts com questao_id e acertou."""
    feitas = {r["questao_id"] for r in progresso_rows if r.get("acertou")}
    out = []
    for e in EIXOS:
        qs = questoes_da_unidade(trilha, e["id"])
        estrategias = sorted({q["estrategia_alvo"] for q in qs})
        n_feitas = sum(1 for q in qs if q["id"] in feitas)
        out.append({**e, "total": len(qs), "feitas": n_feitas,
                    "pct": int(round(100 * n_feitas / len(qs))) if qs else 0,
                    "estrategias": estrategias})
    return out
