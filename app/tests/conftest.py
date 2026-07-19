#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixtures da suíte. DB_PATH precisa apontar para um arquivo temporário ANTES
de importar db/app (db.DB_PATH é lido no import e app.py roda init_db() no import)."""
import os
import sys
import uuid
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['DB_PATH'] = str(Path(tempfile.mkdtemp(prefix='eduai-test-')) / 'escola.db')

import pytest


@pytest.fixture(scope='session', autouse=True)
def _init_db():
    import db
    db.init_db()


@pytest.fixture(scope='session')
def client():
    from fastapi.testclient import TestClient
    import app as appmod
    return TestClient(appmod.app)


@pytest.fixture
def novo_aluno():
    """Factory: cria pai + filho novos e devolve tokens e ids."""
    import db

    def _criar(idade=10):
        suf = uuid.uuid4().hex[:8]
        assert db.criar_pai(f"Pai {suf}", f"pai-{suf}", "senha1234")["ok"]
        pai = db.pai_login(f"pai-{suf}", "senha1234")
        assert db.criar_aluno(pai["id"], f"Aluno {suf}", idade, f"aluno-{suf}", "senha1234")["ok"]
        aluno = db.aluno_login(f"aluno-{suf}", "senha1234")
        return {"pai": pai, "aluno": aluno,
                "tok_pai": db.sessao_nova('pai', pai["id"]),
                "tok_aluno": db.sessao_nova('aluno', aluno["id"])}
    return _criar
