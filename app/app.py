#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — backend FastAPI (Fase 1, single-aluno).
Serve o hub do aluno, o painel dos pais e a API (correção server-side,
gamificação e gate de leitura). Persistência via db.py (SQLite em /data).
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
ALUNO_SENHA = os.environ.get('ALUNO_SENHA', 'aluno')
PAI_SENHA   = os.environ.get('PAI_SENHA', os.environ.get('PORTAL_SENHA', 'pai'))
TERMINAL_URL = os.environ.get('TERMINAL_URL', 'https://vgtux.vsanexus.com')
FOTOS_DIR   = Path('/data/fotos')
MAX_FOTO    = 10 * 1024 * 1024
# Gate do Tux + limites diários
TRILHA_MATERIAS   = [m.strip() for m in os.environ.get('TRILHA_MATERIAS', 'matematica,portugues,ciencias').split(',') if m.strip()]
ATIVIDADES_POR_DIA = int(os.environ.get('ATIVIDADES_POR_DIA', '2'))
TUX_MINUTOS        = int(os.environ.get('TUX_MINUTOS', '60'))

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
        # só aceita arquivos de matéria (evita carregar JSONs de outro formato)
        if isinstance(data, dict) and 'id' in data and 'missoes' in data:
            mats.append(data)
    mats.sort(key=lambda m: m.get('ordem', 99))
    return mats

CONTEUDO_FULL = _carregar_conteudo()

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

# ── Auth (senha por query, igual ao portal) ───────────────────
def checar(senha, esperada):
    if senha != esperada:
        raise HTTPException(401, "Senha inválida")

# ── Correção ──────────────────────────────────────────────────
def _norm(s):
    s = unicodedata.normalize('NFKC', str(s)).strip().casefold()
    return s

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

# ── Páginas ───────────────────────────────────────────────────
@app.get('/', response_class=HTMLResponse)
def home():
    return (STATIC / 'index.html').read_text(encoding='utf-8')

@app.get('/pais', response_class=HTMLResponse)
def pais():
    return (STATIC / 'pais.html').read_text(encoding='utf-8')

# PWA + estáticos servidos da raiz (escopo do service worker = '/')
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

# ── API do aluno ──────────────────────────────────────────────
@app.get('/api/conteudo')
def api_conteudo(senha: str = ''):
    checar(senha, ALUNO_SENHA)
    return JSONResponse({"materias": _sanitizar(CONTEUDO_FULL),
                         "config": {"terminal_url": TERMINAL_URL}})

def _calcular_gate(e):
    """Monta o estado da trilha obrigatória + cap diário + tempo do Tux."""
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
    restante = db.tux_restante(TUX_MINUTOS)
    return {
        "atividades_hoje": e.get("atividades_hoje", 0),
        "limite": ATIVIDADES_POR_DIA,
        "atingiu_limite": e.get("atividades_hoje", 0) >= ATIVIDADES_POR_DIA,
        "trilha": {"destravado": destravado, "faltam": faltam, "pendentes": pendentes},
        "tux": {"destravado": destravado, "minutos": TUX_MINUTOS,
                "restante_seg": restante, "esgotado": (restante is not None and restante <= 0)},
    }

@app.get('/api/estado')
def api_estado(senha: str = ''):
    checar(senha, ALUNO_SENHA)
    e = db.estado()
    e["config"] = {"terminal_url": TERMINAL_URL}
    e["gate"] = _calcular_gate(e)
    return JSONResponse(e)

class CorrigirIn(BaseModel):
    materia: str
    missao:  str
    exercicio: str
    resposta: object = None

@app.post('/api/corrigir')
def api_corrigir(payload: CorrigirIn, senha: str = ''):
    """Corrige UM exercício (feedback imediato) sem gravar nada — gabarito fica no servidor."""
    checar(senha, ALUNO_SENHA)
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
    checar(senha, ALUNO_SENHA)
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
    novas = db.registrar_tentativa(payload.materia, payload.missao, acertos, total,
                                   estrelas, xp, payload.segundos)
    return {"ok": True, "acertos": acertos, "total": total, "estrelas": estrelas,
            "xp_ganho": xp, "correcoes": correcoes, "novas_medalhas": novas,
            "leitura_pendente": estrelas >= 1}

class LeituraIn(BaseModel):
    materia: str
    missao:  str
    titulo:  str = ''
    resumo:  str = ''

def _cap_atingido(materia, missao):
    """True se já bateu o limite diário e esta missão não foi concluída ainda."""
    return db.atividades_hoje() >= ATIVIDADES_POR_DIA and not db.missao_concluida(materia, missao)

@app.post('/api/leitura')
def api_leitura(payload: LeituraIn, senha: str = ''):
    checar(senha, ALUNO_SENHA)
    if _cap_atingido(payload.materia, payload.missao):
        return JSONResponse(status_code=422, content={"ok": False, "limite": True,
            "erro": "Você já fez suas 2 atividades de hoje. Volte amanhã! 🌙"})
    if len(payload.resumo.strip()) < 50:
        return JSONResponse(status_code=422,
                            content={"ok": False, "erro": "Escreva um resumo maior (mín. 50 caracteres) ou envie a foto."})
    novas = db.concluir_leitura(payload.materia, payload.missao)
    return {"ok": True, "novas_medalhas": novas}

@app.post('/api/leitura-foto')
async def api_leitura_foto(materia: str = Form(...), missao: str = Form(...),
                           titulo: str = Form(''), foto: UploadFile = File(...),
                           senha: str = ''):
    checar(senha, ALUNO_SENHA)
    if _cap_atingido(materia, missao):
        return JSONResponse(status_code=422, content={"ok": False, "limite": True,
            "erro": "Você já fez suas 2 atividades de hoje. Volte amanhã! 🌙"})
    if not (foto.content_type or '').lower().startswith('image/'):
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Envie uma imagem."})
    data = await foto.read(MAX_FOTO + 1)
    if len(data) > MAX_FOTO or not data:
        return JSONResponse(status_code=422, content={"ok": False, "erro": "Foto inválida (vazia ou >10MB)."})
    FOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ext = 'png' if 'png' in (foto.content_type or '') else 'jpg'
    nome = f"escola-{materia}-{missao}.{ext}"
    (FOTOS_DIR / nome).write_bytes(data)
    novas = db.concluir_leitura(materia, missao)
    return {"ok": True, "foto": nome, "novas_medalhas": novas}

@app.post('/api/tux/abrir')
def api_tux_abrir(senha: str = ''):
    checar(senha, ALUNO_SENHA)
    g = _calcular_gate(db.estado())
    if not g["trilha"]["destravado"]:
        return JSONResponse(status_code=423, content={"ok": False, "motivo": "trilha",
            "faltam": g["trilha"]["faltam"], "pendentes": g["trilha"]["pendentes"]})
    restante = db.tux_abrir(TUX_MINUTOS)
    if restante <= 0:
        return JSONResponse(status_code=423, content={"ok": False, "motivo": "tempo", "restante_seg": 0})
    return {"ok": True, "url": TERMINAL_URL, "restante_seg": restante}

class AvatarIn(BaseModel):
    codigo: str

@app.post('/api/avatar/comprar')
def api_avatar_comprar(payload: AvatarIn, senha: str = ''):
    checar(senha, ALUNO_SENHA)
    return db.avatar_comprar(payload.codigo)

@app.post('/api/avatar/equipar')
def api_avatar_equipar(payload: AvatarIn, senha: str = ''):
    checar(senha, ALUNO_SENHA)
    return db.avatar_equipar(payload.codigo)

# ── Edu Help (chat de dúvidas, FAQ roteirizado) ───────────────
def _eduhelp_cfg():
    """Valores reais das regras, injetados nas respostas do Edu."""
    return {"limite": ATIVIDADES_POR_DIA, "tux_min": TUX_MINUTOS,
            "xp_nivel": db.XP_POR_NIVEL, "est1": 40, "est2": 70, "est3": 90}

class EduHelpIn(BaseModel):
    pergunta: str = ''

@app.get('/api/eduhelp/sugestoes')
def api_eduhelp_sugestoes(senha: str = ''):
    checar(senha, ALUNO_SENHA)
    return JSONResponse(eduhelp.sugestoes(_eduhelp_cfg()))

@app.post('/api/eduhelp')
def api_eduhelp(payload: EduHelpIn, senha: str = ''):
    checar(senha, ALUNO_SENHA)
    return JSONResponse(eduhelp.responder(payload.pergunta, _eduhelp_cfg()))

# ── API do pai ────────────────────────────────────────────────
@app.get('/api/pais/estado')
def api_pais_estado(senha: str = ''):
    checar(senha, PAI_SENHA)
    e = db.estado()
    # nomes das matérias/missões p/ exibição amigável
    nomes = {}
    for m in CONTEUDO_FULL:
        nomes[m['id']] = {"nome": m['nome'], "icone": m.get('icone', ''), "cor": m.get('cor', ''),
                          "missoes": {mi['id']: mi['titulo'] for mi in m.get('missoes', [])},
                          "total_missoes": len([x for x in m.get('missoes', []) if not x.get('link')])}
    e["catalogo"] = nomes
    return JSONResponse(e)

@app.get('/api/foto/{nome}')
def api_foto(nome: str, senha: str = ''):
    checar(senha, PAI_SENHA)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', nome):
        raise HTTPException(400, "Nome inválido")
    p = FOTOS_DIR / nome
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(str(p))
