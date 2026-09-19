# Plano geral restante — Medieval World Simulator

Atualizado em 19/09/2026. Este documento é a fila de conclusão do roadmap; não
declara o produto concluído. O estado factual está em
`docs/handoff/medieval-current-state.md`, a intenção de produto em
`docs/handoff/medieval-roadmap.md` e os checkpoints em
`medieval-roadmap-completion-plan.md`.

## Decisão de execução

O próximo trabalho não é abrir mais uma feature narrativa. É fechar as
pendências materiais que ainda impedem o mundo de sustentar decisões autônomas
por horizonte longo. A ordem prática é:

```text
provider fail-closed
→ agência/compromissos
→ economia resiliente
→ tecnologia aplicada
→ campanha persistente/solução política
→ magia/ecologia geral
→ intriga + observabilidade do Dao
→ gates de release
```

As ondas 3 e 4 podem avançar em paralelo depois da agência institucional; as
ondas 5 e 6 só devem ser abertas quando seus owners e compromissos puderem
reutilizar essa mesma infraestrutura. Não criar handlers especiais por tipo de
história para preencher o roteiro.

## O que já está comprovado, mas não encerra o plano

- A espinha causal e várias verticais V1 existem: mercado, workforce,
  migração, rotas/alfândega, pesquisa/difusão, diplomacia, ajuda, cerco,
  ocupação, movimentos cívicos, ritos, hazards, criaturas e dossier.
- Três seeds naturais por 360 dias passaram auditoria de causalidade,
  conservação e save/load. Isso ainda não é o gate natural de dez anos.
- Regressões focadas recentes passaram; fallback offline e provider stub não
  contam como validação de autonomia com provider remoto real.
- A pressão alimentar observada é evidência de uma lacuna de resiliência a
  resolver, não autorização para distribuir recursos automaticamente.

## Leitura correta do estado

A espinha dorsal causal já está em uso: estado canônico → fatos e condições →
affordances transitórias → decisão por ID/`NO_ACTION` → owner revalida e executa
→ evento, delta e links causais. Já existem fatias materiais de economia,
workforce, migração, rotas/alfândega, pesquisa/difusão, diplomacia, ajuda
institucional, cerco/ocupação, controle territorial, movimentos cívicos,
ritos, hazards, criaturas e observabilidade.

Isso não equivale ao roadmap geral. O que falta é fechar as verticais e provar
que elas continuam funcionando em horizonte longo, com provider real e sem
transformar fallback, Story ou texto em causa material.

## Trabalho restante, em ordem

### Onda 1 — prova operacional do provider real

**Estado:** harness isolado existe; provider remoto com credencial real ainda
não foi validado.

- Exercitar decisão válida, `NO_ACTION`, provider indisponível, limite de
  orçamento/latência e affordance inexistente ou stale.
- Verificar que a falha é fail-closed: nenhum delta, evento parcial, avanço de
  agenda ou consumo de RNG sem transação confirmada.
- Registrar custo, latência, modelo, receipt, decisão e rollback; repetir a
  continuação após save/load.

**Aceite:** cada caminho deixa evidência auditável e o harness falha
explicitamente quando não há provider configurado. Fallback offline é útil para
desenvolvimento, mas não conta como prova de autonomia.

### Onda 2 — agência institucional e memória social

**Estado:** menu institucional, ajuda, resposta, cumprimento e reparação de
ajuda já têm recortes causais; a agência social geral ainda é parcial.

- Integrar objetivos, planos e memória conhecida ao turno mensal já existente,
  sem criar um segundo planner.
- Completar compromissos multi-termo fora da ajuda: persuasão, recusa, acusação
  baseada em evidência, violação deliberada, reparação e renegociação.
- Manter separadas instituição, office e líder; authority, knowledge, strategy,
  assets e memória precisam continuar com owners distintos.
- Fazer memória apontar para fatos canônicos e receipts de criação/reforço;
  nunca permitir que lembrança ou prosa crie um fato.

**Aceite:** duas instituições escolhem independentemente entre opções válidas;
obrigações não executam sozinhas; breach histórico permanece após reparação;
cada mudança aponta para decisão, owner, evento e delta reais.

### Onda 3 — economia resiliente, subsistência e mobilidade

**Estado:** V1 material de produção, emprego, mercado, rotas, compras,
provisionamento, migração e recuperação existe; cidades ainda podem permanecer
pressionadas e a resiliência de longo prazo não foi comprovada.

- Fechar o ciclo recorrente de renda, emprego, folha, estoque e capacidade sem
  criar dinheiro ou comida fora dos owners econômicos.
- Fazer escassez produzir leituras materiais de saúde, descontentamento e
  migração, preservando `NO_ACTION` quando nenhuma resposta for válida.
- Completar alternativas de abastecimento, trânsito, pedágio, bloqueio,
  contrabando, detecção, apreensão e recuperação por affordances explícitas.
- Confirmar que rota interrompida, alternativa e recuperação geram trajetórias
  diferentes de estoque, população, saúde e pressão social.

**Aceite:** cadeia auditável de pressão → decisão → execução → consequência;
sem distribuição automática, sem estoque estrangeiro privado no prompt e sem
resolver condição apenas porque ela foi detectada.

### Onda 4 — tecnologia e produção além dos recortes atuais

**Estado:** pesquisa, apprenticeship, difusão e algumas aplicações authored já
existem; a cadeia produtiva ampla ainda é incompleta.

- Implementar uma cadeia vertical completa: descoberta → conhecimento próprio
  → treinamento/ensino → instalação → operação → manutenção.
- Ligar ao menos uma técnica a produção, comércio ou campanha fora do bônus
  militar já coberto.
- Exigir em cada etapa autoridade, operador, capacidade física, materiais,
  folha e manutenção válidos.
- Manter conhecimento sem instalação como estado informacional, não como
  mutação material.

**Aceite:** tecnologia instalada muda uma leitura canônica limitada e
revalidável; conhecimento sozinho não aumenta produção, território ou força.

### Onda 5 — campanhas persistentes e solução política

**Estado:** cerco, guarnição, ocupação, controle territorial e cessão
administrativa têm fatias; a campanha completa ainda não está fechada.

- Generalizar manutenção, rotação, queda e recuperação de guarnições.
- Fechar combate/cerco prolongado, abastecimento, controle territorial e
  interdições sem converter ocupação em domínio automático.
- Completar cessar-fogo, retirada, concessão pós-ocupação e seus compromissos
  multi-termo, incluindo breach e remediação.
- Revalidar autoridade concorrente, capacidade militar/logística e condições do
  settlement no momento de cada execução.

**Aceite:** ocupação sem guarnição e suprimento perde controle; proposta aceita
não altera o mundo; cessar-fogo/concessão só produzem mudança após cumprimento
material independente.

### Onda 6 — magia, ecologia e criaturas gerais

**Estado:** leis authored de hazard/metabolismo/estresse e duas criaturas já
existem; generalização para escolas, habitats e contramedidas ainda falta.

- Transformar efeitos mágicos e ecológicos em definições engine-owned com alvo,
  custo, alcance, duração, resistência, recuperação e contramedida.
- Adicionar mais de um habitat e necessidades persistentes sem spawn,
  catástrofe ou ataque obrigatório.
- Permitir memória, negociação e reação material de criaturas somente quando
  houver affordance, conhecimento e owner válidos.

**Aceite:** todo efeito possui fonte física/espiritual, alvo e evidência
navegáveis; narrativa não registra lei nem delta.

### Onda 7 — intriga, religião e produto do Dao

**Estado:** existem ritos, perseguição e movimentos cívicos em recortes; a
camada ampla de intriga e a experiência de observação ainda são incompletas.

- Completar perseguição, conspiração, persuasão e acusações apenas com pressão,
  organização, liderança, conhecimento e ação material.
- Finalizar dossier multi-salto e telas PT-BR para navegar resultado → evento →
  decisão → owner → evidências, incluindo controle, rotas, forças, ameaças,
  compromissos e planos.
- Preservar a assimetria: Dao vê a verdade completa; atores recebem somente
  fatos conhecidos e receipts destinados a eles.
- Garantir que Story, prosa, interpretação LLM e plano privado nunca sejam causa
  material sem fato-fonte.

**Aceite:** o jogador consegue explicar por que algo ocorreu sem receber um
resumo sem origem; cada ligação termina em fato e owner canônicos.

### Onda 8 — gate final de release

Executar somente depois das ondas anteriores:

- regressões focadas por onda, `compileall`, `git diff --check`, type-check e
  testes web medievais;
- fixtures pressionadas para ajuda, escassez, campanha, intriga e ecologia,
  exigindo cadeias multietapas;
- três seeds naturais por dez anos, com estabilidade aceita como resultado
  válido;
- auditoria de causas quebradas, deltas de Story/LLM, conservação, rollback,
  agenda/RNG, save/load, latência/custo do provider e integridade API/UI.

**Aceite:** zero causas quebradas e mutações parciais; continuação após
save/load equivalente; nenhuma Story/LLM como origem material; cadeia completa
obrigatória somente nas fixtures pressionadas.

## Dependências

```text
1 → 2 → (3 e 4) → (5 e 6) → 7 → 8
```

Uma onda só é concluída quando tiver situação canônica, affordance transitória,
decisão/receipt, owner material com revalidação, causalidade navegável,
save/load e regressão focada. Teste isolado, fixture pressionada ou smoke curto
não autoriza marcar o roadmap geral como concluído.

## Fora do escopo

Não criar compatibilidade para saves/contratos antigos, DSL mecânica nova,
planner paralelo, tesouro imperial separado, logística profunda ou eventos
narrativos aleatórios que alterem a realidade.
