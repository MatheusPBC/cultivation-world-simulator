# Handoff — Cultivation World causal

Este pacote permite continuar o fork em outra máquina, sessão ou equipe sem depender do histórico do chat.

Snapshot documental: **12/09/2026**, código-base **`896c0359`**, branch `main`. Este pacote não muda a simulação nem comprova o estado atual da VPS.

## Ordem de leitura

1. [Guia do projeto](projeto.md): visão, arquitetura, mapa do código, execução e operação segura.
2. [Plano principal congelado](plano-principal.md): requisitos e sequência aprovada, não uma declaração de conclusão.
3. [Estado e pendências](estado-e-pendencias.md): cobertura, limitações, evidências e próxima sequência recomendada.
4. [AGENTS.md](../../AGENTS.md): regras locais obrigatórias antes de implementar.

## Fontes e precedência

O [plano arquitetural original](../specs/actor-driven-emergent-world.md) continua sendo a referência normativa. O plano em português deste pacote o consolida para transferência de contexto; não cria um Plano 6 nem amplia o escopo.

O [CONTEXT.md](../../CONTEXT.md) contém vocabulário e um histórico detalhado de checkpoints. Há passagens antigas sobre WIP, deploy e schemas que foram superadas. Não leia cada parágrafo como estado simultaneamente atual. Código, testes executados na revisão em trabalho e inspeção do runtime prevalecem sobre registros antigos.

## Texto para iniciar uma nova sessão

> Trabalhe neste fork do Cultivation World. Leia AGENTS.md e docs/handoff/README.md, projeto.md, plano-principal.md e estado-e-pendencias.md. Confira git status e a revisão antes de agir. Preserve WIP e dados reais. A arquitetura está congelada: estado canônico → affordance → decisão independente → owner → fatos/deltas → memória. Comece pelas pendências prioritárias, sem inventar drama ou abrir sistemas extras. Distinga evidência histórica de validação atual. Nenhum commit, push ou deploy futuro está autorizado apenas por este handoff; confirme o escopo do pedido atual.
