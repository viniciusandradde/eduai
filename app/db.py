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
  moedas INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, ultimo_dia TEXT DEFAULT '',
  tux_dia TEXT DEFAULT '', tux_inicio TEXT DEFAULT ''
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
CREATE TABLE IF NOT EXISTS leitura_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dia TEXT, materia TEXT, missao TEXT, ts TEXT
);
"""

# Avatar — personagens-base e acessórios (estilo Duolingo).
# regra = (stat, valor, dica) desbloqueia por conquista; custo>0 compra com moedas;
# custo=0 e regra=None é grátis (já vem liberado).
AVATAR_BASES = [
    {"codigo": "base_astro",    "nome": "Astronauta", "emoji": "🧑‍🚀", "custo": 0,  "regra": None},
    {"codigo": "base_heroi",    "nome": "Herói",      "emoji": "🦸",   "custo": 40, "regra": None},
    {"codigo": "base_cientista","nome": "Cientista",  "emoji": "🧑‍🔬", "custo": 60, "regra": None},
    {"codigo": "base_raposa",   "nome": "Raposa",     "emoji": "🦊",   "custo": 50, "regra": None},
    {"codigo": "base_ninja",    "nome": "Ninja",      "emoji": "🥷",   "custo": 80, "regra": None},
    {"codigo": "base_mago",     "nome": "Mago",       "emoji": "🧙",   "custo": 0,  "regra": ("nivel", 5, "Chegue ao Nível 5")},
    {"codigo": "base_robo",     "nome": "Robô",       "emoji": "🤖",   "custo": 0,  "regra": ("estrelas_totais", 15, "Junte 15 estrelas")},
    {"codigo": "base_dragao",   "nome": "Dragão",     "emoji": "🐲",   "custo": 0,  "regra": ("streak", 7, "7 dias seguidos")},
]
AVATAR_ACESSORIOS = [
    {"codigo": "topo_bone",    "nome": "Boné",        "emoji": "🧢", "slot": "topo",  "custo": 25, "regra": None},
    {"codigo": "topo_cartola", "nome": "Cartola",     "emoji": "🎩", "slot": "topo",  "custo": 40, "regra": None},
    {"codigo": "topo_coroa",   "nome": "Coroa",       "emoji": "👑", "slot": "topo",  "custo": 0,  "regra": ("tres_estrelas", 5, "Tire 3⭐ em 5 missões")},
    {"codigo": "rosto_oculos", "nome": "Óculos",      "emoji": "🕶️", "slot": "rosto", "custo": 30, "regra": None},
    {"codigo": "rosto_nerd",   "nome": "Óculos nerd", "emoji": "🤓", "slot": "rosto", "custo": 20, "regra": None},
]
AVATAR_TODOS = AVATAR_BASES + AVATAR_ACESSORIOS

# Medalhas: (codigo, nome, emoji, dica, condição(stats)->bool)
MEDALHAS = [
    ("primeira",  "Primeiros passos",   "🥉", "Conclua 1 missão",        lambda s: s["missoes_concluidas"] >= 1),
    ("trio",      "Trio de missões",    "🥈", "Conclua 3 missões",       lambda s: s["missoes_concluidas"] >= 3),
    ("mestre",    "Mestre dedicado",    "🥇", "Conclua 10 missões",      lambda s: s["missoes_concluidas"] >= 10),
    ("estrelado", "Caçador de estrelas","🌟", "Junte 15 estrelas",       lambda s: s["estrelas_totais"] >= 15),
    ("perfeito",  "Nota máxima",        "💯", "Tire 3⭐ numa missão",     lambda s: s["tres_estrelas"] >= 1),
    ("leitor",    "Leitor de verdade",  "📚", "Faça 3 leituras",         lambda s: s["leituras"] >= 3),
    ("fogo3",     "Sequência de 3 dias","🔥", "Estude 3 dias seguidos",  lambda s: s["streak"] >= 3),
    ("nivel5",    "Nível 5",            "⭐", "Chegue ao nível 5",        lambda s: s["nivel"] >= 5),
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
        # migração: adiciona colunas novas em bancos antigos (tux + avatar)
        for col in ("tux_dia", "tux_inicio", "av_base", "av_topo", "av_rosto"):
            try:
                c.execute(f"ALTER TABLE aluno ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        c.execute(
            "INSERT OR IGNORE INTO aluno(id,nome,avatar,xp,nivel,moedas,streak,ultimo_dia,av_base)"
            " VALUES(1,?,?,0,1,0,0,'',?)", (ALUNO_NOME, "🧑‍🚀", "base_astro"))
        # base padrão para alunos já existentes
        c.execute("UPDATE aluno SET av_base='base_astro' WHERE id=1 AND (av_base IS NULL OR av_base='')")
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
        for codigo, nome, emoji, dica, cond in MEDALHAS:
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
        # registra a atividade de leitura do dia (para o cap diário)
        c.execute("INSERT INTO leitura_log(dia,materia,missao,ts) VALUES(?,?,?,?)",
                  (str(date.today()), materia, missao, agora))
        c.execute("UPDATE aluno SET xp=xp+?, moedas=moedas+? WHERE id=1", (bonus_xp, moedas))
        xp = c.execute("SELECT xp FROM aluno WHERE id=1").fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=1", (nivel_de(xp),))
        c.commit()
    return verificar_medalhas()


def atividades_hoje():
    with conn() as c:
        return c.execute("SELECT COUNT(*) n FROM leitura_log WHERE dia=?",
                         (str(date.today()),)).fetchone()["n"]

def missao_concluida(materia, missao):
    with conn() as c:
        r = c.execute("SELECT concluida FROM progresso WHERE materia=? AND missao=?",
                      (materia, missao)).fetchone()
        return bool(r and r["concluida"])

def tux_abrir(minutos):
    """Marca/lê a janela de tempo do Tux do dia. Retorna segundos restantes."""
    hoje = str(date.today()); agora = datetime.now()
    with conn() as c:
        r = c.execute("SELECT tux_dia, tux_inicio FROM aluno WHERE id=1").fetchone()
        dia, inicio = (r["tux_dia"] or ''), (r["tux_inicio"] or '')
        if dia != hoje or not inicio:
            c.execute("UPDATE aluno SET tux_dia=?, tux_inicio=? WHERE id=1",
                      (hoje, agora.isoformat()))
            c.commit()
            return minutos * 60
        try:
            decorrido = (agora - datetime.fromisoformat(inicio)).total_seconds()
        except Exception:
            decorrido = 0
        return int(max(0, minutos * 60 - decorrido))

def tux_restante(minutos):
    """Segundos restantes hoje SEM iniciar a janela (None se ainda não abriu)."""
    hoje = str(date.today())
    with conn() as c:
        r = c.execute("SELECT tux_dia, tux_inicio FROM aluno WHERE id=1").fetchone()
    if (r["tux_dia"] or '') != hoje or not (r["tux_inicio"] or ''):
        return None
    try:
        decorrido = (datetime.now() - datetime.fromisoformat(r["tux_inicio"])).total_seconds()
    except Exception:
        return minutos * 60
    return int(max(0, minutos * 60 - decorrido))


def _avatar_item(codigo):
    return next((i for i in AVATAR_TODOS if i["codigo"] == codigo), None)


def _comprados(c):
    return {r["item"] for r in c.execute(
        "SELECT DISTINCT item FROM compra WHERE status='ativo'").fetchall()}


def _avatar_tem(it, stats, comprados):
    """Item liberado? grátis, comprado ou desbloqueado por conquista."""
    regra = it.get("regra")
    if it["custo"] == 0 and regra is None:
        return True
    if it["codigo"] in comprados:
        return True
    if regra is not None and stats.get(regra[0], 0) >= regra[1]:
        return True
    return False


def avatar_comprar(codigo):
    it = _avatar_item(codigo)
    if not it:
        return {"ok": False, "erro": "Item não existe."}
    if it["custo"] <= 0 or it.get("regra"):
        return {"ok": False, "erro": "Esse item não é da loja."}
    with conn() as c:
        if codigo in _comprados(c):
            return {"ok": True, "status": "ativo"}  # já tem
        moedas = c.execute("SELECT moedas FROM aluno WHERE id=1").fetchone()["moedas"]
        if moedas < it["custo"]:
            return {"ok": False, "erro": "Moedas insuficientes."}
        c.execute("UPDATE aluno SET moedas=moedas-? WHERE id=1", (it["custo"],))
        c.execute("INSERT INTO compra(item,nome,tipo,custo,status,ts) VALUES(?,?,?,?,?,?)",
                  (codigo, it["nome"], "avatar", it["custo"], "ativo", datetime.now().isoformat()))
        c.commit()
    return {"ok": True, "status": "ativo"}


def avatar_equipar(codigo):
    it = _avatar_item(codigo)
    if not it:
        return {"ok": False, "erro": "Item não existe."}
    with conn() as c:
        if not _avatar_tem(it, _stats(c), _comprados(c)):
            return {"ok": False, "erro": "Item ainda bloqueado."}
        slot = it.get("slot", "base")
        if slot == "base":
            c.execute("UPDATE aluno SET av_base=?, avatar=? WHERE id=1", (codigo, it["emoji"]))
        else:
            col = "av_topo" if slot == "topo" else "av_rosto"
            atual = c.execute(f"SELECT {col} v FROM aluno WHERE id=1").fetchone()["v"]
            novo = "" if atual == codigo else codigo   # tocar de novo = tirar
            c.execute(f"UPDATE aluno SET {col}=? WHERE id=1", (novo,))
        c.commit()
    return {"ok": True}


def _avatar_pub(it, stats, comprados, equipado_code):
    return {"codigo": it["codigo"], "nome": it["nome"], "emoji": it["emoji"],
            "slot": it.get("slot", "base"), "custo": it["custo"],
            "dica": (it["regra"][2] if it.get("regra") else ""),
            "tem": _avatar_tem(it, stats, comprados),
            "equipado": it["codigo"] == equipado_code}


def estado():
    with conn() as c:
        aluno = dict(c.execute("SELECT * FROM aluno WHERE id=1").fetchone())
        aluno["xp_prox_nivel"] = aluno["nivel"] * XP_POR_NIVEL
        prog = [dict(r) for r in c.execute("SELECT * FROM progresso").fetchall()]
        meds = [dict(r) for r in c.execute("SELECT * FROM medalha ORDER BY ts").fetchall()]
        ult = [dict(r) for r in c.execute("SELECT * FROM tentativa ORDER BY id DESC LIMIT 20").fetchall()]
        s = _stats(c)
        comprados = _comprados(c)
        ativ = c.execute("SELECT COUNT(*) n FROM leitura_log WHERE dia=?",
                         (str(date.today()),)).fetchone()["n"]
    catalogo = [{"codigo": cod, "nome": nm, "emoji": em, "dica": dc, "tem": bool(cond(s))}
                for (cod, nm, em, dc, cond) in MEDALHAS]
    equipado = {"base": aluno.get("av_base") or "base_astro",
                "topo": aluno.get("av_topo") or "",
                "rosto": aluno.get("av_rosto") or ""}
    avatares = {
        "bases": [_avatar_pub(it, s, comprados, equipado["base"]) for it in AVATAR_BASES],
        "acessorios": [_avatar_pub(it, s, comprados, equipado[it["slot"]]) for it in AVATAR_ACESSORIOS],
        "equipado": equipado,
    }
    return {"aluno": aluno, "progresso": prog, "medalhas": meds,
            "medalhas_catalogo": catalogo, "ultimas": ult,
            "avatares": avatares, "atividades_hoje": ativ,
            "tux": {"dia": aluno.get("tux_dia", ""), "inicio": aluno.get("tux_inicio", "")}}
