# Plano principal congelado

## Visão aprovada

Um mundo de cultivo com atores que acumulam história, formam laços, sustentam obrigações e decidem sobre interesses incompatíveis. As referências de experiência são mundos políticos e aventureiros vivos, não roteiros obrigatórios de traição, guerra ou catástrofe.

O Dao vê toda a verdade canônica. Atores decidem com o conhecimento que adquiriram; suas perspectivas podem ser filtros opcionais, nunca uma limitação do Dao. A crônica resume; detalhes individuais, institucionais e o “Por quê?” permitem investigar como um resultado aconteceu.

```text
estado canônico → leituras/condições → affordances transitórias
→ ator escolhe → contraparte decide, quando necessário
→ owner revalida e executa → fatos/deltas/links
→ memória/relações/condições → decisões futuras
```

A arquitetura original completa está em [Actor-Driven Emergent World](../specs/actor-driven-emergent-world.md). As regras abaixo são requisitos; consulte [o estado](estado-e-pendencias.md) para saber quais composições ainda estão parciais.

## Contratos que não devem ser reabertos sem evidência

### Decisões e causalidade

- `DomainAffordance` é transitória, tem ID determinístico e parâmetros calculados pela engine; não vai para o save.
- `DomainDecision` seleciona uma affordance enumerada ou `maintain`/nenhuma ação. A LLM não inventa alvo, quantidade, termo, evidência, custo ou lei física.
- O registro coletivo não substitui nem duplica o catálogo `ActionRegistry` dos Avatares.
- O owner recompõe as opções e valida autoridade, estoque, capacidade, rota, vida e demais requisitos no instante da execução, inclusive depois de awaits.
- Decisão é `FactKind.DECISION` com `AgentDecision`, sem delta. A transição material é outro evento com `StateDelta` e link à decisão real.
- Story e interpretação LLM nunca carregam deltas nem causam mutações. Narrativa aponta para fatos existentes, não cria resultados mecânicos.
- Sem opção material, registrar receipt determinístico sem chamar provider. Falha técnica não pode ser disfarçada de preferência consciente.

### Instituição, cargo e líder

- Instituição é durável; office define escopos; líder é Avatar. Trocar o líder não apaga compromissos ou relações.
- `AuthorityClaim` admite concorrência. Lifecycle: `active`, `withdrawn`, `defeated`, `expired`.
- Reconhecimento formal é relacional; legitimidade percebida é perspectiva; controle material vem do estado real. Uma claim não concede tropas, tesouro ou território.
- `can_actor_act_for(actor, institution, scope)` deve ser determinístico e recomputável.
- Cidade-instituição usa `CityRegion` somente na V1; referências cruzadas usam `EntityRef`. Não criar outra entidade urbana agora.
- Capacidade é multidimensional: administrativa, diplomática, militar, logística e de projetos; não uma mana estratégica global.

### Compromissos, conhecimento e memória

- `InstitutionalAuthorityState`, `InstitutionalRelationsState` e `InstitutionalKnowledgeState` são estados separados, pertencentes ao World.
- Relações guarda relações, compromissos, memória e reconhecimento; nunca recursos, população, território, estratégia ou decisões.
- Compromissos têm termos independentes; estado agregado é derivado. Termos: `proposed`, `active`, `fulfilled`, `breached`, `remediation_proposed`, `remediated`, `cancelled`, `expired`.
- Termos guardam parâmetros aceitos, não estoque nem reservas. Uma obrigação não é comando automático: entregar e reparar exigem nova decisão e execução pelo owner.
- Prazo perdido pode produzir breach determinístico, nunca transferência automática. Reparação resolve obrigação atual e preserva a quebra histórica.
- Knowledge responde quem sabe; memória responde quanto importa. Toda memória referencia fatos canônicos conhecidos.
- História permanece; relevância ativa decai e pode ser reforçada. Peso histórico é engine-owned, limitado a escala relativa, mudança institucional, quebra de compromisso e impacto em identity anchors.
- Anchors apontam a fundador, sede/capital, relíquia, local sagrado ou compromisso fundador reais.

### Conflitos emergentes

- Traição como interpretação exige quebra deliberada de obrigação conhecida e vigente; benefício ou pressão não são pré-requisitos obrigatórios.
- Guerra não exige hostilidade anterior. Leituras de causa percebida incluem credibilidade, objetivo, alcance, urgência, custo, ganho e alternativas; desconhecido continua desconhecido e leitura não concede autoridade.
- Protesto, greve, tumulto, violência coletiva, movimento, rebelião e revolução não são sinônimos nem uma escada automática. Rebelião organizada exige organização, liderança e capacidade reais; tumulto pode não ter líder.
- Religião compõe seitas, tradições, presença, claims e ações materiais. Não inventar um owner “igreja” paralelo.
- Passado inicial deve produzir fatos executados por owners; não sortear dívidas e rivalidades sem origem. A LLM pode selecionar episódios válidos, não inventar efeitos.

## Primeira vertical e ondas aprovadas

```text
pressão urbana → pedido de ajuda → resposta independente
→ compromisso multi-termo → transferência/projeto
→ cumprimento/recusa/breach/reparação → memória → decisão futura
```

| Onda | Entrega prevista |
| --- | --- |
| 1 | Vocabulário e ADRs: autoridade concorrente, relações, conhecimento/memória, prosa não causal. |
| 2 | Instituições, offices, claims, relações, anchors, termos, persistência e rollback. |
| 3 | Substituir diplomacia antiga das seitas pelo estado institucional compartilhado. |
| 4 | Vertical de ajuda sob pressão urbana, ponta a ponta. |
| 5 | Decisões coletivas por affordance transitória e revalidação do owner. |
| 6 | Cumprimento, breach, reparação, memória e influência nas próximas decisões. |
| 7 | Cadeia completa na API e interface do Dao; preservar acompanhamento de Avatares. |
| 8 | Pré-história factual com possibilidades enumeradas pela engine. |
| 9 | Água próxima como vulnerabilidade, não carga permanente de enchente; hidrologia alimenta reações existentes. |
| 10 | Compor comércio, guerra, religião e desordem civil com as mesmas primitivas. |
| 11 | Considerar intriga, conspiração e ameaças míticas apenas depois de evidência de longo prazo. |

Não abrir uma nova espinha dorsal a cada onda. A onda 11 é condicional, não promessa de implementação imediata. Torneios extras não substituem fechar o plano principal.

## Aceite

- ID inventado ou obsoleto: nenhuma mutação.
- Pedido, resposta, execução e reparação: decisões independentes quando aplicável, com autoria navegável.
- Mudança de liderança preserva obrigações; claim sem controle material não permite gastar recursos.
- Save/load preserva estados, eventos, decisões, receipts e causalidade, nunca affordances.
- Falha mensal restaura estado, eventos, relações, receipts, calendário e RNG.
- Nenhuma Story altera realidade ou aparece como ancestral material.
- Smoke natural de 120 meses: estabilidade é válida, zero causas quebradas e zero mutações de Story; sem cota de acontecimentos.
- Smoke pressionado de 120 meses: exigir cadeia institucional completa, materialmente válida e navegável. Políticas injetadas devem ser declaradas.
- Testes focados e smokes não equivalem à suíte inteira verde ou à prova de qualidade de qualquer mundo natural.

## Fora do escopo congelado

Sem DSL mecânica completa, segunda engine/planner, facção política paralela, tesouro imperial novo, logística profunda ou engine separada de guerra territorial. Aleatoriedade física fundamentada continua permitida; drama aleatório não altera o mundo. Código obsoleto pode ser removido, mas dados reais nunca são apagados ou migrados destrutivamente por consequência disso.
