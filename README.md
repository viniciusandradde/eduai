<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:7c3aed,100:2563eb&height=200&section=header&text=VSA%20EduAI&fontSize=64&fontColor=ffffff&desc=leia%20•%20aprenda%20•%20evolua&descSize=20&descAlignY=72" alt="VSA EduAI" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/lema-leitura%20📖-7c3aed?style=for-the-badge" />
  <img src="https://img.shields.io/badge/gamificado-XP%20•%20medalhas%20•%20streak-f5b301?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PWA-instal%C3%A1vel%20no%20Android-2563eb?style=for-the-badge" />
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

A **VSA EduAI** transforma o estudo das matérias da escola em uma **aventura gamificada**.
O aluno cumpre **missões**, ganha **XP, níveis, medalhas, moedas e streak** e troca recompensas
na **loja** (itens de avatar + tempo de Minecraft).

Mas a **regra de ouro nunca muda**:

> 🔑 **Nenhuma missão se conclui sem a LEITURA.**
> Depois dos exercícios, o aluno precisa **ler e registrar** (resumo escrito **ou** foto do
> resumo no papel) antes de avançar. A leitura é o coração do projeto.

Não é app de "passar o tempo": é um **convite ao crescimento** disfarçado de jogo — feito por
um pai que acredita que quem aprende e lê todos os dias nunca para de evoluir.

---

## 🧩 Módulos (Fase 1)

| | Módulo | O que tem |
|:--:|:--|:--|
| 🔢 | **Matemática** | Frações, porcentagem, equações do 1º grau |
| 📖 | **Português** | Interpretação de texto, ortografia, classes de palavras |
| 🔬 | **Ciências** | Corpo humano, ecossistemas, matéria e energia |
| 💻 | **Programação** | Lógica/algoritmos + abre a **Quest Linux** (terminal) |
| 👨‍👩‍👦 | **Painel dos Pais** | Acompanha progresso, XP, streak, leituras, medalhas e **aprova recompensas** |

Nível inicial: **Fundamental II (6º–9º ano)**.

---

## 🎮 Como funciona (o loop)

```
Escolhe a matéria  →  faz a missão (exercícios, correção na hora)
        ↓
   ganha ⭐ estrelas + XP
        ↓
   📖 LEITURA obrigatória (resumo ou foto)  ←  só aqui a missão CONCLUI
        ↓
   sobe de nível • ganha medalhas • moedas → loja 🛒
```

- **Correção no servidor:** o gabarito **nunca** é enviado ao navegador (sem "ver o código").
- **Estrelas:** 1⭐ (≥40%), 2⭐ (≥70%), 3⭐ (≥90%). Precisa de pelo menos 1⭐ para ir à leitura.
- **Streak:** sequência de dias estudando. **Medalhas:** primeiros passos, nota máxima, leitor,
  sequência de 3 dias, nível 5, e mais.

---

## 🏆 Gamificação

- **XP & Níveis** — cada exercício e cada leitura dá XP; sobe de nível automaticamente.
- **Medalhas (badges)** — conquistas por marcos.
- **Streak 🔥** — dias seguidos de estudo.
- **Moedas 🪙 & Loja 🛒** — itens de avatar (cosméticos) e **tempo de Minecraft**
  (vira um *pedido* que o pai aprova no painel).
- **Avatar** — identidade do explorador (evolui na Fase 2).

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
   ├─ Dockerfile
   ├─ requirements.txt
   └─ static/                # hub do aluno + painel dos pais (PWA)
      ├─ index.html / app.js     # hub + motor de exercícios + loja
      ├─ pais.html / pais.js     # painel dos pais
      ├─ style.css
      └─ manifest.webmanifest / sw.js / icon-*.png
```

- **Backend:** FastAPI (Python 3.11). **Dados:** SQLite (WAL) em `/data/escola.db`.
- **Frontend:** HTML/CSS/JS puro (sem frameworks), **mobile-first** e **PWA** (instalável).
- **Conteúdo:** orientado a dados (JSON) — o motor renderiza/corrige; fácil de expandir.
- **Deploy:** Docker Compose atrás do **Traefik** (Let's Encrypt), pronto para **Dokploy**.

### O contrato de dados (SQLite `/data/escola.db`)
| Tabela | Para quê |
|---|---|
| `aluno` | nome, avatar, XP, nível, moedas, streak |
| `tentativa` | cada resolução de missão (acertos, estrelas, XP, tempo) |
| `progresso` | por missão: melhor estrela, concluída, **leitura_ok** |
| `medalha` | medalhas conquistadas |
| `compra` | itens/recompensas da loja (status `pendente`/`aprovado`) |

---

## 🚀 Rodar

```bash
git clone https://github.com/viniciusandradde/eduai.git
cd eduai
cp .env.example .env        # ajuste senhas e domínio
docker compose up -d --build
```

| Acesso | URL |
|---|---|
| 🧒 Aluno | `https://ESCOLA_DOMAIN/` |
| 👨‍👩‍👦 Pais | `https://ESCOLA_DOMAIN/pais` |

> Local (sem Traefik): exponha a porta do serviço e acesse `http://localhost:8080`.

### Variáveis (`.env`)
| Variável | Padrão | Descrição |
|---|---|---|
| `ESCOLA_DOMAIN` | `escola.vsanexus.com` | Domínio (Traefik/HTTPS) |
| `ALUNO_NOME` | `Explorador` | Nome do aluno |
| `ALUNO_SENHA` | — | Senha do hub do aluno |
| `PAI_SENHA` | — | Senha do painel dos pais |
| `TERMINAL_URL` | `https://vgtux.vsanexus.com` | Link da Quest Linux (módulo Programação) |
| `XP_POR_NIVEL` | `200` | XP necessário por nível |

---

## 📲 Instalar no celular (Android)

No Chrome: abra a URL → menu **⋮** → **Instalar app**. Abre em tela cheia, com ícone próprio.

---

## 🗺️ Roadmap

- **Fase 1 — MVP ✅** matérias + gamificação + **gate de leitura** + painel dos pais + PWA.
- **Fase 2 — IA (Claude):** 🤖 Tutor IA (explica o erro), ✍️ Português com IA (comenta o resumo),
  🧭 trilhas adaptativas, geração assistida de exercícios; avatar/loja avançados; missões diárias;
  novos tipos de exercício (arrastar, associar, ordenar).
- **Fase 3 — Escola:** História Imersiva, Física Visual, **Painel Escolar** e **multi-aluno**
  (SaaS, migração SQLite → Postgres, login de usuários).
- **Integração:** unir a recompensa com a **Quest Linux/Minecraft** (projeto VGTUX) via volume comum.

---

## 🔒 Segurança & privacidade

- Acesso por senha (aluno e pai separados); gabarito corrigido no servidor.
- Fotos do resumo ficam no volume privado; servidas só ao pai (senha + nome sanitizado).
- Projeto single-aluno (uso familiar). Multi-aluno/escola só na Fase 3.

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,100:7c3aed&height=120&section=footer&text=Bora%20aprender!&fontSize=24&fontColor=ffffff" alt="footer" />
</p>
<p align="center"><sub>VSA EduAI • feito com ❤️ por um pai, para quem aprende e lê todos os dias.</sub></p>
