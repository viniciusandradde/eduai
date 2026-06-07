<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:7c3aed,100:2563eb&height=190&section=header&text=VSA%20EduAI&fontSize=60&fontColor=ffffff&desc=leia%20•%20aprenda%20•%20evolua&descSize=20&descAlignY=70" alt="VSA EduAI" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/lema-leitura%20📖-7c3aed?style=for-the-badge" />
  <img src="https://img.shields.io/badge/gamificado-XP%20•%20medalhas%20•%20streak-f5b301?style=for-the-badge" />
  <img src="https://img.shields.io/badge/feito%20com-❤️%20de%20pai-ef4444?style=for-the-badge" />
</p>

<h3 align="center">📚 Plataforma de aprendizado por matérias, gamificada — com a leitura no centro de tudo.</h3>

---

## 🌟 A ideia

O filho aprende por **missões** das matérias da escola, ganha **XP, níveis, medalhas, moedas e
streak**, e troca recompensas na **loja** (itens de avatar + tempo de Minecraft). Mas a regra de
ouro nunca muda: **nenhuma missão se conclui sem a LEITURA** — ler e registrar (resumo ou foto)
antes de avançar.

## 🧩 Módulos (Fase 1)
🔢 Matemática · 📖 Português · 🔬 Ciências · 💻 Programação (abre a quest Linux).
👨‍👩‍👦 **Painel dos Pais** acompanha tudo: progresso, XP, streak, leituras, medalhas e
**aprova os pedidos de recompensa**.

## 🎮 Como funciona
1. Abra o app no navegador (PWA — instalável no Android), digite a senha.
2. Escolha a matéria → a missão → responda os exercícios (correção na hora).
3. **Faça a leitura** e registre (resumo ou foto) — só então a missão conclui.
4. Ganhe XP/medalhas, suba de nível e gaste moedas na loja. 🏅

## 🚀 Rodar
```bash
cp .env.example .env      # ajuste senhas e domínio
docker compose up -d --build
```
Aluno: `https://ESCOLA_DOMAIN` · Pais: `https://ESCOLA_DOMAIN/pais`

## 🗺️ Próximas fases
- **Fase 2 — IA (Claude):** Tutor IA, Português com IA (comenta o resumo), trilhas adaptativas,
  geração assistida de exercícios; avatar/loja avançados; missões diárias; mais tipos de exercício.
- **Fase 3 — Escola:** História e Física, Painel Escolar, multi-aluno (SaaS, Postgres).
- **Integração:** unir a recompensa com a quest Linux/Minecraft do projeto VGTUX (volume comum).

<p align="center"><sub>VSA EduAI • feito com ❤️ por um pai, para quem aprende todos os dias.</sub></p>
