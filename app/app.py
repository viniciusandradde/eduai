#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — backend FastAPI (multiusuário: admin → pais → filhos).
Serve o hub do aluno, o painel dos pais/admin e a API. Auth por token de sessão
(com compatibilidade retroativa à senha antiga do aluno). Persistência via db.py.
"""
import os, json, re, unicodedata
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import eduhelp

BASE        = Path(__file__).parent
STATIC      = BASE / 'static'
CONTEUDO    = BASE / 'conteudo'
ALUNO_SENHA = os.environ.get('ALUNO_SENHA', 'aluno')   # back-compat (Vittor = aluno 1)
PAI_SENHA   = os.environ.get('PAI_SENHA', os.environ.get('PORTAL_SENHA', 'pai'))
TERMINAL_URL = os.environ.get('TERMINAL_URL', 'https://vgtux.vsanexus.com')
FOTOS_DIR   = Path('/data/fotos')
MAX_FOTO    = 10 * 1024 * 1024
TRILHA_MATERIAS   = [m.strip() for m in os.environ.get('TRILHA_MATERIAS', 'matematica,portugues,ciencias').split(',') if m.strip()]
ATIVIDADES_POR_DIA = int(os.environ.get('ATIVIDADES_POR_DIA', '2'))
TUX_MINUTOS        = int(os.environ.get('TUX_MINUTOS', '60'))
FOTO_A_PARTIR_PCT  = int(os.environ.get('FOTO_A_PARTIR_PCT', '50'))

app = FastAPI(title="VSA EduAI")
db.init_db()

# ── Conteúdo (carregado uma vez) ──────────────────────────────
def _carregar_conteudo():
    mats = []
    for f in sorted(CONTEUDO.glob('*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(data, dict) and 'id' in data and 'missoes' in data:
            mats.append(data)
    mats.sort(key=lambda m: m.get('ordem', 99))
    return mats

CONTEUDO_FULL = _carregar_conteudo()
TOTAL_MISSOES = sum(len([mi for mi in m.get('missoes', []) if not mi.get('link')])
                    for m in CONTEUDO_FULL)

(STATIC / 'avatars').mkdir(parents=True, exist_ok=True)
app.mount('/avatars', StaticFiles(directory=str(STATIC / 'avatars')), name='avatars')

def _missao(materia_id, missao_id):
    for m in CONTEUDO_FULL:
        if m['id'] == materia_id:
            for mi in m.get('missoes', []):
                if mi['id'] == missao_id:
                    return mi
    return None

def _sanitizar(mats):
    """Remove gabaritos antes de enviar ao cliente."""
    out = []
    for m in mats:
        mm = {k: v for k, v in m.items() if k != 'missoes'}
        mm['missoes'] = []
        for mi in m.get('missoes', []):
            exs = []
            for e in mi.get('exercicios', []):
                exs.append({k: v for k, v in e.items()
                            if k not in ('correta', 'resposta', 'explicacao', 'aceitos')})
            mm['missoes'].append({**{k: v for k, v in mi.items() if k != 'exercicios'},
                                  'exercicios': exs})
        out.append(mm)
    return out

# ── Auth por token (senha = token de sessão; back-compat p/ Vittor) ──
def _aluno_id(senha):
    s = db.sessao_resolve(senha)
    if s and s[0] == 'aluno':
        return s[1]
    if senha and senha == ALUNO_SENHA:   # cliente antigo do Vittor
        return 1
    raise HTTPException(401, "Sessão inválida")

def _pai(senha):
    s = db.sessao_resolve(senha)
    if s and s[0] == 'pai':
        p = db.pai_get(s[1])
        if p:
            return p
    raise HTTPException(401, "Sessão inválida")

def _pai_aluno(senha, aluno):
    """Pai autenticado + valida que o filho é dele (admin acessa qualquer)."""
    p = _pai(senha)
    aid = int(aluno or 0)
    if not aid:
        raise HTTPException(400, "Filho não informado")
    if not (p["is_admin"] or db.aluno_pertence(aid, p["id"])):
        raise HTTPException(403, "Esse filho não é seu")
    return p, aid

# ── Correção ──────────────────────────────────────────────────
def _norm(s):
    return unicodedata.normalize('NFKC', str(s)).strip().casefold()

def _acerto(ex, resp):
    t = ex['tipo']
    try:
        if t == 'multipla':
            return int(resp) == int(ex['correta'])
        if t == 'numerica':
            return abs(float(resp) - float(ex['resposta'])) < 1e-6
        if t == 'vf':
            v = resp if isinstance(resp, bool) else str(resp).strip().lower() in ('true', 'v', 'verdadeiro', '1', 'sim')
            return bool(v) == bool(ex['resposta'])
        if t == 'lacuna':
            aceitos = [ex['resposta']] + list(ex.get('aceitos', []))
            return _norm(resp) in [_norm(a) for a in aceitos]
    except Exception:
        return False
    return False

def _estrelas(pct):
    if pct >= 0.9: return 3
    if pct >= 0.7: return 2
    if pct >= 0.4: return 1
    return 0

def _foto_obrigatoria_pct(conc):
    return bool(TOTAL_MISSOES) and (100 * conc / TOTAL_MISSOES) >= FOTO_A_PARTIR_PCT

# ── Páginas ───────────────────────────────────────────────────
@app.get('/', response_class=HTMLResponse)
def home():
    return (STATIC / 'index.html').read_text(encoding='utf-8')

@app.get('/pais', response_class=HTMLResponse)
def pais():
    return (STATIC / 'pais.html').read_text(encoding='utf-8')

@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(str(STATIC / 'manifest.webmanifest'), media_type='application/manifest+json')

@app.get('/sw.js')
def sw():
    return FileResponse(str(STATIC / 'sw.js'), media_type='application/javascript')

@app.get('/app.js')
def appjs():
    return FileResponse(str(STATIC / 'app.js'), media_type='application/javascript')

@app.get('/pais.js')
def paisjs():
    return FileResponse(str(STATIC / 'pais.js'), media_type='application/javascript')

@app.get('/style.css')
def css():
    return FileResponse(str(STATIC / 'style.css'), media_type='text/css')

@app.get('/icon-192.png')
def i192():
    return FileResponse(str(STATIC / 'icon-192.png'), media_type='image/png')

@app.get('/icon-512.png')
def i512():
    return FileResponse(str(STATIC / 'icon-512.png'), media_type='image/png')

# ── Login / sessão ────────────────────────────────────────────
class LoginIn(BaseModel):
    login: str = ''
    senha: str = ''

@app.post('/api/login')
def api_login(payload: LoginIn):
    p = db.pai_login(payload.login, payload.senha)
    if p:
        tok = db.sessao_nova('pai', p['id'])
        return {"ok": True, "token": tok, "tipo": "pai", "nome": p['nome'],
                "is_admin": p['is_admin'], "bem_vindo": p['bem_vindo'],
                "filhos": db.listar_alunos(p['id'])}
    a = db.aluno_login(payload.login, payload.senha)
    if a:
        tok = db.sessao_nova('aluno', a['id'])
        return {"ok": True, "token": tok, "tipo": "aluno", "nome": a['nome']}
    return JSONResponse(status_code=401, content={"ok": False, "erro": "Usuário ou senha inválidos."})

@app.post('/api/logout')
def api_logout(senha: str = ''):
    db.sessao_encerra(senha)
    return {"ok": True}

# ── API do aluno ──────────────────────────────────────────────
@app.get('/api/conteudo')
def api_conteudo(senha: str = ''):
    _aluno_id(senha)
    return JSONResponse({"materias": _sanitizar(CONTEUDO_FULL),
                         "config": {"terminal_url": TERMINAL_URL}})

def _calcular_gate(e, aid):
    prog = e.get("progresso", [])
    concluidas = {(p["materia"], p["missao"]) for p in prog if p.get("concluida")}
    faltam, pendentes = [], []
    for mid in TRILHA_MATERIAS:
        m = next((x for x in CONTEUDO_FULL if x["id"] == mid), None)
        if not m:
            continue
        reais = [mi for mi in m.get("missoes", []) if not mi.get("link")]
        feita = any((mid, mi["id"]) in concluidas for mi in reais)
        if not feita:
            faltam.append({"materia": mid, "nome": m["nome"]})
            prox = next((mi for mi in reais if (mid, mi["id"]) not in concluidas), None)
            if prox:
                pendentes.append({"materia": mid, "nome": m["nome"], "missao": prox["id"], "titulo": prox["titulo"]})
    destravado = len(faltam) == 0
    restante = db.tux_restante(aid, TUX_MINUTOS)
    conc = len(concluidas)
    return {
        "atividades_hoje": e.get("atividades_hoje", 0),
        "limite": ATIVIDADES_POR_DIA,
        "atingiu_limite": e.get("atividades_hoje", 0) >= ATIVIDADES_POR_DIA,
        "foto_obrigatoria": _foto_obrigatoria_pct(conc),
        "foto_pct": FOTO_A_PARTIR_PCT,
        "trilha": {"destravado": destravado, "faltam": faltam, "pendentes": pendentes},
        "tux": {"destravado": destravado, "minutos": TUX_MINUTOS,
                "restante_seg": restante, "esgotado": (restante is not None and restante <= 0)},
    }

@app.get('/api/estado')
def api_estado(senha: str = ''):
    aid = _aluno_id(senha)
    e = db.estado(aid, TOTAL_MISSOES)
    e["config"] = {"terminal_url": TERMINAL_URL}
    e["gate"] = _calcular_gate(e, aid)
    return JSONResponse(e)

class CorrigirIn(BaseModel):
    materia: str
    missao:  str
    exercicio: str
    resposta: object = None

@app.post('/api/corrigir')
def api_corrigir(payload: CorrigirIn, senha: str = ''):
    _aluno_id(senha)
    mi = _missao(payload.materia, payload.missao)
    if not mi:
        raise HTTPException(404, "Missão não encontrada")
    ex = next((e for e in mi.get('exercicios', []) if e['id'] == payload.exercicio), None)
    if not ex:
        raise HTTPException(404, "Exercício não encontrado")
    ok = _acerto(ex, payload.resposta)
    return {"correto": ok, "explicacao": ex.get('explicacao', ''),
            "resposta": ex.get('correta', ex.get('resposta'))}

class TentativaIn(BaseModel):
    materia: str
    missao:  str
    respostas: dict
    segundos: int = 0

@app.post('/api/tentativa')
def api_tentativa(payload: TentativaIn, senha: str = ''):
    aid = _aluno_id(senha)
    mi = _missao(payload.materia, payload.missao)
    if not mi:
        raise HTTPException(404, "Missão não encontrada")
    exs = mi.get('exercicios', [])
    total = len(exs)
    correcoes, acertos = [], 0
    for e in exs:
        resp = payload.respostas.get(e['id'])
        ok = _acerto(e, resp)
        if ok: acertos += 1
        correcoes.append({"id": e['id'], "correto": ok,
                          "explicacao": e.get('explicacao', ''),
                          "resposta": e.get('correta', e.get('resposta'))})
    pct = (acertos / total) if total else 0
    estrelas = _estrelas(pct)
    xp = acertos * 10 + estrelas * 10
    novas = db.registrar_tentativa(aid, payload.materia, payload.missao, acertos, total,
                                   estrelas, xp, payload.segundos)
    return {"ok": True, "acertos": acertos, "total": total, "estrelas": estrelas,
            "xp_ganho": xp, "correcoes": correcoes, "novas_medalhas": novas,
            "leitura_pendente": estrelas >= 1}

class LeituraIn(BaseModel):
    materia: str
    missao:  str
    titulo:  str = ''
    resumo:  str = ''

def _cap_atingido(aid, materia, missao):
    return db.atividades_hoje(aid) >= ATIVIDADES_POR_DIA and not db.missao_concluida(aid, materia, missao)

@app.post('/api/leitura')
def api_leitura(payload: LeituraIn, senha: str = ''):
    """Resumo digitado — permitido só ANTES de FOTO_A_PARTIR_PCT% de progresso."""
    aid = _aluno_id(senha)
    if db.missao_concluida(aid, payload.materia, payload.missao):
        return {"ok": True, "ja_registrado": True, "novas_medalhas": []}
    if _foto_obrigatoria_pct(db.total_concluidas(aid)):
        return JSONResponse(status_code=422, content={"ok": False, "so_foto": True,
            "erro": "Agora você já é avançado! Faça o resumo no papel e envie a FOTO. 📸"})
    if _cap_atingido(aid, payload.materia, payload.missao):
        return JSONResponse(status_code=422, content={"ok": False, "limite": True,
            "erro": "Você já fez suas 2 atividades de hoje. Volte amanhã! 🌙"})
    if not (payload.titulo or '').strip():
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Escreva o título do que você leu."})
    if len(payload.resumo.strip()) < 50:
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Escreva um resumo maior (mín. 50 letras)."})
    novas = db.concluir_leitura(aid, payload.materia, payload.missao,
                                payload.titulo.strip(), '', payload.resumo.strip())
    return {"ok": True, "novas_medalhas": novas}

@app.post('/api/leitura-foto')
async def api_leitura_foto(materia: str = Form(...), missao: str = Form(...),
                           titulo: str = Form(''), foto: UploadFile = File(...),
                           senha: str = ''):
    aid = _aluno_id(senha)
    if db.missao_concluida(aid, materia, missao):     # imutável
        return {"ok": True, "ja_registrado": True, "novas_medalhas": [],
                "msg": "Esse resumo já foi registrado e fica guardado. 💜"}
    if _cap_atingido(aid, materia, missao):
        return JSONResponse(status_code=422, content={"ok": False, "limite": True,
            "erro": "Você já fez suas 2 atividades de hoje. Volte amanhã! 🌙"})
    if not (titulo or '').strip():
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Escreva o título do que você leu."})
    if not (foto.content_type or '').lower().startswith('image/'):
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Envie uma imagem."})
    data = await foto.read(MAX_FOTO + 1)
    if len(data) > MAX_FOTO or not data:
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Foto inválida (vazia ou >10MB)."})
    FOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ext = 'png' if 'png' in (foto.content_type or '') else 'jpg'
    nome = f"escola-{aid}-{materia}-{missao}.{ext}"   # por aluno (não colide)
    (FOTOS_DIR / nome).write_bytes(data)
    novas = db.concluir_leitura(aid, materia, missao, titulo.strip(), nome)
    return {"ok": True, "foto": nome, "novas_medalhas": novas}

@app.post('/api/tux/abrir')
def api_tux_abrir(senha: str = ''):
    aid = _aluno_id(senha)
    g = _calcular_gate(db.estado(aid, TOTAL_MISSOES), aid)
    if not g["trilha"]["destravado"]:
        return JSONResponse(status_code=423, content={"ok": False, "motivo": "trilha",
            "faltam": g["trilha"]["faltam"], "pendentes": g["trilha"]["pendentes"]})
    restante = db.tux_abrir(aid, TUX_MINUTOS)
    if restante <= 0:
        return JSONResponse(status_code=423, content={"ok": False, "motivo": "tempo", "restante_seg": 0})
    return {"ok": True, "url": TERMINAL_URL, "restante_seg": restante}

class AvatarIn(BaseModel):
    codigo: str

@app.post('/api/avatar/comprar')
def api_avatar_comprar(payload: AvatarIn, senha: str = ''):
    aid = _aluno_id(senha)
    return db.avatar_comprar(aid, payload.codigo)

@app.post('/api/avatar/equipar')
def api_avatar_equipar(payload: AvatarIn, senha: str = ''):
    aid = _aluno_id(senha)
    return db.avatar_equipar(aid, payload.codigo, TOTAL_MISSOES)

@app.post('/api/bau/abrir')
def api_bau_abrir(senha: str = ''):
    aid = _aluno_id(senha)
    return db.bau_abrir(aid)

@app.post('/api/escudo/comprar')
def api_escudo_comprar(senha: str = ''):
    aid = _aluno_id(senha)
    return db.escudo_comprar(aid)

class FeedbackIn(BaseModel):
    texto: str = ''

@app.post('/api/feedback')
def api_feedback(payload: FeedbackIn, senha: str = ''):
    aid = _aluno_id(senha)
    t = (payload.texto or '').strip()
    if not (3 <= len(t) <= 500):
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Escreva sua ideia (3 a 500 letras)."})
    return db.salvar_feedback(aid, t)

@app.post('/api/mensagens/vistas')
def api_mensagens_vistas(senha: str = ''):
    aid = _aluno_id(senha)
    return db.marcar_mensagens_vistas(aid)

# ── Edu Help ──────────────────────────────────────────────────
def _eduhelp_cfg():
    return {"limite": ATIVIDADES_POR_DIA, "tux_min": TUX_MINUTOS,
            "xp_nivel": db.XP_POR_NIVEL, "est1": 40, "est2": 70, "est3": 90}

class EduHelpIn(BaseModel):
    pergunta: str = ''

@app.get('/api/eduhelp/sugestoes')
def api_eduhelp_sugestoes(senha: str = ''):
    _aluno_id(senha)
    return JSONResponse(eduhelp.sugestoes(_eduhelp_cfg()))

@app.post('/api/eduhelp')
def api_eduhelp(payload: EduHelpIn, senha: str = ''):
    _aluno_id(senha)
    return JSONResponse(eduhelp.responder(payload.pergunta, _eduhelp_cfg()))

# ── API do pai ────────────────────────────────────────────────
def _catalogo():
    nomes = {}
    for m in CONTEUDO_FULL:
        nomes[m['id']] = {"nome": m['nome'], "icone": m.get('icone', ''), "cor": m.get('cor', ''),
                          "missoes": {mi['id']: mi['titulo'] for mi in m.get('missoes', [])},
                          "total_missoes": len([x for x in m.get('missoes', []) if not x.get('link')])}
    return nomes

@app.get('/api/pais/filhos')
def api_pais_filhos(senha: str = ''):
    p = _pai(senha)
    return {"nome": p['nome'], "is_admin": p['is_admin'], "bem_vindo": p['bem_vindo'],
            "filhos": db.listar_alunos(p['id'])}

class FilhoIn(BaseModel):
    nome:  str = ''
    idade: int = 0
    login: str = ''
    senha: str = ''

@app.post('/api/pais/criar-filho')
def api_criar_filho(payload: FilhoIn, senha: str = ''):
    p = _pai(senha)
    return db.criar_aluno(p['id'], payload.nome, payload.idade, payload.login, payload.senha)

@app.post('/api/pais/bem-vindo-ok')
def api_bem_vindo(senha: str = ''):
    p = _pai(senha)
    return db.bem_vindo_ok(p['id'])

@app.get('/api/pais/estado')
def api_pais_estado(senha: str = '', aluno: int = 0):
    p, aid = _pai_aluno(senha, aluno)
    e = db.estado(aid, TOTAL_MISSOES)
    e["catalogo"] = _catalogo()
    e["filho"] = db.aluno_get(aid)
    return JSONResponse(e)

class MensagemIn(BaseModel):
    texto: str = ''
    aluno: int = 0

@app.post('/api/pais/mensagem')
def api_pais_mensagem(payload: MensagemIn, senha: str = ''):
    p, aid = _pai_aluno(senha, payload.aluno)
    t = (payload.texto or '').strip()
    if not (2 <= len(t) <= 300):
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Escreva a mensagem (2 a 300 letras)."})
    return db.enviar_mensagem(aid, t)

class AvaliarIn(BaseModel):
    materia: str
    missao:  str
    nota:    int
    comentario: str = ''
    aluno: int = 0

@app.post('/api/pais/avaliar')
def api_pais_avaliar(payload: AvaliarIn, senha: str = ''):
    p, aid = _pai_aluno(senha, payload.aluno)
    return db.avaliar_leitura(aid, payload.materia, payload.missao, payload.nota, payload.comentario)

# ── API do admin ──────────────────────────────────────────────
def _admin(senha):
    p = _pai(senha)
    if not p['is_admin']:
        raise HTTPException(403, "Apenas o admin.")
    return p

@app.get('/api/admin/pais')
def api_admin_pais(senha: str = ''):
    _admin(senha)
    return {"pais": db.listar_pais()}

class PaiNovoIn(BaseModel):
    nome:  str = ''
    login: str = ''
    senha: str = ''

@app.post('/api/admin/criar-pai')
def api_admin_criar_pai(payload: PaiNovoIn, senha: str = ''):
    _admin(senha)
    return db.criar_pai(payload.nome, payload.login, payload.senha, 0)

# ── Foto do resumo (pai dono do aluno) ────────────────────────
@app.get('/api/foto/{nome}')
def api_foto(nome: str, senha: str = ''):
    p = _pai(senha)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', nome):
        raise HTTPException(400, "Nome inválido")
    mm = re.match(r'escola-(\d+)-', nome)
    aid = int(mm.group(1)) if mm else 1     # nomes antigos (sem id) = Vittor (1)
    if not (p['is_admin'] or db.aluno_pertence(aid, p['id'])):
        raise HTTPException(403, "Foto de outro aluno")
    pth = FOTOS_DIR / nome
    if not pth.is_file():
        raise HTTPException(404)
    return FileResponse(str(pth))
