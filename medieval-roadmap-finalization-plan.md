# Plano de fechamento do roadmap medieval

Atualizado em 19/09/2026. Este plano resume o que ainda falta depois das
fatias V1 já implementadas. A referência detalhada continua em
`medieval-roadmap-remaining-plan.md`; o estado observado está em
`docs/handoff/medieval-current-state.md`.

## Situação atual

Já existem fatias causais de economia, mercado, workforce, migração,
diplomacia, persuasão, espionagem, suborno, sabotagem, pesquisa, venda/roubo
de tecnologia, cerco, guarnição, ocupação, controle territorial, ritos,
hazards, criaturas, protestos, greves, movimentos, rebelião, observabilidade e
save/load.

Isso ainda não equivale ao roadmap completo. Os gates de 120/360 dias e a
matriz natural de três seeds por 360 dias passaram com auditoria limpa, mas o
provider remoto real e o horizonte de dez anos ainda não foram validados. A
economia continua pressionada em algumas cidades; isso é uma lacuna causal a
resolver, não um motivo para distribuir recursos automaticamente.

## Plano executável

1. **Prova operacional do provider**
   - Exercitar decisão válida, `NO_ACTION`, provider indisponível, orçamento
     excedido e affordance stale.
   - Verificar receipt, rollback, agenda/RNG, save/load e ausência de mutação
     parcial.
   - Aceite: falhas são fail-closed e auditáveis; sem provider configurado o
     teste falha explicitamente.

2. **Agência institucional completa**
   - Consolidar objetivos, planos e memória conhecida no turno mensal existente.
   - Fechar persuasão social, violação deliberada, acusação por evidência e
     reparação para compromissos além de pagamento.
   - Aceite: instituições decidem independentemente; obrigação, relação e
     memória apontam para decisão, owner e fatos-fonte.

3. **Economia resiliente**
   - Fechar renda recorrente, efeitos de escassez sobre saúde/descontentamento,
     alternativas de abastecimento, pedágio, trânsito, bloqueio e mobilidade.
   - Completar detecção, devolução e apreensão de contrabando como affordances
     materiais, sem resolução automática.
   - Aceite: rota interrompida, alternativa e recuperação produzem estoques,
     população, saúde e pressão social diferentes e auditáveis.

4. **Tecnologia e produção além da defesa**
   - Ampliar a árvore e demonstrar descoberta → produção → treinamento →
     instalação/operação → manutenção.
   - Ligar pelo menos uma técnica a comércio, produção ou campanha fora dos
     bônus militares já existentes.
   - Aceite: conhecimento sem instalação, autoridade, operador e suprimento não
     altera estado material.

5. **Campanha e solução política**
   - Generalizar manutenção/rotação de guarnição, cerco prolongado, ocupação,
     cessar-fogo bilateral e administração pós-ocupação.
   - Reusar compromissos e owners; nenhuma solução política pode executar só
     por existir uma proposta.
   - Aceite: controle exige guarnição e abastecimento; cessar-fogo e concessão
     só mudam o mundo após aceitação e cumprimento material.

6. **Magia, ecologia e criaturas gerais**
   - Transformar ritos/hazards em definições engine-owned com custo, alcance,
     duração, resistência, recuperação e contramedida.
   - Adicionar diversidade de habitat, necessidades, memória, negociação e
     ataque material sem spawn ou catástrofe obrigatórios.
   - Aceite: cada efeito possui alvo e evidência física revalidáveis.

7. **Intriga, religião e produto do Dao**
   - Completar perseguição, conspiração e persuasão apenas quando houver
     pressão, organização, liderança, conhecimento e ação material.
   - Finalizar dossier multi-salto, mapas de controle/rotas/forças/ameaças e UI
     PT-BR para navegar de resultado → evento → decisão → owner → evidências.
   - Aceite: Dao vê a verdade completa; cada ator vê apenas seus fatos; prosa,
     acusação ou plano privado nunca é causa material sem fato-fonte.

8. **Gate final de release**
   - Rodar regressões focadas por onda e fixtures pressionadas.
   - Executar três seeds naturais por dez anos; estabilidade é resultado válido.
   - Auditar causalidade, conservação, rollback, agenda/RNG, save/load, custo de
     IA e ausência de deltas de Story/LLM.
   - Aceite: zero causas quebradas, zero mutações parciais e equivalência de
     continuação; cadeia multietapas é obrigatória apenas em fixtures
     pressionadas.

## Dependências e ordem

```text
1 → 2 → (3 e 4 em paralelo) → (5 e 6) → 7 → 8
```

O próximo trabalho recomendado é a prova operacional do provider, se houver
credencial/configuração. Sem provider disponível, avançar na cadeia econômica
da onda 3, usando somente affordances já enumeradas e owners canônicos.

## Fora do escopo

Não criar compatibilidade para contratos/saves antigos, DSL mecânica nova,
planner paralelo, tesouro imperial separado, logística profunda ou eventos
narrativos aleatórios que alterem a realidade. Não declarar o roadmap completo
por causa de um teste focado ou smoke curto.
