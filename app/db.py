#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — camada de dados (SQLite), MULTIUSUÁRIO.
admin → pais → filhos (alunos). Cada aluno tem seu próprio progresso, avatar,
leituras, etc. Auth por senha com hash (PBKDF2) + sessão por token.
"""
import os, json, random, secrets, hashlib, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH      = Path(os.environ.get('DB_PATH', '/data/escola.db'))
ALUNO_NOME   = os.environ.get('ALUNO_NOME', 'Explorador')
XP_POR_NIVEL = int(os.environ.get('XP_POR_NIVEL', '200'))
# Seeds iniciais (idempotentes) — credenciais da 1ª carga
ADMIN_LOGIN  = os.environ.get('ADMIN_LOGIN', 'vinny')
ADMIN_SENHA  = os.environ.get('ADMIN_SENHA', os.environ.get('PAI_SENHA', 'pai'))
ANDREIA_SENHA = os.environ.get('ANDREIA_SENHA', 'andreia2026')
VITTOR_SENHA = os.environ.get('ALUNO_SENHA', 'aluno')

SCHEMA = """
CREATE TABLE IF NOT EXISTS pai (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, login TEXT UNIQUE,
  senha_hash TEXT, is_admin INTEGER DEFAULT 0, bem_vindo INTEGER DEFAULT 0, ts TEXT
);
CREATE TABLE IF NOT EXISTS sessao (
  token TEXT PRIMARY KEY, tipo TEXT, ref_id INTEGER, criado TEXT
);
CREATE TABLE IF NOT EXISTS aluno (
  id INTEGER PRIMARY KEY AUTOINCREMENT, pai_id INTEGER, nome TEXT, idade INTEGER DEFAULT 0,
  login TEXT UNIQUE, senha_hash TEXT, avatar TEXT,
  xp INTEGER DEFAULT 0, nivel INTEGER DEFAULT 1,
  moedas INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, ultimo_dia TEXT DEFAULT '',
  tux_dia TEXT DEFAULT '', tux_inicio TEXT DEFAULT '',
  av_base TEXT DEFAULT '', av_topo TEXT DEFAULT '', av_rosto TEXT DEFAULT '',
  bau_dia TEXT DEFAULT '', escudos INTEGER DEFAULT 0, streak_marco INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tentativa (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER,
  materia TEXT, missao TEXT, acertos INTEGER, total INTEGER,
  estrelas INTEGER, xp_ganho INTEGER, segundos INTEGER, ts TEXT
);
CREATE TABLE IF NOT EXISTS progresso (
  aluno_id INTEGER, materia TEXT, missao TEXT, melhor_estrela INTEGER DEFAULT 0,
  concluida INTEGER DEFAULT 0, leitura_ok INTEGER DEFAULT 0, ultima_ts TEXT,
  PRIMARY KEY (aluno_id, materia, missao)
);
CREATE TABLE IF NOT EXISTS medalha (
  aluno_id INTEGER, codigo TEXT, nome TEXT, emoji TEXT, ts TEXT,
  PRIMARY KEY (aluno_id, codigo)
);
CREATE TABLE IF NOT EXISTS compra (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER,
  item TEXT, nome TEXT, tipo TEXT, custo INTEGER, status TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS leitura_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER,
  dia TEXT, materia TEXT, missao TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER, texto TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS leitura (
  aluno_id INTEGER, materia TEXT, missao TEXT, titulo TEXT, resumo TEXT, foto TEXT, ts TEXT,
  nota INTEGER DEFAULT 0, comentario TEXT DEFAULT '', nota_ts TEXT,
  PRIMARY KEY (aluno_id, materia, missao)
);
CREATE TABLE IF NOT EXISTS mensagem (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER, texto TEXT, ts TEXT, vista INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oli_perfil (
  aluno_id INTEGER PRIMARY KEY, trilha TEXT DEFAULT '', origem TEXT DEFAULT '',
  nivelamento_json TEXT DEFAULT '', saltos INTEGER DEFAULT 0, ts TEXT
);
CREATE TABLE IF NOT EXISTS oli_progresso (
  aluno_id INTEGER, questao_id TEXT, trilha TEXT, eixo TEXT,
  acertou INTEGER DEFAULT 0, tentativas INTEGER DEFAULT 0, ultima_ts TEXT,
  PRIMARY KEY (aluno_id, questao_id)
);
CREATE TABLE IF NOT EXISTS oli_simulado (
  id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER, simulado_id TEXT, trilha TEXT,
  iniciado_ts TEXT, duracao_seg INTEGER, respostas_json TEXT DEFAULT '{}',
  marcadas_json TEXT DEFAULT '[]', enviado INTEGER DEFAULT 0, enviado_ts TEXT,
  auto INTEGER DEFAULT 0, nota REAL, detalhe_json TEXT DEFAULT ''
);
"""

# Avatar — robôs ilustrados (DiceBear "bottts", grátis, sem chave) + customização.
DICEBEAR = "https://api.dicebear.com/9.x/bottts/svg"

AVATAR_BASES = [
    {"codigo": "base_bipe",   "nome": "Bipe",   "seed": "Bipe",    "custo": 0,  "regra": None, "categoria": "Robôs"},
    {"codigo": "base_pixel",  "nome": "Pixel",  "seed": "Pixel77", "custo": 40, "regra": None, "categoria": "Robôs"},
    {"codigo": "base_turbo",  "nome": "Turbo",  "seed": "TurboX",  "custo": 60, "regra": None, "categoria": "Robôs"},
    {"codigo": "base_nina",   "nome": "Nina",   "seed": "Nina42",  "custo": 50, "regra": None, "categoria": "Robôs"},
    {"codigo": "base_faisca", "nome": "Faísca", "seed": "Faisca",  "custo": 80, "regra": None, "categoria": "Robôs"},
    {"codigo": "base_volt",   "nome": "Volt",   "seed": "VoltZ",   "custo": 0,  "regra": ("nivel", 5, "Chegue ao Nível 5"), "categoria": "Robôs"},
    {"codigo": "base_mega",   "nome": "Mega",   "seed": "MegaBot", "custo": 0,  "regra": ("estrelas_totais", 15, "Junte 15 estrelas"), "categoria": "Robôs"},
    {"codigo": "base_rex",    "nome": "Rex",    "seed": "RexBot9", "custo": 0,  "regra": ("streak", 7, "7 dias seguidos"), "categoria": "Robôs"},
    # ── Supremos (ocultos): liberam ao passar de 50% das missões. Imagem em alta. ──
    {"codigo": "sup_pikachu",  "nome": "Pikachu",   "img": "/avatars/poke_pikachu.png",  "custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_charizard","nome": "Charizard", "img": "/avatars/poke_charizard.png","custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_mewtwo",   "nome": "Mewtwo",    "img": "/avatars/poke_mewtwo.png",   "custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_gengar",   "nome": "Gengar",    "img": "/avatars/poke_gengar.png",   "custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_lucario",  "nome": "Lucario",   "img": "/avatars/poke_lucario.png",  "custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_greninja", "nome": "Greninja",  "img": "/avatars/poke_greninja.png", "custo": 0, "regra": None, "categoria": "Pokémon",        "supremo": True},
    {"codigo": "sup_sonic",     "nome": "Sonic",       "img": "/avatars/sonic.png",          "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_sonic_super","nome": "Super Sonic","img": "/avatars/sonic_super.png",    "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_shadow",    "nome": "Shadow",      "img": "/avatars/sonic_shadow.png",   "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_silver",    "nome": "Silver",      "img": "/avatars/sonic_silver.png",   "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_blaze",     "nome": "Blaze",       "img": "/avatars/sonic_blaze.png",    "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_tails",     "nome": "Tails",       "img": "/avatars/sonic_tails.png",    "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_knuckles",  "nome": "Knuckles",    "img": "/avatars/sonic_knuckles.png", "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_amy",       "nome": "Amy",         "img": "/avatars/sonic_amy.png",      "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_boom",      "nome": "Sonic Boom",  "img": "/avatars/sonic_boom.png",     "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_werehog",   "nome": "Werehog",     "img": "/avatars/sonic_werehog.png",  "custo": 0, "regra": None, "categoria": "Sonic", "supremo": True},
    {"codigo": "sup_samus",     "nome": "Varia Suit", "img": "/avatars/metroid_samus.png",     "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
    {"codigo": "sup_gravity",   "nome": "Gravity Suit","img": "/avatars/metroid_gravity.png",   "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
    {"codigo": "sup_darksuit",  "nome": "Dark Suit",  "img": "/avatars/metroid_dark.png",       "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
    {"codigo": "sup_darksamus", "nome": "Dark Samus", "img": "/avatars/metroid_darksamus.png",  "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
    {"codigo": "sup_dread",     "nome": "Samus Dread","img": "/avatars/metroid_dread.png",      "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
    {"codigo": "sup_ridley",    "nome": "Ridley",     "img": "/avatars/metroid_ridley.png",     "custo": 0, "regra": None, "categoria": "Super Metroid", "supremo": True},
]
SUPREMO_PCT = 0.5
AVATAR_ACESSORIOS = [
    {"codigo": "cor_azul",    "nome": "Azul",     "slot": "cor",   "param": "29b6f6", "custo": 0,  "regra": None},
    {"codigo": "cor_verde",   "nome": "Verde",    "slot": "cor",   "param": "66bb6a", "custo": 20, "regra": None},
    {"codigo": "cor_roxo",    "nome": "Roxo",     "slot": "cor",   "param": "ab47bc", "custo": 30, "regra": None},
    {"codigo": "cor_laranja", "nome": "Laranja",  "slot": "cor",   "param": "ffa726", "custo": 30, "regra": None},
    {"codigo": "cor_dourado", "nome": "Dourado",  "slot": "cor",   "param": "ffd54f", "custo": 0,  "regra": ("tres_estrelas", 5, "Tire 3⭐ em 5 missões")},
    {"codigo": "olhos_happy",   "nome": "Felizes",  "slot": "olhos", "param": "happy",   "custo": 20, "regra": None},
    {"codigo": "olhos_glow",    "nome": "Brilho",   "slot": "olhos", "param": "glow",    "custo": 30, "regra": None},
    {"codigo": "olhos_hearts",  "nome": "Corações", "slot": "olhos", "param": "hearts",  "custo": 40, "regra": None},
    {"codigo": "olhos_robocop", "nome": "Robocop",  "slot": "olhos", "param": "robocop", "custo": 0,  "regra": ("missoes_concluidas", 10, "Conclua 10 missões")},
]
AVATAR_TODOS = AVATAR_BASES + AVATAR_ACESSORIOS
SLOT_COL = {"cor": "av_topo", "olhos": "av_rosto"}

MISSOES_FIXAS = [
    {"id": "q_responder", "texto": "Responda 2 missões", "emoji": "📝", "metrica": "tentativas", "meta": 2},
    {"id": "q_ler",       "texto": "Faça 2 resumos",     "emoji": "📖", "metrica": "leituras",   "meta": 2},
]
MISSOES_ROTATIVAS = [
    {"id": "q_acertos", "texto": "Acerte 8 questões",    "emoji": "✅", "metrica": "acertos",  "meta": 8},
    {"id": "q_xp",      "texto": "Ganhe 40 XP",          "emoji": "⭐", "metrica": "xp",       "meta": 40},
    {"id": "q_estrela", "texto": "Tire 3⭐ numa missão",  "emoji": "🌟", "metrica": "estrelas", "meta": 3},
]

MARCOS = [(3, 15), (7, 30), (14, 50), (30, 100)]
ESCUDO_CUSTO = 50
ESCUDO_MAX = 2

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


# ── Avatar helpers (stateless) ────────────────────────────────
def _dice_url(seed, cor=None, olhos=None, size=120):
    from urllib.parse import urlencode
    q = [("seed", seed), ("size", str(size))]
    if cor:
        q.append(("baseColor", cor))
    if olhos:
        q.append(("eyes", olhos))
    return DICEBEAR + "?" + urlencode(q)


def _base_item(codigo):
    return next((b for b in AVATAR_BASES if b["codigo"] == codigo), AVATAR_BASES[0])

def _base_seed(codigo):
    return _base_item(codigo).get("seed", "Bipe")

def _acc_param(codigo):
    it = next((a for a in AVATAR_ACESSORIOS if a["codigo"] == codigo), None)
    return it["param"] if it else None

def _supremo_ok(stats, total_missoes):
    if not total_missoes:
        return False
    return stats.get("missoes_concluidas", 0) / total_missoes >= SUPREMO_PCT

def _conquista_tier(conq, stats):
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


# ── Conexão / migração ────────────────────────────────────────
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _cols(c, table):
    return {d[1] for d in c.execute(f"PRAGMA table_info({table})")}


def _migra_pk(c, tabela, ddl_novo, colunas):
    """Recria uma tabela de PK composta adicionando aluno_id=1 aos dados antigos."""
    if "aluno_id" in _cols(c, tabela):
        return
    cols_existentes = _cols(c, tabela)
    sel = ", ".join(col if col in cols_existentes else f"'' AS {col}" for col in colunas)
    c.execute(ddl_novo.replace(tabela, tabela + "_new", 1))
    c.execute(f"INSERT INTO {tabela}_new(aluno_id,{','.join(colunas)}) SELECT 1,{sel} FROM {tabela}")
    c.execute(f"DROP TABLE {tabela}")
    c.execute(f"ALTER TABLE {tabela}_new RENAME TO {tabela}")


def _hash(senha):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', (senha or '').encode(), salt.encode(), 100_000)
    return salt + "$" + dk.hex()

def _verify(senha, stored):
    if not stored or "$" not in stored:
        return False
    salt, h = stored.split("$", 1)
    dk = hashlib.pbkdf2_hmac('sha256', (senha or '').encode(), salt.encode(), 100_000)
    return secrets.compare_digest(dk.hex(), h)


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        # aluno: colunas novas (idempotente)
        aluno_cols = {
            "pai_id": "INTEGER", "idade": "INTEGER DEFAULT 0", "login": "TEXT", "senha_hash": "TEXT",
            "avatar": "TEXT", "tux_dia": "TEXT DEFAULT ''", "tux_inicio": "TEXT DEFAULT ''",
            "av_base": "TEXT DEFAULT ''", "av_topo": "TEXT DEFAULT ''", "av_rosto": "TEXT DEFAULT ''",
            "bau_dia": "TEXT DEFAULT ''", "escudos": "INTEGER DEFAULT 0", "streak_marco": "INTEGER DEFAULT 0",
        }
        have = _cols(c, "aluno")
        for col, ddl in aluno_cols.items():
            if col not in have:
                try: c.execute(f"ALTER TABLE aluno ADD COLUMN {col} {ddl}")
                except Exception: pass
        # leitura antiga (v17) pode não ter 'resumo' — garante antes de recriar
        if "leitura" in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            if "resumo" not in _cols(c, "leitura") and "aluno_id" not in _cols(c, "leitura"):
                try: c.execute("ALTER TABLE leitura ADD COLUMN resumo TEXT DEFAULT ''")
                except Exception: pass
        # tabelas simples: adiciona aluno_id + backfill=1
        for t in ("tentativa", "compra", "leitura_log", "feedback", "mensagem"):
            if "aluno_id" not in _cols(c, t):
                try: c.execute(f"ALTER TABLE {t} ADD COLUMN aluno_id INTEGER")
                except Exception: pass
            c.execute(f"UPDATE {t} SET aluno_id=1 WHERE aluno_id IS NULL")
        # tabelas de PK composta: recria preservando dados (aluno_id=1)
        _migra_pk(c, "progresso",
                  """CREATE TABLE progresso (aluno_id INTEGER, materia TEXT, missao TEXT,
                     melhor_estrela INTEGER DEFAULT 0, concluida INTEGER DEFAULT 0,
                     leitura_ok INTEGER DEFAULT 0, ultima_ts TEXT,
                     PRIMARY KEY (aluno_id, materia, missao))""",
                  ["materia", "missao", "melhor_estrela", "concluida", "leitura_ok", "ultima_ts"])
        _migra_pk(c, "medalha",
                  """CREATE TABLE medalha (aluno_id INTEGER, codigo TEXT, nome TEXT, emoji TEXT, ts TEXT,
                     PRIMARY KEY (aluno_id, codigo))""",
                  ["codigo", "nome", "emoji", "ts"])
        _migra_pk(c, "leitura",
                  """CREATE TABLE leitura (aluno_id INTEGER, materia TEXT, missao TEXT, titulo TEXT,
                     resumo TEXT, foto TEXT, ts TEXT, nota INTEGER DEFAULT 0,
                     comentario TEXT DEFAULT '', nota_ts TEXT,
                     PRIMARY KEY (aluno_id, materia, missao))""",
                  ["materia", "missao", "titulo", "resumo", "foto", "ts", "nota", "comentario", "nota_ts"])

        # ── Seeds (idempotentes) ──────────────────────────────
        def _pai_id(login):
            r = c.execute("SELECT id FROM pai WHERE login=?", (login,)).fetchone()
            return r["id"] if r else None
        if not _pai_id(ADMIN_LOGIN):
            c.execute("INSERT INTO pai(nome,login,senha_hash,is_admin,ts) VALUES(?,?,?,1,?)",
                      ("Vinny", ADMIN_LOGIN, _hash(ADMIN_SENHA), datetime.now().isoformat()))
        if not _pai_id("andreia"):
            c.execute("INSERT INTO pai(nome,login,senha_hash,is_admin,ts) VALUES(?,?,?,0,?)",
                      ("Andreia", "andreia", _hash(ANDREIA_SENHA), datetime.now().isoformat()))
        andreia_id = _pai_id("andreia")
        # aluno existente (Vittor, id=1) — vincula à Andreia e dá login/senha se faltar
        v = c.execute("SELECT id, login, senha_hash, idade, pai_id FROM aluno WHERE id=1").fetchone()
        if v:
            if not (v["login"]):
                c.execute("UPDATE aluno SET login='vittor' WHERE id=1")
            if not (v["senha_hash"]):
                c.execute("UPDATE aluno SET senha_hash=? WHERE id=1", (_hash(VITTOR_SENHA),))
            if not v["pai_id"]:
                c.execute("UPDATE aluno SET pai_id=? WHERE id=1", (andreia_id,))
            if not v["idade"]:
                c.execute("UPDATE aluno SET idade=10 WHERE id=1")
        c.commit()
        # normaliza equip do avatar de cada aluno contra o catálogo
        valid_b = {b["codigo"] for b in AVATAR_BASES}
        valid_a = {a["codigo"] for a in AVATAR_ACESSORIOS}
        for r in c.execute("SELECT id, av_base, av_topo, av_rosto FROM aluno").fetchall():
            if (r["av_base"] or '') not in valid_b:
                c.execute("UPDATE aluno SET av_base=? WHERE id=?", (AVATAR_BASES[0]["codigo"], r["id"]))
            if (r["av_topo"] or '') not in valid_a:
                c.execute("UPDATE aluno SET av_topo='' WHERE id=?", (r["id"],))
            if (r["av_rosto"] or '') not in valid_a:
                c.execute("UPDATE aluno SET av_rosto='' WHERE id=?", (r["id"],))
        c.commit()


# ── Auth: pais, alunos, sessões ───────────────────────────────
def _pub_pai(r):
    return {"id": r["id"], "nome": r["nome"], "login": r["login"], "is_admin": bool(r["is_admin"]),
            "bem_vindo": bool(r["bem_vindo"])}

def criar_pai(nome, login, senha, is_admin=0):
    login = (login or '').strip().lower()
    if not nome.strip() or not login or len(senha or '') < 4:
        return {"ok": False, "erro": "Nome, login e senha (mín. 4) são obrigatórios."}
    with conn() as c:
        if c.execute("SELECT 1 FROM pai WHERE login=?", (login,)).fetchone():
            return {"ok": False, "erro": "Esse login de pai já existe."}
        c.execute("INSERT INTO pai(nome,login,senha_hash,is_admin,ts) VALUES(?,?,?,?,?)",
                  (nome.strip(), login, _hash(senha), 1 if is_admin else 0, datetime.now().isoformat()))
        c.commit()
    return {"ok": True}

def pai_login(login, senha):
    with conn() as c:
        r = c.execute("SELECT * FROM pai WHERE login=?", ((login or '').strip().lower(),)).fetchone()
    if r and _verify(senha, r["senha_hash"]):
        return _pub_pai(r)
    return None

def pai_get(pai_id):
    with conn() as c:
        r = c.execute("SELECT * FROM pai WHERE id=?", (pai_id,)).fetchone()
    return _pub_pai(r) if r else None

def listar_pais():
    with conn() as c:
        pais = [_pub_pai(r) for r in c.execute("SELECT * FROM pai ORDER BY id").fetchall()]
        for p in pais:
            p["filhos"] = [dict(r) for r in c.execute(
                "SELECT id, nome, login, idade FROM aluno WHERE pai_id=? ORDER BY id", (p["id"],)).fetchall()]
    return pais

def bem_vindo_ok(pai_id):
    with conn() as c:
        c.execute("UPDATE pai SET bem_vindo=1 WHERE id=?", (pai_id,))
        c.commit()
    return {"ok": True}

def criar_aluno(pai_id, nome, idade, login, senha):
    login = (login or '').strip().lower()
    if not (nome or '').strip() or not login or len(senha or '') < 4:
        return {"ok": False, "erro": "Nome, usuário e senha (mín. 4) são obrigatórios."}
    with conn() as c:
        if c.execute("SELECT 1 FROM aluno WHERE login=?", (login,)).fetchone():
            return {"ok": False, "erro": "Esse usuário de filho já existe."}
        c.execute("INSERT INTO aluno(pai_id,nome,idade,login,senha_hash,avatar,nivel,av_base)"
                  " VALUES(?,?,?,?,?,?,1,'base_bipe')",
                  (pai_id, nome.strip(), int(idade or 0), login, _hash(senha), "🤖"))
        c.commit()
    return {"ok": True}

def aluno_login(login, senha):
    with conn() as c:
        r = c.execute("SELECT * FROM aluno WHERE login=?", ((login or '').strip().lower(),)).fetchone()
    if r and _verify(senha, r["senha_hash"]):
        return {"id": r["id"], "nome": r["nome"], "pai_id": r["pai_id"]}
    return None

def aluno_get(aid):
    with conn() as c:
        r = c.execute("SELECT id, nome, pai_id, idade, login FROM aluno WHERE id=?", (aid,)).fetchone()
    return dict(r) if r else None

def aluno_pertence(aid, pai_id):
    with conn() as c:
        r = c.execute("SELECT 1 FROM aluno WHERE id=? AND pai_id=?", (aid, pai_id)).fetchone()
    return bool(r)

def listar_alunos(pai_id):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, nome, login, idade FROM aluno WHERE pai_id=? ORDER BY id", (pai_id,)).fetchall()]

def sessao_nova(tipo, ref_id):
    tok = secrets.token_urlsafe(24)
    with conn() as c:
        c.execute("INSERT INTO sessao(token,tipo,ref_id,criado) VALUES(?,?,?,?)",
                  (tok, tipo, ref_id, datetime.now().isoformat()))
        c.commit()
    return tok

def sessao_resolve(token):
    if not token:
        return None
    with conn() as c:
        r = c.execute("SELECT tipo, ref_id FROM sessao WHERE token=?", (token,)).fetchone()
    return (r["tipo"], r["ref_id"]) if r else None

def sessao_encerra(token):
    with conn() as c:
        c.execute("DELETE FROM sessao WHERE token=?", (token,))
        c.commit()
    return {"ok": True}


# ── Dados por aluno (tudo recebe aluno_id) ────────────────────
def nivel_de(xp):
    return 1 + xp // XP_POR_NIVEL


def get_aluno(aid):
    with conn() as c:
        r = c.execute("SELECT * FROM aluno WHERE id=?", (aid,)).fetchone()
    return dict(r) if r else None


def _stats(c, aid):
    a = c.execute("SELECT * FROM aluno WHERE id=?", (aid,)).fetchone()
    conc = c.execute("SELECT COUNT(*) n FROM progresso WHERE aluno_id=? AND concluida=1", (aid,)).fetchone()["n"]
    est = c.execute("SELECT COALESCE(SUM(melhor_estrela),0) s FROM progresso WHERE aluno_id=?", (aid,)).fetchone()["s"]
    tres = c.execute("SELECT COUNT(*) n FROM progresso WHERE aluno_id=? AND melhor_estrela>=3", (aid,)).fetchone()["n"]
    leit = c.execute("SELECT COUNT(*) n FROM progresso WHERE aluno_id=? AND leitura_ok=1", (aid,)).fetchone()["n"]
    return {"missoes_concluidas": conc, "estrelas_totais": est, "tres_estrelas": tres,
            "leituras": leit, "streak": a["streak"], "nivel": a["nivel"], "xp": a["xp"]}


def verificar_medalhas(aid):
    novas = []
    with conn() as c:
        s = _stats(c, aid)
        ja = {r["codigo"] for r in c.execute("SELECT codigo FROM medalha WHERE aluno_id=?", (aid,)).fetchall()}
        for conq in CONQUISTAS:
            _, tier = _conquista_tier(conq, s)
            for ti in range(1, tier + 1):
                code = f'{conq["id"]}_{ti}'
                if code not in ja:
                    nome = f'{conq["nome"]} {TIER_NOMES[ti - 1]}'
                    emoji = TIER_EMOJI[ti - 1]
                    c.execute("INSERT INTO medalha(aluno_id,codigo,nome,emoji,ts) VALUES(?,?,?,?,?)",
                              (aid, code, nome, emoji, datetime.now().isoformat()))
                    novas.append({"codigo": code, "nome": nome, "emoji": emoji})
        c.commit()
    return novas


def _bump_streak(c, aid, hoje):
    r = c.execute("SELECT streak,ultimo_dia,escudos,streak_marco FROM aluno WHERE id=?", (aid,)).fetchone()
    streak, ult = r["streak"], r["ultimo_dia"]
    escudos, marco = r["escudos"] or 0, r["streak_marco"] or 0
    if ult == hoje:
        return streak
    gap = (date.fromisoformat(hoje) - date.fromisoformat(ult)).days if ult else 1
    if gap == 1:
        streak = streak + 1
    else:
        faltou = gap - 1
        if escudos >= faltou:
            escudos -= faltou
            streak = streak + 1
        else:
            streak = 1
            marco = 0
    bonus = 0
    for dias, premio in MARCOS:
        if streak >= dias and marco < dias:
            bonus += premio
            marco = dias
    c.execute("UPDATE aluno SET streak=?, ultimo_dia=?, escudos=?, streak_marco=?, moedas=moedas+? WHERE id=?",
              (streak, hoje, escudos, marco, bonus, aid))
    return streak


def registrar_tentativa(aid, materia, missao, acertos, total, estrelas, xp_ganho, segundos):
    hoje = str(date.today())
    agora = datetime.now().isoformat()
    with conn() as c:
        c.execute("INSERT INTO tentativa(aluno_id,materia,missao,acertos,total,estrelas,xp_ganho,segundos,ts)"
                  " VALUES(?,?,?,?,?,?,?,?,?)",
                  (aid, materia, missao, acertos, total, estrelas, xp_ganho, segundos, agora))
        c.execute("UPDATE aluno SET xp=xp+? WHERE id=?", (xp_ganho, aid))
        _bump_streak(c, aid, hoje)
        row = c.execute("SELECT 1 FROM progresso WHERE aluno_id=? AND materia=? AND missao=?",
                        (aid, materia, missao)).fetchone()
        if row is None:
            c.execute("INSERT INTO progresso(aluno_id,materia,missao,melhor_estrela,ultima_ts)"
                      " VALUES(?,?,?,?,?)", (aid, materia, missao, estrelas, agora))
        else:
            c.execute("UPDATE progresso SET melhor_estrela=MAX(melhor_estrela,?), ultima_ts=?"
                      " WHERE aluno_id=? AND materia=? AND missao=?", (estrelas, agora, aid, materia, missao))
        xp = c.execute("SELECT xp FROM aluno WHERE id=?", (aid,)).fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=?", (nivel_de(xp), aid))
        c.commit()
    return verificar_medalhas(aid)


def concluir_leitura(aid, materia, missao, titulo='', foto='', resumo='', bonus_xp=20, moedas=10):
    agora = datetime.now().isoformat()
    with conn() as c:
        row = c.execute("SELECT leitura_ok FROM progresso WHERE aluno_id=? AND materia=? AND missao=?",
                        (aid, materia, missao)).fetchone()
        if row is None:
            c.execute("INSERT INTO progresso(aluno_id,materia,missao,leitura_ok,concluida,ultima_ts)"
                      " VALUES(?,?,?,1,1,?)", (aid, materia, missao, agora))
        elif row["leitura_ok"]:
            c.commit(); return verificar_medalhas(aid)  # imutável
        else:
            c.execute("UPDATE progresso SET leitura_ok=1, concluida=1, ultima_ts=?"
                      " WHERE aluno_id=? AND materia=? AND missao=?", (agora, aid, materia, missao))
        c.execute("INSERT INTO leitura(aluno_id,materia,missao,titulo,resumo,foto,ts) VALUES(?,?,?,?,?,?,?)"
                  " ON CONFLICT(aluno_id,materia,missao) DO UPDATE SET titulo=excluded.titulo,"
                  " resumo=excluded.resumo, foto=excluded.foto, ts=excluded.ts",
                  (aid, materia, missao, titulo, resumo, foto, agora))
        c.execute("INSERT INTO leitura_log(aluno_id,dia,materia,missao,ts) VALUES(?,?,?,?,?)",
                  (aid, str(date.today()), materia, missao, agora))
        c.execute("UPDATE aluno SET xp=xp+?, moedas=moedas+? WHERE id=?", (bonus_xp, moedas, aid))
        xp = c.execute("SELECT xp FROM aluno WHERE id=?", (aid,)).fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=?", (nivel_de(xp), aid))
        c.commit()
    return verificar_medalhas(aid)


def atividades_hoje(aid):
    with conn() as c:
        return c.execute("SELECT COUNT(*) n FROM leitura_log WHERE aluno_id=? AND dia=?",
                         (aid, str(date.today()))).fetchone()["n"]

def total_concluidas(aid):
    with conn() as c:
        return c.execute("SELECT COUNT(*) n FROM progresso WHERE aluno_id=? AND concluida=1", (aid,)).fetchone()["n"]


def _hoje_metrics(c, aid):
    hoje = str(date.today())
    rows = c.execute("SELECT acertos, estrelas, xp_ganho FROM tentativa WHERE aluno_id=? AND substr(ts,1,10)=?",
                     (aid, hoje)).fetchall()
    leituras = c.execute("SELECT COUNT(*) n FROM leitura_log WHERE aluno_id=? AND dia=?", (aid, hoje)).fetchone()["n"]
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


def bau_abrir(aid):
    hoje = str(date.today())
    with conn() as c:
        quests = _quests_hoje(_hoje_metrics(c, aid))
        if not all(q["feito"] for q in quests):
            return {"ok": False, "motivo": "incompleto"}
        if (c.execute("SELECT bau_dia FROM aluno WHERE id=?", (aid,)).fetchone()["bau_dia"] or '') == hoje:
            return {"ok": False, "motivo": "ja_aberto"}
        moedas = random.randint(10, 30)
        xp = random.choice([0, 0, 10, 20])
        c.execute("UPDATE aluno SET moedas=moedas+?, xp=xp+?, bau_dia=? WHERE id=?", (moedas, xp, hoje, aid))
        novo_xp = c.execute("SELECT xp FROM aluno WHERE id=?", (aid,)).fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=?", (nivel_de(novo_xp), aid))
        c.commit()
    return {"ok": True, "premio": {"moedas": moedas, "xp": xp}}


def missao_concluida(aid, materia, missao):
    with conn() as c:
        r = c.execute("SELECT concluida FROM progresso WHERE aluno_id=? AND materia=? AND missao=?",
                      (aid, materia, missao)).fetchone()
        return bool(r and r["concluida"])


def tux_abrir(aid, minutos):
    hoje = str(date.today()); agora = datetime.now()
    with conn() as c:
        r = c.execute("SELECT tux_dia, tux_inicio FROM aluno WHERE id=?", (aid,)).fetchone()
        dia, inicio = (r["tux_dia"] or ''), (r["tux_inicio"] or '')
        if dia != hoje or not inicio:
            c.execute("UPDATE aluno SET tux_dia=?, tux_inicio=? WHERE id=?", (hoje, agora.isoformat(), aid))
            c.commit()
            return minutos * 60
        try:
            decorrido = (agora - datetime.fromisoformat(inicio)).total_seconds()
        except Exception:
            decorrido = 0
        return int(max(0, minutos * 60 - decorrido))


def tux_restante(aid, minutos):
    hoje = str(date.today())
    with conn() as c:
        r = c.execute("SELECT tux_dia, tux_inicio FROM aluno WHERE id=?", (aid,)).fetchone()
    if (r["tux_dia"] or '') != hoje or not (r["tux_inicio"] or ''):
        return None
    try:
        decorrido = (datetime.now() - datetime.fromisoformat(r["tux_inicio"])).total_seconds()
    except Exception:
        return minutos * 60
    return int(max(0, minutos * 60 - decorrido))


def _avatar_item(codigo):
    return next((i for i in AVATAR_TODOS if i["codigo"] == codigo), None)

def _comprados(c, aid):
    return {r["item"] for r in c.execute(
        "SELECT DISTINCT item FROM compra WHERE aluno_id=? AND status='ativo'", (aid,)).fetchall()}

def _avatar_tem(it, stats, comprados, supremo_ok=False):
    if it.get("supremo"):
        return supremo_ok
    regra = it.get("regra")
    if it["custo"] == 0 and regra is None:
        return True
    if it["codigo"] in comprados:
        return True
    if regra is not None and stats.get(regra[0], 0) >= regra[1]:
        return True
    return False


def avatar_comprar(aid, codigo):
    it = _avatar_item(codigo)
    if not it:
        return {"ok": False, "erro": "Item não existe."}
    if it["custo"] <= 0 or it.get("regra"):
        return {"ok": False, "erro": "Esse item não é da loja."}
    with conn() as c:
        if codigo in _comprados(c, aid):
            return {"ok": True, "status": "ativo"}
        moedas = c.execute("SELECT moedas FROM aluno WHERE id=?", (aid,)).fetchone()["moedas"]
        if moedas < it["custo"]:
            return {"ok": False, "erro": "Moedas insuficientes."}
        c.execute("UPDATE aluno SET moedas=moedas-? WHERE id=?", (it["custo"], aid))
        c.execute("INSERT INTO compra(aluno_id,item,nome,tipo,custo,status,ts) VALUES(?,?,?,?,?,?,?)",
                  (aid, codigo, it["nome"], "avatar", it["custo"], "ativo", datetime.now().isoformat()))
        c.commit()
    return {"ok": True, "status": "ativo"}


def avatar_equipar(aid, codigo, total_missoes=0):
    it = _avatar_item(codigo)
    if not it:
        return {"ok": False, "erro": "Item não existe."}
    with conn() as c:
        sup = _supremo_ok(_stats(c, aid), total_missoes)
        if not _avatar_tem(it, _stats(c, aid), _comprados(c, aid), sup):
            return {"ok": False, "erro": "Item ainda bloqueado."}
        slot = it.get("slot", "base")
        if slot == "base":
            c.execute("UPDATE aluno SET av_base=?, avatar=? WHERE id=?", (codigo, it.get("seed", ""), aid))
        else:
            col = SLOT_COL[slot]
            atual = c.execute(f"SELECT {col} v FROM aluno WHERE id=?", (aid,)).fetchone()["v"]
            novo = "" if atual == codigo else codigo
            c.execute(f"UPDATE aluno SET {col}=? WHERE id=?", (novo, aid))
        c.commit()
    return {"ok": True}


def _avatar_pub(it, stats, comprados, equipado_code, supremo_ok=False):
    slot = it.get("slot", "base")
    tem = _avatar_tem(it, stats, comprados, supremo_ok)
    oculto = bool(it.get("supremo")) and not tem
    if it.get("img"):
        img = it["img"]
    elif slot == "base":
        img = _dice_url(it["seed"], size=120)
    elif slot == "cor":
        img = _dice_url("Bipe", cor=it["param"], size=120)
    else:
        img = _dice_url("Bipe", olhos=it["param"], size=120)
    return {"codigo": it["codigo"], "nome": it["nome"],
            "img": ("" if oculto else img),
            "slot": slot, "custo": it["custo"],
            "categoria": it.get("categoria", "Robôs"),
            "supremo": bool(it.get("supremo")), "oculto": oculto,
            "dica": (it["regra"][2] if it.get("regra") else ""),
            "tem": tem, "equipado": it["codigo"] == equipado_code}


def escudo_comprar(aid):
    with conn() as c:
        r = c.execute("SELECT moedas, escudos FROM aluno WHERE id=?", (aid,)).fetchone()
        escudos = r["escudos"] or 0
        if escudos >= ESCUDO_MAX:
            return {"ok": False, "erro": f"Você já tem o máximo de escudos ({ESCUDO_MAX})."}
        if r["moedas"] < ESCUDO_CUSTO:
            return {"ok": False, "erro": "Moedas insuficientes."}
        c.execute("UPDATE aluno SET moedas=moedas-?, escudos=escudos+1 WHERE id=?", (ESCUDO_CUSTO, aid))
        c.commit()
    return {"ok": True, "escudos": escudos + 1}


def salvar_feedback(aid, texto):
    with conn() as c:
        c.execute("INSERT INTO feedback(aluno_id,texto,ts) VALUES(?,?,?)",
                  (aid, texto, datetime.now().isoformat()))
        c.commit()
    return {"ok": True}


def enviar_mensagem(aid, texto):
    with conn() as c:
        c.execute("INSERT INTO mensagem(aluno_id,texto,ts,vista) VALUES(?,?,?,0)",
                  (aid, texto, datetime.now().isoformat()))
        c.commit()
    return {"ok": True}


def marcar_mensagens_vistas(aid):
    with conn() as c:
        c.execute("UPDATE mensagem SET vista=1 WHERE aluno_id=? AND vista=0", (aid,))
        c.commit()
    return {"ok": True}


def avaliar_leitura(aid, materia, missao, nota, comentario=''):
    nota = max(1, min(5, int(nota)))
    with conn() as c:
        r = c.execute("SELECT 1 FROM leitura WHERE aluno_id=? AND materia=? AND missao=?",
                      (aid, materia, missao)).fetchone()
        if not r:
            return {"ok": False, "erro": "Leitura não encontrada."}
        c.execute("UPDATE leitura SET nota=?, comentario=?, nota_ts=? WHERE aluno_id=? AND materia=? AND missao=?",
                  (nota, comentario or '', datetime.now().isoformat(), aid, materia, missao))
        c.commit()
    return {"ok": True, "nota": nota}


def estado(aid, total_missoes=0):
    with conn() as c:
        arow = c.execute("SELECT * FROM aluno WHERE id=?", (aid,)).fetchone()
        aluno = dict(arow)
        aluno["xp_prox_nivel"] = aluno["nivel"] * XP_POR_NIVEL
        prog = [dict(r) for r in c.execute("SELECT * FROM progresso WHERE aluno_id=?", (aid,)).fetchall()]
        ult = [dict(r) for r in c.execute(
            "SELECT * FROM tentativa WHERE aluno_id=? ORDER BY id DESC LIMIT 20", (aid,)).fetchall()]
        s = _stats(c, aid)
        comprados = _comprados(c, aid)
        ativ = c.execute("SELECT COUNT(*) n FROM leitura_log WHERE aluno_id=? AND dia=?",
                         (aid, str(date.today()))).fetchone()["n"]
        md_metrics = _hoje_metrics(c, aid)
        feedbacks = [dict(r) for r in c.execute(
            "SELECT texto, ts FROM feedback WHERE aluno_id=? ORDER BY id DESC LIMIT 20", (aid,)).fetchall()]
        leituras = [dict(r) for r in c.execute(
            "SELECT materia, missao, titulo, resumo, foto, ts, nota, comentario, nota_ts"
            " FROM leitura WHERE aluno_id=? ORDER BY ts DESC", (aid,)).fetchall()]
        mensagens = [dict(r) for r in c.execute(
            "SELECT id, texto, ts, vista FROM mensagem WHERE aluno_id=? ORDER BY id DESC LIMIT 20", (aid,)).fetchall()]
    conquistas = [_conquista_pub(conq, s) for conq in CONQUISTAS]
    supremo_ok = _supremo_ok(s, total_missoes)
    progresso_pct = int(round(100 * s["missoes_concluidas"] / total_missoes)) if total_missoes else 0
    equipado = {"base": aluno.get("av_base") or "base_bipe",
                "cor": aluno.get("av_topo") or "",
                "olhos": aluno.get("av_rosto") or ""}
    base_eq = _base_item(equipado["base"])
    if base_eq.get("img"):
        url, url_contain = base_eq["img"], True
    else:
        url = _dice_url(_base_seed(equipado["base"]),
                        cor=_acc_param(equipado["cor"]) if equipado["cor"] else None,
                        olhos=_acc_param(equipado["olhos"]) if equipado["olhos"] else None,
                        size=160)
        url_contain = False
    avatares = {
        "url": url, "url_contain": url_contain,
        "supremo_ok": supremo_ok, "supremo_pct": int(SUPREMO_PCT * 100), "progresso_pct": progresso_pct,
        "bases": [_avatar_pub(it, s, comprados, equipado["base"], supremo_ok) for it in AVATAR_BASES],
        "acessorios": [_avatar_pub(it, s, comprados, equipado[it["slot"]], supremo_ok) for it in AVATAR_ACESSORIOS],
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
            "feedbacks": feedbacks, "leituras": leituras, "mensagens": mensagens,
            "atividades_hoje": ativ,
            "tux": {"dia": aluno.get("tux_dia", ""), "inicio": aluno.get("tux_inicio", "")}}


# ── Olimpíadas de Matemática (estilo Canguru) ─────────────────
# Fora do gate de leitura e do limite diário por construção: nada aqui toca
# leitura_log/progresso. Funções de simulado aceitam `agora` p/ testes de timer.
OLI_TOLERANCIA_SEG = 30
OLI_MOEDAS_SIMULADO = 30

OLI_MEDALHAS = {
    "oli_nivelado":  ("Canguru descoberto", "🦘"),
    "oli_unidade1":  ("Primeira unidade olímpica", "🥾"),
    "oli_trilha":    ("Trilha olímpica completa", "🏔️"),
    "oli_simulado1": ("Primeiro simulado", "🏁"),
    "oli_nota_top":  ("Nota olímpica de ouro", "🏆"),
}


def medalha_conceder(aid, codigo):
    """Concede uma medalha avulsa (idempotente). Retorna a medalha se for nova."""
    nome, emoji = OLI_MEDALHAS[codigo]
    with conn() as c:
        if c.execute("SELECT 1 FROM medalha WHERE aluno_id=? AND codigo=?", (aid, codigo)).fetchone():
            return None
        c.execute("INSERT INTO medalha(aluno_id,codigo,nome,emoji,ts) VALUES(?,?,?,?,?)",
                  (aid, codigo, nome, emoji, datetime.now().isoformat()))
        c.commit()
    return {"codigo": codigo, "nome": nome, "emoji": emoji}


def oli_perfil_get(aid):
    with conn() as c:
        r = c.execute("SELECT * FROM oli_perfil WHERE aluno_id=?", (aid,)).fetchone()
    return dict(r) if r else None


def oli_perfil_set_trilha(aid, trilha, origem, nivelamento_json=''):
    with conn() as c:
        c.execute("INSERT INTO oli_perfil(aluno_id,trilha,origem,nivelamento_json,ts) VALUES(?,?,?,?,?)"
                  " ON CONFLICT(aluno_id) DO UPDATE SET trilha=excluded.trilha, origem=excluded.origem,"
                  " nivelamento_json=CASE WHEN excluded.nivelamento_json<>'' THEN excluded.nivelamento_json"
                  "                       ELSE oli_perfil.nivelamento_json END, ts=excluded.ts",
                  (aid, trilha, origem, nivelamento_json or '', datetime.now().isoformat()))
        c.commit()
    return oli_perfil_get(aid)


def oli_progresso_list(aid, trilha=None):
    with conn() as c:
        if trilha:
            rows = c.execute("SELECT * FROM oli_progresso WHERE aluno_id=? AND trilha=?",
                             (aid, trilha)).fetchall()
        else:
            rows = c.execute("SELECT * FROM oli_progresso WHERE aluno_id=?", (aid,)).fetchall()
    return [dict(r) for r in rows]


def oli_registrar_resposta(aid, questao_id, trilha, eixo, acertou, pontos):
    """Prática de unidade: upsert de progresso; saltos/XP só na 1ª vez certa.
    Conta streak (estudar olimpíada é estudar), mas não consome atividade diária."""
    agora = datetime.now().isoformat()
    hoje = str(date.today())
    ganhou = False
    with conn() as c:
        row = c.execute("SELECT acertou FROM oli_progresso WHERE aluno_id=? AND questao_id=?",
                        (aid, questao_id)).fetchone()
        if row is None:
            c.execute("INSERT INTO oli_progresso(aluno_id,questao_id,trilha,eixo,acertou,tentativas,ultima_ts)"
                      " VALUES(?,?,?,?,?,1,?)", (aid, questao_id, trilha, eixo, 1 if acertou else 0, agora))
            ganhou = bool(acertou)
        else:
            ja_acertou = bool(row["acertou"])
            c.execute("UPDATE oli_progresso SET acertou=MAX(acertou,?), tentativas=tentativas+1, ultima_ts=?"
                      " WHERE aluno_id=? AND questao_id=?", (1 if acertou else 0, agora, aid, questao_id))
            ganhou = bool(acertou) and not ja_acertou
        saltos = xp = 0
        if ganhou:
            saltos = pontos
            xp = pontos * 2
            c.execute("INSERT INTO oli_perfil(aluno_id,saltos,ts) VALUES(?,?,?)"
                      " ON CONFLICT(aluno_id) DO UPDATE SET saltos=saltos+excluded.saltos",
                      (aid, saltos, agora))
            c.execute("UPDATE aluno SET xp=xp+? WHERE id=?", (xp, aid))
            novo_xp = c.execute("SELECT xp FROM aluno WHERE id=?", (aid,)).fetchone()["xp"]
            c.execute("UPDATE aluno SET nivel=? WHERE id=?", (nivel_de(novo_xp), aid))
        _bump_streak(c, aid, hoje)
        c.commit()
    return {"primeira_vez_certa": ganhou, "saltos_ganhos": saltos, "xp_ganho": xp}


def _oli_row(r):
    d = dict(r)
    d["respostas"] = json.loads(d.pop("respostas_json") or '{}')
    d["marcadas"] = json.loads(d.pop("marcadas_json") or '[]')
    d["detalhe"] = json.loads(d["detalhe_json"]) if d.get("detalhe_json") else None
    d.pop("detalhe_json", None)
    return d


def oli_sim_restante(row, agora=None):
    agora = agora or datetime.now()
    try:
        decorrido = (agora - datetime.fromisoformat(row["iniciado_ts"])).total_seconds()
    except (TypeError, ValueError):
        decorrido = 0
    return int(max(0, row["duracao_seg"] - decorrido))


def oli_sim_expirado(row, agora=None):
    """Expirado de verdade (com tolerância de rede): não aceita mais saves."""
    agora = agora or datetime.now()
    try:
        decorrido = (agora - datetime.fromisoformat(row["iniciado_ts"])).total_seconds()
    except (TypeError, ValueError):
        return False
    return decorrido > row["duracao_seg"] + OLI_TOLERANCIA_SEG


def oli_simulado_aberto(aid):
    with conn() as c:
        r = c.execute("SELECT * FROM oli_simulado WHERE aluno_id=? AND enviado=0"
                      " ORDER BY id DESC LIMIT 1", (aid,)).fetchone()
    return _oli_row(r) if r else None


def oli_simulado_get(aid, sim_row_id):
    with conn() as c:
        r = c.execute("SELECT * FROM oli_simulado WHERE id=? AND aluno_id=?",
                      (sim_row_id, aid)).fetchone()
    return _oli_row(r) if r else None


def oli_simulado_iniciar(aid, simulado_id, trilha, duracao_seg, agora=None):
    """Um simulado aberto por vez; reabrir o mesmo retoma (idempotente)."""
    agora = agora or datetime.now()
    aberto = oli_simulado_aberto(aid)
    if aberto:
        if aberto["simulado_id"] == simulado_id:
            return aberto
        return {"erro": "outro_aberto", "aberto": aberto}
    with conn() as c:
        cur = c.execute("INSERT INTO oli_simulado(aluno_id,simulado_id,trilha,iniciado_ts,duracao_seg)"
                        " VALUES(?,?,?,?,?)", (aid, simulado_id, trilha, agora.isoformat(), duracao_seg))
        c.commit()
        sid = cur.lastrowid
    return oli_simulado_get(aid, sid)


def oli_simulado_salvar(aid, sim_row_id, questao_id=None, resposta=None, branco=False,
                        limpar=False, marcadas=None, agora=None):
    """Autosave atômico. Branco é explícito e reversível; limpar remove a entrada.
    Se o tempo (com tolerância) estourou, não salva e sinaliza expiração."""
    agora = agora or datetime.now()
    with conn() as c:
        r = c.execute("SELECT * FROM oli_simulado WHERE id=? AND aluno_id=?",
                      (sim_row_id, aid)).fetchone()
        if not r:
            return {"erro": "nao_encontrado"}
        row = _oli_row(r)
        if row["enviado"]:
            return {"erro": "ja_enviado"}
        if oli_sim_expirado(row, agora):
            return {"expirado": True}
        respostas = row["respostas"]
        if questao_id:
            if limpar:
                respostas.pop(questao_id, None)
            elif branco:
                respostas[questao_id] = {"r": None, "branco": 1, "ts": agora.isoformat()}
            elif resposta is not None:
                respostas[questao_id] = {"r": int(resposta), "ts": agora.isoformat()}
        novas_marcadas = row["marcadas"] if marcadas is None else list(marcadas)
        c.execute("UPDATE oli_simulado SET respostas_json=?, marcadas_json=? WHERE id=?",
                  (json.dumps(respostas), json.dumps(novas_marcadas), sim_row_id))
        c.commit()
    return {"ok": True, "restante_seg": oli_sim_restante(row, agora)}


def oli_simulado_enviar(aid, sim_row_id, nota, detalhe_json, auto=0, agora=None):
    """Grava nota/relatório e credita recompensas (uma única vez)."""
    agora = agora or datetime.now()
    with conn() as c:
        r = c.execute("SELECT * FROM oli_simulado WHERE id=? AND aluno_id=?",
                      (sim_row_id, aid)).fetchone()
        if not r:
            return {"erro": "nao_encontrado"}
        if r["enviado"]:
            return {"ja_enviado": True, "nota": r["nota"]}
        c.execute("UPDATE oli_simulado SET enviado=1, enviado_ts=?, auto=?, nota=?, detalhe_json=? WHERE id=?",
                  (agora.isoformat(), 1 if auto else 0, nota, detalhe_json, sim_row_id))
        xp = max(0, int(round(nota)))
        saltos = max(0, int(round(nota)))
        c.execute("INSERT INTO oli_perfil(aluno_id,saltos,ts) VALUES(?,?,?)"
                  " ON CONFLICT(aluno_id) DO UPDATE SET saltos=saltos+excluded.saltos",
                  (aid, saltos, agora.isoformat()))
        c.execute("UPDATE aluno SET xp=xp+?, moedas=moedas+? WHERE id=?",
                  (xp, OLI_MOEDAS_SIMULADO, aid))
        novo_xp = c.execute("SELECT xp FROM aluno WHERE id=?", (aid,)).fetchone()["xp"]
        c.execute("UPDATE aluno SET nivel=? WHERE id=?", (nivel_de(novo_xp), aid))
        _bump_streak(c, aid, str(date.today()))
        c.commit()
    return {"ok": True, "xp_ganho": xp, "saltos_ganhos": saltos, "moedas_ganhas": OLI_MOEDAS_SIMULADO}


def oli_simulados_do_aluno(aid):
    """Histórico de simulados enviados (mais antigo primeiro — evolução)."""
    with conn() as c:
        rows = c.execute("SELECT id, simulado_id, trilha, iniciado_ts, enviado_ts, auto, nota"
                         " FROM oli_simulado WHERE aluno_id=? AND enviado=1 ORDER BY id", (aid,)).fetchall()
    return [dict(r) for r in rows]
