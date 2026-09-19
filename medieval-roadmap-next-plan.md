# Plano de conclusão do roadmap medieval

Atualizado em 19/09/2026. Este é o plano de execução a partir do WIP atual; não
é uma declaração de que o roadmap está concluído. O detalhe histórico fica em
[`medieval-roadmap-completion-plan.md`](medieval-roadmap-completion-plan.md), e o
estado/handoff em [`docs/handoff/medieval-current-state.md`](docs/handoff/medieval-current-state.md).

## Onde estamos

Já existem contratos causais, affordances com ID, `NO_ACTION`, owners com
revalidação, rollback/save-load, memória institucional, economia material V1,
mobilidade/payroll, alfândega, pesquisa/difusão em recortes, cerco/ocupação,
movimentos cívicos, duas espécies, hazards e observabilidade inicial. Os
últimos checkpoints de workforce/emprego corrigiram a prioridade de agricultura
sem criar renda, comida ou população fora dos owners.

Ainda não existe autonomia geral nem resiliência econômica comprovada. O
provider remoto não foi validado, e o gate natural de três seeds por dez anos
continua sem execução.

## Trabalho restante, em ordem

- [ ] **1. Prova operacional do provider** — executar uma sondagem pequena com
  provider real para decisão válida, `NO_ACTION`, erro, orçamento excedido,
  indisponibilidade e affordance stale. Verificar fail-closed, receipt, rollback,
  agenda/RNG e ausência de mutação parcial. Sem provider configurado, o harness
  deve falhar explicitamente.

- [ ] **2. Agência institucional social** — completar objetivos/planos dentro
  do turno mensal existente; ampliar persuasão, acusação por evidência,
  violação deliberada e reparação. Compromissos continuam obrigações, nunca
  comandos automáticos; breach permanece como fato histórico mesmo após reparo.
  Verificar que duas instituições decidem independentemente e cada efeito aponta
  para decisão, owner e fatos-fonte.

- [ ] **3. Economia resiliente** — fechar o ciclo renda/emprego/estoque das
  coortes e demonstrar alternativas reais de abastecimento: produção, rota
  alternativa, bloqueio, pedágio, contrabando, detecção, apreensão, migração e
  recuperação. Não adicionar distribuição gratuita. Verificar diferenças
  materiais em estoque, saúde, população e unrest entre rota interrompida,
  alternativa e recuperação.

- [ ] **4. Tecnologia e produção** — ampliar além das cadeias agrícolas/militares
  atuais com uma cadeia completa descoberta → produção → treinamento →
  instalação/operação → manutenção. O efeito deve depender de autoridade,
  operador, insumo e capacidade authored, e alterar uma leitura de comércio,
  defesa ou campanha de forma limitada.

- [ ] **5. Campanha e solução política** — generalizar manutenção e rotação de
  guarnições, combate/cerco prolongado, controle territorial sustentado e
  administração pós-ocupação. Cessar-fogo, concessão ou retirada só mudam o
  mundo após aceitação independente e cumprimento material.

- [ ] **6. Magia, ecologia e criaturas** — transformar os ritos/hazards estreitos
  em definições engine-owned reutilizáveis, com escola, custo, alcance, duração,
  resistência e contramedida. Adicionar habitat/necessidade/negociação de outro
  território authored, sem spawn ou catástrofe obrigatórios.

- [ ] **7. Intriga, religião e UI** — completar perseguição religiosa,
  conspiração e persuasão somente quando houver pressão, organização, liderança,
  conhecimento e ação material. Finalizar dossier multi-salto, mapa de
  controle/rotas/forças/ameaças/planos e UI PT-BR. O Dao permanece onisciente;
  cada ator continua limitado ao próprio conhecimento.

- [ ] **8. Gate final** — rodar regressões focadas por onda; depois três seeds
  naturais por dez anos e fixtures pressionadas para exigir cadeias
  multietapas. Auditar causas quebradas, deltas de Story/LLM, conservação,
  rollback, agenda/RNG, save/load, custo/latência de IA e evidência navegável.
  Mundo natural estável é resultado válido; drama só é obrigatório na fixture.

## Dependências e regra de avanço

1. A prova operacional do provider é pré-requisito para usar IA real como
   evidência; testes determinísticos continuam válidos para desenvolvimento.
2. Agência institucional deve preceder intriga e solução política.
3. Economia e tecnologia podem avançar em paralelo depois dos contratos sociais
   estabilizados.
4. Campanhas, magia/ecologia e UI dependem dos owners e projeções anteriores.
5. O gate final é sempre a última etapa.

Uma etapa só vira concluída quando possui owner material, cadeia causal
navegável, save/load, regressão focada e evidência de execução. Um teste focado,
um smoke curto ou uma fixture pressionada não autoriza declarar o roadmap geral
verde.

## Fora do escopo

Não criar compatibilidade com saves/contratos antigos, DSL mecânica nova,
planner paralelo, tesouro imperial separado, logística profunda ou eventos
narrativos que alterem estado sem fato-fonte.
