#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — camada de dados (SQLite).
Single-aluno (id=1). Guarda XP, nível, streak, moedas, tentativas,
progresso por missão, medalhas e compras da loja.
"""
import os, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH      = Path(os.environ.get('DB_PATH', '/data/escola.db'))
ALUNO_NOME   = os.environ.get('ALUNO_NOME', 'Explorador')
XP_POR_NIVEL = int(os.environ.get('XP_POR_NIVEL', '200'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS aluno (
  id INTEGER PRIMARY KEY, nome TEXT, avatar TEXT,
  xp INTEGER DEFAULT 0, nivel INTEGER DEFAULT 1,
  moedas INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, ultimo_dia TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tentativa (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  materia TEXT, missao TEXT, acertos INTEGER, total INTEGER,
  estrelas INTEGER, xp_ganho INTEGER, segundos INTEGER, ts TEXT
);
CREATE TABLE IF NOT EXISTS progresso (
  materia TEXT, missao TEXT, melhor_estrela INTEGER DEFAULT 0,
  concluida INTEGER DEFAULT 0, leitura_ok INTEGER DEFAULT 0, ultima_ts TEXT,
  PRIMARY KEY (materia, missao)
);
CREATE TABLE IF NOT EXISTS medalha (
  codigo TEXT PRIMARY KEY, nome TEXT, emoji TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS compra (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item TEXT, nome TEXT, tipo TEXT, custo INTEGER, status TEXT, ts TEXT
);
"""

# Loja (itens de avatar + recompensas reais aprovadas pelo pai)
LOJA = [
    {"codigo": "av_capa",    "nome": "Capa de herói 🦸", "tipo": "avatar",     "custo": 30},
    {"codigo": "av_coroa",   "nome": "Coroa 👑",         "tipo": "avatar",     "custo": 60},
    {"codigo": "av_oculos",  "nome": "Óculos legais 🕶️", "tipo": "avatar",     "custo": 40},
    {"codigo": "mc_15",      "nome": "15 min de Minecraft ⛏️", "tipo": "recompensa", "custo": 50},
    {"codigo": "mc_30",      "nome": "30 min de Minecraft ⛏️", "tipo": "recompensa", "custo": 90},
]

# Medalhas: (codigo, nome, emoji, condição(stats)->bool)
MEDALHAS = [
    ("primeira",  "Primeiros passos",   "🥉", lambda s: s["missoes_concluidas"] >= 1),
    ("trio",      "Trio de missões",    "🥈", lambda s: s["missoes_concluidas"] >= 3),
    ("mestre",    "Mestre dedicado",    "🥇", lambda s: s["missoes_concluidas"] >= 10),
    ("estrelado", "Caçador de estrelas","🌟", lambda s: s["estrelas_totais"] >= 15),
    ("perfeito",  "Nota máxima",        "💯", lambda s: s["tres_estrelas"] >= 1),
    ("leitor",    "Leitor de verdade",  "📚", lambda s: s["leituras"] >= 3),
    ("fogo3",     "Sequência de 3 dias","🔥", lambda s: s["streak"] >= 3),
    ("nivel5",    "Nível 5",            "⭐", lambda s: s["nivel"] >= 5),
]


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT OR IGNORE INTO aluno(id,nome,avatar,xp,nivel,moedas,streak,ultimo_dia)"
            " VALUES(1,?,?,0,1,0,0,'')", (ALUNO_NOME, "🧑‍🚀"))
        c.commit()


def nivel_de(xp):
    return 1 + xp // XP_POR_NIVEL


def get_aluno():
    with conn() as c:
        return dict(c.execute("SELECT * FROM aluno WHERE id=1").fetchone())


def _stats(c):
    a = c.execute("SELECT * FROM aluno WHERE id=1").fetchone()
    conc = c.execute("SELECT COUNT(*) n FROM progresso WHERE concluida=1").fetchone()["n"]
    est = c.execute("SELECT COALESCE(SUM(melhor_estrela),0) s FROM progresso").fetchone()["s"]
    tres = c.execute("SELECT COUNT(*) n FROM progresso WHERE melhor_estrela>=3").fetchone()["n"]
    leit = c.execute("SELECT COUNT(*) n FROM progresso WHERE leitura_ok=1").fetchone()["n"]
    return {"missoes_concluidas": conc, "estrelas_totais": est, "tres_estrelas": tres,
            "leituras": leit, "streak": a["streak"], "nivel": a["nivel"], "xp": a["xp"]}


def verificar_medalhas():
    novas = []
    with conn() as c:
        s = _stats(c)
        ja = {r["codigo"] for r in c.execute("SELECT codigo FROM medalha").fetchall()}
        for codigo, nome, emoji, cond in MEDALHAS:
            if codigo not in ja and cond(s):
                c.execute("INSERT INTO medalha(codigo,nome,emoji,ts) VALUES(?,?,?,?)",
                          (codigo, nome, emoji, datetime.now().isoformat()))
                novas.append({"codigo": codigo, "nome": nome, "emoji": emoji})
        c.commit()
    return novas


def _bump_streak(c, hoje):
    r = c.execute("SELECT streak,ultimo_dia FROM aluno WHERE id=1").fetchone()
    streak, ult = r["streak"], r["ultimo_dia"]
    if ult == hoje:
        return streak
    ontem = str(date.fromisoformat(hoje) - timedelta(days=1))
    streak = streak + 1 if ult == ontem else 1
    c.execute("UPDATE aluno SET streak=?, ultimo_dia=? WHERE id=1", (streak, hoje))
    return streak


def registrar_tentativa(materia, missao, acertos, total, estrelas, xp_ganho, segundos):
    hoje = str(date.today())
    agora = datetime.now().isoformat()
    with conn() as c:
        c.execute("INSERT INTO tentativa(materia,missao,acertos,total,estrelas,xp_ganho,segundos,ts)"
                  " VALUES(?,?,?,?,?,?,?,?)",
                  (materia, missao, acertos, total, estrelas, xp_ganho, segundos, agora))
        c.execute("UPDATE aluno SET xp=xp+? WHERE id=1", (xp_ganho,))
        _bump_streak(c, hoje)
        row = c.execute("SELECT 1 FROM progresso WHERE materia=? AND missao=?",
                        (materia, missao)).fetchone()
        if row is None:
            c.execute("INSERT INTO progresso(materia,missao,melhor_estrela,ultima_ts)"
                      " VALUES(?,?,?,?)", (materia, missao, estrelas, agora))
        else:
            c.execute("UPDATE progresso SET melhor_estrela=MAX(melhor_estrela,?), ultima_ts=?"
                      " WHERE materia=? AND missao=?", (estrelas, agora, materia, missao))
        xp = c.execute("SELECT xp FROM aluno WHERE id=1").fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=1", (nivel_de(xp),))
        c.commit()
    return verificar_medalhas()


def concluir_leitura(materia, missao, bonus_xp=20, moedas=10):
    agora = datetime.now().isoformat()
    with conn() as c:
        row = c.execute("SELECT leitura_ok FROM progresso WHERE materia=? AND missao=?",
                        (materia, missao)).fetchone()
        if row is None:
            c.execute("INSERT INTO progresso(materia,missao,leitura_ok,concluida,ultima_ts)"
                      " VALUES(?,?,1,1,?)", (materia, missao, agora))
        elif row["leitura_ok"]:
            c.commit(); return verificar_medalhas()  # já contou
        else:
            c.execute("UPDATE progresso SET leitura_ok=1, concluida=1, ultima_ts=?"
                      " WHERE materia=? AND missao=?", (agora, materia, missao))
        c.execute("UPDATE aluno SET xp=xp+?, moedas=moedas+? WHERE id=1", (bonus_xp, moedas))
        xp = c.execute("SELECT xp FROM aluno WHERE id=1").fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=1", (nivel_de(xp),))
        c.commit()
    return verificar_medalhas()


def comprar(codigo):
    item = next((i for i in LOJA if i["codigo"] == codigo), None)
    if not item:
        return {"ok": False, "erro": "Item não existe."}
    with conn() as c:
        moedas = c.execute("SELECT moedas FROM aluno WHERE id=1").fetchone()["moedas"]
        if moedas < item["custo"]:
            return {"ok": False, "erro": "Moedas insuficientes."}
        c.execute("UPDATE aluno SET moedas=moedas-? WHERE id=1", (item["custo"],))
        status = "pendente" if item["tipo"] == "recompensa" else "ativo"
        c.execute("INSERT INTO compra(item,nome,tipo,custo,status,ts) VALUES(?,?,?,?,?,?)",
                  (item["codigo"], item["nome"], item["tipo"], item["custo"], status,
                   datetime.now().isoformat()))
        c.commit()
    return {"ok": True, "status": status}


def aprovar_compra(compra_id):
    with conn() as c:
        c.execute("UPDATE compra SET status='aprovado' WHERE id=? AND tipo='recompensa'", (compra_id,))
        c.commit()
    return {"ok": True}


def estado():
    with conn() as c:
        aluno = dict(c.execute("SELECT * FROM aluno WHERE id=1").fetchone())
        aluno["xp_prox_nivel"] = aluno["nivel"] * XP_POR_NIVEL
        prog = [dict(r) for r in c.execute("SELECT * FROM progresso").fetchall()]
        meds = [dict(r) for r in c.execute("SELECT * FROM medalha ORDER BY ts").fetchall()]
        compras = [dict(r) for r in c.execute("SELECT * FROM compra ORDER BY ts DESC LIMIT 30").fetchall()]
        ult = [dict(r) for r in c.execute("SELECT * FROM tentativa ORDER BY id DESC LIMIT 20").fetchall()]
    return {"aluno": aluno, "progresso": prog, "medalhas": meds,
            "compras": compras, "ultimas": ult, "loja": LOJA}
