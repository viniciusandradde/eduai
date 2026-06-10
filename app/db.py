#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — camada de dados (SQLite).
Single-aluno (id=1). Guarda XP, nível, streak, moedas, tentativas,
progresso por missão, medalhas e compras da loja.
"""
import os, random, sqlite3
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

# Avatar — robôs ilustrados (DiceBear "bottts", grátis, sem chave) + customização.
# base = robô (seed); acessórios mudam a COR do corpo (baseColor) ou os OLHOS (eyes).
# regra = (stat, valor, dica) desbloqueia por conquista; custo>0 compra com moedas;
# custo=0 e regra=None é grátis (já vem liberado).
DICEBEAR = "https://api.dicebear.com/9.x/bottts/svg"

AVATAR_BASES = [
    {"codigo": "base_bipe",   "nome": "Bipe",   "seed": "Bipe",    "custo": 0,  "regra": None},
    {"codigo": "base_pixel",  "nome": "Pixel",  "seed": "Pixel77", "custo": 40, "regra": None},
    {"codigo": "base_turbo",  "nome": "Turbo",  "seed": "TurboX",  "custo": 60, "regra": None},
    {"codigo": "base_nina",   "nome": "Nina",   "seed": "Nina42",  "custo": 50, "regra": None},
    {"codigo": "base_faisca", "nome": "Faísca", "seed": "Faisca",  "custo": 80, "regra": None},
    {"codigo": "base_volt",   "nome": "Volt",   "seed": "VoltZ",   "custo": 0,  "regra": ("nivel", 5, "Chegue ao Nível 5")},
    {"codigo": "base_mega",   "nome": "Mega",   "seed": "MegaBot", "custo": 0,  "regra": ("estrelas_totais", 15, "Junte 15 estrelas")},
    {"codigo": "base_rex",    "nome": "Rex",    "seed": "RexBot9", "custo": 0,  "regra": ("streak", 7, "7 dias seguidos")},
]
AVATAR_ACESSORIOS = [
    # cor do corpo (DiceBear baseColor — hex sem '#')
    {"codigo": "cor_azul",    "nome": "Azul",     "slot": "cor",   "param": "29b6f6", "custo": 0,  "regra": None},
    {"codigo": "cor_verde",   "nome": "Verde",    "slot": "cor",   "param": "66bb6a", "custo": 20, "regra": None},
    {"codigo": "cor_roxo",    "nome": "Roxo",     "slot": "cor",   "param": "ab47bc", "custo": 30, "regra": None},
    {"codigo": "cor_laranja", "nome": "Laranja",  "slot": "cor",   "param": "ffa726", "custo": 30, "regra": None},
    {"codigo": "cor_dourado", "nome": "Dourado",  "slot": "cor",   "param": "ffd54f", "custo": 0,  "regra": ("tres_estrelas", 5, "Tire 3⭐ em 5 missões")},
    # estilo dos olhos (DiceBear eyes)
    {"codigo": "olhos_happy",   "nome": "Felizes",  "slot": "olhos", "param": "happy",   "custo": 20, "regra": None},
    {"codigo": "olhos_glow",    "nome": "Brilho",   "slot": "olhos", "param": "glow",    "custo": 30, "regra": None},
    {"codigo": "olhos_hearts",  "nome": "Corações", "slot": "olhos", "param": "hearts",  "custo": 40, "regra": None},
    {"codigo": "olhos_robocop", "nome": "Robocop",  "slot": "olhos", "param": "robocop", "custo": 0,  "regra": ("missoes_concluidas", 10, "Conclua 10 missões")},
]
AVATAR_TODOS = AVATAR_BASES + AVATAR_ACESSORIOS
# qual coluna do aluno guarda cada slot de acessório
SLOT_COL = {"cor": "av_topo", "olhos": "av_rosto"}

# Missões do dia (baú): 2 fixas + 1 que gira por dia. metrica casa com _hoje_metrics.
MISSOES_FIXAS = [
    {"id": "q_responder", "texto": "Responda 2 missões", "emoji": "📝", "metrica": "tentativas", "meta": 2},
    {"id": "q_ler",       "texto": "Faça 2 leituras",    "emoji": "📖", "metrica": "leituras",   "meta": 2},
]
MISSOES_ROTATIVAS = [
    {"id": "q_acertos", "texto": "Acerte 8 questões",    "emoji": "✅", "metrica": "acertos",  "meta": 8},
    {"id": "q_xp",      "texto": "Ganhe 40 XP",          "emoji": "⭐", "metrica": "xp",       "meta": 40},
    {"id": "q_estrela", "texto": "Tire 3⭐ numa missão",  "emoji": "🌟", "metrica": "estrelas", "meta": 3},
]

# Ofensiva (streak): marcos (dias -> bônus de moedas) + Escudo da Chama.
MARCOS = [(3, 15), (7, 30), (14, 50), (30, 100)]
ESCUDO_CUSTO = 50   # moedas
ESCUDO_MAX = 2      # quantos escudos o aluno pode guardar


def _dice_url(seed, cor=None, olhos=None, size=120):
    from urllib.parse import urlencode
    q = [("seed", seed), ("size", str(size))]
    if cor:
        q.append(("baseColor", cor))
    if olhos:
        q.append(("eyes", olhos))
    return DICEBEAR + "?" + urlencode(q)


def _base_seed(codigo):
    it = next((b for b in AVATAR_BASES if b["codigo"] == codigo), AVATAR_BASES[0])
    return it["seed"]


def _acc_param(codigo):
    it = next((a for a in AVATAR_ACESSORIOS if a["codigo"] == codigo), None)
    return it["param"] if it else None

# Conquistas em níveis (Bronze → Prata → Ouro), com barra de progresso.
# metrica casa com _stats; niveis = limiares dos 3 tiers.
TIER_NOMES = ["Bronze", "Prata", "Ouro"]
TIER_EMOJI = ["🥉", "🥈", "🥇"]
CONQUISTAS = [
    {"id": "missoes",  "nome": "Missões concluídas",  "emoji": "🎯", "metrica": "missoes_concluidas", "niveis": [1, 5, 10]},
    {"id": "estrelas", "nome": "Caçador de estrelas",  "emoji": "⭐", "metrica": "estrelas_totais",    "niveis": [5, 15, 30]},
    {"id": "perfeito", "nome": "Perfeccionista",       "emoji": "💯", "metrica": "tres_estrelas",      "niveis": [1, 5, 15]},
    {"id": "leitor",   "nome": "Leitor de verdade",    "emoji": "📚", "metrica": "leituras",           "niveis": [3, 10, 25]},
    {"id": "ofensiva", "nome": "Pegando fogo",         "emoji": "🔥", "metrica": "streak",             "niveis": [3, 7, 30]},
    {"id": "nivel",    "nome": "Evoluindo",            "emoji": "🚀", "metrica": "nivel",              "niveis": [3, 5, 10]},
]


def _conquista_tier(conq, stats):
    """Quantos tiers (0..3) já foram atingidos."""
    val = stats.get(conq["metrica"], 0)
    return val, sum(1 for t in conq["niveis"] if val >= t)


def _conquista_pub(conq, stats):
    val, tier = _conquista_tier(conq, stats)
    niveis = conq["niveis"]
    maxed = tier >= len(niveis)
    meta = niveis[-1] if maxed else niveis[tier]
    progresso = meta if maxed else min(val, meta)
    return {"id": conq["id"], "nome": conq["nome"], "emoji": conq["emoji"],
            "valor": val, "tier": tier, "niveis": niveis, "maxed": maxed,
            "tier_nome": TIER_NOMES[tier - 1] if tier > 0 else "",
            "tier_emoji": TIER_EMOJI[tier - 1] if tier > 0 else "",
            "proximo_nome": "" if maxed else TIER_NOMES[tier],
            "meta": meta, "progresso": progresso}


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
        for col in ("tux_dia", "tux_inicio", "av_base", "av_topo", "av_rosto", "bau_dia"):
            try:
                c.execute(f"ALTER TABLE aluno ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        for col in ("escudos", "streak_marco"):
            try:
                c.execute(f"ALTER TABLE aluno ADD COLUMN {col} INTEGER DEFAULT 0")
            except Exception:
                pass
        c.execute(
            "INSERT OR IGNORE INTO aluno(id,nome,avatar,xp,nivel,moedas,streak,ultimo_dia,av_base)"
            " VALUES(1,?,?,0,1,0,0,'',?)", (ALUNO_NOME, "🤖", "base_bipe"))
        # normaliza equip do avatar contra o catálogo atual (limpa códigos antigos)
        valid_b = {b["codigo"] for b in AVATAR_BASES}
        valid_a = {a["codigo"] for a in AVATAR_ACESSORIOS}
        row = c.execute("SELECT av_base, av_topo, av_rosto FROM aluno WHERE id=1").fetchone()
        if row:
            if (row["av_base"] or '') not in valid_b:
                c.execute("UPDATE aluno SET av_base=? WHERE id=1", (AVATAR_BASES[0]["codigo"],))
            if (row["av_topo"] or '') not in valid_a:
                c.execute("UPDATE aluno SET av_topo='' WHERE id=1")
            if (row["av_rosto"] or '') not in valid_a:
                c.execute("UPDATE aluno SET av_rosto='' WHERE id=1")
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
    """Registra tiers recém-conquistados (code = '<id>_<tier>') e retorna os novos."""
    novas = []
    with conn() as c:
        s = _stats(c)
        ja = {r["codigo"] for r in c.execute("SELECT codigo FROM medalha").fetchall()}
        for conq in CONQUISTAS:
            _, tier = _conquista_tier(conq, s)
            for ti in range(1, tier + 1):
                code = f'{conq["id"]}_{ti}'
                if code not in ja:
                    nome = f'{conq["nome"]} {TIER_NOMES[ti - 1]}'
                    emoji = TIER_EMOJI[ti - 1]
                    c.execute("INSERT INTO medalha(codigo,nome,emoji,ts) VALUES(?,?,?,?)",
                              (code, nome, emoji, datetime.now().isoformat()))
                    novas.append({"codigo": code, "nome": nome, "emoji": emoji})
        c.commit()
    return novas


def _bump_streak(c, hoje):
    r = c.execute("SELECT streak,ultimo_dia,escudos,streak_marco FROM aluno WHERE id=1").fetchone()
    streak, ult = r["streak"], r["ultimo_dia"]
    escudos, marco = r["escudos"] or 0, r["streak_marco"] or 0
    if ult == hoje:
        return streak
    gap = (date.fromisoformat(hoje) - date.fromisoformat(ult)).days if ult else 1
    if gap == 1:
        streak = streak + 1
    else:
        faltou = gap - 1            # dias perdidos entre a última atividade e hoje
        if escudos >= faltou:       # Escudo da Chama cobre os dias perdidos
            escudos -= faltou
            streak = streak + 1
        else:                       # quebrou a ofensiva
            streak = 1
            marco = 0               # marcos podem ser reconquistados na nova ofensiva
    # marcos de ofensiva -> bônus de moedas (uma vez por marco)
    bonus = 0
    for dias, premio in MARCOS:
        if streak >= dias and marco < dias:
            bonus += premio
            marco = dias
    c.execute("UPDATE aluno SET streak=?, ultimo_dia=?, escudos=?, streak_marco=?, moedas=moedas+? WHERE id=1",
              (streak, hoje, escudos, marco, bonus))
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


def _hoje_metrics(c):
    """Métricas de HOJE para as missões do dia."""
    hoje = str(date.today())
    rows = c.execute("SELECT acertos, estrelas, xp_ganho FROM tentativa WHERE substr(ts,1,10)=?",
                     (hoje,)).fetchall()
    leituras = c.execute("SELECT COUNT(*) n FROM leitura_log WHERE dia=?", (hoje,)).fetchone()["n"]
    return {"tentativas": len(rows),
            "acertos": sum(r["acertos"] for r in rows),
            "xp": sum(r["xp_ganho"] for r in rows),
            "estrelas": max([r["estrelas"] for r in rows], default=0),
            "leituras": leituras}


def _quests_hoje(m):
    rot = MISSOES_ROTATIVAS[date.today().toordinal() % len(MISSOES_ROTATIVAS)]
    out = []
    for q in MISSOES_FIXAS + [rot]:
        prog = min(m.get(q["metrica"], 0), q["meta"])
        out.append({"id": q["id"], "texto": q["texto"], "emoji": q["emoji"],
                    "meta": q["meta"], "progresso": prog, "feito": prog >= q["meta"]})
    return out


def bau_abrir():
    """Abre o baú do dia se as 3 missões foram feitas e ainda não abriu hoje."""
    hoje = str(date.today())
    with conn() as c:
        quests = _quests_hoje(_hoje_metrics(c))
        if not all(q["feito"] for q in quests):
            return {"ok": False, "motivo": "incompleto"}
        if (c.execute("SELECT bau_dia FROM aluno WHERE id=1").fetchone()["bau_dia"] or '') == hoje:
            return {"ok": False, "motivo": "ja_aberto"}
        moedas = random.randint(10, 30)
        xp = random.choice([0, 0, 10, 20])
        c.execute("UPDATE aluno SET moedas=moedas+?, xp=xp+?, bau_dia=? WHERE id=1", (moedas, xp, hoje))
        novo_xp = c.execute("SELECT xp FROM aluno WHERE id=1").fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=1", (nivel_de(novo_xp),))
        c.commit()
    return {"ok": True, "premio": {"moedas": moedas, "xp": xp}}

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
            c.execute("UPDATE aluno SET av_base=?, avatar=? WHERE id=1", (codigo, it["seed"]))
        else:
            col = SLOT_COL[slot]
            atual = c.execute(f"SELECT {col} v FROM aluno WHERE id=1").fetchone()["v"]
            novo = "" if atual == codigo else codigo   # tocar de novo = tirar
            c.execute(f"UPDATE aluno SET {col}=? WHERE id=1", (novo,))
        c.commit()
    return {"ok": True}


def _avatar_pub(it, stats, comprados, equipado_code):
    slot = it.get("slot", "base")
    if slot == "base":
        img = _dice_url(it["seed"], size=120)
    elif slot == "cor":
        img = _dice_url("Bipe", cor=it["param"], size=120)
    else:
        img = _dice_url("Bipe", olhos=it["param"], size=120)
    return {"codigo": it["codigo"], "nome": it["nome"], "img": img,
            "slot": slot, "custo": it["custo"],
            "dica": (it["regra"][2] if it.get("regra") else ""),
            "tem": _avatar_tem(it, stats, comprados),
            "equipado": it["codigo"] == equipado_code}


def escudo_comprar():
    """Compra um Escudo da Chama (protege a ofensiva), com teto e custo fixos."""
    with conn() as c:
        r = c.execute("SELECT moedas, escudos FROM aluno WHERE id=1").fetchone()
        escudos = r["escudos"] or 0
        if escudos >= ESCUDO_MAX:
            return {"ok": False, "erro": f"Você já tem o máximo de escudos ({ESCUDO_MAX})."}
        if r["moedas"] < ESCUDO_CUSTO:
            return {"ok": False, "erro": "Moedas insuficientes."}
        c.execute("UPDATE aluno SET moedas=moedas-?, escudos=escudos+1 WHERE id=1", (ESCUDO_CUSTO,))
        c.commit()
    return {"ok": True, "escudos": escudos + 1}


def estado():
    with conn() as c:
        aluno = dict(c.execute("SELECT * FROM aluno WHERE id=1").fetchone())
        aluno["xp_prox_nivel"] = aluno["nivel"] * XP_POR_NIVEL
        prog = [dict(r) for r in c.execute("SELECT * FROM progresso").fetchall()]
        ult = [dict(r) for r in c.execute("SELECT * FROM tentativa ORDER BY id DESC LIMIT 20").fetchall()]
        s = _stats(c)
        comprados = _comprados(c)
        ativ = c.execute("SELECT COUNT(*) n FROM leitura_log WHERE dia=?",
                         (str(date.today()),)).fetchone()["n"]
        md_metrics = _hoje_metrics(c)
    conquistas = [_conquista_pub(conq, s) for conq in CONQUISTAS]
    equipado = {"base": aluno.get("av_base") or "base_bipe",
                "cor": aluno.get("av_topo") or "",
                "olhos": aluno.get("av_rosto") or ""}
    url = _dice_url(_base_seed(equipado["base"]),
                    cor=_acc_param(equipado["cor"]) if equipado["cor"] else None,
                    olhos=_acc_param(equipado["olhos"]) if equipado["olhos"] else None,
                    size=160)
    avatares = {
        "url": url,
        "bases": [_avatar_pub(it, s, comprados, equipado["base"]) for it in AVATAR_BASES],
        "acessorios": [_avatar_pub(it, s, comprados, equipado[it["slot"]]) for it in AVATAR_ACESSORIOS],
        "equipado": equipado,
    }
    quests = _quests_hoje(md_metrics)
    completo = all(q["feito"] for q in quests)
    bau = "aberto" if (aluno.get("bau_dia") or '') == str(date.today()) else ("pronto" if completo else "bloqueado")
    missoes_dia = {"quests": quests, "completo": completo, "bau": bau}
    streak = aluno["streak"]
    ofensiva = {
        "streak": streak,
        "escudos": aluno.get("escudos", 0) or 0,
        "escudo_custo": ESCUDO_CUSTO, "escudo_max": ESCUDO_MAX,
        "marcos": [{"dias": d, "bonus": b, "atingido": streak >= d} for (d, b) in MARCOS],
        "proximo": next((d for (d, b) in MARCOS if streak < d), None),
    }
    return {"aluno": aluno, "progresso": prog, "conquistas": conquistas, "ultimas": ult,
            "avatares": avatares, "missoes_dia": missoes_dia, "ofensiva": ofensiva,
            "atividades_hoje": ativ,
            "tux": {"dia": aluno.get("tux_dia", ""), "inicio": aluno.get("tux_inicio", "")}}
