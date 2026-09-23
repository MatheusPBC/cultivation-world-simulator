# Handoff completo — Medieval World Simulator / Cultivation World Causal Kernel

> Documento de transferência para revisão externa. Atualizado em 2026-09-23
> (America/Sao_Paulo). Este arquivo foi escrito no próprio repositório; não foi
> publicado no ai-memory.

## 📌 Current State

- **Active Task:** concluir o plano principal do fork medieval com
  `$task-orchestration` e MetaGame/Laya apenas em shadow mode; este checkpoint
  entrega ao revisor o histórico desde o início desse goal até E156.
- **Last Agent:** Codex (`/root`).
- **Timestamp:** 2026-09-23T08:47:24-03:00.
- **Status:** `review-needed` para este documento; pausa do goal solicitada
  pelo usuário após E156, sem concluir nem descartar o WIP.
- **Branch:** `codex/medieval-remote`.
- **HEAD verificado:** `a244e4cd` — `docs(medieval): registra progresso do roadmap e handoff`.
- **Tracking:** `github-personal/codex/medieval-remote`.
- **Remote de deploy histórico:** `origin` aponta para o checkout da VPS
  (`root@100.101.254.17:/opt/cultivation-world/app`). Isso não significa que o
  estado atual foi enviado ou implantado.
- **Git atual:** `git status --short` mostrou 235 entradas em 23/09; há WIP
  anterior e atual misturado. Nenhuma mudança do goal atual foi commitada,
  enviada ao GitHub ou implantada. Não inferir o conteúdo remoto do HEAD local.

## 🎯 Active Task Summary

O projeto é um simulador medieval/cultivation em que o jogador é o Dao
Celestial, com visão verdadeira e completa do mundo. O mundo deve parecer vivo
porque cidades, governos, seitas, dinastias, escritórios, líderes, grupos,
criaturas e outros atores percebem condições, escolhem affordances e executam
ações materiais por meio de owners da engine. A IA interpreta e decide entre
opções enumeradas; ela nunca inventa a realidade.

O objetivo do handoff é permitir que outra IA continue sem confundir:

1. a arquitetura causal já estabelecida;
2. os recortes realmente implementados e testados;
3. os planos aprovados mas ainda não implementados;
4. o WIP local não publicado;
5. os limites e falhas que continuam abertas.

**Fronteira temporal deste handoff:** o goal atual começou em 22/09/2026; seu
registro primário é `../.agent/tasks/medieval-closure-plan/` (relativo a este
repositório) com E1–E156. As
seções de arquitetura e o bloco histórico anteriores ao goal dão contexto,
mas não significam que todo esse código tenha sido escrito desde 22/09. O
arquivo `docs/handoff/medieval-current-state.md` e a matriz de fechamento
foram atualizados durante o goal. Nenhuma tarefa foi delegada nesta retomada:
o contrato local mantém `may_delegate: false`, `may_commit: false`,
`may_push: false`, `may_deploy: false`.

Se o revisor estiver fora deste workspace, envie junto este arquivo, o
`evidence.md` e `state.md` desse registro, além de
`docs/handoff/medieval-closure-matrix.md`; tanto `.agent/HANDOFF.md` quanto
`../.agent/tasks/` estão não rastreados e não estão no GitHub. Só o link do
repositório remoto não contém este WIP.

## ✅ Regra causal central

```text
estado canônico
  → métricas, condições e fatos
  → affordances transitórias válidas
  → interpretação/contexto do ator
  → decisão por affordance_id ou NO_ACTION
  → owner revalida a decisão no estado atual
  → execução material
  → Event + StateDelta + causal links + receipts
  → conhecimento, memória, relações e futuras affordances
```

Invariantes:

- A LLM escolhe somente affordances que a engine enumerou.
- Alvos, quantidade final, custo, autoridade, resistência, leis físicas e
  deltas são calculados/revalidados pela engine e pelos owners.
- Uma interpretação narrativa ou Story nunca é causa material.
- `ACTOR_DECISION` precisa apontar para uma decisão canônica real, atual e
  pertencente ao ator correto.
- Compromisso é obrigação, não comando futuro. Um prazo vencido não move
  recursos sozinho.
- Cumprimento exige estoque, rota, autoridade, capacidade, termos atuais e
  nova decisão/execução válida.
- Affordances são transitórias e recompostas; não são persistidas.
- História factual permanece navegável mesmo quando estado atual ou memória
  ativa mudam.
- Fallback automático só existe em política explícita de `offline/test`; no
  modo IA, provider ausente, resposta inválida, orçamento esgotado ou opção
  stale deve pausar/rollback (`ProviderDecisionRequired`).

## 🧭 Visão do produto e da gameplay

O pedido original evoluiu de um mundo em que a crônica apenas resumia eventos
para um mundo explicável e administrável pelo jogador:

- A crônica mostra acontecimentos importantes em alto nível.
- Dossiers, personagens, instituições e a função `why()` devem mostrar a
  cadeia detalhada: condição → decisão → ação → owner → evidência.
- O Dao é onisciente; não é limitado pela perspectiva de um NPC.
- NPCs e instituições têm conhecimento parcial e só agem sobre fatos recebidos,
  observados ou inferidos por mecanismos válidos.
- O drama não deve ser uma quota de eventos. Intriga, religião, guerra,
  revolta, comércio, traição, criaturas e campanhas nascem de pressão,
  interesses incompatíveis, compromissos, recursos, autoridade, capacidade,
  conhecimento e decisões independentes.
- Um mundo natural estável é um resultado válido. Uma fixture pressionada deve
  produzir uma cadeia material multietapas.

Exemplos de emergência desejada:

```text
pressão urbana
  → pedido de ajuda
  → cidade/seita/governo avalia de forma independente
  → aceitação/recusa
  → compromisso
  → estoque/rota/projeto material
  → cumprimento, breach ou reparação
  → memória/reputação
  → decisões futuras
```

```text
pressão + organização + liderança + causa + oportunidade
  → tumulto/movimento/rebelião possível
```

```text
conflito de recurso ou ameaça percebida + capacidade + alvo alcançável
  → leitura de casus belli + decisão de negociar, pressionar ou lutar
```

Nada disso pode ser criado apenas pela prosa da IA.

## 🧱 Arquitetura de domínio aprovada

### Entidades

- **Instituição:** cidade, seita, dinastia, governo ou outra entidade que
  persiste através da troca de líderes.
- **Office:** cargo/órgão que possui capacidade administrativa, diplomática,
  militar, logística ou de projeto.
- **Líder atual:** Avatar com personalidade, conhecimento e influência; não é
  a própria instituição.
- **AuthorityClaim:** reivindicação concorrente de autoridade. Lifecycle e
  reconhecimento são separados.
- **InstitutionalMemory:** peso/relevância ativa de fatos; não é o sistema que
  decide quem conhece um fato.
- **Knowledge:** ownership de quem conhece determinado fato/evidência.
- **InstitutionalCommitment:** obrigação durável, preparada para múltiplos
  termos, breach, remediação e reparação.
- **DomainAffordance:** objeto transitório com ID determinístico, domínio,
  actor_ref, action_kind, alvos, parâmetros engine-owned, urgência e eventos
  motivadores.
- **DomainDecision:** decisão comum (`maintain` ou `act` com
  `selected_affordance_id`).
- **DomainAffordanceRegistry:** providers/executors coletivos registrados em
  código; não substitui o `ActionRegistry` de Avatar.

### Autoridade e memória

Authority deve distinguir:

```text
formal_recognition
perceived_legitimacy
material_control
```

Uma claim não concede automaticamente tropas, território, tesouro ou acesso a
um office. Cada ator/instituição pode reconhecer, contestar ou ignorar a claim
independentemente. O lifecycle da claim é algo como `active`, `withdrawn`,
`defeated` ou `expired`; reconhecimento é relacional.

Fatos históricos são permanentes. A memória ativa tem salience/decay,
reinforcement, historical weight e anchors de identidade institucional, como
fundador, sede, relíquia, templo ou massacre fundador. A LLM não escolhe
livremente o peso histórico.

### Compromissos

Um compromisso pode ter termos individuais:

```text
termo A: fulfilled
termo B: active
termo C: breached
```

O estado geral é derivado. Um breach continua sendo fato histórico mesmo após
reparação:

```text
FATO: A quebrou o acordo
ESTADO ATUAL: A reparou
MEMÓRIA: B ainda pode guardar ressentimento
```

### Escopo V1 consciente

Na V1, `CityRegion` funciona como identidade urbana/institucional para a
vertical atual. Isso é dívida conceitual documentada, não uma verdade eterna:
uma futura cidade exilada, capital provisória ou região com múltiplas cidades
exigirá separar instituição política de localização.

## 🗺️ Evolução do plano maior (Planos 1–5)

O plano foi refinado por várias rodadas antes de virar arquitetura congelada:

### Plano 1 — linguagem causal

Substituir reações roteirizadas e causalidade invertida pelo fluxo
estado → affordance → interpretação → decisão → owner → evento/delta/causas.
Remover Story como causa de mutação, prosa como entrada mecânica, eventos
aleatórios narrativos, ocupação automática e sucessão automática.

Também foram definidos: `DomainAffordance`, `DomainDecision`, registry
transitório, migração/economia/urbanismo/ritos como executores, hazards
engine-owned, relação qualitativa interpretada e magnitude determinística,
Dynasty com casa/linhagem por IDs e ações materiais de população sempre com
owner e evidência.

### Plano 2 — agência institucional

Provar que cidades, governos e seitas decidem independentemente. A hidrologia
deixou de ser a primeira vertical obrigatória; a primeira prova passou a ser
pressão → pedido → decisão de outro ator → commitment → execução → memória.
O Dao ficou explicitamente onisciente, enquanto atores continuam limitados ao
conhecimento adquirido.

### Plano 3 — continuidade histórica

Separar instituição, office e líder. Introduzir capacidades estratégicas
multidimensionais (`administrative_bandwidth`, `diplomatic_bandwidth`,
`military_command`, `project_capacity`, `logistics_capacity`), commitments
multi-termo, breach deliberado, guerra sem hostilidade prévia obrigatória,
escada de desordem (protest/strike/riot/mob/civic movement/rebellion/
revolution), pré-história factual e memória ativa com salience/decay.

### Plano 4 — autoridade concorrente

Introduzir claims concorrentes, distinção entre reconhecimento formal,
legitimidade percebida e controle material, peso histórico engine-owned e
`CasusBelliReading` com urgência, custo esperado, ganho, alternativas e causa
material/política percebida.

### Plano 5 — referência congelada

Fechou as ressalvas de cidade/região V1, remediação de breach sem apagar o
fato, ownership separado de conhecimento e memória, e dois tipos de smoke:

- **Natural smoke:** estabilidade é válida; nenhuma cadeia dramática é exigida.
- **Pressured smoke:** a fixture deve ter ao menos uma cadeia multietapas.

O Plano 5 é a referência arquitetural. Não deve ser redesenhado sem evidência
concreta de implementação/simulação.

## 📚 Histórico de implementação desde o goal longo inicial

Esta seção é uma síntese dos handoffs e do estado cronológico versionado em
`docs/handoff/medieval-current-state.md`. O arquivo citado contém o diário
completo por checkpoint; aqui estão as linhas de evolução necessárias para
retomar o raciocínio.

### Fundação causal e separação de narrativa

- Estado canônico, eventos, deltas, receipts, causal links e finalizer foram
  consolidados como fonte da realidade.
- Story/Crônica passou a ser consequência/observação de fatos, sem delta
  material próprio.
- A consulta `why()`/dossier ganhou caminho navegável para origem, decisão,
  owner e evidências.
- Eventos de decisão passaram a ser auditáveis; a validação de histórico e
  rollback transacional passaram a ser tratados como gates, não como detalhes
  opcionais.
- A regra de save rejeita schemas obsoletos explicitamente; não há camada de
  compatibilidade para saves antigos.

### Geografia, hazards, infraestrutura e saúde

- Mapa/geografia, regiões, rotas, rios, instalações e sites oficiais foram
  modelados como estado canônico.
- Overflow/flood passou a usar definição engine-owned, limiares, resistência,
  exposição, dano e restauração material.
- Manutenção e reativação exigem maintainer explícito, capacidade, recursos e
  decisão; proximidade ou descrição não inferem owner.
- Saúde, unrest, população e rotas recebem deltas apenas de owners materiais.
- A cadeia planejada chuva → enchente → exposição → ponte danificada → rota
  reduzida → affordance de restauração existe como referência; não deve ser
  confundida com a prova de que todo mundo natural terá enchente.

### Governo, dinastia, seitas e autoridade

- Governança, offices, Dynasty, casa real/linhagem, relações entre Avatars e
  instituições foram separados.
- Sucessão automática mensal foi removida; crises de desafio/sucessão usam
  claims, posições, avaliações, evidências e vencedor qualificável.
- Ritos populares e patrocínio institucional foram separados; audiência exige
  patrocínio decidido por uma instituição.
- Authority claims, reconhecimento, retirada e lapse foram trazidos para
  decisões/receipts, com lapse automático mantido como efeito engine-owned.

### Economia material e pressão urbana

- Produção, payroll, renda, emprego, consumo, estoques públicos e domésticos,
  demanda, preços, tarifas, rotas, frete e settlement reports foram
  materializados.
- Ajuda/relief deixou de reduzir métrica sem destino; a entrega vai para
  `household-stock:<group_id>` e é consumida na resolução seguinte.
- A origem de uma transferência reserva sua necessidade própria; uma decisão de
  ajuda não pode apagar déficit local já conhecido.
- Emprego permanente respeita payroll e shortfall; workforce é affordance
  explícita, não criação automática de trabalhadores.
- A rotação de produção compartilhando payroll evita que ordenação por ID
  concentre permanentemente uma linha, sem criar dinheiro, mão de obra ou
  comida.
- Ainda existe déficit material de longo prazo; a economia não está declarada
  resiliente/concluída.

### Diplomacia, commitments e conflito civil

- Propostas, respostas, recusa, persuasão, multi-termo, breach, renegociação,
  reparação, memória e relações institucionais têm slices materiais.
- Ajuda institucional, mercado bilateral, cessar-fogo, remediação de ensino e
  concessão administrativa passam por decisão e owner.
- Movimento cívico, protesto, tumulto, repressão, provisão e anistia foram
  separados em estágios causais.
- Espionagem, suborno, acusação, marcas de descoberta e respostas independentes
  possuem recortes, mas a composição ampla de intriga/religião ainda está
  aberta.

### Campanhas, tecnologia, criaturas e ecologia

- Força agregada, comando, fadiga, suprimento, cerco, retirada, cessar-fogo,
  guarnição, controle revogável e solução política possuem recortes materiais.
- Pesquisa, conhecimento, ensino/venda/roubo, instalação, operador,
  manutenção e cadeia industrial aplicada foram iniciados.
- Ecologia por espécie, habitat, capacidade, hazards e criatura/dragão têm
  definições/owners iniciais.
- Campanha persistente multi-turno, generalização tecnológica, magia ampla,
  criaturas em múltiplos habitats e intriga/religião integrada continuam
  incompletas.

### UI, crônica e participação do jogador

- O usuário apontou que a crônica resumida não explica “por que” algo ocorreu e
  que a tela de personagens deveria acompanhar ações, contexto e histórico.
- Foram trabalhados DTOs, dossiers, observatório, causal query, labels PT-BR e
  painéis de diplomacia/mercado/campanha.
- A visão de produto é: crônica resumida para não poluir; personagem,
  instituição e `why()` para detalhe operacional. A reformulação visual completa
  da tela de personagem e a navegabilidade perfeita de toda a cadeia ainda
  precisam de validação frontend; não assumir que estão concluídas.
- O usuário pediu ajuda de Claude Opus via HerdR para mapa/HUD, mas Claude
  atingiu limite e foi pausado em parte do trabalho. O estado atual desta
  sessão usou somente inspeção local e agentes Luna/Terra quando necessário;
  não há trabalho do Claude a ser presumido além do que está no Git.

## 🔬 Checkpoint herdado antes do goal atual

Este bloco estava no handoff de 22/09 e descreve trabalho anterior ao registro
`medieval-closure-plan`. Foi preservado como contexto histórico, não como
"último checkpoint" nem como prova de que esses arquivos foram criados durante
o goal atual. O resumo atual começa na seção seguinte.

### 1. Prioridade de produção

Arquivos principais:

- `src/sim/medieval/production_priority.py` (novo).
- `src/classes/economy/models.py`.
- `src/classes/economy/state.py`.
- `src/classes/economy/serialization.py`.
- `src/sim/medieval/economy.py`.
- `src/sim/medieval/institutional_agenda.py`.
- `tests/test_medieval_production_priority.py`.

Comportamento:

- `ProductionPriority` é transitória/persistida como estado de economia,
  schema de economia 13 → 14, sem migração de schema antigo.
- Affordance existe apenas quando há conflito local real entre facilities com
  mesmo owner/payroll/settlement/occupation.
- A decisão contém apenas `selected_affordance_id`.
- O owner revalida decisão atual, autoridade, settlement e payroll.
- A prioridade vale para a próxima produção e deixa receipt causal.
- Não cria comida, recursos, trabalhadores ou output automaticamente.

Evidência: 17 testes focados verdes em produção + turno institucional; compile
e `git diff --check` verdes. Uma suíte econômica mais antiga ainda possui uma
expectativa obsoleta de falta `10900` versus observação `4700`, porque relief
offline explícito executou distribuições reais; isso é divergência de política
do teste, não comida criada silenciosamente.

### 2. Autoria causal em owners pequenos

Arquivos principais:

- `src/sim/medieval/research.py` e `research_policy.py`.
- `src/sim/medieval/authority_claims.py`.
- `src/sim/medieval/tariffs.py`.
- `src/sim/medieval/site_services.py`.
- `src/sim/medieval/workforce.py`.
- `src/sim/medieval/persistence.py`.
- `tests/test_medieval_knowledge_verticals_fail_closed.py` (novo).
- `tests/test_medieval_observatory.py`.
- `tests/test_medieval_research.py`.
- `tests/test_medieval_site_services.py`.
- `tests/test_medieval_tariffs.py`.
- `tests/test_medieval_workforce_transitions.py`.

Correções:

- Pesquisa recompõe a decisão exata do mesmo dia antes de criar decisões
  detalhadas de sponsor/worker.
- IDs existentes de eventos, decisões antigas, eventos comuns ou decisões de
  outro ator não podem ser usados como causa.
- Authority claims exigem decisão atual; declare/withdraw/recognize/withdraw
  recognition carregam payload de autoria.
- Tarifas, site service e início pago de workforce foram reclassificados para
  `ACTOR_DECISION` com payload exato.
- Lapse automático de claim e conclusão/falha futura de workforce continuam
  deterministicamente engine-owned.
- Expectativa antiga do observatory foi corrigida para schema canônico `61`; o
  save antigo continua sendo rejeitado, sem compatibilidade.

Evidência: 56 testes focados de autoria/knowledge/research/authority/services/
tariffs/observatory verdes; 2 testes locais de workforce verdes; compile e
`git diff --check` verdes.

### 3. Mercado institucional bilateral

Arquivos principais:

- `src/sim/medieval/market_purchase_policy.py` (novo).
- `src/sim/medieval/procurement.py`.
- `src/sim/medieval/concurrent_civil_decision.py`.
- `src/sim/medieval/institutional_agenda.py`.
- `src/sim/medieval/markets.py`.
- `src/sim/medieval/logistics.py`.
- `tests/test_medieval_market_purchase_policy.py` (novo).
- `tests/test_medieval_concurrent_civil_decision.py`.
- `tests/test_medieval_markets.py`.

Antes, `execute_market_purchase_option` chamava `consider_sale` e fazia o
vendedor aceitar em silêncio. Agora:

```text
comprador escolhe pedido
  → vendedor recebe affordance transitória no mesmo dia
  → vendedor aceita/recusa independentemente
  → owner revalida termos
  → freight/payment/purchase material
```

- O comprador só seleciona ID enumerado.
- A aceitação do vendedor recompõe o pedido atual; pedido stale desaparece.
- Duplicatas são suprimidas.
- `CIVIL_ADAPTERS`, menus mensais e opções compostas exibem os dois lados.
- Household market clearing continua agregado pela engine; não se consulta uma
  LLM por cidadão.
- Caminho offline `consider_sale` continua explicitamente determinístico, não
  deve ser confundido com o fluxo bilateral em modo IA.

Evidência: 39 testes focados de mercado/decisão/concurrent policy verdes;
compile e `git diff --check` verdes.

### 4. Guarnição, infraestrutura e ajuda

Arquivos principais:

- `src/sim/medieval/force.py`.
- `src/sim/medieval/infrastructure.py`.
- `src/sim/medieval/institutional_aid.py`.
- `src/sim/medieval/settlement_intelligence.py`.
- `tests/test_medieval_force.py`.
- `tests/test_medieval_siege_campaign.py`.
- `tests/test_medieval_infrastructure.py`.
- `tests/test_medieval_institutional_aid.py`.
- `tests/test_medieval_ai_decision.py`.

Correções:

- Estabelecer, rotacionar e retirar guarnição materialmente escolhido carregam
  decisão de ator; manutenção, colapso e lapse continuam datados/engine-owned.
- Reativação de site usa autoria exata.
- Fulfillment/remediação de ajuda escolhidos por IA preservam payload do
  provider em freight, obrigação e memória.
- Fixture de infraestrutura agora cria frete fluvial pago via decisões reais
  comprador/vendedor, em vez de depender de uma política implícita.
- Wear/reparo foi ajustado para expectativa material correta (`0.50 → 0.49`
  no wear e depois `+0.10 → 0.59` no reparo).
- Relatórios de settlement existentes são refrescados em ordem estável por ID;
  save/load seguido do mesmo passo produz os mesmos IDs/receipts.

Evidência: ajuda/AI 26 testes verdes; infraestrutura 21 testes verdes após
fixture/order fix; narrow reactivation passou.

### 5. Smoke de autonomia

Arquivos principais:

- `tools/medieval_autonomy_smoke.py`.
- `tests/test_medieval_autonomy_smoke.py`.

O ator de fixture reconhece IDs reais e aliases públicos para os dois lados do
mercado. A política continua escolhendo apenas opções enumeradas.

Evidência atual: 14 testes de smoke verdes. O smoke completo de 120 dias não
foi repetido neste último recorte; evidências anteriores existem nos handoffs,
mas devem ser reexecutadas antes de declarar gate amplo verde.

## 🧪 Registro anterior de task-orchestration

O registro local está em:

```text
../.agent/tasks/medieval-economy-resilience/
  contract.yaml
  state.md
  evidence.md
```

O registro marcou a tarefa como `validating`, com C1–C12 concluídos. Abaixo está
o resumo das evidências E1–E14:

| ID | Evidência | Resultado/limite |
|---|---|---|
| E1 | relief/institution/engine | 36 testes verdes |
| E2 | optional provider fail-closed | 21 testes verdes; rollback do candidato |
| E3/E5 | aftermath | 4 e depois 5 testes verdes |
| E4 | seed 73, dia 30 | Salgueiro tinha déficit 640, estoque próprio 4640 e duas opções de relief; política escolheu uma opção maior em outro boundary |
| E6 | production priority | 17 testes verdes |
| E7/E8 | research/authority/authorship | 23 e 56 testes verdes em recortes distintos |
| E9 | workforce local transition | 2 testes verdes, 33 deselecionados |
| E10 | bilateral market | 39 testes verdes |
| E11 | garrison/siege/reactivation | 24 testes verdes no recorte e narrow reactivation |
| E12 | aid/AI | 26 testes verdes |
| E13 | infrastructure/determinism | 21 testes verdes; rollback/save-load estável |
| E14 | autonomy smoke fixture | 14 testes verdes |

Essas evidências anteriores provam contratos estreitos. Não substituem o
registro E1–E156 do goal atual, descrito abaixo.

## 🧪 Goal atual (22–23/09): inventário integral E1–E156

**Fonte primária:** `../.agent/tasks/medieval-closure-plan/{contract.yaml,state.md,evidence.md}`.
O contrato cobre o fechamento das ondas 0–6 do roadmap, mantém execução
`single_agent` e não concede commit, push, deploy ou delegação. Cada E abaixo
tem comando/artefato/limitação no arquivo de evidências. Os grupos são um
índice para revisão, não 150 afirmações novas nem uma suíte agregada verde.

| Evidências | Trabalho efetivo desde o início do goal | Resultado e fronteira |
|---|---|---|
| E1–E4 | Revisão de escopo e de `$task-orchestration`; sessões MetaGame/Laya shadow; runtime local tolera JSONL maior, preserva `primary_signal` sob fallback de baixa confiança. | Laya foi chamado de verdade, mas apenas observou; `neutral` não é parecer do Laya. Falhas de socket iniciais foram classificadas. |
| E5–E10 | Baseline econômica/causal; ajuda → frete → observação → relief doméstico; inventário de eventos materiais no auditor; links temporais em observações recorrentes de rota, site e hidrologia. | Conservação, save/load e auditoria passaram nos recortes; bootstrap físico inicial não foi maquiado com decisão fictícia. |
| E11–E13 | Comparação de políticas econômicas em 120 dias, baseline militar e checkpoint Laya. TTL do observer remoto foi acrescentado após processo órfão e sua limpeza explícita. | Política de relief melhorou falta na fixture, mas nenhuma opção provou equilíbrio geral. Observer não alterou jogo. |
| E14–E20 | Provider OAuth/Codex Luna local (`codex_cli`) integrado; budget/fail-closed; turno econômico com 14 decisões reais; adoção defensiva, mobilização, abastecimento e retirada bilateral por decisões independentes. | Choices foram IDs enumerados e receipts zero-delta; exemplos reais curtos, não autonomia longa. O teto impediu a 15ª consulta e preservou o save anterior. |
| E21–E28 | Checkpoint Laya inconclusivo; pesquisa/metalurgia → aplicação → ferro extra com Luna; `NO_ACTION` em suborno; protesto civil; correção de expectativa física no overflow; criatura percebe frete e escolhe sem dano forçado; rollback de knowledge e inventário econômico. | Intriga/ameaça não foram forçadas; uma recusa real não é execução material daquela vertical. |
| E29–E38 | API/observatório, dossiês de personagem, pólis e organização, inspeção de força, `why()`/causas, navegador real e save/load/retomada no frontend. | Navegação focal passou, não cobertura visual de todas as cadeias nem UX final. Checkpoints Laya intercalados tiveram falhas honestamente registradas. |
| E39–E43 | Release gate integrado de 120 dias, primeiro ano de três seeds, checkpoints e perfil do menu mensal. | Encontrou custo de escala do menu; não tratou horizonte curto como prova de dez anos. |
| E44–E54 | Retomadas anuais/auditorias da seed 73; diagnóstico de starvation de agenda em ajuda; fallback offline passou a priorizar pressão observada e outra cidade quando cadeia já aberta. Sessão shadow com `primary_signal` real. | Um save retomado mostrou pedido de Valedouro, aceite, frete e relief; decisões offline não equivalem a provider real. Erros de transporte do observer foram registrados, não ocultados. |
| E55–E79 | Nova série da seed 73 após correções; oferta de workforce stale por caixa foi revalidada; documentação da política; diagnóstico de falta com alimento físico; otimizações/checkpoints e auditoria por ano. | Conservação e causalidade passaram em saves auditados, mas privação cresceu; o smoke não era prova de saúde econômica. |
| E80–E110 | Seeds 101/137 em processos isolados, retomadas e auditorias anuais; seed 73, 101 e 137 chegaram a **3.600 dias cada** no checkout daquele momento. Um checkpoint 137/ano 6 teve round-trip independente; saves finais e SHA foram verificados; temporários intermediários específicos foram removidos após validação. MetaGame/Laya shadow foi novamente observado. | Auditorias finais: zero causas quebradas, autoria inválida e Story/LLM material; `real_ai_calls=0` em todas. Houve 5.297/5.162/5.949 mortes por privação nas seeds 73/101/137. O gate ficou **stale após mudanças posteriores** de população e mecânica. Não usar esses saves para declarar o checkout atual equilibrado. |
| E111–E118 | Corrigido seed exibido em retomada; inspeção de affordances reais de relief no ano 10; fixture contrafactual de rota aberta/fechada, recuperação por frete sucessor e compra; repudiação deliberada → conhecimento/memória → recourse escolhido; fortificação passou a exigir posição e provisão, além de knowledge; perda de meios produtivos e testes conjuntos. | Recuperação e resposta são fixtures pressionadas com IDs válidos injetados, não vontade espontânea do provider. Política offline ainda limita uma distribuição por polity/ciclo. |
| E119–E124 | Treino pago e datado por coluna, logística de campo dependente do treino, roubo técnico ligado a produção recente, venda de técnica → treino → força; plano defensivo persiste coluna e encerra só após relatório próprio. Checkpoints shadow. | Conhecer técnica não concede bônus físico automaticamente. Difusão geral e campanha natural continuam abertas. |
| E125–E135 | Cidade própria ocupada por rival pode ser investida; plano → coluna → provisões → cerco → retomada; falta de ração ou rota fechada interrompe cerco; cessar-fogo exige consentimento/retiradas independentes; terreno e relatório local mudam elegibilidade/baixas; expedição longa consome ração e gera fadiga que aumenta perdas. | Cadeias pressionadas com decisões válidas injetadas, não vitória garantida nem controle político secular. Fadiga tardia foi testada contra rival preparado como premissa factual. |
| E136–E145 | Sonda de provider inicialmente barrada antes do envio; ensino bilateral → treino local → força; paliçada construída, danificada e reparada materialmente; soldados iniciais são pessoas reais da população; pesquisa de `field_drill` com meios reais; falta em pesquisa e plano defensivo abre demanda tipada → convite → aceitação de grupo → transição paga → nova decisão de mobilizar. Plano sem coluna agenda reavaliação sem erguer soldados sozinho. | Nenhum novo soldado é criado; opção forjada/recusa não executa. Sonda E136 não foi contada como chamada real. Recrutamento foi provado em fixture, não numa campanha natural longa. |
| E146–E148 | UI Trabalho passou a aceitar demandas de facility, repair, customs, research e military; relief distribui só a falta ainda não paga de cada coorte; dossiê de acessibilidade passou a respeitar a data do relatório conhecido, inclusive boletim remoto. | 3 testes frontend, type-check e build passaram naquele recorte; 74/75 testes backend focados nos recortes finais. Diagnóstico natural atual de 180 dias mostrou desemprego/renda artesanal insuficiente apesar de comida pública. |
| E149–E150 | Consulta **única autorizada** ao OAuth/Luna com fixture sintética de campanha retornou `NO_ACTION` válido, receipt `llm_interpretation` sem delta, nenhuma execução. Contrafactual ampliou recrutamento agrícola até headroom material; piorou falta aos 180 dias e foi **totalmente revertido do código**. | Prova E149 é de recusa dentro do menu, não de campanha positiva. E150 mostra que mais oferta física não dá renda aos artesãos desempregados; não introduzir subsídio/quota para mascarar isso. |
| E151 | Handoff de revisão atualizado neste arquivo. | Documento local, não commitado/publicado; revisar código e evidências diretamente. |
| E152 | Dossiê do administrador passou a mostrar, com relatório local datado, residentes por ocupação e trabalhadores pagos pelas próprias linhas produtivas; o menu já tinha oficina material. | `42 passed`; leitura não é emprego criado nem decisão real de construir. |
| E153 | Provider stub leu o novo contexto e escolheu a oficina enumerada; o owner abriu projeto sem site, emprego ou moeda grátis. | `43 passed` no recorte ampliado; não foi consulta real ao Luna nem prova de recuperação econômica. |
| E154 | Checkpoint de handoff solicitado pelo usuário: estado, registros, matriz e WIP conferidos; nenhuma implementação nova após E153. | Revisor deve tratar E1–E153 como evidências históricas por recorte, não como suíte verde do checkout final. |
| E155 | Uma fixture única seleciona oficina e linha por IDs válidos via stub, conclui ambas com owners pagos e liga produção → salário → compra doméstica. Contra mundo sem obras, há mais compras, menor falta e saúde maior; moeda/população, save/load e auditoria passam. | `44 passed` no recorte dossiê/menu/construção. Não é provider real nem recuperação natural de longo prazo. |
| E156 | O `MedievalSimulator` completo reapresentou a fundação após a obra e chegou a produção, salário e compra. O teste revelou `KeyError: None` na consulta de linhas planejadas para uma obra sem âncora; o guard corrigiu isso. | `72 passed` no recorte afetado, save/load/auditoria da fixture. O teste antigo de Ferroalto passou a usar a população atual; sem consulta real a Luna/Laya ou gate natural. |

### Estado numérico que o revisor não deve misturar

- Gate antigo de 3 seeds × 10 anos: continuidade, save/load, conservação e
  auditoria causal passaram no checkout de E107; os resultados econômicos
  foram ruins e o gate ficou stale depois de E115–E148.
- Smoke atual após E147: seed 73/60 dias, `money_conserved=true`,
  `all_resources_accounted=true`, save/load e auditoria `ok=true`, 1.214
  transições materiais, zero causas/autorias quebradas ou Story/LLM material.
  Isso é apenas dois meses.
- Diagnóstico após E148: seed 73/180 dias, falta agregada 18, saúde média
  950,63, zero mortes por privação até ali; Pedraclara tinha 1.929 artesãos,
  473 moedas de salários artesanais e 10.382 rações públicas; Portovelho,
  1.603 artesãos, 202 moedas de salários e 8.803 rações. Alimento custava 1.
- Contrafactual **descartado** E150, mesma seed/dia: fazendas
  Pedraclara/Portovelho produziram 118/118 lotes contra 44/37 e passaram a
  1.443/1.352 agricultores contra 450/380; falta agregada foi 35, não 18, e
  tesouro de Auren caiu de 12.359 para 6.269. O código experimental foi
  retirado; os saves `/tmp/cws-farm-headroom-20260923/` são diagnóstico.
- O último teste de regressão após a retirada foi `2 passed, 34 deselected`;
  `git diff --check` passou. Não foi rodada a suíte inteira no checkout final.

### MetaGame/Laya e provider do jogo são coisas diferentes

`$task-orchestration` mantém contrato, estado e evidência; `shadow-codex`
inicia observer Laya efêmero na VPS, observa uma sessão Codex externa e encerra
em `finally`/TTL. Sinais `primary_signal.provider=laya` foram registrados em
E3/E6/E12/E16/E48/E54/E69/E90/E110/E121/E124/E133, geralmente com baixa
confiança e política efetiva neutra `observe`. Algumas sessões falharam antes
de inferência ou tiveram erro de transporte; não as conte como revisão bem
sucedida. O observer não muda a engine e não vê retroativamente este chat.

Já o **provider do jogo** foi Codex OAuth/Luna: E14–E26 demonstraram amostras
curtas de escolha real; E149 acrescentou uma consulta sintética autorizada no
checkout atual e `NO_ACTION`. Não existe validação de provider em três seeds
por dez anos, nem autorização implícita para mais consultas externas.

## 🧾 Comandos históricos e verificações do goal atual

Os comandos abaixo são do checkpoint anterior ao goal atual; servem para
reproduzir aqueles recortes, não para alegar que todo o WIP de E1–E156 foi
revalidado hoje. Sempre isolar dados de teste com `CWS_DATA_DIR=/tmp/...`.

```bash
CWS_DATA_DIR=/tmp/cws-priority-final2 TMPDIR=/tmp \
XDG_DATA_HOME=/tmp/cws-priority-final2-xdg \
.venv/bin/pytest -q \
  tests/test_medieval_production_priority.py \
  tests/test_medieval_institutional_decision_turn.py \
  --basetemp=/tmp/cws-priority-final2-pytest
# 17 passed
```

```bash
CWS_DATA_DIR=/tmp/cws-authorship-complete TMPDIR=/tmp \
XDG_DATA_HOME=/tmp/cws-authorship-complete-xdg \
.venv/bin/pytest -q \
  tests/test_medieval_site_services.py \
  tests/test_medieval_tariffs.py \
  tests/test_medieval_research.py \
  tests/test_medieval_knowledge_verticals_fail_closed.py \
  tests/test_medieval_observatory.py \
  --basetemp=/tmp/cws-authorship-complete-pytest
# 56 passed
```

```bash
.venv/bin/pytest -q tests/test_medieval_workforce_transitions.py \
  -k local_transition
# 2 passed, 33 deselected
```

```bash
CWS_DATA_DIR=/tmp/cws-market-final TMPDIR=/tmp \
XDG_DATA_HOME=/tmp/cws-market-final-xdg \
.venv/bin/pytest -q \
  tests/test_medieval_market_purchase_policy.py \
  tests/test_medieval_concurrent_civil_decision.py \
  tests/test_medieval_markets.py \
  --basetemp=/tmp/cws-market-final-pytest
# 39 passed
```

```bash
CWS_DATA_DIR=/tmp/cws-infra-determinism TMPDIR=/tmp \
XDG_DATA_HOME=/tmp/cws-infra-determinism-xdg \
.venv/bin/pytest -q tests/test_medieval_infrastructure.py \
  --basetemp=/tmp/cws-infra-determinism-pytest
# 21 passed
```

```bash
CWS_DATA_DIR=/tmp/cws-smoke-market-final TMPDIR=/tmp \
XDG_DATA_HOME=/tmp/cws-smoke-market-final-xdg \
.venv/bin/pytest -q tests/test_medieval_autonomy_smoke.py \
  --basetemp=/tmp/cws-smoke-market-final-pytest
# 14 passed
```

Também foi executado `compileall` e `git diff --check` nos recortes; não foram
usados como substituto da suíte completa.

Para os recortes **recentes do goal**, consultar primeiro o comando literal e
o resultado na entrada E correspondente. Exemplos verificáveis:

```bash
CWS_DATA_DIR=/tmp/cws-affordability-observation-20260923 \
  .venv/bin/pytest -q tests/test_medieval_actor_dossier.py \
  tests/test_medieval_relief.py tests/test_medieval_workforce_transitions.py \
  tests/test_medieval_institutional_decision_turn.py
# E148: 75 passed em 29,95s, no checkout daquele recorte
```

```bash
CWS_DATA_DIR=/tmp/cws-farm-headroom-20260923 \
  .venv/bin/pytest -q tests/test_medieval_workforce_transitions.py \
  -k 'natural_food_pressure_can_improve_through_workforce_decisions or the_labour_signal_is_typed_quantified_and_restated_every_cycle'
# E150: 2 passed, 34 deselected após retirada do experimento
```

E146 registrou `npm run test -- src/medieval/__tests__/workforce.test.ts`
(`3 passed`), `npm run type-check` e `npm run build` com saída 0 no checkout do
recorte. O teste de browser E31/E35 não foi repetido após E146. O gate final
deve reexecutar backend afetado, frontend e auditoria no **mesmo checkout**;
não somar resultados de revisões diferentes como uma suíte única.

## 📁 Mapa do repositório

```text
src/classes/core/          mundo, infraestrutura, config, persistence base
src/classes/economy/       estado, modelos, payroll, serialização, logística
src/classes/environment/   mapa, creatures, overflow, geografia
src/classes/governance/    autoridade, diplomacia, knowledge, strategy
src/classes/research/      estado de pesquisa
src/classes/society/        população, movimentos, unrest
src/sim/medieval/           owners, policies, affordances, decisões e fases
src/server/medieval/        contratos, queries, runtime/API
tests/                      regressões focadas e fixtures
tools/                      smoke, release gate e auditoria causal
web/src/medieval/           UI Vue/TypeScript e testes de frontend
docs/handoff/               roadmap, estado cronológico e documentação
../.agent/tasks/             registro local de task-orchestration no workspace
```

Documentos de referência:

- `docs/handoff/projeto.md` — visão, arquitetura, setup, APIs e deploy histórico.
- `docs/handoff/medieval-roadmap.md` — ondas 0–6 do roadmap versionado.
- `docs/handoff/medieval-current-state.md` — diário cronológico completo dos
  checkpoints, C108–C130 e além.
- `docs/handoff/medieval-goal-progress-2026-09-18-19.md` — progresso do goal
  anterior.
- `docs/handoff/estado-e-pendencias.md` — inventário de estado/pendências.
- `docs/handoff/plano-principal.md` — plano causal original consolidado.
- `docs/handoff/plano-consequencia-causal.md` — separação de fatos, story e
  causal links.
- `medieval-corrections-and-finalization-plan.md` — plano operacional atual,
  correções, ondas restantes e gates.

## ⚠️ Estado atual real e limites

Não declarar “plano concluído”. O documento operacional atual classifica:

| Área | Estado real |
|---|---|
| Autoria causal/Why | Auditorias standalone de fixtures e saves naturais passaram, inclusive inventário por owner; ainda falta auditoria de todos os owners no checkout final. |
| Provider fail-closed | Codex OAuth/Luna fez escolhas reais e recusas válidas em sondas curtas; falhas/budget pausam sem material parcial. Não há gate representativo de horizonte longo nem cobertura de todas as verticais. |
| Economia | Mercado bilateral, ajuda, relief por coorte, emprego, workforce, preço, frete e recuperação existem. Acesso doméstico à comida e emprego material artesanal continuam falhando no horizonte; E150 refutou recrutamento agrícola isolado. |
| Diplomacia/commitments | Respostas independentes, repudiação, breach/remediação e memória têm cadeias pressionadas. Intriga ampla e negociação autônoma multi-termo ainda não foram provadas. |
| Campanhas | Plano/coluna/suprimento/cerco/retomada/cessar-fogo persistem em fixtures multietapas; informação, terreno, fadiga, paliçada e recrutamento têm recortes. Não há campanha longa natural nem solução política geral validada. |
| Tecnologia | Metalurgia aplicada com Luna; campo, logística e ensino/venda com treino aplicado; roubo exige operação material. Catálogo e difusão ampla permanecem parciais. |
| Magia/ecologia/criaturas | Recortes iniciais; rito/contramedida/ameaça de habitat composta ainda abertos. |
| Intriga/religião/Dao | Acusação, suborno, protesto e dossiers têm fatias; composição ampla e `why()` multi-salto de todas as verticais ainda faltam. |
| Gates finais | Três seeds × dez anos passaram **no checkout anterior** como gate offline de continuidade/causalidade, mas tiveram milhares de mortes por privação e ficaram stale. Frontend focado/type-check/build passou em E146; gate consolidado atual ainda aberto. |

Limites econômicos observados:

- O gate antigo de dez anos mostrou sobrevivência técnica, não equilíbrio;
  smokes atuais de 60/180 dias não substituem o horizonte longo.
- Na seed 73, mesmo com relief/workforce, houve falta material residual.
- Estoque público não equivale a poder de compra doméstico.
- Famílias podem não conseguir comprar mesmo quando há estoque na cidade.
- Não adicionar produção automática, subsídio automático ou anti-shortage
  override. O próximo diagnóstico deve separar renda, payroll, trabalho,
  armazenamento, rota, preço e decisões possíveis.

Limites de causalidade observados:

- A auditoria anterior encontrou que `validate_history` podia aceitar uma
  transição `ACTOR_DECISION` sem decision source; os recortes recentes fecharam
  vários owners, mas isso não prova todos.
- Testes verdes de fallback/repression não provam conformidade arquitetural
  completa.
- Houve escolhas reais de Codex/Luna em E14–E26 e uma recusa sintética
  autorizada em E149. A sonda de campanha E136 foi barrada antes do envio e
  não deve ser contada; E149 não executou owner material.
- A existência de uma fixture pressionada não significa que o mundo natural
  produzirá a mesma cadeia.

Limites operacionais:

- Worktree tem WIP não commitado; não usar `git reset --hard`, `git checkout`
  ou limpeza ampla.
- Não afirmar push/deploy atual sem verificar SHA remoto e serviço.
- Remotes: `github-personal` é GitHub; `origin` é a VPS.
- O espaço em disco estava apertado; foram removidos apenas caches/temp
  recriáveis em momento anterior, não dados do projeto. Manter testes em `/tmp`
  e evitar smokes gigantes sem necessidade.

## 🔜 O que falta, em ordem do plano principal

### Gate 0 — corrigir e auditar a fundação

1. Completar auditoria de autoria de todos os owners que emitem delta.
2. Encontrar e remover qualquer fallback determinístico que substitua provider
   em modo IA.
3. Verificar que commitments nunca executam sozinhos.
4. Separar fato histórico, estado reparado, knowledge e institutional memory em
   todas as projeções.
5. Validar save/load/rollback de agenda, RNG, decisões, commitments, relações,
   memória, knowledge e auditoria, sem persistir affordances.
6. Produzir auditoria final com `broken_cause_ids=[]`, zero
   `ACTOR_DECISION` sem fonte e zero Story/LLM com efeito material.

### Onda 1 — economia resiliente

1. Fechar a lacuna de renda/emprego dos artesãos da seed 73 com trabalho e
   demanda material verificáveis. E148 separou estoque de poder de compra;
   E150 refutou simplesmente ampliar ofertas agrícolas. Inspecionar opções
   atuais de fundar linha/obra e sua real viabilidade antes de acrescentar
   outra lei econômica.
2. Fazer instituições escolherem entre produção, empregos, compra, ajuda,
   relief e investimento com informação datada, sem a engine subsidiar famílias
   automaticamente nem criar uma quota de atividade.
3. Revalidar a cadeia de rota interrompida/recuperação e os recortes de tarifa,
   embargo e contrabando no mesmo checkout após mexer no mercado.
4. Repetir fixture pressionada e, só ao estabilizar mecânicas, smokes naturais.

### Onda 2 — agência institucional/diplomacia

1. Completar objetivos/planos verificáveis e barganha bilateral.
2. Integrar influência, espionagem, suborno, sabotagem, acusação, traição e
   commitments multi-termo.
3. Exigir conhecimento privado, authority e memória sem transformar interpretação
   em causa.
4. Demonstrar concessão/breach/reparação e decisão futura influenciada pelo
   fato histórico.

### Onda 3 — tecnologia aplicada

1. Completar cadeia descoberta → knowledge → ensino/venda/roubo/migração →
   instalação → operador → manutenção → output/defesa/campanha.
2. Demonstrar perda de output sem operador, equipamento, material ou manutenção.
3. Generalizar difusão e defesa depois de uma cadeia ponta a ponta verde.

### Onda 4 — campanhas e controle

1. A cadeia pressionada E126 já persiste plano/coluna/suprimento/cerco por
   turnos; ampliá-la para uma campanha natural longa sem fixar vitória.
2. Integrar informação, terreno, fadiga, recrutamento E144, guarnição e
   controle duradouro à escolha real do provider; E149 foi `NO_ACTION` e não
   equivale à escolha positiva desta cadeia.
3. Confirmar que retirada, cessar-fogo, ocupação revogável e solução política
   continuam exigindo decisões e owners em cada etapa, inclusive save/load.

### Onda 5 — magia, ecologia e criaturas

1. Generalizar hazards/ritos com custos, resistências, habitat, alcance,
   duração, recuperação e owner.
2. Dar criaturas necessidades, memória e affordances próprias.
3. Provar ameaça material sem spawn/catástrofe obrigatórios.

### Onda 6 — intriga, religião e observabilidade

1. Completar investigação, evidência privada, acusação, perseguição, negociação
   e recuo.
2. Manter protesto, tumulto, civic movement, rebelião e revolução distintos.
3. Integrar religião, claims concorrentes, influência e conflito institucional.
4. Finalizar dossier multi-salto/UI PT-BR: resultado → evento → decisão → owner
   → evidências/perspectiva.

### Gates finais

- Regressões focadas, compileall, `git diff --check`, type-check e testes web.
- Fixtures pressionadas para economia, diplomacia, campanha, intriga,
  tecnologia e ecologia.
- Três seeds naturais por dez anos; estabilidade é válida, cadeia dramática não
  é obrigatória. O gate antigo E107 deve ser repetido no checkout final porque
  as premissas populacionais/mecânicas mudaram.
- Provider real validado isoladamente e em falha sem mutação parcial.
- Auditoria final limpa.
- Só então marcar ondas como concluídas, atualizar docs, commit/push/merge e
  deployar.

## 🧩 Arquivos modificados/novos relevantes no WIP

O `git status --short` é a lista autoritativa completa. O conjunto recente mais
relevante inclui:

```text
src/classes/economy/models.py
src/classes/economy/serialization.py
src/classes/economy/state.py
src/sim/medieval/economy.py
src/sim/medieval/institutional_agenda.py
src/sim/medieval/production_priority.py
src/sim/medieval/research_policy.py
src/sim/medieval/authority_claims.py
src/sim/medieval/site_services.py
src/sim/medieval/tariffs.py
src/sim/medieval/workforce.py
src/sim/medieval/market_purchase_policy.py
src/sim/medieval/procurement.py
src/sim/medieval/markets.py
src/sim/medieval/logistics.py
src/sim/medieval/concurrent_civil_decision.py
src/sim/medieval/force.py
src/sim/medieval/infrastructure.py
src/sim/medieval/institutional_aid.py
src/sim/medieval/settlement_intelligence.py
src/sim/medieval/persistence.py
tools/medieval_autonomy_smoke.py
tools/medieval_causal_audit.py
tools/medieval_release_gate.py
tests/test_medieval_production_priority.py
tests/test_medieval_knowledge_verticals_fail_closed.py
tests/test_medieval_market_purchase_policy.py
tests/test_medieval_concurrent_civil_decision.py
tests/test_medieval_infrastructure.py
tests/test_medieval_institutional_aid.py
tests/test_medieval_ai_decision.py
tests/test_medieval_autonomy_smoke.py
medieval-corrections-and-finalization-plan.md
docs/handoff/medieval-current-state.md
web/src/medieval/components/DiplomacyPanel.vue
web/src/medieval/i18n.ts
web/src/types/medieval-api.ts
```

No goal atual, consultar também os seguintes limites de edição/prova (lista
seletiva, não um `git status` completo):

```text
../.agent/tasks/medieval-closure-plan/contract.yaml
../.agent/tasks/medieval-closure-plan/state.md
../.agent/tasks/medieval-closure-plan/evidence.md
docs/handoff/medieval-closure-plan.md
docs/handoff/medieval-closure-matrix.md
src/sim/medieval/actor_dossier.py
src/sim/medieval/relief.py
src/sim/medieval/workforce.py
src/sim/medieval/strategy_response.py
src/sim/medieval/force.py
src/sim/medieval/force_training.py
src/sim/medieval/settlement_intelligence.py
src/sim/medieval/market_purchase_policy.py
src/sim/medieval/institutional_decision_turn.py
tools/medieval_campaign_provider_probe.py
tools/medieval_autonomy_smoke.py
tools/medieval_causal_audit.py
tests/test_medieval_actor_dossier.py
tests/test_medieval_relief.py
tests/test_medieval_workforce_transitions.py
tests/test_medieval_persistent_campaign_chain.py
tests/test_medieval_military_recruitment.py
web/src/medieval/mappers.ts
web/src/medieval/__tests__/workforce.test.ts
```

Alguns arquivos acima já estavam modificados antes do último turno; não usar
esta lista para atribuir autoria temporal de cada linha. `git diff` e E1–E156
definem o que está no WIP local, e commits anteriores mostram o baseline.

Existem também muitos arquivos históricos modificados em `src/classes`,
`src/sim`, `tests` e `web`; não remover nem resetar sem revisar autoria e
dependências.

## 🛠️ Como a próxima IA deve continuar

1. Ler este arquivo.
2. Ler `medieval-corrections-and-finalization-plan.md`.
3. Ler o topo e as últimas seções de `docs/handoff/medieval-current-state.md`.
4. Inspecionar `git status --short --branch`, `git diff --stat` e o HEAD antes
   de editar.
5. Não assumir que o branch limpo ou que o remote/deploy contém este WIP.
6. Não resetar, limpar, migrar saves ou alterar dados reais sem autorização.
7. Escolher um recorte pequeno com owner claro e teste focado.
8. Preservar a cadeia causal e adicionar evidência de decisão/owner/source.
9. Rodar somente testes relevantes e reportar falhas reais, sem alegar suíte
   geral verde.
10. Atualizar `docs/handoff/medieval-current-state.md`, a matriz de fechamento,
    o registro de evidências e este handoff em checkpoint relevante.
11. Quando um checkpoint de código estiver realmente fechado, pedir/confirmar
    antes de commit, push, merge ou deploy; publicar o SHA e validar o ambiente
    remoto separadamente.

A preferência operacional do usuário é: tarefas leves podem ir para Luna,
tarefas complexas para Terra; Claude/HerdR foi usado em fases anteriores, mas o
uso foi pausado quando o limite de Claude foi atingido. Não inventar trabalho de
Claude que não esteja no código/commit.

## 🧠 Decisões que não devem ser reabertas sem evidência

| Decisão | Racional | Áreas afetadas |
|---|---|---|
| Dao é onisciente | O jogador precisa ver a verdade; atores têm knowledge limitado | UI, dossier, IA, investigação |
| LLM só escolhe affordance | Evita prosa virar física/estado | todos os owners |
| Story não causa mutação | Narrativa explica fatos reais | events, chronicle, why |
| Fallback só offline/test | IA indisponível não deve inventar ação | provider, transaction, rollback |
| Commitments são obrigações | Prazo não é transferência automática | aid, trade, diplomacy |
| Instituição ≠ office ≠ líder | Continuidade sobrevive a morte/troca | authority, memory, governance |
| Claim não concede poder material | Legitimidade e capacidade são separadas | succession, war, treasury |
| Fato histórico ≠ memória ativa | História não some; relevância pode decair | knowledge, memory, why |
| Natural smoke pode ser estável | Não existe quota de drama | release gates |
| Pressured smoke exige cadeia | Fixtures precisam provar composição | acceptance |
| `CityRegion` é cidade V1 | Dívida explícita, não modelo eterno | city/institution |
| Não preservar compatibilidade de código/saves antigos | Contrato novo deve falhar claramente | persistence |

## 🚧 Blockers & Open Questions

- Não há bloqueio de código para continuar a Onda 1, mas falta fechar o
  diagnóstico econômico sem inventar produção, trabalho ou renda. O
  contrafactual E150 refutou uma solução simples.
- A lista de owners que ainda podem emitir `ACTOR_DECISION` sem fonte precisa
  ser auditada diretamente, não inferida de handoffs.
- Provider real foi sondado no checkout atual uma vez em E149 e retornou
  `NO_ACTION`; a escolha material positiva da cadeia militar e a execução
  natural prolongada com provider continuam sem prova.
- O gate natural offline de dez anos rodou em E86/E106/E107, **antes** das
  mudanças de população/mecânica recentes; não foi repetido no checkout
  atual. A suíte completa também não foi executada aqui.
- Ainda é necessário decidir, quando houver evidência, como separar cidade e
  região além da V1; não antecipar esse refactor.
- A qualidade final de UI/personagem/crônica precisa ser verificada no frontend
  real, não apenas nos contratos/API.
- E152 confirmou opções atuais de oficina em Pedraclara e Portovelho e
  acrescentou leitura datada de residentes/payroll produtivo próprio. E153
  provou a escolha por stub e projeto aberto. E155 compôs na mesma fixture
  opção → decisões → obra paga → linha → salário → compra/saúde, com controle
  sem obra, save/load e auditoria. E156 percorreu turnos completos do
  simulador e corrigiu a consulta que falhava para obra sem âncora (`72 passed`).
  A escolha real do provider e a recuperação natural não foram demonstradas.

## 📋 Usage Protocol

1. Esta é a referência de transferência, mas o código e os testes atuais têm
   precedência sobre frases históricas.
2. Sempre distinguir `implementado`, `testado`, `documentado`, `não executado` e
   `planejado`.
3. Ao adicionar um recorte, atualizar os arquivos específicos, os testes, a
   evidência e a seção de estado atual.
4. Não marcar o roadmap inteiro como concluído porque um smoke ou fixture passou.
5. Para qualquer alegação de causalidade, mostrar a decisão-fonte, owner,
   affordance, payload e links do evento.
6. Para qualquer alegação de publicação/deploy, mostrar branch, SHA remoto,
   serviço/endpoint e smoke pós-deploy.
7. Ao encerrar outro turno, atualizar este arquivo sobrescrevendo o estado
   antigo (não criar um segundo handoff paralelo).
