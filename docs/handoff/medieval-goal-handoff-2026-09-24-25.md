# Handoff — trabalho do goal de conclusão medieval

**Período coberto:** 24–25/09/2026

**Objetivo ativo:** implementar o plano de conclusão do Medieval World Simulator; Industrial Warfare explicitamente fora do escopo.

**Estado:** pausado no checkpoint do smoke seed 73/dia 1.560. O goal não está concluído.

Este handoff registra o trabalho feito durante este goal, os resultados observados e, igualmente importante, o que não foi fechado. Ele não declara que todo o roadmap está implementado.

## Resumo honesto

Houve trabalho material em quatro frentes: autoria causal dos owners, composição de campanha com alterações ambientais, diagnóstico/observabilidade econômica e atomicidade de executores. A principal prova de runtime atual é um smoke offline da seed 73 até o dia 1.560, não o gate final de dez anos.

Há também risco real de fragmentação: vários owners foram fortalecidos um a um, mas a auditoria transversal ainda não acabou; a projeção de acesso alimentar melhora o diagnóstico do Dao, mas não resolve a economia nem cria novas decisões para NPCs. Parte considerável do tempo recente foi execução e auditoria do smoke longo, não implementação de uma nova vertical de gameplay.

Não existe snapshot Git limpo do início deste goal. O checkout já continha WIP amplo. Portanto, o diff atual (238 arquivos rastreados modificados, cerca de 15.982 inserções e 1.432 remoções, além de arquivos novos) **não pode ser atribuído integralmente a este goal**. O número descreve o worktree atual, não uma medida confiável do que foi escrito neste período.

## O que foi implementado ou reforçado

### 1. Autoria, decisões e evidência material

Vários caminhos de decisão/executor agora preservam a decisão do ator até o receipt material, recompõem opções atuais e rejeitam seleção copiada, obsoleta ou sem autoria sem mutação. Os recortes documentados incluem ajuda e alívio, compromissos e transferências, compras domésticas, emprego/workforce, prioridades produtivas, pesquisa e difusão de técnica, suborno, mobilização/comando, viagem, manutenção/reparo, controle territorial, movimentos cívicos e certas respostas de criatura.

O auditor causal também valida com mais rigor decisões-fonte, temporalidade, receipts de provider, roots de bootstrap e existência das entidades referenciadas. A Crônica distingue premissa de geração do mundo de ausência inexplicada de causa.

**Limite:** isto cobre owners e eventos exercitados, não todo caminho material do jogo. A matriz ainda classifica a auditoria transversal como incompleta. Os testes negativos são importantes, mas não provam por si sós o inventário inteiro.

### 2. Ambiente, infraestrutura e campanha

Foi observada numa trajetória natural da seed 14 a sequência enchente/overflow → dano de instalação → capacidade de rota reduzida → leitura local do mantenedor → affordance e escolha offline explícita de reparo → consumo de materiais/trabalho → rota recuperada. A reparação não é inferida de proximidade nem de texto narrativo.

Também foram reforçados os elos logísticos de campanha: decisões de suprimento atribuídas ao titular do QG, uso de relatórios próprios de rota, aviso por frete atrasado, revisão posterior e opção de retirada revalidada pelo owner. Fixtures compostas provam partes dessa cadeia, inclusive capacidade física compartilhada e carga em trânsito.

**Limite:** a coluna/campanha não surgiu espontaneamente de uma cadeia política natural completa. As composições mais longas usam fixtures e escolhas por stub; não provam uma sequência rei → QG → general com conflito e transmissão real de ordens.

### 3. Diagnóstico e observabilidade econômica

O smoke passou a registrar leituras mensais de liquidez da folha por conta empregadora: saldo, folha efetivamente paga, limites de payroll e instalações bloqueadas por caixa. Isso permite separar teto de contrato de despesa realizada.

Foi implementada uma projeção somente leitura de acesso alimentar público, compartilhada entre smoke, API `/api/v2` e painel Finanças. Ela expõe estoque/preço, dinheiro agregado por ocupação, estimativa de rações que as coortes disponíveis não poderiam pagar e eventos-fonte consultáveis. A projeção é do observador onisciente: não cria falta canônica, não altera saldos e não é entregue aos NPCs como conhecimento.

Uma inspeção do save do dia 1.200 encontrou, em Campomanso, 464 rações faltantes mesmo com 2.115 no estoque público; os saldos estavam concentrados em algumas coortes agrícolas e quase ausentes entre artesãos. Isso motivou diagnóstico, não redistribuição automática de renda/alimento.

**Limite:** não foi corrigido o quadro de resiliência econômica. Nenhuma prosperidade, renda ou recuperação foi garantida. O offline `routine-rules` não permite concluir o que um provider real escolheria.

### 4. Atomicidade e rollback local de owners

Foram fechados recortes transacionais com regressões de falha injetada: distribuição pública de alívio, recuperação de frete, reativação e autorização de reparo de infraestrutura, início de construção/expansão/fundação, progresso mensal de obras, divulgação de conhecimento, provisões agregadas de coortes e alteração do serviço de rota. Nos recortes cobertos, uma exceção antes da publicação deixa o snapshot original intacto.

**Limite:** isso não comprova atomicidade de todos os executores, nem rollback integral do mês/simulação.

### 5. Evidência de simulação e docs

O checkout atual foi medido em trajetórias offline; a seed 14 chegou ao dia 1.290 em registro anterior. O smoke atual da seed 73 avançou até o checkpoint 1.560/3.600. Os saves dos dias 960, 1.200, 1.320, 1.440 e 1.560 passaram auditoria causal standalone; o checkpoint 1.560 também registrou conservação e equivalência save/load.

Roadmap, matriz de fechamento, estado atual e plano V1 separam escopo do produto, progresso, evidência e gates de implementação. Este documento complementa — não substitui — esses registros:

- [Roadmap do fork](medieval-roadmap.md)
- [Estado atual e evidências](medieval-current-state.md)
- [Matriz de fechamento](medieval-closure-matrix.md)
- [Plano operacional canônico — Medieval V1](medieval-finalization-plan.md)
- [Registro de planejamento anterior](medieval-closure-plan.md)
- [Registro de trabalho histórico](../../medieval-finalization-next-plan.md)

## Smoke pausado: resultado e significado

Comando executado em modo offline, sem provider real, com checkpoints de 120 dias:

```bash
CWS_DATA_DIR=/tmp/cws-medieval-final-seed73-current-data \
  ./.venv/bin/python tools/medieval_autonomy_smoke.py \
  --seed 73 --days 3600 \
  --output /tmp/cws-medieval-final-seed73-3600-current-20260925.mws \
  --checkpoint-days 120 \
  --progress-jsonl /tmp/cws-medieval-final-seed73-3600-current-20260925.jsonl
```

O processo foi encerrado depois que o checkpoint do dia 1.560 foi gravado, conforme pedido do usuário. Save:
`/tmp/cws-medieval-final-seed73-3600-current-20260925.checkpoint-day-01560.mws`.

No ciclo do dia 1.560: 65.130 eventos, 49.946 transições materiais, falta alimentar 758, saúde média 276,38, unrest 411,25 e 361 mortes acumuladas por privação. O checkpoint registrou conservação e save/load equivalentes. A auditoria causal standalone dos checkpoints 960/1.200/1.320/1.440/1.560 encontrou zero causas quebradas, erros de autoria/fonte, roots inválidas/ausentes, eventos Story materiais ou interpretações materiais.

**Interpretação:** a integridade causal passou nos saves amostrados; a resiliência econômica falhou fortemente. Isso não prova que todos os owners estejam corretos nem que a economia não possa se recuperar com decisões válidas. O run não terminou os 3.600 dias e não é gate final.

## O que não foi feito

- Não foi concluído o inventário causal/autoria de todos os owners.
- Não foram concluídas três seeds naturais de 3.600 dias no checkout atual; apenas a seed 73 chegou a 1.560 e foi pausada.
- Não houve validação provider-real representativa no smoke atual; decisões `routine-rules` são fallback offline.
- Não foi resolvida a crise econômica observada, nem adicionados subsídios, transferências automáticas ou cotas de recuperação.
- Não foi demonstrada uma campanha natural multissistema com rei, QG, comandante, ambiente, comércio e população reagindo simultaneamente.
- Não foram fechadas todas as lacunas de tecnologia/difusão, magia, criaturas e conflito social do roadmap.
- Não foi feita auditoria integral de rollback mensal, gate completo de escala ou navegação humana de todas as cadeias na UI.
- Industrial Warfare, torneios e novas verticais laterais não foram trabalhados.
- Nada neste checkpoint foi commitado, enviado ao remoto ou deployado. HEAD permanece `51c213df`; há WIP local amplo.

## Auditoria de fidelidade ao plano

**Alinhado ao plano:** reforçar autoria causal, conectar condição ambiental a consequência física e ao decisor, distinguir observação do jogador de conhecimento dos atores, medir economia antes de alterar regras e executar o gate longo no checkout atual.

**Risco de ter fugido para arestas:** a sequência de correções de atomicidade/autoria em owners isolados pode virar uma coleção interminável de recortes se não for encerrada por uma auditoria com cobertura explícita. A projeção de comida é observabilidade, não gameplay. O smoke de longa duração trouxe evidência útil, mas também consumiu uma fração grande do trabalho sem fechar o gate solicitado.

**Conclusão honesta:** houve avanço real na fundação e em provas compostas, porém o objetivo de “terminar o principal” permanece aberto. A próxima etapa não deve abrir feature lateral: deve usar o checkpoint já salvo para retomar/verificar o gate, encerrar uma fatia transversal da auditoria de owners e decidir a correção econômica somente após traçar caixa → folha → produção → compra/falta em registros concretos.
