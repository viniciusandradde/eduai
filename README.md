<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:7c3aed,100:2563eb&height=200&section=header&text=VSA%20EduAI&fontSize=64&fontColor=ffffff&desc=leia%20•%20aprenda%20•%20evolua&descSize=20&descAlignY=72" alt="VSA EduAI" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/lema-leitura%20📖-7c3aed?style=for-the-badge" />
  <img src="https://img.shields.io/badge/gamificado-XP•medalhas•streak•loja-f5b301?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PWA-responsivo%20•%20instalável-2563eb?style=for-the-badge" />
  <img src="https://img.shields.io/badge/feito%20com-❤️%20de%20pai-ef4444?style=for-the-badge" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Traefik-HTTPS-24A1C1?logo=traefikproxy&logoColor=white" />
</p>

<h3 align="center">📚 Plataforma de aprendizado por matérias, gamificada — com a leitura no centro de tudo.</h3>

---

## 🌟 A ideia

A **VSA EduAI** transforma o estudo das matérias da escola em uma **aventura gamificada**:
o aluno cumpre **missões**, ganha **XP, níveis, medalhas, moedas e streak**, e troca recompensas
na **loja** (itens de avatar + tempo de Minecraft). Mas a **regra de ouro nunca muda**:

> 🔑 **Nenhuma missão se conclui sem a LEITURA.**
> Depois dos exercícios, o aluno precisa **ler e registrar** (resumo escrito **ou** foto do
> resumo no papel) antes de avançar. A leitura é o coração do projeto.

🔗 **Demo:** `https://escola.vsanexus.com` · 👨‍👩‍👦 Pais: `https://escola.vsanexus.com/pais`

---

## ✨ Destaques

- 🎨 **Design hi-fi** (estilo "Lovable"): gradiente roxo, cards largos, fonte *Plus Jakarta Sans*,
  avatar com **anel de nível**, animações e *game-feel*.
- 📱 **PWA responsivo** (mobile-first, safe-area p/ notch) — **instalável** no Android.
- 🧠 **Motor de exercícios próprio**, **uma questão por vez**, com correção e explicação na hora.
  O **gabarito fica no servidor** (`/api/corrigir`) — sem "ver a resposta no código".
- 🏆 **Gamificação completa:** XP · níveis · streak 🔥 · medalhas 🏅 · moedas 🪙 · loja 🛒.
- 👨‍👩‍👦 **Painel dos Pais:** progresso por matéria, leituras, medalhas, últimas atividades e
  **aprovação dos pedidos de recompensa**.

---

## 🧩 Módulos & conteúdo

| | Módulo | Missões (exemplos) |
|:--:|:--|:--|
| 🔢 | **Matemática** | Frações, porcentagem, equações · **5º ano:** decimais, geometria/perímetro, dinheiro e medidas |
| 📖 | **Português** | Interpretação, ortografia, classes · **5º ano:** acentuação, pontuação, sentido das palavras |
| 🔬 | **Ciências** | Corpo humano, ecossistemas, matéria · **5º ano:** nutrição/digestão, ciclo da água, materiais |
| 💻 | **Programação** | Lógica e algoritmos + abre a **Quest Linux** (terminal) |

Conteúdo **autoral em JSON**, alinhado à **BNCC** (5º ano: EF05MA / EF05LP / EF05CI).
Hoje: **~95 exercícios** (tipos: múltipla escolha, V/F, numérica, completar lacuna).

---

## 🎮 O loop

```
Escolhe a matéria → faz a missão (1 questão por vez, feedback na hora)
        ↓ ganha ⭐ estrelas + XP
   📖 LEITURA obrigatória (resumo ou foto)  ←  só aqui a missão CONCLUI
        ↓ sobe de nível • ganha medalhas • moedas → loja 🛒
```

- **Estrelas:** 1⭐ (≥40%) · 2⭐ (≥70%) · 3⭐ (≥90%). Precisa de 1⭐ para ir à leitura.
- **Medalhas:** primeiros passos, trio, nota máxima 💯, leitor 📚, streak 🔥, nível 5, e mais.
- **Loja:** itens de avatar (cosméticos) + **tempo de Minecraft** (vira pedido → o pai aprova).

---

## 🧱 Arquitetura

```
eduai/
├─ docker-compose.yml        # serviço web + Traefik (HTTPS) + volume eduai-data
├─ .env.example              # senhas, domínio, link do terminal
├─ scripts/gen_icons.py      # gera os ícones do PWA (stdlib)
└─ app/
   ├─ app.py                 # FastAPI: páginas + API (correção, gamificação, gate de leitura)
   ├─ db.py                  # SQLite (aluno, tentativa, progresso, medalha, compra)
   ├─ conteudo/*.json        # conteúdo autoral por matéria (com gabarito, server-side)
   ├─ Dockerfile / requirements.txt
   └─ static/                # frontend (vanilla JS, sem build)
      ├─ index.html / app.js     # hub do aluno + motor de exercícios + loja
      ├─ pais.html / pais.js     # painel dos pais
      ├─ style.css               # design system
      └─ manifest.webmanifest / sw.js / icon-*.png
```

**Stack:** FastAPI (Python 3.11) · SQLite (WAL) em `/data/escola.db` · frontend HTML/CSS/JS puro
(PWA) · Docker Compose atrás do **Traefik** (Let's Encrypt), pronto para **Dokploy**.

### Principais endpoints
| Método | Rota | Para quê |
|---|---|---|
| GET | `/` · `/pais` | hub do aluno · painel dos pais |
| GET | `/api/conteudo` | matérias/missões **sem gabarito** |
| GET | `/api/estado` | XP, nível, streak, progresso, medalhas, loja |
| POST | `/api/corrigir` | corrige **1 questão** (gabarito no servidor) |
| POST | `/api/tentativa` | pontua a missão (XP/estrelas) |
| POST | `/api/leitura` · `/api/leitura-foto` | **gate de leitura** (resumo ou foto) |
| POST | `/api/loja/comprar` | compra item/recompensa |
| GET/POST | `/api/pais/estado` · `/api/pais/aprovar` | painel + aprovar recompensa |

---

## 🚀 Rodar

```bash
git clone https://github.com/viniciusandradde/eduai.git
cd eduai
cp .env.example .env        # ajuste senhas e domínio
docker compose up -d --build
```

| Variável | Padrão | Descrição |
|---|---|---|
| `ESCOLA_DOMAIN` | `escola.vsanexus.com` | Domínio (Traefik/HTTPS) |
| `ALUNO_NOME` | `Explorador` | Nome do aluno |
| `ALUNO_SENHA` / `PAI_SENHA` | — | Senhas do hub / do painel |
| `TERMINAL_URL` | `https://vgtux.vsanexus.com` | Link da Quest Linux |
| `XP_POR_NIVEL` | `200` | XP por nível |

📲 **Instalar no Android:** abra a URL no Chrome → menu **⋮** → **Instalar app**.

---

## 🗺️ Roadmap

- **Fase 1 — MVP ✅** matérias + gamificação + **gate de leitura** + painel dos pais + PWA responsivo + design hi-fi.
- **Fase 2 — IA (Claude):** 🤖 Tutor IA (explica o erro), ✍️ Português com IA (comenta o resumo),
  🧭 trilhas adaptativas, geração assistida de exercícios; missões diárias; novos tipos de exercício.
- **Fase 3 — Escola:** História e Física, **Painel Escolar**, **multi-aluno** (SaaS, Postgres, login).
- **Integração:** unir a recompensa com a **Quest Linux/Minecraft** (projeto VGTUX) via volume comum.

---

## 🔒 Segurança & privacidade

- Acesso por senha (aluno e pai separados); **gabarito corrigido no servidor**.
- Fotos do resumo ficam no volume privado; servidas só ao pai (senha + nome sanitizado).
- Projeto single-aluno (uso familiar). Multi-aluno/escola só na Fase 3.

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,100:7c3aed&height=120&section=footer&text=Bora%20aprender!&fontSize=24&fontColor=ffffff" alt="footer" />
</p>
<p align="center"><sub>VSA EduAI • feito com ❤️ por um pai, para quem aprende e lê todos os dias.</sub></p>
