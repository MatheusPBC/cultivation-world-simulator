# ADR 0004: Affordances transitórias e causalidade factual

- Status: Aceita
- Data: 2026-09-03
- Escopo: decisões de domínios coletivos, autoria causal e narrativa

## Contexto

Propostas fechadas por domínio permitiam que interpretadores repetissem parte
da mecânica e favoreciam handlers ligados ao nome de uma condição. Eventos
narrativos também podiam ficar próximos demais da mutação que apenas deveriam
explicar. Isso invertia autoria: interpretação ou prosa parecia produzir a
realidade que deveria somente observar.

## Decisão

Domínios coletivos expõem `DomainAffordance`s transitórias por um registro em
código. Cada opção deriva do estado canônico, contém ID determinístico, ação,
alvos, parâmetros calculados pela engine, urgência e fatos motivadores. A opção
nunca é persistida. O ator retorna somente `maintain` ou `act` com um
`selected_affordance_id`; antes da execução, o owner recompõe as opções e
bloqueia um ID ausente ou obsoleto.

O catálogo existente de ações de Avatar continua único. O registro de
affordances serve apenas aos domínios coletivos e não possui estado, planner ou
validador paralelo.

Toda decisão persistida usa `FactKind.DECISION` e carrega `AgentDecision` sem
`StateDelta`. Uma transição com autoria de ator aponta para esse fato de
decisão. Interpretações de LLM e Stories não carregam deltas. Story aponta para
um fato real, nunca aparece como causa material e não é usada como entrada
numérica. O finalizador valida essas invariantes antes do commit mensal.

Impactos de relação seguem o mesmo limite: a interpretação escolhe categorias
qualitativas por direção; o owner converte intensidade em 2, 4 ou 6, limita as
valências permitidas e emite a transição e seus deltas.

## Consequências

- Uma ação pode responder a condições diferentes sem novo dispatch por nome.
- Uma condição pode oferecer várias ações ou nenhuma.
- Decisions e receipts são auditáveis, enquanto affordances sempre refletem o
  estado atual.
- Saída inválida da LLM não escolhe outra ação implicitamente e não muta o
  mundo.
- Novas leis materiais, como interações de hazards, continuam registradas pela
  engine; texto não registra física.

Este ADR substitui os trechos do ADR 0002 que descrevem proposals fechadas e
fallbacks específicos por domínio.
