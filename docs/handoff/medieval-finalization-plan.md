# Plano de fechamento — Medieval V1

> Ordem de execução substituída em 28/09/2026 pelo
> [contrato de conclusão](../../medieval-completion-contract.md), incluindo
> explicitamente povos, magia e religião. Os gates abaixo preservam a V1 técnica
> histórica; seus checks não fecham o contrato ampliado.

Atualizado em 25/09/2026, sucedido em 28/09/2026. Este foi o plano operacional
da V1 técnica. O [roadmap](medieval-roadmap.md) continua sendo a visão de produto;
a [matriz](medieval-closure-matrix.md) registra estado por requisito; o
[estado atual](medieval-current-state.md) guarda evidência, medições e progresso.
O antigo `medieval-finalization-next-plan.md` é arquivo de trabalho/histórico,
não instrução vigente.

## Objetivo e escopo congelado

Fechar uma fatia medieval jogável, causal, adaptativa e investigável. Não abrir
Industrial Warfare, torneios ou novas verticais durante este plano. V1 não quer
completar cada sistema amplo do roadmap; quer provar uma integração mínima e
extensível entre:

- economia capaz de oferecer ao menos uma resposta material válida quando
  conhecimento, autoridade e recursos compatíveis existem;
- ajuda, comércio e compromissos bilaterais com decisões independentes;
- objetivo político, QG/office militar e comandante de campo em decisões
  separadas;
- campanha persistente com suprimento e ao menos uma interferência ambiental;
- consequência econômica ou social fora da campanha;
- uma interação representativa de cultivation ou criatura;
- conhecimento/memória que afete uma decisão posterior;
- observabilidade de fato → decisão → owner → delta → consequência (`why()`),
  save/load e custo operacional aceitável.

Não é requisito: prosperidade garantida, ausência de mortes/conflito, drama em
toda seed, vitória militar, provider sempre escolhendo ação, nem generalizar toda
magia, religião, espionagem, tecnologia, espécie ou forma de governo. Esses
requisitos amplos continuam visíveis na matriz/roadmap e não podem ser
silenciosamente declarados concluídos pelo aceite V1.

## Como acompanhar progresso

O plano fica estável e contém entregas/aceites; a matriz contém o status por
requisito; `medieval-current-state.md` é o diário append-only de evidências,
medições e descobertas. Não copiar resultados de teste ou histórico de owners
para este plano. Cada entrega principal abaixo tem checkbox; as subetapas
executáveis ficam no checklist da matriz. Antes de cada recorte de trabalho,
criar uma caixa `[ ]` específica na matriz se ela ainda não existir. Ao concluir
o recorte, marcar essa caixa `[x]`, registrar no mesmo checkpoint uma entrada
`E` reproduzível no estado atual e atualizar a linha correspondente da matriz.
Cada caixa descreve um resultado verificável, não tempo gasto ou intenção;
check parcial não fecha automaticamente a entrega principal.
Não marcar por código existente, intenção, teste isolado ou smoke de
outro checkout. Se a evidência ficar stale por mudança de código, reabrir a
caixa. Ao pausar, registrar último item concluído, próximo item aberto e limites
conhecidos. Em cada checkpoint, revisar desvio de escopo em shadow com
MetaGame/Laya via task-orchestration quando disponível; registrar o sinal como
consultivo, nunca como validação ou autoridade de owner. Indisponibilidade do
observador deve ficar explícita, sem fallback oculto.

### Checklist de execução

O acompanhamento granular, com um check por subetapa e referência E, fica na
[matriz de fechamento](medieval-closure-matrix.md). Este plano mantém apenas
os gates, a ordem e os critérios de aceite.

### Evidência já disponível — não equivale a gates fechados

- [x] Foi observada uma cadeia natural seed 14: overflow/enchente → instalação
  danificada → rota reduzida → leitura do mantenedor → escolha de reparo → custo
  material/trabalho → rota recuperada. Evidência: estado atual e matriz, entrada
  de 25/09; a decisão de reparo foi offline, não provider real.
- [x] Há campanha multietapas em fixtures com coluna, carga, cerco, retirada,
  contrafactuais de suprimento/rota/terreno/fadiga e save/load. Evidência:
  matriz, linha 4; isso ainda não é a cadeia política natural de V1.

### Entregas e gates

- [x] **1. Baseline preservado e mapa de fechamento sincronizado.** Registrar
  branch/HEAD/WIP do checkout de retomada sem atribuir mudanças sem baseline.
  Confirmar que matriz e estado atual apontam para este plano e não contradizem
  o roadmap. Verificar: links e status conferidos; WIP preservado. Evidência
  `E125` em `.agent/tasks/medieval-world-simulator/evidence.md` e seção de
  retomada em `medieval-current-state.md`; baseline não atribui o diff inteiro
  a este goal.

- [x] **2. Inventário completo de mutações materiais (Gate A).** Cruzar emissores
  estáticos com eventos observados em saves. Para cada família registrar owner,
  decisão/affordance ou causa física permitida, conhecimento, revalidação,
  delta/fontes, atomicidade e verificação negativa. Classificar `verificado`,
  `parcial`, `falha reproduzida` ou `não exercitado`; corrigir apenas falhas
  concretas e agrupadas. Verificar: cobertura conhecida finita, exceções
  nomeadas, divergências estático/runtime explicadas; não confundir inventário
  com exercício em runtime. Progresso parcial: `E126` agrupou o histórico do
  save dia 1.560, `E129` cruzou fontes estáticas/runtime e `E130` classificou
  famílias e nomes dinâmicos. `E137` registra a classificação finita por
  owner/origem/conhecimento/delta/transação/negativa. “Parcial” e “não
  exercitado” permanecem limites explícitos; inventário não certifica toda
  semântica de owners nem substitui os gates C/D.

- [x] **3. Limite comum de execução material (Gate A).** A partir das falhas do
  inventário, estabelecer o menor caminho comum que exija autoria/causa,
  validação temporal, candidato transacional, publicação atômica e receipt/link
  material. Owners continuam donos de regras e cálculos específicos; não criar
  um framework especulativo nem migrar owners antigos sem falha/evidência que o
  justifique. Todo caminho material novo do V1, porém, deve usar esse limite.
  Verificar: testes negativos compartilhados provam que falha de validação ou
  execução não deixa mutação parcial; cobertura e owners migrados listados na
  matriz.
  Evidência `E131/E133/E136`: início e recuperação de migração são os dois
  comandos migrados; negativos cobrem falha tardia, mutação sem receipt e
  transição sem causa. `AGENTS.md` exige esse limite para comandos diretos
  materiais V1 novos. Owners antigos não são certificados por isso.

- [x] **4. Causa dominante da crise econômica identificada (Gate B).** Seguir,
  em assentamentos/coortes representativos, caixa de empregador → folha paga →
  emprego/produção → renda familiar → acesso/oferta/compra → falta canônica →
  saúde/mortalidade. Identificar o primeiro elo limitante e distinguir falta de
  conhecimento, affordance, autoridade, recurso/rota, prioridade escolhida,
  escala insuficiente e projeção exclusiva do Dao. Verificar: owner, evento,
  estado e decisão disponíveis documentados para cada elo; diagnóstico
  reproduzível no save/seed selecionado.
  Evidência `E135` limita a conclusão a Campomanso/Cinzaverde e a este dia:
  renda não chega às coortes artesãs; em Cinzaverde o payroll anterior zera
  caixa antes da produção. Construção é elegível, mas não escolhida no run
  `ai_enabled=False`; isso não demonstra que a economia global se recupera.

- [x] **5. Capacidade de adaptação econômica demonstrada (Gate B).** Quando
  conhecimento, autoridade e meios compatíveis existem, pelo menos uma cadeia
  válida deve permitir a um ator reduzir materialmente a pressão. Comparar com
  contrafactual `NO_ACTION`/resposta inviável e mostrar a diferença vindo de
  ação normal do owner — não de renda, estoque, emprego, subsídio ou recuperação
  automática. A trajetória ainda pode piorar por recusa, demora, prioridade ou
  resposta insuficiente. Uma economia não passa apenas porque a trajetória
  trágica pode ser explicada: se há comida/estoque, dinheiro, autoridade e rota
  adequados, mas nenhuma ação consegue conectar esses meios às famílias, é
  lacuna de design e o gate falha. Verificar: a opção é acessível ao ator por
  evidência válida; escolha/execução/efeito são causais; a comparação mede
  falta/acesso e saúde, não exige prosperidade universal nem zero mortes.
  `E134` prova a cadeia longa de oficina → linha → emprego → salário → compra
  usando holdings iniciais. `E140-finalização` prova, no save crítico do dia
  1.560, que Campomanso consegue iniciar obra, comprar madeira com aceite
  independente e rota real, pagar artesãos e reduzir a falta após um mês em
  relação ao controle. Cinzaverde possui obra e quatro rotas de compra
  enumeradas, mas seu resultado mensal específico não foi contrafactualmente
  executado; o aceite V1 exige ao menos uma resposta eficaz, não recuperação
  universal. Sem escolha do provider, a trajetória natural ainda pode falhar.
  A fixture pareada E208 também demonstra que crédito familiar voluntariamente
  decidido pode financiar a folha seguinte: o controle sem o empréstimo continua
  `unpaid_funds`. Isso prova eficácia potencial da nova affordance, não adoção
  natural nem substitui a cadeia histórica E140.

- [x] **6. Cadeia política-militar-social integrada (Gate C).** Provar primeiro
  num cenário autônomo controlado: condições iniciais podem ser preparadas, mas
  após iniciar não há escolhas injetadas; decisões vêm do provider ou de
  políticas explícitas identificadas e owners resolvem consequências. A cadeia
  deve incluir autoridade política, QG/office, comandante e ator econômico ou
  grupo populacional; política/comando, campanha/logística, ambiente/criatura e
  economia/sociedade. A autoridade política escolhe ou mantém o objetivo; o QG
  decide plano/ordem/suprimento; o comandante recebe informação local e decide
  executar, adaptar ou não agir. Essas são decisões independentes, não etapas
  roteirizadas por um único decisor. Uma interferência externa altera o plano
  materialmente, chega em relatórios datados, provoca pelo menos duas decisões
  independentes entre esses atores, causa consequência fora do militar e é
  navegável pelo `why()`. Verificar: alterar rota/suprimento/conhecimento muda
  decisão ou resultado; as mesmas campanha/força persistem entre etapas; nenhum
  ator usa informação que não recebeu; save/load mantém a cadeia. E139 fecha
  este aceite em fixture autônoma controlada com provider stub; o contrafactual
  de rota aberta é o recorte físico pareado já existente, não uma segunda
  trajetória autônoma. Formação natural e provider real seguem itens 7/8.

- [x] **7. Observação natural sem cota de drama (Gate C).** Procurar a composição
  do item 6 em trajetórias naturais, sem injetar decisão depois do início e sem
  exigir que toda seed a produza. Distinguir explicitamente fixture autônoma,
  fallback/offline, provider real e observação natural. Verificar: só chamar de
  emergência natural o que aconteceu sem escolhas injetadas; registrar também
  `NO_ACTION`, paz e ausência de cadeia como resultados legítimos.
  `E165-finalização` inspecionou duas trajetórias atuais offline, seeds 14
  (1.440 dias) e 73 (2.610 dias): há ajuda, trabalho e leituras, mas nenhuma
  campanha/cerco ou destacamento. A cadeia física enchente→reparo é evidência
  histórica de checkout anterior; não substitui a cadeia política completa.

- [x] **8. Provider real — corpus curto e explícito (Gate D).** Com configuração
  e autorização disponíveis, rodar ao menos 10 decisões pareadas/situadas,
  cobrindo crise econômica, rota/campanha, compromisso próximo do prazo,
  exigência de criatura e disputa entre prioridade militar/alimento. Verificar:
  seleciona apenas affordance oferecida ou `NO_ACTION`, respeita conhecimento
  disponível, não repete opção impossível após causa mudar, receipt é válido e
  falha não deixa mutação parcial. Não pontuar “otimalidade”; relatar decisões,
  latência, falhas e custo. Se indisponível, manter caixa aberta — uma chamada
  isolada ou `NO_ACTION` não fecha este item.
  E195 executou 10 consultas OAuth/Luna em menus distintos, mais uma consulta
  pareada após cumprimento material da obrigação. Os 11 IDs foram válidos,
  receipts não alteraram matéria e saves originais permaneceram intactos; o
  par causal removeu a affordance antiga e Luna escolheu outra. Uma retirada
  decidida pelo comandante encerrou a revisão antes do turno do QG nesse
  caso. O cliente não fornece uso/preço, logo o custo monetário é
  indisponível, não zero. Os checks de conhecimento foram dirigidos aos
  campos inspecionados, não uma auditoria universal de prompts.

- [x] **9. Orçamento operacional V1 congelado antes do gate longo.**
  Medir baseline no host de referência, sem smokes concorrentes, e registrar
  limites antes da execução final. Estes limites foram fixados a partir do
  baseline medido; o gate longo ainda precisa demonstrar cumprimento:
  3.600 dias por seed ≤ 60 min; pico RSS ≤ 4 GiB; save de 10 anos ≤ 512 MiB;
  save/load ≤ 60 s cada; p95 de avanço mensal em checkpoint tardio ≤ 35 s; p95
  de `why()` ≤ 2 s para consulta de até 100 links. Verificar: mesma máquina,
  versão, cenário e método; medir ledger/saves e ao menos 20 consultas `why()`.
  O limite mensal original de 20 s foi refutado por 18 meses contíguos tardios
  da seed 73 (p95 30,90 s) e foi fixado em 35 s antes do gate final; os demais
  limites permanecem. Não relaxá-los depois de ver o resultado final. Não
  truncar fatos para caber;
  índices/segmentos são aceitáveis se IDs e navegação causal sobreviverem.

- [ ] **10. Smoke final e aceite V1 (Gate D).** Somente após gates 1–9 e checkout
  estabilizado: três seeds naturais sequenciais por 3.600 dias, checkpoints,
  conservação, save/load/continuação e auditoria causal; cenário autônomo do
  item 6; provider corpus reportado separadamente; regressão focada API/UI e
  navegação `why()`. Verificar: nenhuma causa/autoria/story-material inválida;
  limites operacionais atendidos; toda falha e limitação reportada. Não chamar
  um gate histórico ou smoke parcial de atual/concluído.
  O instrumento `medieval_release_gate.py --final-v1` exige três seeds
  distintas, checkpoints anuais ou mais frequentes e verifica os limites
  congelados; sua existência não substitui executar e aprovar o run.

## Estado dos gates neste checkpoint

- Gate A: **fechado no escopo V1 dos entregáveis 2/3** — inventário finito e
  limite comum direto existem; owners antigos classificados como parciais não
  receberam certificação semântica integral.
- Gate B: **aceite mínimo contrafactual demonstrado; persistência/adaptação
  ainda em andamento** — E140 mostrou redução material no save crítico. E215
  manteve falta e desigualdade de acesso após continuação natural. E216/E217
  mostraram Luna escolhendo a oficina e o owner abrindo projeto em clone;
  E218–E221 acompanharam frete físico e conclusão, mas a compra usou política
  offline e a cadeia não chegou a linha, folha e compra doméstica. Em E235 Luna
  escolheu sem direcionamento uma affordance válida de auxílio em Ferroalto;
  E237 reproduziu o ID em clone e o owner reduziu falta `653→0`, elevou saúde
  `611→631` e reduziu unrest `385→365`. E238 confirmou zero efeitos no ramo
  `NO_ACTION`. E242 avançou ambos os clones por 30 dias sob `routine-rules`:
  ambos chegaram a falta alimentar zero e sem mortes por privação; a diferença
  relativa de saúde/unrest persistiu, mas rotinas offline também decidiram nos
  dois ramos. E243 confirmou conservação, save/load e auditorias limpas. Isso
  não isola toda diferença à escolha inicial, nem prova provider contínuo,
  recuperação natural ou estabilidade. No save corrente E252/dia 480, E263
  revalidou uma resposta aguda: relief escolhido por decisão API no clone moveu
  223 rações às famílias e alterou falta/saúde/unrest via owner, com histórico
  válido e fonte intacta. E264 mostrou que a oficina comprou/recebeu madeira,
  mas bloqueou em `payroll_funds`; controle e intervenção tiveram relief/frete
  offline e terminaram iguais, então não atribuir benefício à oficina. O
  aceite de resposta aguda está renovado; adaptação estrutural de renda,
  atribuição em horizonte longo e composição natural seguem pendentes.
- Gate C: **fechado no aceite V1 controlado e observado** — item 6 passou em
  cenário autônomo controlado e a busca natural do item 7 foi documentada.
  A formação espontânea da cadeia política completa não foi observada;
  nenhuma quota de guerra é inferida disso.
- Gate D: **aceite técnico histórico no fingerprint** — corpus real E195; três
  seeds de 3.600 dias, auditorias e budgets E199; cenário controlado, API/UI e
  `why()` E200 passaram em
  `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28`.
  Esse resultado ficou stale após mudanças posteriores. E235 é uma decisão
  provider real no menu corrente, mas não revalida o corpus; E240 constatou
  que os saves antigos do corpus não carregam sob o schema atual. O item 10
  exige fixtures compatíveis e repetição da validação no checkout estabilizado.
  A economia permanece sob alerta: mortes por privação e saúde final foram
  materialmente diferentes entre seeds e altas em duas delas. Este aceite não
  significa que as verticais explicitamente adiadas nem o polimento de produto
  estejam concluídos.

## Referências de trabalho

- [Roadmap de produto](medieval-roadmap.md)
- [Matriz de fechamento](medieval-closure-matrix.md)
- [Estado atual, evidências e métricas](medieval-current-state.md)
- [Handoff do goal de 24–25/09](medieval-goal-handoff-2026-09-24-25.md)
