#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSA EduAI — backend FastAPI (multiusuário: admin → pais → filhos).
Serve o hub do aluno, o painel dos pais/admin e a API. Auth por token de sessão
(com compatibilidade retroativa à senha antiga do aluno). Persistência via db.py.
"""
import os, json, re, unicodedata
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import eduhelp
import olimpiadas as oli

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
oli.carregar()      # valida o banco olímpico no boot — não sobe com conteúdo quebrado

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

@app.get('/oli.js')
def olijs():
    return FileResponse(str(STATIC / 'oli.js'), media_type='application/javascript')

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

# ── Olimpíadas de Matemática (estilo Canguru) ─────────────────
def _oli_perfil(aid):
    p = db.oli_perfil_get(aid)
    if not p or not p.get('trilha'):
        raise HTTPException(409, "Faça o nivelamento primeiro")
    return p

def _oli_respostas_map(row):
    """respostas_json → {qid: int|None} (branco explícito e ausente viram None)."""
    out = {}
    for qid, e in (row.get('respostas') or {}).items():
        out[qid] = e.get('r') if isinstance(e, dict) else None
    return out

def _oli_estrategias_pub(ids=None):
    return [e for e in oli.ESTRATEGIAS if ids is None or e['id'] in ids]

def _oli_medalhas_pratica(aid, trilha):
    """Concede medalhas de unidade/trilha completa após uma resposta certa."""
    unidades = oli.montar_unidades(trilha, db.oli_progresso_list(aid, trilha))
    completas = [u for u in unidades if u['total'] and u['feitas'] >= u['total']]
    novas = []
    if completas:
        m = db.medalha_conceder(aid, 'oli_unidade1')
        if m: novas.append(m)
    if unidades and len(completas) == len(unidades):
        m = db.medalha_conceder(aid, 'oli_trilha')
        if m: novas.append(m)
    return novas

def _oli_sim_pub(row, agora=None):
    """Estado do simulado aberto para o cliente (questões sanitizadas, sem correção)."""
    sim = oli.SIMULADOS[row['simulado_id']]
    return {"sim_id": row['id'], "simulado": row['simulado_id'], "trilha": row['trilha'],
            "nome": sim.get('nome', row['simulado_id']),
            "questoes": [oli.sanitizar_questao(oli.QUESTOES[q]) for q in sim['questoes']],
            "respostas": row.get('respostas') or {}, "marcadas": row.get('marcadas') or [],
            "restante_seg": db.oli_sim_restante(row, agora),
            "duracao_seg": row['duracao_seg']}

def _oli_autoenviar(aid, row):
    """Tempo esgotado: envia com o que está salvo (auto=1) e devolve o relatório."""
    sim = oli.SIMULADOS[row['simulado_id']]
    respostas = _oli_respostas_map(row)
    anteriores = [h['nota'] for h in db.oli_simulados_do_aluno(aid) if h['trilha'] == row['trilha']]
    fim = datetime.fromisoformat(row['iniciado_ts']) + timedelta(seconds=row['duracao_seg'])
    rel = oli.montar_relatorio(sim, respostas, row['iniciado_ts'], fim.isoformat(), anteriores)
    db.oli_simulado_enviar(aid, row['id'], rel['nota'], json.dumps(rel), auto=1)
    _oli_medalhas_simulado(aid, rel)
    return {"sim_id": row['id'], "auto": True, "relatorio": rel}

def _oli_medalhas_simulado(aid, rel):
    novas = []
    m = db.medalha_conceder(aid, 'oli_simulado1')
    if m: novas.append(m)
    if rel['nota'] >= 0.8 * rel['nota_max']:
        m = db.medalha_conceder(aid, 'oli_nota_top')
        if m: novas.append(m)
    return novas

@app.get('/api/oli/estado')
def api_oli_estado(senha: str = ''):
    aid = _aluno_id(senha)
    perfil = db.oli_perfil_get(aid)
    hist = db.oli_simulados_do_aluno(aid)
    aberto = db.oli_simulado_aberto(aid)
    out = {"perfil": perfil, "trilhas": oli.TRILHA_NOMES,
           "estrategias": _oli_estrategias_pub(),
           "simulados_hist": hist,
           "simulado_aberto": ({"sim_id": aberto['id'], "simulado": aberto['simulado_id'],
                                "restante_seg": db.oli_sim_restante(aberto)} if aberto else None)}
    if perfil and perfil.get('trilha'):
        t = perfil['trilha']
        out["trilha_nome"] = oli.TRILHA_NOMES[t]
        out["unidades"] = oli.montar_unidades(t, db.oli_progresso_list(aid, t))
        out["simulados"] = [{"id": s['id'], "nome": s.get('nome', s['id']),
                             "n_questoes": len(s['questoes']), "duracao_seg": s['duracao_seg'],
                             "nota_max": oli.nota_maxima(s)}
                            for s in oli.SIMULADOS.values() if s['trilha'] == t]
    return JSONResponse(out)

@app.get('/api/oli/nivelamento')
def api_oli_nivelamento(senha: str = ''):
    aid = _aluno_id(senha)
    p = db.oli_perfil_get(aid)
    if p and p.get('trilha'):
        return JSONResponse(status_code=409, content={"ok": False, "ja_nivelado": True, "trilha": p['trilha']})
    return {"questoes": [oli.sanitizar_questao(oli.QUESTOES[q])
                         for q in oli.NIVELAMENTO['questoes']]}

class OliNivelamentoIn(BaseModel):
    respostas: dict = {}

@app.post('/api/oli/nivelamento')
def api_oli_nivelamento_post(payload: OliNivelamentoIn, senha: str = ''):
    aid = _aluno_id(senha)
    p = db.oli_perfil_get(aid)
    if p and p.get('trilha'):
        return JSONResponse(status_code=409, content={"ok": False, "ja_nivelado": True, "trilha": p['trilha']})
    resultado = oli.corrigir_nivelamento(payload.respostas or {})
    aluno = db.aluno_get(aid) or {}
    sugerida = oli.sugerir_trilha(aluno.get('idade', 0), resultado['por_trilha'])
    resultado['sugerida'] = sugerida
    resultado['ts'] = datetime.now().isoformat()
    db.oli_perfil_set_trilha(aid, sugerida, 'nivelamento',
                             json.dumps({**resultado, "por_trilha": {k: list(v) for k, v in resultado['por_trilha'].items()}}))
    novas = [m for m in [db.medalha_conceder(aid, 'oli_nivelado')] if m]
    return {"ok": True, "acertos": resultado['acertos'], "total": resultado['total'],
            "trilha": sugerida, "trilha_nome": oli.TRILHA_NOMES[sugerida], "novas_medalhas": novas}

@app.get('/api/oli/unidade')
def api_oli_unidade(eixo: str, senha: str = ''):
    aid = _aluno_id(senha)
    p = _oli_perfil(aid)
    if eixo not in oli.EIXO_IDS:
        raise HTTPException(404, "Eixo não encontrado")
    qs = oli.questoes_da_unidade(p['trilha'], eixo)
    prog = {r['questao_id']: r for r in db.oli_progresso_list(aid, p['trilha'])}
    questoes = []
    for q in qs:
        pr = prog.get(q['id'])
        questoes.append({**oli.sanitizar_questao(q),
                         "feita": bool(pr), "acertou": bool(pr and pr['acertou'])})
    eixo_meta = next(e for e in oli.EIXOS if e['id'] == eixo)
    estrategias = sorted({q['estrategia_alvo'] for q in qs})
    return {"eixo": eixo_meta, "trilha": p['trilha'],
            "estrategias": _oli_estrategias_pub(estrategias), "questoes": questoes}

class OliResponderIn(BaseModel):
    questao: str
    resposta: int

@app.post('/api/oli/responder')
def api_oli_responder(payload: OliResponderIn, senha: str = ''):
    aid = _aluno_id(senha)
    p = _oli_perfil(aid)
    q = oli.QUESTOES.get(payload.questao)
    if not q or q['uso'] != 'unidade' or q['trilha'] != p['trilha']:
        raise HTTPException(404, "Questão não encontrada")
    corr = oli.corrigir(payload.questao, payload.resposta)
    if corr is None:
        raise HTTPException(422, "Resposta inválida")
    reg = db.oli_registrar_resposta(aid, q['id'], q['trilha'], q['eixo'],
                                    corr['correto'], q['valor_pontos'])
    novas = _oli_medalhas_pratica(aid, p['trilha']) if corr['correto'] else []
    return {**corr, **reg, "novas_medalhas": novas}

class OliSimuladoIn(BaseModel):
    simulado: str = ''
    sim_id: int = 0

@app.post('/api/oli/simulado/iniciar')
def api_oli_sim_iniciar(payload: OliSimuladoIn, senha: str = ''):
    aid = _aluno_id(senha)
    p = _oli_perfil(aid)
    sim = oli.SIMULADOS.get(payload.simulado)
    if not sim:
        raise HTTPException(404, "Simulado não encontrado")
    if sim['trilha'] != p['trilha']:
        raise HTTPException(403, "Esse simulado é de outra trilha")
    aberto = db.oli_simulado_aberto(aid)
    if aberto and db.oli_sim_expirado(aberto):
        _oli_autoenviar(aid, aberto)          # fecha o esquecido e segue
        aberto = None
    r = db.oli_simulado_iniciar(aid, sim['id'], sim['trilha'], sim['duracao_seg'])
    if r.get('erro') == 'outro_aberto':
        return JSONResponse(status_code=409, content={"ok": False, "erro": "Você já tem um simulado em andamento.",
                                                      "simulado": r['aberto']['simulado_id']})
    return _oli_sim_pub(r)

@app.get('/api/oli/simulado/atual')
def api_oli_sim_atual(senha: str = ''):
    aid = _aluno_id(senha)
    aberto = db.oli_simulado_aberto(aid)
    if not aberto:
        raise HTTPException(404, "Nenhum simulado em andamento")
    if db.oli_sim_expirado(aberto):
        return JSONResponse({"expirado": True, "resultado": _oli_autoenviar(aid, aberto)})
    return _oli_sim_pub(aberto)

class OliSalvarIn(BaseModel):
    sim_id: int
    questao: str = ''
    resposta: object = None
    branco: bool = False
    limpar: bool = False
    marcadas: list = None

@app.post('/api/oli/simulado/salvar')
def api_oli_sim_salvar(payload: OliSalvarIn, senha: str = ''):
    aid = _aluno_id(senha)
    resposta = payload.resposta
    if resposta is not None:
        try:
            resposta = int(resposta)
        except (TypeError, ValueError):
            raise HTTPException(422, "Resposta inválida")
        if not (0 <= resposta <= 4):
            raise HTTPException(422, "Resposta inválida")
    r = db.oli_simulado_salvar(aid, payload.sim_id, payload.questao or None, resposta,
                               payload.branco, payload.limpar, payload.marcadas)
    if r.get('erro') == 'nao_encontrado':
        raise HTTPException(404, "Simulado não encontrado")
    if r.get('erro') == 'ja_enviado':
        return JSONResponse(status_code=409, content={"ok": False, "ja_enviado": True})
    if r.get('expirado'):
        row = db.oli_simulado_get(aid, payload.sim_id)
        return JSONResponse({"expirado": True, "resultado": _oli_autoenviar(aid, row)})
    return r

@app.post('/api/oli/simulado/enviar')
def api_oli_sim_enviar(payload: OliSimuladoIn, senha: str = ''):
    aid = _aluno_id(senha)
    row = db.oli_simulado_get(aid, payload.sim_id)
    if not row:
        raise HTTPException(404, "Simulado não encontrado")
    if row['enviado']:
        return {"ok": True, "ja_enviado": True, "relatorio": row['detalhe']}
    sim = oli.SIMULADOS[row['simulado_id']]
    anteriores = [h['nota'] for h in db.oli_simulados_do_aluno(aid) if h['trilha'] == row['trilha']]
    rel = oli.montar_relatorio(sim, _oli_respostas_map(row), row['iniciado_ts'],
                               datetime.now().isoformat(), anteriores)
    env = db.oli_simulado_enviar(aid, row['id'], rel['nota'], json.dumps(rel))
    novas = _oli_medalhas_simulado(aid, rel)
    return {"ok": True, "relatorio": rel, "novas_medalhas": novas,
            "xp_ganho": env.get('xp_ganho', 0), "moedas_ganhas": env.get('moedas_ganhas', 0),
            "saltos_ganhos": env.get('saltos_ganhos', 0)}

@app.get('/api/oli/simulado/relatorio')
def api_oli_sim_relatorio(id: int, senha: str = ''):
    aid = _aluno_id(senha)
    row = db.oli_simulado_get(aid, id)
    if not row or not row['enviado']:
        raise HTTPException(404, "Relatório não encontrado")
    return {"sim_id": row['id'], "simulado": row['simulado_id'], "trilha": row['trilha'],
            "enviado_ts": row['enviado_ts'], "auto": bool(row['auto']), "relatorio": row['detalhe']}

@app.get('/api/pais/oli')
def api_pais_oli(senha: str = '', aluno: int = 0):
    p, aid = _pai_aluno(senha, aluno)
    perfil = db.oli_perfil_get(aid)
    nivelamento = None
    if perfil and perfil.get('nivelamento_json'):
        try:
            nivelamento = json.loads(perfil['nivelamento_json'])
        except ValueError:
            nivelamento = None
    unidades = (oli.montar_unidades(perfil['trilha'], db.oli_progresso_list(aid, perfil['trilha']))
                if perfil and perfil.get('trilha') else [])
    return {"perfil": perfil, "trilhas": oli.TRILHA_NOMES, "nivelamento": nivelamento,
            "unidades": unidades, "simulados": db.oli_simulados_do_aluno(aid)}

class OliTrilhaIn(BaseModel):
    aluno: int = 0
    trilha: str = ''

@app.post('/api/pais/oli/trilha')
def api_pais_oli_trilha(payload: OliTrilhaIn, senha: str = ''):
    p, aid = _pai_aluno(senha, payload.aluno)
    if payload.trilha not in oli.TRILHAS:
        raise HTTPException(422, "Trilha inválida")
    perfil = db.oli_perfil_set_trilha(aid, payload.trilha, 'pais')
    return {"ok": True, "perfil": perfil}

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
