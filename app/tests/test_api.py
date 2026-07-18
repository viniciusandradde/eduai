#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Endpoints /api/oli/*: auth, sanitização de gabarito e fluxo E2E."""
import json

import olimpiadas as oli


def _sem_segredos(payload):
    txt = json.dumps(payload, ensure_ascii=False)
    for campo in ('"gabarito"', '"solucao_passo_a_passo"', '"distratores_explicados"'):
        assert campo not in txt, f"vazou {campo}"


def _nivelar(client, tok, acertar_tudo=True):
    r = client.get('/api/oli/nivelamento', params={'senha': tok})
    assert r.status_code == 200
    respostas = {}
    for q in r.json()['questoes']:
        g = oli.QUESTOES[q['id']]['gabarito']
        respostas[q['id']] = g if acertar_tudo else (g + 1) % 5
    r = client.post('/api/oli/nivelamento', params={'senha': tok}, json={'respostas': respostas})
    assert r.status_code == 200
    return r.json()


def test_sem_token_401(client):
    for rota in ('/api/oli/estado', '/api/oli/nivelamento', '/api/oli/simulado/atual'):
        assert client.get(rota, params={'senha': 'token-falso'}).status_code == 401


def test_nivelamento_sanitizado_e_sugestao(client, novo_aluno):
    u = novo_aluno(idade=10)
    tok = u['tok_aluno']
    r = client.get('/api/oli/nivelamento', params={'senha': tok})
    body = r.json()
    assert len(body['questoes']) == 12
    _sem_segredos(body)
    res = _nivelar(client, tok, acertar_tudo=True)
    assert res['acertos'] == 12 and res['trilha'] == 'B'      # 10 anos, gabaritou o bloco B → sobe
    assert any(m['codigo'] == 'oli_nivelado' for m in res['novas_medalhas'])
    r = client.get('/api/oli/nivelamento', params={'senha': tok})
    assert r.status_code == 409 and r.json()['ja_nivelado']


def test_unidade_player_e_pratica(client, novo_aluno):
    u = novo_aluno(idade=8)
    tok = u['tok_aluno']
    assert client.get('/api/oli/unidade', params={'senha': tok, 'eixo': 'numeros'}).status_code == 409
    res = _nivelar(client, tok, acertar_tudo=False)           # 8 anos errando tudo → P
    assert res['trilha'] == 'P'
    r = client.get('/api/oli/unidade', params={'senha': tok, 'eixo': 'numeros'})
    body = r.json()
    assert len(body['questoes']) == 6
    assert [q['valor_pontos'] for q in body['questoes']] == [3, 3, 4, 4, 5, 5]
    assert body['estrategias'] and all(e['aula'] for e in body['estrategias'])
    _sem_segredos(body)

    qid = body['questoes'][0]['id']
    q = oli.QUESTOES[qid]
    errada = (q['gabarito'] + 1) % 5
    r = client.post('/api/oli/responder', params={'senha': tok},
                    json={'questao': qid, 'resposta': errada}).json()
    assert not r['correto'] and r['distrator_explicado'] and r['solucao']
    assert r['xp_ganho'] == 0
    r = client.post('/api/oli/responder', params={'senha': tok},
                    json={'questao': qid, 'resposta': q['gabarito']}).json()
    assert r['correto'] and r['primeira_vez_certa'] and r['saltos_ganhos'] == q['valor_pontos']
    # questão de simulado não pode ser praticada
    qsim = next(x for x in oli.QUESTOES.values() if x['trilha'] == 'P' and x['uso'] == 'simulado')
    assert client.post('/api/oli/responder', params={'senha': tok},
                       json={'questao': qsim['id'], 'resposta': 0}).status_code == 404


def test_simulado_e2e(client, novo_aluno):
    u = novo_aluno(idade=10)
    tok = u['tok_aluno']
    _nivelar(client, tok, acertar_tudo=False)                 # fica na E
    r = client.post('/api/oli/simulado/iniciar', params={'senha': tok}, json={'simulado': 'sim_e_1'})
    body = r.json()
    assert r.status_code == 200 and len(body['questoes']) == 24
    assert body['restante_seg'] == 6000
    _sem_segredos(body)
    sim_id = body['sim_id']
    # simulado de outra trilha é bloqueado
    assert client.post('/api/oli/simulado/iniciar', params={'senha': tok},
                       json={'simulado': 'sim_b_1'}).status_code == 403

    ids = [q['id'] for q in body['questoes']]
    # 3 acertos, 2 erros, 1 branco explícito, resto sem visitar
    def responder(qid, r_):
        rr = client.post('/api/oli/simulado/salvar', params={'senha': tok},
                         json={'sim_id': sim_id, 'questao': qid, 'resposta': r_})
        assert rr.json().get('ok')
    for qid in ids[:3]:
        responder(qid, oli.QUESTOES[qid]['gabarito'])
    for qid in ids[3:5]:
        responder(qid, (oli.QUESTOES[qid]['gabarito'] + 1) % 5)
    rr = client.post('/api/oli/simulado/salvar', params={'senha': tok},
                     json={'sim_id': sim_id, 'questao': ids[5], 'branco': True, 'marcadas': [ids[7]]})
    assert rr.json().get('ok')

    # retomada (queda de conexão): estado preservado
    r = client.get('/api/oli/simulado/atual', params={'senha': tok}).json()
    assert r['sim_id'] == sim_id and r['marcadas'] == [ids[7]]
    assert r['respostas'][ids[5]]['branco'] == 1 and len(r['respostas']) == 6
    _sem_segredos(r)

    r = client.post('/api/oli/simulado/enviar', params={'senha': tok}, json={'sim_id': sim_id}).json()
    rel = r['relatorio']
    esperado = sum(oli.QUESTOES[q]['valor_pontos'] for q in ids[:3]) \
        - 0.25 * sum(oli.QUESTOES[q]['valor_pontos'] for q in ids[3:5]) + 24
    assert rel['nota'] == round(esperado, 2)
    assert rel['acertos'] == 3 and rel['chutes'] == 2 and rel['brancos'] == 19
    assert any(m['codigo'] == 'oli_simulado1' for m in r['novas_medalhas'])
    assert r['moedas_ganhas'] == 30

    r2 = client.post('/api/oli/simulado/enviar', params={'senha': tok}, json={'sim_id': sim_id}).json()
    assert r2['ja_enviado']
    r = client.get('/api/oli/simulado/relatorio', params={'senha': tok, 'id': sim_id}).json()
    assert r['relatorio']['nota'] == rel['nota']
    # pós-envio o relatório traz solução para revisar erros
    assert all(d['solucao'] for d in r['relatorio']['questoes'])

    est = client.get('/api/oli/estado', params={'senha': tok}).json()
    assert est['simulado_aberto'] is None
    assert est['simulados_hist'][-1]['nota'] == rel['nota']
    assert est['perfil']['saltos'] > 0


def test_pais_ve_e_ajusta_trilha(client, novo_aluno):
    u = novo_aluno(idade=11)
    tok_a, tok_p = u['tok_aluno'], u['tok_pai']
    _nivelar(client, tok_a, acertar_tudo=False)
    aid = u['aluno']['id']
    r = client.get('/api/pais/oli', params={'senha': tok_p, 'aluno': aid}).json()
    assert r['perfil']['trilha'] == 'E' and r['nivelamento']['acertos'] == 0
    # outro pai não acessa
    outro = novo_aluno()
    assert client.get('/api/pais/oli', params={'senha': outro['tok_pai'], 'aluno': aid}).status_code == 403
    # ajuste de trilha pelos pais
    r = client.post('/api/pais/oli/trilha', params={'senha': tok_p},
                    json={'aluno': aid, 'trilha': 'P'}).json()
    assert r['perfil']['trilha'] == 'P' and r['perfil']['origem'] == 'pais'
    est = client.get('/api/oli/estado', params={'senha': tok_a}).json()
    assert est['perfil']['trilha'] == 'P'
    assert client.post('/api/pais/oli/trilha', params={'senha': tok_p},
                       json={'aluno': aid, 'trilha': 'X'}).status_code == 422
