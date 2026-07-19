# Banco autoral — Olimpíadas de Matemática (estilo Canguru)

Conteúdo **100% autoral** (nenhuma questão copiada de provas oficiais; a marca
"Canguru" não aparece em nome comercial). Os gabaritos ficam apenas no servidor —
`app.py` sempre envia questões via `olimpiadas.sanitizar_questao()`.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `trilha_p.json` / `trilha_e.json` / `trilha_b.json` | Questões das trilhas P (3º/4º ano), E (5º/6º) e B (7º/8º) |
| `simulados.json` | Definições dos simulados (ids de questões, ajuste +24/+30, duração) |
| `estrategias.json` | Micro-aulas das 7 estratégias de resolução |
| `nivelamento.json` | 12 questões do diagnóstico (4 por trilha) + regra de idade |

## Schema da questão

```json
{"id": "p-num-u01", "trilha": "P", "eixo": "numeros", "valor_pontos": 3,
 "uso": "unidade",
 "enunciado": "...", "alternativas": ["a","b","c","d","e"], "gabarito": 2,
 "solucao_passo_a_passo": "1) ... 2) ...",
 "distratores_explicados": {"0": "...", "1": "...", "3": "...", "4": "..."},
 "estrategia_alvo": "desenhar", "habilidade_bncc": "EF04MA11"}
```

- `eixo`: `numeros` | `geometria` | `logica` | `contagem`.
- `uso`: `unidade` (prática na trilha) | `simulado` | `nivelamento` — sem vazamento
  entre usos (questão de simulado nunca aparece na prática).
- `distratores_explicados`: exatamente os 4 índices errados, em string.

## Guia de estilo

- **Lúdico e visual**: personagens (o canguru Salto 🦘 e amigos), situações
  concretas, "desenho" em texto/emoji quando ajudar. Zero fórmula decorada —
  a filosofia da prova é raciocínio.
- **Distratores honestos**: cada alternativa errada corresponde a um erro real
  (parou um passo antes, somou em vez de multiplicar, esqueceu um caso, inverteu
  a ordem, leu depressa) e a explicação diz isso em tom acolhedor: "você
  provavelmente...".
- **Solução ensina a estratégia**: 2–4 passos numerados usando a
  `estrategia_alvo` da questão.
- **Dificuldade espelha a prova**: 3 pts direto (1 ideia), 4 pts intermediário
  (2 ideias encadeadas), 5 pts desafio (precisa de insight).
- **Linguagem por faixa**: P = frases curtas, números pequenos; E = vocabulário
  do 5º/6º ano; B = pode usar negativos, frações, porcentagem, potências.

## Validação

Toda alteração passa por `pytest tests/test_banco.py` (5 alternativas, gabarito
único 0–4, distratores completos, composição oficial dos simulados 8+8+8 /
10+10+10, ajuste +24/+30, sem ids/enunciados duplicados). O servidor valida o
banco no boot e não sobe com conteúdo inconsistente.
