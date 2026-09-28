# Estado atual — Medieval World Simulator

## E281 — renda recorrente não cobre todas as coortes — 28/09/2026

- Reconciliação: o contrato e a matriz agora referenciam E280 como último
  recorte antes desta investigação; o antigo “próximo após E273” foi removido.
  Nenhum probe provider isolado de relief foi iniciado.
- O diagnóstico read-only cruzou E278 com `src/sim/medieval/consumption.py`,
  `labor.py`, `permanent_employment.py`, `workforce.py`, `demography.py`,
  `force.py`, `relief.py` e `opening_income.py`. Compra de ração só reduz falta
  para grupos que têm saldo em `household:{group_id}`. Trabalho pago deposita
  salário na conta do grupo que realmente trabalhou; conta ausente pode ser
  criada nesse pagamento, sem crédito. Emprego permanente só oferece coortes
  empregáveis por uma linha produtiva local e exclui `dependent`. Uma transição
  de trabalho exige demanda/notice datados e uma conta doméstica válida antes
  da aceitação. Salário militar tem causa material em recrutamento ou guarnição
  ativa; não remunera automaticamente toda reserva.
- `dependent` é um grupo demográfico agregado, sem parentes/guardiões no modelo.
  Nascimento cria dependentes; a maturação datada move quem restou à coorte de
  farmers, sem escolher uma família ou transferir renda. `opening_income.py` é
  uma transferência inicial finita, não uma folha recorrente. A alternativa
  existente para cobrir falta observada é relief: depende de relatório e estoque
  atuais e uma decisão pontual; a política offline ignora falta abaixo de 20.
- Conclusão limitada: existe alívio material possível e há trabalho/salário
  para coortes com ocupação e demanda reais, mas a representação não fornece
  renda recorrente ou relação de sustento entre adulto e dependente. Não inferir
  família por raça/assentamento, não atribuir salário a reserva parada e não
  criar auxílio automático. O Gate B não passou.
- Evidência reproduzível combinada: E278, seed 73, captura natural do dia 300
  por `tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --trace-next-boundary --priority-facility-id
  works:campos-do-lume`; inspeção dos owners acima no checkout `2eb1f9e3` mais
  WIP E277–E280. Limitação: inspeção de contratos não mede uma nova trajetória,
  nem prova que todo grupo soldado estava fora de guarnição.
- Próximo recorte a registrar: selecionar um caminho estrutural existente de
  emprego/renda ou acesso, definir seus owners e comparar por vários ciclos
  contra controle sem transferir privação. Não acrescentar uma relação familiar
  ou regra de benefício sem decisão de domínio e causal owners definidos.

## E280 — affordance pequena permanece sem escolha no offline — 28/09/2026

- A continuação sem interação/API do branch controle E270 foi levada do dia 300
  ao 330. `world_ai_enabled=false`; não houve `relief_distributed`. Campomanso
  terminou novamente com falta 6 e affordances atuais de relief por 6/3, baseadas
  em relatório próprio atual.
- O fallback declarado define `FALLBACK_MIN_SHORTFALL=20` e portanto ignora esse
  caso de seis rações; não foi emitida decisão nem `NO_ACTION` receipt. Isso
  explica a ausência sem atribuir intenção ao ator ou resultado ao provider.
  `provider_available()` também retornou falso no ambiente desta execução. O
  adapter entra no menu mensal provider-enabled pelo código, mas isso não foi
  validado por chamada real neste recorte.
- Comando: `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e280 .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --relief-settlement-id campomanso`. A consulta da falta
  ocorreu após a revisão do ciclo e nenhum save original foi carregado/salvo.
- Gate B permanece aberto porque a resposta comprovada foi uma decisão API e a
  política offline não cobre essa falta menor. Gate de provider real ainda não
  foi executado.

## E279 — relief voluntário reduz a falta por um ciclo — 28/09/2026

- No mesmo harness de clone E277/E278, uma decisão API explícita no dia 300
  selecionou a affordance de distribuir 6 rações de `stock:campomanso`. Decision
  `event:10071`; execução material `event:10072`; fontes: falta/subsistence
  `event:9107`, relatório próprio de Auren `event:9485`, além da decisão.
- O receipt moveu 6 alimentos do estoque público (41.600→41.594) a cinco
  pantries (1/1/1/2/1) para grupos de soldados/dependente. Não alterou contas;
  total monetário ficou igual entre branches.
- Até dia 330, no ramo sem relief, Campomanso continuou com falta 6, health 989,
  unrest 11. No ramo com relief, as pantries já tinham sido consumidas; Campomanso
  terminou falta 0, health 1.000 e unrest 0 (diferença relativa +12/-12). No
  agregado do mundo, falta caiu de 58 para 52. É melhora material de um ciclo;
  não prova continuidade ou escolha por provider/offline. Sem saldo nas coortes,
  a causa pode reaparecer em ciclos seguintes.
- Comando: `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e279-final .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --priority-facility-id works:campos-do-lume
  --relief-settlement-id campomanso`.
  O harness valida Economy e causal history após cada avanço; os três branches
  são cópias efêmeras, não saves de usuário.
- E280 registrado antes de iniciar: observar, sem resposta injetada, se a
  affordance de relief entra na próxima decisão offline quando a falta retorna,
  que opções concorrem e qual decisão/NO_ACTION receipt resulta. Gate B permanece
  aberto até evidência de decisão e repetição sustentada.

## E278 — caixa priorizado não cobre coortes sem renda — 28/09/2026

- O probe E277 foi ampliado para observar, no fechamento do dia 300, estoque
  local, preço, grupos/contas domésticas, compras e `subsistence_resolved`, sem
  mutar o mundo. Com a prioridade de Campomanso, a despensa pública terminou com
  41.600 de 43.000 alimentos; o preço permaneceu 1. A necessidade era 1.101,
  compras cobriram 1.095 e a falta ficou em 6.
- O receipt `event:9107` identifica exatamente as seis unidades não cobertas:
  dwarf soldier 1, elf soldier 1, human dependent 1, human soldier 2, orc
  soldier 1. Os saldos correspondentes eram zero para as quatro coortes de
  soldados; a dependente não tinha conta doméstica. Os grupos agrícolas e
  artesãos com saldo compraram suas quotas. Logo o stock/output já existia e o
  preço estava baixo; o gargalo imediato era acesso das coortes sem recursos,
  não um preço alto nem falta física agregada.
- Após o fechamento, o dono Auren tinha affordances correntes de `relief` para
  6 ou 3 unidades, limitadas pelo relatório próprio e pelo estoque real. Como a
  consulta ocorreu após o turno que gerou esse relatório, isso prova ação
  elegível para o próximo review, não que fallback/provider a escolherá. Nenhuma
  decisão foi executada neste diagnóstico.
- Comando reproduzível:
  `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e278 .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --trace-next-boundary
  --priority-facility-id works:campos-do-lume`.
  O branch foi regenerado em memória; nenhum save de usuário foi lido ou gravado.
- Verificação adicional incluiu o traço datado das compras locais, source IDs,
  payload de falta/affordability e affordances de relief. Próximo E279: exercer
  apenas em clone a affordance de relief 6 via decisão API e comparar até o dia
  330, incluindo uso de pantry/recorrência; isso mede capacidade existente, não
  comportamento espontâneo.

## E277 — precedência explícita no caixa produtivo compartilhado — 28/09/2026

- A prioridade de produção existente agora também expõe opções entre instalações
  próprias que compartilham payroll account, mas somente quando uma instalação
  teve receipt atual `production_limited` com `payroll_funds`. IDs incluem o
  próximo boundary; execução recompõe a affordance e exige decisão corrente
  `ACTOR_DECISION`. Economy persiste um registro por account/boundary, com deltas
  e payload para scope, instalação e data efetiva. O owner altera apenas a ordem
  de avaliação; não reserva saldo, não move trabalhadores entre cidades nem
  promete lote. Economy schema 20/save schema 79 rejeitam versões antigas.
- Probe reproduzível (seed 73 regenerada em memória, sem carregar/salvar save de
  usuário):
  `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e277-final2 .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --priority-facility-id works:campos-do-lume`.
  Captura natural no dia 270, `event:8158`; a affordance API selecionada foi
  `production-priority:pool:polity:auren:treasury:auren:300:works:campos-do-lume`,
  decisão `event:9005`, receipt de prioridade `event:9006`, efetiva no dia 300.
- Resultado no primeiro boundary: controle sem empréstimo produziu 28/3/0
  lotes nas fazendas de Pedra Clara/Montenegro/Campomanso; empréstimo sem
  prioridade produziu 29/3/0; empréstimo + prioridade de Campomanso produziu
  9/1/22. A escolha deslocou 22 lotes para Campomanso, sem elevar output total
  do pool. A falta alimentar permaneceu 129 agregada e 6 em Campomanso nos três
  ramos; dinheiro total ficou 76.000. O receipt local mudou de payroll limitante
  para storage, demonstrando a revalidação do owner, não produção garantida.
- Classificação: decisão API controlada; nenhum provider real ou política
  offline selecionou a prioridade. A affordance fecha a lacuna de escolha sobre
  competição entre cidades e persiste após save/load no teste focal. **Não fecha
  Gate B:** agora é necessário explicar por que o output local não reduziu a
  falta (estoque/capacidade, compra, distribuição e affordability) antes de
  propor outra alavanca.
- Verificações: `tests/test_medieval_production_priority.py`, persistência,
  empréstimos familiares e projeção focal do observatório → 35 passed; o teste
  inclui receipt-gating, decisão, save/load, prioridade efetiva no boundary e
  conservação. O teste inicial da fixture estreita falhou por falta do registry
  no fake; o helper recebeu o estado canônico vazio e a execução focal passou.
- Próximo recorte registrado como E278: rastrear Campomanso no mesmo ciclo desde
  produção local → estoque → quota/compra das famílias → falta/saúde, incluindo
  causas e saldos; não mudar preços, inventário, renda ou regra de compra nesse
  diagnóstico.

## E276 — prioridade produtiva ausente entre cidades — 28/09/2026

- Cenário regenerado pela ferramenta `tools/medieval_family_loan_counterfactual.py`
  (`seed=73`, primeira oportunidade no dia 270, evento `event:8158`). A nova
  seção `production_priority_options_at_source` recompõe o menu canônico antes
  de qualquer decisão e retornou `[]` para Auren. Nenhuma prioridade foi criada.
- As três instalações `works:campos-de-pedra-clara`,
  `works:campos-de-pontenegro` e `works:campos-do-lume` compartilham
  `treasury:auren`, mas estão em assentamentos diferentes. A implementação atual
  agrupa affordances por owner/account/settlement/occupation e exige pelo menos
  duas instalações na mesma chave; portanto o ator não pode priorizar Campos do
  Lume frente às outras fazendas. Porém `_rotated_facilities` rotaciona as três
  pelo mesmo account, criando disputa material entre cidades sem opção política
  correspondente.
- A mudança do utilitário foi validada com
  `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e276-logs .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --trace-next-boundary`; reproduziu produção de 28/3/0
  lotes no controle e 29/3/0 com o empréstimo. Uma prioridade não foi aplicada
  neste trace; ele apenas prova a ausência atual de opção e a competição de caixa.
- Próximo recorte E277: ampliar o `ProductionPriority` existente para escolha
  engine-owned entre instalações próprias que compartilham payroll account,
  habilitada apenas por receipts correntes de payroll limitante; então medir em
  clone se Auren direciona um lote a Campomanso e qual cidade/coorte perde a
  precedência. Não chamar essa decisão preparada de provider ou emergência
  natural.

## E275 — destino do crédito alimentar na primeira fronteira — 28/09/2026

- Baseline recuperável: commit local `6f78ea11`, branch
  `codex/medieval-remote`, sem push. Evidência reproduzida contra seed 73
  regenerada em memória, na primeira affordance de crédito alimentar (dia 270,
  origem `event:8158`); pedido e contribuição API foram feitos somente em clone.
  Nenhum save de usuário foi carregado, gravado ou alterado.
- Comando: `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e275-logs .venv/bin/python -u
  tools/medieval_family_loan_counterfactual.py --seed 73 --days 30
  --max-source-day 900 --trace-next-boundary`. O novo trace registra mudanças do
  saldo e produção de todas as instalações que compartilham a conta.
- O credor `pop:campomanso:orc:farmer` transferiu 40 para
  `treasury:auren` (`event:9004`): saldo de 2.903 para 2.943; a soma de dinheiro
  permaneceu 76.000. Três fazendas usam a mesma conta. No dia 300, o controle
  produziu 28 lotes em Pedra Clara e 3 em Ponte Negro; o ramo do crédito produziu
  29 em Pedra Clara e 3 em Ponte Negro. Campos do Lume, origem do pedido,
  produziu zero em ambos. O crédito permitiu um lote de 100 alimentos em outra
  instalação do mesmo pool, não desapareceu nem foi reservado à fazenda-alvo.
- Na avaliação de Campos do Lume, havia 18 no controle e 22 no ramo do crédito;
  cada lote custa 40. Trabalho disponível era 87 e os limites de capacidade,
  integridade e armazenamento permitiam produção. O único limitador foi
  `payroll_funds=0`. A rotação/ordem do pool e folha compartilhada consumiram a
  liquidez antes do alvo. A falta alimentar agregada ao fechamento foi 129 em
  ambos, portanto o lote extra não reduziu pressão nesse dia.
- Conclusão: a affordance serve apenas como crédito voluntário, fungível, para
  folha alimentar institucional; não promete o lote/local que originou o gatilho.
  Ajustei rótulos e o contexto do credor para explicitar caixa compartilhado,
  ausência de earmark e ausência de resultado garantido. Sem novo mecanismo,
  reserva, política fiscal ou mudança de economia. E274/E275 não satisfazem a
  adaptação sustentada do M1.
- Verificação após a transparência: `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e275-logs
  .venv/bin/pytest -q tests/test_medieval_family_loans.py` → 5 passed;
  `git diff --check` e `compileall` dos três módulos/tool alterados passaram.
  O provider não foi chamado; os resultados são um recorte de uma seed e uma
  fronteira, com escolhas API preparadas, não escolha natural.
- Próximo: E276, recompor no dia 270 as affordances de prioridade de produção e
  testar em clone se existe uma escolha material para priorizar a fazenda local
  sem apenas transferir falta/custo a outra coorte.

## E274 — crédito voluntário para lote alimentar limitado por folha — 28/09/2026

- O contrato do crédito familiar aceitava apenas `unpaid_funds` de contrato
  permanente; um recibo `production_limited` não podia iniciar pedido.
- O mesmo fluxo agora admite `food_production_payroll` somente quando um recibo
  do dia identifica alimento, `batches=0`, `payroll_funds=0` e todas as outras
  capacidades permitem ao menos um lote. O principal é exatamente o salário de
  um lote. A decisão e a oferta familiar continuam independentes; o crédito não
  reserva caixa nem executa produção.
- Save/Economy/Knowledge foram elevados a 78/19/10; os contratos estritos
  rejeitam schema 77/18/9 sem migração. O novo teste preserva dinheiro total e prova que emprestar não
  altera o estoque alimentar nem executa produção.
- A comparação reproduzível `PYTHONPATH=. CWS_DATA_DIR=/tmp/cws-e274-logs
  .venv/bin/python -u tools/medieval_family_loan_counterfactual.py --seed 73
  --days 180 --max-source-day 900` capturou a primeira opção natural no dia 270.
  Uma escolha API de Auren e uma escolha API da família orc agricultora de
  Campomanso financiaram 40; daí em diante ambos seguiram `routine-rules`, sem
  provider. No dia 300, a instalação-alvo continuou em `production_limited`,
  zero batches, `payroll_funds=0`, nos dois ramos. No fim do dia 450, o alvo
  acumulou os mesmos 30 batches; a intervenção teve produção alimentar total
  21.300 vs 25.400 e falta final 427 vs 364. A falta em Campomanso fechou zero
  nos dois, a credora manteve 2.069 contra reserva de 219 e a dívida seguia
  ativa; dinheiro total permaneceu 76.000 em ambos. Houve divergência de eventos
  (16.394/16.017), então este par não estima efeito geral. O recorte não prova
  adaptação estrutural; E274 não fecha M1. Nenhum save foi gravado/alterado.
- Testes focados de empréstimos, observatório e persistência: 38 passed após as
  mudanças de schema/aviso, incluindo rejeição de save schema 76/77 e Economy
  18/Knowledge 9. `git diff --check` e `compileall` dos módulos/tool alterados
  passaram. O provider não foi chamado.

## E273 — menu econômico vigente após E272 — 28/09/2026

- Recompus os menus em clones read-only dos dois saves d1290. Para Auren, ambos
  enumeravam uma contratação em Campomanso: até 3 artesãos anões, salário 2;
  42 opções de reduzir vínculos; nenhum pedido de empréstimo familiar vigente;
  nenhuma prioridade de produção concorrente; e alívio agudo de 15 ou 7 rações.
  Nenhuma vaga atual foi oferecida às coortes agricultoras; Ponte Negro teve
  déficit em fechamentos anteriores, embora estivesse sem falta no d1290.
- A consulta reproduz-se carregando cada `*-day1290.mws` com `load_world`, usando
  `EntityRef("polity", "auren")` nos owners de emprego, staffing, crédito e
  prioridade, e filtrando vagas por `settlement_id == "campomanso"`; alívio usa
  `relief_settlement_options(world, "auren", settlement_id="campomanso")`.
- As cinco coortes consultadas tinham zero `household_provision_options`, mas
  essa affordance é compra pré-paga de provisões para possível migração, não a
  compra de alimento do cotidiano. A compra/atendimento mensal de rações é um
  cálculo material do owner de Economy (`purchase_monthly_rations`); conta
  familiar sem caixa não paga sua quota. Evitar usar o menu de migração como
  prova de inexistência de compra regular.
- Consulta read-only sobre os saves de controle/intervenção E272; nenhuma
  mutação, provider ou alteração de save. Resultado apenas do d1290 e do actor
  Auren. Próximo recorte M1 continua em aberto: descobrir mecanismo elegível
  que conecte renda e acesso alimentar sem tratar alívio pontual nem corte de
  folha como solução sustentada.

## E272 — contrafactual de realocação de folha, seis ciclos — 28/09/2026

- Base: save do dia 1.110 da trajetória E269; controle e intervenção usam o
  mesmo snapshot e seed 101. No clone de intervenção, uma única decisão API
  atual reduziu o contrato de agricultores humanos de Ponte Negro de 180 para
  90 (360 moedas/ciclo nominais). Depois ambos avançaram 180 dias em seis blocos
  retomáveis de 30 dias com `routine-rules`; nenhum segundo ato foi injetado e
  nenhuma chamada de provider foi feita. Saves: `/tmp/cws-m1-reallocation.current/`
  (`control-day1140..1290.mws`, `intervention-day1140..1290.mws`); início da
  intervenção: `intervention-day1110.mws`. O save-base de controle tem SHA-256
  `2b349a99abb8219775d49faf43b02642cefa6ceedd993d0d84c5433e370c07f6`; o clone
  com decisão inicial tem `41d13b665cee7b10b4942aa115a46f7798f5b89cc61807c63f77aca1e2edd502`.
- Cada ramo foi avançado por seis comandos equivalentes:
  `.venv/bin/python tools/medieval_autonomy_smoke.py --days 30 --resume-save <checkpoint> --output <novo-save>`.
  Os saves finais (`control-day1290.mws`, SHA-256
  `4da1195c37d19f0fb1e5411dd0cc92f87138e5847ecef6aae2115b58ccf21a1f`;
  `intervention-day1290.mws`, SHA-256
  `0fa8c10a44d55cc6b7e753c612ea821e2efdaaa1350123b1df3c198a9f24fb14`) foram
  auditados com `.venv/bin/python tools/medieval_causal_audit.py <save>`.
- O fallback escolheu a mesma affordance de emprego para 27 artesãos humanos em
  ambos os ramos, não apenas no ramo reduzido: decisão `event:46647` e criação
  `event:46648` no controle (dia 1.200); decisão `event:47813` e criação
  `event:47814` na intervenção (dia 1.230). Fonte registrada nos dois receipts:
  `fallback / routine-rules / permanent_employment`. Isso prova adoção por essa
  política offline nesse estado, não escolha OAuth/Luna nem ocorrência natural.
- Resultado por checkpoints (soma de falta alimentar de todas as cidades em
  cada leitura): controle/intervenção d1140 `3255/3219`, d1170 `1899/1935`,
  d1200 `2665/2665`, d1230 `1558/1558`, d1260 `2844/3010`, d1290 `1564/1453`.
  Soma das seis leituras: `13.785/13.840`, 55 rações pior na intervenção.
  No dia 1.290 a falta mundial era `481/387`, mas o ganho final não apaga as
  janelas intermediárias piores. A coorte humana agricultora cortada terminou
  com caixa `5.171/2.180`; a coorte de agricultores anões de Ponte Negro somou
  `135/207` rações não atendidas nos fechamentos, 72 a mais na intervenção.
- Houve mais lotes produzidos no recorte em Campomanso/Ponte Negro (`61/27`
  controle; `87/65` intervenção). Isso não melhorou a série de falta sem custo
  distributivo. Saúde média mundial no dia 1.290 foi `450,00/451,75`, falta
  local em Ponte Negro `96/0`, mas falta local em Campomanso `15/15`; mortes por
  privação acumuladas terminaram `192/192`. Uma affordance pode elevar produção
  e melhorar o snapshot terminal enquanto piora acesso em outra coorte/janela.
- Os dois saves finais passaram `tools/medieval_causal_audit.py`: controle
  50.500 eventos; intervenção 50.527; zero causas quebradas, erros de autoria,
  origem sem fonte, erros de fonte, Story material, interpretação material e
  mutações materiais sem raiz. Cada avanço de 30 dias também passou o smoke de
  conservação e equivalência save/load/continuação (`tools/medieval_autonomy_smoke.py`);
  nenhum provider foi chamado.
- Conclusão: o experimento E272 foi concluído e falsificou a hipótese de que
  esse corte específico fecha M1. A contratação apareceu nos dois ramos e a
  intervenção elevou produção, mas a soma das faltas piorou 55 e uma coorte
  distinta acumulou mais 72 ração de acesso não atendido. Sem mudança de código
  neste recorte; não generalizar para toda realocação possível. M1 continua
  aberto. Próximo: identificar outra affordance atual capaz de conectar caixa,
  emprego e compra sem ocultar custo em coortes vizinhas.

## E271 — oportunidade e custo de realocação salarial — 2026-09-28

- Inventário read-only das affordances de staffing para Auren no ramo E269 do
  dia 1.110. Nenhum emprego local era financiável: a conta tinha 2.223 moedas
  frente a custo comprometido de 2.432/ciclo. Uma opção atual reduz o contrato
  `pop:pontenegro:human:farmer` de 180 para 90, economizando 360/ciclo. O grupo
  tinha 5.584 moedas e zero falta alimentar local no último fechamento (a cidade
  tinha falta residual apenas em coortes de soldados/dependentes). O corte,
  contudo, retira salário de 90 trabalhadores; caixa presente não prova ausência
  de dano futuro.
- A opção estava causalmente habilitada por `event:41757`, uma limitação de
  produção na oficina de toolmaking de Campomanso com `payroll_funds=0`. A conta
  após o corte ficaria em 2.072/ciclo, permitindo pela guarda atual financiar
  uma vaga local para os 27 artesãos humanos (custo 54/ciclo), se a affordance
  for recomposta e continuar elegível. A realocação abre um caminho entre
  assentamentos, mas não há prova de que a política offline o escolherá nem de
  que o emprego resultante compensa a renda perdida.
- O teste pareado está registrado em E272 acima. M1 não foi fechado porque o
  saldo de produção e o snapshot final melhoraram, mas as seis leituras somadas
  pioraram e uma coorte distinta acumulou falta adicional.

## E270 — affordances para a privação residual — 2026-09-28

- Inspeção read-only do ramo de intervenção E269 no dia 1.110. A soma de
  `unmet_by_group` em Campomanso é 237; os maiores déficits são 166 anões
  agricultores e 54 humanos artesãos. Os grupos afetados com conta familiar
  tinham saldo zero e `household_provision_options` vazio. Não usar capacidade
  de pantry como quantidade de alimento: este recorte avaliou affordance e caixa.
- Recompostos os menus atuais para todos os polities/organizations com autoridade:
  nenhum oferecia emprego permanente local em Campomanso. A conta `treasury:auren`
  tinha 2.223, mas custo mensal comprometido 2.432, então a guarda de fundos do
  owner bloqueava nova contratação. Opções de staffing existentes só reduziam
  vínculos atuais. Isso comprova limitação do menu naquele snapshot, não ausência
  de resposta em todos os meses ou assentamentos.
- `family_loan_request_options` de Auren estava vazio, sem contratos `unpaid_funds`
  atuais ou pedido aberto; a via de crédito já implementada não podia financiar
  nova vaga neste instante. Não houve mutação nem chamada de provider.
- Diagnóstico: havia recursos domésticos concentrados em outros grupos, mas não
  havia conexão canônica disponível naquele checkpoint para transferir renda a
  esses dois grupos sem realocar folha. O helper `household_provision_options`
  consultado ali refere-se a provisões de viagem/migração, não às compras
  mensais de subsistência, que são executadas automaticamente pelo owner Economy.
  Esta evidência justifica investigar realocação via staffing ou a lacuna de
  elegibilidade do crédito existente; não autoriza criar subsídio automático.
  M1 segue aberto.
- Próximo recorte: contrafactual focal de reequilíbrio de vínculos atuais versus
  nenhuma mudança, acompanhando as famílias que perderiam salário e as que
  poderiam ganhar acesso. Não executar até definir opções e contrafactual pelo
  mesmo save; decisão deve continuar explícita e owners devem revalidar.

## E269 — emprego local pareado por seis ciclos — 2026-09-28

- Controle e intervenção partiram do mesmo save local do dia 930
  (`/tmp/cws-m1-delivery.5GYXrp/day0930.mws`), avançaram 180 dias pelo
  `MedievalSimulator` com a mesma política offline, em processos separados.
  Apenas a intervenção recebeu uma decisão API no dia 931: ID vigente para
  emprego permanente do grupo `pop:campomanso:orc:artisan`, 31 pessoas, salário
  2 por trabalhador (folha bruta 62/ciclo). Autoridade/conta/limite foram
  recompostos pelo owner. Os saves finais são
  `/tmp/cws-m1-six-cycle.current/control.mws` e `intervention.mws`.
- Falta alimentar de Campomanso no controle/intervenção em cada fechamento:
  dia 960 `398/434`; 990 `576/513`; 1020 `107/107`; 1050 `197/181`; 1080
  `256/193`; 1110 `302/237`. Portanto, a primeira janela piorou 36; as cinco
  seguintes foram iguais ou melhores, e no fim a intervenção teve 65 menos de
  falta e saúde 511 contra 498. Não zerou a privação: faltaram 237 rações no
  estado final.
- No dia 1.110, o grupo de artesãos orcs tinha 68 moedas de caixa familiar
  (controle: zero); caixa de agricultores ficou igual nos dois ramos (3.662).
  Compras alimentares do ciclo foram 941 contra 876; estoque público terminou
  em 17.316 contra 17.679, e tesouro em 2.223 contra 2.174. Os resultados
  preservaram dinheiro, não criaram recurso grátis, mas a queda de estoque
  público e a pressão residual impedem declarar recuperação estrutural.
- A trilha inclui affordance/decisão `event:34070`, criação de contrato
  `event:34071`, seis receipts pagos do contrato (`event:34424`, `35899`,
  `37319`, `38848`, `40307`, `41679`) e caminho causal de folha → salário →
  compra familiar → subsistência (por exemplo, `event:34424` → `35897` →
  `36000` → `36001`). Os dois saves terminaram no dia 1.110 com auditoria
  `ok=true`: controle 42.884 eventos, intervenção 42.928; zero causas quebradas,
  autoria/fonte inválida, Story/interpretation material ou material sem raiz.
- Limites: decisão API preparada, não escolha natural ou provider; um save/seed;
  fallback offline continuou nos dois ramos; a intervenção acrescenta uma
  contratação e não mede sensibilidade a outras prioridades. Este experimento
  fecha apenas o recorte comparativo de seis ciclos, não o aceite de M1.
- Próximo M1: diagnosticar a pressão residual por coorte e verificar se outra
  affordance já existente conecta renda/produção àqueles grupos sem transferir
  privação. Depois observar a escolha no fluxo normal/provider dentro do saldo
  autorizado; não criar nova mecânica sem demonstrar uma lacuna material.

## E268 — auditoria dos ramos econômicos até o dia 1.110 — 2026-09-28

- Auditoria standalone dos saves `/tmp/cws-m1-sixmonth.gGbPzF/control-day1110.mws`
  e `intervention-day1110.mws`; ambos carregaram no schema atual e retornaram
  `ok=true`. Controle: 42.055 eventos; intervenção: 42.884. Em ambos houve
  zero causas quebradas, erros de autoria/fonte, Story material,
  interpretação material ou eventos materiais sem raiz. Os saves originais
  permaneceram apenas lidos.
- No estado comparado, controle terminou com saúde média 571, falta 0 e caixa
  familiar 11.551; intervenção terminou com saúde 498, falta 302 e caixa familiar
  3.698 (artesãos 36, agricultores 3.662), apesar de estoque público de alimento
  17.679. Os números vêm do resumo determinístico da execução registrada no
  checkpoint anterior; a auditoria desta entrada confirma causalidade, não os
  recalcula.
- Limite importante: isto não é um par contrafactual válido de decisão única.
  Controle partiu do save do dia 480, enquanto a intervenção incluiu escolhas
  explícitas em 510/660/870 e continuou depois do dia 930 sob fallback offline.
  O resultado mostra apenas que essa trajetória de obra/cortes não sustentou
  acesso alimentar; não demonstra que contratar artesãos piora por si só, nem
  que o ator recusou contratação.
- Laya/Herdr não está disponível entre as ferramentas desta sessão; nenhuma
  revisão Laya foi executada. O teste de provider real autorizado anteriormente
  não foi repetido neste recorte.
- Próximo recorte M1 (`E270`): mapear a privação residual a affordances/custos
  atuais antes de escolher outra ação. M1 permanece aberto.

## E265 — checkpoint local e reconciliação inicial M0 — 28/09/2026

- Checkout preservado sem alterar o branch: `codex/medieval-remote`, HEAD
  `51c213dfd11e891f2e0e5d73f79fc54da9b09035`, 274 caminhos no status antes
  deste registro. Snapshot recuperável em `/tmp/medieval-m0-checkpoint.refkrM/`:
  `tracked.patch` é patch binário relativo ao HEAD, `untracked.tar.gz` contém
  23 arquivos novos, e `status.txt`, `head.txt`, `branch.txt`, `SHA256SUMS`
  registram identificação e integridade.
- `git apply --check --reverse tracked.patch` passou contra o worktree atual;
  `sha256sum -c SHA256SUMS` passou e o tar lista 23 arquivos. O snapshot registra
  o WIP antes da edição deste próprio diário/matriz. Não houve commit/push/merge.
- Referências de execução apontam para `medieval-completion-contract.md`;
  E199/E200 são evidência histórica e não gate atual.
- Limite naquele checkpoint: E244–E255 ainda não estavam reconstruídos; E266
  resolveu somente a parte recuperável. O crosswalk então era inicial e precisava
  classificar todos os requisitos antes de M1.

## E266 — recuperação e classificação dos artefatos E244–E255 — 28/09/2026

O diretório versionado de evidências não tinha entradas individuais E244–E255.
Inspecionei os artefatos preservados e rodei `tools/medieval_causal_audit.py`
read-only nos dez saves disponíveis. Todos carregaram no schema atual e
retornaram `ok=true`, zero broken causes, autoria inválida, Story material ou
interpretação com material:

| IDs/artefatos recuperados | Dia | Eventos / materiais |
|---|---:|---:|
| E245 controle 30d | 990 | 39.856 / 29.840 |
| E245 auxílio 30d | 990 | 39.886 / 29.872 |
| E247 prioridades | 480 | 18.015 / 12.343 |
| E248 prazo de compromisso | 510 | 18.981 / 12.867 |
| E249 segunda resposta | 480 | 17.988 / 12.315 |
| E251 prioridades | 480 | 18.014 / 12.341 |
| E252 seed 101 | 480 | 18.118 / 12.464 |
| E253 seed 14 | 480 | 17.279 / 11.815 |
| E254 seed 101, request-ready | 480 | 18.122 / 12.466 |
| E255 seed 14, request-ready | 480 | 17.283 / 11.817 |

E244 (`/tmp/cws-e244-inspect-data`), E246 (diretórios de auditoria/intervalo)
e E250 (`/tmp/cws-e250-locations-data`) não conservaram save/relatório
reproduzível; o único log E250 tem 79 bytes e nenhum conteúdo de resultado.
Esses três números ficam como histórico não verificado. A auditoria posterior
dos saves prova integridade dos arquivos atuais, não reconstitui as ações,
menus ou conclusões originais de E244/E246/E250, nem converte fixtures em
evidência natural. A referência de E243 a arquivos prefixados E245 descreve
auditorias que ficaram com nomes de artefato posteriores; preservo a sequência
original e registro aqui a associação explícita.

A matriz agora classifica os artefatos recuperáveis; E267 fecha o crosswalk
detalhado dos requisitos do roadmap. E199/E200 continuam apenas gate técnico
histórico. O próximo marco aberto é M1: isolar caixa/folha/renda e medir uma
resposta estrutural sem confundir fallback de auxílio.

## E267 — crosswalk dos requisitos do roadmap — 28/09/2026

Revisei as sete seções numeradas (0–6) de `docs/handoff/medieval-roadmap.md`
contra M0–M8 do contrato. A matriz registra por seção os marcos responsáveis,
owners/integradores, evidência presente e lacuna/limite. Capacidades com vários
subrequisitos permanecem explicitamente abertas nos checklists de seus marcos;
`existente` não foi tratado como aceite. M0 fecha o inventário documental e
checkpoint, não certifica owners nem gates de runtime. `git diff --check`
passou após a edição. O snapshot E265 identifica o WIP anterior às edições
posteriores e não substitui os arquivos ativos.

## Retomada do roadmap maior — 27/09/2026

O Gate D técnico da V1 foi fechado no E200; isso não encerra o roadmap do
produto nem certifica a saúde econômica. O checkout atual está na branch
`codex/medieval-remote`, HEAD `51c213df`, com WIP anterior preservado. E201
acrescentou crédito familiar voluntário para fixture preparada. E207 corrigiu
o lifecycle para aceitar contribuições independentes de várias famílias,
limitadas ao principal remanescente e com encerramento somente quando totalmente
financiado ou expirado. Fixture de duas famílias e save/load passaram. E205/E206
encontraram recibos de folha sem fundos em trajetórias offline, mas o caixa já
havia se recuperado no momento do turno; não houve oferta/pedido e isso não
prova recusa nem adoção espontânea.

O save atual usa schema 78, Economy 19 e Knowledge 10; saves anteriores são
rejeitados sem migração. O WIP amplo não foi commitado, enviado ou implantado.

### E206–E209 — 27/09/2026

E206 rodou dois preflights offline independentes (seeds 101 e 137) até o dia
480. Ambos passaram checkpoints de conservação/save-load e auditoria causal; os
recibos `unpaid_funds` apareceram antes do turno em que opções de empréstimo
seriam compostas. No dia 480 havia zero opção/pedido/loan. Resultado: reforça o
diagnóstico de timing, não mostra comportamento de ator.

E207 mudou `FamilyLoanRequest` para armazenar vários IDs de empréstimos e estados
`open`, `partially_funded` e `funded`. Uma família fecha apenas seu próprio
aviso ao contribuir; os demais podem avaliar o saldo restante. Uma mesma família
só pode contribuir uma vez, cada valor é revalidado contra caixa disponível e
principal remanescente, e o pedido fecha exatamente ao completar o valor. Save
schema 76/Economy 18 rejeita a forma anterior; Knowledge continua schema 9. O
teste de fixture com duas famílias passou junto aos testes focados de folha e
agenda (32 no total), incluindo save/load da coleção de empréstimos. Nenhuma
decisão natural/provider adicional foi executada; adoção e efeito macroeconômico
continuam abertos. Também foi verificado que uma oferta do segundo grupo
composta antes da contribuição inicial fica stale depois dela e é rejeitada sem
mudança de saldo ou evento.

E208 estendeu a fixture para um contrafactual sem empréstimo. Após duas
contribuições cobrirem o pedido de 284, o relógio avançou um ciclo: a conta paga
folha bruta 284 e o grupo empregado recebe salário. No clone sem contribuições,
o mesmo contrato registra `unpaid_funds` e não cria payroll. Os dois estados
passaram validação de Economy e Knowledge. É prova do mecanismo e de sua
consequência material sob fixture, não de seleção natural ou recuperação
macroeconômica.

E209 ajustou verificações que ainda assumiam save schema 74 ou Economy 16.
Agora o teste de load rejeita explicitamente schema 75 e confirma que o arquivo
não foi alterado; a economia rejeita schema 17; o teste de save/load da consulta
observacional exige o schema 76 corrente. Verificação focada: 22 testes de
persistência, crédito familiar e save/load observacional passaram.

E210 rodou a seed 73 sem provider nem decisões injetadas do dia 0 ao 480 no
schema 76. Os quatro checkpoints passaram conservação e save/load; auditoria
standalone final retornou `ok=true` em 17.984 eventos e 12.313 eventos materiais,
sem causas quebradas, material sem raiz, erros de autoria/fonte, Story material
ou interpretação material. Houve zero mortes por privação, falta alimentar
acumulada 1.148, saúde média 865 e unrest médio 70,38. Save: 5.812.224 bytes;
pico de memória: 340.959.232 bytes; duração: 68,67s; p95 mensal: 4,7549s.
É evidência de smoke curto no checkout atual, não do gate de 3.600 dias, da
adoção de crédito ou de resiliência econômica. O diagnóstico natural de pedido/
empréstimo continua aberto.

## E211 — continuação natural schema 76, seed 73, dia 480→600 — 2026-09-27

- Retomado o save E210 por 120 dias, offline `routine-rules`, sem provider nem
  decisões injetadas. Checkpoints 510/540/570/600 passaram conservação e
  save/load; o save final tem 22.481 eventos e 6.959.104 bytes. Auditoria
  standalone: `ok=true`, 15.549 eventos materiais, zero causas quebradas,
  material sem raiz, erros de autoria/fonte, Story material ou interpretação
  material. 0 chamadas reais.
- Não houve pedidos nem empréstimos familiares. Os 22 receipts
  `permanent_employment_unpaid` foram registrados entre os dias 480 e 600.
  No checkpoint do dia 510, cinco contratos registraram folhas não pagas, mas
  a conta de Escarlia já tinha 1.670 moedas, suficiente para os 1.424 de folha
  bruta somada desses contratos. Como o empréstimo exige shortfall atual no
  turno do ator, nenhuma opção válida apareceu. Portanto esses receipts são
  sinais de limitação transitória durante a ordem de produção/pagamento, não
  evidência de caixa insuficiente persistente nem de recusa de crédito.
- Apesar de zero mortes por privação, a soma da falta alimentar nos quatro meses
  da continuação foi 3.244. E210 soma 1.148 em dezesseis meses, portanto as
  janelas não são diretamente comparáveis; isso apenas confirma falta material
  nos meses recentes. Saúde média final caiu de 865 para 775,75 e unrest médio
  subiu para 105,88. Isso mantém aberto o Gate B: a
  pressão relevante neste recorte é acesso/subsistência, não um déficit de caixa
  do empregador que justifique abrir crédito familiar.
- Run total: 65,06s, p95 mensal 5,7493s, pico de memória 451.342.336 bytes. O
  gate de 3.600 dias, adoção de crédito e provider real permanecem abertos. Sem
  commit, push ou deploy.

## E212 — diagnóstico de acesso e prioridades de folha no save E211 — 2026-09-27

- Consulta somente leitura ao save do dia 600. Os oito estoques públicos locais
  somam 158.613 alimentos para 10.879 moradores; em cada assentamento o estoque
  público excede a população local. Ainda assim, a soma de `missing_food` do
  mês é 815, concentrada em Cinzaverde (438) e Pontenegro (363); saúde final é
  668 e 763 nesses locais. Portanto não é uma falta agregada de estoque físico.
- `public_food_access_projection` (somente observatório Dao, não conhecimento
  de NPC) estima 5.734 rações públicas inacessíveis pelo saldo atual antes de
  descontar provisões privadas/ajuda. O caixa de grupos artesãos soma 0 em
  Pedraclara (1.426 pessoas), 17 em Portovelho (1.181) e 55 em Ferroalto
  (1.367), enquanto agricultores concentram caixa. Esses números contextualizam
  desigualdade de compra; a projeção não é falta canônica nem opção do ator.
- No recibo do dia 600, a tesouraria de Escarlia iniciou os pagamentos em 1.868.
  Contratos agrícolas de Brumafria foram pagos primeiro; após a folha de
  agricultores de Cinzaverde, o saldo chegou a zero e os três contratos
  artesãos de Ferroalto registraram `unpaid_funds`. Compras de rações depois
  repuseram a conta a 2.661. As instalações produtivas registraram
  `payroll_funds` como limitação, com uma exceção que completou três lotes.
- Recompus o menu atual de Escarlia: 30 opções válidas de staffing (10
  suspensões e 20 reduções), com relatórios datados de Brumafria, Cinzaverde e
  Ferroalto e contexto do empregador mostrando standing payroll 3.626 contra
  saldo 2.661. No dia 600 também havia uma affordance de oficina em Pedraclara
  para Auren e outra em Cinzaverde para Escarlia; nenhum vínculo novo estava
  elegível. Isso prova que há caminhos enumerados para revisar compromissos e
  investir, mas não que uma IA escolheu ou que esses caminhos resolverão a
  pressão. Nenhuma opção foi executada; nenhuma LLM foi chamada.
- Conclusão E212: a camada observada é fluxo de renda/caixa e distribuição de
  acesso sob compromissos concorrentes, não ausência agregada de comida. A
  ordem de liquidação atual é determinística e por ID de contrato; a sequência
  do dia 600 mostrou agricultores pagos antes de artesãos. Isso merece revisão
  da prioridade/compromissos como regra do owner, mas não justifica substituir
  omissão do fallback por subsídio, renda ou rateio automático.

## E213–E214 — contrafactual de staffing e reparo do elo causal — 2026-09-27

- A partir do mesmo save E211/dia 600, comparei controle e uma intervenção API
  explícita que suspende `employment:pop:brumafria:dwarf:farmer`. Não houve
  provider nem escolha espontânea. O simulador avançou ambos os ramos ao dia
  638; no ciclo relevante, falta alimentar agregada foi 846 no controle e 681
  na intervenção, saúde média 758,88→760,00 e unrest 123,12→122,00.
- E213 revelou uma lacuna real de `why()`: o owner material produzia mais e
  pagava salários, mas a produção não citava a pausa que liberou o caixa. E214
  passou a incluir como causas da produção somente recibos de pausa do mesmo
  `payroll_account_id` e do mesmo dia, sem incorporar decisões de outras contas
  nem recibos antigos.
- Teste focal verifica decisão → `employment_staffing_changed` →
  `permanent_employment_paused` → produção → `wages_paid`; no cenário pareado,
  a alcançabilidade também chega a compras domésticas e `subsistence_resolved`.
  O módulo `tests/test_medieval_permanent_employment.py` passou: 22 testes.
- Saves pós-correção em `/tmp/cws-e214-control-day0638.mws` e
  `/tmp/cws-e214-choice-day0638.mws`. Auditorias standalone dos dois ramos:
  `ok=true`, 23.658/23.684 eventos, zero causas quebradas, erros de
  autoria/fonte, Story material ou interpretação material. A intervenção é
  contrafactual explícita, não prova adoção natural nem provider real.
- Sem commit, push ou deploy; o WIP preexistente continua preservado.

## Retomada do plano Medieval V1 — 25/09/2026

O plano operacional canônico é [medieval-finalization-plan.md](medieval-finalization-plan.md).
Na retomada, o checkout está na branch `codex/medieval-remote`, HEAD `51c213df`;
`git status --short` lista 244 entradas (239 rastreadas modificadas e 5 novas),
com `git diff --shortstat` de 239 arquivos, 15.996 inserções e 1.439 remoções.
Esse é um baseline do WIP misturado no checkout, não atribuição deste goal; nada
foi resetado, commitado, enviado ou implantado. O save seed 73/dia 1.560
continua disponível em `/tmp/cws-medieval-final-seed73-3600-current-20260925.checkpoint-day-01560.mws`.

**Revisão de critérios do plano — 25/09/2026:** o documento canônico foi
ajustado para separar plano, matriz e diário; tornar explícita a capacidade
adaptativa econômica (uma tragédia explicável não passa se meios existentes não
podem alcançar as famílias); detalhar decisões independentes de autoridade,
QG e comandante no cenário autônomo; e exigir o limite transacional comum em
novos owners materiais V1. O escopo V1 e os limites provisórios de desempenho
ficam explícitos antes dos smokes finais. Nenhum gate técnico foi fechado por
esta revisão. E126 registra a auditoria focal; E127 registra a mudança do plano.

No checkpoint E125, a entrega 1 (baseline e links) foi conferida; o inventário
transversal e o limite material comum ainda estavam abertos. Depois, E136/E137
fecharam esses dois entregáveis no escopo V1, com cobertura antiga parcial
nomeada na matriz. `task-orchestration` foi
recarregado da skill local. A tentativa de consultar o servidor Herdr retornou
`PermissionDenied`; a inferência MetaGame/Laya deste checkpoint não foi
executada e não é presumida. Evidência E125 registra a verificação. Isso não
altera a execução do jogo.

**E126 parcial — auditoria de classes de delta:** reauditei o save existente
com `tools/medieval_causal_audit.py` no checkout atual: dia 1.560, 65.130
eventos, 49.946 materiais, 61 tipos de evento material e 183 grupos
`evento × owner_kind × aspecto × origem`; 786 materiais atribuídos a decisão e
49.160 determinísticos. Resultado `ok=true`, sem causas quebradas, erros de
autoria/source, roots inválidas/ausentes, Story material ou interpretação
material. O auditor agora expõe amostras de owner/event IDs e contagens por
grupo. Isto é inventário de histórico exercitado, não a lista completa de
callsites futuros, nem prova de atomicidade ou validação por owner. O teste
focal `tests/test_medieval_causal_audit.py` passou (`3 passed`) em
`CWS_DATA_DIR=/tmp/cws-medieval-c105-tests`; a primeira tentativa sem esse
namespace falhou na importação porque o logger tentou escrever na pasta padrão
somente leitura, antes dos testes começarem.

**E128 parcial — primeiro elo limitante econômico:** rastreamento read-only do
save dia 1.560 identificou em Campomanso 164 rações faltantes apesar de 9.313
no estoque final; compras registradas foram só de coortes agrícolas, enquanto
artesãos/dependentes/soldados estavam sem saldo. Em Cinzaverde, a conta de
Escárlia zerou antes de payroll/produção limitada por caixa, seguida de 459
rações faltantes e 17 mortes. As affordances recomputadas permitem reduzir
contratos agrícolas, mas não oferecem transição/migração às coortes sem renda.
Isso sustenta distribuição/acesso como causa direta local e revela possível
falta de ação adaptativa; não demonstra causalidade geral. O contrafactual de
um mês ainda não foi rodado, a análise veio de investigador read-only, e o
Gate B permanece aberto. Os eventos e limites estão em `.agent/tasks/medieval-world-simulator/evidence.md` E128.

**E129 parcial — fontes estáticas dos eventos materiais:** criei
`tools/medieval_material_inventory.py` para enumerar chamadas candidatas a
evento com delta, incluindo os wrappers materiais usados por economia, frete,
migração e força. O scanner encontrou 226 callsites candidatos, 222 nomes de
evento visíveis e seis pontos com nome dinâmico. Cruzado com o mesmo save do
dia 1.560, todos os 61 tipos emitidos e os 183 grupos de delta têm nome
estático correspondente; 161 nomes candidatos não aparecem nessa trajetória.
Isso não atesta que todos esses candidatos emitam delta, sejam alcançáveis ou
tenham owner/autoria/atomicidade corretos. As seis expressões dinâmicas estão
listadas pelo comando e seguem para análise de caller; o Gate A fica aberto.
Ruff e `git diff --check` passaram para o scanner; a auditoria do save segue
`ok=true`. A prova de correspondência detalhada pode ser refeita com
`--details` no mesmo comando.

**E130 parcial — classificação por famílias:** produção/consumo/mercado,
frete, construção/infraestrutura, ajuda/compromissos, autoridade/alfândega,
força/campanha e civismo foram classificados com owners, fontes, revalidação,
deltas, fronteira transacional e testes negativos existentes na matriz.
Os seis nomes dinâmicos têm callers delimitados; os 161 nomes ausentes do save
permanecem como não exercitados, sem inferir falha. A classificação é read-only
e não reexecutou todos os testes citados. Gate A ainda aberto.

**E131 parcial — atomicidade da migração direta:** teste novo reproduziu que
viajante nomeado inválido deixava `migration_authorized` após a rejeição.
`start_migration` agora executa em candidato por `material_execution.execute_material`;
o limite valida owners, atividades e sufixo causal antes de publicar. Outro
teste força falha de validação depois do efeito material no candidato e exige
snapshot publicado idêntico. Migração + conhecimento: `26 passed` em 11,33 s;
Ruff nos arquivos novos/teste e `git diff --check` passaram. Ruff do módulo
`migration.py` ainda acusa `F841` em `food_bulk` preexistente e não relacionado;
não foi ocultado como verde. Isto prova um primeiro owner direto, não a
atomicidade transversal nem o orçamento de desempenho.

**E132 — mercado sem consulta repetida:** no checkout atual, o filtro de
pedidos já apresentados ao vendedor já existia. A regressão integrada nova
restringiu o turno mensal a comprador/vendedor de mercado, orçamento de duas
chamadas, comprador pedindo compra e vendedor escolhendo `NO_ACTION`.
Houve exatamente duas consultas, nenhuma terceira consulta e nenhum pagamento;
`test_medieval_market_purchase_policy.py` + agenda passaram `11` testes no
recorte. Não foi uma consulta OAuth real nem prova de todos os menus.

**E133 parcial — recuperação de migração:** reproduzi uma falha após
`migration_return_started` e atualização da agenda/provisão que deixava o
world publicado diferente do snapshot anterior. `recover_migration` agora
reutiliza `execute_material`; uma exceção posterior ao efeito no candidato
deixa o world publicado inalterado. Migração, conhecimento de migração e
compra bilateral passaram `33` testes em 14,45 s. A validação focada continua
sem substituir inventário de outros owners ou smoke longo.

**E134 parcial — resposta econômica em holdings naturais:** reexecutei
`test_unmodified_seed_can_fund_workshop_and_pay_artisans_without_extra_resources`
no checkout atual (`1 passed, 20 deselected`, 31,87 s). A seed 73 não recebe
recursos extras: IDs atuais abrem oficina e linha, trabalho paga artesãos,
famílias compram mais alimento e aos 390 dias a falta é menor que no controle
`NO_ACTION`. Save/load e auditoria fazem parte do teste. A saúde pode chegar
ao piso nas duas trajetórias; as escolhas foram por stub, não provider real.
O caso não resolve o primeiro elo limitante de Campomanso/Cinzaverde nem fecha
o Gate B.

**E137 — inventário Gate A finito:** a matriz agora classifica oito famílias
de transições por owner, origem/knowledge, revalidação, delta, transação e
negativa. Os 161 nomes estáticos ausentes da seed 73/dia 1.560 se distribuem
em 52 módulos; os maiores blocos são força 22, alfândega 10, criaturas 9,
abastecimento de campanha 8 e movimento cívico 8. Reexecutei dez testes
negativos focados de força, customs e criatura (`10 passed` em 6,01 s).
Entrega 2 fecha como **inventário/classificação**, não prova semântica integral
dos executores não exercitados ou de emergência natural.

**E136 — limite comum direto reforçado:** `execute_material` recusa operação
sem receipt material ou transição sem causa; o owner continua responsável por
revalidar affordance e lei física no candidato. Dois negativos exigem snapshot
inalterado. Com migração e conhecimento de migração, `29 passed` em 11,91 s;
Ruff e `git diff --check` passaram. `AGENTS.md` exige esse limite para novos
comandos materiais diretos V1. Entrega 3 fechada nesse escopo; owners antigos
e inventário semântico do Gate A continuam abertos.

**E135 — diagnóstico reproduzido do primeiro elo econômico:** carreguei
read-only o checkpoint seed 73/dia 1.560 e comparei `public_food_access_projection`,
contas/coortes, facilities, leitura local do administrador e affordances
recompostas. Campomanso: 9.313 rações públicas/preço 1, falta canônica 164;
artesãos 153 sem renda, dependentes dois e soldados nove também com caixa zero;
farmeiros mantêm 16.070 moedas. Facility local paga só agricultores.
Cinzaverde: `event:64122` zerou o tesouro de Escárlia após pagar uma coorte em
Ferroalto; `event:64177` limitou a produção local por `payroll_funds`; vendas
posteriores voltaram a trazer dinheiro, tarde para aquela produção. Sua falta
canônica é 459 e houve mortes em `event:64339`. Ambas as administrações têm
leitura própria do dia e affordance atual de oficina, mas nenhuma opção de
emprego artesão antes de haver site apto. O save está `ai_enabled=False` e
não selecionou a obra. Projeção de acesso não é conhecimento dos atores e,
especialmente em Cinzaverde, seu número após consumo/mortes não é a falta
canônica daquele instante. O diagnóstico fecha a entrega 4 apenas para esses
dois casos; a entrega 5/recuperação ampla permanece aberta.

**E138-finalização parcial — cenário autônomo controlado de interferência:**
adicionei uma regressão em `test_medieval_campaign_creature_interference.py`.
Antes da linha de início, a fixture prepara ocupação, rota alternativa fechada,
pedido da criatura, plano defensivo e compra de alimento. Depois dela, apenas
`MedievalSimulator.step` e escolhas por IDs oferecidos ao provider stub atuam:
autoridade política autoriza, QG mobiliza a coluna, a criatura restringe a
passagem, a carga atrasa e o fechamento mensal registra falta de alimento em
Portovelho. O evento de restrição é causa navegável do atraso e da subsistência;
save/load preserva snapshot e links. `1 passed, 1 deselected` em 2,69 s com
`CWS_DATA_DIR=/tmp/cws-medieval-c105-tests`. Isto é **fixture autônoma com
provider stub**, não provider real nem emergência natural. A campanha ainda não
nomeia um comandante por decisão autônoma nesse fluxo; não houve contrafactual
pareado nele. Gate C e entrega 6 permanecem abertos.

**E139-finalização — Gate C controlado, não natural:** conectei as opções já
existentes de nomeação ao turno de mobilização do QG. O provider recebe um menu
institucional atual e pode nomear ou escolher `NO_ACTION`; o owner de comando
revalida pessoa, cargo e presença antes de criar o comando material. Na mesma
fixture autônoma, um comandante elegível está presente como premissa inicial.
Depois da linha de início não há decisão ou executor injetado: autoridade
política autoriza, QG mobiliza e nomeia, criatura restringe a rota, a carga
atrasa, a coluna é detida, o comandante escolhe `NO_ACTION` diante da leitura
local e o QG escolhe aguardar diante de seus próprios relatórios. A falta
alimentar civil é consequência da restrição; os recibos de comandante e QG
têm o bloqueio em sua ancestralidade. `causal_view`, save/load e auditoria do
save passam. O teste físico pareado pré-existente compara a rota aberta com a
fechada; a nova trajetória não possui controle autônomo pareado. Regressão
focada de interferência, estratégia e comando: `31 passed` em 23,07 s; Ruff
e `git diff --check` passaram. Entrega 6 fecha **só como cenário autônomo
controlado com provider stub**. Item 7 (formação natural), item 8 (provider
real) e gates econômico/operacional permanecem abertos.

**E140-finalização — Gate B adaptativo, resultado limitado:** no checkpoint
seed 73/dia 1.560, Campomanso tinha falta 164, saúde 434 e 153 artesãos sem
salário local, apesar de comida pública. A affordance de oficina é válida,
mas não cria capacidade ou emprego sozinha; faltavam 48 madeiras locais. O
diagnóstico `tools/medieval_economic_counterfactual.py` carrega o mesmo save
duas vezes, sem alterar o arquivo-fonte. Na intervenção controlada, o
administrador decide a obra; comprador e vendedor aceitam separadamente a
compra de 48 madeiras por 96 moedas na rota real Salgueiro–Campomanso. Após
30 dias pelo engine, a obra avançou 4/12 unidades e seu payroll pagou 24
moedas a 12 artesãos; a falta ficou em 150 e a saúde em 423. No controle
`NO_ACTION`, falta 164 e saúde 422. Diferenças: menos 14 rações faltantes e
mais 1 ponto de saúde, não recuperação completa. O teste integrado anterior
`E134` já demonstrara a continuação oficina → linha → emprego → compra em
holdings iniciais, com redução de falta em 390 dias. No mesmo save dia 1.560,
Cinzaverde também oferece a obra e, depois de aberta, quatro opções de compra
de madeira; seu resultado de 30 dias não foi executado. Gate B fecha apenas o
aceite mínimo de **uma** resposta material eficaz quando meios existem.
Tudo aqui foi escolha injetada por fixture/`source=api`, nunca observação
natural nem provider real. O comando reproduzível e os event IDs constam da
evidência E140.

**E141-finalização — busca natural limitada:** inventariei tipos de evento
em três saves já existentes: seed 73/dia 1.560 (65.130 eventos; 2.122
`cargo_delayed`), seed 14/dia 720 (26.423 eventos; 143 atrasos e um
`regional_overflow_started`) e seed 14/dia 1.260 (50.295 eventos; 1.388
atrasos e dois overflows). Nenhum dos três contém decisão de defesa
`strategy_defense_*`, comandante nomeado, coluna detida ou rota restrita por
criatura. Todos têm `ai_enabled=false`, `decision_policy=routine-rules`;
portanto, a ausência de campanha aqui é **ausência observada sob política
offline**, não prova de paz emergente com atores AI nem falha causal. A cadeia
natural enchente → reparo da seed 14 continua evidência de um subconjunto,
não da composição política-militar-social inteira. Item 7 permanece aberto.

**E142-finalização — baseline operacional preliminar, sem gate aprovado:**
retomei o save natural seed 73/dia 1.560 por dois meses, separadamente. No
segundo, dia 1.590 → 1.620, o journal mediu 42,31 s até o fechamento mensal;
o comando completo levou 81,15 s incluindo save/load e continuação. O save
do dia 1.620 tem 18.468.864 bytes, save em 12,012 s, load em 9,088 s e pico
RSS de 1.138.728.960 bytes. Vinte consultas `causal_view` ao mesmo save deram
p50 0,0715 s, p95 0,0729 s e máximo 0,0816 s. Conservação e equivalência
save/load passaram. O mundo continuou sob pressão: 1.095 rações faltantes,
saúde média 255,62 e 453 mortes acumuladas por privação. É um único cenário
offline e um mês tardio, insuficiente para p95 e para ratificar o orçamento;
o valor medido já alerta que o limite provisório de 20 s/mês não foi atendido.

**E143-finalização — índice de eventos, resultado idêntico:** o perfil do
mês 1.620 → 1.650 apontou reconstruções repetidas de `event_index`; o tempo
sob `cProfile` não foi usado como benchmark. `record_event` agora acrescenta
ao índice apenas quando o cache corresponde ao ledger anterior, e
`transaction_copy` dá ao candidato seu próprio mapa para não vazar eventos
em caso de rollback. Dois testes focados passaram, inclusive substituição
não append e isolamento do candidato. Repeti o mesmo save dia 1.590 → 1.620:
o journal marcou 35,33 s, contra 42,31 s antes; o comando completo levou
73,96 s, contra 81,15 s. Os dois saves do dia 1.620 são byte a byte iguais
(SHA-256 `d265358f2ff91b5091dddefc30cb93b884529b32ca08099114dc7e24f03630c0`),
com 68.134 eventos, conservação e save/load válidos. A economia permanece
igual — inclusive suas falhas. Trata-se de melhora localizada, não de um p95
ratificado nem de conclusão do Gate D.

**E144-finalização — índice de tipo e busca de autorização:** um novo perfil
após E143 mostrou `events_of_type` reconstruindo o histórico em chamadas
repetidas. O índice transitório por tipo agora acrescenta o evento novo quando
o ledger anterior corresponde ao cache e dá ao candidato transacional um mapa
próprio. A validação de pesquisa consulta apenas eventos
`research_authorized` por esse índice, sem mudar a ordem nem o critério da
busca. Quatro testes de cache e 24 de pesquisa passaram. No mesmo save
dia 1.590 → 1.620, o mês caiu de 35,33 s (E143) para 27,12 s; o save final
permaneceu byte a byte igual ao baseline E142. É uma comparação de um mês,
não uma garantia de p95.

**E145-finalização — três meses tardios e auditoria:** do save seed 73/dia
1.620, o engine offline avançou até 1.710 sem injeção de escolhas. Os tempos
acumulados do journal foram 22,30 s, 58,43 s e 82,22 s; por mês, 22,30 s,
36,13 s e 23,79 s. O save final tem 19.496.960 bytes, pico RSS de
1.192.169.472 bytes, save/load de 12,623/9,482 s; conservação, continuação
e auditoria standalone passaram. A auditoria cobriu 72.217 eventos, sem
causas quebradas, autoria inválida, raiz material ausente, Story ou
interpretação material. Ainda são três meses de uma única seed offline: não
ratificam os limites provisórios nem representam provider real. Nesse mesmo
mundo, saúde média caiu de 255,62 (dia 1.620) para 239,25 e mortes por
privação subiram de 453 para 645; integridade causal não é saúde econômica.

**E146-finalização — affordance presente, provider ausente:** leitura sem
mutação do save seed 73/dia 1.710 encontrou oficina canônica elegível em
Campomanso (falta 164, saúde 374), Cinzaverde (falta 584, saúde 0) e Pedra
Clara (falta 44, saúde 12), entre outros assentamentos. Nos dias 1.680–1.710,
o ledger registra seis `ai_decision_failed` e nenhuma
`ai_decision_interpreted`; o save está em `ai_enabled=false`. Logo, a
persistência da crise nesse smoke não demonstra que uma IA consultada recusou
essas opções. Demonstra que a política offline não as executou; não justifica
criar emprego ou renda automaticamente nem declarar a economia adaptativa
naturalmente validada.

**E147-finalização — limite do provider real neste checkpoint:** o perfil
Codex CLI/OAuth em pasta temporária sem segredo configurou
`provider_available=True`. Uma primeira consulta sintética pelo runtime
restrito não retornou dentro da observação e foi interrompida, sem receipt ou
save; não foi classificada como `NO_ACTION`. Uma chamada direta e sintética
ao Codex OAuth/Luna fora da restrição de rede respondeu JSON
`{"selected_id":"NO_ACTION"}`, provando apenas conectividade do CLI.
Foi preparado um probe local que usa o menu institucional canônico em uma
cópia em memória e verifica ID, receipt e save intacto. A tentativa de
executá-lo com dossiê derivado do save foi **rejeitada pela revisão de
permissões antes do envio**: a autorização anterior só cobria fixture
sintética, não dados canônicos de save a um provider externo. Não houve
contorno nem segunda via. O corpus do item 8 permanece aberto, aguardando
autorização específica; a conectividade sintética não é agência validada.

**E148-finalização — probe local pronto, provider ainda não exercitado:**
`tools/medieval_provider_civil_probe.py` recompõe o mesmo menu civil
concorrente de uma instituição, trabalha numa cópia transacional em memória,
exige ID ofertado ou `NO_ACTION`, receipt sem delta, sufixo causal válido e
hash do save de origem inalterado. Dois testes focados com provider stub
passaram: recusa explícita e escolha de uma opção enumerada; ambos deixam o
arquivo original byte a byte igual. Ruff passou para o instrumento. O teste
não enviou dossiê local para fora e não conta como decisão real do Luna.

**E149-finalização — baseline tardio de seis meses, orçamento reprovado:**
retomada sem provider da seed 73/dia 1.710 até 1.890, sem escolhas injetadas
após o início. Os tempos mensais foram 33,75 / 31,63 / 27,78 / 49,61 /
46,64 / 41,97 s; p95 por nearest-rank nesta amostra de seis é 49,61 s,
contra limite provisório de 20 s. O save final tem 82.239 eventos,
21.774.336 bytes, pico RSS 1.329.352.704 bytes, save/load de 14,839 /
10,979 s. Conservação, continuação e auditoria causal passaram, sem causas
quebradas, autoria inválida, root material ausente ou Story material. A saúde
média caiu de 239,25 para 195 e mortes por privação subiram de 645 para
1.118; o dado é resultado offline, não decisão de uma IA consultada. Essa
amostra refuta o limite mensal de 20 s neste host/cenário, mas não basta para
aprovar outro limite ou o gate de dez anos.

**E150-finalização — consulta de trabalho sem varrer o ledger:** o perfil do
mês dia 1.890→1.920 atribuiu cerca de 20,6 s sob `cProfile` à busca linear de
eventos em `workforce._event`, repetida ao recompor demandas para grupos.
O helper agora usa o `event_index` transitório já validado, sem mudar a
seleção de eventos. Testes de trabalho e agenda institucional: 43 passaram;
Ruff passou. No mesmo horizonte seed 73/dia 1.710→1.890, os seis meses
somaram 158,25 s contra 231,38 s antes (31,6% menos). O maior mês observado
caiu para 31,67 s; o save final é byte a byte igual ao anterior (SHA-256
`cc6d2a6a77f41e4e16190a671a197ad1550f5baaa17545817a576b6c96b7fc64`).
Conservação e save/load continuaram válidos. A otimização não curou a
economia nem aprovou o limite provisório de 20 s.

**E151-finalização — segunda seed, horizonte mais cedo:** seed 14/dia
1.260→1.440 no mesmo checkout offline. Os seis meses levaram 15,26 / 15,67 /
15,40 / 19,17 / 14,93 / 14,29 s, com p95 nearest-rank de 19,17 s nesta
amostra. O save final tem 58.488 eventos, 15.962.112 bytes, pico RSS
992.706.560 bytes; conservação, save/load/continuação e auditoria causal
passaram. Saúde média terminou em 269,38, mortes acumuladas por privação em
416. A seed 14 está no ano 4, enquanto a comparação mais lenta da seed 73
está no ano 6; não misturar os tempos como se medissem o mesmo estágio.

**E152-finalização — projeção de Knowledge por destinatário:** o perfil já
sem a varredura de trabalho apontou 5,24 s sob `cProfile` para consultas
repetidas a relatórios por ator. Quatro registries de relatórios agora
agrupam uma vez por `recipient_ref` a cada epoch, mantendo a ordenação por
ID que a consulta anterior produzia. Testes de cache, dossiê e conhecimento
de migração: 49 passaram. Repetindo seed 73/dia 1.710→1.890, os meses
somaram 146,96 s contra 158,25 s antes; maior mês, 30,09 contra 31,67 s.
Os saves finais são byte a byte iguais (SHA-256
`cc6d2a6a77f41e4e16190a671a197ad1550f5baaa17545817a576b6c96b7fc64`),
com conservação e save/load válidos. Continua acima de 20 s/mês na seed 73
tardia; não ratifica orçamento nem altera a crise econômica.

**E153-finalização — horizonte tardio estendido, sem provider:** a seed 73
foi retomada do save do dia 1.890 e avançou sem decisões injetadas até 2.070.
Os seis meses levaram 20,41 / 17,65 / 24,27 / 34,74 / 33,31 / 29,31 s
(p95 nearest-rank 34,74 s); o run inteiro, incluindo save/load, levou
208,68 s. O save final tem 89.366 eventos e 23.613.440 bytes. Conservação,
equivalência save/load e continuação para o dia 2.071 passaram; a auditoria
standalone retornou `ok=true`, sem causa quebrada, decisão/autoria inválida,
Story material, interpretação material ou mutação sem root. A saúde média
caiu de 195 para 147,62 e mortes acumuladas por privação subiram de 1.118
para 1.605. O desempenho não cresce monotonicamente mês a mês, mas a
amostra tardia continua acima do limite provisório de 20 s; não aprova novo
orçamento nem o gate de dez anos. A piora econômica é um resultado offline
material, não recusa observada de provider real. Save:
`/tmp/cws-v1-perf-horizon-seed73-day2070-20260926.mws`; progresso:
`/tmp/cws-v1-perf-horizon-seed73-day2070-20260926.jsonl`.

**E154-finalização — ausência natural classificada e perfil de dia 2.070:**
entre os dias 1.891 e 2.070, o save offline contém fretes, pedidos e recusas
de ajuda, mas nenhum evento de campanha/comando militar. No estado final há
36 objetivos (28 de insumos e oito de comida), 36 planos de abastecimento
(21 satisfeitos, nove aguardando entrega e seis bloqueados) e nenhum
objetivo defensivo. A ausência de campanha impede que esse intervalo prove
a composição natural do Gate C; não é falha causal nem motivo para forçar
guerra. As três recusas observadas são decisões `routine-rules`, não Luna.
No pedido aberto a Valedouro no dia 2.070, a engine oferece tanto recusa
quanto aceite material de 1.805 unidades de comida; a leitura institucional
do solicitante é -2, por isso o fallback conservador tende à recusa. Isso
mostra uma escolha possível que não foi tomada, não valida comportamento
do provider real. Perfil read-only de mais 30 dias a partir do save: 27,37 s
para avançar, 89.366→90.357 eventos, origem intacta. Maiores custos
cumulativos foram `transaction_copy` (7,06 s), validação de Economy
(5,50 s) e Relations (4,85 s). Esses custos orientam investigação, mas
não autorizam enfraquecer atomicidade/validação para atender orçamento.

**E155-finalização — validação única no commit de Economy/Relations:** o
estado publicado já foi validado no commit anterior ou no load, e a única
operação anterior ao tick (`revoke_invalid_detachment_commands`) não altera
Economy/Relations. Removi as duas verificações completas repetidas na entrada
de `MedievalSimulator.step`; ambas continuam obrigatórias no candidato final,
antes de save/publicação. Regressões negativas injetam falha final em cada
owner e confirmam rollback; o conjunto engine/isolamento passou `39` testes.
Reexecutando a seed 73/dia 2.070→2.100, o avanço mensal caiu de 14,83 para
12,61 s (~15% nessa amostra), e os dois saves têm SHA-256 idêntico
(`139bb29fa2c9ab38cc9b8a73000de58ef68df2b974a003952e18840476a41873`).
O save otimizado tem 90.357 eventos, passou conservação, save/load e
auditoria causal standalone sem violações. Ruff e `git diff --check` passaram.
Um mês mais leve não estabelece p95 nem resolve o limite refutado nos meses
anteriores; Gate D continua aberto.

**E156-finalização — equivalência em seis meses tardios:** retomei a seed
73 do mesmo save do dia 1.890 até 2.070 no checkout com a validação pré-tick
reduzida. Os meses levaram 17,25 / 14,50 / 20,91 / 31,39 / 28,79 /
25,86 s, totalizando 138,70 s de avanço contra 159,69 s no baseline
(~13% menos); p95 nearest-rank caiu de 34,74 para 31,39 s. Os saves
terminaram com o mesmo SHA-256
`a7681d5b88f2a5e1d0bf9169b788f4f1bd4416176e727e871d0fa15531b037b4`,
89.366 eventos e 23.613.440 bytes. Conservação, equivalência save/load,
continuação e auditoria standalone passaram, sem violação causal/material.
O p95 continua acima dos 20 s provisórios; não há ratificação de orçamento,
provider real nem gate de dez anos. Novo save:
`/tmp/cws-v1-prevalidation-optimized-day2070-20260926.mws`.

**E157-finalização — equivalência em segunda seed:** retomei a seed 14 do
dia 1.260 até 1.440 com a mesma mudança de validação. Os seis meses
levaram 11,94 / 12,12 / 11,83 / 15,75 / 11,24 / 10,45 s, total 73,33 s
contra 94,72 s antes (~22,6% menos). O p95 nearest-rank dessa amostra caiu
de 19,17 para 15,75 s. O save final é byte a byte idêntico ao baseline
(SHA-256 `83cb0f40b1175f87aa0f184950264cbdb08a6cc5ce4508c66e214c9c599b0cb9`),
com 58.488 eventos e 15.962.112 bytes. Conservação, save/load, continuação
e auditoria standalone passaram. A seed 14 neste trecho está no ano 4;
não juntar seu p95 ao da seed 73 no ano 6 nem usar esses seis meses como
aprovação do limite de dez anos. Save:
`/tmp/cws-v1-prevalidation-optimized-seed14-day1440-20260926.mws`.

**E158-finalização — latência local do `Por quê?`:** no save seed 73/dia
2.070 com 89.366 eventos, executei `causal_view` 20 vezes sobre IDs
distribuídos entre fatos com causas, `limit=100`: mediana 0,101 s, p95
nearest-rank 0,106 s, máximo 0,108 s. Uma segunda amostra escolheu os 20
fatos de maior fanout (1.849–2.642 efeitos cada) e retornou 100 efeitos
por consulta: mediana 0,101 s, p95 0,105 s, máximo 0,107 s. Ambas estão
abaixo do limite provisório de 2 s para backend local. Não medem transporte
HTTP, renderização ou um save de dez anos; orçamento V1 ainda exige os
demais limites e o horizonte final.

**E159-finalização — mais um ano natural e caixa produtivo esgotado:**
seed 73 offline do dia 2.070 ao 2.430, com checkpoints auditáveis nos dias
2.250 e 2.430. Descontando os 40,32 s de save/load do primeiro checkpoint
que entram no intervalo seguinte, os 12 meses somaram 186,38 s; p95
nearest-rank 23,28 s. O segundo checkpoint custou 43,11 s e não entra
nesses 12 meses. Save final 26.673.152 bytes, 100.921 eventos, pico RSS
1.644.216.320 bytes; conservação, save/load/continuação e auditoria causal
standalone passaram sem violações. A amostra continua insuficiente para
ratificar o orçamento de 3.600 dias, especialmente porque a população caiu.

O resultado econômico é grave: população 8.267, saúde média 83,88, unrest
médio 716,38, 2.668 mortes acumuladas por privação. Ferroalto, Brumafria
e Cinzaverde terminaram com estoque público de comida zero; suas fazendas
fizeram zero batches com `payroll_funds`, e as contas pagadoras estavam em
zero. O dinheiro total permaneceu conservado em 76.000, mas 46.567 estavam
nas quatro coortes agricultoras de Campomanso; Escarlia tinha tesouro zero.
Isso é um estrangulamento de circulação e distribuição, não criação ou
destruição inexplicada de recursos. Não há opção de nova fundação produtiva
para os três governos neste estado: entre as combinações de site/blueprint,
28 falham por capacidade física e duas linhas já existem. Há 30/47/24
opções de ajustar staffing para Auren/Escarlia/Valedouro, mas reduzir folha
não cria caixa em Escarlia. Auren ainda poderia aceitar um pedido de ajuda
de Escarlia por 349 rações; a trajetória offline não o escolheu. Antes de
mais horizonte longo, verificar uma via de decisão material que reconecte
caixa ocioso, produção e famílias, sem subsídio automático ou lei inventada
pela LLM. Save: `/tmp/cws-v1-prebudget-seed73-day2430-20260926.mws`;
progresso: `/tmp/cws-v1-prebudget-seed73-day2430-20260926.jsonl`.

**E160-finalização — pré-checagem pública proporcional:** `npm run build`
em `web/` passou, incluindo `vue-tsc --noEmit` e Vite; o bundler avisou
sobre chunks >500 kB, sem erro. Cinco contratos focados passaram em 3,29 s:
eventos/causas paginados, delta no dossiê, snapshot único do observatório,
cadeia `why()` de venda e serviço do bundle medieval. Uma tentativa de rodar
o grupo inteiro de API/observatório (33 testes) ficou vários minutos no
primeiro lifecycle público de um ano e foi interrompida intencionalmente
com exit 130; não é passe nem falha funcional demonstrada. A regressão
integrada final segue para o checkout congelado.

**E161-finalização — falha fechada da sondagem local de provider:** o probe
de menu civil agora confere o SHA-256 do save de origem até quando a consulta
falha ou rejeita uma resposta. Um provider simulado que devolve ID inventado
gera `ProviderDecisionRequired` sem alterar os bytes do save. Os três testes
focados do probe passaram em 1,14 s; Ruff e `git diff --check` passaram.
Isso não é consulta OAuth/Luna real, nem fecha o corpus de 10 decisões do
Gate D. A autorização anterior cobria apenas fixture sintética; a consulta
canônica externa segue sem autorização.

**E162-finalização — perfil localizado no mundo tardio:** o profiler
read-only avançou a seed 73 do dia 2.430 ao 2.460 em memória, sem provider e
sem modificar o hash do save de origem. Registrou 22,39 s sob `cProfile`
para 15 saltos, adicionando 864 eventos. Cópia transacional (6,53 s), revisão
diplomática (4,24 s) e validação de Relations (3,06 s) são tempos acumulados
com sobreposição, não partes somáveis. Numa medição isolada sem profiler, copiar
os nove estados de owner custou aproximadamente 0,05 s; não comparar diretamente
com o custo instrumentado de 30 transações. O save tinha 906 propostas
diplomáticas, 767 rejeitadas e 138 aceitas. Uma tentativa auxiliar de contar
técnicas falhou por nome de atributo incorreto após imprimir as contagens de
propostas/obrigações; nenhuma alteração de estado ocorreu. O dado localiza
custos para investigação, mas não ratifica o p95 do orçamento nem demonstra
que ofertas repetidas são bug. A regra diplomática foi preservada.

**E163-finalização — orçamento fixado antes do gate longo:** a seed 73
continuou de 2.430 a 2.610 dias sem provider real nem decisões injetadas,
com `routine-rules` explícita. Os incrementos mensais de tempo foram
12,73/12,70/17,04/25,51/30,90/18,25 s. Com os 12 meses anteriores no mesmo
checkout, o p95 nearest-rank dos 18 meses contíguos é 30,90 s, média
16,86 s. O teto provisório de 20 s não é realista para este baseline; antes
do gate final, o orçamento V1 foi fixado em p95 mensal ≤ 35 s, mantendo
3.600 dias/seed ≤ 60 min, pico RSS ≤ 4 GiB, save dez anos ≤ 512 MiB,
save/load ≤ 60 s cada e `why()` p95 ≤ 2 s. O gate final deve verificar esses
limites, não reajustá-los retroativamente.

O save `/tmp/cws-v1-budget-seed73-day2610-20260926.mws` tem 28.295.168 bytes,
SHA-256 `93355de1dba15ffa3de74d8395f1a37b1e7039fdc1153e94c722dca0f4d4285f`,
106.994 eventos, pico RSS 1.749.499.904 bytes, save 18,71 s e load 15,06 s.
Conservação e equivalência save/load passaram. A auditoria causal standalone
retornou `ok=true`, zero causas quebradas, erros de autoria, origens sem
decisão, roots inválidas, Story material e interpretação material. O mundo
terminou com população 7.835, falta alimentar 2.984 no mês, saúde média
71,38, unrest 784,25 e 3.100 mortes por privação acumuladas. Esta trajetória
mostra crise persistente, não capacidade adaptativa natural nem provider real.
Uma inspeção read-only do mesmo save encontrou 36 planos (25 satisfeitos,
oito aguardando entrega e três bloqueados), zero destacamentos e nenhum
evento de campanha/cerco; a composição militar natural do Gate C não surgiu
nessa trajetória offline, apesar da ecologia de criaturas continuar ativa.
O progresso mensal está em
`/tmp/cws-v1-budget-seed73-day2610-20260926.jsonl`; Gate C natural,
corpus de provider e três seeds/3.600 dias continuam abertos.

**E164-finalização — leitura de ajuda indexada sem alterar trajetória:**
no save dia 2.610, Escarlia tem 24 moedas em contas da instituição, seis
opções de pedir ajuda e nenhuma opção atual de receber/entregar resposta de
ajuda; Auren possui caixa e relief próprios, mas nenhuma resposta de ajuda
pendente nesse limite. A checagem `_own_open_chain` percorria todos os
106.994 eventos para cada assentamento, embora exista índice transitório por
tipo. Ela agora lê somente `institutional_aid_requested`, preservando a
mesma validação de decisão, assentamento e obrigação. Trinta consultas aos
três assentamentos de Escarlia passaram de 0,569 s para 0,036 s no mesmo
save (medição isolada, índice aquecido). Nove testes focados de ajuda/índice,
Ruff e `git diff --check` passaram.

Repeti offline os mesmos 180 dias desde o save do dia 2.430: o novo save do
dia 2.610 é byte a byte idêntico ao anterior, SHA-256
`93355de1dba15ffa3de74d8395f1a37b1e7039fdc1153e94c722dca0f4d4285f`.
O tempo mensal acumulado passou de 117,13 para 115,54 s; as execuções não
são controle de ruído de máquina, portanto não atribuir os 1,59 s inteiros à
mudança. A intervenção é performance da consulta, não nova via fiscal nem
prova de recuperação da economia.

**E165-finalização — busca natural sem cota de drama:** inspecionei os saves
atuais seed 14/dia 1.440 (58.488 eventos) e seed 73/dia 2.610 (106.994
eventos). Ambos persistem `ai_enabled=false` e `decision_policy=routine-rules`;
suas trajetórias foram executadas sem decisões injetadas após o início.
Existem 35 e 36 planos estratégicos, respectivamente, mas zero destacamentos
em ambos e nenhum evento de campanha ou cerco. Houve ajuda institucional
(130/167 pedidos), relatórios de rota e transições ocupacionais, sem compor
política→QG→comandante→ambiente→população.

Classificação: o aceite multissistema E139 é **fixture autônoma controlada**
com provider stub; esta inspeção é **observação natural offline**, cujas
decisões usam política explícita `routine-rules`; nenhuma é **provider real**.
A enchente→reparo natural da seed 14 documentada em 24/09 pertence a outro
checkout/save e não é atribuída ao save atual de dia 1.440. A busca do item
7 do plano foi cumprida com resultado negativo para a cadeia política plena;
isso não cria quota de drama nem prova que a visão emergente completa já surge
espontaneamente. O corpus real e o gate de três seeds/3.600 dias permanecem
abertos.

**E166-finalização — prévia local e compactação do contexto de provider:**
montei o menu mensal canônico de Escarlia no save seed 73/dia 2.610 sem chamar
serviço externo. Havia 120 opções: 54 de supply, seis pedidos de ajuda, duas
de diplomacia, 47 ajustes de staffing, uma econômica e dez de bribery. O prompt
teria 75.264 bytes, dos quais 39.205 eram o fragmento de staffing repetindo
salário, caixa e recibos do mesmo contrato em cada alvo. A situação agora
emite evidência fixa uma vez por contrato (`staffing_contracts`) e mantém os
47 alvos calculados em `staffing_options`; os IDs selecionáveis continuam na
lista canônica de escolhas. Não há ID bruto de opção duplicado no fragmento.

No mesmo save, o fragmento caiu para 19.738 bytes e o prompt total para
55.797 bytes, sem reduzir as 120 opções nem os 51 aliases de IDs privados.
Uma varredura local deste prompt não encontrou os marcadores `stock:`,
`account:`, `treasury:`, `payroll:` ou `household-stock:`; isso é só uma amostra,
não garantia universal de privacidade para todos os atores/famílias.
O módulo focal de emprego passou 22 testes após atualizar seu contrato de
contexto; um teste adicional de cardinalidade passou isoladamente. Ruff e
`git diff --check` passaram. Isso prepara custo/egress do Gate D, mas não é
consulta OAuth/Luna, não demonstra latência ou escolha do provider e não
autoriza enviar dados derivados do save sem aprovação específica.

**E167-finalização — prévia local de todos os menus institucionais do save:**
no mesmo seed 73/dia 2.610, três polities e oito organizações tinham menus
mensais com 10–120 opções. Os prompts teriam 3.350–55.797 bytes; Escarlia
foi a maior (120 opções, 51 aliases), Ofícios da Serra teve 41 opções e 31
aliases. A varredura dos 11 prompts encontrou zero ocorrências de `stock:`,
`account:`, `treasury:`, `payroll:` e `household-stock:`. Isso não é garantia
universal de privacidade nem inclui população/campanha/estados futuros. O
provider está configurado localmente, mas nenhuma chamada externa foi feita.

**E168-finalização — aceite operacional instrumentado, não executado:** o
smoke passa a retornar duração individual de cada mês e p95 nearest-rank,
descontando o custo de checkpoints que ocorrem entre marcas mensais. O
verificador `--final-v1` exige três seeds naturais distintas por 3.600 dias
com checkpoints anuais ou mais frequentes; recusa sobrescrever saves finais
existentes. Avalia os tetos já fixados: 60 min/seed, 4 GiB RSS, 512 MiB save,
60 s para gravar e carregar, p95 mensal 35 s e p95 de 20 consultas `why()`
até 100 links em 2 s. A medição local de `why()` no save dia 2.610 retornou
p95 0,1218 s para 20 consultas. Quatro testes focados do release gate passaram
em 6,04 s, incluindo um run curto com checkpoint e negativos de orçamento/
forma do gate; Ruff e `git diff --check` passaram. Não houve run de três
seeds/3.600 dias, nem provider real, e a ferramenta não certifica UI/rede.

## Ledger rejeita autoria stale e causa futura — 25/09/2026

O auditor e o ledger agora exigem que todo evento não `DECISION` com origem
`ACTOR_DECISION` tenha uma decisão real do mesmo dia entre suas causas. Quando
há delta, ator e affordance também precisam coincidir com o payload direto da
decisão. Antes, a autoria direta só era verificada para eventos com delta; uma
ocorrência sem delta podia ter fonte ausente/stale. Regressões cobrem essas
falhas e preservam o receipt não material de contraproposta diplomática quando
ele aponta para sua decisão contemporânea. Os testes focados passaram; o save
natural seed 14/dia 120 foi re-auditado no checkout: `ok=true`, 3.839 eventos,
2.738 transições materiais e zero erros de autoria ou transições sem causa/root.
Isso audita o vínculo histórico, mas não prova affordance ainda válida no
momento da execução; isso continua responsabilidade de cada owner e da
auditoria transversal, ainda aberta.

O mesmo gate de autoria provider agora rejeita receipt de interpretação/recusa
de outro dia, mesmo se ator e affordance coincidirem; a seleção precisa ser
factualmente contemporânea à decisão. `record_event` também impede aplicar uma
decisão de ator do dia anterior, e `validate_history` rejeita essa autoria ao
reler o ledger. Regressões cobrem tentativa no append, receipt provider stale e
adulteração do histórico; autoria, auditoria e diplomacia passaram juntas
(`30 passed`).

## Revalidação natural após receipts de autoria — 25/09/2026

A seed 73 foi rodada novamente por 120 dias em modo offline (`routine-rules`,
sem provider real), no checkout após os últimos receipts de autoria. Conservação,
save/load, continuação até o dia 121 e auditoria passaram. O save contém 3.859
eventos e tem 2,27 MB; o auditor encontrou zero causas quebradas, erros de
autoria, decisões sem fonte ou mutações por Story/interpretação. Foram 90
transições materiais de ator e 2.666 determinísticas.
Uma segunda seed (14), no mesmo horizonte, repetiu a concentração de pressão
nos mesmos assentamentos e os indicadores agregados; seu save de 2,27 MB também
passou a auditoria. Isso é um indício de pressão estrutural reproduzível, não
uma conclusão de colapso ou equilíbrio de longo prazo. O volume reportou cerca
de 8,2 GiB livres depois dos saves temporários; nenhum arquivo foi removido.

No último mês, a falta agregada caiu a 16 e não houve mortes por privação, mas a
saúde média chegou a 951,25 e unrest a 48,75. Ferroalto, Pedra Clara e Porto
Velho tiveram episódios grandes de falta nos dias 60/120 e terminaram com
unrest 90/141/140 após alívios materiais limitados. No snapshot final ainda
havia 3.513/5.037/4.121 unidades de alimento em estoque público nesses locais,
enquanto diversos grupos artesãos tinham 0–5 moedas domésticas e algumas folhas
estavam limitadas por `payroll_funds`. Isso sugere uma questão de acesso/renda e
composição ocupacional, não falta agregada de comida; a causa raiz ainda precisa
ser confirmada na cadeia emprego → folha → preço → compra. Isso deixa a economia
natural em diagnóstico: o resultado não autoriza balanceamento artificial nem
demonstra provider/IA real. O [plano operacional](medieval-finalization-plan.md)
define os gates; esta página guarda evidência e descobertas. O
progresso JSONL da execução é temporário e não substitui estes registros.
Na trilha, folhas artesanais pagaram 1–2 moedas por trabalho realizado, compras
anteriores de ração chegaram a 4 moedas cada, e no dia 120 grupos artesãos
iniciaram transições para `farmer`. É evidência de adaptação e tensão de poder de
compra, não ainda prova de que a economia converge ou colapsa no longo prazo.

Estendi uma trajetória natural por um ano (seed 14, dia 360), com checkpoints
em 120/240/360. Conservação e cada round-trip/continuação passaram; auditoria
final: 12.658 eventos, 8.943 transições materiais, sem causa/autoria quebrada,
Story material ou interpretação LLM. O arquivo ficou com 4,48 MB, save/load
2,18/1,45 s, pico RSS ~268 MB e ~8,2 GiB livres. Sem mortes por privação, porém
o resultado foi desigual: saúde média 917,75/unrest 75,62; Pedra Clara terminou
em 690/260 e Porto Velho em 740/260, enquanto Ferroalto recuperou a 1000/0.
Foram registrados 33 pedidos de ajuda, 30 cumprimentos, 24 alívios e 6 migrações.
É um diagnóstico de um ano em fallback determinístico, não gate final nem prova
de resposta por provider; ainda precisamos rastrear a causa dessa diferença
entre assentamentos antes de balancear a economia.

Continuei o mesmo save natural até o dia 720 (ano 2). Auditoria final e todos os
checkpoints de 120 dias passaram, com 26.423 eventos e sem falhas causais; save
7,99 MB, pico RSS ~498 MB, save/load 4,67/2,95 s. A saúde média caiu a 674,75,
unrest foi a 145 e falta mensal a 506; zero mortes. Campomanso terminou com 449
de falta e 22.461 de comida pública a preço 1. A leitura econômica confirma
separação entre estoque e acesso: no snapshot há grupos sem caixa, 11 instalações
limitadas por folha e 66 opções já enumeradas de reduzir/suspender contratos
(18/15/33 por polidade). O fallback offline não as selecionou; não foi criada
uma decisão automática para “resolver” o dado. A população tinha 56.927 moedas,
organizações 14.027 e polities 5.046, então a hipótese mais forte agora é
distribuição/acesso e orçamento produtivo, ainda sem root cause fechado. Provider
real não foi chamado; a autorização anterior era de uso único.
Três testes focados do owner confirmaram que a affordance de suspensão/redução
aparece no menu institucional único e é revalidada após receipt de payroll não
pago (`3 passed`); isso não equivale a uma seleção real do provider.

O smoke agora expõe estoque público, preço, caixa doméstico, estimativa de
rações públicas inacessíveis ao preço atual e instalações limitadas por payroll
no breakdown mensal por assentamento. A estimativa de affordability antecede
provisões privadas/alívio e não substitui `missing_food`; o teste focal passou.

## Autoria da viagem individual — 25/09/2026

O receipt material de partida de personagem agora preserva a decisão individual
`ACTOR_DECISION`, a affordance de trecho escolhido e o personagem que decidiu;
a chegada continua sendo resolução datada do owner, não teleporte nem segunda
escolha. Viagem e comando militar passaram em `13` testes focados, com Ruff e
`git diff --check` limpos. Isso fecha autoria da partida no recorte atual, não
uma simulação ampla de vidas pessoais.

## Autoria na autorização de reparo — 25/09/2026

O mantenedor continua escolhendo uma affordance atual e o owner mantém um
receipt determinístico separado com os termos exatos da obra. O receipt
material `repair_started` agora aponta diretamente para a decisão original do
mantenedor, sua affordance e o relatório local de dano; a oficina/pagamento
gradual ainda exige as condições materiais dos ciclos seguintes. A regressão de
reparo, desgaste, serviços de sítio e campanha passou (`40 passed`), com Ruff e
`git diff --check` limpos. Isso verifica o caminho focal de manutenção, não
fecha todo o inventário de transições dos owners.

## Autoria material no cumprimento diplomático e na concessão — 25/09/2026

Cumprimento e reparação de transferências negociadas agora registram a decisão
do devedor no receipt da obrigação e na abertura do frete. A transferência de
administração também aponta para a decisão atual do administrador; proposta e
aceite continuam separados, e nenhum prazo executa compromisso sozinho. A
regressão focal de concessão, abastecimento recíproco e ajuda passou (`43
passed`), com Ruff e `git diff --check` limpos. O recorte exercita as decisões
atuais e seus owners, não conclui a auditoria global nem demonstra negociação
espontânea/provider real em horizonte longo.

## Autoria material das ordens militares e do abastecimento — 25/09/2026

Mobilização de coluna, início de preparo em posição, nomeação de comandante,
mudança de doutrina e despacho de suprimento agora marcam seus receipts
materiais como `ACTOR_DECISION`, apontando para a decisão corrente, seu ator e
affordance selecionada. A abertura do frete de campanha usa o mesmo payload do
turno do QG; a chegada, o consumo e outras consequências continuam owners
determinísticos. A revisão focal de força, posição, comando, retirada,
abastecimento e campanha persistente passou (`37 passed`), com Ruff e
`git diff --check` limpos. Isso fecha autoria dos comandos exercitados, não prova
uma cadeia espontânea longa, provider remoto nem a separação política/QG em
toda campanha.

## Autoria material em recuperação de compra e pressão de campanha — 25/09/2026

Recuperação bilateral de compra bloqueada agora registra pedido do comprador,
recusa/aceite do vendedor, frete sucessor e resolução da carga original como
transições `ACTOR_DECISION`, com `decision_event_id`, ator e affordance no
payload causal. A retirada manual da pressão de uma coluna sobre as rotas segue
o mesmo contrato; encerramento automático por perda física de posição,
provisões ou acesso mantém origem determinística e causas materiais.
Regressão focal de recuperação, investimento, cerco e campanha persistente:
`35 passed`; Ruff e `git diff --check` passaram. Isto fecha os owners exercitados,
não o inventário global de autoria ou os gates naturais/provider remoto.

Linha de base read-only do espaço: volume do workspace com 8,3 GiB livres
(97% usado); checkout com 937 MiB; `/tmp` com 121 MiB observados. Não houve
remoção de arquivos. O número do volume inclui dados fora deste checkout e não
identifica sozinho quais arquivos são seguros para limpeza.

## Ajuda, patrimônio produtivo e ensino exigem autoria bilateral — 25/09/2026

Pedido, aceite e recusa de ajuda institucional agora registram no próprio
receipt a decisão de ator e a affordance escolhida; cumprimento e remediação já
tinham essa autoria. A política de ajuda continua baseada no relatório local
datado de fome, sem depender de um plano estratégico lateral. Uma fixture que
esperava um plano `blocked` foi corrigida para afirmar a evidência que o owner
realmente consome: relatório atual privado com necessidade positiva.

Transferência de workshop agora aceita apenas proposta e aceite
`ACTOR_DECISION`; payload determinístico idêntico não cria oferta nem transfere
controle/bindings. Ensino de técnica também exige consentimento autoral atual
do docente e do aprendiz; cópias determinísticas não alteram KnowledgeState.
As fixtures de comandos API registram `decision_source=api` explicitamente.

Conhecimento valida também a autoria dos receipts persistidos de pedido e
resposta; se a origem material for adulterada para determinística, a validação
rejeita o snapshot. Verificação focal conjunta: ajuda, política offline,
abastecimento recíproco, transferência produtiva, pesquisa/ensino e cadeia de
treinamento — `74 passed`; Ruff e `git diff --check` passaram nos arquivos
tocados. Isso fecha autoria e regressões desses caminhos exercitados, não a
auditoria global de owners, o provider real, difusão espontânea ou o gate natural
longo. WIP permanece sem commit/push.

## Autoria nos owners materiais de alívio, cerco, tecnologia e trabalho — 25/09/2026

Distribuição e transferência institucional de alívio, ocupação pós-breach e
roubo de técnica agora rejeitam decisões determinísticas mesmo quando carregam
payload de affordance atual. Divulgação voluntária de técnica valida
`ACTOR_DECISION` tanto no disclosure explícito como quando a proposta de ensino
é sua causa factual. Os executores continuam recompondo opções, verificando
autoridade e revalidando estoque/estado.

Workforce transitória (aceite do grupo e autorização de recrutamento),
contratação permanente e mudança de alvo de staffing também exigem origem
`ACTOR_DECISION`. Claims/reconhecimento de autoridade e patrocínio de
apprenticeship exigem a mesma origem; affordances de claim ou patrocínio
copiadas para evento determinístico são recusadas sem mutação (`2` e `8 passed`);
alívio, cerco/pressão e roubo passaram em recorte (`46 passed`);
sighting, ensino e diplomacia passaram (`24 passed`); workforce/emprego passou
(`59 passed`). Ruff e
`git diff --check` passaram nos arquivos tocados. Falhas intermediárias
revelaram fixtures antigas sem autoria em decisões de diplomacia/comando; elas
foram atualizadas e os recortes correspondentes reexecutados. Isto não é
certificação da auditoria global nem do smoke de dez anos; ainda restam owners
materiais a revisar. A tarifa de exportação também exige decisão de ator: o
recorte focado passou (`10 passed`), incluindo affordance sem autoria recusada
sem efeito.

Construção de expansão/fundação/sítio valida origem direta ou recibo
determinístico que cite a affordance exata escolhida pelo ator no mesmo dia;
isso preserva os parâmetros materiais calculados pelo owner sem perder a causa
da escolha. Os recortes de expansão/fundação/construção passaram (`47 passed`).
Serviço de infraestrutura e imposto de renda também exigem decisão de ator;
os testes de sítio e tarifa passaram (`17 passed`). Compras de mercado exigem
decisão independente com autoria tanto do comprador como do vendedor, e venda
de tecnologia exige a mesma origem nas duas pontas; regressões de consentimento
falsificado não alteram estado. Recortes de mercado e venda tecnológica
passaram (`29 passed`); o smoke preparado de comércio passou no grupo (`21
passed`). Ruff e `git diff --check` passaram. Estes recortes não concluem a
auditoria de todos os owners nem substituem o gate natural longo.

O embargo comercial revogável agora recebe diretamente a decisão atual da
instituição; o owner não fabrica mais uma decisão intermediária determinística
para expressar o mesmo ato. A regressão tenta executar a affordance exata sem
autoria e confirma rejeição sem efeito; a cadeia de embargo passou (`13
passed`).

## Consumo doméstico e comando militar exigem decisão de ator — 25/09/2026

O executor de compra de rações valida agora `ACTOR_DECISION` tanto para o grupo
que compra como para o fornecedor que consente. Pagamento bilateral, preço,
estoque, mandato, validade diária e uso único seguem revalidados pelo owner. O
owner de comando de destacamento também exige decisão atual do ator para
nomeação, doutrina e liberação. Regressões com payload determinístico copiado
confirmam que não há transferência de alimento/dinheiro nem nomeação sem escolha.

Uma fixture válida da fronteira de consumo foi atualizada para declarar origem
`api`. Recortes de consumo, comando, engajamento, mortalidade e cadeia cívica
passaram (`55 passed`); Ruff e diff-check passaram. Isso fecha autoria nos
owners exercitados, não a auditoria material completa. A fatia posterior de
25/09 fecha ocupação pós-cerco, divulgação/sighting, claims de autoridade,
apprenticeship, tarifa de exportação e alguns caminhos de workforce/emprego;
outros owners seguem pendentes.

## Decisões da cadeia cívica exigem autoria — 25/09/2026

Os owners de protesto, recusa administrativa, tumulto, formação/adesão a
movimento, greve geral, declaração de rebelião, resposta (repressão/negociação),
dissolução e anistia agora validam `CausalOrigin.ACTOR_DECISION`, além de data,
ator e affordance corrente. Fixtures de escolhas válidas registram
`decision_source.kind=api`. Uma regressão tenta abrir protesto copiando um ID
atual em evento determinístico e confirma rejeição sem alteração do snapshot.

A fixture de repressão reutiliza a coorte de soldados existente, eliminando um
grupo duplicado que violava a identidade única de população por ocupação/local.
Os testes de protesto e política passaram (`16 passed`); Ruff e `git diff
--check` passaram nos arquivos tocados. Isso fecha autoria nesta cadeia, não
prova uma revolta surgindo naturalmente ou qualquer categoria cívica inteira
além dos owners exercitados. A auditoria de outros owners continua aberta.

## Pagamento exige escolha do titular da conta — 25/09/2026

`transfer_money` agora rejeita decisões de origem diferente de
`ACTOR_DECISION`, além de exigir intenção exata, dia atual, saldo, mandato e
uso único. Uma regressão com payload correto copiado para um evento
determinístico confirma snapshot inalterado. Fixtures de pagamento válidas,
remediação/renegociação de compromisso e a cadeia de rota foram alinhadas para
declarar origem `api`. Os recortes focados passaram (`13 passed`), com Ruff e
`git diff --check` limpos nos arquivos tocados.

Uma rodada maior de economia/diplomacia reteve duas falhas fora desta alteração:
uma expectativa antiga de movimentação ocupacional e uma expectativa de
consumo/falta. Não as alterei nem as chamei de regressões de autoria; a suíte
ampla de economia não está verde. O inventário global também segue em andamento.

## Autoria em viagem e negação de assembleia — 25/09/2026

`travel_character` e o owner de negação de assembleia agora recusam uma
`DECISION` determinística mesmo se ela copiar a affordance atual. Viagem só
começa com decisão atual do personagem; negação exige a escolha atual da força
que observou a assembleia. Regressões confirmam snapshot intacto para a
tentativa sem autoria. Viagem e a cadeia local de assembleia/religião passaram
(`6 passed`); Ruff e `git diff --check` passaram nos arquivos tocados.

A varredura estática seguinte ainda encontrou guards de decisão que precisam de
revisão, incluindo a família de protesto/movimento cívico e pagamentos/consumo.
Portanto isto fecha somente os dois owners exercitados, não a autoria global.

## Autoria e integração diplomática — 25/09/2026

O validador diplomático compartilhado agora exige `ACTOR_DECISION` para ofertas,
respostas, pagamentos, ensino/compromissos e decisões correlatas. Os owners de
abastecimento recíproco também rejeitam explicitamente escolhas determinísticas,
mesmo quando copiam uma affordance válida. Uma regressão tenta abrir a proposta
com esse payload e confirma erro sem mudança no snapshot.

As fixtures de recourse e repudiação foram alinhadas à autoria auditável. A
fixture de abastecimento recíproco agora publica relatórios atuais de estoque e
remove cobertura alimentar dos estoques próprios antes de revisar a política;
assim a necessidade de negociar decorre de um plano bloqueado com evidência,
não de um estado de falta sem causa conhecida. Diplomacia, abastecimento
recíproco, recourse, repudiação, concessão administrativa e desescalada passaram
juntos (`43 passed`). Ruff nos arquivos tocados e `git diff --check` passaram.

Isso fecha a autoria nos caminhos exercitados, mas não prova negociação/provider
espontâneo, efeito de memória numa decisão futura ou auditoria de todos os
owners materiais. WIP permanece sem commit/push.

## Migração exige autoria e recuperação preserva a cadeia — 25/09/2026

Os owners de partida e recuperação de migração aceitam agora uma escolha
direta `ACTOR_DECISION` ou uma autorização determinística interna causada, no
mesmo dia, pela affordance atual selecionada pelo grupo. Intenção determinística
com payload idêntico não inicia a jornada. A opção é recomposta antes da
validação de data para que relatório expirado continue sendo classificado como
opção stale. A autorização de início também é contada no bloqueio de replay.

O caminho composto de recuperação agora liga autorização à decisão do grupo e
aos relatórios usados. A fixture de redirecionamento percorre esse executor e
confere separadamente escolha → autorização → mudança material de rota. Uma
regressão rejeita escolha determinística sem mutação. Migração e conhecimento
passaram (`23 passed`); Ruff passou ignorando um `F841` preexistente no owner e
`git diff --check` passou. Isso fecha autoria e recuperação nos caminhos
exercitados, não migração espontânea nem difusão tecnológica ampla. WIP segue
sem commit/push.

## Pesquisa e rito exigem autoria de ator — 25/09/2026

Na continuação da auditoria dos owners, pesquisa agora valida `ACTOR_DECISION`
no patrocínio e no consentimento independente do pesquisador; a seleção da
affordance de pesquisa também não aceita payload determinístico idêntico. Os
menus deixam de oferecer resposta a patrocínio sem autoria. Ritos patrocinados
e cancelados usam o mesmo requisito no helper do owner. O fallback de pesquisa
continua sendo escolha explícita de ator com origem `fallback`, não bypass
determinístico.

Regressões negativas provaram os três caminhos de pesquisa e o patrocínio de
rito sem autoria; nos casos rejeitados o snapshot não muda. Pesquisa,
apprenticeship, venda de técnica, fail-closed e ritos passaram juntos
(`52 passed`). Ruff foi verificado nos arquivos tocados, ignorando apenas
F401/F841 preexistentes em fixtures; `git diff --check` passou. Isso fecha os
owners exercitados, não a auditoria causal global, a árvore tecnológica ou os
gates naturais/provider. WIP permanece sem commit/push.

## Pesquisa exige autoria do patrocinador e do pesquisador — 25/09/2026

Os owners de pesquisa agora exigem que a escolha que patrocina a pesquisa e o
consentimento do pesquisador sejam decisões atuais de ator (`ACTOR_DECISION`).
`execute_research_option` também rejeita uma intenção determinística mesmo
quando ela copia exatamente a affordance vigente. Menus de oferta não expõem
autorizações cuja origem não seja uma decisão real. As escolhas offline
continuam válidas porque são registradas como decisões explícitas com
`decision_source=fallback`; fixtures de comando direto declaram `api`.

Regressões negativas cobrem affordance exata determinística, patrocínio sem
autoria e consentimento sem autoria, preservando snapshot sem mutação. Pesquisa,
aprendizagem/apprenticeship, venda de técnica e falha fechada passaram em
conjunto (`48 passed`). O Ruff da mudança e `git diff --check` foram verificados;
alguns avisos F401/F841 preexistentes nos arquivos de teste permanecem fora
deste recorte. Isso fecha a fronteira de autoria exercitada, não toda a árvore
tecnológica, difusão natural ou provider real. WIP permanece sem commit/push.

## Autoria da decisão de reparo e manutenção — 25/09/2026

O owner `start_repair` não aceita mais um evento determinístico que apenas
repita os termos exatos do reparo. A autorização interna de projeto precisa ser
determinística, atual e diretamente causada pela escolha `ACTOR_DECISION` da
affordance recomposta para o mantenedor. O executor de autorização e o de
reativação também exigem uma decisão de ator atual. A política offline de
manutenção agora emite escolha auditável com `decision_source=fallback`, e a
execução de cada lote identifica a regra do owner Economy; isso não transforma
reparo em efeito automático nem remove sua exigência de materiais e trabalho.

Uma fixture que chamava o executor diretamente foi migrada para o fluxo normal
de manutenção. O recorte focal de infraestrutura, desgaste, cópia de técnica e
reparo após overflow passou (`27 passed`); Ruff e `git diff --check` passaram
nos arquivos alterados. Uma primeira rodada encontrou ainda uma fixture de
frete com autoria determinística; ela foi alinhada ao contrato atual da API, sem
relaxar o owner de logística. Isso fecha manutenção/reparo e as regressões
citadas, não a auditoria global de autoria, o provider real ou os gates naturais
longos. WIP permanece sem commit/push.

## Alfândega exige autoria de ator — 25/09/2026

Os owners de abertura de posto, resolução de carga, apreensão e pagamento
alfandegário agora rejeitam escolhas cuja origem não seja `ACTOR_DECISION`,
além de revalidarem o payload da affordance corrente. Uma decisão determinística
com os mesmos termos não pode abrir um posto. Fixtures de comando direto agora
registram explicitamente fonte `api`.

O recorte de alfândega, tarifas e embargo passou (`40 passed`); Ruff e
`git diff --check` passaram nos arquivos tocados. Isso valida esses fluxos e
seus casos cobertos, não a auditoria de todos os owners econômicos nem os gates
naturais longos. WIP permanece sem commit/push.

## Criatura exige decisão própria — 25/09/2026

O owner da criatura também exige agora uma `ACTOR_DECISION` atual cuja ação,
ator e affordance correspondam ao turno recomposto. A fome/percepção ainda só
habilitam opções; uma intenção determinística equivalente não pode abrir pedido
de tributo ou outra ação da criatura. A fixture que faz comando direto declara
`decision_source=api`.

Uma regressão confirma que a intenção determinística não altera o snapshot. Os
módulos de criatura, autonomia da criatura e sabotagem passaram (`17 passed`);
Ruff e `git diff --check` passaram. Isso protege o owner, não prova uma cadeia
natural de criatura interferindo numa campanha em andamento. Auditoria dos
demais owners e gates naturais seguem abertos; WIP sem commit/push.

## Intriga exige escolha de ator no owner — 25/09/2026

Owners de espionagem, suborno e sabotagem validam agora que a decisão selecionada
é uma `ACTOR_DECISION` do dia e corresponde exatamente à affordance recomposta.
Antes, esses caminhos conferiam payload/opção e data, mas ainda permitiam que
uma decisão determinística com o mesmo conteúdo iniciasse missão, proposta de
suborno ou dano material. Helpers que simulam comando direto agora registram
origem `api` explicitamente.

Um teste negativo por vertical confirma que a intenção determinística não
executa a ação e preserva o snapshot. Espionagem, suborno e sabotagem passaram
juntos (`22 passed`); Ruff e `git diff --check` passaram. Isso fecha somente
esses três owners. Alfândega, manutenção/reparo, pesquisa e os demais owners
materiais ainda precisam da auditoria de autoria. WIP segue sem
commit/push.

## Procurement e frete exigem decisão de ator — 25/09/2026

Na continuação da auditoria dos owners, compra de mercado, objetivo de
abastecimento, despacho para campanha, recuperação de frete/compra e frete
interno agora rejeitam `DECISION` determinística ou de interpretação quando uma
escolha material precisa ser de ator. `queue_freight` também exige origem
`ACTOR_DECISION`; os owners continuam recompondo a affordance e conferindo dia,
ator e payload antes da execução. Helpers de teste que representam comandos
diretos declaram `decision_source=api` explicitamente.

A auditoria descobriu que um objetivo sem relatório local atual era marcado como
bloqueado sem causa e, portanto, não persistia o plano. Agora o owner liga o
bloqueio ao último relatório canônico de inventário que possuía; sem relatório
fonte, continua sem inventar um plano. O cenário stale da fixture passou a
representar essa sequência de forma explícita.

Regressões negativas confirmam que intenção determinística não cria frete
interno, não materializa compra, não executa objetivo de abastecimento e não
despacha provisões da campanha; os casos verificam snapshot inalterado. Os seis
módulos de decisão civil, compra bilateral, logística, recuperação e campanha
passaram juntos (`70 passed`); Ruff e `git diff --check` passaram nos arquivos
tocados. Isso fecha os owners exercitados, não a auditoria global de autoria.
Os gates naturais e provider continuam abertos. WIP sem commit/push.

## Force exige autoria real e não consulta presença rival pelo ator — 25/09/2026

Os owners de Force agora aceitam apenas eventos `ACTOR_DECISION`; a
mobilização ligada a plano também verifica essa origem antes de retirar pessoas,
ração e folha. A affordance de ocupação deixou de consultar presença rival
canônica para o ator: ela usa o relatório próprio, e `occupy_settlement` continua
revalidando a presença material e rejeitando a ocupação quando um rival real já
está no local. Isso restaura a separação entre conhecimento e verdade sem
enfraquecer o owner.

O helper compartilhado dos owners Force agora só aceita eventos
`ACTOR_DECISION`; mobilização ligada a plano impõe a mesma origem no seu caminho
próprio. Fixtures de decisão direta identificam fonte `api`, e um teste negativo
confirma que decisão determinística não ergue coluna nem altera recursos. Uma
fixture de retirada agora cruza o limiar de abastecimento vigente após o consumo
do dia, em vez de presumir um estoque fixo obsoleto.

Validação focal: Force/comando/QG/aftermath/criatura/guarnição/resposta
estratégica — `69 passed`; oito módulos de campanha, interdição, cerco, posição,
retirada, concessão e avistamento — `50 passed`; revisão final do cerco e
regressões de ocupação/autoria — `22 passed`. Ruff e `git diff --check`
passaram. A auditoria de outros owners e os gates naturais/provider continuam
abertos; WIP sem commit/push.

## Autoria revalidada nos dois owners de objetivo estratégico — 25/09/2026

A auditoria focal encontrou o mesmo limite em dois owners da cadeia estratégica:
a adoção de defesa a um assentamento ocupado e a prioridade de abastecimento de
guarnição recompunham a affordance, mas podiam aceitar um evento de decisão
determinístico ou divergente. Ambos agora exigem `ACTOR_DECISION`, ator/ação
corretos e igualdade com a affordance atual antes de persistir o objetivo. As
fixtures que chamam esses owners diretamente registram agora autoria `api`
explícita.

Verificação conjunta de resposta estratégica, aftermath, interferência com
criatura e objetivo/política de guarnição: `57 passed`; Ruff e
`git diff --check` passaram. Isso fecha os dois caminhos exercitados, não a
auditoria de todos os owners. WIP permanece sem commit/push.

## Owner de objetivo de guarnição valida autoria da escolha — 25/09/2026

O owner que persiste a prioridade de rações da guarnição recompunha a opção,
mas não confirmava que o evento citado era a decisão atual daquele ator para
aquele `affordance_id`. Agora exige `ACTOR_DECISION`, ação e ator corretos e
igualdade integral com a opção recomposta antes de alterar `StrategyState`.
Regressões cobrem ação, ator, affordance e origem incompatíveis e confirmam que
nenhuma delas persiste o objetivo.

Verificação focada de objetivo/owner e política de guarnição: `20 passed`;
Ruff e `git diff --check` passaram nos arquivos tocados. Isso fecha uma fronteira
de autoria reproduzível, não a auditoria de todos os owners nem os gates naturais
longos. WIP permanece sem commit/push.

## Retaliação limitada ao fato contratual e folha da coluna — 25/09/2026

Uma obrigação de entrega quebrada abria `recourse`, mas as affordances de
marcha e ocupação podiam apontar para qualquer assentamento que o credor
conhecesse. Agora, enquanto o turno responde a um breach conhecido, a expansão
militar só aparece para a localização do estoque canônico de origem da entrega
prometida, desde que esse estoque continue pertencendo ao devedor; ocupação e
formalização de controle seguem o mesmo limite. Isso não determina que o credor
ataque: mantém a decisão e `NO_ACTION` com o ator. Se a origem material não
existe mais, não há essa opção de represália.

A validação da cadeia também revelou que a mobilização debitava o tesouro
corretamente, mas distribuía o salário entre qualquer coorte de soldados na
origem, em vez dos soldados que formaram a coluna. O owner agora exige a coorte
selecionada na folha, preservando o valor total e a conservação de moeda.

Verificação focal da trajetória de breach → opções limitadas → marcha/ocupação e
da presença militar sem administração automática: `2 passed`; o módulo de
recourse completo passou (`2 passed`). Ruff e `git diff --check` passaram nos
arquivos tocados. Isso não valida guerra natural nem provider remoto. WIP segue
sem commit/push.

## Idade da leitura de poder de compra — 25/09/2026

O dossier do ator já projetava a incapacidade de compra a partir do receipt
canônico de subsistência, mas não expunha quando esse receipt ocorreu. Um
relatório local renovado podia, portanto, carregar essa evidência anterior sem
deixar clara sua idade. Agora o contexto inclui `affordability_observed_day` e
`affordability_age_days` calculados em relação ao dia do relatório conhecido;
quando ainda não há receipt conhecido, ambas as datas permanecem desconhecidas.
Quantidades agregadas e ID causal continuam disponíveis, sem expor saldo
doméstico ou IDs de coorte.

Verificação focada: dossier econômico, composição do menu institucional e
situação de emprego — `16 passed`, com `CWS_DATA_DIR` isolado. Isso melhora a
interpretação temporal da evidência; não valida uma escolha nova de provider nem
fecha a resiliência econômica natural. Nenhum teste alterou saves reais.

Uma verificação composta adicional confirmou que o menu institucional que
oferece construção de oficina inclui também essa leitura datada do dossier base:
no dia 30, o ator recebe a observação de affordability do próprio fechamento,
com idade zero, ao lado das opções de trabalho local. Assim, a evidência não fica
restrita ao endpoint/dossier de observação. Continua faltando uma escolha remota
autorizada no schema atual e a trajetória econômica natural de longo prazo.

## Enforcement de autoria no ledger — 24/09/2026

O `record_event` rejeita agora qualquer fato de decisão de ator sem
`decision_source` válido já no momento do append; `validate_history` aplica a
mesma regra ao histórico persistido. Fontes provider precisam apontar para um
receipt anterior de interpretação/recusa, sem deltas, e corresponder ao ator e à
affordance escolhida. Fontes de fallback nomeiam política e regra; entradas de
jogador e API são declaradas explicitamente. Os owners de rito e venda de
técnica também exigem essa autoria.

Ao fechar o contrato, corrigi a divulgação de técnica no ensino: a oferta de
ensino já revela a técnica à contraparte e causa o receipt correspondente. O
owner de conhecimento agora reconhece a decisão original de oferta ou a
affordance explícita de divulgação, sem criar uma segunda escolha fictícia.
Verificação focada em diplomacia, conhecimento, autoria e auditoria: `35 passed`;
ritos, alcance, política de rito, interação com criatura, venda de técnica,
autoria e auditoria: `39 passed`. Ruff passou com `E701`, `E702` e `F401`
preexistentes ignorados e `git diff --check` passou. Em execução exploratória
mais ampla revelou coortes duplicadas em fixtures de treinamento e uma
expectativa de schema obsoleta no observatório. Corrigi as fixtures para usar
coortes soldier canônicas existentes e seus efetivos disponíveis, e atualizei a
expectativa para schema 74. Treinamento, cadeia de difusão por ensino/venda e a
projeção do observatório passaram juntos (`8 passed`). A varredura semântica de
todos os owners e o smoke natural do checkout atual seguem pendentes.

## Transições ACTOR_DECISION exigem decisão de ator real — 24/09/2026

O vínculo de autoria para transições materiais ficou mais estrito: não basta
apontar para qualquer `FactKind.DECISION` com os mesmos campos. Quando uma
transição declara `CausalOrigin.ACTOR_DECISION`, seu `decision_event_id` precisa
ser uma decisão cujo próprio `causal_origin` também seja `ACTOR_DECISION`, e
ator/affordance precisam corresponder. Isso impede que uma autorização
determinística criada pelo owner seja usada como se fosse a escolha do ator.
Uma regressão negativa cobre esse caso.

Fixtures de API agora registram `decision_source=api`; o stub provider dos
testes grava o receipt `LLM_INTERPRETATION` correspondente antes da escolha.
Infraestrutura, workforce, comando militar, engajamento e autoria passaram em
um recorte de `82 passed`. Isto cobre os owners tocados e não equivale à
auditoria semântica completa de todos os domínios. Ruff e `git diff --check`
foram verificados nos arquivos alterados; gates naturais longos seguem
pendentes.

Também ajustei fixtures de API que ainda gravavam escolhas de manutenção,
transição ocupacional, comando/engajamento militar, rito e criaturas com origem
default determinística; agora declaram `ACTOR_DECISION` e `decision_source=api`.
Seleções simuladas pela IA no teste de workforce emitem o receipt de provider
antes da escolha. O recorte de diplomacia, conhecimento, rito, criatura, venda
de técnica, autoria e auditoria passou (`67 passed`), além do recorte material de
infraestrutura/workforce/comando/engajamento (`82 passed`). Nenhum gate longo ou
provider remoto foi executado.

Um smoke natural offline da seed 73 percorreu 120 dias depois do enforcement,
com checkpoints nos dias 60 e 120 e continuação até 121. Houve 3.859 eventos,
conservação de moeda/recursos e round-trip dos saves. A auditoria de cada
checkpoint e do save final retornou `ok=true` e arrays vazios para causas
quebradas, autoria/fonte inválidas, transições sem decisão de ator e mutações
Story/interpretação. As métricas finais ainda mostram pressão: falta 93,
saúde média 951,25 e unrest médio 48,75; portanto esse smoke curto não certifica
resiliência nem substitui o gate natural de 3.600 dias.

O próprio smoke revelou que `medieval_causal_audit.py` classificava `fallback`
com `policy` e `rule` válidos como tipo não suportado. Corrigi o branch e
acrescentei caso de regressão; o módulo de auditoria/autoria passou (`9 passed`).

## Staffing limitado apenas reduz o alvo vigente e preserva autoria — 24/09/2026

Quando uma falha de folha em instalação abre affordances de revisão de
compromisso, os alvos positivos agora são calculados a partir do staffing atual,
e só aparecem se forem estritamente menores. Uma revisão posterior nunca pode
ser apresentada como redução e, na realidade, elevar o quadro acima do limite
que o empregador já escolheu. Suspensão continua disponível quando aplicável.

Os helpers de decisão direta para criação/revisão de vínculo também exigem
`decision_source`; chamadas de API e fallback registram sua origem. O teste
composto revelou que os dois caminhos de fixture gravavam `ACTOR_DECISION` sem
essa autoria, algo que o audit causal já detectava. Após corrigir os comandos e
as fixtures, o módulo completo passou (`22 passed`), incluindo nova pressão
depois de uma redução e auditoria causal do save. Isso fecha o contrato local do
staffing; não valida ainda uma decisão espontânea de provider no mundo natural
nem a recuperação econômica de longo prazo.

## QG revisa campanha direta após enchente natural — 24/09/2026

Uma coluna levantada por decisão explícita mas sem `StrategicPlan` não fica mais
fora do ciclo de comando: quando uma carga de campanha atrasada é de fato
carregada na bagagem, o QG recebe uma revisão logística própria. Com seus
relatórios datados, pode manter (`NO_ACTION`) ou escolher retirada; a decisão
recompõe a opção, exige autoridade operacional, revalida a rota e encerra avisos
abertos sem mexer em cargas pendentes. O caminho não cria um objetivo político
retroativo nem persiste affordances.

A seed 14 agora percorre na mesma trajetória a enchente natural do dia 240,
redução de capacidade, atraso do frete de campanha, aviso causal de seguimento,
entrega física e turno do QG; na fixture, o provider simulado escolhe retornar.
O save final passa auditoria causal. A coluna e o frete concorrente foram
preparados pela fixture, e a escolha foi simulada: isso prova interferência
ambiental e agência do QG sobre uma campanha direta, mas não formação espontânea
de guerra nem provider real.

Verificação focal: `test_natural_overflow_limits_active_campaign_rations_on_its_known_route`
passou; resposta estratégica e suprimento de campanha passaram em conjunto
(`26 passed`). Ruff e `git diff --check` passaram.

## Precisão da retirada após atraso logístico — 24/09/2026

A retirada estratégica distingue agora três estados físicos: uma parcela ainda
em trânsito bloqueia a affordance; uma obrigação já despachada também bloqueia;
um aviso aberto mas ainda não despachado pode ser encerrado como `lapsed` pela
decisão explícita do QG. O owner mantém a carga original intacta. A documentação
e o teste integrado foram alinhados para verificar o ID exato do aviso de
seguimento e sua ligação causal à decisão de retirada, além do save/load. Antes
de escolher, o contexto e os rótulos do menu também enumeram quais avisos abertos
cada rota de retorno encerrará; isso expõe o custo da affordance sem permitir
que o provider crie ou altere esses efeitos.

Verificação focal: Ruff, `git diff --check`, resposta estratégica e suprimento
de campanha — `26 passed`; a fixture integrada e a trajetória natural isoladas
passaram novamente (`2 passed` em 29,68 s). O teste natural
continua sendo uma trajetória de suprimento após enchente; não prova que a
enchente leve o QG a retirar naturalmente, nem valida provider remoto. O WIP
permanece sem commit/push.

## `NO_ACTION` preserva autoria provider — 24/09/2026

As recusas explícitas nos menus individuais e institucionais agora apontam para
o receipt corrente `ai_decision_declined`: o helper valida ator, dia e causas,
anexa o receipt à decisão e registra `decision_source.kind=provider`. Isso
impede que a ausência escolhida pelo ator apareça como decisão sem origem ou
seja confundida com falha técnica. A mesma regra agora atende o menu
institucional composto e os caminhos que já usam `record_no_action_decision`.

Verificação focal: 123 testes passaram em 13 módulos de recusas, menus,
causalidade e verticais consumidoras; Ruff passou nos arquivos tocados
ignorando `E702` preexistente e `git diff --check` passou. Isso fecha a
proveniência desses caminhos testados, não a auditoria de todos os turnos nem
os gates naturais/provider de longo horizonte.

## Autoria dos fallbacks econômicos — 24/09/2026

Os fallbacks offline de emprego permanente e transição ocupacional agora
registram `decision_source` com `kind=fallback`, `policy=routine-rules` e a
regra específica. O mesmo foi aplicado à compra de provisões domésticas e à
resposta automática do vendedor offline, à compra/venda de abastecimento,
frete, tarifa de exportação, serviço local de site, migração e revisão
diplomática. As decisões diplomáticas de rotina e os pedidos de oferta,
resposta e cumprimento recebem `routine-rules`; uma seleção no turno composto
do provider continua marcada `provider`. Assim, esses receipts não podem ser
confundidos entre si, e escolhas externas/injetadas não são rotuladas como
fallback. Outras rotinas offline ainda precisam de auditoria, então isto não é
declaração de cobertura global.

Na manutenção de infraestrutura, a decisão offline que autoriza um projeto
marca `routine-rules`; quando a affordance é escolhida pelo provider, a origem
é propagada até a autorização material. Os lotes seguintes registram fonte
`owner/economy`, pois são progresso do projeto já autorizado, calculado pelas
condições atuais de materiais, trabalho e caixa, e não uma nova escolha do
ator. Isso não altera a regra física nem torna reparo obrigatório.

Verificação focal consolidada: emprego permanente, transições ocupacionais,
provisões domésticas e auditoria causal, `69 passed`; autonomia, tarifas e
serviços de site, `28 passed`. Um round-trip de save/load preserva as fontes
`routine-rules` das decisões bilaterais de provisões. Ruff passou nos arquivos
tocados; em `test_medieval_tariffs.py`, foi ignorado somente um `F841`
preexistente fora deste diff. Em seguida, diplomacia offline/provider e
migração passaram em `31 passed`; os receipts distinguem as duas fontes. Ruff
passou isolando findings anteriores de estilo: `E701` em `diplomacy_policy.py`;
`E701`/`E702`/`F401` em `test_medieval_diplomacy_policy.py`; e `F841` em
`test_medieval_tariffs.py`. `git diff --check` passou. Isso fecha somente a
autoria dos caminhos citados, não uma auditoria de todos os fallbacks,
autonomia econômica natural, provider real ou o gate longitudinal.

Verificação focal adicional de autorização e progresso de reparos com o menu
civil: `43 passed`. Ruff passou em `infrastructure.py` e seu módulo de testes;
em `test_medieval_concurrent_civil_decision.py`, foi ignorado apenas um
`F841` preexistente em fixture alheia a esta mudança. O teste cobre fallback,
seleção provider, propagação até a autorização e fonte `owner/economy` dos
lotes.

## Sonda de decisão real usa o menu institucional/econômico atual — 24/09/2026

`tools/medieval_provider_probe.py` recompõe agora o menu mensal institucional
completo, não apenas `CIVIL_ADAPTERS`. A sonda escolhe uma polity cuja situação
natural oferece ao menos duas affordances concorrentes de `production_priority`
e consulta com todos os demais adapters/rótulos atuais presentes no mesmo menu.
Continua apenas interpretativa: não executa owners nem aplica deltas; o resultado
identifica se foi escolhida uma opção da família econômica ou `NO_ACTION`. Ao
compor esse menu, descobri que prioridade produtiva compartilhava a chave de
contexto `production` com construção de instalações; como o agregador permite
um builder por chave, isso ocultava o contexto de concorrência de folha/insumos.
Agora `production_priority` possui uma chave separada e a consulta mantém
visíveis ambas as leituras. Os testes focados de sonda, prioridade produtiva,
composição institucional e cadeia de oficina passaram (`21 passed`), com Ruff e
`git diff --check`. Nesta
continuação,
nenhuma chamada remota foi feita: a autorização anterior era de uso único e já
foi consumida. O probe pode ser executado quando houver autorização atual, mas
seu teste local não prova decisão de provider real. O gate natural offline de
3.600 dias foi interrompido sem relatório final; veja abaixo.

## Ordem política recebida pelo QG e interrupção causal — 24/09/2026

O prompt do QG numa defesa persistente agora recebe a ordem política canônica
(evento emissor, dia, titular, plano e ação autorizada) junto da leitura
territorial própria. Essa situação só aparece depois do turno político e
permanece verificável após save/load; a escolha de mobilizar continua sendo do
QG e a execução, do owner Force. Um teste que passava a decisão pelo limite JSON
normal do provider revelou que reroute/retirada podia passar IDs de relatório
duplicados para o receipt, abortando a escolha quando havia várias rotas; agora
`ai_decider._receipt` deduplica referências de causa compartilhadas sem deixar de
validar IDs desconhecidos no ledger; os chamadores também normalizam listas
compostas com `_causes`. A cadeia focada de política → QG → comandante,
incluindo criatura fechando rota, coluna parada, retirada e auditoria causal
após save/load passou em três testes; a regressão central de receipt e a suíte
focal de decisão/QG passaram em conjunto (`15 passed`), com Ruff e
`git diff --check`. É evidência em fixture com provider simulado, não formação
espontânea em mundo natural nem validação de provider externo.

## Otimização medida da capacidade estratégica — 24/09/2026

`StrategyState.capacity_for` continua derivando os mesmos estados e referências
dos registros canônicos, mas lê diretamente os campos persistidos de modelos
Pydantic em vez de invocar `__getattr__` para cada campo de propriedade ausente.
O fallback por `getattr` permanece para registros com slots. No mesmo checkpoint
do dia 510 e no mesmo profiler, a recomposição do menu caiu de 1,469 s para
1,252 s (33 atores, 280 affordances nas duas execuções); o trecho
`capacity_for` caiu de 0,305 s para 0,090 s. São medições únicas sob profiler,
não um benchmark estável nem evidência de gate de escala. Os cinco testes de
`tests/test_medieval_strategy_capacity.py`, Ruff no módulo e `git diff --check`
passaram.

## Gate natural interrompido sem relatório final — 24/09/2026

O `tools/medieval_release_gate.py --days 3600 --checkpoint-days 360` executou
offline na seed 73. O último checkpoint formal que foi observado era o dia
3.240; naquele ponto havia população 8.500, 2.440 mortes acumuladas por
privação, 41 rações faltantes no mês, saúde média 177,38 e unrest médio 266,75.
A última linha de progresso emitida chegou ao dia 3.270: população 8.480,
2.460 mortes, falta mensal 69, saúde 179,38 e unrest 213,12. Depois, o handle do
processo deixou de existir e `/tmp/cws-final-gate-20260924` não está mais
presente. Não foi localizado relatório final nem auditoria causal; portanto o
run é incompleto e não aprova o gate. As execuções longas finais devem ocorrer
depois das correções e preservar seus artefatos fora de diretório temporário
volátil.

## Acesso alimentar e autoria do alívio — checkpoint histórico do dia 3.240

Uma leitura read-only do checkpoint mostrou que a falta não é uniforme nem pode
ser reduzida a “produção insuficiente”. No receipt `subsistence_resolved` de
Campomanso, 28 rações ficaram sem compra: 21 eram do grupo de artesãos orcs,
apesar de estoque público 2.224 e preço local 1. Em Pedra Clara, 2 rações de
artesãos humanos ficaram sem compra com estoque público 69.200 e preço 1. Já em
Pontenegro, Ferroalto e Salgueiro, faltas de 68, 779 e 495 rações, respectivamente,
foram seguidas no mesmo dia por distribuições materiais de exatamente esses
volumes; os receipts mostram os estoques domésticos abastecidos e mudanças de
necessidade/saúde/unrest com decisão e fontes. Isso demonstra um caminho causal
de alívio no fallback offline, não escolha de provider nem recuperação econômica
duradoura. Limitações observadas nas fazendas variaram entre mão de obra,
armazenamento e folha; não há uma única correção mecânica comprovada.

O receipt histórico `relief_distribution_decided` identifica a affordance e a
decisão, mas não persistia que a escolha veio do fallback. O fallback futuro de
distribuição local agora grava `causal_payload.decision_source` com
`kind=fallback`, `policy=routine-rules` e `rule=urgent_local_relief`. Saves
históricos não são reescritos; essa alteração ainda precisa ser observada em um
novo run. A política compartilhada de ajuda institucional também agora grava
`decision_source` em decisões `routine-rules`. Quando a decisão veio do provider,
ela grava o ID do receipt `ai_decision_interpreted` e o liga causalmente à
decisão do ator; o owner continua recebendo como causa direta a decisão, não a
interpretação. Isso evita atribuir silenciosamente ao provider uma escolha do
fallback nessa vertical. Testes focados de alívio e ajuda institucional passaram
(`31 passed`); ainda não é uma auditoria de autoria de todos os domínios.

A leitura histórica do checkpoint do dia 2.520 confirma que não há um único
gargalo: Campomanso tinha 9.040
unidades de comida em estoque público, mas ainda registrava falta 73 e saúde
247; Pontenegro tinha 289 unidades públicas, falta 111 e cotação 6; Ferroalto
tinha 11.959 unidades públicas e nenhuma falta corrente, mas saúde acumulada
44. Estoque atual, falta corrente e dano histórico de saúde não são a mesma
medida. A trajetória exige separar escassez local, poder de compra e duração da
privação; não justifica distribuição automática ou balanceamento por quota.
O recibo estruturado `subsistence_resolved` daquele dia discrimina o acesso:
em Campomanso, 64 das 73 rações não compradas pertenciam ao grupo de artesãos
orcs; em Pontenegro, 91 das 111 faltantes pertenciam a grupos de agricultores
(48 humanos e 43 orcs), coerente com seu estoque menor/cotação alta; em Ferroalto,
22 das 46 faltantes eram do grupo de artesãos orcs. Cinzaverde teve 5 faltantes,
um em cada um de cinco grupos pequenos. Isso localiza quem ficou sem acesso,
mas ainda não identifica por si só a affordance de recuperação que cada ator
conhecia ou por que a escolheu/ignorou; esse é o próximo diagnóstico após a
auditoria formal do gate.

Uma consulta read-only às affordances da mesma gravação encontrou, para a
polity Auren, três opções válidas de construir oficinas, quatro de distribuição
local de alívio e oito de transferência de alívio; sua configuração tinha
`ai_enabled=False`. Nesse limite, `relief_distribution_decided` não representa
uma escolha do provider: `review_relief_fallback` aplica a política offline
de maior falta observada/cobertura disponível e não substitui o turno IA de
construção. Assim, o run mostra que havia uma opção estrutural além do alívio,
mas não prova que uma IA a ignorou, nem que construí-la seria a decisão correta.
Esse é um limite de interpretação importante do gate offline.

## Custo do menu mensal no save do dia 510 — 24/09/2026

O profiler read-only `tools/medieval_decision_menu_profile.py` mediu o menu do
save `/tmp/cws-econ-followup-day510.mws` (schema 74, 18.947 eventos). A execução
inicial levou 4,10 s para 33 atores, 280 opções e 33 contextos. O perfil mostrou
buscas de todo o ledger repetidas por site na elegibilidade de sabotagem (0,92 s),
por ator na recomposição de compras domésticas abertas (0,44 s) e reconstrução
do mapa de eventos durante validação de relatórios de infraestrutura (0,44 s).

As leituras agora reutilizam índices transitórios existentes no mundo:
decisões por ator, eventos por tipo e `event_index()`. Nenhum cache novo é salvo,
nenhuma affordance ou regra mecânica mudou. A busca de evidência estratégica
também passou a consultar apenas eventos do tipo correspondente, em vez de
percorrer todo o ledger. No mesmo checkpoint e ferramenta, a última medição
caiu para 1,94 s, mantendo 33 atores, 280 opções e 33 contextos (redução
observada de aproximadamente 53% frente à primeira execução única; é um
indicador, não um benchmark estável nem gate de release). O perfil posterior
passou a concentrar custo em `_by_id` (1,27 s), `monthly_actors` (0,62 s),
projeções de capacidade estratégica, contexto diplomático e previews de
suprimento; o trabalho de escala continua aberto.

Verificações focadas: economia/campanha/interferência, 27 testes; supply/cerco/
comando/aftermath/estratégia, 66; mercado de famílias e sabotagem, 18;
infraestrutura/relatórios/sabotagem/roubo de tecnologia, 34; e dossiê/diplomacia/
sabotagem depois do último ajuste, 37. A fixture de sabotagem agora reserva
soldados de uma coorte canônica existente e cobre a regra de uma sabotagem por
site/ator/dia, sem duplicar demografia. Ruff passou nos arquivos de
infraestrutura, compras e contexto diplomático; nos arquivos de sabotagem foram
ignorados somente `F401`/`F841` preexistentes e não alterados. `git diff --check`
passou. O checkpoint foi aberto somente para leitura e a cópia de round-trip do
profiler foi temporária.

## Revalidação natural curta no checkout atual — 24/09/2026

Após as alterações de pós-combate, o gate natural da seed 73 foi repetido por
120 dias com checkpoint, sem provider real. O release gate retornou `ok=true`;
conservação de moeda/recursos, save/load e auditoria causal passaram em 3.833
eventos, sem causa quebrada, erro de autoria, mutação por interpretação LLM ou
chamada real. O mundo terminou com zero mortes por privação, falta mensal 16,
saúde média 951,25, unrest médio 48,75, 4 vínculos de emprego e 51 transições de
força de trabalho. Confirma a integridade do horizonte curto, não economia
resiliente nem autonomia com provider real.

## Gate natural pós-correções: 480 dias, seed 73 — 24/09/2026

Depois de impedir folha em sites sem instalação produtiva e corrigir a autoria
de recibos sem provider, a seed 73 foi rodada novamente por 480 dias, com saves
e auditorias a cada 120 dias. Dinheiro/recursos conservaram, save/load e
continuação ficaram equivalentes, e a auditoria final passou em 17.832 eventos:
zero causa quebrada, erro de autoria, material por interpretação ou
interpretação LLM. As 12 consultas que não puderam ocorrer foram recibos
`ai_decision_failed` determinísticos; `real_ai_calls=0`.

No dia 480: falta mensal 355, saúde média 870,88, unrest médio 47,38, zero
mortes por privação, 52 migrações e 42 cumprimentos de ajuda em 45 pedidos. O
save final tem 5.767.168 bytes. Isso prova integridade causal do horizonte, não
uma economia resiliente: houve falta alimentar relevante e saúde média caiu em
relação ao smoke schema 72 anterior. Não houve provider real, e o resultado não
fecha o gate de três seeds por 3.600 dias.

## Resposta independente do lado derrotado — 24/09/2026

O fim de um combate de campo já não dispersa automaticamente as colunas
sobreviventes do lado derrotado. O fato de batalha encerra os contatos armados
daquelas colunas e agenda primeiro um turno privado ao lado derrotado; o vencedor
recebe seu turno no dia seguinte. Cada instituição pode escolher entre as
affordances materiais atuais para cada coluna participante, incluindo retirada,
dissolução e nomeação de comandante quando válida. Se a coluna continua no local,
o owner ainda bloqueia ocupação rival; território não é concedido pelo resultado
do combate. Vários reforços participantes recebem opções próprias, em vez de
ficarem abandonados fora do receipt principal.

Fixtures com provider simulado provam tanto dissolução quanto retirada material
da coluna derrotada, com decisão da instituição, autoria `ACTOR_DECISION` e
causal link ao resultado. Dissolver retorna a força à população; retirar inicia
uma marcha para destino conhecido; nenhuma escolha concede ocupação. Save/load
mantém as revisões agendadas; `NO_ACTION`/provider indisponível continuam sem
executar resposta. Verificação focal: 26 testes de combate e aftermath passaram;
somando 8 testes de comando de força, 34 passaram. Ruff nos cinco arquivos Python
envolvidos e `git diff --check` passaram. A mudança resolve o descarte
automático no recorte de batalha, não prova formação natural de campanha,
coordenação estratégica completa, nem smoke longo atualizado.

Como uma decisão pode agora incluir várias colunas, os rótulos do menu de
aftermath também passaram a distinguir ID da coluna, destino e rota, em vez de
apresentar escolhas materialmente diferentes com a mesma descrição.

## Continuação causal do diagnóstico econômico: dia 510 — 24/09/2026

O mesmo save foi continuado por mais 30 dias, sem provider e sem alterar a
política, para verificar se a limitação de folha do dia 480 se desfazia no
ciclo seguinte. A conservação e o round-trip/continuação de save-load passaram;
a auditoria causal do save do dia 510 também retornou `ok=true` em 18.947
eventos, sem causa quebrada, erro de autoria, efeito material por interpretação
ou chamada real de IA. Ainda assim, a falta mensal subiu de 355 para 378 e a
saúde média caiu de 870,88 para 861,50; não houve morte por privação nesse
recorte.

O ledger identifica a pressão: no dia 510, salários de contratos permanentes
reduziram os caixas de Auren, Escarlia e Valedouro, respectivamente, de 2.561,
2.424 e 1.687 para valores entre 0 e 5 antes da produção. Dez instalações
registraram `payroll_funds=0` e zero lotes; a madeireira de Salgueiro foi a
exceção, com um lote. As compras domésticas ocorreram depois e voltaram a
creditar os caixas públicos, portanto saldo positivo no fim do dia não estava
disponível retroativamente para a produção daquele ciclo.

Isso não demonstra que o caixa tenha sido criado nem que o motor tenha ignorado
uma ordem de produção: as despesas de emprego e a produção são transações
materiais distintas e conservadas. A affordance de reduzir/suspender um vínculo
exige recibo atual de produção limitada; seu executor já permite uma decisão do
empregador. No modo offline, porém, a política não escolhe essa revisão. Assim,
o resultado aponta para uma dependência ainda não validada: o ator/provider
precisa comparar folha contratada com a produção que deixou de ser financiada.
Não se adicionou ajuste automático, crédito, subsídio ou prioridade para a
recuperação. A economia natural continua aberta.

## Oferta de emprego exige trabalho material representado — 24/09/2026

A revisão da seed natural encontrou opções de folha permanente em instalações
vazias: em Auren, 8 de 16 opções apontavam agricultores ou soldados para um
posto sem linha produtiva. O owner agora só oferece vínculo quando o site possui
uma instalação cuja receita usa aquela ocupação. Isso evita pagar/reservar
trabalhadores para uma atividade que a simulação não representa; a construção
de oficina continua sendo apenas capacidade e precisa da fundação/operação
separada antes de oferecer folha.

Verificação focal: 40 testes selecionados de emprego e construção de oficina
passaram; Ruff e `git diff --check` passaram. Na seed 73, Auren agora tem 8
opções de emprego, todas ancoradas em instalação compatível. O smoke natural
repetido por 120 dias passou conservação, save/load e auditoria causal. Em
relação ao run anterior, contratos de emprego caíram de 15 para 4; a saúde média
passou de 952,88 para 951,25 e a falta mensal de 15 para 16. Não houve mortes.
Essa seed curta não prova a resiliência econômica; mostra que remover empregos
sem trabalho representado custa renda no fallback atual, sem esconder esse
efeito com subsídio ou regra de recuperação.

## Smoke do checkout atual: 120 dias provider-free, pós-correção de emprego — 24/09/2026

A seed 73 avançou do dia 0 ao 120 com `ai_enabled=false`, `policy=routine-rules`,
sem perfil de teste e sem provider. O motor conservou dinheiro/recursos e
save/load mais continuação ficaram equivalentes. A auditoria causal standalone
terminou `ok=true` em 3.833 eventos, com 51 transições materiais sob autoria de
decisão e zero interpretação LLM. No dia 120: falta alimentar mensal 16, saúde
média 951,25, unrest médio 48,75 e nenhuma morte por privação; houve 9 pedidos
de ajuda, 6 cumprimentos, 7 distribuições de relief, 7 compras de mercado,
4 contratos de emprego e 51 transições de workforce. O save final tinha
2.256.896 bytes.

Este é um smoke curto de estabilidade e causalidade sob as regras/fallbacks
determinísticos do modo `routine-rules`, não evidência de decisão por IA. Ele
mostra pressão localizada crescente (Pedra Clara chegou a unrest 141) e nenhum
protesto até esse horizonte; não prova que um provider escolheria oficina,
organização cívica ou campanha. O gate de economia natural de longo horizonte e
as decisões com provider real seguem abertos.

## QG decide após combate inconclusivo — 24/09/2026

O turno independente do QG após boletim de combate agora também cobre um
empate. O relatório precisa ter sido publicado pela própria instituição e
entregue ao seu QG; a affordance é recomposta para o destacamento sobrevivente
daquele lado, usando rotas e destinos que o QG conhece. O titular escolhe
retirar ou `NO_ACTION`/manter; o owner revalida autoridade, relatório, carga e
rota antes de iniciar a retirada. Derrotas em que a regra atual dispersa a
coluna derrotada continuam sem opção de retirada por esse caminho.

O teste focal produz um empate real com forças iguais (a fixture revelou que o
destacamento disponível era menor do que a população nominal usada no setup),
entrega boletim ao QG correto, escolhe retirada e confirma autoria causal na
marcha e no plano. O arquivo inteiro `test_medieval_field_aftermath.py` passou
(`15 passed`); o teste existente de retirada após vitória também passou. A
prova segue sendo fixture com provider simulado, não formação natural nem
provider remoto.

## Controle territorial cessa quando a guarnição colapsa — 24/09/2026

Uma auditoria da saída de campanha confirmou que o owner já revoga controle
territorial quando a guarnição perde sua sustentação; faltava uma regressão que
atravessasse a sequência completa. A nova fixture estabelece controle válido
para o defensor, inicia um cerco real, deixa a pressão datada colapsar a
guarnição e verifica o evento `territorial_control_lapsed` causalmente ligado
ao colapso. Ocupação e administração continuam com seus titulares: a brecha
não transfere a cidade. O estado final também passa a validação de `Society`.

O teste focal passou. Isso fecha a evidência local de revogação automática por
perda da base material; não fecha a auditoria geral de campanhas prolongadas,
cessar-fogo, concessões ou remediação.

## Cessar-fogo não cria obrigações concorrentes — 24/09/2026

Após a aceitação de um cessar-fogo, o acordo ainda precisa ser cumprido por
retiradas materiais independentes. Nesse intervalo, o mesmo cerco permanecia
com as colunas presentes e o código só bloqueava novas propostas que ainda
estivessem `offered`; isso permitia empilhar outro compromisso sobre as mesmas
forças. A enumeração agora também bloqueia novo acordo enquanto existir termo de
retirada aceito e `active`. Propostas rejeitadas/expiradas e obrigações já
concluídas não mantêm esse bloqueio.

A regressão verifica que ambos os lados deixam de receber novas affordances
após o aceite, mas mantêm as opções materiais do acordo existente. O recorte
combinado de cerco, força e campanha persistente passou em `32` testes; Ruff
para os arquivos tocados ignorando apenas findings preexistentes (`E402`,
`F401`, `F841`) e `git diff --check` também passaram. Isto não executa retirada
automaticamente: cada termo continua exigindo ação própria.

## Autoria ao cumprir retirada por acordo — 24/09/2026

Uma regressão focal encontrou dois problemas no ciclo de campanha. O review de
abastecimento agora compõe as necessidades e opções válidas de todas as colunas
do mesmo proprietário num único menu diário, com quantidade/local para comparar,
sem deixar um aviso sem rota/estoque executável consumir uma consulta nem
esconder outra coluna elegível. A decisão material aponta só ao aviso
selecionado. Também havia executores de retirada por cessar-fogo, desescalada ou
cerco que substituíam o ID de affordance escolhido por um ID interno de rota na
transição material. O owner agora preserva o ID externo realmente selecionado
até a retirada física, de modo que a validação de autoria confirma a decisão
original. O teste de supply verifica o delta de provisões efetivamente carregado
em vez de exigir saldo mínimo após dias posteriores de consumo. Foram aprovados
11 testes focados de abastecimento, cumprimento de cessar-fogo e desescalada;
Ruff nos arquivos tocados (ignorando findings preexistentes E402/F401) e
`git diff --check` também passaram. Isso fecha um erro de autoria no caminho de
saída política, não a auditoria ampla das campanhas nem sua formação natural.

Uma regressão adicional usa duas colunas reais do mesmo proprietário e seus
avisos abertos reais. O review faz uma única consulta; o contexto inclui a
necessidade das duas colunas, enquanto as escolhas contêm somente despachos
atualmente válidos para ambas as colunas. Após selecionar e despachar uma,
o owner recompõe as opções e o aviso aberto da outra recebe revisão no dia
seguinte, em vez de perder sua única situação agendada. Depois do save/load,
essa revisão reaparece, o ator escolhe a outra coluna e o owner abre o segundo
frete em decisão separada; nenhum frete é aberto automaticamente. A fixture
prova duas colunas com opções reais acionáveis em turnos consecutivos, mas não
uma campanha longa. O arquivo completo `tests/test_medieval_campaign_supply.py`
passou (`6 passed`); Ruff passou ignorando o `E402` do import tardio
preexistente em `campaign_supply.py`, e `git diff --check` passou.

## Contraparte atual em concessão administrativa — 24/09/2026

Uma proposta de transferência administrativa pós-ocupação permanecia
respondível pelo antigo administrador depois que a administração do assentamento
mudava. A affordance de oferta também não incluía a identidade da contraparte
no ID, permitindo reaproveitar a decisão anterior após a mudança. Agora o ID
vincula a administração enumerada, e a resposta revalida que o atual
administrador ainda é exatamente a contraparte que recebeu a proposta, com os
termos devedor/credor coerentes. Uma transferência independente entre oferta e
resposta invalida a opção antiga sem aceitar o acordo.

Verificação focal: `tests/test_medieval_administration_concession.py` passou
(`8 passed`) e a affordance integrada pós-ocupação em
`tests/test_medieval_siege_campaign.py` passou (`1 passed`); Ruff e
`git diff --check` passaram. Isto fecha stale/retarget nessa modalidade, não a
auditoria de campanhas longas ou formação natural de acordos.

## Boletim factual de combate para titulares distantes — 24/09/2026

Relatórios locais tipados agora incluem resultados de combates resolvidos no
mesmo assentamento nos últimos 30 dias: participantes, vencedor, baixas e evento
material-fonte. Observadores que sejam donos de destacamentos presentes também
produzem relatório local; a distribuição a um titular de QG continua usando o
boletim de assentamento existente e exige caminho físico alcançável. A leitura
tem deltas e causal links validados contra o combate original; alterar baixas no
DTO sem alterar o fato é rejeitado. Uma prova focada confirma o caminho
combate → observação própria → publicação → receipt do QG, com save schema 74.
O inspetor de assentamento no Observatório agora mostra leituras de combate dos
relatórios disponíveis, deduplica pelo engajamento e abre o evento-fonte. Isso é
a visão omnisciente do Dao; não altera o conjunto de fatos que qualquer NPC
conhece. A interface e o type-check passam com essa forma de resposta. Isso
entrega e torna legível o conhecimento. No dia seguinte ao boletim, um QG com
autoridade operacional pode consultar affordances de retirada da própria coluna
vencedora ou sobrevivente de um empate, limitadas às próprias leituras atuais de rotas e assentamentos; o
provider escolhe entre esses IDs ou `NO_ACTION`, e o owner de força revalida a
rota material antes de iniciar a marcha. A decisão e o movimento citam o
boletim de combate e os recibos de rota; a transição material registra
`ACTOR_DECISION` com decisão, ator e affordance. Se houver plano estratégico
ativo vinculado à coluna, o owner o passa a `withdrawn` quando o retorno começa;
esse vínculo de plano não foi incluído na fixture deste recorte. A fixture
focada cobre escolha, rota obsoleta, save/load e execução com provider
simulado. Isso não fecha o retorno em si nem mede provider real; uma resposta
do titular político ao mesmo resultado tático ainda falta. Os 43 testes focados de aftermath,
conhecimento de rotas e estratégia passaram, junto com Ruff e `git diff --check`.

## Cadeia material de renda local — fixture com seed natural — 24/09/2026

Validei duas provas focadas que já existiam no checkout. A seed 73 intacta
oferece uma obra de oficina ao lado do censo datado de Pedra Clara; `NO_ACTION`
mantém a cidade inalterada. Numa comparação pareada, um provider simulado
seleciona, em dias diferentes, construir a oficina, fundar uma linha de
ferramentas e depois contratar artesãos por affordances enumeradas. Não há
estoque, tesouro ou população adicionados à fixture. Os owners pagam materiais,
trabalho de construção e salários; a linha produz ferramentas e o saldo real
dos domicílios permite comprar mais alimento. Aos 390 dias, o ramo de decisões
teve mais compra/saúde e menos falta que o controle `NO_ACTION`, mas ainda teve
rações faltantes. O teste verifica save/load e auditoria causal. É uma prova
controlada de que a economia pode gerar renda e recuperação material por uma
cadeia válida; não prova seleção espontânea, provider real ou recuperação
duradoura.

Foram executados os dois testes dessa vertical: `test_unmodified_seed_offers_workshop_beside_dated_livelihood_reading`
e `test_unmodified_seed_can_fund_workshop_and_pay_artisans_without_extra_resources` —
2 passaram em 33,35s. Assim, o item econômico já tem um caminho causal material
demonstrado; a escolha natural pelo provider e a saúde macroeconômica de longo
horizonte ainda faltam.

## Diagnóstico econômico same-seed no schema 72 — 24/09/2026

O smoke natural da seed 73 avançou 120 dias no schema 72, com conservação,
save/load/continuação e auditoria causal aprovados; não houve provider real. A
comparação econômica do `tools/medieval_release_gate.py --economic` repetiu o
mesmo seed/horizonte com quatro políticas determinísticas de teste, cada uma
escolhendo affordances canônicas e sem alterar o engine. Todas as quatro
auditorias ficaram `ok`, sem causa quebrada, erro de autoria ou interpretação
material.

Os resultados deixam a pressão mais nítida: no dia 120, `desatento` terminou
com 6.266 rações faltantes, saúde 886,12 e unrest 113,88; `mercado` comprou
quatro vezes, mas terminou com 6.259 faltantes e saúde 887,25; `mobilidade`
criou 24 vínculos e fez 47 transições de trabalho, mas ainda terminou com
4.694 faltantes, saúde 899,38 e unrest 100,62. Já `alivio` distribuiu nove
rações de ajuda, terminando com 68 faltantes e saúde 947,50, mas não fez
compras, emprego ou transições. Nenhuma política teve morte por privação neste
horizonte. O contraste não prova uma solução econômica nem autonomia de IA: são
perfis offline explícitos, e os dados mostram que emprego/mobilidade isolados
não substituem acesso alimentar imediato.

Inspeção read-only do save natural do dia 120 mostra a forma local dessa causa:
Pedra Clara tinha 2.118 artesãos e 1.270 moedas somadas nas contas domésticas,
sem instalação artesanal local; Portovelho tinha 1.762 artesãos, 1.066 moedas
domésticas e também não tinha instalação artesanal local. Seus estoques
canônicos de comida eram 4.976 e 4.138, respectivamente, com preços 3 e 2:
não era ausência física de alimento, mas baixa renda distribuída entre grandes
coortes. Em Ferroalto havia uma mina de ferro que pagara 590 artesãos, mas
operava limitada por integridade do sítio; a linha de ferramentas existente
estava limitada por caixa de folha. Auren e Valedouro tinham affordance válida
de construir oficina em seus próprios assentamentos, mas ainda não a haviam
construído. Isso identifica oportunidades e limites concretos, não prova que
uma instituição deveria escolhê-los nem que a construção, isoladamente,
recuperaria a economia.

Como passo pequeno para decisões futuras mais informadas, o contexto da
affordance de emprego agora inclui leituras datadas de residentes por ocupação,
trabalhadores já pagos nas instalações próprias, pressão alimentar reportada e
incapacidade de compra observada. As fontes de censo/folha e o report de
affordability entram nos links causais da decisão. Não são expostos saldos de
conta/estoque e o owner continua revalidando oferta, autoridade e recursos. A
regressão focal `tests/test_medieval_permanent_employment.py` passou com 20
testes; Ruff, compileall e `git diff --check` passaram. Nenhum efeito dessa
ampliação de contexto sobre uma escolha de provider real foi medido; um teste
com provider simulado confirma que a decisão cita os eventos de censo/folha do
contexto. Economia natural
resiliente, provider real no schema atual e gate de longo prazo continuam
abertos.

## Horizonte natural de 480 dias — schema 72 — 24/09/2026

Rodei a seed natural 73 por 480 dias em `routine-rules`, sem provider real e
com checkpoints a cada 120 dias. O processo concluiu o dia 480, retomou e
avançou até 481. Dinheiro e recursos foram conservados, save/load foi
equivalente, e o save final mais os quatro checkpoints passaram auditoria
causal (`ok=true`, sem causa quebrada, erro de autoria, evento Story material
ou interpretação com delta). O run produziu 17.777 eventos, durou 99,8s,
salvou 5.591.040 bytes e atingiu 327.118.848 bytes de memória máxima.

No fim: população 10.930, zero mortes por privação, falta mensal 173, saúde
média 877,62 e unrest 81,75; a soma de falta mensal registrada nos 16 ciclos
foi 1.310. O fallback explícito registrou 45 pedidos de ajuda, 42 cumprimentos,
37 distribuições de alívio, 42 compras, 37 vínculos de emprego, 79 transições
de trabalho e 27 migrações. Portanto o mundo permaneceu materialmente íntegro,
mas não economicamente saudável nem recuperado; a trajetória inclui políticas
offline e não mede comportamento de provider. Este resultado do schema 72
substitui como evidência atual o smoke schema 71 do mesmo horizonte; não fecha
o gate de três seeds por dez anos.

## Reencaminhamento de coluna parada por rota fechada — 24/09/2026

Uma campanha defensiva mobilizada agora pode recompor uma rota quando a coluna
atinge fisicamente um trecho fechado. A affordance só aparece após a própria
instituição e o titular atual do QG terem recebido leituras datadas e atuais
de que o trecho está interrompido e de cada trecho alternativo. Os boletins
para o QG seguem a rede física; não são copiados da memória institucional. O
caminho é calculado pela engine;
QG seleciona o ID ou `NO_ACTION`, e o owner militar recompõe conexão, passagem,
autoridade e ordem política antes de substituir o restante da rota. A decisão
do QG, a rota escolhida, a coluna, o bloqueio e os relatórios usados ficam
ligados causalmente. Não há reroute implícito, teletransporte, nem alteração da
carga civil já despachada.

O teste focal estendeu a fixture de interferência campanha–criatura–comércio:
após a criatura fechar a travessia e a coluna registrar `detachment_held`, a
instituição e o titular do QG recebem boletins atualizados; o QG escolhe uma estrada alternativa,
e a mesma coluna prossegue sem usar a travessia fechada. A carga comercial,
que continua na rota contratada original, atrasa e mantém efeito diferente na
subsistência do ramo de passagem aberta. Save/load e auditoria causal do mundo
continuam no fim do mesmo teste. O mesmo curso agora prossegue até uma coluna
rival presente: a instituição nomeia uma pessoa local como comandante, e ela
escolhe postura tática num turno posterior. A regressão também remove, numa
cópia diagnóstica, os boletins próprios do QG e confirma que os relatórios
agrupados da instituição não bastam para oferecer o desvio. A sequência é
causalmente navegável do bloqueio, passando por espera, boletins, reencaminhamento,
provisão e chegada, até o contato e a decisão do comandante.

## Atores políticos, QG e comandante na mesma campanha — 24/09/2026

Uma única fixture agora compõe os atores existentes: a instituição adota a
defesa observada; o titular político autoriza no dia seguinte; o titular do QG
escolhe e paga a mobilização; uma criatura fecha a rota; o QG recebe os boletins
próprios, escolhe reencaminhar a mesma coluna, e o frete civil na rota original
atrasa, alterando subsistência. Depois da chegada, uma coluna rival de fixture
entra em contato; a instituição nomeia uma pessoa local e, em outro dia, ela
escolhe postura tática. A decisão do comandante cita seu contato e nomeação; a
cadeia de eventos conserva o bloqueio como ancestral causal. Choices usam
provider simulado, e rival/comandante presentes são premissas de fixture.

Isso prova a composição sob pressão, com autoria e calendário separados, não
formação natural de guerra, nem a escolha de provider real. O comandante decide
após chegar e entrar em contato; ainda não reavalia a rota durante a marcha ou
responde a uma mudança tática causada pela criatura. A regra limitada de
`hold/press` e sua influência na leitura de força seguem cobertas na vertical
de combate, mas não foram usadas para forçar um resultado nesta fixture.

## Schema 71 — suspensão decidida de vínculo permanente — 24/09/2026

Após receipt atual da própria produção limitada por folha, o empregador pode
escolher entre reduzir o alvo ou suspender o vínculo no próximo ciclo (alvo
zero). A pausa não demite pessoas, muda ocupação, remove o contrato nem paga
salários: apenas não reserva trabalhadores naquele ciclo, deixando-os elegíveis
para outras atividades materiais. O receipt `permanent_employment_paused`
registra a decisão causal, a data e o estado do vínculo. Se houver nova pressão
de folha, opções atuais permitem retomada/revisão; nada ocorre sem nova decisão.
Finanças apresenta o resultado `paused` em português.

O save foi elevado a schema 71; schemas anteriores são rejeitados sem migração
ou sobrescrita, com teste explícito de que save 70 permanece intacto. Uma
fixture contrafactual liberou trabalho e caixa e produziu mais lotes no ciclo
seguinte; não mediu recuperação de renda doméstica, saúde ou população. Um
provider stub selecionou o ID zero pelo menu institucional composto e o owner
registrou a pausa. Passaram 18 testes de emprego e um recorte combinado de 22
testes de emprego, persistência/schema e observatório, além de Ruff,
`git diff --check`, type-check medieval e quatro testes de Finanças. O smoke
natural schema 71 da seed 73 avançou 120 dias sem provider: 3.867 eventos,
76.000 moedas e recursos conservados, save/load/continuação equivalentes até o
dia 121 e auditorias do save/checkpoint `ok=true`, sem causas quebradas, erros
de autoria ou efeitos Story/LLM. Durou 13,02s, salvou 2.232.320 bytes e chegou
a RSS de 153.382.912 bytes. Houve 84 rações faltantes acumuladas, saúde média
952,88 e zero mortes; não foi registrada decisão de staffing. Isso verifica
integridade curta, não a eficácia natural da suspensão, provider real ou
estabilidade longa. A série natural abaixo é evidência de checkout anterior e
não certifica esta regra.

Uma continuação independente do save schema 71 do dia 120 até o dia 480 foi
executada sem provider real (`routine-rules`, zero chamadas externas). O run
terminou com 17.777 eventos; conservação de dinheiro/recursos, save/load e
continuação passaram. A auditoria final retornou `ok=true`, sem causas
quebradas, autoria inválida, origem de decisão sem fonte ou mutação por Story/
interpretação. Durou 86,04s, salvou 5.558.272 bytes e atingiu RSS de
348.762.112 bytes. No dia 480 havia 0 mortes por privação, mas saúde média
877,62, unrest 81,75 e falta mensal 173; o acumulado mensal de falta foi
1.226. Houve 45 pedidos de ajuda, 42 cumprimentos, 37 distribuições de relief,
42 compras de mercado, 37 novos vínculos de emprego e 27 migrações iniciadas.
Não houve decisão de staffing nem construção de oficina. Portanto, é evidência
de integridade e pressão econômica persistente, não de política ótima ou
recuperação natural.

Para medir o efeito material de uma suspensão sem atribuí-la a uma política
natural, fiz uma comparação pareada a partir desse mesmo save do dia 480. No
tratamento, Auren tomou uma decisão auditável para suspender o vínculo
`employment:pop:campomanso:human:farmer` (alvo 219 → 0); no controle, nada mudou.
As duas cópias avançaram 120 dias pelo mesmo engine offline, sem provider e sem
outras decisões injetadas. No dia 600, tratamento vs. controle registrou:
comida total em estoques, cargas e provisões 163.417 vs. 158.917 (+4.500 no
tratamento), cinco eventos a mais de `production_completed`, falta alimentar
agregada 50 vs. 53, saúde média 827,75 vs. 821,38 e unrest médio 112,25 vs.
118,62. População e mortes por privação ficaram iguais (10.930 e zero). É um
sinal causal favorável nesse
estado específico, não prova de escolha espontânea, melhora geral ou efeito
persistente: a comparação foi diagnóstica, executada em memória, sem saves
finais próprios nem auditoria independente dos dois resultados.

O dossiê do dia 120 distingue falta física de alimento não comprado em reports
atuais: por exemplo, Pedra Clara tinha `missing_food=0` após intervenção, mas
1.847 unidades de falta por incapacidade de compra; seu censo reportava 2.118
artesãos e apenas 0 pagos por instalações próprias de Auren. O menu composto
enumerava uma oficina válida para Pedra Clara. A situação dessa affordance
agora mostra requisitos de materiais, saldo em estoque, custo de reposição,
trabalho e salários totais, tesouro próprio e o limite do resultado (abrir
capacidade do site, sem criar linha produtiva/emprego automaticamente). São
projeções do blueprint e estado canônico; o owner continua revalidando tudo. O
recibo de decisão de construção também aponta para os eventos disponíveis de
materiais, saldo, relatório local, acessibilidade alimentar e censo/folha
produtiva usados no contexto; baseline inicial sem receipt continua sendo raiz
de mundo, não um evento inventado. O teste focal comprova essa proveniência e o
contexto, não uma escolha de provider. O smoke está em
`/tmp/cws-schema71-seed73-day480.mws` nesta máquina.

O contrato de provider também ganhou uma verificação de timeout no limite do
simulador: após um ator alcançar o provider e receber `TimeoutError`, o step
inteiro é descartado; snapshot, eventos e RNG publicados ficam idênticos ao
estado anterior. Com orçamento esgotado, `NO_ACTION`, affordance stale/inventada
e resposta com erro já havia cobertura focal. Os seis recortes selecionados
(incluindo o de timeout e contexto de oficina) passaram juntos: 8 testes, Ruff e
`git diff --check`. São providers simulados; não validam latência, qualidade ou
escolha do Codex OAuth/Luna real.

O mesmo save natural do dia 480 contém vínculos cuja última folha falhou por
`unpaid_funds`. Agora, se a falha é do ciclo atual e o saldo ainda não paga nem
um trabalhador, o empregador recebe uma affordance para suspender o vínculo;
reduzir para um alvo positivo não é oferecido enquanto nenhum salário cabe. Ao
recompor as opções sobre esse save com o código atual, apareceram 13 opções de
suspensão, todas sustentadas por recibos `permanent_employment_unpaid` do dia
480, para Liga das Barcas, Ordem da Aurora e Torre do Âmbar. O owner registra
decisão e transição causadas pelo recibo; suspender reduz o compromisso futuro
de folha, mas não gera dinheiro, salário ou emprego alternativo. Não foi feita
decisão dos atores nesse save. Os 19 testes da vertical de emprego passaram,
com Ruff e `git diff --check`; não houve mudança de schema, apenas uso do
contrato/recibo já persistido.

## Série natural de dez anos de checkout anterior — 23/09/2026

As seeds 73, 101 e 137 foram executadas do dia zero ao dia 3.600 no checkout
com o fallback de ajuda e a affordance de workforce corrigidos. Os checkpoints
anuais passaram conservação e auditoria causal independente; os saves finais
passaram também save/load. As três auditorias finais retornaram `ok=true`,
respectivamente com 121.707, 105.622 e 108.090 eventos materiais, sem causa
quebrada, autoria inválida ou mutação por Story/LLM. O log do sexto ano da
seed 137 não registrou seu recibo final de save/load, mas o arquivo foi
auditado, retomado e passou um round-trip independente com continuação
equivalente; os anos 7–10 também passaram essa checagem. Nenhuma série usa
provider real: são smokes offline `routine-rules`.

Isso não demonstra economia saudável. No dia 3.600, as seeds 73/101/137
acumularam 5.297/5.162/5.949 mortes por privação; saúde média 97/118,62/91,12
e falta alimentar 211/86/210. O relief offline escolhe uma cidade por
polity/ciclo, embora o owner transfira rações reais à despensa dos moradores
e deixe deltas navegáveis. Outras cidades podem continuar famintas apesar de
estoque público local e incapacidade de compra das famílias. A adequação
dessa restrição decisória ainda precisa ser avaliada; nenhuma mudança nela
foi feita durante a série. Essa matriz completou o horizonte no checkout em que
foi executada, mas mudanças posteriores de economia e schema reabriram o gate
para o checkout atual. Os gates de provider real, produto e funcionalidades
amplas continuam abertos.

## Ajuda institucional deixa de privilegiar IDs — 22/09/2026

O save natural da seed 73 no dia 2.520 revelou um bloqueio do fallback offline:
Auren e Escarlia, sempre consultadas primeiro por ID, pediram 1–2 rações a
cada mês e ocuparam os dois provedores que admitem um pedido pendente.
Valedouro, apesar de mais de mil rações em falta, não abriu nenhum pedido no
ano 7. O fallback agora ordena instituições e seus assentamentos pela falta
do relatório próprio atual; uma cidade com cadeia aberta não impede a mesma
instituição de considerar outra cidade. Não muda consentimento, quantidades,
frete, owners nem a escolha do provider real.

A regressão falhou antes da correção e o recorte de ajuda/agenda passou
`32 testes` depois. Retomando o save real, Valedouro pediu 1.290 rações para
Portovelho no dia 2.550; Auren aceitou no dia seguinte e despachou no outro.
As 1.290 rações chegaram fisicamente até o dia 2.568. No dia 2.580,
Portovelho distribuiu 1.321 rações do estoque e ficou com falta residual de
20; Valedouro pediu então 992 rações para Salgueiro. Ambos os saves de 30 dias
passaram conservação, equivalência save/load e auditoria causal independente.
Esta é evidência de uma cadeia offline corrigida, não de equilíbrio econômico
global ou decisão por provider real. Como os sete anos anteriores foram
simulados antes da correção, esse save é diagnóstico; o gate de três seeds por
dez anos precisa recomeçar do dia zero com o checkout corrigido.

## Smoke natural longo: seed 73 até sete anos — 22/09/2026

A seed 73 foi retomada por checkpoints anuais até o dia 2.520 (sete anos), sem
provider real e sem recomeçar do dia zero. O save final tem 133.690 eventos;
conservação de comida, dinheiro e recursos, equivalência save/load e auditoria
causal standalone passaram. A auditoria encontrou 107.304 eventos materiais,
nenhuma causa quebrada, autoria inválida ou mutação originada em Story/LLM.
Isso não fecha o gate planejado de três seeds por dez anos.

O resultado econômico merece investigação antes de seguir: 4.222 mortes por
privação acumuladas e falta alimentar de 2.244 no dia 2.520. Ainda existem
110.539 unidades de comida em estoques do mundo, concentradas longe dos
assentamentos famintos. Valedouro tinha só 24 moedas; seu menu canônico
oferecia compras pequenas, pedidos de troca/ajuda, abastecimento e relief
local. A evidência aponta para distribuição, poder de compra e escolhas de
política como hipóteses, não para perda oculta de comida nem para uma correção
automática. A trajetória foi medida em `routine-rules`, portanto não demonstra
comportamento de provider real.

## Observação pós-relief e validação de commitment — C130 — 21/09/2026

Uma distribuição material de alimento agora recompõe somente os relatórios
locais que já existiam no assentamento atingido. A nova observação aponta para
o receipt de `relief_distributed`; não publica boletim novo nem revela a
situação a uma instituição remota. Assim um pedido institucional posterior no
mesmo ciclo vê a falta residual canônica, e não a leitura anterior ao ato de
ajuda.

Durante a regressão, a validação de relações também passou a reconstruir o
índice factual no seu limite de integridade. O índice global otimizado continua
válido para o ledger append-only normal, mas não pode mascarar adulteração de
um evento intermediário quando `RelationsState.validate` verifica a
proveniência de um compromisso. A suite combinada de relief, ajuda institucional
e engine passou em `36 testes` (`12,65s`). Isso cobre a cadeia curta e a
rejeição de provenance adulterada; não substitui os smokes longos de economia.

## Fallback de relief passa a ser decisão auditável — C127 — 21/09/2026

O modo offline/teste agora possui uma política de ajuda alimentar declarada:
cada polity pode selecionar no máximo uma affordance local de distribuição já enumerada
quando o shortfall observado for coletivo (`>= 20`). A prioridade é urgência,
entrega direta em empate, cobertura e ordem estável. O fallback registra uma
`DECISION` com `ACTOR_DECISION`; Economy recompõe a opção e ainda
revalida estoque, autoridade e quantidade antes da mutação. Transferência roteada
permanece uma opção concorrente exclusiva do provider, pois depende de rota e
fiscalidade atuais no despacho. Com provider
habilitado esse caminho não roda: o ator continua vendo todas as opções
concorrentes e pode escolher qualquer uma ou não agir.

O recorte de relief e engine passou em `20 testes` (`8,93s`), seguido de
`compileall` e `git diff --check`. Isso torna o mundo offline menos inerte sem
introduzir repasse automático, mas não prova resiliência anual nem substitui uma
política escolhida por IA real. MetaGame/Laya registrou C127 e a correção C129
em `shadow/observe`.

O smoke natural de `120` dias também foi reexecutado com esse caminho e salvou
`3.334` eventos; a auditoria retornou `ok=true`, sem causas quebradas, decisão
sem fonte, autoria divergente, Story material ou interpretação LLM material.
O artefato temporário foi removido após a auditoria por causa do espaço livre
limitado. A tentativa inicial de incluir transferência roteada no fallback foi
retirada: ela exige uma oferta de rota/fiscal ainda atual no despacho e, portanto,
permanece corretamente no menu que o provider pode escolher/revalidar.
Durante essa verificação, a enumeração de transferências internas foi corrigida
para excluir estoques de destino pertencentes a outra polity: conhecer pressão
estrangeira não é autoridade para abrir freight para ela. Antes, o executor já
rejeitava esse caso; agora a opção inválida nem chega ao ator.

## Diagnóstico da resiliência: decisão e fluxo são distintos — C126 — 21/09/2026

Uma execução natural de oito meses na seed `73` mostrou que os três
assentamentos inicialmente pressionados acumulam déficit enquanto suas
granarias públicas ainda conservam alimento. Isso não é criação/perda oculta:
sem provider, `relief` não possui fallback automático, logo a administração
não pode transformar estoque em distribuição sem uma decisão discricionária.
Com o perfil de decisão de recuperação, as distribuições acontecem e a
escassez inicial cai; porém a política de fixture seleciona apenas uma ação
por instituição/boundary e não é evidência de uma estratégia geral nem de
resiliência anual.

O checkpoint também expôs um limite operacional: o save SQLite de doze meses
com cerca de `10.369` eventos não foi gravado neste ambiente porque restavam
apenas alguns megabytes no filesystem. Os artefatos temporários criados para a
medição foram removidos; nenhum dado do projeto ou save do usuário foi tocado.
Antes de executar gates longos, é necessário disponibilizar espaço persistente
suficiente para os artefatos. A próxima correção de produto deve separar com
cuidado política de fallback de decisão por provider, sem converter a ajuda em
um repasse automático roteirizado.

## Auditoria do artefato de save separada do harness — C125 — 21/09/2026

O smoke de recuperação de `120` dias foi reexecutado com `save_load_equivalent`,
conservação de dinheiro/recursos e auditoria causal sem causas quebradas,
decisões sem fonte, autoria divergente ou materialidade de interpretação. Uma
reprodução de `30` dias confirmou que o arquivo `.mws` é criado e pode ser lido
pela auditoria. A tentativa anterior de auditar um caminho em `/dev/shm` numa
invocação posterior falhou porque esse diretório é efêmero entre invocações do
harness; não foi uma falha do contrato de persistência. Nenhuma alteração de
código foi necessária neste checkpoint. MetaGame/Laya registrou C125 em
`shadow/observe`.

## Receipts de produção explicam o limite engine-owned — C124 — 21/09/2026

Eventos `production_completed` e `production_limited` agora carregam um
`causal_payload.production` estruturado com instalação, assentamento, receita,
lotes, limites calculados, fatores limitantes, shortfall de mão de obra e dia
observado. O payload é somente evidência: não é instrução, não altera o owner
de Economy e não substitui os deltas canônicos.

A regressão de produção/indústria/workforce passou em `29 testes`; a cadeia de
rota e persistência passou em `11 testes`, com `compileall` e `git diff --check`
verdes. Isso melhora `Why` e diagnóstico sem usar prosa como causa. A Onda 1,
as campanhas amplas e os gates longos continuam abertos. MetaGame/Laya registrou
C124 em `shadow/observe`.

## Cadeia de pressão produtiva tem aceite material — C123 — 21/09/2026

Foi adicionada uma fixture de aceite de `150` dias para a cadeia econômica:
linhas limitadas por mão de obra publicam o shortfall, grupos recebem ofertas
engine-owned, decisões de workforce/emprego são executadas pelos owners e os
receipts posteriores de produção reduzem a falta alimentar. A cadeia não cria
comida, trabalhadores ou dinheiro e ainda exige que a pressão residual possa
permanecer.

O teste passou isoladamente em `15,57s`; a regressão combinada de workforce,
emprego e economia passou em `68 testes` (`32,34s`), com `compileall` e
`git diff --check` verdes. Isso prova uma fixture multietapas, não resiliência
natural universal nem o gate de dez anos. MetaGame/Laya registrou C123 em
`shadow/observe`.

## Evidência produtiva chega à diplomacia — C122 — 21/09/2026

O fragmento customizado da consulta diplomática agora inclui
`own_production_readings`, mantendo a mesma fronteira do dossier: somente
instalações do ator, último receipt de produção, limitações e falta de mão de
obra. Saldos, contas, estoques privados e produção estrangeira continuam fora
do contexto. Nenhuma proposta ou obrigação é executada por essa leitura.

A regressão de diplomacia, decisão civil e dossier passou em `68 testes`, com
`compileall` e `git diff --check` verdes. Isso melhora negociações baseadas em
escassez material, mas não é ainda a implementação de barganha/estratégia
ampla nem fecha a Onda 1 econômica. MetaGame/Laya registrou C122 em
`shadow/observe`.

## Gargalo produtivo chega às consultas institucionais — C121 — 21/09/2026

As situações customizadas de abastecimento, relief e emprego permanente agora
incluem a mesma leitura `own_production_readings` do dossier. Assim, uma
consulta que usa um fragmento específico não perde a evidência das próprias
linhas produtivas: o ator pode comparar escassez, produção limitada, mão de
obra e alternativas enumeradas. A projeção continua somente leitura, limitada
ao estoque do próprio ator e derivada do receipt mais recente; nenhum contexto
expõe saldo, conta, estoque privado estrangeiro ou efeito futuro.

A regressão de dossier, decisão civil, relief e emprego passou em `56 testes`,
com uma verificação adicional de consulta em `24 testes`; `compileall` e
`git diff --check` também passaram. Isso fecha a passagem da evidência para as
consultas, mas ainda não fecha a resiliência econômica nem qualquer onda ampla
do roadmap. MetaGame/Laya permaneceu em `shadow/observe`.

## Dossier expõe gargalo produtivo do próprio ator — C120 — 21/09/2026

O dossier institucional agora projeta `own_production_readings` somente para
instalações cujo estoque pertence ao ator. Cada leitura vem do último receipt
canônico de produção e informa assentamento, ocupação, lotes/capacidade,
limitações, eventual `labor_shortfall`, dia observado e `event_id`; não estima
produção futura, não expõe saldos estrangeiros e não cria trabalhadores ou
comida. Isso dá ao ator evidência para escolher workforce, mercado ou expansão
sem transformar a leitura em planner ou mutação.

A regressão focal de dossier/turno institucional/decisão passou em `32 testes`,
e a regressão econômica de produção/renda/mercado/workforce/expansão passou em
`100 testes`, com `compileall` e `git diff --check` verdes. O recorte melhora a agência
informada da Onda 1, mas não resolve a resiliência econômica nem o gate natural
de dez anos. MetaGame/Laya registrou C120 em `shadow/observe`; nenhum agente
externo foi executado.

## Gate natural longo evidencia a lacuna econômica — C119 — 21/09/2026

O gate natural da seed `73` foi iniciado para `3.600` dias em `/dev/shm`, mas
foi interrompido no dia `570` depois de tornar a limitação econômica observável
sem esperar dezenas de minutos por um resultado já conhecido. Até esse ponto a
simulação preservou a cadeia factual e continuou produzindo pedidos de ajuda,
entregas, compras, migrações e transições de workforce; não houve provider real
nem mutação narrativa.

O mundo, porém, não é resiliente no modo natural: no mês 19 havia população
`10.758`, `161` mortes por privação, saúde média `494`, unrest médio `277,88` e
déficit alimentar agregado `4.704`. Isso não é falha de causalidade nem aceita
o gate de dez anos; é evidência direta de que produção, mobilidade, mercado e
decisões sem um perfil de governo ainda não fecham a resiliência econômica.
O arquivo de saída foi temporário e não é um artefato de release. MetaGame/Laya
registrou C119 em `shadow/observe` e recomendou continuar.

## Checkpoint de verificação de infraestrutura e campanha — C118 — 21/09/2026

O recorte foi verificado em `/dev/shm`, sem alterar o código neste checkpoint.
Infraestrutura, desgaste, reativação, manutenção e overflow regional passaram
em `40 passed`; força, guarnição, abastecimento e cerco passaram em `31 passed`.
Os testes confirmam que dano, reparo, controle e retirada continuam separados:
decisões apenas selecionam affordances, enquanto Map/Society/Economy executam
os deltas materiais com causas navegáveis.

Isso não fecha a etapa de campanhas: ainda faltam manutenção militar ampla,
controle territorial duradouro fora da fixture estreita e solução política geral.
Também não fecha a etapa econômica nem o smoke natural de 3.600 dias. O
MetaGame/Laya registrou C118 em `shadow/observe`; a primeira emissão inválida
usou tipos de evento inexistentes, foi classificada como falha de protocolo sem
efeito no repositório e corrigida usando somente os tipos suportados.

## Relief, workforce e histórico cívico preservam a cadeia material — 21/09/2026

Uma distribuição de relief agora reduz `missing_food` e recupera `health`/
`unrest` apenas em proporção à comida realmente entregue, limitada a 20 por
ciclo; não há subsídio nem cura narrativa. A demanda de workforce preserva os
termos do receipt enquanto o mesmo evento de produção mantém o
`labor_shortfall`, mesmo se outro owner alterar a subsistência no mesmo dia.
Protestos abertos exigem uma coorte completamente disponível; protestos
fechados mantêm sua participação como história e não invalidam quando a
coorte depois encolhe.

A regressão composta passou em 81 testes. O smoke pressionado de 360 dias da
seed 73 terminou com 10.247 eventos, déficit alimentar agregado 3.249, saúde
média 633,38, unrest médio 366,62, 74 transições de workforce, zero mortes por
privação e auditoria causal limpa (`broken_cause_ids=[]`, zero decisões sem
autoria e zero material Story/LLM). A Onda 1 continua aberta: renda,
produção, rotas e o gate de dez anos ainda não estão resolvidos.

## Contratos não agravam falta de mão de obra alimentar — 21/09/2026

O owner de emprego permanente agora lê o receipt tipado da produção atual. Se
uma linha de comida está limitada por `labor_shortfall`, ele não enumera um
contrato que reserve agricultores antes da produção. Isso evita transformar a
própria política de emprego em causa da escassez; recomposição continua
dependendo de uma decisão de workforce e da execução do owner. A regressão
focada passou em 61 testes. Na fixture `seed=73`, 180 dias reduziram a falta
alimentar agregada de 1.195 para 325, mantendo conservação, save/load e
auditoria causal (`broken_cause_ids=[]`). O horizonte ainda não prova
resiliência de dez anos.

## Affordability reading chega ao dossier sem vazar contas — 21/09/2026

O receipt engine-owned de `subsistence_resolved` já calculava
`unaffordable_by_group`, mas o contexto institucional mostrava apenas a falta
agregada. O dossier e o menu de relief agora projetam somente
`unaffordable_food`, `unaffordable_group_count` e o `affordability_event_id`.
Isso permite distinguir estoque público de renda doméstica sem expor saldos,
IDs de famílias ou inventários, e sem transformar leitura em subsídio ou
planner. A regressão focada passou em 36 testes; a resiliência econômica segue
pendente.

## Revisões individuais também respeitam fail-closed — 21/09/2026

Viagem de personagem, oferta/patrocínio de rito restaurador e consequência
privada após uma vitória de campo agora atravessam `select_option` quando uma
affordance material já foi agendada. Se o mundo está em modo IA e o provider
desaparece, falta orçamento ou a consulta falha, `ProviderDecisionRequired`
descarta a transação; nenhum movimento, oferta, ocupação ou delta é aplicado.
Em modo offline essas revisões continuam explicitamente inativas. A regressão
focada composta passou em 28 testes, e o smoke/auditoria de 30 dias manteve
`broken_cause_ids=[]`, zero decisões sem autoria e zero material Story/LLM.
Isso fecha mais uma fronteira de provider, mas não conclui a resiliência
econômica, as campanhas persistentes ou os gates longos.

## Abastecimento de campanha respeita fail-closed do provider — 21/09/2026

O review datado de abastecimento de uma coluna não retorna mais silenciosamente
quando o mundo está em modo IA sem provider, sem orçamento ou com consulta
indisponível. Havendo opções materiais, a decisão chega ao mesmo
`ProviderDecisionRequired` do turno institucional e a transação é descartada;
nenhuma carga é aberta. Em modo offline essa vertical opcional permanece
explicitamente inativa. A regressão focada de campanha passou em 4 testes,
incluindo seleção, `NO_ACTION`, chegada/save-load e a pausa fail-closed. Isso
fecha uma fronteira de provider, mas não a campanha persistente geral nem o
gate de provider real.

## Matriz natural de três seeds — 19/09/2026

O gate natural de 360 dias foi executado para as seeds `73`, `101` e `137` com
o harness corrigido. Os três saves conservaram dinheiro e recursos, passaram a
continuação por save/load e a auditoria causal (`ok=true`,
`broken_cause_ids=[]`, `story_material_events=[]`). O custo cresceu até cerca
de 235 segundos por seed; os mundos permaneceram materialmente pressionados,
com falta alimentar, queda de saúde e aumento de unrest em alguns
assentamentos. Isso é evidência de causalidade e da lacuna econômica, não
aceite de resiliência nem do gate natural de dez anos.

A comparação econômica de quatro perfis foi interrompida após iniciar a
fixture `socorro/73`, para não transformar a verificação em uma suíte longa;
os artefatos naturais estão em `/tmp/cws-release-gate-360-current`.

## Harness de smoke e regressão fiscal — 19/09/2026

`tools/medieval_autonomy_smoke.run` agora normaliza o artefato de saída para
`Path` na fronteira pública. Sondagens e notebooks podem passar `str` ou
`Path`, e o save/load continua usando o mesmo caminho canônico. A regressão
`tests/test_medieval_autonomy_smoke.py` cobre o caminho com `str`.

O teste fiscal mensal deixou de comparar o saldo final, depois de todas as
operações do boundary, diretamente com o bruto da folha. Ele agora verifica o
recibo `wages_paid`, o delta exato do tesouro e que a cotação publicada reflete
a política fiscal que efetivamente sobreviveu ao boundary. A regressão focada
de tarifas, smoke, ajuda, concessão administrativa e cerco passou em 52 testes.

Isso melhora a prova do harness e remove uma expectativa histórica incorreta;
não fecha a resiliência econômica nem o gate natural de dez anos.

Uma regressão material ampliada cobrindo produção/pesquisa, apprenticeship por
migração, venda/roubo de tecnologia, cerco, força/guarnição, cessar-fogo,
escassez de rota, recuperação de frete e alfândega passou em 93 testes em
35,77s. O probe do provider real continua falhando explicitamente antes da
decisão porque não há provider configurado; fallback offline/stub não é prova
de autonomia real.

O probe ganhou duas regressões: provider ausente falha antes de criar o mundo e
orçamento não positivo é rejeitado antes de qualquer consulta. O recorte de
provider/turno institucional passou em 31 testes; `compileall` e
`git diff --check` também passaram.

Transferências alimentares interurbanas agora oferecem cobertura integral ou
metade do shortfall observado, mantendo a escolha em affordances opacas e a
revalidação de rota/estoque pelo owner. A regressão de relief, turno e provider
passou em 30 testes; não há distribuição automática nem resolução gratuita da
escassez.

## Fallbacks mensais respeitam o turno composto — 19/09/2026

Tarifas, manutenção, abastecimento, provisão domiciliar, migração e serviço de
instalação agora recebem `excluded_actors` e só executam a política
determinística para atores que não tiveram consulta concluída. No modo com IA,
esses fallbacks foram movidos para depois do turno mensal composto; assim um
`NO_ACTION` real não é sobrescrito por política automática e um ator que perdeu
o slot de orçamento ainda pode agir por uma affordance já enumerada.

Transferências de ajuda também passaram a usar IDs opacos no contexto do
provider: estoques e rotas continuam nos termos privados recomputados pelo
owner, enquanto o ator vê apenas destino, quantidade e número de rotas.

As regressões de agenda, decisão composta, relief, provisão, migração, serviço,
tarifa e workforce passaram em 50 testes; `compileall` e `git diff --check`
passaram. Uma expectativa histórica isolada de tarifa ainda falha porque o
fixture de emprego permanente termina com saldo `283` e folha `120`; isso é
registrado como pendência do WIP, não mascarado.

## Fallback para atores sem consulta por orçamento — 19/09/2026

O fallback de workforce e emprego permanente não é mais desativado apenas
porque o provider está configurado. A consulta mensal marca em `excluded_actors`
somente quem realmente recebeu uma decisão; atores que ficaram sem slot por
limite de orçamento continuam podendo escolher, de forma conservadora, uma
affordance já enumerada. Isso preserva o limite de IA sem transformar falha de
orçamento em ausência silenciosa de agência.

A regressão conjunta passou em 50 testes. No smoke `seed=73`, 120 dias com o
perfil `mobilidade` passou de 6.273 para 4.276 unidades de falta alimentar,
com 20 transições e 21 vínculos de emprego, conservação de recursos/dinheiro e
save/load equivalente. A economia ainda não está resiliente; a melhoria apenas
fecha o caminho de fallback para atores não consultados.

## Fallback de mobilidade respeita a pressão alimentar local — 19/09/2026

Quando uma coorte recebe várias ofertas `farmer` válidas para instalações do
mesmo patrocinador, a política offline agora prefere primeiro a affordance cuja
instalação fica no assentamento que reportou a falta. A quantidade publicada e
os termos continuam vindo dos receipts engine-owned; a mudança apenas evita
que uma escolha de maior volume desloque trabalhadores para longe da própria
crise. Se não houver oferta local, a maior oferta válida continua sendo o
desempate estável.

A regressão de workforce e do smoke passou em 37 testes. O smoke de 120 dias
continua pressionado, então isto é correção de priorização causal, não prova de
resiliência econômica completa.

## Fallback de mobilidade prioriza a maior necessidade material — 19/09/2026

Quando uma coorte recebe várias ofertas engine-owned para a mesma pressão
alimentar, o fallback offline agora prefere a maior quantidade já publicada
para a ocupação prioritária, mantendo a ordenação estável como desempate. Isso
evita gastar a única transição ativa da coorte em uma demanda pequena enquanto
uma instalação agrícola com shortfall maior aguarda. A quantidade continua
sendo a do notice canônico; não há criação de trabalhadores ou comida.

A regressão de workforce e harness passou em 36 testes. O smoke de 120 dias
continua materialmente pressionado, portanto a mudança melhora a escolha local
sem ser declarada como solução da resiliência econômica.

## Descoberta de guarnições de organizações — 19/09/2026

O boundary de gestão de guarnições não restringe mais a descoberta ao conjunto
de polities. Organizações que possuem um `AuthorityOffice` militar agora entram
quando o próprio owner publica uma affordance canônica de estabelecimento,
retirada ou rotação; a execução continua no owner de `Society/force`, com as
mesmas revalidações de coluna, provisões e autoridade. Nenhum novo planner ou
estado de campanha foi criado.

A regressão focada de garrison policy e agenda passou em 7 testes. A guerra
prolongada e a solução política ampla continuam pendentes.

## Cerco com pressão material de provisões — 19/09/2026

O progresso diário de uma `SiegeCampaign` agora aplica, além do consumo normal
da coluna pelo owner de força, uma pressão de bloqueio limitada de uma ração
por soldado sobre as provisões da guarnição defensora. O owner do cerco não
cria comida nem decide baixas: ele revalida a guarnição e registra o delta de
provisões no mesmo fato de progresso; a endurance continua sendo uma leitura
separada e a brecha ainda exige a decisão/execução já existentes. Quando o
cerco termina por brecha, a última pressão de provisões também fica no receipt
da brecha e pode ser navegada pelo `Why`.

A regressão focada de cerco, suprimento e força passou em 23 testes. Isso fecha
uma ligação material da campanha, mas não a guerra prolongada, a solução
política ampla ou o gate natural de longa duração.

## Smoke de escassez e política de socorro — 19/09/2026

O smoke natural `seed=73` mostrou que `desatento` pode levar uma economia sem
intervenção a falta de comida no mês 2 e mortes por privação a partir do mês
11; isso é evidência de pressão material, não uma causa narrativa nem uma
falha do owner. O perfil `socorro` continua escolhendo pedidos/aceites
enumerados, e agora também pode escolher `relief-transfer` quando uma rota de
excedente próprio aparece. O helper do smoke não inventa IDs.

A regressão do helper de smoke, relief e agenda passou em 17 testes. Uma
execução provider-free de 120 dias com `socorro` completou com população,
recursos e dinheiro conservados, zero mortes, save/load equivalente e
`real_ai_calls=0`; isso é um smoke curto, não o gate de 120 meses. O smoke de
120 meses não foi declarado verde: a execução foi interrompida após revelar a
falha de resiliência, que permanece pendente para a próxima onda.

O perfil `mobilidade`, que escolhe empregos e transições canônicos, também
completou 120 dias sem mortes e abriu vínculos de emprego/transições materiais;
mesmo assim acumulou falta alimentar. Emprego isolado não é tratado como
solução completa.

## Transferência de excedente alimentar por decisão — 19/09/2026

A administração agora pode escolher uma affordance de transferência entre dois
assentamentos próprios quando possui excedente físico acima da reserva
engine-owned, relatório atual de falta no destino e rota fiscal observada. A
execução abre frete real pelo owner de logística, debita o estoque de origem e
aguarda a entrega física; não reduz o déficit nem cria comida no momento da
decisão. A rota, inventário e relatório são revalidados pelo executor e a
opção entra no boundary mensal de relief.

A transferência também foi adicionada ao catálogo civil determinístico, sem
criar um caminho executor diferente do adapter mensal. A regressão focada de
relief, logística, ajuda institucional, catálogo e agenda passou em 30 testes;
`compileall` e `git diff --check` também passaram. Isso melhora a
resiliência material, mas não fecha distribuição geral, alternativas de
abastecimento ou o smoke longo.

## Ciclo de vida dos próprios planos no dossier — 19/09/2026

O contexto privado do ator agora inclui `own_plans`, derivado dos objetivos e
planos persistidos que pertencem à instituição. Ele informa assentamento,
recurso, tipo, estágio, bloqueador e data da última revisão, mas não expõe IDs
de estoque, ordens de frete ou planos estrangeiros. Isso permite que a consulta
considere um plano próprio bloqueado/concluído sem transformar `StrategicCapacity`
em planner ou criar estado paralelo.

A regressão focada de dossier, capacidade estratégica, turno institucional e
projeção passou em 26 testes; `compileall` e `git diff --check` também passaram.

## Resposta independente a acusação — 19/09/2026

Uma acusação baseada em finding agora gera duas affordances canônicas para o
sujeito notificado: negar ou pedir revisão. A resposta é deliberada, limitada
ao aviso recebido e registrada como ocorrência com `causal_origin` de decisão
do ator, apontando para a acusação e para a decisão correspondente. Ela não
cria culpa, absolvição, retaliação nem delta material; também não pode ser
repetida para a mesma resposta/aviso. O adapter entra no mesmo boundary mensal
e organizações também são incluídas quando possuem essa opção.

A resposta também aparece no contexto estratégico apenas para o autor e para o
acusador, sem criar uma segunda registry de conhecimento. A regressão focada de
sabotagem, investigação, acusação, agenda institucional, suborno e dossier
passou em 21 testes; `compileall` e `git diff --check` também passaram.
Isso fecha apenas o primeiro passo de reação bilateral da intriga, não uma
perseguição ou cadeia de sanção automática.

## Conflito institucional no boundary mensal — 19/09/2026

As affordances existentes de sabotagem, investigação paga e acusação baseada
em finding já estavam registradas no `sabotage_adapters`; o gap era de
descoberta: organizações fora do conjunto base de polities podiam possuir uma
dessas opções e nunca receber consulta no turno mensal. `monthly_actors` agora
inclui somente organizações com uma affordance de conflito corrente, sem criar
planner ou executor paralelo. O owner continua revalidando autoridade, finding,
causas e estado material antes de executar.

A regressão focada de sabotagem, agenda institucional e suborno passou em 16
testes. Isso fecha a entrega do actor boundary para essa família, mas não a
intriga ampla, espionagem ofensiva ou consequências automáticas de acusações.

## Findings estratégicos no dossier privado — 19/09/2026

O dossier genérico usado pelo turno institucional agora inclui
`known_strategic_evidence`: findings de espionagem, investigação, roubo
tecnológico e acusações filtrados pelo destinatário canônico. A projeção não
adiciona conhecimento, não segue causas desconhecidas e não expõe inventário,
planos ou evidência privada de outra instituição; é a mesma leitura já usada
no contexto diplomático, compartilhada com as demais famílias.

A regressão de dossier/API/diplomacia passou em 24 testes. Isso melhora a
decisão baseada em evidência conhecida, mas não transforma findings em culpa,
retaliação ou mutação automática.

## Persuasão bilateral de propostas abertas — 19/09/2026

A affordance `persuade_proposal` agora pode ser escolhida por qualquer lado
que tenha sido notificado de uma proposta ainda aberta, não apenas pelo
proponente. O owner registra uma tentativa factual sem deltas e reemite a
notificação da mesma proposta; status, cláusulas e obrigações continuam
inalterados até uma resposta independente da contraparte. A opção continua
datada, limitada a uma tentativa por ator/proposta/dia e revalidada pelo ID
transitório.

A regressão focada de diplomacia, negociação, persistência e turno institucional
passou em 45 testes. Isso amplia a agência bilateral da persuasão sem declarar
concluídas intriga ou campanhas políticas gerais.

## Cache da geometria authored de regiões — 19/09/2026

`SettlementRegion.center_loc` agora usa `cached_property`. A geometria `cors`
é authored e não muda durante um step medieval; somente rotas, instalações e
outros campos de runtime são copiados/mutados. O cache remove recomputação do
centróide durante buscas de rota e viagem sem criar estado canônico novo.

A regressão focada de rotas, viagem, engine e suprimento passou em 31 testes.
O smoke mantém as mesmas métricas e a mesma conservação; o gate de dez anos
continua pendente.

## Validação de conhecimento no commit único — 19/09/2026

O início de cada step deixou de repetir a caminhada completa de proveniência
de `KnowledgeState`. O mundo publicado já entra validado pelo commit anterior,
nenhuma operação pré-step altera os registries de conhecimento, e o candidato
continua sendo validado integralmente antes de qualquer save/publicação. Assim,
a fronteira de segurança causal permanece no finalizador, sem aceitar um
candidato inválido.

Os testes de engine, persistência e histórico passaram em 37 casos. No gate
curto natural de 120 dias, o tempo caiu de aproximadamente 14 s para 12 s,
com os mesmos eventos, métricas, conservação e save/load; o gate de dez anos
continua operacionalmente aberto.

## Gate natural prolongado revalidado — 19/09/2026

Uma nova execução natural da seed `73` com horizonte de `3600` dias chegou ao
dia `420` sem crash, erro de conservação observado ou falha de causalidade no
trecho produzido. O custo acumulado foi de aproximadamente cinco minutos por
ano simulado e cresceu com os eventos; a execução foi interrompida antes do
horizonte por custo operacional. Isso confirma a limitação de performance, não
é aceite do gate de dez anos nem substitui as outras seeds.

## Cessar-fogo de campanha no turno institucional — 19/09/2026

As affordances já existentes de oferta, resposta e cumprimento de cessar-fogo
de cerco agora estão registradas no menu institucional mensal. A composição
apenas une os três owners atuais: a proposta continua pertencendo a Relations,
as decisões são independentes e cada retirada passa pelo owner de Society/Force
com revalidação de campanha, coluna e rota. Nenhuma retirada é automática por
estar no menu.

A regressão focada de cerco, cessar-fogo e turno institucional passou em 30
testes. Isso fecha a entrada da solução de cessar-fogo no ciclo de agência;
manutenção ampla e solução política posterior continuam pendentes.

## Revalidação da rota fiscal escolhida pelo abastecimento — 19/09/2026

O fallback de procurement agora preserva a rota fiscal que tornou a oferta
conhecida e ranqueada. Durante a revalidação, ele procura essa mesma sequência
entre as opções atuais; se ela deixou de ser válida, registra o bloqueio em vez
de substituí-la silenciosamente pela primeira rota disponível. Isso mantém o
resultado material alinhado à evidência datada e às affordances enumeradas,
sem transformar o fallback em planner novo.

A regressão focada de rotas, procurement, ajuda e decisão civil passou em 49
testes. A resiliência econômica de longo prazo ainda não está provada.

## Inclusão de organizações com affordances de suborno — 19/09/2026

O turno institucional mensal agora inclui organizações que possuem uma oferta,
resposta ou pagamento de suborno material atualmente enumerado. Antes, uma
organização só entrava no conjunto de atores se outra família tivesse publicado
uma opção para ela, deixando essa vertical válida fora da consulta composta.
O menu e os owners não mudaram: a correção apenas torna o ator elegível para a
consulta única quando a affordance já existe.

A regressão focada de suborno e agenda passou em 21 testes. Isso fecha uma
lacuna de integração do conflito econômico; persuasão e campanhas políticas
mais amplas continuam pendentes.

## Remediação de ensino após breach — 19/09/2026

Quando um compromisso de ensino já pago vence sem que a técnica seja ensinada,
o professor passa a receber uma affordance de renegociação de ensino, desde
que ainda detenha a técnica, autoridade de pesquisa e a contraparte tenha
capacidade authored para recebê-la. A nova proposta é independente: a
contraparte aceita ou recusa, o professor consente e o aprendiz aceita; somente
então Knowledge registra a técnica. O pagamento original não é repetido e o
breach histórico continua preservado.

A regressão de diplomacia/renegociação passou em 23 testes, incluindo
save/load. Isso fecha a remediação de ensino desta vertical; tratados sociais
mais amplos e negociações multi-termo continuam pendentes.

## Remediação de cessão administrativa após breach — 19/09/2026

Uma cessão administrativa pós-ocupação que vence sem cumprimento agora deixa
uma affordance posterior de remediação, desde que o ocupante ainda tenha
controle territorial, guarnição abastecida e relatório atual do assentamento.
Essa remediação cria uma nova proposta e uma nova decisão da contraparte; ela
não reabre nem apaga a obrigação anterior, e a administração só muda após o
cumprimento material da nova obrigação. A causa do novo compromisso inclui o
evento canônico do breach, mantendo a cadeia navegável.

A regressão de administração/observatório passou em 17 testes. Isso fecha a
remediação dessa vertical específica; renegociação social ampla e campanhas
persistentes continuam pendentes.

## Oferta de retorno agrícola escalada por escassez — 19/09/2026

Quando o owner de Economy registra `missing_food` no assentamento da demanda,
as ofertas de transição para `farmer` podem abranger até metade da coorte de
origem; demandas sem escassez e ocupações não agrícolas continuam limitadas a
um quinto. A fração é calculada pela engine, permanece apenas na affordance
transitória e não reserva pessoas: a coorte ainda precisa aceitar, pagar e
concluir a transição física em 30 dias.

A regressão de workforce e emprego passou em 41 testes. O gate natural de 120
dias manteve conservação, save/load e auditoria causal, mas terminou com
`missing_food=4.221`; portanto a mudança amplia a capacidade de reação, sem
provar resiliência econômica de longo prazo.

## Alvo canônico das soluções políticas no atlas — 19/09/2026

O `CampaignView` agora deriva `settlement_id` para cada proposta política
ativa: diretamente do termo administrativo ou, no caso de desescalada armada,
do `standoff` canônico. O atlas mostra esse assentamento junto dos atores e do
estado da proposta, mantendo a fonte navegável. Nenhum alvo é persistido no
read model; ele é recomposto dos termos e registros de Society.

## Solução política pós-ocupação — 19/09/2026

Quando um ocupante sustenta controle territorial ativo, uma guarnição válida e
relatórios recentes do assentamento, o owner passa a expor uma affordance de
cessão administrativa pós-guerra. O ocupante pode propor a transferência da
administração à instituição que ainda administra a cidade; essa contraparte
aceita ou recusa por decisão própria. A aceitação cria somente a obrigação de
transferência, e a administração muda apenas quando o administrador atual
cumpre essa obrigação materialmente. O fluxo não cria retirada automática,
controle territorial, recursos ou paz narrativa; o caminho antigo de contato
armado continua exigindo cessão e retirada como termos separados.

A regressão de cessão administrativa passou em 5 testes. Isto fecha uma fatia
causal da solução política pós-guerra, mas persuasão, campanhas persistentes e
a composição política geral continuam pendentes; espionagem, suborno e
sabotagem já possuem owners próprios, embora ainda não constituam a solução
política completa.

## Folha de emprego escalada por pressão — 19/09/2026

Uma oferta de emprego permanente agora continua limitada a um quinto da
coorte em assentamentos estáveis, mas pode chegar à metade quando o owner
observa `missing_food`, saúde baixa ou descontentamento material no assentamento.
Esse aumento é calculado pela Economy a partir de `SettlementNeeds`; a decisão
continua selecionando somente a affordance e o owner ainda recompõe site,
coorte, autoridade, saldo e payroll antes de criar o contrato. Não há criação
de população, dinheiro ou comida.

A regressão de emprego e workforce passou em 41 testes. No smoke natural de
120 dias com `seed=73`, a falta de comida final caiu de 4.224 para 4.020 e a
saúde média subiu de 899,38 para 903,00, mantendo conservação, save/load e
auditoria causal. Isso é recuperação parcial; resiliência econômica de longo
prazo continua pendente.

## Folha material de guarnição — 19/09/2026

A manutenção diária de uma guarnição agora transfere o salário engine-owned
também para a conta da coorte de soldados que originou o destacamento. O owner
continua debitando o tesouro do proprietário, consumindo rações antes da
manutenção e encerrando a guarnição quando autoridade, presença, coorte ou
saldo deixam de ser válidos. Nenhuma população ou dinheiro é criado: o evento
`garrison_maintained` registra os dois deltas de contas e mantém a cadeia causal
ligada à coorte, ao destacamento e à decisão de estabelecer a guarnição.

Regressão focada de força, cerco e turno civil: 40 testes passaram. Isso fecha
uma parte material da manutenção militar, mas manutenção ampla de campanha,
guerra prolongada e solução política pós-guerra continuam pendentes.

## Demanda de trabalho agrícola proporcional à escassez — 19/09/2026

Quando uma facility agrícola fica limitada por falta de trabalhadores, o
relatório de workforce continua apontando para o recibo de produção do ciclo.
Se Economy também registrou `missing_food`, a quantidade demandada passa a ser
dimensionada pelos lotes authored necessários para cobrir essa falta, em vez
de ficar presa ao único lote mínimo. O limite de publicação permanece um
quinto da coorte e cada grupo ainda precisa aceitar a affordance, pagar o
stipend e concluir a transição física; nenhuma pessoa ou alimento é criado.

O recibo `workforce_demand` agora registra um delta engine-owned de `count`,
para que o aumento da demanda continue validável e navegável sem esconder a
prova de produção. A regressão de workforce, emprego e engine passou em 46
testes. No gate natural de 120 dias (`seed=73`), a mudança elevou transições
de 14 para 32 e reduziu `missing_food` final de 5.948 para 4.224, mantendo
conservação de dinheiro/recursos; resiliência de longo prazo e o gate de dez
anos continuam pendentes.

## Perseguição ritual no turno institucional — 19/09/2026

A negação de uma assembleia ritual observada agora também pode ser escolhida
no turno institucional mensal, sem depender de um aviso de contato militar.
`assembly_denial_adapters()` apenas expõe as opções já calculadas pelo owner de
Society: força própria preparada e abastecida, autoridade militar, observação
local recente e rito ainda em curso. A decisão continua contendo somente o
`selected_affordance_id`; o executor recompõe a observação, a posição e o rito
antes de criar `assembly_denied`, com payload `religious_persecution` e causas
canônicas. Levantar uma negação existente usa o mesmo owner e não cria um
efeito narrativo automático.

A regressão de ritos passou em 3 testes, e a integração conjunta de rito,
turno institucional, força e observatório passou em 30 testes. Isso fecha
apenas a entrada da perseguição ritual no ciclo de decisão; perseguição ampla,
intriga e solução política continuam pendentes.

## Catálogo PT-BR para capacidade institucional e mercado — 19/09/2026

Os rótulos de mercado local, oferta/demanda observadas e do painel de
capacidades estratégicas agora passam pelo catálogo `pt-BR` de
`web/src/medieval/i18n.ts`, em vez de strings hardcoded nos componentes. Isso
fecha uma fatia de UI da observabilidade sem criar estado novo. O type-check
medieval e os testes de `app`/`chronicle` passaram (12 testes); UI PT-BR
integral, provider remoto e o gate final continuam pendentes.

## Payload causal canônico no evento medieval — 19/09/2026

`WorldEvent.causal_payload` agora é um campo explícito do contrato Pydantic e
de `record_event`, em vez de um atributo extra anexado depois da criação. Isso
faz evidências estruturadas de ecologia, hazard e owners sobreviverem a
`model_dump` e save/load. O backend/frontend passaram a expor esse campo; a
Crônica mostra a evidência estruturada no detalhe causal. Persistência,
criaturas e ritos passaram em 22 testes; a regressão da Crônica passou em 4 e
o type-check medieval passou.

O finalizador também rejeita uma interpretação `LLM_INTERPRETATION` que tente
carregar `deltas` dentro do payload estruturado. A regressão conjunta de
persistência, autoria e engine passou em 27 testes.

## Limite operacional do gate natural de dez anos — 19/09/2026

Uma execução natural da seed `73` foi iniciada por `3600` dias para o gate
final e alcançou o dia `450` (mês 15) sem crash, sem falha de conservação
observada e com a cadeia causal de abastecimento/migração preservada. O trecho
levou aproximadamente 355 s; a projeção torna a execução integral longa demais
para este checkpoint e ela foi interrompida. O resultado não é aceite do gate:
três seeds, o horizonte completo e as fixtures pressionadas continuam
pendentes. A escassez crescente também confirma empiricamente que resiliência
econômica não deve ser declarada a partir de conservação isolada.

## Definições engine-owned de ecologia por espécie — 19/09/2026

Os parâmetros de metabolismo mensal e estresse de habitat das criaturas agora
vivem em `CREATURE_SPECIES`, um registro de código tipado em
`src/classes/environment/creature.py`. O executor material consulta a
definição da espécie e não mantém mais dicionários paralelos por nome. As duas
espécies authored atuais (`river_drake` e `river_serpent`) preservam seus
valores e a validação rejeita qualquer espécie sem lei engine-owned. Isso
generaliza a base da ecologia sem criar spawn, catástrofe ou ação automática;
15 testes focados de criaturas/hazards passaram.

## Probe operacional isolado do provider — 19/09/2026

Foi criado `tools/medieval_provider_probe.py` para a sondagem mínima da
fronteira real: ele recompõe uma affordance institucional atual, consulta o
provider somente quando explicitamente executado, aceita apenas o ID atual ou
`NO_ACTION` e verifica que o receipt `LLM_INTERPRETATION` não possui delta nem
origina mutação. Sem credencial/configuração, o comando falha explicitamente
com `real provider is not configured`; isso é o bloqueio operacional esperado,
não uma prova de autonomia. A regressão de AI/smoke/menu passou em 28 testes.

## Ajuda em curso no menu institucional único — 19/09/2026

No modo com provider, respostas, cumprimentos e reparações de ajuda
institucional agora entram no mesmo menu mensal que pedidos, mercado,
pesquisa, campanha e manutenção. O owner de `institutional_aid` continua
recompondo rota, estoque, autoridade e decisão; a mudança remove apenas a
consulta duplicada que antes ocorria depois do menu composto. Revisões datadas
de prazos reais continuam independentes. A regressão focada do menu civil
passou em 22 testes, incluindo uma entrega de ajuda escolhida por ID opaco e
executada materialmente.

## Reativação explícita após reparo — 19/09/2026

Uma instalação que foi materialmente interditada (`enabled=False`) agora pode
ser reaberta pelo maintainer apenas depois de sua integridade chegar a `1.0`.
`site_reactivation_options` recompõe uma affordance transitória a partir da
observação local atual, autoridade de `supply`, presença material e ausência de
reparo pendente. O executor exige a decisão por `selected_affordance_id`,
revalida a observação e emite `site_reactivated` com delta somente de
operabilidade; reparo continua sendo o owner da integridade e não há
reativação automática por narrativa ou conclusão de projeto.

A opção entrou no menu civil institucional e atualiza os relatórios de rota
após a decisão. A regressão de infraestrutura, serviços de site e menu passou
em 48 testes; `compileall` e `git diff --check` também passaram. O fixture de
frete `importing_world` foi tornado determinístico: como o mapa agora possui
uma facility agrícola em cada assentamento, a linha de Cinzaverde foi limitada
no cenário para que a escassez continue exercitando explicitamente a travessia
fluvial, sem impor preferência pela rota fluvial ao runtime geral.

## Índice transitório de rotas na revisão de migração — 19/09/2026

A revisão mensal de migração agora reutiliza, durante o próprio turno, os
relatórios públicos de rota já conhecidos por cada coorte. Antes, cada destino
possível reconstruía a mesma leitura e a mesma busca de topologia; isso tornava
o gate prolongado desnecessariamente caro. O índice é descartado ao fim da
revisão, não é persistido e não escolhe nem executa ações: `migration_options`
e `recovery_options` continuam recompondo affordances a partir de relatórios
atuais, e os owners revalidam a rota antes da marcha.

Regressão de migração, conhecimento e menu: 41 testes passaram. Smoke de 360
dias (`seed=73`) terminou em 180,74 s, conservou dinheiro/recursos, manteve
`save_load_equivalent=true` e a auditoria encontrou `broken_cause_ids=[]` e
`story_material_events=[]`. A economia continua pressionada; este checkpoint é
de eficiência e integridade, não aceite da resiliência nem do gate de dez anos.

## Correção de revalidação de expansão — 19/09/2026

O fallback determinístico que aplica técnicas conhecidas agora também valida
`required_site_capabilities` antes de criar um projeto, alinhado à mesma
pré-condição de `expansion_options`. Antes disso, o gate natural longo caía ao
tentar aplicar uma técnica em site authored incompatível. A regressão de
pesquisa/expansão passou em 33 testes; a execução curta de 360 dias com seed 73
e perfis natural/pressionados concluiu com conservação, save/load equivalente
e auditoria causal limpa. O gate de dez anos continua pendente, e a pressão de
subsistência observada permanece uma lacuna econômica real.

Atualizado em 19/09/2026. Este documento descreve o WIP local que será publicado
na branch de trabalho; não é uma declaração de produto concluído.

## Prioridade causal de workforce — 19/09/2026

O fallback offline de transição ocupacional agora prioriza corretamente uma
affordance cujo destino é `farmer` quando o relatório canônico registra falta
de comida. A correção removeu uma comparação com tupla aninhada que nunca
classificava essa opção como prioritária; nenhuma oferta nova, estoque ou renda
foi criada. O owner continua revalidando a decisão e pagando o stipend. A
regressão focada de workforce/emprego passou em 38 testes, e o smoke de 120
dias manteve conservação de dinheiro/recursos e equivalência de save/load. A
economia ainda pode permanecer pressionada; o gate de dez anos continua aberto.

No mesmo checkpoint, o fallback de emprego permanente passou a preferir uma
ocupação `farmer` quando duas affordances têm a mesma pressão local e há falta
de comida. A ordenação não cria emprego nem recurso: somente escolhe melhor
entre opções já enumeradas, mantendo a revalidação material do owner. A
regressão conjunta de emprego/workforce/smoke passou em 45 testes; resiliência
econômica de longo prazo continua pendente.

## Cadeia tecnológica agrícola — 19/09/2026

A árvore authored agora contém `crop_rotation`, dependente de `irrigation`, e
o blueprint `crop-rotation-works`, que transforma uma facility
`irrigated_harvest` em `rotated_harvest`. A sequência foi coberta por uma
regressão focada: pesquisa consome insumos, tempo, trabalhadores e folha;
conhecimento sozinho não altera a facility; a adaptação exige decisão do
proprietário, autoridade, site capaz, ferramentas, madeira e artesãos; somente
após a conclusão a produção passa de 120 para 150 alimentos por lote. Isso
amplia a árvore tecnológica sem criar catálogo paralelo ou efeito gratuito.
Ainda faltam difusão ampla e outras cadeias de produção fora desse recorte.
O release gate comparativo de 120 dias com seed 73 foi reexecutado depois da
mudança (`ok=true`, natural e pressionado, conservação de dinheiro/recursos,
save/load equivalente e auditoria sem causas quebradas ou Story material).

### Hazard por espécie — 19/09/2026

O owner de criaturas agora deriva efeito e resistência do registro
`HazardInteractionDefinition` da espécie, em vez de carregar constantes do
drake no payload. A segunda espécie authored (`river_serpent`) foi exercitada
por uma cadeia material de travessia, fome, demanda vencida, decisão e ataque
populacional limitado. A regressão focada de criaturas/autonomia passou em 14
testes, com `compileall` e `git diff --check`; magia/ecologia geral continuam
pendentes.

O observatório preserva o contrato público `dict[str, bool]` para resistência:
perfis ativos são chaves booleanas, sem lista transitória no read model. A
regressão composta de pesquisa, campanha, criaturas/autonomia e decisão passou
em 47 testes depois da correção.

O gate curto pós-alteração (`seed 73`, 120 dias, natural, `socorro` e quatro
perfis econômicos) terminou com `ok=true`, conservação de dinheiro/recursos,
save/load equivalente e auditoria sem causas quebradas ou Story material. A
economia continua pressionada, e o gate de três seeds por dez anos/provider
remoto permanece pendente.

Depois desse checkpoint, a regressão focada conjunta de pesquisa, logística de
campanha, cerco, criaturas/autonomia e decisão por provider passou em 45 testes.
Ela confirma as cadeias já implementadas e a fronteira de `NO_ACTION`/affordance
enumerada; provider remoto, ecologia geral, campanha territorial completa e o
gate prolongado continuam pendentes.

O recorte de integração institucional/econômica também passou em 85 testes,
cobrindo agenda mensal, menu civil, economia, migração, alfândega e conflito
cívico. Isso é evidência de owners/revalidação das fatias atuais, não aceite da
resiliência econômica geral ou da simulação de dez anos.

A segunda espécie agora também possui uma contramedida authored própria:
`rite-of-serpent-countermeasure` tem custo material, duração de 40 dias e o
perfil engine-owned `serpent_countermeasure`. O hazard do `river_serpent`
consulta esse perfil e pode ficar abaixo do limiar de impacto; a interação do
`river_drake` não é alterada. A regressão focada de ritos/hazard passou em 18
testes. Isso amplia a vertical de contramedidas, mas não fecha escolas mágicas
gerais ou ecologia ampla.

Uma campanha que já chegou a `breached` agora também recompõe uma retirada
material antes da ocupação: a coluna precisa de rota e suprimento atuais, o
owner encerra o investimento e registra `breached → withdrawn`, sem transferir
administração ou ocupação. A regressão conjunta de cerco/ocupação/controle
passou em 28 testes; guerra prolongada e solução política ampla continuam
pendentes.

Esse estado também pode abrir um cessar-fogo unilateral formal: a contraparte
responde independentemente e a obrigação de retirada só é concluída quando o
owner inicia a marcha física. Cessar-fogo mútuo permanece limitado ao cerco
ativo, porque a guarnição colapsada não tem retirada executável. A regressão de
campanha passou em 29 testes.

## Tecnologia aplicada — capacidade física authored

`irrigation-works` não depende apenas de conhecimento e materiais: o blueprint
exige `water_management`, presente no site authored `campos-do-lume`. A
affordance, o início e o progresso da obra revalidam essa capacidade; sem ela a
aplicação fica bloqueada sem mutação. A regressão focada de apprenticeship,
industry e expansion passou em 28 testes.

O menu civil composto agora entrega abastecimento e compras de mercado com um
contexto de situação público compartilhado. O provider vê apenas relatórios
próprios de assentamento, recursos, rotas conhecidas e cotações públicas
datadas; IDs de objetivo, estoque, conta, folha e quantidades permanecem
engine-owned. Os
executores recompõem e revalidam os termos atuais, portanto esta mudança fecha
uma lacuna de contexto/privacidade, mas não encerra a resiliência econômica.
Quando há várias compras possíveis, o fragmento também informa índice da
opção, origem pública e cotação datada; quantidade, saldo e reserva continuam
fora do provider e são recalculados pelo owner.

O release gate econômico também foi ampliado para comparar as políticas
determinísticas `desatento`, `alivio`, `mercado` e `mobilidade` na mesma seed.
A execução de 120 dias com seed 73 passou com alívio, compras de mercado e
empregos/transições selecionados, resultados materiais diferentes,
conservação de recursos e save/load equivalentes. A escassez ainda termina
pressionada; portanto a comparação valida alternativas causais, não equilíbrio
econômico ou resiliência de longo prazo.

## Trânsito público de rotas — 19/09/2026

`RouteReport` agora inclui `daily_flow_bulk`, leitura agregada e datada do
volume que atravessou a rota naquele dia. O valor é derivado do `RouteFlow`
canônico e não carrega IDs de carga, estoque, conta ou proprietário. O menu
civil de abastecimento/mercado entrega essa leitura junto das alternativas de
rota; o owner continua recompondo capacidade e termos antes de abrir o frete.
Save/load, proveniência de boletim, logística e decisão institucional foram
regredidos em 50 testes focados; a UI PT-BR mostra o trânsito observado na
inspeção de rota e nos planos de abastecimento.

Contratos de emprego permanente agora usam o salário authored da facility local
compatível com a ocupação, com piso V1 apenas para site sem facility. Isso
remove o valor fixo paralelo de salário e mantém produção, payroll e renda
doméstica na mesma premissa canônica; o owner ainda revalida saldo e mão de
obra a cada mês. A regressão focada de emprego passou em 10 testes.

## Checkpoint de verificação — 19/09/2026

O fallback offline/test de workforce agora pode aceitar uma oferta de transição
ocupacional já observada quando há pressão de subsistência e falta de trabalho
material. Ele seleciona somente o ID de uma affordance existente, com ordenação
conservadora; stipend, disponibilidade, autoridade, rota e conclusão continuam
sob o owner de workforce. Isso permitiu que a matriz econômica de 120 dias
exercitasse transições sem transformar estoque público em consumo gratuito.

Na execução `seed=73`, 120 dias, com os quatro perfis econômicos, o gate terminou
com `ok=true`, `natural_ok=true`, `pressured_ok=true`, conservação de recursos,
save/load equivalente e auditoria sem causas quebradas ou Story material. Os
perfis selecionaram alívio, mercado e mobilidade, e a mobilidade registrou
transições ocupacionais. Isso é evidência da alternativa causal, não prova de
resiliência econômica de longo prazo; o provider remoto e o gate de dez anos
continuam pendentes.

O clone transacional do mapa agora compartilha apenas topologia authored e
isola rotas, sites, interdições e fila de updates. A igualdade de eventos trata
listas/tuplas JSON como a mesma sequência para validar save/load. A regressão
focada passou em 26 testes; o gate natural + pressionado de 120 dias com seed
73 terminou com `ok=true`, `natural_ok=true` e `pressured_ok=true`, conservação
de recursos e continuação equivalente.

O contrato de publicação do observatório agora rejeita retratos sem as projeções
canônicas de campanha (`territorial_controls`, `occupations`, `siege_campaigns`
e `threats`) antes de substituir o snapshot exibido. A regressão web focada
passou em 18 testes e o `vue-tsc` continuou limpo; isso protege a UI contra
fallback parcial da API, sem criar compatibilidade com payloads antigos.

A projeção de ameaças também cobre interdição física de rota, perseguição
religiosa material e dano de hazard em instalação. O último caso aponta para o
`damage_event_id` e o `site_id`, permitindo seguir a cadeia de exposição até a
restauração sem transformar a consulta em decisão ou conhecimento de ator.

Memórias institucionais agora carregam uma classificação derivada do fato
(`commitment_fulfilled`, `commitment_breached`, `commitment_repudiated` ou
reparação), exibida na diplomacia. A classificação é read-only e preserva o
evento e a saliência engine-owned como fontes únicas.

O release gate persistente de 360 dias concluiu as três seeds naturais (`73`,
`101`, `137`) e a fixture pressionada `socorro` (`73`). As quatro execuções
conservaram dinheiro/recursos, preservaram save/load e passaram a auditoria com
`broken_cause_ids=[]` e nenhuma Story material. A linha pressionada terminou com
17.412 eventos, 33 pedidos, 29 cumprimentos e 22 protestos; a crise alimentar
reduziu a saúde média para 33 e elevou o unrest médio para 949,5, com 296 mortes
por privação. Isso é evidência de pressão material e de reação causal, não prova
de resiliência econômica: a vertical de escassez/abastecimento ainda precisa
permitir alternativas de rota, produção e migração antes do gate final de três
seeds naturais por dez anos. Ainda falta também validar provider remoto real.

O mapa authored agora possui uma fazenda alimentar real em cada um dos oito
assentamentos, com facility `harvest`, estoque público local, tesouro
administrador e owner/maintainer explícitos. Isso corrige a premissa anterior
em que sete cidades tinham agricultores, mas nenhuma instalação produtiva local;
não cria comida fora de `produce_monthly`: cada facility ainda depende de
integridade, autoridade, mão de obra, folha e capacidade de armazenamento. A
folha agrícola agora paga `4` por trabalhador, igual ao preço-base da ração;
isso é uma premissa econômica authored, não uma transferência automática fora
do owner de Economy. A regressão de economia/consumo/engine/mapa passou em 47
testes, e o smoke de 120 dias com a fixture `socorro/73` terminou sem mortes por
privação (saúde média 880,5), com 9 pedidos, 6 cumprimentos e 3 migrações
iniciadas por coortes que tinham renda, reserva, reports e rotas válidos. A
pressão ainda é visível e a chegada/mobilidade continuam materiais; o artefato
foi auditado com 3.330 eventos, `broken_cause_ids=[]` e
`story_material_events=[]`.

O prolongamento pressionado de 360 dias com a mesma premissa agrícola
(`socorro/73`) também concluiu sem crash e passou a auditoria: foram 13.527
eventos, população final 10.717, 28 migrações iniciadas e 24 chegadas, sem
morte de personagem. Isso não fecha a vertical de escassez: `ferroalto`,
`pedraclara` e `portovelho` ainda chegaram a `health=0`/`unrest=1000`, enquanto
as demais cidades conservaram pressão menor. O resultado confirma que emprego,
renda, rota e chegada são materiais, mas que distribuição de excedente,
alternativas de abastecimento e recuperação social ainda precisam ser
produzidas por decisões e owners reais.

Uma reprodução no dia 30 separou o gargalo: `ferroalto`, `pedraclara` e
`portovelho` ainda possuíam estoque público de alimento, mas suas coortes
locais não tinham saldo doméstico suficiente para comprar as rações. Ao mesmo
tempo, coortes de agricultores se deslocaram para assentamentos com
trabalho/estoque mais favoráveis. A próxima correção econômica deve, portanto,
enumerar renda, requalificação ou migração como affordances materiais; não deve
converter estoque público em consumo gratuito nem criar dinheiro fora de
payroll/mercado. O turno institucional agora entrega ao provider um fragmento
público de emprego permanente — pressão observada, coorte, ocupação, site,
limite e salário da opção — sem expor saldos de conta ou estoque privado; o
owner ainda recompõe e revalida todos os termos antes de criar o contrato. Isso
melhora a escolha causal, mas não transforma emprego em renda automática e ainda
precisa de provider operacional e fixture pressionada para medir o efeito.
Recuperação de frete bloqueado agora também aparece no menu civil do
proprietário: esperar ou abrir uma remessa sucessora por rota fiscal conhecida.
O order original permanece histórico e imutável; somente o owner de Logistics
abre o successor após nova decisão e revalidação física.
Compras bilaterais bloqueadas agora também entram na decisão civil: o comprador
solicita reenvio por rota sem tarifa e o vendedor responde separadamente. A
resolução devolve o parcel original ao estoque do vendedor e abre uma única
sucessora, sem duplicar o pagamento histórico.
Ofertas de transição ocupacional agora também entram no mesmo menu mensal do
grupo populacional: o grupo pode aceitar uma opção enumerada, mas o stipend,
treinamento e mudança de ocupação continuam passando pelos owners materiais.
Migração e recuperação de jornadas seguem o mesmo contrato ID-only: a consulta
expõe apenas ação, ator e affordance; o owner recompõe contagem, ração, rota e
reports atuais antes de criar a autorização material ou alterar a jornada. A
regressão focada de migração passou em 12 testes e a integração de agenda/engine
em 11, incluindo retorno e reroute por rotas conhecidas, sem perder a
proveniência do decision event. Isso fecha o contrato causal, não a resiliência
econômica geral.
Pagamentos materiais de suborno e abertura de alfândega seguem a mesma fronteira:
o ator seleciona somente a affordance; o owner recompõe contas, valor, equipe e
site e registra a autorização interna antes da mutação. As regressões focadas
passaram em 4 testes de suborno e 18 de alfândega.
A transferência bilateral de workshop também usa consentimento ID-only: o
vendedor seleciona a affordance, e o comprador recompõe destinatário, facility,
estoque e folha atuais antes da aceitação. A regressão de conveyance passou em
11 testes; a aceitação também não carrega termos materiais, e nenhum direito
patrimonial novo foi criado.
O perfil determinístico do smoke responde `NO_ACTION` para essa família por
escopo, então a integração não é apresentada como resiliência econômica já
alcançada.
O perfil de fixture `mobilidade` foi adicionado para exercitar essa costura sem
provider real: em 120 dias criou 20 contratos permanentes, liquidou 28 folhas
e registrou 2 não-pagamentos, com dinheiro/recursos conservados e auditoria
causal limpa (`broken_cause_ids=[]`, nenhum Story material). Isso é prova da
vertical de decisão/payroll, não uma afirmação de economia resiliente.
O evento `subsistence_resolved` agora também carrega a leitura
estruturada de `required`, `public_required`, consumo doméstico, compras,
déficit e coortes afetadas, permitindo explicar esse gargalo sem interpretar a
prosa ou vazar saldos privados para decisões que não os conhecem.

A ecologia de criaturas ganhou uma leitura material adicional: quando uma rota
authored ligada ao habitat está fechada por um fato canônico, o próximo tick
mensal aplica somente o estresse engine-owned daquela espécie e aponta para a
causa de fechamento. Isso não cria demanda, retaliação ou ataque; a criatura
ainda precisa receber sua própria affordance e decidir depois. A regressão
focada de criaturas/hazard/engine passou em 20 testes.
O tick também preserva payload estruturado com espécie, rotas fechadas,
estresse de habitat, decaimento-base e decaimento total. O observatório/`Why`
pode explicar a leitura sem interpretar a prosa do evento.

Criaturas agora também mantêm uma memória curta de até 32 eventos canônicos que
elas próprias vivenciaram (travessias, demandas, tributos e consequências
materiais). A memória não duplica o EventStorage: o save guarda apenas IDs
validados, o turno da criatura recompõe tipo/data desses eventos e decisões
continuam limitadas às affordances atuais. O schema nested de `CreatureState`
foi avançado para 4, rejeitando saves antigos explicitamente. A regressão de
criaturas/autonomia/hazard/observatório passou em 26 testes; isso fecha a
memória local da vertical, não a ecologia geral nem todas as espécies.

Uma negação material de assembleia ritual agora produz a cadeia
`assembly_denied → rite_interrupted → rite_interruption_pressure`: o owner de
Economy aplica no máximo 60 pontos de `unrest`, com causas navegáveis, sem
iniciar automaticamente protesto, movimento ou rebelião. A regressão ritual,
de alcance e cívica passou em 21 testes.

Compromissos de pagamento quebrados agora também podem ser reparados por uma
affordance transitória do próprio devedor: ela exige aviso privado da quebra,
autoridade de comércio e saldo atual suficiente. O owner de Economy executa o
pagamento; Relations marca o termo como `remediated`, preserva o evento
`commitment_breached` e cria memória/causalidade da reparação. A regressão
focada de pagamentos, renegociação, memória, ritos e civic passou em 31 testes.

A árvore militar ganhou `fortification`, dependente de `siegecraft`. Quando o
defensor conhece a técnica antes de iniciar um cerco, o owner de Society
recompõe a endurance inicial de 12 para 14, com delta e validação canônicos;
sem conhecimento o valor permanece 12. A regressão conjunta de cerco,
engajamento, indústria e pesquisa passou em 37 testes.

A mesma árvore agora contém `field_logistics`, dependente de `field_drill`.
Conhecimento dessa técnica aumenta em cinco dias a capacidade de ração da
coluna e da bagagem de campanha, somente para o proprietário que a conhece;
nenhum estoque ou provisão é criado no aprendizado. A regressão de supply,
cerco e pesquisa passou em 24 testes.

Repressão cívica agora também atravessa o owner de Economy: a decisão militar
produz `civic_suppression_pressure` limitado a 120 pontos de `unrest`, e o
receipt de `civic_movement_suppressed` aponta para essa pressão. Participantes
continuam sendo liberados, administração não muda e nenhum novo movimento é
criado automaticamente. A regressão cívica, ritual e engine passou em 21 testes.

A negação material de assembleia ritual agora também classifica o fato canônico
como `social_conflict.kind=religious_persecution`, apontando para o observador,
site e decisão que produziram a negação. Isso é apenas observabilidade do ato
material; a pressão continua sendo aplicada por Economy e não cria perseguição
ou movimento por texto.

A matriz natural de três seeds (`73`, `101`, `137`) por 360 dias também
concluiu sem provider real: todas conservaram dinheiro/recursos, mantiveram
`save_load_equivalent=true` e passaram a auditoria sem causas quebradas ou
Story material. O gate de dez anos e a validação operacional do provider ainda
estão pendentes.

Uma tentativa posterior de 3.600 dias com a seed 73 chegou ao dia 180 sem
crash ou causa quebrada no trecho observado, mas foi interrompida por custo
operacional (aproximadamente 69 segundos para seis meses). Isso não é um
resultado do gate de dez anos: o horizonte continua pendente e a interrupção
não deve ser interpretada como falha causal.

Para reduzir esse custo sem relaxar rollback, o clone transacional do mundo
passou a compartilhar somente os objetos do prefixo de eventos append-only,
mantendo lista, registries, agenda e RNG isolados. O perfil de 18 passos caiu
de 14,5 s para 11,4 s. O gate natural de seed 73 por 120 dias depois dessa
mudança terminou com `ok=true`, conservação de dinheiro/recursos,
`save_load_equivalent=true`, `broken_cause_ids=[]` e nenhum Story material; o
gate de dez anos ainda não foi executado.

Também foi corrigido um vazamento no menu institucional composto: IDs de
affordances que embutem estoque, tesouro, conta, folha ou pantry são tokens
opacos no prompt do provider e voltam ao ID canônico somente na fronteira de
revalidação. O dossier/contexto de capacidade estratégica para atores agora
leva apenas status e contagens; a projeção Dao/API mantém os IDs navegáveis.
IA, recourse, dossier, estratégia e diplomacia passaram em 32 testes focados.

O procurement econômico deixou de descartar rotas fiscais alternativas. Cada
caminho conhecido agora gera uma affordance transitória distinta; a política
offline mantém sua ordenação deterministicamente conservadora, enquanto o
provider pode escolher uma rota enumerada. Quantidade, tarifa, cotação e
revalidação continuam pertencendo ao owner de Economy/Logistics. Os rótulos
mostram a rota pública, mas a resposta continua sendo somente o ID enumerado.
A regressão focada de procurement, roteamento, escassez, ajuda e recuperação
passou em 56 testes.

## Atualização incremental do roadmap (18/09/2026)

As ondas recentes adicionaram fatias causais, não encerraram os sistemas inteiros:

- fatos medievais classificados como `STATE_TRANSITION` agora exigem ao menos
  um `StateDelta`; um receipt textual sem mudança canônica não pode se apresentar
  como mutação material.
- a affordance de pedido de ajuda alimentar não depende mais de existir um
  objetivo estratégico: relatório atual de fome e administração local bastam.
  O smoke mostrou que o fallback ainda pode escolher outras affordances antes
  do pedido, mas a opção agora existe quando a pressão é real. A leitura de
  presença de sabotagem também deriva corretamente `ExpansionProject` pela
  instalação da facility.

- venda tecnológica paga: comprador e detentor consentem separadamente; pagamento,
  instalação, autoridade, conhecimento e receipt causal são revalidados pelo owner;
- `SiegeCampaign`: cerco persistente sobre investimento e guarnição reais, com
  progresso diário, `breached` ou `lapsed`, sem transferir ocupação ou administração;
- a manutenção militar agora oferece rotação explícita: outra coluna própria,
  presente, abastecida e financiável pode substituir a guarnição ativa sem
  transferir ocupação, administração ou controle; o vínculo antigo fica
  `withdrawn` e o novo tem decisão, receipt e save/load canônicos;
- o próprio proprietário agora recebe, na consulta institucional mensal, as
  affordances de estabelecer, retirar ou rotacionar uma guarnição atual mesmo
  sem contato estrangeiro. A execução continua no owner de Society/force; o
  fluxo bilateral de contato permanece separado;
- interação de hazard do drake com instalação: ward é resistência engine-owned,
  magnitude limitada e evidência de hazard/exposição/resistência registrada;
- proteção mágica agora pode persistir perfis de resistência engine-owned:
  `rite-of-river-countermeasure` grava `river_countermeasure` na ward e o
  registro de hazard aplica essa resistência limitada sem depender de prosa;
- o segundo habitante do Rio Lume agora é uma `river_serpent` authored, não um
  alias do dragão: suas magnitudes e resistências de hazard são registradas no
  catálogo engine-owned e escolhidas pela espécie canônica;
- projeções de API/observatório passam a expor campanhas, vendas tecnológicas e
  evidência de hazard.
- `CampaignView` também projeta propostas ativas de desescalada e concessão
  administrativa com seus termos, estado e eventos-fonte; o Atlas exibe esses
  acordos em curso somente como leitura navegável.
- o runtime de jogo e os smokes optam por uma única renda domiciliar inicial,
  financiada pelos tesouros e registrada como fato/delta; a factory padrão segue
  pura para testes e ferramentas que não optam pela premissa.
- objetivos e planos institucionais persistidos agora recompõem uma capacidade
  estratégica multidimensional (reservas, insumos produtivos e defesa territorial)
  dentro da única consulta mensal já composta; a capacidade é read model derivado,
  não um planner, não cria recursos e não executa ações automaticamente.
- a memória institucional direcional agora entra no contexto diplomático apenas
  quando o ator possui notice e fato canônico correspondentes; a leitura expõe
  valor derivado e eventos de evidência, sem copiar termos estrangeiros nem criar
  um segundo score persistido.
- a decisão defensiva também recebe essas leituras institucionais conhecidas,
  sempre como referências a fatos e sem transformar memória em capacidade ou
  planner;
- decisões cívicas do administrador agora recebem a mesma leitura direcional
  de memória institucional filtrada por notices conhecidos, sem copiar saldo,
  estoque ou termos estrangeiros para o prompt; a decisão continua pertencendo
  ao ator e a execução aos owners de Society/Economy.
- o orçamento mensal mantém todas as polities antes da fila de organizações,
  rotacionando cada classe separadamente para que uma rotação nunca consuma o
  orçamento inteiro antes de uma instituição política receber consulta;
- cópia tecnológica e alfândega agora participam da mesma consulta composta:
  o primeiro fluxo revalidado abre trabalho pago quando há acesso material, e o
  segundo permite ao proprietário escolher declaração, evasão, pagamento ou
  retorno de contrabando a partir das opções atuais.
- `field_drill` foi adicionado ao catálogo de pesquisa como capacidade militar;
  conhecimento canônico dessa técnica produz somente +1 por combatente em
  `field_strength`, com teste causal separado. `siegecraft` agora depende de
  `field_drill`; quando ambos são conhecidos, o cálculo engine-owned acrescenta
  apenas um segundo passo limitado de força de campo. O owner de pesquisa rejeita
  qualquer aprendizado cujo pré-requisito ainda não seja conhecido.
- a crônica recebe datas humanas canônicas além dos cursores internos de mês, e o
  template é instruído a nunca interpretar `month_stamp` como ano.
- uma consulta institucional sem affordance agora gera receipt determinístico sem
  chamar provider; o observatório separa `provider_declines`, `provider_failures`
  e `no_affordance_receipts` em vez de inferir manutenção a partir da ausência de
  decisão; a UI mostra esses cinco contadores sem misturá-los, com teste de
  integração que verifica valores e rótulos independentemente.
- `SiegeCampaign` persiste `garrison_endurance` e reduz essa resistência por
  força relativa, provisões atuais e pressão diária engine-owned; não transfere
  administração ou ocupação. Ao zerar a endurance, a owner de Society registra
  `garrison_collapsed` e encerra a obrigação da guarnição, mas mantém o
  destacamento defensor presente para uma decisão posterior.
- roubo tecnológico institucional agora usa agente/ofício, presença física,
  sighting, relatório de instalação e conhecimento-fonte canônicos; só o resultado
  bem-sucedido cria `TechnicalKnowledge(channel="stolen")`, enquanto falha ou
  descoberta preservam o catálogo e deixam finding privado.
- emprego recorrente agora possui contrato Economy-owned explícito: a instituição
  escolhe uma affordance de site local próprio e coorte, o owner persiste empregador,
  estoque, conta, limite e salário, e cada fronteira mensal revalida site, mão de
  obra, autoridade e fundos antes de chamar `settle_work`; insuficiência gera receipt
  de não pagamento, nunca dinheiro criado.
- a difusão por apprenticeship exige agora um receipt do owner de migração
  (`migration_arrived` ou `migration_returned`) que tenha movido o especialista;
  um evento genérico de relocação não é aceito como causa de transferência
  tecnológica. A oferta também pode ser feita por um residente habilidoso que
  não foi o pesquisador do projeto, desde que a jornada material e o fato de
  conhecimento da instituição de origem sejam encontrados; o receipt da oferta
  aponta para essas duas evidências.
- `tools/medieval_causal_audit.py` oferece uma auditoria read-only de saves,
  verificando histórico, causas quebradas, materialidade de Story e separação
  dos receipts de interpretação LLM; não é o smoke final de dez anos.
- Persuasão diplomática V1 agora é uma escolha própria do proponente sobre uma
  proposta ainda aberta. O owner registra um receipt zero-delta e reentrega o
  aviso à contraparte, sem alterar termos, status ou obrigações; a contraparte
  continua precisando responder em sua própria decisão.
- uma recusa administrativa de demanda cívica agora fecha o protesto com decisão
  própria e permite ao owner de Economy registrar `civic_refusal_pressure`: um
  incremento limitado de `unrest`, com causa apontando para a recusa. Isso alimenta
  futuras affordances sociais sem iniciar revolta automaticamente; quando a demanda
  é respondida por entrega ou reparo material comprovado, o mesmo owner registra
  `civic_resolution_relief`, um alívio limitado causalmente ligado ao encerramento.
- a primeira composição material após a recusa agora é o tumulto cívico V1:
  `join_civic_tumult` só aparece com unrest alto observado pelo grupo, recusa
  recente e uma instalação local observada. A decisão do grupo danifica no máximo
  `0.08` de integridade via owner de Map e emite `civic_tumult_occurred` com
  decisão, recusa, relatórios e instalação na cadeia causal. Uma recusa autoriza
  no máximo um tumulto; não há líder, facção ou rebelião automática.
- grupos com unrest observado muito alto (`650+`) e coorte disponível suficiente
  também podem selecionar `organized_strike`: uma paralisação local de três dias
  que reserva uma fração engine-owned da própria coorte. Ela expira sem criar
  liderança ou autoridade política; resposta administrativa e pressão causal
  continuam separadas da futura rebelião.
- uma chegada de migração agora também altera as condições sociais de forma
  engine-owned: o `unrest` da origem recebe alívio limitado pela fração que
  efetivamente chegou, enquanto a pressão observada dos migrantes é incorporada
  ao destino. Os dois deltas ficam no fato `migration_arrived`, com decisão,
  provisão, rota e jornada na cadeia causal; retorno físico não recebe esse atalho.
- uma jornada que fica bloqueada por falta de moradia agora oferece reroute para
  outra cidade conhecida, desde que relatórios de assentamento/rota estejam
  atuais e a capacidade de destino comporte o grupo. A decisão altera somente a
  jornada e abre um novo trecho físico; população, estoque e pressão só mudam
  quando a chegada posterior for executada. A regressão de migração passou em 12
  testes.
- um movimento cívico V1 agora pode ser formado somente depois de um catalisador
  cívico recente, relatórios locais atuais com pressão suficiente, pelo menos dois
  grupos na mesma cidade e uma liderança nomeada presente. A owner de Society
  reserva participantes reais dos grupos, persiste o movimento e mantém seus
  fatos/causas; após três dias a liderança pode dissolvê-lo e liberar as coortes.
  Não concede autoridade, território, armas ou rebelião automática.
- um movimento cívico ativo e estabilizado agora pode iniciar uma greve geral V1:
  grupos locais reservam trabalhadores adicionais por três dias, a agenda resolve
  a liberação por recibo factual e a disponibilidade de trabalho cai durante o
  intervalo. A greve exige relatórios atuais, liderança presente e decisão do
  movimento; não cria rebelião, autoridade ou dano narrativo automático.
- depois de uma mobilização concluída, pressão observada de `800+` e liderança
  presente, o movimento pode declarar uma rebelião V1 por decisão própria. A
  declaração mantém administração e território intactos, conserva participantes
  reservados e deixa a Economy registrar pressão adicional com causa navegável;
  não cria facção, guerra ou vitória automática.
- a administração local pode oferecer negociação preventiva a um movimento ativo
  ou responder a uma rebelião declarada com supressão/negociação, desde que
  possua autoridade militar e observação atual do próprio assentamento. A
  Society registra a decisão com causas do movimento/da rebelião e do relatório;
  não há ainda solução política geral. Em ambos os casos, a liderança aceita
  pela affordance própria;
  a liderança aceita pela affordance própria, encerra o movimento e a Economy
  aplica alívio limitado sem apagar a rebelião histórica.
- uma rebelião persistente, com pressão observada de `900+` e mobilização
  concluída, também pode declarar revolução por decisão do movimento. O estágio
  aumenta a pressão de forma limitada e continua sem transferir administração,
  território ou vitória; a mesma negociação/supressão precisa ser escolhida
  posteriormente pela administração.
- depois que a liderança aceita a negociação e dissolve o movimento, a
  administração pode conceder uma anistia formal por uma decisão independente.
  A anistia é persistida pela Society, aponta para a dissolução e o relatório
  atual, não ressuscita participantes, não altera administração e não apaga a
  rebelião ou a recusa histórica.
- a negociação cívica agora carrega uma oferta alimentar engine-owned do estoque
  atual do administrador. A oferta é persistida no movimento, mas o estoque só
  é consumido depois da aceitação da liderança; se a reserva mudou, a
  affordance fica stale e nenhuma mutação ocorre. O alívio de unrest continua
  sendo aplicado pelo owner de Economy e aponta para a entrega material.
- resoluções de combate de campo agora preservam a força anterior e registram
  deltas engine-owned para o terreno físico da região, a fadiga derivada dos dias
  de implantação e a moral tática limitada por preparo/suprimento. Esses fatores
  alteram a força efetiva sem serem escolhidos pela LLM ou inferidos da prosa.
- uma campanha de cerco que chega a `breached` agora recompõe, no turno armado
  posterior, uma affordance explícita de `occupy_after_siege_breach`. O owner de
  Society altera somente `occupier_id`, preserva o administrador vigente e exige
  decisão atual, relatório local, presença/suprimento do atacante e guarnição
  defensora já colapsada; a brecha sozinha continua sem conceder ocupação.
- ocupação física, controle territorial e administração agora são estados
  distintos: depois de ocupar e manter uma guarnição paga, o ocupante pode
  selecionar uma affordance explícita de controle territorial. Society persiste
  essa decisão, exige observação local atual e não muda administrador ou claims;
  perda material/colapso da guarnição encerra o controle por evento causal
  próprio. O ocupante também pode retirar esse mandato por decisão separada,
  mantendo presença e administração como estados independentes. A instituição
  agora pode retirar voluntariamente a guarnição por decisão própria: o dever e
  o controle sustentado por ele terminam, mas a coluna, a ocupação física e a
  administração permanecem. A projeção de campanhas expõe os controles ao Dao.
- a API ganhou o read model privado `/api/v2/query/dossier/{actor_kind}/{actor_id}`:
  ele filtra notices e relatórios pelo `recipient_ref`, inclui conhecimento técnico,
  memórias e planos do próprio ator e agora inclui o receipt factual conhecido,
  além de expor somente os elos causais de um fato cujo evento também esteja no
  conjunto conhecido pelo ator. Não copia inventário, plano ou observação de outra
  instituição; a cadeia completa continua exclusiva da visão causal do Dao.
- uma escolha que fica obsoleta durante a consulta institucional agora deixa o
  receipt determinístico `institutional_decision_stale_affordance`, sem delta e
  sem transformar a interpretação em mutação.
- cumprimentos materiais de ajuda agora criam memória institucional para
  proponente e contraparte no próprio receipt `institutional_aid_fulfilled`;
  o credor recompõe uma leitura positiva limitada (+3), enquanto a memória
  continua sujeita à saliência derivada e à fronteira de conhecimento. O fato
  de cumprimento não apaga breaches anteriores.
- conclusões de qualquer obrigação bilateral agora criam memória para as duas
  instituições: pagamento, ensino, frete, retirada e transferência administrativa
  passam pelo mesmo receipt canônico. A leitura continua direcional e derivada
  apenas quando o observador possui o notice do fato; nenhum score social novo é
  persistido.
- `tools/medieval_autonomy_smoke.py` agora oferece `--real-provider` como
  sondagem explícita, com limite configurável por passo e falha visível quando
  o provider não existe; não há fallback silencioso para perfil determinístico.
- Após essa alteração, o smoke curto da seed 73 por 30 dias terminou com
  conservação de comida/dinheiro/recursos, save-load equivalente e 0 causas
  quebradas na auditoria (`506` eventos; nenhuma Story material). Isso é
  evidência de regressão curta, não o gate final de dez anos.
- A reexecução natural da seed 73 por 120 dias terminou com `2268` eventos,
  conservação econômica, save-load equivalente e auditoria sem causas quebradas
  nem Story material. Foram 161 interpretações em test mode; a sondagem com
  provider real ainda está pendente.
- Uma execução persistente da seed 73 por 360 dias terminou em
  `horizon_complete` com 7.698 eventos, conservação econômica,
  `save_load_equivalent=true` e auditoria sem causas quebradas nem Story
  material. O perfil determinístico cobre socorro direto/protesto, não o pedido
  institucional de ajuda; portanto `aid_requests_total=0` nesse relatório não
  é conclusão sobre o provider real. O gate de dez anos e a sondagem operacional
  do provider continuam pendentes.
- O harness também possui o perfil determinístico `socorro` para testar a cadeia
  institucional completa sem inventar parâmetros: em 120 dias ele produziu 9
  pedidos e 5 cumprimentos de ajuda, com 3.496 eventos, conservação,
  save/load equivalente e auditoria causal limpa. Isso é fixture de verificação,
  não comportamento automático do motor nem substituto do provider real.
- Findings privados de espionagem, investigação e roubo tecnológico agora são
  projetados no contexto diplomático apenas para o `recipient_ref`, mantendo a
  separação entre conhecimento e memória e sem transportar saldos, estoques ou
  planos alheios. A regressão focada desses caminhos passou em 21 testes.
- Uma investigação atribuída agora pode abrir uma affordance explícita de
  acusação institucional. O owner registra uma decisão sem delta, entrega ao
  sujeito um `InvestigationAccusationNotice` persistente e liga o evento à
  descoberta factual; não há culpa automática, retaliação, alteração de relação
  ou efeito material. A regressão de sabotagem/investigação/persistência passou
  em 5 testes, e o conjunto focado de intriga/conhecimento em 31.
- A projeção de diplomacia do `/api/v2` também expõe ao Dao esses findings
  estratégicos com `recipient_ref`, resultado e evidências canônicas; o frontend
  valida/tipa `strategic_evidence` e o painel de diplomacia lista cada finding,
  seu destinatário e navegação para o evento causal. `vue-tsc` e os 61 testes medievais da UI
  passaram, além de 21 testes focados de API/observatório.
- O commit transacional do engine valida incrementalmente apenas os eventos
  novos do candidato; persistência e auditoria seguem com validação completa.
  A regressão de eventos/persistência passou em 102 testes. O smoke natural de
  120 dias preservou recursos, dinheiro e equivalência de save/load; uma rodada
  de dez anos chegou ao dia 420 sem crash, mas foi interrompida por custo de
  execução e não fecha o gate final.
- O teste de persistência do engine agora compara a linha contínua com a linha
  save/load sem presumir que cada passo seja um mês: agendas datadas de frete e
  recourse podem consumir passos intermediários. `tests/test_medieval_engine.py`
  passou em 6 testes; o smoke natural de dez anos continua pendente.
- A vertical mágica agora também registra `rite-of-flood-control`, um ward
  material com custo, qualificação e duração de 30 dias que expõe o perfil
  engine-owned `flood_control`. A lei de enchente consulta essa resistência
  limitada; o rito não repara o site nem cancela a causa. Ritos/hazard passaram
  em 12 testes focados.
- O atlas de campanhas agora destaca demandas abertas de criaturas na rota
  conhecida, com linha de ameaça e marcador no ponto médio; o desenho é uma
  projeção transitória de `CreatureView.demands` e não cria estado de mapa.
  `vue-tsc` e os 61 testes medievais da UI passaram.
- O Rio Lume agora começa com um segundo indivíduo do mesmo habitat, com
  limiar e tributo próprios. Para manter a agência separada, revisões são
  agendadas por criatura (`creature-review:{creature_id}:{day}`); uma revisão
  não consulta nem move outro habitante. A regressão de criaturas, autonomia e
  hazard passou em 11 testes.
- Smoke natural pós-multiplicidade (seed 73, 120 dias) terminou com 2.815
  eventos, conservação econômica, save/load equivalente e auditoria sem causas
  quebradas nem Story material. A pressão final foi material (`missing_food`
  10.145, saúde média 731,25, unrest médio 268,75); o gate de dez anos segue
  pendente.
- Jornadas de migração bloqueadas agora acumulam pressão social observável: a
  cada sete atrasos materiais, o owner de subsistência aplica +5 de `unrest` na
  origem, limitado a 1000, com delta e causas da rota/jornada. Isso não inicia
  migração, revolta ou narrativa automaticamente; a regressão de migração passou
  em 11 testes.
- `tools/medieval_release_gate.py` agora reúne o smoke natural e a fixture
  pressionada em uma única verificação auditável. A execução verificada da seed
  73 por 120 dias com `--pressured` preservou comida/dinheiro/recursos, manteve
  save/load equivalente e auditoria causal limpa, além de exercitar pedidos e
  cumprimentos institucionais de ajuda. É um gate curto de release, não
  substitui provider real nem o smoke de três seeds por dez anos.
- O atlas agora oferece uma camada visual de campanhas: ocupações e controles
  territoriais colorem assentamentos, interdições destacam rotas, colunas
  presentes mostram sua contagem e cercos, planos e instalações danificadas
  ficam marcados. Tudo é derivado do `CampaignView`; não existe
  estado transitório persistido na UI. Type-check e 60 testes medievais do
  frontend passaram.
- O dossier privado agora inclui `causal_depth` para a cadeia conhecida entre
  decisões próprias e fatos observados. É apenas read model: causas não
  conhecidas pelo ator continuam ocultas e o grafo completo permanece Dao-only.
- O contexto diplomático agora inclui a capacidade estratégica derivada do
  próprio ator nas dimensões de reservas, insumos e defesa. É leitura dos
  objetivos/planos persistidos; não reserva recursos nem revela estado externo.
- A capacidade estratégica passou a expor também as dimensões derivadas de
  administração, diplomacia, comando militar, projetos e logística. Elas são
  reconstruídas de contratos, propostas, forças, projetos e cargas canônicos
  quando o contexto possui o mundo; não são um planner nem reservam recursos.
  A regressão focada de estratégia/diplomacia passou em 18 testes.
- O `GovernanceView`/observatório agora projeta essas capacidades por ator,
  incluindo os IDs dos registros canônicos que sustentam cada dimensão. A
  projeção é Dao-only e não transporta inventário, planos estrangeiros ou
  affordances transitórias; `vue-tsc` passou.
- O observatório também exibe um painel PT-BR de capacidades estratégicas por
  instituição, com status e quantidade de registros-fonte. O painel é somente
  leitura do Dao e mantém o fallback vazio quando uma fixture antiga não traz
  a projeção; o frontend passou em 62 testes medievais.
- a projeção da sociedade agora valida e exibe `civic_protests`,
  `civic_movements`, `civic_strikes` e `civic_amnesties` na inspeção do assentamento, incluindo
  demanda, estágio, participantes, liderança e duração com link para o receipt
  canônico; a UI não transforma a pressão em comando do jogador.
- Recursos do catálogo agora carregam `trade_class`; a apresentação civil de
  uma carga persiste essa classificação no `CustomsNotice` e no evento de
  apresentação, permitindo ao observador distinguir contrabando de mercadoria
  comum. O proprietário pode escolher `return_contraband_cargo` enquanto a
  rota física e a capacidade do estoque de origem continuam válidas; o owner de
  Economy devolve a quantidade, encerra a ordem como resolvida e preserva a
  evidência. O operador também pode apreender explicitamente a carga detectada
  em estoque local; não há confisco automático, destruição ou rerroteamento.

Continuam deliberadamente abertos: validação operacional do provider remoto
(a sondagem local falha explicitamente quando ele não está configurado), efeitos completos de migração,
políticas de negociação após contrabando e separação patrimonial mais ampla
(a apreensão agora é uma affordance explícita do operador, limitada por
classificação, autoridade e estoque local; o smoke confirmou escassez já no segundo mês; contratos permanentes agora
existem, mas ainda não cobrem toda a economia), difusão geral de tecnologia além
das fatias de venda, roubo, apprenticeship e do efeito limitado de `field_drill`,
memória e objetivos estratégicos gerais, escassez completa, combate e controle
territorial, magia geral, múltiplas criaturas, provider remoto de IA, UI completa
e o smoke final de dez anos.

## Visão que orienta o fork

O projeto deixa de ser um simulador xianxia e passa a ser um mundo medieval de
alta fantasia observado de cima. Personagens, instituições, grupos populacionais,
mercados, pesquisas, magia e criaturas devem agir a partir de capacidades,
necessidades, conhecimento, relações e recursos reais. Conflitos são uma
possibilidade importante de teste, mas não uma obrigação narrativa: cooperação,
comércio, crescimento pacífico e períodos estáveis também são resultados válidos.

Não existe diretor de história. Um dragão, uma torre mágica, uma guilda, uma casa
nobre ou uma vila só altera o mundo por ações implementadas e validadas. A prosa
explica fatos; nunca cria recursos, vitórias, mortes, obrigações ou consequências.

## O que já existe no WIP local

- Runtime medieval separado, configuração persistente e save schema 60 (Society19,
  Economy13, Knowledge8); dados de execução usam namespace próprio e saves antigos são rejeitados,
  preservados sem sobrescrita ou migração.
- Calendário híbrido de 12 meses de 30 dias. Rotinas agregadas usam o salto mensal;
  agendas, prazos, viagem, carga e situações ativas podem exigir processamento por
  dia. Cada salto é transacional e preserva relógio, agenda, eventos e RNG.
- Cenário inicial `Vale das Três Coroas`, com 12 personagens relevantes e população
  em coortes (10.900 pessoas), três cidades e suas instalações/rotas. Isso é uma
  fundação, não o mapa final de todo o escopo proposto.
- Estados com owners separados para sociedade/população, economia, autoridade,
  conhecimento, estratégia, pesquisa e relações. Registros causais distinguem
  decisão, execução material e interpretação.
- Produção, estoques, contas, salários, imposto sobre renda, consumo doméstico,
  ajuda pública, trabalho, transporte de cargas, pedidos de abastecimento,
  compras/remessas e construção financiada.
- Pesquisa inicial, conhecimento institucional, ensino consentido, obras de
  aplicação e linhas produtivas preparadas para carvão, aço, motores e bombeamento.
  Em mundos com provider habilitado, expansões de instalações e aplicação de
  técnicas já conhecidas entram no menu civil como affordances recomputadas;
  construção só nasce depois da escolha do owner e da revalidação material.
  O início automático de pesquisa ainda é uma lacuna separada desta vertical.
- Núcleo de diplomacia: propostas, contrapropostas, aceitação sem transferência,
  obrigações de pagamento/ensino, prazos, expiração, quebra, dispensa e avisos
  privados. Cumprimento material ainda exige uma decisão nova e autorização atual.
  Barganha determinística por contexto de ator registra uma tentativa de
  contraproposta como fato sem delta, com vínculo ao sucessor. `GET
  /api/v2/query/diplomacy` e o DiplomacyPanel do observatório já estão integrados;
  IA real de negociação ainda não está coberta por produção.
- Mercado material possui preços derivados de oferta/demanda, compras bilaterais,
  frete, estoques, tarifas históricas e provisões domésticas. Procurement agora
  também enumera uma compra de mercado para objetivos de abastecimento, sempre
  usando a cotação, rota e quantidade calculadas pelo engine.
- Cada atualização de mercado agora persiste `observed_supply` e
  `observed_demand` por recurso como leituras públicas canônicas, junto dos
  deltas e causas do `market_updated`. Isso permite que decisões de comércio,
  produção e alívio consultem a pressão local real, sem expor inventários
  estrangeiros nem transformar a cotação em comando automático. A leitura é
  preservada no save/load; a resiliência econômica de longo prazo continua
  pendente.
- O contexto público compartilhado das affordances civis agora inclui essas
  leituras locais datadas nas oportunidades de abastecimento/mercado. O
  provider pode comparar pressão, oferta e demanda antes de escolher uma opção;
  estoque, conta, quantidade, fornecedor e rota executável continuam fora do
  prompt e são recompostos pelo owner.
- Espionagem institucional V1 possui missão transitória para agente autorizado
  presente no assentamento, resultado `success`/`failure`/`discovered` e finding
  privado persistido somente quando aponta para observação canônica existente.
- Conhecimento datado de rotas (schema17, `route_reports`): observação
  administrativa por instituição-extremo com mandato de abastecimento (não
  exige estrada aberta), boletim mensal por decisão que entrega um recibo por
  destinatário pela rede física alcançável a partir do publicador, e planejador
  que trata relatório de 30+ dias como desatualizado. Painel de inspeção de
  rota compara o dado datado com a capacidade canônica atual; ver
  medieval-autonomy.md.
- API `/api/v2`, observatório PT-BR e frontend Vue para mapa, cronologia, economia,
  pesquisa, obras, abastecimento, saves e inspeção causal.
- O Map continua dono da integridade/operabilidade das instalações. Economy schema
  13 possui `repair_blueprints`, `repairs` e contratos de emprego permanente:
  reparos continuam sendo uma obrigação de projeto, não um
  comando automático. Cada `repair_batch_decided` revalida materiais locais,
  salários e a força de trabalho mensal compartilhada; restaura no máximo 0,10
  de integridade e não reativa `enabled=false`. O catálogo de reparo só cobre
  `farm`, `mine`, `port`, `workshop`, `forest` e `mountainpass`.
- `SiteReport` é conhecimento privado do proprietário ou mantenedor com presença
  local, armazenado em Knowledge; não é broadcast automático. Portos e passagens
  também têm `service_suspended`, separado de dano físico: só o proprietário com
  mandato de abastecimento, presença e relatório atual pode suspender/retomar o
  próprio serviço. A suspensão reduz a capacidade derivada a zero e faz cargas
  aguardarem; não confisca carga nem representa bloqueio militar ou fiscalização.
- A demanda de reparo já entra no preço local; `market_updated` cita o projeto
  e o `SiteReport` que fundamentam essa demanda.
- Desgaste de infraestrutura já é uma consequência material engine-owned: o Map
  reduz a integridade somente quando há recibo de produção ou de carga real que
  ultrapasse o limiar de uso. A lei é determinística, limitada a 0,01 por ciclo
  de 30 dias, sem clima, evento aleatório ou reparo automático. O relatório do
  mesmo ciclo expõe o dano ao mantenedor, que continua precisando escolher e
  financiar o reparo existente.
- Tarifas de exportação são cotação pública e histórica da jurisdição que administra
  o estoque de origem. `TaxPolicy.export_rate_permille` usa
  `export_policy_event_id` próprio, separado de renda e de `last_event_id`.
  O comprador vê taxa/fato/coletor, nunca saldo estrangeiro; na abertura bilateral
  paga base mais tarifa uma vez, com base ao vendedor e tarifa ao tesouro da origem.
  Não há tarifa doméstica/frete próprio, pedágio, trânsito ou bloqueio.
- Alfândega civil é um posto Economy-owned em porto/passagem: equipe local paga
  no ciclo, autoridade atual de supply/trade/taxation e serviço físico ativo são
  pré-requisitos. Ao ser apresentada, a parcela canônica fica retida e o dono recebe
  aviso privado. Ele só escolhe declarar o manifesto exato ou tentar evadir a taxa;
  o engine resolve detecção com capacidade paga e RNG salvo. Declaração seguida de
  pagamento libera a mesma parcela; evasão não detectada a reagenda para o dia seguinte.
  Não há força militar, confisco, alteração de rota/quantidade/propriedade ou escolha
  de rerroteamento nesta vertical.
- Rotas fiscais são conhecimento datado: o operador ativo observa o checkpoint e
  uma decisão de publicação emite recibos físicos para destinatários alcançáveis.
  A abertura de carga usa opções enumeradas pelo engine, distinguindo rotas legais
  sem posto (taxa zero); relatórios vencidos, IDs inventados e postos divergentes
  são rejeitados. Ordens existentes não são redirecionadas, e a camada não cria
  força, confisco, bloqueio ou rotas secretas.
- Conveyance produtiva V1 permite transferir bilateralmente o controle institucional
  de um workshop já comissionado. As duas decisões são opções transitórias
  enumeradas pelo engine; o executor revalida identidade física do site,
  owner/maintainer, autoridade e vínculos locais de estoque e folha antes de
  alterar o Map e a instalação. Estoques, saldos e projetos não são movidos.
  Não existe ainda `PropertyTitle`, arrendamento, herança, captura de guerra nem
  controle dessa operação na UI.
- Recuperação de frete bloqueado (`freight_recovery.py`): a `FreightOrder`
  original é imutável — rotas, quantidade, decisões e recibos nunca são
  reescritos, reroteados ou reexecutados. `wait`/`successor` são opções
  transitórias enumeradas pelo engine a cada chamada, nunca persistidas; a
  decisão só nomeia o ID da opção. Por ora, só uma transferência interna não
  paga e ainda não entregue é recuperável; uma compra bilateral bloqueada exige
  sua própria decisão bilateral futura e não é rerroteada por este módulo.
  Escolher `successor` retira estoque novo e abre uma ordem própria com
  vínculos causais para a decisão e para a ordem bloqueada, sem restituição
  nem duplo pagamento sobre a original. Não há rotina automática, força ou
  bloqueio militar nesta vertical.
- Recuperação bilateral de compra pré-paga (`purchase_recovery.py`) agora cobre
  a V1 específica de compra já paga, sem tarifa, sem entrega parcial e com o
  frete integralmente bloqueado. O comprador solicita uma rota fiscal alternativa
  por opção transitória; o vendedor aceita ou recusa em decisão independente.
  Ordem, pagamento, recibo e carga originais permanecem imutáveis. Na aceitação,
  a carga original é explicitamente devolvida ao estoque do vendedor e uma ordem
  sucessora usa estoque novo sem novo pagamento; a execução registra deltas e
  causas correspondentes. Não há refund, tarifa, recuperação automática,
  despachante de affordances, UI ou API pública para essa vertical.
- Fornecimento recíproco V1 permite que um settlement com plano alimentar bloqueado
  ofereça uma concessão que realmente possui. O requester compõe a proposta apenas
  de seu relatório, estoque, conta e rotas conhecidas; o counterpart não expõe
  inventário privado. Aceite só vincula duas entregas independentes: alimento
  primeiro e recurso prometido depois, cada uma com decisão atual, freight canônico,
  dependência e breach causal quando não cumprida. Isto não é mercado geral nem
  estratégia ampla.
- Apprenticeship V1 difunde uma técnica por um especialista que migrou de fato e
  reside no settlement anfitrião. O especialista oferece; a instituição anfitriã
  patrocina, paga trabalhadores locais e uma agenda de 30 dias conclui a cópia da
  técnica no catálogo institucional. A origem mantém seu conhecimento; não há
  conhecimento pessoal nem treinamento geral.
- Forças agregadas V1 levantam soldados de coortes reais, descontam rações, pagam
  salário, marcham por rotas operacionais e podem registrar ocupação revogável de
  settlement. Ocupação não concede administração, estoque, conta ou imposto; falta
  de provisão/dissolução limpa a ocupação e devolve sobreviventes à coorte real.
  Comando, doutrina, combate de campo voluntário, abastecimento, interdição,
  desescalada e resposta pós-combate já têm fatias causais; cerco persistente,
  desgaste de guarnição, ocupação pós-brecha e controle territorial explícito
  também existem em V1. Ainda faltam manutenção recorrente ampla e solução
  política.
- Sabotagem V1 é uma ação material engine-owned: presença militar preparada ou
  trabalho local pago, relatório atual do site, ferramentas próprias e autoridade
  válida são pré-requisitos; o dano é limitado, auditável e agora também pode ser
  escolhido no turno institucional mensal. Investigação posterior continua
  separada e não transforma a vertical em espionagem geral.
- Ritos restaurativos V1 são trabalho material delimitado: oficiante residente,
  site capaz, reagentes próprios, assistentes pagos e testemunhas. A conclusão
  reduz saúde registrada dentro do limite do blueprint; interrupção/cancelamento
  perde os reagentes e não cria recursos, pessoas, capacidade ou controle.
- Criaturas agora existem no runtime em uma vertical estreita: as espécies do Rio Lume
  percebe somente cargas que cruzam sua rota, pode pedir tributo, restringir sua
  própria passagem e recuar; instituições recebem aviso e respondem com alimento
  próprio. A decisão por provider V1 escolhe apenas IDs enumerados e registra
  interpretação sem delta; fallback/indisponibilidade não fecha a rota. Não há
  ainda um sistema geral de monstros, ameaças, magia ou territórios múltiplos. Os
  blueprints de rito expõem escola, custo, alcance e duração como leitura derivada,
  sem registrar uma segunda árvore de feitiços. Quando uma exigência vencida é
  ignorada, o drake agora também recebe uma affordance explícita para atacar uma
  coorte anônima real no extremo observado da rota. A perda é limitada pela lei
  engine-owned, não inclui moradores nomeados, expira a demanda e registra
  `creature_attacked_population` com payload de hazard, causa e delta de Society.
  O tributo institucional pode ser entregue em parcelas: cada decisão consome
  alimento próprio e atualiza `food_received`; enquanto houver saldo, a demanda
  permanece aberta e uma affordance posterior oferece apenas quantidades válidas.
  A quitação final marca `satisfied` e `settled_by_ref`; nenhuma parcela cria
  recurso ou fecha a passagem automaticamente.

### Customs-to-workforce

Um checkpoint civil só gera demanda de `merchant` quando está ativo, tem equipe
e folha válidas, esgotou realmente as inspeções pagas do dia e não possui
merchant local plenamente disponível. O `labor_shortfall` é tipado e emitido
pela engine; demand, offer e `target_occupation` não vêm da prosa. Um farmer
local aceita somente os IDs atuais, recebe estipêndio, fica reservado por 30
dias e então vira `merchant`, ligado como `staff_group` para payroll posterior.
Não há educação genérica, população, migração, autoaceite, UI/API ou outras
ocupações.

### Ajuda alimentar institucional

A vertical está preparada para execução direta, mas não constitui autonomia geral
ou Stage 2 concluída. A instituição solicitante usa somente seu próprio
`SettlementReport` atual com `missing_food`; as affordances são objetos transitórios,
enumerados pelo engine e não persistidos. O ID selecionado persiste somente na
decisão, no receipt e na proveniência causal. O pedido gera um aviso privado ao
provedor, e a aceitação ou recusa gera uma resposta privada ao solicitante. O aviso
não leva oferta, inventário estrangeiro ou rota, e a aceitação não altera estoque,
dinheiro ou frete. Uma decisão posterior, atual e de abastecimento do provedor
revalida autoridade, estoque e relatórios fiscais datados de rota, abre o frete
canônico e cumpre a obrigação no despacho; a chegada permanece sob a logística.
Se o despacho falhar, a quebra persiste. A remediação exige decisão posterior do
provedor, aviso privado da quebra e nova validação de autoridade, estoque e rota
atual; abre um novo frete e nunca apaga a quebra original. Não há política
automática, decisão por IA real, mutação pública na UI/API ou divulgação de
inventário estrangeiro. O aviso persistido contém somente `requested_food`, quantidade
engine-owned derivada do relatório causal atual do requester; nunca é um relatório
vivo. O provider avalia-o contra seu próprio stock e relatórios fiscais datados.
No fallback determinístico `routine-rules`, cada polity faz no máximo uma ação por
revisão, na prioridade `respond`, `fulfill`, `remediate`, `request`. Request usa
somente plano alimentar bloqueado, shortfall atual e uma cadeia/settlement aberto;
as demais ações exigem opções atuais válidas. A agenda permite request em N, reply
em N+1 e fulfillment em N+2; isso não é IA real nem Stage 2.

### Memória institucional

`KnowledgeState` continua sendo o owner do conhecimento factual por meio de
`DiplomaticNotice`; `RelationsState` persiste apenas memórias institucionais
ativas com `id`, `institution_ref`, `event_id`, `recorded_day` e
`last_reinforced_day`. Cada memória aponta para o fato canônico de transição e
para o receipt/delta que a criou ou reforçou. Saliência e view são read models
puros, derivados no momento da leitura com decaimento linear em 360 dias. A V1
tem somente a view direcional de ajuda: o credor vê breach como -4 e remediação
como +2. Não há score social genérico persistido, fator de LLM, UI/API, IA real
ou estratégia geral nessa camada.

## Evidência disponível e limites

Há ampla cobertura focada herdada do WIP para economia, agenda, pesquisa,
observatório e persistência. Portanto, não declarar a suíte global verde nem
publicar uma versão como validada.

Recorte atual de integração: execução 78524 aprovou 90 testes em 54,66s para
tarifas, conhecimento, mercados, renda, autonomia, persistência, pagamentos,
rotas e provisões domésticas. É uma rodada focada, não a suíte global nem o
encerramento da etapa 1. As evidências da rodada anterior de migração/retorno
permanecem separadas. A execução 46405, posterior ao cálculo exato do orçamento e
da rotina mensal, aprovou 49 testes de tarifas/mercados/renda/autonomia em 39,66s.
API 75902 aprovou 21 e deselecionou 1 em 9,23s fora do sandbox. Após o guard que
ignora ordens estrangeiras já concluídas, o arquivo de tarifas foi reexecutado:
9 aprovados em 5,88s (13862), incluindo retirada da tarifa por entrega pendente
e ausência dessa retirada quando o pedido já foi entregue. Não somar os recortes.

Frontend final: execução 42384 aprovou 46 testes em 4,18s e o build levou 4,87s,
com o aviso Pixi conhecido. No browser, fixture de política registrou 151 ->
buy206/sell207/order208/payment209: base 400, tarifa 20, Auren 20.000 -> 20.420 e
comprador 20.000 -> 19.580. Desktop 1440 e mobile 390 foram capturados; no mobile,
clientWidth=scrollWidth=375 com scrollbar de 15px e inspector de 343px permaneceram
legíveis. O único erro anotado na primeira abertura foi favicon 404.

Smoke natural histórico: execução 38769, seed73 dias 180/181, levou 55,11s, com 130 saltos,
47 ordens, 5.208/5.233 eventos e 76.000 moedas; conservação e save/load foram
verdadeiros, com zero IA real. A auditoria desse save encontrou zero causas quebradas,
zero deltas de interpretação e zero causas materiais de interpretação. Zero eventos
de exportação e tarifas zero nesse mundo natural são válidos; fixture preparada não
é evidência de comportamento natural. O smoke 38293 para
`/tmp/cws-medieval-tariffs-final-20260913.mws` concluiu em 54,09s com os mesmos
resultados. Sua auditoria confirmou schema15, 5.208 eventos e zero causas quebradas,
deltas de interpretação ou mutações causadas por interpretação. Não houve tarifa
natural nem IA real; isso não prova o aceite de três seeds por dez anos.

Histórico (superado): a execução anterior da suíte específica de diplomacia
havia retornado 21 aprovados e 2 falhas — quebra esperada no dia 101 vs.
cumprimento no dia 96, e uma fixture que alterava diretamente o campo imutável
`capability_ids`. As duas falhas foram corrigidas nas próprias **fixtures**, não
no motor: o mandato passou a expirar no dia 91 para forçar um cenário de quebra
genuína (em vez de um cumprimento antecipado disfarçado de quebra), e a
identidade imutável passou a ser substituída via `dataclasses.replace` em vez de
mutação direta de `capability_ids`.

Correção adicional e independente: `_purchase_terms`/`queue_freight` (markets e
logistics) passaram a exigir que a decisão de compra/venda/frete seja do dia
corrente, distinto do `quote_day`/`updated_day` do mercado — isto resolve uma
classe de problema de consentimento datado, mas **não foi a causa** dos 23
testes de diplomacia passarem; são correções separadas em módulos separados.

Mesma classe de correção, aplicada agora em `transfer_money` (pagamento avulso,
Opus): decisão também passou a exigir dia corrente, distinto de qualquer campo
de cotação/prazo do pagamento. Teste dedicado cobre save/load preservando
conservação de saldo e proveniência causal do pagamento. Regressão posterior
relevante — `tests/test_medieval_payments.py`, `test_medieval_diplomacy.py`,
`test_medieval_diplomacy_policy.py` e `test_medieval_economy.py` — passou: 45
aprovados em 6.89s. O teste anual histórico (1 aprovado em 424,40s) foi executado
antes dos guards de pagamento/reparo e não foi reexecutado nesta rodada.

## Evidência de execução

Os números abaixo são recortes do WIP local (HEAD 85fe9717), separados por rodada.
Não somar os recortes nem tratá-los como suíte global. Primeiro, o histórico anterior
à integração final da migração (save13):

- Infraestrutura: 18 aprovados em 33,04s (execução 36986); o recorte anterior
  de 14 aprovados/2 falhas foi resolvido.
- Regressão economia/expansão/income/persistência/história/rotas: 89 aprovados
  em 17,56s (execução 91740).
- API/observatório: 21 aprovados e 1 deselecionado em 6,40s (execução 43488); a
  projeção atual exige `migrations`, `migration_provisions` e `settlement_reports`.
- Frontend após o ajuste de materiais: 39 aprovados em 3,70s; build em 4,59s
  (execução 93214; aviso de chunk Pixi mantido).
- Mercado: 13 aprovados em 6,28s no recorte executado pelo agente; o teste
  consolidado principal foi concluído abaixo.
- Consolidado principal (infra/markets/logistics/autonomy/inputs): 68 aprovados
  em 52,89s (execução 47209); infraestrutura agora inclui a verificação de
  autoridade após o início do reparo e preserva `enabled=false`.
- Smoke natural posterior à integração de mercados: seed73/180 dias em 38,08s
  (execução 93139; arquivo `/tmp/cws-medieval-market-repair-final-20260913.mws`),
  4.904 eventos no dia180 e 4.929 no dia181, 47 pedidos, 130 saltos, 76.000
  moedas, conservação/save-load verdadeiros e `real_ai_calls=0`.
- Fixture positiva de manutenção: Docas passou de 40% para 50%, consumiu 6
  madeira, 3 pedra e 1 ferramenta, pagou 12 moedas em salários e registrou
  `SiteReport` de 40%. No desktop, a causalidade foi confirmada: evento 220
  (integridade 40%→50%) com causas 1 (dano), 11 (projeto), 219 (decisão) e 82
  (observação), seguido por evento 221 com 12 moedas em salários.
- Verificação visual final em desktop 1440px e mobile 390px após o build:
  materiais separados, custos legíveis, `clientWidth == scrollWidth == 390`,
  painel de 358px e console do reload final com 0 erros/avisos. Mensagens de
  favicon, WebGL e reinício transitório pertencem a execuções anteriores.

Rodada de migração (save14/Society2/Economy8):

- Migração, provisões, conhecimento, consumo, persistência, sociedade e logística:
  89 aprovados em 31,64s (execução 65431). Arquivo de migração reexecutado após
  acrescentar rollback na chegada: 9 aprovados em 7,39s (48328).
- Regressão de infraestrutura e mercados: 33 aprovados em 65,72s (65166).
- API/observatório: 21 aprovados, 1 deselecionado, em 9,20s (77806), fora do
  sandbox. Dentro dele a resposta de arquivo estático ficou aguardando; o processo
  foi encerrado e essa execução não foi declarada verde. O teste anual não rodou.
- Frontend: 43 aprovados em 5,19s; type-check/build em 5,54s (18088). O aviso
  existente de chunk Pixi permanece.
- Smoke natural seed73/180 dias (51234): 55,15s, 130 saltos, 47 pedidos, 5.208
  eventos no save e 5.233 após continuar até o dia181; conservação de recursos e
  76.000 moedas, save/load e continuação equivalentes. Zero migrações e zero compras
  de provisão nessa seed são resultados válidos; os cenários preparados provam essas
  possibilidades. Auditoria do save: zero links causais ausentes e zero mutações
  por interpretação. Zero chamadas de IA real, não é o aceite de três seeds/dez anos.
- Navegador real com fixture isolada: jornada de 79 pessoas, 2.400 residentes e
  2.321 presentes em Pedraclara, alimento/saldo por donos canônicos, decisão com
  fontes de rota e povoados navegáveis. Desktop1440/mobile390 legíveis, sem overflow
  horizontal (390/390). O reload aceitou o contrato final incluindo consumo e retorno;
  o caso visual é de ida, e o retorno é coberto por teste de componente/material.

Histórico anterior de `RouteReport` usava schema 12; isso descreve a rodada
histórica, não o schema 15 atual. As contagens antigas não devem ser misturadas
com os resultados acima.

A estabilização inicial está verificada apenas nos recortes testados acima; isso
não encerra o roadmap nem constitui aprovação global. O WIP continua local e não
publicado.

Evidência atual da vertical de ajuda (histórica, schema28): o recorte focado aprovou 33 testes de
política/ajuda/memória/customs em 16,51s. O smoke natural de 120 dias (seed 73)
salvou schema 28 com 2.867 eventos, 32
`orders` e 76.000 moedas; alimentos e recursos foram conservados e a continuação
após save/load foi equivalente. Não houve eventos de ajuda nem chamadas de IA real
nesse mundo estável — ambos são resultados válidos, não uma exigência de drama.

Validação recente dos slices novos: o recorte
`tests/test_medieval_reciprocal_supply.py tests/test_medieval_apprenticeship.py
tests/test_medieval_force.py tests/test_medieval_rites.py
tests/test_medieval_creatures.py tests/test_medieval_creature_autonomy.py
tests/test_medieval_ai_decision.py` aprovou 16 testes em 12,16s. Isso cobre os
contratos focados, inclusive decisão por provider com fallback e save/load do
drake; não é suíte global, smoke natural ou prova de provider remoto/deploy.

**Etapa1 do roadmap está PARCIAL.** O que já existe (fundação, informação
datada, abastecimento/logística/mercados, diplomacia determinística, conhecimento
de rotas, migração temporal/provisão, obrigação material de reparo, desgaste por
uso, conveyance produtiva bilateral, fornecimento recíproco, apprenticeship,
forças/destacamentos, rito restaurativo, criatura do Rio Lume e decisão por provider
V1)
está coberto pelos recortes de teste acima. O overflow regional sazonal já existe
como vertical limitada: Map-owned, baseada em água/elevação, exige duas avaliações
altas consecutivas, danifica no máximo um site aquático por ocorrência, e reports
observam no mesmo ciclo; o Dao expõe a ocorrência sem ensinar clima aos atores.
Ainda faltam, explicitamente: outros hazards naturais e clima geral,
mobilidade/treinamento geral de força de trabalho (a primeira transição farmer→artisan agregada já existe, mas as vilas continuam farmer, então
o trabalho artesanal pode bloquear), genealogia profunda e difusão de conhecimento
por migração,
  pedágios/trânsito/bloqueios/contrabando e qualquer integração de IA real.
Etapa1 não deve ser lida como encerrada.

## Lacunas explícitas

- O motor possui decisão por provider via affordances, mas ainda falta validar um
  provider real no mundo completo atual. A política `routine-rules` continua como
  fallback explícito; não equivale a autonomia inteligente. O observatório e a
  API agora permitem opt-in somente com provider disponível e mundo pausado; a
  configuração completa enviada na criação é aplicada ao mundo canônico, fica no
  autosave e pode ser desligada do mesmo modo. Retomar um save com IA ligada
  também revalida disponibilidade do provider; se ele sumiu, o mundo permanece
  pausado. Esses checks usam provider mockado nos testes; nenhum provider real
  foi chamado aqui.
- Objetivos e planos estratégicos, informação privada, espionagem, suborno,
  sabotagem, persuasão V1 e repudiation deliberada já têm fatias causais; ainda
  não compõem uma vertical completa de estratégia social, descoberta e traição.
  Uma recusa deliberada de ajuda já cria memória negativa apenas no solicitante,
  com leitura direcional engine-owned limitada e notice canônico; isso ainda é
  uma memória social estreita, não uma reputação geral.
  O orçamento diplomático reserva uma folha corrente antes de permitir
  contrapropostas, evitando que capacidade produtiva authored consuma toda a
  affordance de negociação; o owner ainda revalida o saldo no pagamento.
- Não há campanha territorial completa: manutenção ampla, resolução de
  guarnições fora do cerco e acordo político posterior continuam pendentes. Uma
  concessão administrativa bilateral já permanece enumerável depois da
  ocupação pós-brecha, mas só muda o administrador após cumprimento explícito.
  Já existem contingentes, reconhecimento, comando, suprimento, posições,
  táticas, cerco persistente e ocupação pós-brecha em recortes V1; a regressão
  conjunta confirma essa affordance pós-ocupação sem transformar presença em
  administração.
- Magia ainda não é um sistema geral, mas ritos materiais de restauração,
  proteção, alcance, custo, duração e duas contramedidas engine-owned já existem;
  escolas amplas, detecção geral e efeitos ofensivos continuam pendentes.
- Um `river_drake` e uma `river_serpent` do Rio Lume, demandas, tributo parcial,
  restrição, dano de instalação e ataque limitado a população já existem nesta
  vertical estreita; metabolismo mensal por espécie agora é um fato determinístico
  que pode abrir uma revisão futura sem escolher ação; faltam ecologia geral,
  ameaças dinâmicas e criaturas com territórios/necessidades mais diversos.
- Demografia profunda, herança, famílias individualizadas e patrimônio além de
  dinheiro/provisões, pedágios, trânsito, bloqueios, contrabando e
  calibração econômica de longo prazo continuam abertos. Preços locais já existem
  no fluxo mensal limitado de `markets.py`; isso não equivale a um
  mercado local completo.
- O executor de reparo material existe apenas para os kinds catalogados; o desgaste
  por uso já existe, mas não há dano natural/climático que o acione nem reativação
  automática de instalações interditadas. Conveyance existe somente para workshops
  já comissionados e não é ainda um sistema geral de propriedade.
- O observatório ainda não mostra campanha, criatura, estratégia geral ou todas as
  cadeias de informação. Testes de backend não substituem inspeção visual e mundos
  naturais de longa duração.

Validação incremental de 18/09/2026: a rotação de consultas institucionais foi
corrigida para preservar polities sob orçamento finito; a cópia tecnológica
integrada voltou a concluir com o provider stub; alfândega passou a compor o
turno mensal e uma decisão de declaração foi executada por affordance. Os
recortes `customs`, `technique_copy`, `institutional_agenda` e `strategy_response`
passaram (27 testes); `compileall` e `git diff --check` também passaram. Isso é
evidência focada, não conclusão do roadmap.

Validação adicional de 19/09/2026: recuperação de frete, reenvio bilateral de
compra e transição de força de trabalho agora compartilham o menu civil; o recorte
de mobilidade passou com 20 contratos criados e 28 folhas liquidadas. Expansões de
instalações também deixaram de iniciar automaticamente quando `ai_enabled=True`:
  uma instalação ociosa só aparece como `ExpansionOption` financiável e o owner
  recompõe o ID antes de abrir o projeto. O teste focado de revalidação e a regressão
  de expansão/recuperação passaram em 32 testes; a regressão de pesquisa ainda tem
  uma expectativa histórica de dois projetos que falha no estado WIP atual e não foi
  mascarada. A autorização de pesquisa também passou a ser `ResearchOption` no
  mesmo menu civil quando `ai_enabled=True`; o owner escolhe site/tecnologia e o
  executor recompõe pesquisador, conta, estoque, pré-requisitos e orçamento antes
  de registrar o consentimento e iniciar o projeto. O recorte civil atualizado
  passou em 17 testes. O início de cerco agora também é registrado como
  affordance no turno mensal quando coluna, investimento, abastecimento e
  guarnição rival estão presentes; a execução continua no owner de Society e não
  transfere ocupação automaticamente. A regressão de campanha + menu passou em
  24 testes. Instituições não-polity com office reconhecido também entram no
  conjunto de atores mensais quando possuem pesquisa ou expansão materialmente
  disponíveis. A workforce agora também recompõe retorno ocupacional: quando uma
  facility `harvest` prova falta de trabalhadores, uma coorte artisan disponível
  pode aceitar uma transição paga para farmer; a validação de Society/Knowledge
  foi ampliada para esse alvo. O shortfall agrícola pode pedir o lote bounded
  pelo receipt, enquanto as outras ocupações continuam em ofertas unitárias; a
  regressão workforce/engine passou em 33 testes. A rotação mensal prioriza
  grupos populacionais com uma affordance vigente antes de offices sem opção
  material; o smoke `mobilidade/73` de 120 dias registrou 9 transições iniciadas,
  7 concluídas, conservação de dinheiro/recursos e save/load equivalente. A
  escassez caiu apenas marginalmente, então resiliência econômica continua aberta.
  Emprego permanente também revalida a compatibilidade entre a ocupação da
  coorte e as facilities authored no site; um vínculo não nasce apenas porque o
  empregador possui um local próximo.
  O perfil `socorro` do smoke também escolhe objetivos de abastecimento quando
  existe uma opção de ordem material; em 120 dias registrou 9 pedidos, 6
  cumprimentos e conservação de dinheiro/recursos, mas a oferta local continuou
  insuficiente nos assentamentos de artisans.

Validação adicional de 19/09/2026: o contrato do turno institucional foi
uniformizado nas verticais de pesquisa, expansão, abastecimento, alfândega,
socorro, workforce e recuperação de frete/compra. A decisão persistida do ator
agora contém somente ação, referência do ator e `selected_affordance_id`;
technology, site, conta, estoque, rota, quantidade e notice são recompostos pelo
owner. Quando uma validação histórica precisa dos termos materiais, o owner cria
um receipt de autorização separado, causalmente ligado à decisão. A regressão
conjunta passou em 95 testes; `compileall` e `git diff --check` passaram. O gate
natural de 120 dias da seed 73 também terminou com conservação, save/load
equivalente, `broken_cause_ids=[]` e nenhuma Story material. Isso melhora a
autoria causal, mas não fecha provider remoto, economia resiliente ou o gate de
  dez anos.

O fallback determinístico de provisões domésticas também foi delimitado:
`review_household_provisions` não compra por trás dos grupos quando
`ai_enabled=True`; nesse modo, a compra precisa voltar por uma affordance e por
decisões bilaterais. Em mundos offline/test mode a política conservadora antiga
continua disponível. A regressão de household provisioning, engine e menu passou
em 33 testes.

Serviço de porto/passagem também passou a respeitar a mesma fronteira: com
`ai_enabled=True`, suspensão ou retomada não ocorre por limiar automático; o
proprietário recebe uma affordance atual e o owner de Map revalida a observação
antes de alterar a capacidade da rota. O fallback permanece apenas no modo
determinístico. Regressão de serviço, agenda e engine: 17 testes.

A política de tarifa de exportação também foi ligada ao turno institucional:
com provider consultável, a administração escolhe uma taxa enumerada e o owner
recompõe o relatório fiscal antes de aplicar; sem provider, o fallback fiscal
conservador continua disponível. A expectativa histórica de caixa insuficiente
do teste de tarifa permanece falha do WIP atual e não foi mascarada.

Em 19/09/2026, o modo offline/teste ganhou um fallback conservador para
emprego permanente. Quando não há provider real consultável, cada instituição
pode escolher no máximo uma affordance de vínculo para uma coorte cujo relatório
público atual mostre fome, saúde baixa ou descontentamento. A escolha permanece
um decision event por ID; o owner recompõe e revalida site, autoridade, coorte,
estoque e saldo antes de criar o contrato, e o payroll mensal continua sendo a
única fonte de renda. A regressão focada de emprego passou em 9 testes e a de
engine/transação/renda em 33. Isso é uma recuperação de test mode, não uma
afirmação de resiliência econômica geral nem de provider remoto validado.

Na mesma data, uma chegada migratória bloqueada por falta de moradia passou a
registrar pressão social limitada no destino, proporcional à fração de pessoas
impedidas e com delta de `subsistence.unrest` no receipt
`migration_arrival_blocked`. O efeito não cria tumulto nem força retorno ou
reroute; a política ignora esse próprio delta como motivo isolado no mesmo
turno. Migração, conhecimento e engine passaram em 26 testes focados. Isso
fecha uma parte da cadeia migração → descontentamento, mas não a resiliência
econômica de longo prazo.

### Retirada voluntária de cerco — 19/09/2026

Uma campanha de cerco ativa agora recompõe `SiegeWithdrawalOption` usando os
acessos que a própria coluna investiu e uma settlement report atual do destino
administrado pelo atacante. A decisão é somente o `selected_affordance_id`.
O owner de Society encerra as interdições do investimento, registra o fim de
qualquer aviso de suprimento pendente sem mover carga, e chama o owner de força
para iniciar a retirada datada por rota material. O campaign passa a
`phase=withdrawn`; ocupação e administração não mudam. Carga já despachada
continua impedindo a retirada até ser resolvida pelo owner de logística.

Regressão focada: `tests/test_medieval_siege_campaign.py` passou em 9 testes;
integração de campanha, suprimento, força, comando, menu civil e observatório
passou em 47 testes. Isso fecha somente a retirada unilateral de uma campanha;
cessar-fogo bilateral e solução política ampla continuam pendentes.

### Cessar-fogo bilateral de campanha — 19/09/2026

O cerco ativo agora pode abrir um `DiplomaticProposal` de
`proposal_kind=campaign_ceasefire` usando `CampaignWithdrawalClause`, sem criar
um catálogo de termos paralelo. A affordance pode propor retirada própria ou
retirada mútua; a contraparte recebe uma resposta independente e a aceitação
cria uma obrigação por coluna. Cada owner recompõe a rota atual antes de
cumprir: o atacante usa o executor de retirada do cerco, enquanto o defensor
encerra sua duty de guarnição e inicia sua própria marcha. Recusar, ficar sem
rota ou deixar o prazo passar não transfere ocupação/administração e não move
carga por promessa.

O contrato, a validação de cláusulas, save/load e o menu civil compartilham o
fluxo existente de proposals/obligations. A regressão de campanha passou em 10
testes; a integração de campanha, diplomacia, desescalada, concessão,
observatório e menu passou em 62 testes. Isso fecha um cessar-fogo bilateral
estreito para cerco; tratados gerais, guerra prolongada e política pós-guerra
mais ampla continuam pendentes.

### Relief no menu institucional — 19/09/2026

`relief_adapters()` agora participa do menu civil composto. Quando a escassez
é observada pelo próprio proprietário do estoque, a autoridade de `supply` é
válida e há comida física, `relief-distribute:*` aparece como affordance junto
às demais decisões; a distribuição continua explícita e revalidada pelo owner.
Os testes focados de menu/relief passaram, e o perfil de harness `alivio` foi
adicionado para comparar políticas: na seed 73 por 120 dias ele executou nove
distribuições materiais, conservou recursos e preservou save/load. O resultado
não fecha resiliência: a ajuda consome estoque público e a comparação terminou
com escassez agregada ligeiramente maior, mostrando um trade-off real que ainda
precisa de alternativas de oferta e política econômica mais ampla.

O release gate aceita `--economic` para executar a comparação na mesma seed e
emitir `relief_selected`, `different_material_outcome` e conservação como
campos auditáveis. Seus logs de progresso vão para `stderr`, portanto o
relatório em `stdout` é JSON consumível por automação.

### Ofertas de mercado no turno institucional — 19/09/2026

Ofertas bilaterais já observadas agora entram no mesmo menu civil que o plano
de abastecimento, ajuda e recuperação de frete. A instituição pode selecionar
somente o `market-purchase:*` enumerado; o owner de Economy recompõe a oferta,
rota, tarifa, saldo e autoridade, registra a resposta independente do vendedor
e só então abre a remessa física. A decisão não carrega fornecedor, quantidade
ou rota inventados. A correção também substituiu o ID do relatório de oferta
(que não é um evento) pelas evidências canônicas do relatório e das rotas nos
causal links da compra.

O teste focado do menu/mercado passou junto com a regressão civil (18 testes
no arquivo de decisões compostas; 31 incluindo recuperação e relief). A
resiliência econômica de longo prazo continua pendente: esta mudança torna a
alternativa selecionável, mas não garante que a política escolhida seja boa.

### Provisão domiciliar com decisão bilateral — 19/09/2026

Quando o provider está disponível, uma coorte sob pressão e com destino
conhecido recebe affordances `household-provision:*` para ofertas públicas
locais atuais. A compra selecionada não move alimento: ela registra a intenção
da coorte. No turno posterior, o proprietário da oferta recebe opções separadas
de aceitar ou recusar; somente o aceite recompõe preço, reserva, saldo,
capacidade da despensa e autoridade e chama o executor bilateral existente.
Assim, a provisão não é um subsídio automático nem uma decisão do vendedor
tomada pela coorte. O fallback antigo permanece apenas no modo offline sem
provider.

A regressão de household provisioning passou em 11 testes; agenda, engine e
migração passaram em 24. Isso fecha a entrada de provisão domiciliar no fluxo
de decisão, mas ainda não prova resiliência econômica de longo prazo.

### Dossier estratégico no turno institucional comum — 19/09/2026

O `actor_dossier` agora expõe, além das memórias ativas, as leituras
institucionais direcionais que o ator realmente conhece e a capacidade
estratégica derivada dos registros persistentes. A projeção é somente leitura:
`KnowledgeState` continua delimitando os fatos visíveis, e `StrategyState`
continua sendo o owner da capacidade. Isso permite que qualquer adapter do
menu composto considere memória e capacidade sem criar um planner paralelo.

A regressão focada de dossier, turno institucional e diplomacia passou em 29
testes. Provider remoto e o gate de longa duração continuam pendentes.

### Ocupação e controle no menu de campanha — 19/09/2026

As affordances de ocupar após uma brecha e de estabelecer/retirar controle
territorial agora compõem o mesmo turno institucional mensal que inicia ou
retira o cerco. Elas continuam usando os owners de `SiegeCampaign` e
`TerritorialControl`: a brecha não ocupa sozinha, o controle exige guarnição
paga e abastecida, e nenhuma dessas escolhas altera a administração do
assentamento. A concessão administrativa também entra nesse menu como oferta,
resposta e cumprimento independentes. A regressão de campanha, menu e agenda
passou em 38 testes.

### Ecologia por capacidade operacional — 19/09/2026

O tick mensal das criaturas agora lê a capacidade operacional derivada de cada
rota authored, não apenas o booleano `enabled`. Uma perda de qualidade da rota
ou uma instalação dependente danificada recompõe estresse de habitat limitado,
aponta para o fato de degradação e expõe `impaired_route_ids` no payload
estruturado. O baseline é o valor authored ou o `before` do último fato de
qualidade, portanto uma qualidade inicial de 0,9 não é tratada como dano novo.
Nenhuma demanda, ataque ou fechamento é criado pelo tick. A regressão focada
de criatura/magia passou em 8 testes.

### Observabilidade de estresse de habitat — 19/09/2026

O `CampaignView` agora projeta uma ameaça `creature_habitat_stress` quando o
último tick canônico de uma criatura aponta rotas com capacidade operacional
prejudicada. A ameaça carrega a rota, severidade limitada e o próprio evento
ecológico como fonte; a leitura não cria conhecimento nem altera o mapa. O
Atlas recebe a tradução PT-BR do novo tipo, e a regressão backend/frontend
passou em 19 e 65 testes, respectivamente.

### Leituras públicas de oferta e demanda local — 19/09/2026

`Market` passou a carregar a última oferta e demanda observadas para todo o
catálogo local. O owner de Economy calcula esses valores a partir de estoques,
população, instalações, obras, pesquisa e reparos; o evento `market_updated`
registra os mapas como `StateDelta`, mantendo a cadeia causal que explica a
cotação. A leitura é limitada ao assentamento e não substitui conhecimento
privado de inventários estrangeiros. A regressão focada de mercados passou em
14 testes. O smoke preparado de comércio agora explicita, por uma decisão de
pagamento auditada, o reforço do tesouro comprador antes da remessa; a cadeia
de bloqueio e recuperação passou, conservando dinheiro, comida e save/load.

Na mesma vertical, o contexto de decisão civil passou a entregar a leitura
pública correspondente junto de cada oportunidade de abastecimento. A
regressão do menu civil passou em 21 testes; isso melhora a agência da escolha,
mas não fecha a resiliência econômica nem cria um planner automático.

O Inspector do observatório também exibe, por assentamento, oferta e demanda
observadas, preço e dia da leitura. A API continua entregando o objeto `Market`
canônico, e a verificação frontend passou em type-check e 65 testes.

### Gate comparativo de 120 dias — 19/09/2026

O `medieval_release_gate.py` passou com as seeds naturais 73, 101 e 137, além
da fixture pressionada `socorro` e da comparação econômica na seed 73. Todas as
execuções conservaram dinheiro/recursos, foram equivalentes em save/load e
terminaram com `broken_cause_ids=[]` e nenhum Story material. A fixture
pressionada registrou 9 pedidos e 6 cumprimentos de ajuda. O resultado também
confirma a pendência da economia resiliente: os cenários continuam com déficit
alimentar e pressão social material no dia 120, apesar de emprego, mercado,
ajuda e mobilidade. O gate de três seeds por dez anos continua não executado.

## Handoff Git

A branch real desta execução é `codex/medieval-remote`, com WIP
local não commitado além desse ponto. Não há autorização de commit, push ou
deploy nesta preparação. O remote `github-personal` é o GitHub pessoal do
usuário; `origin` aponta para a VPS e não deve ser confundido com o destino de
publicação. Nenhuma alteração deve ser enviada à `main`, mesclada ou publicada
como release por este handoff. Arquivos de cache, `web/dist-medieval` e
`.test-data` não pertencem ao commit.
## Gate comparativo pós-reativação — 19/09/2026

O `tools/medieval_release_gate.py` concluiu a matriz de 120 dias da seed `73`
com três linhas de referência (`natural`, `pressured/socorro`) e quatro
políticas econômicas (`desatento`, `alivio`, `mercado`, `mobilidade`). Os seis
artefatos `.mws` foram escritos em `/tmp/cws-reactivation-gate`; cada execução
preservou conservação de dinheiro/recursos, continuidade de save/load e
auditoria causal limpa. A matriz exercitou alívio, mobilidade e a cadeia de
ajuda, mas a economia ainda terminou pressionada: `missing_food` variou de
5948 a 6276 e a saúde média de 877,88 a 883,25. Isso é evidência de caminhos
materiais distintos, não de equilíbrio ou resiliência econômica de longo prazo.
O provider remoto e o gate natural de três seeds por dez anos continuam
pendentes.

### Continuação causal — 21/09/2026

O owner de cessar-fogo de campanha agora aceita iniciativa de qualquer
participante atual do cerco. A affordance só aparece quando o próprio
destacamento possui uma rota de retirada conhecida e abastecida; a proposta
usa o destacamento do proponente e o da contraparte como termos separados,
sem mover tropas no aceite. A regressão específica de cessar-fogo passou em
4 testes e a regressão conjunta de cerco, abastecimento e concessão em 25.

`tools/medieval_causal_audit.py` também passou a reportar explicitamente
transições `ACTOR_DECISION` sem decisão-fonte e materialidade de interpretações
LLM. O save natural auditado nesta rodada ficou `ok=true`, com ambas as listas
vazias. Isso amplia a prova de autoria, mas não fecha campanha persistente,
provider real ou os gates naturais de dez anos.

Na continuação da mesma rodada, foi adicionada a fixture pressionada
`recuperacao`. Ela não introduz uma política no motor: apenas seleciona, em
ordem estável, affordances que o próprio estado enumerou para ajuda,
suprimento, mercado, emprego e transição de workforce. Em 120 dias, a fixture
registrou 9 pedidos e 6 cumprimentos de ajuda, 13 decisões de emprego e 19
transições de workforce, conservando dinheiro e recursos. O save passou no
auditor causal (`ok=true`, sem causas quebradas, decisões sem fonte ou
interpretações materiais). A pressão alimentar nos assentamentos artesanais
continua visível; isso é precisamente a pendência de resiliência econômica,
não uma razão para adicionar fallback roteirizado.

O observatório do Dao também passou a projetar propostas vivas de
`campaign_ceasefire` junto das demais soluções políticas de campanha. O
assentamento é resolvido a partir da campanha canônica referenciada pelos
termos, e uma proposta mútua mantém visíveis os dois compromissos de retirada;
nenhum deles executa movimentação por si só. A regressão de projeção passou em
5 testes.

O contrato web PT-BR foi atualizado para aceitar essa nova categoria de solução
política; o type-check e os 66 testes medievais do frontend passaram. A leitura
continua somente observacional: aceitar um acordo ainda exige as decisões e
retiradas materiais dos proprietários.

Os tipos públicos e a tela de diplomacia também reconhecem termos de retirada,
retirada de campanha e transferência administrativa. Eles não são mais
renderizados como termos de ensino; a regressão específica passou em 6 testes
com type-check verde.

### Reparação de entregas negociadas — 21/09/2026

Compromissos `resource_transfer` fora da vertical específica de ajuda agora
também têm uma affordance transitória de reparação. Depois de um breach
notificado, o devedor pode decidir novamente; o owner recompõe estoque próprio,
rota fiscal conhecida, autoridade e disponibilidade atuais, abre uma nova
remessa pelo owner de logística e marca somente a obrigação atual como
`remediated`. O breach original, seu evento e sua memória continuam intactos.
O caminho foi incluído no menu civil institucional comum e validado junto com
as regressões de reciprocal supply, ajuda, diplomacia, repudiation e
renegotiation: 56 testes passaram. Isso fecha uma lacuna de commitments, mas
não encerra a resiliência econômica ou as demais ondas amplas.

### Leitura de demanda publicada após custos derivados — 21/09/2026

O owner de `Market` agora congela `observed_demand` somente depois de acumular
demanda de produção, construção, pesquisa e reparos — a mesma leitura
engine-owned usada para calcular a cotação. Antes, a cotação já reagia a
reparos e projetos, mas o relatório público entregue ao ator omitia esses
componentes, deixando a affordance com contexto material incompleto. A correção
não altera estoque, preço ou política automaticamente; apenas torna a evidência
publicada coerente com a causa do preço. A regressão de mercados, menu civil e
smoke de autonomia passou em 46 testes.

### Migração não usa fallback em modo IA — 21/09/2026

O tick datado do engine deixou de chamar `review_migration` quando
`ai_enabled=true`. Migração e recuperação já estão registradas no turno
institucional mensal dos próprios grupos populacionais, portanto a chamada
datada duplicava o owner e podia mover uma coorte por política determinística
fora da decisão do ator. O fallback continua disponível somente no modo
offline/teste explícito; no modo IA a opção precisa passar pelo menu e pela
revalidação do owner.

### Execução da migração escolhida pela IA — 21/09/2026

A autorização material criada pelo adapter de migração passou a carregar o
`option_id` canônico e todos os eventos dos relatórios de assentamento e rota
que sustentam a affordance. Isso permite ao owner `start_migration` recompor a
opção atual, rejeitar alterações reais e, quando ela permanece válida, executar
a jornada com provisão, custos e deltas de população. A regressão de mobilidade
e agenda passou em 29 testes; a onda de resiliência econômica continua aberta.

### Orçamento do smoke autônomo — 21/09/2026

O harness autônomo passou a usar por padrão 256 consultas por boundary, o
mesmo teto configurado pelo engine para a agenda institucional composta. O
padrão anterior era menor que o número de atores/fases consultáveis e podia
interromper um smoke por `ProviderDecisionRequired` antes de completar as
decisões, sem representar uma falha do mundo. O smoke de 30 dias concluiu com
conservação de dinheiro/recursos e save/load equivalente. Isso não resolve o
déficit material observado nos assentamentos pressionados; ele continua sendo
o próximo recorte da onda de economia resiliente.

### Acessibilidade alimentar publicada — 21/09/2026

O recibo `subsistence_resolved` passou a publicar `unaffordable_by_group`: a
quantidade de ração que cada grupo não conseguiu comprar com sua cota e saldo
atuais. Isso distingue estoque público de alimento efetivamente acessível e
explica o déficit observado no smoke sem criar comida, subsídio ou decisão
automática. A regressão de consumo, economia, workforce e smoke passou em 75
testes; ainda falta a cadeia institucional que escolha uma resposta material
suficiente para eliminar a pressão.

### Revalidação de criaturas, tecnologia e campanha — 21/09/2026

Os harnesses compostos dessas verticais foram alinhados ao contrato atual de
provider: cenários que consultam a agenda expandida usam orçamento explícito,
enquanto o caso de provider quebrado espera `ProviderDecisionRequired` e
rollback, sem publicar uma falha determinística como se fosse decisão do ator.
Criaturas, ritos, técnica, intriga estreita, campanha e abastecimento passaram
em 83 testes focados. Isso é evidência dos slices existentes, não conclusão
das ondas amplas.

### Folha recorrente e rotação de produção — 21/09/2026

O owner de emprego permanente agora recompõe o custo mensal dos contratos já
aceitos por conta de payroll antes de enumerar um novo vínculo. Uma instituição
não recebe uma affordance recorrente se a própria conta não cobre as obrigações
existentes e o primeiro pagamento do candidato; isso não cria crédito, cancela
contratos ou presume receita futura. A regressão de economia, renda e emprego
passou em 49 testes.

Além disso, `produce_monthly` agrupa as linhas pelo account de payroll e gira a
ordem de execução de forma determinística a cada mês. O caixa compartilhado não
é mais consumido permanentemente pela primeira linha em ordem alfabética. Cada
linha continua usando seus limites de trabalhadores, estoque, capacidade,
autoridade e saldo, e os salários continuam sendo pagos pelo owner.

O smoke pressionado de 360 dias (`seed=73`, `recuperacao`) terminou com falta
agregada `2174` (antes `2208`), saúde média `799.5`, unrest médio `200.5`,
conservação de dinheiro/recursos e save/load equivalentes. A auditoria causal
retornou `ok=true`, com `10369` eventos, zero causas quebradas, decisões sem
fonte ou materialidade de Story/LLM. A melhora é parcial: renda doméstica,
rotas alternativas e resiliência econômica de longo prazo continuam abertas.

### Transferência preserva a necessidade da origem — 21/09/2026

O owner de relief agora desconta também o `missing_food` canônico do
assentamento de origem ao enumerar transferências. Reservas de subsistência,
ordens e produção continuam sendo respeitadas; a nova guarda impede que uma
ajuda válida para o destino piore uma escassez que já existia na origem. A
regressão de relief/abastecimento/logística passou em 25 testes. O smoke
pressionado de 180 dias manteve conservação, contabilidade, save/load e
auditoria causal verdes (`5071` eventos, falta final `344`, `ok=true`). Isso é
uma correção de segurança causal local, não uma solução para a resiliência
econômica de longo prazo.

### Imposto de renda preserva o bruto agregado — 21/09/2026

O owner de folha agora calcula a retenção sobre o salário bruto total antes de
arredondar e distribui os restos de forma determinística entre as contas das
coortes. Antes, folhas pequenas podiam truncar cada parcela para zero e perder
um imposto que existia no agregado. A regressão de pesquisa/emprego/economia/
renda/consumo passou em 86 testes; smoke pressionado de 180 dias conservou
recursos, dinheiro e save/load, com auditoria causal `ok=true`. Isso corrige
contabilidade, não fecha a falta de renda estrutural da Onda 1.

### Review de ajuda respeita uma consulta por ator — 21/09/2026

O review provider agora diferencia ausência de affordance, `NO_ACTION` e
execução. Uma instituição que foi consultada e recusou não é consultada de
novo por fulfillment, remediação ou pedido no mesmo turno. A regressão de
decisão institucional/ajuda/menu passou em 44 testes; um smoke offline de 60
dias preservou conservação, contabilidade e save/load. Provider real continua
sem sondagem nesta rodada.

### Autoria histórica rejeita decisão-fantasma — 21/09/2026

Foi adicionada uma regressão que tenta marcar uma transição material como
`ACTOR_DECISION` usando um `decision_event_id` inexistente e uma causa que é
apenas ocorrência. `validate_history` rejeita o histórico antes do commit. A
regressão composta de autoria, relief, abastecimento e logística passou em 39
testes; `compileall` e `git diff --check` também ficaram verdes. O guardrail
está comprovado, mas a varredura de autoria de todos os owners e os gates de
provider/horizonte longo continuam pendentes.

### Fixture pressionada prova cadeia material — 21/09/2026

O smoke de recuperação pressionada ganhou uma aceitação explícita para 120
dias (`seed=73`, perfil `recuperacao`). A execução passou em 13 testes e
materializou, pelas affordances/owners existentes, compras de mercado, emprego
permanente, transições de workforce e relief. Os totais finais foram 3, 12, 16
e 9, respectivamente; a pressão permaneceu visível com `missing_food=148`,
sem mortes por privação. Conservação, save/load e auditoria causal continuam
verdes. É uma fixture determinística de cobertura, não provider real,
autonomia natural de dez anos ou conclusão da Onda 1 econômica.

### Stale de provider aborta o candidato — 21/09/2026

Quando o provider escolhe uma affordance que desaparece na revalidação, o
receipt `institutional_decision_stale_affordance` continua disponível no
diagnóstico unitário, mas o `MedievalSimulator` agora levanta a espera tipada
`ProviderDecisionRequired` e descarta o candidato inteiro em modo IA, inclusive
quando o stale ocorre na revisão diária de recourse. Assim,
nenhum evento, decisão ou delta de famílias posteriores é publicado junto de
um mês parcialmente processado. Engine/provider/AI passaram em 26 testes
focados; provider real e owners diários continuam sem cobertura completa.

### Fixtures de recourse respeitam o fail-closed — 21/09/2026

Os testes que preparam uma quebra diplomática agora usam um provider falso
explicitamente durante a preparação. Quando a consulta real é feita sem
provider em modo IA, a expectativa é `ProviderDecisionRequired`: não há
fallback determinístico nem receipt de falha publicado. Engine, menu
institucional, turno diário e AI passaram em 34 testes. Provider remoto e a
varredura completa dos owners diários continuam pendentes.

### Abastecimento de campanha respeita stale do provider — 21/09/2026

Uma escolha de abastecimento que deixa de revalidar não é mais engolida pelo
review. O owner propaga `ProviderDecisionRequired`, nenhum frete é aberto pela
chamada direta e o `MedievalSimulator` continua responsável por descartar o
candidato. A regressão de campanha passou em 5 testes; contatos armados,
aftermath e resposta estratégica ainda não têm a mesma auditoria completa.
-
### Estratégia e aftermath respeitam stale do provider — 21/09/2026

As duas famílias restantes deste recorte agora propagam `ProviderDecisionRequired`
quando a affordance escolhida deixa de ser válida ou o owner rejeita a execução.
IDs forjados, rota fechada e provider ausente foram cobertos pela regressão focada
de 7 testes. O fechamento de um objetivo por condição factual resolvida continua
normal. A responsabilidade de rollback permanece no `MedievalSimulator`; provider
remoto, owners diários completos e as verticais maiores ainda estão pendentes.

### Contato armado e viagem individual respeitam stale — 21/09/2026

Os reviews de contato armado e viagem de personagem agora pausam com
`ProviderDecisionRequired` quando a affordance escolhida envelhece entre consulta
e execução. A regressão composta com estratégia e aftermath passou em 16 testes,
incluindo uma rota fechada durante a consulta e um standoff resolvido antes da
execução. Provider remoto e os demais owners opcionais permanecem pendentes.

### Ajuda institucional respeita stale do provider — 21/09/2026

Resposta, cumprimento, reparação e pedido de ajuda agora levantam
`ProviderDecisionRequired` quando a opção escolhida fica stale ou o owner
material recusa a execução. Aid/recourse/daily turn passaram em 26 testes e a
regressão de decisões provider em 9. A rotina determinística ainda pode tentar
novamente em um dia posterior; provider remoto e rollback integrado de todos os
owners continuam pendentes.

### Ritos individuais respeitam stale do provider — 21/09/2026

Oferta de rito por personagem e patrocínio institucional agora pausam com
`ProviderDecisionRequired` quando a observação ou oferta envelhece entre a
consulta e a execução. A regressão de ritos passou em 4 testes. Pesquisa, cópia
tecnológica, criaturas, espionagem e provider remoto ainda precisam da mesma
auditoria.

### Criaturas e tributos respeitam stale do provider — 21/09/2026

O turno da criatura e a resposta institucional a uma exigência de tributo agora
levantam `ProviderDecisionRequired` quando a affordance envelhece ou o owner
rejeita a execução. A regressão de autonomia/criaturas passou em 8 testes,
incluindo ausência de provider e demandas ignoradas. Pesquisa, cópia tecnológica,
espionagem e provider remoto permanecem pendentes.

### Aceitação de ensino revalida compromisso — 21/09/2026

A fase separada do aprendiz agora recompõe a affordance e o consentimento do
professor antes de registrar a decisão. Se a obrigação fica stale, o provider é
pausado com `ProviderDecisionRequired`; nenhum ensino é cumprido por seleção
obsoleta. A regressão de diplomacia provider passou em 16 testes. Provider real,
rollback integrado e as verticais maiores continuam pendentes.

### Learner diplomático fail-closed — 21/09/2026

O aceite de ensino posterior ao menu composto revalida a obrigação e o
consentimento do professor antes de gravar a decisão do aprendiz. Seleção stale
ou rejeição do owner pausa com `ProviderDecisionRequired`; a regressão provider
passou em 16 testes sem criar conhecimento ou cumprimento parcial.

### Gate comparativo após fail-closed — 21/09/2026

O gate de 120 dias passou com seeds naturais 73/101/137, fixture pressionada e
comparação econômica (`ok=true`). Todas as linhas conservaram dinheiro/recursos,
save/load e auditoria causal; alívio, mercado e mobilidade produziram resultados
materiais distintos. A fixture ainda termina com déficit alimentar, e o provider
real/gate de dez anos continuam pendentes.

### Diagnóstico do smoke natural de dez anos — 21/09/2026

O smoke de 3600 dias iniciou com as três seeds e chegou ao dia 450 sem erro
causal, mas levou aproximadamente 630 segundos para 15 meses. Foi interrompido
controladamente antes de produzir um gate final; a taxa atual tornaria três
seeds por dez anos impraticáveis. O próximo passo é perfilar/otimizar o caminho
de horizonte longo sem reduzir as garantias de rollback e autoria.

### Cópia transacional de conhecimento — 21/09/2026

O perfil de 60 dias localizou custo relevante na cópia repetida dos valores
históricos de `KnowledgeState`. A transação agora copia os registries, mas
compartilha seus valores congelados; o teste focado passou em 23 casos e o gate
natural de 120 dias da seed 73 passou com `ok=true`, conservação e save/load.
Isso é uma otimização parcial: o smoke natural de 3600 dias segue não aprovado,
e provider remoto/rollback integrado das verticais maiores permanecem
pendentes.

### Validação runtime de conhecimento — 21/09/2026

A proveniência semântica continua sendo validada em cada candidato, mas o
runtime não serializa novamente cada valor congelado de `KnowledgeState`; a
validação Pydantic completa permanece no load/save. O recorte de conhecimento e
autoria passou em 37 testes e o gate natural de 120 dias continuou verde. O
perfil curto caiu de 4,24 s para 3,95 s sob cProfile, mas o smoke de 3.600 dias
continua pendente.

### Índices derivados de ledger — 21/09/2026

O runtime passou a reutilizar índices transitórios por ID/tipo de evento e
contextos diplomáticos/capacidade estratégica, invalidando-os quando a
assinatura do ledger ou do conhecimento muda. O recorte passou em 69 testes; os
gates naturais de 120 dias com seeds 73/101/137 e de 210 dias com seed 73
ficaram verdes. O smoke de 3.600 dias ainda não foi concluído.

### Leituras derivadas de migração — 21/09/2026

A revisão de migração reutiliza um grafo transitório por ator e as projeções
frequentes de `KnowledgeState` usam cache invalidado por mudanças no ledger ou
registry. O recorte passou em 60 testes e o gate de 210 dias continuou verde
em ~25,5 s. Isso reduz trabalho repetido, mas não conclui o smoke de 3.600 dias.

### Dispatcher institucional fail-closed para affordances stale — 21/09/2026

O dispatcher comum agora propaga `ProviderDecisionRequired` em modo IA quando
uma affordance escolhida desaparece durante a recomposição ou quando o owner
rejeita a execução. Isso fecha a lacuna comum que afetava pesquisa, cópia,
roubo e espionagem: a consulta não pode virar silenciosamente um receipt de
ausência de ação depois de uma decisão stale. Offline/teste explícito mantém o
receipt sem mutação. A regressão focada passou em 37 testes; provider remoto,
rollback integrado e o smoke natural de 3.600 dias continuam pendentes.

### Cessar-fogo do defensor respeita guarnição colapsada — 21/09/2026

O owner de campanhas agora enumera uma iniciativa de cessar-fogo do defensor
somente quando sua guarnição ainda tem retirada materialmente executável. Após o
colapso, a affordance e a opção de cumprimento desaparecem; o compromisso ativo
não transfere controle nem cria retirada automática. A mesma vertical permite
que o defensor inicie um cessar-fogo quando a saída existe. A regressão de
cerco/força/concessão passou em 28 testes.

### Pesquisa institucional com publicação atômica — 21/09/2026

O patrocínio de pesquisa agora monta autorização, aceite e projeto num candidato
isolado e só publica o conjunto depois que o owner valida `start_research`.
Seleção stale ou rejeição de termos não deixa recibos de autorização, aceite ou
projeto no mundo publicado. A auditoria conjunta das verticais de conhecimento
passou em 86 testes; a verificação integrada com campanhas passou em 109. A
suíte global não foi promovida: foi interrompida por custo e expôs um 404
pré-existente da API de avatar fora do fork.
### Owners de tecnologia sem `StopIteration` e orchestration em shadow — 21/09/2026

Venda e roubo de tecnologia agora rejeitam explicitamente conhecimento, site ou
resultado ausente. A rejeição sobe pelo dispatcher IA como
`ProviderDecisionRequired`, sem transformar uma affordance inválida em ausência
de ação e sem publicar recibos/deltas parciais. A regressão focada passou em 52
testes; a integração do recorte atual passou em 109.

Também foi validado o `task-orchestration` em `RuntimeMode.SHADOW` com o
observador MetaGame/Laya. O runtime passou em 32 testes e recebeu eventos de
tarefa/plano/arquivos/testes, mas permaneceu somente observacional. O provider
Laya real não está instalado/configurado: a decisão foi fallback neutro com
`observe`, e nenhum agente foi executado pelo runtime. Provider remoto, smoke
natural de 3.600 dias e ondas de economia resiliente, magia/ecologia e campanhas
completas permanecem abertos.

### Cadeia composta de resiliência econômica — 21/09/2026

A auditoria da Onda 1 confirmou que o déficit observado não é automaticamente
falta física: nos cenários auditados havia comida nos celeiros e rotas abertas,
enquanto `missing_food` coincidia com a leitura agregada de alimento inacessível
por falta de saldo doméstico. O contexto de workforce passou a entregar apenas
essa leitura engine-owned (`unaffordable_food` e `unaffordable_group_count`),
sem expor contas ou IDs privados.

O teste composto novo percorre a cadeia real por affordance e owner: interrupção
factual da rota, escassez datada, remessa sucessora por rota conhecida, entrega
conservada e distribuição institucional posterior para despensas. A distribuição
melhora a condição, mas o teste preserva e explica o déficit residual; a rota não
é tratada como causa única. Foram `35 passed` no recorte de rota/recuperação/
relief/logística e `41 passed` no recorte workforce/dossier. A correção de
indentação em `customs.py` também restaurou seus seis testes focados.

O task-orchestration segue validado em shadow com MetaGame/Laya em modo somente
observação. O provider Laya real ainda não está configurado; não houve execução
autônoma pelo runtime. Smoke natural de 3.600 dias, provider remoto e ondas de
magia/ecologia e campanhas amplas permanecem pendentes.

### Espionagem com conhecimento acionável e presença limitada — 21/09/2026

Uma missão bem-sucedida agora produz uma observação local própria do assentamento
para a instituição que enviou o agente. O evento `settlement_observed` é publicado
antes de `espionage_resolved`, torna-se o `evidence_event_id` do finding e fica
ligado à decisão, à evidência pública alvo e à presença material. Missões falhas
ou descobertas não aprendem nada.

Relatórios obtidos por visita não são renovados indefinidamente: a rotina de
refresh exige presença atual do observador. Assim, espionagem não vira uma fonte
gratuita de vigilância permanente nem altera o estado do assentamento observado.
A regressão de espionagem, agenda institucional e protesto passou em 22 testes;
compileall e diff check ficaram verdes. Provider remoto, smoke de 3.600 dias e
as ondas amplas permanecem abertos.

### Guarnição defensiva no próprio assentamento — 21/09/2026

Uma instituição administradora pode agora escolher, no turno mensal, uma
guarnição defensiva para uma coluna própria presente, abastecida e financiada.
O caminho reutiliza o mesmo `Garrison` e os owners existentes: salário e rações
continuam materiais, manutenção ocorre como consequência da decisão, e a
guarnição decai quando perde tesouro, presença ou administração. Não há defesa
automática nem estado militar paralelo.

O controle territorial continua exigindo `occupier_id`, portanto a defesa de uma
cidade própria não duplica sua administração com `TerritorialControl`. Foram
`31 passed` nos testes focados, com compileall e `git diff --check` verdes.
Campanhas amplas, soluções políticas gerais, provider Laya real e smoke natural
de 3.600 dias continuam abertos.

### Memória direcional de suborno — 21/09/2026

O pagamento de suborno já era uma obrigação material concluída pelo owner
genérico de compromissos e, portanto, já criava memórias para as duas partes.
O recorte desta etapa corrige a interpretação: `institutional_memory` resolve o
proposal canônico e classifica `proposal_kind=bribery` com peso próprio, em vez
de conceder crédito de compromisso honrado ou desaparecer da leitura.

Isso não cria affordances, autoridade, culpa ou retaliação automáticas; é apenas
contexto institucional derivado de um fato conhecido. A regressão focada de
bribery, memória, diplomacia e estratégia passou em `37 passed`, com compileall
e `git diff --check` verdes. Composição estratégica ampla, provider Laya real,
provider remoto e smoke natural de 3.600 dias permanecem pendentes.

### Leitura causal de exposição a transbordamento — 21/09/2026

O dossier de cada ator passou a incluir `known_site_overflow_reports` somente
quando existe um `SiteReport` próprio para o site. A projeção combina a
vulnerabilidade geográfica do mapa com a última avaliação hidrológica e a
ocorrência aberta já persistidas pelo owner de overflow. Ela não calcula o mês
seguinte, não cria ocorrência, não recomenda manutenção e não revela estoque,
contas ou rotas de sites estrangeiros.

O recorte de overflow, dossier e regressões de hazards passou em `36 passed`,
com compileall e `git diff --check` verdes. O task-orchestration foi encerrado
em shadow/observe após registrar arquivos, testes e conclusão; como o provider
Laya real não está configurado, o observador usou fallback neutro. Provider
remoto, smoke natural de 3.600 dias e as ondas de economia/magia/campanhas
amplas permanecem pendentes.

### Validade do canal de conhecimento de overflow — 21/09/2026

O dossier institucional não trata mais a existência de um registro em
`site_reports` como conhecimento atual. Antes de projetar exposição de
transbordamento, ele reutiliza `current_observation`, que verifica a proveniência
do recibo e a janela de frescor de 30 dias. Observações stale ou adulteradas são
omitidas, enquanto a leitura continua derivada, sem previsão, planner ou mutação.

A regressão conjunta de dossier, overflow e infraestrutura passou em `39 passed`,
com compileall e `git diff --check` verdes. O MetaGame/Laya permaneceu em
shadow/observe com fallback neutro. Provider remoto, smoke natural de 3.600 dias
e as ondas de economia, magia/ecologia e campanhas amplas permanecem pendentes.

### Fundação causal de linha produtiva — 21/09/2026

A economia agora possui uma primeira vertical para transformar capacidade física
authored em trabalho real sem inventar uma facility. Um site sem linha pode
oferecer uma affordance transitória de fundação; a instituição escolhe apenas o
ID, e o owner revalida site, autoridade, conhecimento, estoque, conta,
trabalhadores, materiais e fundos. O projeto usa o progresso e payroll de
expansão já existentes e só ao completar cria a `ProductionFacility`, com
receipt, deltas e causal links.

O caminho não cria capacidade, dinheiro ou materiais por narrativa. Expansões
normais continuam exigindo uma facility-mãe; `demand` e `investment` passaram a
tratar explicitamente projetos de fundação sem assumir `facility_id`. A
regressão focada passou em `86 passed`; a suíte ampliada de economia, engine,
agenda, recuperação de rota e campanha passou em `117 passed`, com compileall e
`git diff --check`.

O observador MetaGame/Laya registrou C98 em shadow/observe com fallback neutro;
Laya real não está disponível. Provider remoto, smoke natural de 3.600 dias e
as ondas maiores de economia/diplomacia, magia/ecologia e campanhas continuam
abertos. Esta etapa não foi commitada, enviada ao remoto ou deployada.

### Proveniência direta de capabilities de sítio — 21/09/2026

C104 endurece a cadeia C99: o receipt material que comissiona um sítio agora
declara também `capability_ids`. O validator Map/infrastructure compara a
capacidade atual com esse delta, exige IDs únicos e não vazios e rejeita uma
capacidade que nenhum blueprint authored concede. Sites authored continuam
válidos sem receipt de commissioning.

O foco passou em `15 passed`; a regressão de construção, fundação, expansão e
infraestrutura passou em `77 passed`, com uma falha antiga fora do recorte:
`test_map_source_schema_six_requires_and_round_trips_sites` ainda espera um
payload sem `service_suspended`. Compileall e `git diff --check` passaram.
MetaGame/Laya permaneceu em shadow/observe com fallback neutro; provider real,
smoke longo e ondas amplas continuam abertos. Nada foi commitado, enviado ou
deployado.

### Comando e fadiga no desgaste de cerco — 21/09/2026

C102 fecha a lacuna causal em que comando, doutrina e fadiga alteravam combate
de campo, mas eram inertes no cerco persistente. `siege_campaign` agora lê
`effective_doctrine` e `_fatigue_level` pelos helpers canônicos de
`field_engagement`: `press` sustenta pressão enquanto a coluna consegue fazê-lo,
`hold` reduz a pressão, a postura do defensor modula a resistência e a fadiga
remove o ganho ofensivo com o tempo.

Sem comando vigente, o resultado é exatamente o anterior. O desgaste continua
limitado a `[1, 7]`, suprimento não é contado duas vezes e nenhum planner,
registro, affordance ou subsistema novo foi criado. Foram `6 passed` no recorte
focado e `59 passed` na regressão de cerco, força, comando, campo, campanha e
manutenção, com compileall e `git diff --check` verdes. MetaGame/Laya permaneceu
em shadow/observe com fallback neutro; provider real, smoke natural de 3.600
dias e ondas amplas continuam abertos. Esta etapa não foi commitada, enviada ao
remoto ou deployada.

### Construção causal de sítio de infraestrutura — 21/09/2026

C99 fecha o elo que faltava entre população artesã e a capacidade física do
mapa. Uma administração pode escolher uma affordance para construir um sítio
authored em um assentamento já existente, mas a engine não deixa o ator inventar
posição, região ou capacidade. O owner revalida autoridade, administração,
estoque, conta, materiais, construtores e o teto de uma capacidade por local.

O progresso usa o mesmo `ExpansionProject`, payroll e consumo material de C98.
Quando a obra termina, o `Map` escolhe uma célula livre da região já conhecida,
registra o sítio e mantém a proveniência no recibo; `validate_infrastructure`
confirma os deltas. A linha de produção pode então ser fundada no sítio, e a
cadeia demonstrada melhora a leitura de renda dos artesãos sem criar dinheiro
ou recursos por narrativa.

Foram `78 passed` no recorte C99 e `118 passed` na regressão ampliada, com
compileall e `git diff --check`. O MetaGame/Laya foi usado em shadow/observe com
fallback neutro; Laya real não está configurado. Um teste antigo de fixture de
mapa ainda espera um payload sem `service_suspended`, uma falha fora do diff de
C99. Provider remoto, smoke natural de 3.600 dias e as ondas amplas permanecem
abertos. Nada foi commitado, enviado ao remoto ou deployado.

### Embargo econômico dirigido — 21/09/2026

C100 adiciona o instrumento que faltava entre tarifa universal, suspensão de
serviço e bloqueio militar: uma instituição pode recusar a carga de uma
contraparte específica em um posto alfandegário que realmente opera. Declarar e
levantar são affordances transitórias; a decisão persistida carrega apenas o ID,
e o owner recompõe política, posto, alvo e autoridade.

A recusa ocorre no encontro material da carga com o posto. A mercadoria volta ao
estoque de origem, nenhuma taxa é cobrada, a rota continua aberta para outros
atores e o aviso só aparece para o dono da carga. O motivo fica disponível ao
owner de recuperação (`refused_routes`) sem criar retaliação, memória ou
conhecimento global; rotas alternativas e contrabando continuam decisões
independentes. O mesmo adapter foi integrado ao menu civil composto e à agenda,
sem duplicar o orçamento de consulta.

Foram `12 passed` no recorte do embargo e `93 passed` na regressão ampliada,
com compileall e `git diff --check`. MetaGame/Laya rodou em shadow/observe com
fallback neutro; Laya real ainda não está configurado. Provider remoto, smoke
natural de 3.600 dias e as ondas de campanhas, magia/ecologia e continuidade
histórica continuam abertos. Nada foi commitado, enviado ou deployado.

### Objetivo persistente de manutenção militar — 21/09/2026

C101 fecha a lacuna entre campanha e manutenção durável: a instituição pode
escolher uma affordance para reservar rações de uma guarnição própria ativa,
presente e ocupando validamente o assentamento. O owner recompõe todos esses
termos, além de conta, estoque e autoridade; nenhum texto ou decisão fornece
guarnição, coluna, posse ou recurso.

O objetivo `maintain_garrison_supply` só soma ao `reserve_quantity` a comida já
existente necessária para `count × 30 × reserve_months`. Não compra, cria,
recruta, marcha, paga automaticamente ou mantém o dever vivo. A guarnição
continua passando pelo `_maintain_garrison` existente e pode sofrer lapse;
abandonar o objetivo remove a prioridade sem alterar a força. O save/load, o
menu civil e a agenda institucional usam o mesmo adapter, sem consulta
duplicada.

Foram `14 passed` nos testes focados e `77 passed` na regressão composta local,
com compileall e `git diff --check` verdes. A validação persistida rejeita
também ocupação perdida, coluna deslocada/retornando, dever lapsado e coluna de
outro dono. MetaGame/Laya foi mantido em shadow/observe com fallback neutro;
Laya real não está configurado. Provider remoto, smoke natural de 3.600 dias e
as ondas de campanhas, magia/ecologia e continuidade histórica continuam
abertos. Esta etapa não foi commitada, enviada ao remoto ou deployada.

### Marca causal após espionagem descoberta — 21/09/2026

C103 torna a defesa materialmente relevante para espionagem persistente. Um
finding com `result=discovered` marca o mesmo agente no mesmo assentamento por
uma janela curta de 30 dias, e a affordance desaparece nesse período. A mesma
leitura engine-owned é reutilizada por roubo de tecnologia, com o lugar sendo a
instalação observada.

A marca é derivada dos findings já persistidos: não há timer, agenda, modelo,
memória, relação, notícia ou retaliação. Failure e success continuam apenas
gastando o dia; outro agente, outro lugar e mundos sem guarnição não são
bloqueados. Save/load e `knowledge.validate` permanecem no caminho existente.

Foram `15 passed` no foco e `86 passed` na regressão ampliada de espionagem,
roubo, tecnologia, agenda, guarnição e knowledge, com compileall e
`git diff --check` verdes. MetaGame/Laya permaneceu em shadow/observe com
fallback neutro; provider real, smoke natural e ondas amplas continuam
abertos. Esta etapa não foi commitada, enviada ao remoto ou deployada.

### Cache transitório da validação de conhecimento — 21/09/2026

`KnowledgeState.validate(world)` mantém a validação estrutural em toda chamada,
mas evita repetir a validação semântica quando o mesmo snapshot canônico é
validado novamente dentro da transação. A chave transitória inclui o tamanho e
o último objeto do ledger, o dia e a identidade de cada valor dos registries;
qualquer novo fato ou substituição de entrada invalida o cache. Save/load segue
no caminho completo de validação, e nenhum estado novo é persistido.

O recorte de histórico, knowledge e rotas passou em `50 passed`; o recorte
conjunto do dispatcher e knowledge passou em `45 passed`; o smoke de 120 dias
com `seed=73` e perfil `socorro` conservou dinheiro/recursos e save/load.
O ganho medido foi pequeno (aproximadamente `8,7s` por 120 dias nesta máquina),
portanto o smoke natural de 3.600 dias continua não certificado. MetaGame/Laya
registrou C106 em shadow/observe com fallback neutro; provider real, commit,
push e deploy continuam fora desta etapa.

### Época O(1) para registries de conhecimento — C108 — 21/09/2026

O perfil de horizonte longo mostrou que a tentativa anterior de invalidar a
validação semântica por identidade de todos os valores ainda percorria e
ordenava os 26 registries a cada chamada. C108 substitui isso por dicionários
rastreados com uma época transitória: qualquer `set`, `delete`, `update` ou
substituição de entrada incrementa a época em O(1), e a chave da validação
continua combinando ledger, dia e época. O cache de consultas também mantém um
índice independente por registry, sem apagar `reports` ao consultar rotas.

`transaction_copy` reata os registries ao candidato e limpa projeções/cache;
save/load continua no caminho completo de validação. A regressão focada de
histórico, knowledge, rotas e migração passou em `68 passed`; smoke natural de
120 dias (`9,14s`) e 360 dias (`89,46s`) preservou dinheiro, recursos e
save/load. O ganho não linear ainda não fecha o gate natural de 3.600 dias:
ele permanece pendente e deve ser medido novamente após a próxima fatia de
perfil. MetaGame/Laya registrou C108 em shadow/observe com fallback neutro;
provider real, commit, push e deploy continuam fora da etapa.

### Índices de conhecimento preservados entre transações — C109 — 21/09/2026

Os candidatos transacionais agora recebem uma cópia rasa dos índices de
consulta por ator enquanto compartilham apenas os valores congelados de
conhecimento. Os containers continuam isolados; uma escrita no registry
incrementa a época e descarta a entrada correspondente. O cache semântico de
validação permanece limpo no candidato, portanto nenhuma validação causal é
herdada sem ser reexecutada quando necessário.

O recorte conjunto de história, knowledge, rotas, migração e dispatcher passou
em `70 passed`; o smoke natural de 360 dias (`89,11s`) preservou dinheiro,
recursos e save/load. O perfil ainda mostra custo dominante em
`_actor_query`/`knowledge.validate`, então o gate de 3.600 dias continua
aberto. MetaGame/Laya registrou C109 em shadow/observe com fallback neutro;
provider real, commit, push e deploy permanecem fora desta etapa.

### Auditoria de transições actor-decision sem delta — C110 — 21/09/2026

Foi testada uma ampliação do guardrail para exigir decisão real em qualquer
`STATE_TRANSITION` com `CausalOrigin.ACTOR_DECISION`, mesmo sem `deltas`. O
schema já rejeita esse estado impossível antes de `validate_history`: uma
transição material precisa conter pelo menos um delta. A alteração redundante
foi revertida, sem adicionar caminho alternativo ou compatibilidade artificial.

O recorte de autoria, histórico, knowledge, rotas, migração e dispatcher ficou
em `73 passed`, com compileall e `git diff --check`. MetaGame/Laya registrou a
auditoria C110 em shadow/observe com fallback neutro; a auditoria completa de
todos os owners, provider real, smoke natural de 3.600 dias e ondas amplas
continuam abertos.

### Épocas por registry no índice transitório — C116 — 21/09/2026

O cache de consultas de `KnowledgeState` agora invalida apenas o registry que
recebeu uma escrita. `set`, `delete`, `update` e `|=` mantêm uma época global
para a validação estrutural e épocas independentes para as projeções de ator;
assim, uma observação diplomática nova não descarta um índice de relatórios
inalterado. Os candidatos transacionais continuam reatachando os registries ao
clone e isolando os dicionários de projeção, sem persistir épocas ou caches.

Foi adicionada uma regressão explícita para garantir que uma escrita em outro
registry preserve a projeção já construída. O recorte conjunto de histórico,
knowledge, rotas, migração e dispatcher passou em `71 passed`; `compileall` e
`git diff --check` também passaram. O perfil de 120 dias continua dominado por
`KnowledgeState.validate`, cópias transacionais e políticas institucionais,
sem ganho material mensurável neste horizonte; o smoke natural de 3.600 dias,
a auditoria owner-a-owner e as ondas amplas do roadmap continuam abertos.
MetaGame/Laya registrou C116 em `shadow/observe`, com provider real ausente e
fallback neutro; nenhuma ação externa foi autorizada.

### Clones preservam projeções transitórias de knowledge — C117 — 21/09/2026

`transaction_copy` agora preserva as épocas por registry e as projeções de
consulta já construídas quando os valores congelados de `KnowledgeState` são
compartilhados entre o mundo publicado e o candidato. Os dicionários continuam
isolados: qualquer escrita no clone incrementa sua própria época global e a
época do registry afetado, descartando somente aquela projeção. O cache não é
persistido e a validação completa de save/load permanece intacta.

O recorte de histórico, knowledge, rotas, migração e dispatcher passou em
`71 passed`; `compileall` e `git diff --check` passaram. Duas execuções de 120
dias ficaram em `10,68s` e `10,63s`, sem ganho material neste horizonte, então
o próximo gargalo não deve ser tratado como resolvido por esta otimização. O
smoke natural de 3.600 dias, provider real e as verticais amplas do roadmap
continuam abertos. MetaGame/Laya registrou C117 em `shadow/observe`, com
fallback neutro e sem autoridade de execução.

### Cache estrutural transitório de knowledge — C114 — 21/09/2026

Além da chave semântica, `KnowledgeState.validate(world)` agora memoriza a
validação estrutural dos registries até a próxima época de escrita. O cache é
transitório, é invalidado por `set/delete/update/|=` e não participa do schema;
`validate()` sem mundo continua revalidando todos os modelos no save/load.

O recorte de histórico, knowledge, rotas, migração e dispatcher passou em
`70 passed`; o smoke natural de 120 dias completou em aproximadamente `10,43s`
nesta máquina. A medição não mostrou ganho material neste horizonte, portanto
o smoke não-linear de 3.600 dias continua aberto. MetaGame/Laya registrou C114
em shadow/observe com fallback neutro; provider real e ondas amplas permanecem
pendentes.

### Fixture econômica de recuperação — C111 — 21/09/2026

O smoke pressionado `seed=73`, perfil explícito `recuperacao`, por 180 dias
reduziu o déficit alimentar final para `344` sem criação automática de comida,
dinheiro ou população. A cadeia usou apenas as affordances já enumeradas de
relief, emprego permanente e workforce; houve 15 distribuições de relief e 25
transições de workforce. Dinheiro, recursos, save/load e continuidade do dia
seguinte permaneceram conservados.

No mesmo arquivo, a auditoria causal retornou `ok=true`, com
`broken_cause_ids=[]`, nenhuma autoria de decisão inválida, nenhuma transição
de decisão sem fonte e nenhum Story/LLM material. MetaGame/Laya registrou C111
em shadow/observe com fallback neutro. Isso fecha evidência da fixture, não a
resiliência econômica de dez anos: o provider real, o gate natural de três
seeds e a redução estrutural do déficit continuam abertos.

### Gate natural de três seeds — execução interrompida por espaço — 21/09/2026

Uma execução do gate natural de 120 dias foi iniciada para as seeds `73`,
`101` e `137`. As duas primeiras completaram com conservação de dinheiro e
recursos, save/load e auditoria causal; a terceira chegou ao horizonte, mas a
persistência falhou com `sqlite3.OperationalError: database or disk is full`
porque `/tmp` estava sem espaço. Os diretórios temporários desta tentativa
foram removidos; o gate não é considerado verde e precisa ser repetido em um
filesystem com espaço disponível. Isso não altera o estado canônico do projeto.

### Gate natural de três seeds concluído no horizonte curto — C112 — 21/09/2026

Repetindo a matriz em `/dev/shm`, as seeds `73`, `101` e `137` completaram 120
dias com `natural_ok=true` e `ok=true`. Cada save/load foi equivalente, dinheiro
e recursos permaneceram conservados e as auditorias dos três arquivos não
encontraram causas quebradas ou materialidade narrativa. O resultado não
antecipa estabilidade em dez anos: `3.600` dias continua um gate separado.

### Auditor de autoria cobre receipts sem delta — C113 — 21/09/2026

`tools/medieval_causal_audit.py` agora verifica toda ocorrência não-`DECISION`
com `CausalOrigin.ACTOR_DECISION`, não apenas eventos que carregam `StateDelta`.
Transições materiais continuam exigindo o payload que casa ator e affordance
com a decisão-fonte; receipts actor-owned também precisam apontar para uma
decisão real. O recorte de smoke/autoria passou em `16 passed`, e um save de 360
dias retornou `ok=true` sem gaps de autoria. MetaGame/Laya registrou C113 em
shadow/observe com fallback neutro; a revisão owner-a-owner e o provider real
continuam abertos.

### Continuação do gate natural no checkout corrigido — 22/09/2026

Após corrigir a prioridade dos pedidos de ajuda da política offline, a seed
`73` foi reiniciada no dia zero: os sete anos de um checkout anterior não
contam para este gate. Seis checkpoints anuais chegaram ao dia `2160`, todos
com conservação de comida, dinheiro e recursos, equivalência save/load e
auditoria causal standalone `ok=true`. No sexto ano houve 103.791 eventos
(80.729 materiais), sem causas quebradas, autoria de decisão inválida, decisão
sem fonte ou mutação originada em Story/LLM.

A cadeia de ajuda deixou de ficar presa a cidades pequenas com pedido aberto:
em diagnóstico anterior, Valedouro pediu 1.290 rações, Auren aceitou, o frete
foi aberto e a entrega material chegou a Portovelho. No mundo reiniciado, porém,
a população caiu a 8.494, saúde média a 137,62 e houve 2.425 mortes por privação
até o dia 2160. O resultado prova continuidade e auditabilidade deste recorte,
não resiliência econômica. Restam quatro anos da seed `73` e o horizonte longo
das seeds `101` e `137`; o teste usa `routine-rules`, sem provider real.

Uma continuação ao sétimo ano expôs outra lacuna antes do dia 2460: a oferta de
transição ocupacional permanecia enumerada após a conta do patrocinador perder
fundos. O owner recusou a execução e o smoke parou sem publicar o save final.
`workforce_transition_options` agora recompõe também a viabilidade financeira
e o ownership das contas; o executor continua revalidando. O teste de regressão
falhou antes da mudança, e o arquivo focado passou em `36 passed` depois.
Como isso pode alterar decisões anteriores, os seis anos acima são diagnóstico
histórico e **não** certificam o checkout final: o gate de dez anos será
reiniciado do dia zero após verificar a continuação que reproduziu a falha.

Essa continuação diagnóstica atravessou o ciclo antes bloqueado e chegou ao dia
`2520` com código 0, conservação de recursos e equivalência save/load. A
auditoria standalone retornou `ok=true` em 118.456 eventos, sem causas quebradas
ou materialidade Story/LLM. Ainda não é o gate final: começou de um save gerado
antes da correção, e a saúde média caiu a 100,12 com 3.263 mortes por privação.

O gate do checkout atual foi então reiniciado: a seed `73` completou cinco anos
(`1800` dias) com conservação, save/load e auditoria causal `ok=true` em
87.706 eventos. Os arquivos anuais coincidem byte a byte com os cinco primeiros
anos da trajetória anterior, mas os outros checkpoints ainda precisam de
execução própria. A seed continua em política offline `routine-rules`, sem
provider real. Restam cinco anos dessa seed e as seeds `101`/`137` inteiras.
Já há 1.631 mortes por privação e saúde média 186: a continuidade causal não
resolveu a crise material.

Um checkpoint MetaGame/Laya de revisão da ordem foi repetido com inicialização
mais longa depois de um timeout inicial. A sessão somente leitura terminou sem
erros de observer ou telemetria perdida; o sinal primário Laya foi real, mas de
baixa confiança, com fallback neutro e sem override. A decisão de continuar o
gate longo vem do plano e das provas focadas anteriores, não de aprovação do
Laya nem de uma suposição de equilíbrio econômico.

O sexto ano do checkout atual chegou ao dia `2160` com auditoria `ok=true` em
103.791 eventos, conservação e save/load. Seu arquivo é byte a byte idêntico
ao save que iniciou a continuação corrigida do sétimo ano, já executada e
auditada no dia `2520`. Nenhum código Python de `src/` ou `tools/` mudou entre
essa execução e a comparação; por isso o save corrigido do dia `2520` foi
adotado como checkpoint do ano 7 sem repetir um run determinístico idêntico.
Ele tem 118.456 eventos e auditoria causal `ok=true`, mas registra população
7.656, saúde média 100,12 e 3.263 mortes por privação. O ano 8 foi iniciado
desse save; faltam três anos da seed `73` e as seeds `101`/`137` longas.

O oitavo ano da seed `73` terminou no dia `2880` com código 0, conservação de
dinheiro/recursos e equivalência save/load. A auditoria standalone do save
retornou `ok=true` em 133.005 eventos (101.387 materiais), sem causa quebrada,
autoria inválida ou mutação Story/LLM. A população caiu a 6.757; são 4.161
mortes acumuladas por privação. A crise material permanece e não deve ser
confundida com falha causal nem ocultada por uma recuperação automática.
Faltam dois anos dessa seed e os horizontes longos de `101`/`137`.
O `civic_protests_total=0` desse smoke não significa que os grupos não possam
protestar: uma leitura do save encontrou 30 grupos com opções cívicas válidas.
Este run usa `ai_enabled=false` e nenhum `gov_profile`, logo não instala ator
cívico e o motor não força um protesto. O horizonte natural serve para testar
conservação, persistência e causalidade, não para inferir decisões de NPCs com
provider real. As provas cívicas com ator consultado permanecem separadas.

O nono ano da mesma seed `73` terminou no dia `3240`: conservação de comida,
dinheiro e recursos, equivalência save/load e auditoria causal standalone
`ok=true` em 147.201 eventos, sem causa quebrada, autoria inválida ou material
Story/LLM. A população era 6.125, com 4.793 mortes acumuladas por privação.
Falta o décimo ano dessa seed e as seeds `101`/`137` por dez anos; os dados
offline não comprovam que um mundo com provider real teria as mesmas escolhas.

A seed `73` completou os dez anos naturais no dia `3600`: cada retomada anual
partiu de save previamente auditado, e o save final passou conservação,
equivalência save/load e auditoria causal standalone (`ok=true`, 161.796
eventos, 121.707 materiais, zero causas quebradas, autoria inválida ou mutação
Story/LLM). É **uma de três** seeds do gate longo, ainda sem provider real.
A população caiu a 5.621, com 5.297 mortes acumuladas por privação; isso é
um sinal de crise material a investigar, não algo que o gate causal sozinho
possa declarar resolvido. As seeds `101` e `137` seguem em checkpoints
independentes, com saves auditados até os dias `1080` de ambas.

O checkpoint MetaGame/Laya após essa primeira seed completa teve inferência
primária real e nenhum erro de observer, mas a baixa confiança resultou na
política efetiva neutra `observe`, sem override e sem arquivos alterados. Ele
não certifica causalidade nem balanceamento. As seeds `101` e `137` chegaram
com auditoria limpa ao dia `1440` cada e seguem para o quinto ano; ambas
também apresentam mortes por privação, então o problema econômico não se
restringe à seed `73`.

As seeds `101` e `137` também completaram cinco anos (`1800` dias) com
conservação, save/load e auditoria causal `ok=true` em cada checkpoint anual.
As mortes por privação já chegam, respectivamente, a 2.050 e 2.201. Os
sextos anos estão em execução; dez anos de cada uma ainda não foram provados.
Saves temporários dos anos 1–3 dessas duas seeds foram removidos após hashes
e auditorias, preservando os logs e os saves usados na continuação.
Uma inspeção dos receipts do dia `1800` mostrou a mesma classe de gargalo
material nas duas: Salgueiro (`101`) tinha 20.416 rações fora das casas, mas
200 não eram compráveis; Pontenegro (`137`) tinha 33.783 e 283 não eram
compráveis. As administrações distribuíram ajuda em outras cidades naquele
ciclo. Isto indica acesso/poder de compra e triagem limitada, não comida
desaparecida; ainda não prova como o provider real escolheria.

## 23/09/2026 — aplicação material de treino de campo

O bônus genérico de força baseado em qualquer conhecimento de `military_training`
foi removido. Apenas `field_drill` e `siegecraft` podem fortalecer uma coluna
específica depois de uma decisão de treino, consumo de ferramentas locais e
três dias estacionários com rações reais. Falta de suprimento ou partida causa
lapse do treino ainda em curso. Conhecimento institucional sozinho não altera
força; `fortification` e `field_logistics` não entram nessa soma.

Society persiste o treino e seus receipts; Economy debita as ferramentas;
combate cita a conclusão e a aquisição da técnica. Um cenário pressionado
verificou combate, save/load, auditoria causal e seleção stale. O schema de
save atual é 62 (Society 21, Economy 14); saves anteriores permanecem no
disco e são rejeitados explicitamente, sem migração. Os três smokes offline
de dez anos ocorreram antes dessa mudança e não são gate do checkout atual.
O efeito logístico por conhecimento isolado continua pendente, assim como a
árvore tecnológica ampla e a validação com provider real.

## 23/09/2026 — logística aplicada à coluna

`field_logistics` deixa de ampliar provisões ou bagagem por conhecimento
institucional isolado. Depois de `field_drill`, a mesma coluna precisa de uma
decisão de treino, ferramentas locais e três dias abastecidos. A conclusão
amplia apenas o limite de provisões dessa coluna; uma bagagem já existente
recebe aumento de capacidade por transição própria, ligada à conclusão. A
criação tardia da bagagem também preserva a referência ao treino, embora o
fluxo normal a estabeleça antes da conclusão. Nenhuma
ração é criada pelo bônus. Save schema 63 rejeita saves anteriores sem tentar
inventar o treino ausente; os arquivos antigos permanecem intactos.

Testes focados de treino, abastecimento, combate, persistência e observatório
passaram (`40 passed`). Uma tentativa de testar criação tardia falhou porque a fixture
já estabelece a bagagem durante os dias de treino; o cenário artificial foi
retirado. A regressão final ainda precisa de execução. Os smokes naturais anteriores
foram executados antes desta semântica e não validam o checkout atual.

## 23/09/2026 — roubo técnico exige aplicação observável

A affordance de roubo técnico antes confundia técnica conhecida com técnica
operando: bastava o detentor ter qualquer facility no site com a capacidade
correspondente. Agora o agente local só recebe a opção quando há uma linha
que produziu recentemente por uma receita dependente daquela técnica, com
`production_completed` positivo e link ao conhecimento do detentor. A opção
e o receipt citam também essa operação. Linha parada, receita básica ou
conhecimento não aplicado não são alvo válido; o owner recompõe a opção no
momento da execução.

A fixture de roubo passou a construir a linha de carvão, pagar seu trabalho e
produzir antes da tentativa; o forno eficiente não serviu porque sua receita
operacional não requer metalurgia, embora a construção requeira. A primeira
regressão expôs isso (`3 failed, 1 passed`); corrigida a fixture material, a
regressão de roubo/venda/cópia/indústria/observatório/persistência passou
(`44 passed`), incluindo save/load e auditoria standalone `ok=true` do roubo.
Save schema 64 rejeita o contrato antigo sem produção-fonte, preservando os
arquivos. O checkpoint shadow `medieval-stage3a-catalog-20260923` teve sinal
primário Laya real, mas baixa confiança e efeito neutro `observe`; não foi
verificação de código. A árvore tecnológica ampla e os gates finais seguem
pendentes.

## 23/09/2026 — difusão paga até treino material

Uma fixture pressionada integrou venda bilateral de `field_drill` a outra
instituição, com sighting voluntário, decisão independente do comprador e do
vendedor, transferência real de dinheiro, e só depois treino local de uma
coluna dessa compradora. A venda não mudou a força. O treino consumiu
ferramentas e três dias de provisões antes de elevar a força apenas daquela
coluna; a conclusão cita o conhecimento recebido. Save/load e auditoria
standalone passaram. O site militar adicional da compradora é premissa
explícita da fixture, não uma instalação criada pela venda.

Um teste integrado e a regressão adjacente (`17 passed`) cobrem essa cadeia.
Isso prova uma via de difusão aplicada em cenário preparado, não a árvore
tecnológica inteira nem decisões autônomas de provider real.

## 23/09/2026 — intenção defensiva sobrevive à mobilização

O plano `defend_occupied_settlement` antes passava a `closed` no instante em
que o owner levantava uma coluna. Agora a decisão e o destacamento real deixam
o plano em `mobilized`, com `detachment_id` persistido e uma revisão datada. A
perda da coluna retorna a intenção a `adopted`, para nova escolha do ator; não
cria substituto. O fim da ocupação só encerra o plano depois de relatório local
atual da própria instituição. Uma contradição entre relatório e estado canônico
bloqueia a execução até nova observação, sem ensinar a verdade privada ao ator.

A observação de ocupação alterada agora cita a transição material de ocupação;
leituras seguintes citam a observação anterior. Assim o receipt de encerramento
alcança o fato real pela cadeia causal. Save schema 65/Strategy schema 2
persistem a coluna vinculada e rejeitam snapshots antigos explicitamente. O
teste preparado cobre adoção, mobilização, perda após 30 dias, revisão,
encerramento após relatório e round-trip. A regressão focada de estratégia,
campanha, retirada, cerco, observatório e persistência passou (`71 passed`).
Isso é uma intenção militar persistente e auditável, não uma campanha completa:
suprimento continuado, combate em vários turnos, solução política e escolha por
provider real nessa cadeia ainda exigem prova integrada. Também foi constatado
que o ensino institucional imediato conclui hoje a obrigação no mesmo ato;
simplesmente postergar a técnica sem mudar a semântica do cumprimento criaria
um compromisso falsamente satisfeito. A via de ensino datado permanece aberta.

### Reocupação entre relatório e revisão

A revisão agora revalida a ocupação canônica antes de aceitar um relatório que
diz “livre”. Se outra ocupação material surgiu depois dessa observação, o plano
fica `blocked`, preserva sua coluna e agenda nova revisão; não publica um
encerramento obsoleto nem revela automaticamente ao ator quem retomou a cidade.
O teste de corrida cobre essa ordem e a regressão focada conjunta passou em
`72 passed`. O cenário contrafactual injeta os dois fatos territoriais como
premissas de teste; não representa uma invasão espontânea no mundo natural.

## 23/09/2026 — cidade própria ocupada entra no caminho material de cerco

A affordance de `settlement_invest` antes exigia administração estrangeira.
Isso deixava sem cerco possível justamente a resposta defensiva a uma cidade
própria sob ocupação inimiga. Agora uma coluna própria presente e preparada
pode pressionar acessos de sua cidade administrada somente quando um relatório
local próprio, atual, confirma o ocupante estrangeiro. O ID transitório e o
receipt citam a observação junto das leituras de rota; o notice privado vai ao
ocupante, não à administração que está tentando recuperar o lugar. Cidade
própria livre continua sem affordance. Se o ocupante dissolve materialmente sua
guarnição antes da seleção chegar ao owner, a opção antiga é recusada sem
mutação de investimento.

Uma fixture com administração própria, guarnição estrangeira e coluna atacante
já presente percorreu investimento → rotas restringidas → notice ao ocupante
→ cerco datado → brecha/colapso → decisão separada de ocupar. O resultado
preserva a administração, salva/carrega equivalentemente e passa auditoria
causal standalone. A revisão do plano também reconhece `occupier_id` próprio
como fim da ocupação estrangeira após relatório atual, sem oferecer nova defesa
contra si mesmo. O caso de revisão é uma fixture separada; a coluna da adoção
estratégica ainda não foi conduzida ponta a ponta até esse cerco no mesmo teste.
Isto fecha um elo de affordance e execução, não o aceite completo de campanha
persistente nem uma escolha de provider real para a cadeia toda.

## 23/09/2026 — mesma coluna: retomada, escassez e cessar-fogo

Uma fixture integrada agora parte da adoção do plano defensivo e conserva o
mesmo `detachment_id` por mobilização, marcha, frete real, carga de provisões,
posição preparada, investimento e cerco. Com estoque inicial suficiente, a
guarnição rival sofre breach, o ator decide retomar a cidade e a revisão do
dia 31 fecha o plano somente depois do relatório próprio. Sem o alimento
adicional declarado como premissa factual da fixture, o cerco expira e nenhuma
ocupação é oferecida. Os dois resultados passam save/load e auditoria causal;
não houve suplemento automático nem vitória roteirizada.

O ramo negociado mantém a mesma coluna, mas a política injetada recusa um
segundo frete: atacante e ocupante tomam decisões independentes de
cessar-fogo, cumprem retiradas materiais separadas e o plano fecha após a
observação de fim da ocupação. Isso revelou que uma parcela pendente ainda
fazia o menu oferecer retirada impossível; a opção agora desaparece até a
bagagem estar vazia e sem cargo em trânsito. Notice aberto sem carga pode ser
encerrado pela decisão de retirada, nunca move frete.

`FreightOrder` guarda os locais imutáveis de dispatch com deltas no receipt de
abertura. Uma bagagem vazia pode seguir a coluna depois da entrega, sem
reescrever a rota histórica do pedido; enquanto houver parcela pendente, o
stock de destino não pode sair do local prometido. Economy schema 15/save
schema 67 rejeitam snapshots anteriores sem migração ou remoção automática.
As decisões dos testes selecionam IDs canônicos por fixture, não provam que
o provider real escolheria cessar-fogo ou retomada. Terreno/informação,
controle prolongado, provider real e os gates longos ainda estão abertos.

## 23/09/2026 — fechamento físico de rota interrompe o mesmo cerco

Uma continuação controlada da cadeia persistente fecha fisicamente um acesso
durante o investimento. Na revisão datada, o owner levanta o investimento,
o cerco expira, a cidade continua com o ocupante rival e não há opção de
ocupação. O levantamento agora cita o fato que fechou a rota, além do fato
anterior do investimento; o relatório próprio observa capacidade zero.
Save/load e auditoria causal passam. O fechamento é uma premissa factual da
fixture, não uma enchente ou sabotagem espontânea, e as escolhas anteriores
continuam injetadas por IDs canônicos. A regressão afetada passou em 54 testes;
isso não fecha provider real nem campanha natural longa.

## 23/09/2026 — terreno muda perdas com o mesmo contato e decisões

Um contrafactual de combate mantém colunas, avistamento limitado, oferta e
aceite iguais, mas troca apenas o terreno autoral da região de floresta para
planície. A lei Map-owned já existente produz modificador diferente e muda
as baixas, que ficam explícitas no fato de resolução. Os dois lados salvam,
carregam e passam auditoria causal; 29 testes afetados passaram. Isso prova
um efeito material de terreno nessa fixture, não que o ator planejou usando
conhecimento geográfico próprio, nem campanha natural longa ou provider real.

## 23/09/2026 — sem observação local, a pressão não abre

Uma coluna estrangeira presente, preparada e abastecida diante dos mesmos
dois acessos não recebe affordance de investimento sem os relatórios próprios
dessas rotas. Um ID obtido no contrafactual informado falha na recomposição
do owner sem mutação. Após observação local dos dois acessos, uma nova opção
com novos IDs de evidência abre e sua execução material fecha as rotas.
Save/load e auditoria causal passam; 53 testes afetados passaram. A ausência
de observação é premissa da fixture, não um ator esquecendo um relatório que
já recebeu. Isto comprova um limite de informação na decisão de cercar, mas
não escolha espontânea por provider real nem campanha natural longa.

## 23/09/2026 — defesa pode escolher duração material da coluna

O menu do plano defensivo agora compõe expedições de 10 ou 40 dias pelo mesmo
owner de força, sempre conforme população disponível, estoque próprio,
salários, rota conhecida e autoridade atual. A opção informa soldados, rações
e duração calculados pela engine; a escolha é somente o ID, e o owner recompõe
exatamente aquela duração antes de debitar estoque, pagar e mobilizar.

Uma fixture pressionada escolhe a expedição longa: a coluna recebe `count × 40`
rações do estoque factual, consome 30 dias pela agenda e continua presente com
`count × 10` rações. A leitura de fadiga chega a 1 após dias reais; save/load
e auditoria causal passam. Isso habilita campanha prolongada sem alimento
gratuito, mas não demonstra ainda um combate tardio cujo resultado muda pela
fadiga. A regressão afetada passou em 56 testes. Uma fixture anterior de
posição tinha orçamento para uma consulta embora dois atores fossem
consultados; ela agora lhes dá turnos independentes, com `NO_ACTION` do rival.

## 23/09/2026 — fadiga de dias reais altera baixas de campo

Duas fixtures mantêm a mesma força, terreno, suprimento inicial, contato e
decisões de oferta/aceite. Uma desafia logo após preparar posição; a outra
passa 30 dias adicionais em campo, consumindo rações pela agenda diária antes
de encontrar o rival. Ambas ainda têm provisões suficientes para lutar, mas
a veterana sofre mais baixas. Cada fato de resolução expõe sua leitura de
fadiga (`0` ou `1`); os dois mundos salvam/carregam e passam auditoria causal.
O rival chega como premissa factual da fixture no dia do contato, não por
mobilização autônoma. A prova fecha o efeito material da fadiga num combate
controlado, não campanha natural longa nem escolha de provider real.

## 23/09/2026 — ensino consentido só afeta combate após treino material

Uma prova integrada parte de conhecimento prévio da instituição docente,
registra decisões atuais e independentes de ensinar e aprender, e usa o owner
de ensino existente para transferir apenas `field_drill`. A força da coluna
aluna não muda com esse conhecimento. A instituição precisa então escolher um
treino da própria coluna, gastar ferramentas locais e sustentar três dias de
instrução com provisões; só a conclusão aumenta a força. O fato de conclusão
cita o conhecimento adquirido. Save/load e auditoria causal passam.

O teste fecha a composição aplicada dessa via num cenário preparado, não o
catálogo tecnológico completo ou uma escolha espontânea da IA. O ensino
institucional segue imediato como transferência de conhecimento; não foi
introduzido um curso obrigatório sem resolver instrutor, localização, meios e
prazo do compromisso. Uma nova amostra de provider real foi tentada, mas a
revisão de permissão barrou a consulta antes do envio dos dados da fixture;
portanto ela não é contada como validação do provider.

Atualização após autorização explícita: uma única sonda OAuth/Codex Luna com
fixture sintética de ocupação e relatório foi executada no checkout atual. Havia
uma affordance de adoção defensiva; o provider retornou `NO_ACTION`. O receipt
`ai_decision_declined` tem origem `llm_interpretation`, zero deltas e nenhuma
ação material foi executada. É uma recusa válida dentro do menu, não uma prova
de que o provider escolha uma campanha positiva nem de que a cadeia militar
completa funciona em execução natural.

## 23/09/2026 — paliçada material e população militar de abertura

`defensive_barriers` agora é uma técnica dependente de `fortification` que
habilita obra de paliçada. A obra usa materiais, mão de obra e salários do
estoque local; o site com maintainer e integridade pertence ao Map. O cerco
calcula uma resistência limitada de um ponto de desgaste diário somente quando
a paliçada do defensor está íntegra e operante, e cita o fato material atual do
site. Dano até integridade inferior a 0,50 retira o efeito; reparo pago e
material pode restaurá-lo. A fixture prova construção, dano, perda do bônus,
reparo, save/load e auditoria causal, mas injeta conhecimento e impacto físico
como premissas explícitas. Não é descoberta natural nem lei de hazard nova.

A inspeção revelou que o mundo inicial não possuía nenhuma coorte de soldados,
embora pesquisa militar e mobilização as exigissem. O catálogo de sociedade
agora distribui 109 pessoas em coortes de ocupação militar entre os oito assentamentos, subtraídas das
ocupações civis sem alterar os 10.900 habitantes. São uma premissa física de
abertura, não guarnições ativas, destacamentos, ordens de marcha ou salários
automáticos. Após
relatórios próprios de rotas e assentamentos, as três instituições têm
affordances reais de mobilização, ainda limitadas por rações, dinheiro e
autoridade. Recrutamento posterior continua ausente e é uma lacuna distinta.

O recorte integrado de sociedade, mundo, força, pesquisa, paliçada, obra,
cerco, infraestrutura, rotas e persistência passou em `131 passed`; o teste
novo de abertura também passa a validação completa do snapshot. Uma quebra
colateral da observação de obras sem `facility_id` foi corrigida em
`route_intelligence.py`; não havia caminho válido para esse acesso quando o
projeto criava um site novo. Os smokes naturais anteriores foram executados
antes dessa mudança de população inicial e não validam o checkout atual.
Um smoke natural curto da seed 73 avançou 60 dias, conservou dinheiro/recursos,
salvou/carregou o mesmo estado e passou auditoria standalone sem causas ou
autorias quebradas. No segundo mês ainda houve falta alimentar; dois meses
offline não equivalem a dez anos nem a decisões de provider real.
Um teste separado parte desse mundo gerado, seleciona uma opção canônica de
pesquisa militar para Auren e paga seis parcelas de ferramentas, trabalho de
soldados e salário até conhecer `field_drill` no dia 180, com save/load
equivalente. A decisão foi selecionada pela fixture; não é resultado espontâneo
de IA ou prova de recrutamento.

## 23/09/2026 — falta real em pesquisa pode recrutar assistentes

Pesquisa autorizada agora registra `labor_shortfall` apenas quando assistentes
indisponíveis são o impedimento efetivo, com líder, insumos e caixa ainda
viáveis. O relatório privado e a oferta direta usam esse recibo tipado, a
ocupação exigida pela técnica e a quantidade limitada pela engine. O grupo
escolhe a oferta atual ou pode não agir; só a aceitação paga bolsa, reserva a
fração por 30 dias e permite à Society mudar sua ocupação. O projeto continua
sem progresso até novo trabalho material.

A fixture mobiliza todos os soldados do local por decisões válidas, consumindo
rações e salários. `field_drill` fica bloqueada por dois assistentes. Um grupo
civil aceita a oferta, o tesouro paga sua conta, a opção vencida é recusada,
e no dia 60 os dois participantes passam à coorte militar sem alterar o total
populacional. Só então um novo fechamento de pesquisa avança uma unidade.
O save pendente e o final carregam iguais, e a auditoria causal é limpa. A
regressão de força de trabalho, pesquisa, força e persistência passou em
`75 passed`. Um smoke natural curto de 60 dias no checkout novo também
conservou recursos/dinheiro, fez save/load e passou auditoria (`ok=true`).
Isso prova uma via de recrutamento derivada de trabalho real; campanhas ainda
não podem emitir uma oferta equivalente por iniciativa militar, e o provider
real não escolheu essa oferta na prova.

## 23/09/2026 — plano defensivo bloqueado volta a consultar meios atuais

Um plano defensivo sem coluna deixava de receber revisão se não houvesse opção
material para mobilizar. `NO_ACTION` também encerrava a chance de uma decisão
posterior. Agora ambos mantêm uma revisão datada em 30 dias. O owner recompõe
o relatório próprio e as opções de força; um plano sem coluna só mobiliza se
uma nova escolha válida do ator chegar ao executor. Uma fixture retira
provisões reais de todos os estoques da instituição, observa o bloqueio,
repõe os estoques e demonstra que o mesmo plano pode escolher uma coluna na
revisão seguinte. Outra comprova `NO_ACTION` seguido de decisão posterior.
O primeiro cenário salva/carrega e passa auditoria causal.

A regressão focada de estratégia, campanha persistente e recrutamento passou
em `15 passed`. Quatro falhas intermediárias de campanha eram pressupostos de
fixture após a inclusão de coortes militares iniciais: o teste escolhia uma
coorte menor pelo primeiro ID e esperava carga pendente mesmo no ramo que
partiu com provisões para 40 dias. A fixture passou a selecionar explicitamente
a coluna de 60 pessoas e a distinguir carga pendente de ração inicial;
nenhuma lei de campanha foi ajustada para alcançar vitória. Isto não cria uma
oferta de recrutamento para a campanha, não valida o provider real e não
substitui o gate natural longo.

## 23/09/2026 — campanha pede voluntários por duas decisões independentes

Um plano defensivo bloqueado por falta de soldados agora pode gerar uma
leitura `labor_shortfall` somente se Force confirmar rota própria atual,
rações livres, caixa para bolsa e salário inicial, autoridade e civis locais
disponíveis. Esse recibo não envia ofertas. A instituição precisa escolher
`authorize_military_recruitment` no menu mensal; o owner revalida e envia
avisos diretos. Cada grupo pode aceitar ou recusar, e a aceitação paga a bolsa
e reserva no máximo um quinto da coorte por 30 dias. Society muda a ocupação;
um novo turno do plano ainda precisa selecionar a coluna real e Force volta
a cobrar rações e salário.

A fixture começou com todos os soldados de dois assentamentos enviados, pagos
e provisionados em outras colunas. O plano de cidade ocupada ficou sem força,
observou a falta e, no mês seguinte, recebeu o relatório datado. `NO_ACTION`
do patrocinador não criou oferta. Depois da decisão institucional e da
aceitação independente do grupo, uma opção forjada e a retirada posterior de
rações foram rejeitadas. No dia 61 a nova coorte permitiu erguer uma coluna;
total populacional conservado, save/load pendente/final e auditoria causal
passaram. A regressão afetada foi `76 passed`. Um smoke natural offline de
60 dias conservou recursos e dinheiro, fez round-trip e terminou com auditoria
`ok=true`, sem provider real; nesse mundo não houve esta pressão militar.

Isso fecha a fatia de recrutamento ligada ao plano defensivo conhecido, não
reposição geral de guarnição, campanha ampla ou escolha por IA real no novo
fluxo. O gate natural de três seeds por dez anos segue pendente para o checkout
final.

## 23/09/2026 — observador reconhece todas as demandas de trabalho atuais

O backend já enviava demandas e transições de `customs`, `research` e
`military_recruitment`, mas a validação do snapshot no frontend aceitava
somente `facility` e `repair`; um mundo válido com essas demandas podia ser
recusado como retrato incompleto. O contrato TypeScript e a validação agora
incluem as cinco origens e os campos canônicos de ocupação/destino. A tela
Trabalho mostra a ocupação pretendida e resolve local por instalação, reparo,
posto alfandegário, projeto de pesquisa ou assentamento do recrutamento.
“Por quê?” continua ligado ao fato de demanda, ao aviso e à decisão do grupo,
sem converter texto em efeito.

O teste focado de interface passou `3 passed`; `vue-tsc` e build de produção
passaram. Isso corrige a visualização desse fluxo, mas não comprova navegação
humana em navegador nem cobre todas as cadeias do observador.

## 23/09/2026 — ajuda alimentar respeita a falta de cada coorte

O diagnóstico do dia 60 mostrou alimento público disponível em Ferroalto,
mas apenas 399 de 1.805 rações foram compradas. A decisão de ajuda distribuiu
1.406 rações; antes, o owner as repartia por população total, inclusive para
coortes que já tinham comprado comida. O fechamento agora registra
`unmet_by_group` no fato `subsistence_resolved`. A affordance e o executor de
ajuda recompõem a falta remanescente por coorte, descontam distribuições
anteriores ao próximo fechamento e alocam apenas a quem não recebeu a ração.
Nenhum alimento, saldo ou decisão foi criado por essa leitura. Uma premissa
inicial de escassez sem fechamento mensal ainda usa a falta canônica existente.

O teste focado de compra parcial prova que a coorte já alimentada não recebe
ajuda duplicada; save/load preserva o receipt. A regressão de consumo,
relief, autonomia e ajuda institucional passou em 74 testes após a correção
da chegada tardia de carga (a falha intermediária restringia indevidamente a
leitura ao mesmo dia do fechamento). Um smoke offline natural de 60 dias
conservou dinheiro/recursos, fez save/load e passou auditoria standalone:
`ok=true`, 1.214 eventos materiais, zero causas/autorias quebradas e zero
mutação Story/LLM. A saúde média no dia 60 ainda foi 971,62 e houve déficit
alimentar; a distribuição correta não resolve por si só a renda doméstica
insuficiente nem valida o gate final de três seeds por dez anos.

## 23/09/2026 — leitura de acessibilidade respeita o canal observado

O dossiê recuperava o último `subsistence_resolved` global de uma cidade mesmo
quando o ator só possuía um `SettlementReport` anterior. Isso podia mostrar
ao decisor uma falta de poder de compra ainda não observada. A projeção agora
usa a observação factual que originou o relatório (inclusive quando chegou
por boletim) e não inclui recibos de subsistência posteriores àquela
observação. Sem relatório válido, não há leitura de acessibilidade; sem novo
boletim, um destinatário remoto não recebe a atualização do mesmo dia.
`relief` e workforce usam a mesma regra, sem copiar saldos privados.

A fixture de mesmo dia demonstra os três estados — antes do fechamento,
observação local posterior e boletim remoto posterior. A regressão focada de
dossiê, relief, workforce e menu institucional passou `75 passed`. O primeiro
teste de workforce falhou porque assumia que a coorte conhecia a nova leitura
sem chamar a observação; a fixture foi ajustada para provar explicitamente
zero antes do relatório e o valor após o relatório. Não se alterou a lei de
consumo, preço ou transferência.

Um diagnóstico natural adicional da seed 73 chegou a 180 dias com conservação
e save/load, falta final agregada 18 e saúde média 950,63, sem mortes por
privação até então. Isto não é equilíbrio: no dia 180, Pedraclara tinha preço
de alimento 1, 1.929 artesãos e apenas 473 moedas de salários artesanais no
mesmo ciclo; Portovelho tinha 1.603 artesãos e 202 moedas de salários.
Existia alimento público nas duas cidades. A renda insuficiente e sua
distribuição entre coortes continuam problema a investigar; o smoke de 180
dias não representa provider real nem substitui o gate de dez anos.

## 23/09/2026 — mais recrutamento agrícola, sozinho, não resolveu a renda

Um contrafactual local ampliou a demanda de trabalhadores das fazendas até o
headroom físico e financeiro registrado no receipt de produção. Na seed 73,
em 180 dias, Pedraclara/Portovelho produziram 118/118 lotes em vez de 44/37,
e passaram a ter 1.443/1.352 agricultores em vez de 450/380. Ainda assim, a
falta alimentar agregada subiu de 18 para 35; o tesouro de Auren caiu de
12.359 para 6.269. Conservação e save/load passaram no contrafactual.

O experimento foi retirado do código: mais oferta física e folha agrícola não
deram renda aos artesãos sem trabalho. A próxima correção econômica precisa
vincular emprego e produção a trabalho material e demanda observável, sem
inventar subsídio, quota de drama ou distribuição por prosa. Os saves
sintéticos do comparativo permanecem apenas em `/tmp`; este não é um aceite
de equilíbrio econômico nem uma validação de provider real.

## 23/09/2026 — administrador enxerga trabalho produtivo local ao avaliar obra

No save natural da seed 73/dia 180, `site_construction_options` ainda oferecia
uma oficina de artesanato em Pedraclara para Auren e outra em Portovelho para
Valedouro. O menu institucional já incluía essas affordances, mas o dossiê
composto não mostrava a população por ocupação ao lado do trabalho produtivo
remunerado. A IA via a obra possível sem uma leitura local clara do problema.

`build_actor_dossier` agora acrescenta `own_local_livelihood_readings` apenas
para a administração que possui um `SettlementReport` próprio e observado no
dia atual. A projeção valida o receipt do relatório, recusa contagens alteradas
depois dele e mostra por ocupação os residentes e os trabalhadores pagos
naquele ciclo **por linhas produtivas da própria instituição**. Não estima
desemprego total, não revela saldos, empregadores estrangeiros ou IDs de
coortes; os IDs-fonte do relatório e payroll acompanham a leitura. É só
contexto de decisão, sem nova affordance, delta ou persistência.

No mesmo save, a leitura aponta 1.929/1.603 artesãos em Pedraclara/Portovelho
e zero salários artesanais das linhas produtivas próprias, ao lado das opções
de construir oficina. O primeiro teste novo falhou por esperar agricultores
pagos em Pedraclara na premissa inicial, onde ainda não havia agricultores;
a fixture passou a verificar a folha rural real de Campomanso. A regressão
final de dossiê, turno institucional e construção passou `42 passed`;
`py_compile` e `git diff --check` saíram 0. Não houve consulta ao provider real
nem prova de que o ator escolherá a obra, a completará ou recuperará a renda.

Um teste adicional com provider stub entregou o novo dossiê no mesmo menu da
oficina. O ator devolveu o ID canônico, o owner abriu um projeto de construção
e registrou decisão/fonte, sem criar site, emprego ou moeda no ato de escolher.
A regressão focada ampliada passou `43 passed`. Nenhuma consulta real ao Luna
foi feita neste recorte.

## 23/09/2026 — escolha de oficina até compra doméstica numa fixture única

`test_chosen_workshop_pays_artisans_and_improves_food_access_against_no_works`
compõe o dossiê datado com duas escolhas por IDs canônicos: a administração
autoriza primeiro a oficina e, depois da obra paga, a linha de ferramentas.
Cada autorização aponta para a decisão do menu; obra e fundação consomem
materiais/trabalho antes de criar o sítio e a linha. Num limite mensal posterior,
a linha paga artesãos; um recibo de compra doméstica desses trabalhadores
aponta ao pagamento (ou à retenção tributária derivada dele). Save/load e
auditoria causal do mundo resultante passaram.

Comparado com um mundo equivalente sem as obras, no mesmo dia de produção e
consumo, o cenário com oficina comprou mais comida, teve menor falta e saúde
maior em Pedraclara. Moeda e população se conservaram. A regressão focada de
construção, dossiê e menu passou `44 passed`; `py_compile` e `git diff --check`
passaram. É uma fixture pressionada com estoque/tesouro iniciais ampliados e
decisões selecionadas por stub; o avanço das obras chama seus owners, não um
turno completo da simulação. Portanto prova a composição material e o
contrafactual local, **não** escolha espontânea de Luna, melhora econômica em
mundo natural nem o gate final de três seeds/dez anos. Laya não participou
deste recorte.

## 23/09/2026 — obra e fundação atravessam os turnos completos do simulador

A fixture E155 provava os owners em sequência, mas não o menu mensal completo.
`test_workshop_choice_reappears_as_foundation_in_the_normal_monthly_engine`
agora executa `MedievalSimulator.step()` com provider stub: a administração
escolhe a oficina no menu concorrente, a obra progride nos meses seguintes, a
fundação volta como opção válida, a linha produz e paga artesãos, e uma compra
doméstica cita a renda recebida. O save final passa round-trip e auditoria
causal. Outros atores escolhem `NO_ACTION`; nenhuma obra é imposta pela engine.

Esse turno revelou um defeito real em `line_exists_or_planned`: ao compor
outras opções de expansão, ele acessava `economy.facilities[None]` para uma
obra sem instalação de origem. A consulta agora só examina projetos que têm
`facility_id`; não transforma a obra em linha nem cria fallback. A regressão
ampliada encontrou também um teste antigo que ainda assumia 1.800 artesãos
em Ferroalto, embora a população inicial atual separe 18 soldados; sua
expectativa passou a ser calculada do trabalho local e dos payrolls reais.

Após a correção, os cinco arquivos de testes afetados passaram `72 passed`
em 30,08s; `py_compile` e `git diff --check` passaram. A prova usa estoque e
tesouro ampliados na fixture e escolhas injetadas por ID, sem consulta real ao
Luna ou ao Laya. Ainda não prova que um mundo natural escolherá a oficina,
nem que sua economia de longo prazo se recuperará. O goal foi pausado neste
checkpoint a pedido do usuário.
# Checkpoint de armazenamento e oficina natural — 23/09/2026

O WIP E1–E156 foi preservado em commit local `6d0e357b`, sem push/deploy.
Quatro diretórios temporários de checkpoints (anos 3–6, oito saves) foram
compactados em `/tmp/cws-resume-year3-to6-20260923.tar.gz` (98.621.855 bytes,
SHA-256 `9efb7985e4fcc743827fe8415a858666aec3092ac6f3162bc0d2579e352306a0`).
O Dropbox confirmou o upload em `/VPS Backups/cws-resume-year3-to6-20260923.tar.gz`
com o mesmo tamanho. Só então as quatro pastas expandidas foram removidas;
o arquivo local e o remoto permanecem. Espaço livre: 4,2 → 6,2 GiB.

Save schema 67 mantém o histórico integral em blocos zlib de até 512 eventos,
com índice separado de sequência, ID e dia. O loader confere cada índice,
rejeita bloco corrompido e continua exigindo snapshot/event_count e validação
causal completos. Não migra nem sobrescreve schema 66. Um smoke natural de
120 dias da seed 73, sem provider, gravou 3.947 eventos em 2.228.224 bytes,
com save/load equivalente, conservação e auditoria causal `ok=true`; levou
15,82 s de parede e atingiu 150.240 KiB de RSS no processo. Isso não mede
dez anos nem prova decisão espontânea da IA. O smoke agora expõe tamanho do
save, tempo de save/load, pico de RSS e espaço livre após a gravação.

Na seed 73 sem qualquer reforço de estoque ou tesouro, o menu mensal de Auren
já oferece a obra de oficina ao lado de outras opções, com leitura local datada
de artesãos residentes versus empregados pagos. `NO_ACTION` não constrói nada.
E155–E156 seguem sendo a prova material com decisão injetada; ainda falta
observar um provider real escolher a oficina por conta própria e a recuperação
econômica natural em horizonte longo.

Uma fixture pressionada compôs a primeira interferência direta entre campanha,
criatura e comércio: cargas reais no rio reduziram a condição do dragão; ele
escolheu pedir tributo e, após o prazo, escolheu fechar sua própria travessia.
Valedouro já havia adotado a defesa de Portovelho e mobilizado uma coluna por
essa rota, enquanto uma compra bilateral seguia pelo mesmo rio. Contra cópia
com a travessia aberta, a coluna ficou retida, a carga atrasou e a entrega
ficou menor. Ambos os recibos de espera citam o fechamento da criatura, e o
save/load com auditoria causal passou. A estrada alternativa fechada e a
ocupação são premissas explícitas da fixture; isso **não** demonstra que a
sequência surgiu naturalmente, nem reação de QG/rei ou consequência
populacional posterior. O recorte de force também passou a ligar diretamente
`detachment_held` ao fato Map-owned que tornou a rota indisponível.

No checkout schema 68, a mesma fixture passou a começar com o celeiro de
Portovelho vazio nos dois mundos e uma compra maior já paga. A travessia
fechada conservou a carga, mas a entrega menor chegou à população no próximo
fechamento: mais rações faltantes e saúde menor que no controle aberto. O
recibo de subsistência cita o fechamento da criatura. A extensão expôs um
`KeyError` real no menu mensal: a compra presumiu que o ID de um estoque de
acampamento codificava uma cidade. O menu agora consulta a localização do
estoque canônico, como a execução existente já fazia. Os 7 testes focados de
mercado, criatura e interferência passaram, assim como save/load e auditoria
da fixture. Isso verifica composição pressionada, não ocorrência espontânea,
reação de QG/rei ou decisão de provider real nessa cadeia.

### Medição natural de um ano no schema 67

A seed 73, sem provider real e sem reforço artificial, completou 360 dias no
checkout atual. Os checkpoints de 90/180/270/360 dias e o save final passaram
round-trip; o final tem 13.024 eventos e 4.448.256 bytes. A auditoria causal
do save final retornou `ok=true`, sem causas quebradas, autoria de decisão
inválida, interpretação material ou Story material. No dia 360 havia 10.949
habitantes, falta de 37 unidades de alimento, saúde média 934 e zero mortes por
privação nessa seed. Isso é uma medição de um ano, não o gate natural de três
seeds por dez anos e não mede escolhas de um provider real.

### Continuação natural até o segundo ano

O primeiro avanço a partir do save do dia 360 abortou no dia 420: a coorte
`pop:pedraclara:human:dependent`, surgida por nascimento, tinha seis rações
mas não possuía conta doméstica. `migration_options` oferecia uma viagem
chegável por rota/comida sem verificar a conta que `start_migration` exige.
Agora a opção só existe quando a conta pertence ao próprio grupo; o owner
continua a revalidar antes de mover qualquer pessoa. Não foi criada conta nem
moeda fictícia. Os 15 testes focados de migração passaram, e a reprodução
determinística ultrapassou o dia 420 com migrações de outros grupos.

A seed 73 prosseguiu até o dia 720, sem provider real, conservando moeda e
recursos. Os saves trimestrais e o final passaram round-trip. O final tem
27.273 eventos, 8.028.160 bytes e auditoria `ok=true`, sem causas quebradas
ou mutações originadas em Story/interpretação. A saúde média caiu de 934 para
749,88 ao longo desses dois anos; não há evidência de equilíbrio econômico.
O ano 2 consumiu 240,17 s e atingiu 489.971.712 bytes de pico RSS. O gate de
três seeds por dez anos permanece aberto.

O checkpoint `a260c3df` foi publicado em `github-personal/codex/medieval-remote`.
Cinco diretórios de medições antigas (2,4 GiB expandidos) foram compactados e
verificados em `/tmp/cws-legacy-gate-evidence-20260923.tar.gz` (136.461.129
bytes, SHA-256 `0e953d699d62b84f0b9eebb7e6f3b37277f7df4756d7d2810c0cfb67b4ddb697`)
antes de remover somente as cópias expandidas. Esse segundo arquivo permanece
apenas no disco local, não no Dropbox; o espaço livre subiu para 8,0 GiB.

### Terceiro ano e limite da política offline

Após o fix de migração, a mesma seed 73 alcançou o dia 1080 em 438,26 s.
Conservação de moeda/recursos, checkpoints, round-trip e auditoria causal
continuaram verdes: 42.390 eventos, save final de 12.009.472 bytes,
`ok=true`, zero causas quebradas e zero Story/interpretação material. O pico
RSS do processo foi 716.472.320 bytes. A saúde média, porém, caiu para
477,75; Pedraclara chegou a 32/1000. Logo, integridade técnica não equivale
a resiliência econômica.

O diagnóstico read-only do save mostrou contraste material: no ano 3,
Pedraclara recebeu apenas 862 moedas em `wages_paid` para domicílios, mas
9.022 rações em relief, e terminou com 536 moedas domésticas, 6.548 rações
no estoque público e saúde 32. Portovelho teve 602 moedas de salários e
11.209 rações em relief. Já os assentamentos agrícolas Brumafria, Campomanso
e Salgueiro receberam respectivamente 14.824, 16.860 e 17.200 moedas em
salários e terminaram com saúde acima de 900. Esses números indicam um
problema de renda/trabalho e acesso, não prova de falta física global de
alimento; são agregados de eventos/estado, ainda não um diagnóstico causal
completo de cada família.

A affordance de construir oficina continua disponível para Pedraclara no
dia 1080 (`construction_blocker=None`), mas `routine-rules` não a escolhe.
Portanto prolongar indefinidamente esse mesmo mundo offline mede a ausência
de decisão econômica discricionária, não a qualidade de um provider real.
O gate de três seeds por dez anos e a escolha espontânea do provider seguem
abertos; nenhuma oficina foi criada automaticamente para melhorar a métrica.

### Custo do avanço após três anos

Um perfil dos mesmos 30 dias, retomando o save do dia 1080, identificou duas
varreduras repetidas de histórico/avisos dentro das validações: capacidade
física era buscada uma vez por site; conhecimento do fato, uma vez por memória
institucional. As duas validações agora criam índices **transitórios por chamada**,
sem salvá-los e sem alterar os critérios de aceite. Os quatro módulos focados
de infraestrutura, construção, memória e diplomacia passaram `71 passed`.
Sob `cProfile`, o avanço comparável caiu de 75,968 s para 55,751 s (−26,6%).
Partindo do mesmo save, os 30 dias após a alteração produziram snapshot e
lista completa de 43.912 eventos idênticos aos da execução anterior. Isso
mostra ganho no recorte medido, não garante a mesma taxa em dez anos; contexto
diplomático e capacidade estratégica ainda aparecem entre os custos maiores.

### Uma decisão real de Luna no menu econômico natural

Uma cópia sintética da seed 73 foi avançada sem provider até o dia 30. Nesse
estado, Auren recebeu numa única consulta OAuth/Codex Luna o menu composto da
instituição (29 opções). O dossiê incluía leitura datada de Pedraclara: 2.376
artesãos residentes e nenhum trabalhador pago na produção própria, com eventos
fonte. A construção de oficina em Pedraclara estava no mesmo menu. Luna escolheu
um ID canônico diferente: criar vínculo permanente de emprego agrícola para a
coorte de Pontenegro. O owner revalidou a escolha e criou o contrato; a
interpretação da IA não carregou delta material. A auditoria do save resultante
passou com zero causas quebradas ou mutações originadas em Story/LLM.

Para observar consequências sem gastar novas consultas, duas cópias do dia 30
(controle e escolha de Luna) avançaram pelos mesmos owners, ambas com IA
desligada, até o dia 360. Em Pontenegro, a escolha terminou com falta alimentar
2 contra 15 no controle e saúde 988 contra 984. No mundo inteiro, a falta foi
22 contra 37, mas a saúde média ficou 933,25 contra 934,00. Ambos os saves
conservaram moeda/recursos e passaram na auditoria causal. Esta é uma
comparação contrafactual de **uma decisão real**, não autonomia do provider ao
longo de um ano nem prova de recuperação econômica global. A amostra também
não demonstra que a IA escolherá oficina quando a privação se agravar: no dia
30 nenhuma cidade tinha fome, e não houve segunda consulta para esse cenário.

### Consulta real sob privação no ano 2

No save sintético da mesma seed no dia 720, Auren recebeu 46 affordances no
menu composto. O dossiê continha censo local válido de Pedraclara, relatório
de 1.495 pessoas sem poder comprar comida ali e falta de 81 rações em
Pontenegro. A oficina de Pedraclara estava entre as opções. Uma consulta
OAuth/Codex Luna com uma única tentativa escolheu, sem injeção de ID, distribuir
socorro em Pontenegro. O owner consumiu estoque existente e registrou cinco
deltas; a interpretação ficou sem delta. O save isolado
`/tmp/cws-provider-auren-pressured-day720-20260923.mws` passou na auditoria
standalone (`ok=true`, zero causas quebradas, autoria inválida ou mutações de
Story/LLM). Isso demonstra seleção e execução material sob pressão, **não**
escolha espontânea de investimento produtivo nem recuperação estrutural.

No save do dia 1080, o dossiê pós-fechamento omite corretamente o censo de
Pedraclara: seis migrações ocorreram depois do último `settlement_observed` do
ciclo, invalidando sua contagem de ocupações. O relatório de acessibilidade
alimentar permanece datado e visível. Não apresentar uma leitura ao vivo da
população como se fosse conhecimento novo do ator apenas para orientar a IA.

### Primeiro turno tático independente do comandante

A instituição continua nomeando/liberando uma pessoa real para uma coluna,
mas não pode mais escolher a doutrina dessa pessoa. Só o comandante atual,
vivo e presente recebe `hold`/`press` por IDs recomputados. Um contato armado
agenda sua consulta separada para o dia seguinte; a IA vê apenas sua coluna,
personalidade e o contato local ainda válido. A escolha ou `NO_ACTION` ganha
decisão própria com fonte no contato; mudar doutrina continua passando pelo
owner de Society e só surte efeito no dia posterior. Perder pessoa, presença,
office ou contato atual impede a execução. Uma fixture focada provou dois
turnos de atores diferentes e o receipt material; os testes de comando/cerco
passaram `11 passed`, o grupo com contato/desescalada/observatório passou
`31 passed` (incluindo save/load do turno pendente e `NO_ACTION`), e
`py_compile`/`git diff --check` passaram. O schema atual é 68: um save 67
com autoria antiga foi rejeitado com `Unsupported Medieval World Simulator
save`, mantendo hash e bytes intactos. Os saves anuais schema 67 citados acima
são evidência histórica, não um gate de load no novo checkout. Isso fecha
**um elo de comando tático independente**, não a cadeia rei → QG → general:
objetivo político, plano operacional, ordem transmitida, atraso e desacordo
ainda não estão compostos.

Um smoke offline sintético de 60 dias no schema 68 concluiu com conservação
de moeda/recursos, save/load equivalente e auditoria causal `ok=true` (1.732
eventos, nenhuma causa quebrada, autoria inválida ou mutação Story/LLM). Ele
não criou naturalmente um comandante em contato e não substitui o gate longo.

Uma consulta real OAuth/Codex Luna como `character:002`, numa fixture de
contato com uma coluna já nomeada, escolheu `hold` dentre as opções enumeradas.
O receipt `ai_decision_interpreted` teve zero deltas, a decisão nomeou o
personagem, e o owner registrou três deltas em `detachment_doctrine_set`.
Após save/load no schema 68, a doutrina ainda não valia no dia da decisão;
passou a valer no dia seguinte. Auditoria standalone `ok=true`, sem causas
quebradas nem Story/LLM material. É uma prova curta de ator independente, não
uma campanha natural com rei, QG e general.

### Dinheiro acompanha a transição de trabalho

O teste de mortalidade encontrou uma perda econômica de identidade: ao
concluir uma mudança de ocupação, Society movia as pessoas, mas o saldo
doméstico inteiro ficava na coorte de origem. A coorte nova, mesmo criada
numa cidade com comida física, tinha apenas a pequena bolsa de aceitação e
podia não comprar sua ração. O owner da transição agora transfere a fração
inteira do saldo corrente correspondente às pessoas movidas, cria a conta
doméstica de destino se necessário e registra os dois deltas no mesmo fato
que muda a população. Nenhuma moeda é criada ou retirada; a migração já
seguia regra análoga para o saldo portátil.

O teste de transição verifica contas, deltas e soma global; o caso de
mortalidade antes falhava com duas mortes de privação depois de fornecer
comida, por duas coortes novas de agricultores sem poder de compra. Os grupos
focados de workforce, mortalidade, campo e contato passaram `49 passed`.
Um smoke offline sintético de 120 dias no schema 68 preservou moeda e
recursos, save/load e auditoria causal (`ok=true`, 3.855 eventos, zero causas
quebradas ou Story/LLM material). A saúde em Pedraclara/Portovelho ainda caiu
para 862/860: esta correção resolve a renda que não acompanhava indivíduos,
**não** prova equilíbrio econômico nem decisão espontânea de construir oficina.

### Rechecagem natural após composição campanha/criatura/população

A seed 73 foi executada novamente por 120 dias no schema 68 após a correção
do menu de compras para estoques de acampamento: 3.855 eventos, save de
2.215.936 bytes, conservação de moeda/recursos, save/load equivalente e
auditoria causal `ok=true`. O horizonte não produziu fechamento de travessia,
campanha nem comandante nomeado; ausência de crise não é falha da seed. A
saúde final de Pedraclara/Portovelho continuou em 862/860. Esta medição não
resolve a pressão econômica nem substitui três seeds por dez anos ou provider
real.

O recibo de subsistência do dia 120 mostra a causa imediata da queda: antes
das decisões de socorro do mesmo fechamento, Pedraclara tinha 1.847 rações
não compráveis e Portovelho 1.581. O estoque público final ainda continha
5.006/4.074 rações, respectivamente; portanto, neste recorte a barreira
dominante é renda doméstica/acesso, não ausência física de comida na cidade.
Coortes grandes de artesãos tinham saldos quase zerados. A próxima mudança
econômica deve ampliar trabalho/remuneração materialmente viável para essas
coortes ou outro caminho de acesso decidido por ator, não criar rações.

### Oficina e empregos com recursos iniciais, sem cura roteirizada

Uma fixture parte de dois mundos idênticos da seed 73, sem aumentar estoques
ou tesouros. Em um, um decisor stub seleciona por ID válido a oficina em
Pedraclara, depois sua fundação produtiva e, em turnos mensais posteriores,
contratos de trabalho para artesãos. No outro, responde `NO_ACTION`.
Construção e produção consumiram materiais, tempo e salários reais; os
contratos fizeram dez pagamentos até o dia 390. O mundo com decisões comprou
mais rações e teve falta de 1.604, contra 2.264 no controle. Save/load e
auditoria causal passaram. Ainda assim, ambos chegaram ao piso de saúde:
mesmo quatro contratos não cobrem toda a população, e este stub recusou
outras ações como socorro. A prova mostra uma resposta parcial possível,
**não** recuperação geral nem escolha de provider real. Neste ambiente,
`provider_available()` retornou `False`; a validação com modelo real aguarda
configuração operacional, não um fallback silencioso.

### Elo operacional do QG na defesa de uma cidade ocupada

Um reino com personagem local elegível começa com um `AuthorityOffice` de QG
separado da autoridade militar institucional. O titular é um personagem
existente, recebe sua própria observação local ou um boletim de assentamento
com recibo causal e, após o plano defensivo da instituição, escolhe uma
affordance atual de mobilização ou `NO_ACTION`. `Force` recompõe plano,
autoridade, relatório do titular e opção material antes de retirar soldados,
comida e salários. Sem titular ou conhecimento próprio, o plano fica bloqueado;
uma decisão institucional forjada não consegue mobilizar a coluna por esse
caminho. O titular do QG também não pode ocupar simultaneamente o comando de
campo. A carga pendente em destino móvel continua bloqueando retirada.

Evidência focada neste checkpoint: `33 passed` em resposta estratégica,
campanha persistente, comando de campo e autonomia; Ruff e `git diff --check`
passaram. A fixture separada de carga pendente protege o caso em que a remessa
ainda não chegou; no teste de cerco desabastecido, a remessa inicial já pode
ter sido entregue antes do início do cerco. Isto prova um elo de decisão
operacional, **não** uma ordem política independente, atraso de transmissão,
discordância rei/QG/general, campanha espontânea ou gate natural de dez anos.

### Rechecagem natural e leitura sob demanda da migração

No schema 68, a seed 73 sem provider chegou a 120 dias: 3.864 eventos,
2.224.128 bytes de save, conservação de moeda/recursos, save/load equivalente,
zero mortes por privação e saúde média 952,88. Pedraclara/Portovelho já caíram
para 862/863; o problema econômico segue aberto. O perfil da continuação
120→150 dias mostrou 2.183 consultas a relatórios de rota, embora a maioria
das coortes não precisasse de um grafo de migração.

`review_migration` agora consulta rotas apenas para jornadas encalhadas ou
coortes cuja leitura própria satisfaz os pré-requisitos de migração. A busca
dos retornos do dia também para no primeiro fato anterior, sem varrer todo o
histórico. A mesma continuação de 30 dias antes/depois gerou arquivos com
SHA-256 idêntico, snapshots e 4.900 eventos iguais; 22 testes focados,
Ruff, save/load e auditoria causal (`ok=true`, zero mutações Story) passaram.
No perfil, as consultas `routes_for_actor` caíram de 2.183 para 1.227 e o
tempo instrumentado de 10,33 para 9,65 s. É uma melhoria local medida,
**não** solução do custo de dez anos nem aprovação do gate longo.

### Um ano natural atual e custo da diplomacia offline

A mesma seed 73 completou 360 dias no schema 68 com 12.926 eventos,
4.456.448 bytes de save, conservação de moeda/recursos, round-trip e auditoria
causal `ok=true` (zero causas quebradas ou Story material). Não houve morte por
privação nesse primeiro ano, mas Pedraclara/Portovelho terminaram com saúde
747/792 e média mundial 926,75. Uma seed por um ano não substitui o gate de
três seeds por dez anos nem demonstra recuperação econômica.

O perfil read-only dos dias 360→390 mostrou que a rotina diplomática montava
repetidamente capacidade estratégica e evidências para objetos usados apenas
na execução mecânica offline. `diplomatic_context(..., mechanical_only=True)`
agora preserva caixa, orçamento, técnicas, propostas e autoridade, mas não
monta as três projeções exclusivas do dossiê de provider. O contexto padrão
continua completo para a IA. Os 35 testes focados de diplomacia passaram; a
mesma continuação antes/depois produziu saves SHA-256 idênticos, snapshot e
14.324 eventos iguais. O perfil instrumentado caiu de 16,05 para 13,98 s.
Isto reduz custo medido sem alterar decisões, não é validação de IA real ou
aprovação de horizonte longo.

### Autorização política anterior ao QG e retirada bilateral — 23/09/2026

Na defesa de um assentamento ocupado, um titular político nomeado recebe seu
próprio boletim datado e escolhe autorizar o plano ou `NO_ACTION`. A ordem
auditável só permite que o titular distinto do QG decida no dia posterior; Force
revalida ordem, relatório do QG, autoridade e opção material antes de mover
pessoas ou recursos. Uma recusa não mobiliza ninguém. O recibo da ordem
pendente preserva a cadeia após save/load. Isto é uma separação de decisões e
um atraso de calendário, **não** um sistema de mensageiro físico, conflito
rei/QG/general completo ou campanha espontânea.

O contrato persistido passa a schema 69; saves 68 continuam intactos em disco,
mas não carregam no runtime atual, sem migração automática.

O dia adicional revelou uma inconsistência real no cessar-fogo bilateral: o
defensor podia receber uma opção de retirada com pedido de suprimento aberto,
mas o executor recusava o mesmo estado. A decisão de cumprir agora encerra o
pedido aberto antes de retirar a guarnição; carga pendente ou bolsa abastecida
continuam impedindo a retirada. O pedido encerrado e a retirada têm causa
auditável na decisão, sem teleporte ou descarte de carga.

O checkpoint passou em 74 testes focados de persistência, observatório,
resposta estratégica, campanha, interferência de criatura, recrutamento,
comando de campo e autonomia; uma regressão adicional confirmou que a mesma
pessoa não pode ocupar simultaneamente o turno político e o do QG. A seed
natural 73 no schema 69 chegou a 120 dias
sem provider: 3.864 eventos, conservação de moeda/recursos e round-trip
equivalente. A auditoria do save retornou `ok=true`, sem causas quebradas,
autoria inválida ou mutação por Story/LLM. A saúde de Pedraclara/Portovelho
ficou em 862/863; nem esse smoke curto nem os testes focados aprovam o gate de
três seeds por dez anos ou a recuperação econômica espontânea.

### Perfil do horizonte longo e validação histórica incremental — 23/09/2026

Uma seed natural 73 sem provider, iniciada no schema 69 antes desta otimização,
foi interrompida no dia 1500 por custo crescente; **não** gerou save final nem
passou o gate de dez anos. A saída parcial registrou 404 mortes por privação e
saúde média 333,12. Ajuda institucional continuava ocorrendo, mas o número de
empregos permanentes pouco crescia. É diagnóstico de uma trajetória offline,
não inferência sobre a escolha de um provider real. Os tempos por mês incluem
outras sondas executadas em paralelo e não são benchmark isolado.

Um perfil separado de um salto no dia 270 mostrou validações repetidas de
boletins históricos de rota/assentamento e dos registries de relações. O
KnowledgeState agora guarda somente uma prova transitória por objeto/recibo
imutável; mudança do relatório ou recibo invalida a prova, e ator, lugar e dia
continuam checados a cada validação. RelationsState mantém as verificações
semânticas completas durante o runtime, mas só faz o round-trip Pydantic de
todos os valores no save/load. Nada disso entra no snapshot.

No mesmo salto perfilado, `engine.step` caiu de 0,963 s para 0,686 s. A
continuação natural idêntica do dia 270 ao 300 produziu saves com SHA-256
igual (`c4db184d985a3eee7808312316a230be4486d2ff18d7572058aa1c195e871d0e`),
conservação, save/load e auditoria causal `ok=true`. Passaram 64 testes focados
de conhecimento/ajuda/persistência, 38 de ajuda/persistência após a segunda
mudança, e uma regressão que invalida a cache ao substituir relatório ou
remover ator. O ganho medido nesse recorte não aprova escala de dez anos;
o gate atualizado precisa recomeçar com checkpoints periódicos.

### Diagnóstico do ano 3 e custo das jornadas — 23/09/2026

O novo gate natural da seed 73 (schema 69, sem provider) produziu checkpoints
nos dias 360, 720, 1080 e 1440. O do dia 1440 passou na auditoria causal
(`ok=true`, zero causas quebradas, autorias inválidas ou deltas Story/LLM).
O gate continua em execução e **não** é
o gate completo de três seeds por dez anos. No dia 1080 havia 60.031 unidades
de alimento nos estoques, mas os saldos domésticos somados dos artesãos
caíram de 278 (dia 360) para 9 (dia 1080), embora a população artesã
permanecesse em 4.098. Dos 38 contratos permanentes, só 14 tiveram último
resultado `paid`; 19 estavam `unpaid_funds` e cinco `unpaid_labor`. Em
Pedraclara, os 1.242 artesãos tinham saldo doméstico zero e o estoque público
ligado às necessidades continha 5.637 rações. Esses números distinguem falta
de renda/acesso de falta física global de comida; **não** provam ainda que a
oficina, sozinha, recupere a economia por dez anos. A trajetória natural já
registrou mortalidade por privação, portanto o gate não deve ser descrito como
sucesso econômico.

Um salto isolado a partir do checkpoint do dia 1440 mostrou, sob `cProfile`,
4,249 s em `engine.step`; 14 validações de `RelationsState` consumiram 1,761 s
e 15 buscas de causa de rota consumiram 0,632 s. Como nenhuma memória ativa
daquele save havia sido reforçada após a criação, a validação agora só percorre
os deltas históricos de reforço quando há memória que precise dessa prova.
Além disso, todas as jornadas vencidas no mesmo dia reutilizam uma única
leitura das causas de suas rotas; migrações não mudam o Map durante esse lote.
No mesmo checkpoint, o salto perfilado caiu para 3,434 s. É uma comparação
local sob carga concorrente, não uma garantia de ganho para dez anos. Passaram
35 testes focados de memória/ajuda e 49 de migração/histórico; a continuação
otimizada do dia 1440 ao 1441 passou save/load e auditoria (`ok=true`, zero
causas quebradas, autorias inválidas ou deltas Story/LLM). A continuação
natural em andamento foi iniciada antes desta mudança, então seu resultado
futuro será evidência do runtime anterior, não aprovação do checkout novo.

A continuação otimizada do checkpoint antigo de dia 1440 até o dia 1800
conservou moeda e recursos e passou save/load. Comparada ao checkpoint de dia
1800 da trajetória original, `world_snapshot` foi integralmente igual e os
80.374 eventos coincidiram um a um, sem primeiro evento divergente. Os hashes
dos arquivos SQLite diferiram, portanto a igualdade afirmada é **semântica**
(estado canônico e história), não identidade byte a byte dos contêineres.
Isso prova equivalência neste recorte de 360 dias, não nas demais seeds ou em
todo o horizonte de dez anos.

A execução original, iniciada antes das duas otimizações acima, chegou ao dia
2190; o checkpoint de dia 2160 foi salvo e relido. Ela foi encerrada
intencionalmente depois dessa confirmação, sem apagar seus checkpoints. A
continuação do **checkout otimizado** começou do save semanticamente idêntico
de dia 1800 e tem alvo de dia 3600, com novos checkpoints a cada 360 dias.
Ainda não há resultado final para a seed 73, nem execução das outras duas
seeds exigidas pelo gate.

### Trabalho parcial em contratos permanentes — 23/09/2026

O diagnóstico do save natural no dia 1800 mostrou contratos que prometiam
empregar **até** um limite, mas o owner exigia o limite inteiro disponível e
financiado. Exemplo: um contrato de 178 artesãos em Ferroalto tinha 58 pessoas
disponíveis e ficava `unpaid_labor`, pagando zero. A liquidação agora toma o
mínimo entre teto contratado, trabalhadores presentes e salários que a conta
real pode pagar. Zero trabalhadores ou verba insuficiente para um salário
continuam gerando recibo de não pagamento; nenhum dinheiro ou pessoa é criado.
O recibo de pagamento nomeia trabalhadores pagos versus teto.

No recorte natural do dia 1800 ao 1830, nove contratos tiveram folha parcial:
246 trabalhadores e 966 moedas brutas efetivamente transferidas. O smoke
conservou dinheiro e recursos, passou save/load, e a auditoria do save de dia
1830 registrou `ok=true`, sem causas quebradas, autoria inválida ou deltas de
Story/LLM. Os 16 testes focados de emprego passaram. Esse resultado corrige
uma perda artificial de renda, **não** prova recuperação macroeconômica: no
dia 1830 várias cidades ainda estavam no piso de saúde.

A execução de dez anos iniciada antes desta correção foi encerrada
intencionalmente no dia 1980; seus checkpoints permanecem. O gate atual de
três seeds por dez anos deve rodar novamente depois de estabilizar estas
regras materiais, em vez de ser declarado verde a partir do runtime antigo.

O menu transitório de construção passou a apresentar o nome real da obra e
do assentamento, além de esclarecer que materiais e trabalho pago vêm antes
da nova capacidade. IDs de conta e estoque continuam fora do rótulo; o owner
não mudou os critérios materiais da opção. Os 20 testes focados de construção
passaram. A seed 73 foi reiniciada do dia zero no checkout atual, sem provider,
com checkpoints anuais e alvo de 3600 dias; ainda está em execução. Esse gate
offline mede conservação/estabilidade, não escolhas de um provider real.

### Leitura econômica do Dao — 23/09/2026

O painel existente de Finanças agora abre, por povoado, a poupança total ao
lado da quantidade de artesãos, sua poupança agregada, alimento no estoque
local, déficit de rações e saúde do último fechamento. Grupos artesãos podem
ser expandidos até suas contas e recibos; estoque e subsistência também abrem
os fatos-fonte. É uma projeção do snapshot observacional já autorizado ao Dao,
não conhecimento extra entregue aos atores e não uma nova fonte de verdade.
O texto esclarece que alimento disponível não implica poder de compra. Os
três testes focados do painel, type-check e build medieval passaram; o build
mantém um aviso não bloqueante de chunk JavaScript acima de 500 kB. Ainda
faltam outras visões causais de campanha, comando e mudanças de plano.

### Contratos não são produção alimentar — 23/09/2026

Uma comparação da seed 73 no dia 1080 encontrou um efeito cruzado da nova
liquidação parcial: a poupança artesã subiu de 9 para 74 moedas e contratos
pagos de 14 para 21, mas a saúde média caiu de 509 para 471 e a produção
alimentar daquele fechamento foi menor. O contrato reserva trabalhadores
antes da produção; ele paga serviço local, não aciona a receita da instalação.
Esse trade-off real não deve ser apresentado à IA como “emprego agrícola gera
comida”. O menu da IA agora declara explicitamente esse efeito e a política
offline não dá preferência artificial ao agricultor quando falta alimento.

Foi testado, e rejeitado, um veto geral a contratos de agricultores: ao fim de
360 dias ele deixou 279.671 unidades de alimento nos estoques, mas 486 rações
faltantes; Campomanso tinha 31.788 no estoque local, produção limitada por
armazenamento e uma coorte agrícola sem dinheiro. A regra final **não** contém
esse veto: renda e produção continuam caminhos materiais distintos que podem
competir por trabalhadores. Nessa seed, o primeiro ano com a política final
teve `world_snapshot` integralmente igual e 13.185 eventos idênticos ao
primeiro ano da execução anterior à mudança de apresentação/política. Passaram
15 testes focados de emprego. Isso não certifica os anos seguintes nem a
recuperação econômica.

### Mandato defensivo visível e gargalo econômico natural — 23/09/2026

O Inspector do Dao agora mostra, sob cada polity, os titulares **atuais** dos
cargos `policy` e `operations` e seus planos defensivos persistidos. Cada plano
mostra assentamento, estágio, impedimento, data da última revisão, coluna
vinculada (quando existe) e fonte causal navegável. A coluna aponta de volta
ao plano. A projeção usa os dados canônicos já presentes em `GovernanceView` e
`CampaignView`; não atribui uma ordem histórica ao titular atual nem inventa
transporte de mensagem. Os tipos TypeScript foram alinhados aos campos
`operations`/`policy`, plano defensivo e `detachment_id` já emitidos pelo
backend. Um teste focado do Inspector e o type-check passaram. Isto melhora a
investigação, mas **não** implementa a cadeia independente rei–QG–general.

No smoke offline atual da seed 73, o checkpoint do dia 1080 mostrou onze
instalações com produção zero por `payroll_funds`. Havia alimento em estoques
locais de cidades com saúde muito baixa: Pedraclara tinha 4.156 rações,
saúde 31/1000 e 1.460 artesãos com poupança agregada zero; Ferroalto tinha
1.690 rações, saúde 160/1000 e 1.343 artesãos com 68 moedas. As contas
públicas no fim do dia ainda tinham saldo, mas o receipt tipado da produção
registra limite de folha zero no momento da execução. A liquidação dos
contratos permanentes acontece antes da produção e disputa o mesmo orçamento
e força de trabalho. Um contrafactual isolado do save de dia 1080 até 1110
confirmou o conflito de orçamento: o caminho normal concluiu 16 lotes em 3
instalações; uma fixture que apenas suprimiu a liquidação dos contratos naquele
ciclo concluiu 150 lotes em 9 instalações. Saúde média ao fim foi 453,5 contra
457,12; a falta pontual foi 192 contra 225, portanto **não** se pode inferir
cura imediata da privação somente pela produção. A fixture não é proposta de
implementação: deixar de pagar vínculos sem decisão e receipt quebraria a
causalidade social. O resultado aponta para uma affordance real de revisão ou
priorização entre obrigações e produção, não para uma correção automática por
falta alimentar. O smoke segue rodando, e seus resultados ainda não aprovam
resiliência econômica.

### Alvo de contratação decidido pelo empregador — 23/09/2026

Depois de um recibo **próprio e atual** de produção limitada por folha, a
instituição empregadora recebe no menu mensal único opções transitórias de
ajustar o alvo de trabalhadores de cada vínculo a um quarto, metade ou teto
original. A IA ou fixture escolhe apenas o ID; Economy recompõe a opção,
confere autoridade e a decisão com fonte, e persiste `staffing_target` com
delta e receipt. O teto original não muda. A próxima folha paga somente
trabalho e salário materialmente disponíveis até esse alvo. O alvo não cria
produto: a instalação precisa executar sua receita e pagar sua própria folha.
O modo offline não escolhe automaticamente esse ajuste.

Um teste contrafactual a partir da mesma pressão de folha demonstrou que
reduzir o alvo deixou mais orçamento e trabalho para produção no fechamento
seguinte; opção stale ou sem relatório-fonte é rejeitada sem mutação. Passaram
18 testes focados de emprego, 23 com a agenda composta e 56 no recorte
emprego/agenda/observatório/construção; type-check e testes de Finanças
passaram. O save da escolha passou round-trip e auditoria causal `ok=true`.
O schema medieval agora é 70 (Economy 16), rejeitando e preservando saves
anteriores sem migração. O smoke natural que já rodava iniciou sob schema 69 e
é apenas uma linha de base antiga, não gate do checkout novo. Falta uma série
natural atual e decisões de provider real para medir se atores de fato escolhem
esse ajuste frente a outras prioridades.

A composição entre domínios tem uma prova **pressionada** já existente e
revalidada neste checkout: `test_medieval_campaign_creature_interference.py`
passou. Nela, uma criatura decide restringir uma rota, a mesma coluna de um
plano defensivo fica retida, uma carga de alimento atrasa e a subsistência
civil piora em comparação à rota aberta; as fontes da restrição aparecem nos
receipts de retenção, atraso e subsistência. A ocupação e a consulta de decisão
foram montadas pela fixture. Portanto ela não prova que rei, QG, comandante,
comerciantes e população formem espontaneamente toda essa cadeia num mundo
natural; esse aceite continua aberto.

Um mundo novo da seed 73 rodou 120 dias no schema 70: 3.867 eventos, dinheiro e
recursos conservados, save/load equivalente e auditoria separada `ok=true`
(zero causas quebradas, autorias inválidas ou deltas Story/LLM). O checkpoint
antigo schema 69 de dia 1440 foi rejeitado por `load_world`; seu SHA-256 antes
e depois da tentativa permaneceu
`7a45729add2609cc1deb25b645048cc03207df16b724c74d6febf3222dd9cb6e`.
Essas provas são focadas e curtas, não substituem as três séries longas.

Na mesma continuação, Finanças passou a oferecer um link causal separado para
`staffing_event_id` de cada vínculo permanente. Assim, o Dao pode abrir a
decisão que alterou o alvo de trabalhadores sem confundi-la com o receipt da
folha mais recente. O teste focado `web/src/medieval/__tests__/income.test.ts`
valida essa navegação (4 testes passaram), assim como o type-check do frontend.

### Smoke natural schema 70 retomado até o ano 4 — 23/09/2026

A seed 73 do checkout schema 70 foi retomada do save íntegro do dia 1080 e
avançada mais 360 dias até o dia 1440, sem provider real e com a política
`routine-rules`. Conservou as 76.000 moedas e todos os recursos, salvou e
recarregou estado/história equivalentemente; o checkpoint do dia 1440 ocupa
15.765.504 bytes e o pico de memória observado foi 938.307.584 bytes. O save
final avançou uma etapa adicional de continuação determinística. A auditoria
causal do checkpoint encontrou 59.634 eventos, `ok=true`, nenhuma causa
quebrada, autoria inválida, Story material ou delta de interpretação.

O resultado natural não é saudável: população 10.479, 452 mortes por privação,
saúde média 321,62/1000, unrest médio 449,75/1000 e 320 rações faltantes no
fechamento. Houve 135 pedidos de ajuda, 123 cumpridos, 133 distribuições de
alívio, 141 compras de mercado, 232 migrações iniciadas e 136 transições de
trabalho. No último snapshot havia 49 contratos permanentes, dos quais 29
pagos e 20 sem fundos; dez de 13 instalações estavam limitadas por
`payroll_funds` e oito não produziram lotes. Nenhum contrato registrou
`staffing_event_id`: a decisão de ajuste de equipe não foi escolhida nesta
execução sem provider, o que não permite inferir como o modelo real escolheria.

Este gate avançou apenas uma seed até quatro anos; não é a série completa de
dez anos/três seeds nem valida a economia como estável. Os artefatos ficam em
`/tmp/cws-schema70-seed73-resumed-to1440.mws` e
`/tmp/cws-schema70-seed73-resumed-to1440.checkpoint-day-01440.mws`.

### Fonte da acessibilidade alimentar — 23/09/2026

O fechamento `subsistence_resolved` agora aponta para o último evento de saldo
de cada grupo doméstico participante e para o último evento da cotação local,
além das fontes de estoque/compra que já citava. Assim, quando o payload mostra
que parte das rações ficou inacessível por dinheiro, o `Por quê?` pode seguir
até os recebimentos/despesas da coorte e ao preço aplicado. Isso só completa
proveniência: não muda preço, saldo, compras, alívio, saúde ou população. Os 17
testes focados de `tests/test_medieval_consumption.py`, Ruff nos dois arquivos
alterados e `git diff --check` passaram.

### Contexto econômico para revisão de folha — 23/09/2026

A affordance `employment_staffing` já entrava no turno institucional único e
mostrava as limitações datadas de produção, mas o contexto não expunha os
termos financeiros necessários para comparar os alvos. Agora cada opção mostra
local e ocupação do vínculo, trabalhadores atuais/propostos, salário por
trabalhador, custo bruto daquele vínculo e saldo atual da conta do próprio
empregador com seu evento-fonte. O campo explicita que não representa a folha
total das instalações nem prevê o próximo ciclo; owner e executor continuam
revalidando recursos e disponibilidade. Nada seleciona a opção automaticamente
nem muda o fallback. Os 18 testes focados de
`tests/test_medieval_permanent_employment.py`, Ruff e `git diff --check`
passaram.

### Retirada de coluna durante marcha — auditoria de 24/09/2026

O fluxo atual permite ao QG reencaminhar uma coluna detida por passagem
fechada somente quando há alternativa conhecida até o objetivo. A retirada
material genérica é composta apenas para colunas `present`; portanto ainda não
há opção para abandonar uma missão em marcha quando não existe caminho
alternativo ao objetivo. A auditoria de `force.py` também encontrou um limite
de representação: durante o percurso, `location_id` permanece no assentamento
de origem até a chegada, enquanto `route_index` avança. Assim, ele não basta
para calcular uma retirada a partir da posição física atual depois de vários
trechos. Nenhum comportamento foi alterado; a próxima implementação dessa
lacuna precisa primeiro definir a posição atual do destacamento e exigir
relatórios de rota conhecidos e atuais para o retorno.

### Retirada de campanha interrompida — 24/09/2026

A lacuna foi fechada para a campanha defensiva persistente. Uma coluna `marching`
que chegou a um trecho bloqueado agora oferece ao titular atual do QG duas
alternativas separadas: reencaminhar até o objetivo ou encerrar o plano e
retornar a um assentamento da própria instituição. Ambas exigem a ordem política
vigente e boletins pessoais atuais do QG sobre a obstrução e a rota escolhida.
O início da retirada substitui somente o sufixo ainda não percorrido da rota;
o prefixo material permanece, a rota de retorno é revalidada contra o mapa, a
carga não é movida, e o plano recebe lifecycle terminal `withdrawn`. Sem rota
observada/operacional ou com carga de campanha ainda comprometida, a affordance
fica ausente. A região atual em marcha é derivada topologicamente do prefixo
percorrido; mudanças em rotas já atravessadas não deslocam retroativamente a
coluna.

A fixture composta escolheu tanto desvio quanto retirada em cópias do mesmo
checkpoint bloqueado. No ramo de retirada, verificou decisão do QG, evento de
movimento citando a detenção e os relatórios, plano `withdrawn`, coluna ainda
`marching`, destino próprio e equivalência save/load. Os recortes de campanha,
resposta estratégica, comando e observatório passaram em 34 testes; mais 16
testes de capacidade estratégica e rejeição de schema antigo também passaram.
Ruff nos arquivos alterados e `git diff --check` passaram. Isso fecha somente
a saída de uma coluna parada nesta vertical — não fecha a campanha geral,
cessar-fogo, controle territorial, interações naturais ou os gates longos. O
save passa a schema 72 e Strategy State a schema 3; saves antigos continuam
preservados e são rejeitados, sem migração.

### Comandante acompanha sua coluna desde a saída — 24/09/2026

O titular do QG pode nomear um comandante real no mesmo dia em que a coluna é
erguida, antes do primeiro trecho (`route_index=0`). A nomeação é a relação
persistida que coloca a pessoa naquela coluna; ela não cria outra viagem nem
altera provisões. Enquanto a coluna marcha, essa pessoa conta como ocupada e
não recebe ações locais nem affordances de viagem individual. Até a chegada,
`Character.location_id` retém o assentamento de partida; a relação com a coluna
é a evidência de sua posição física em trânsito. A chegada atualiza
`Character.location_id` no mesmo evento material da chegada da coluna, cuja
causa inclui a nomeação. Se a autoridade do office deixar de valer durante o
percurso, a pessoa continua fisicamente com a coluna, mas perde a validade para
decisões táticas e é liberada ao chegar.

O teste focal verifica nomeação no ponto de partida, bloqueio de viagem
individual, save/load em trânsito, chegada da mesma coluna e atualização causal
de localização. Isso fecha a representação de presença do comandante na marcha,
mas não a decisão: ainda faltam affordances próprias para ele reagir a um
bloqueio a partir dos relatórios locais que pode obter, e a reação posterior do
QG/política ao resultado tático. `location_id` durante a estrada continua
retendo o assentamento de partida; a associação com a coluna é a evidência de
presença em trânsito.

### Decisão de campo do comandante durante a marcha — 24/09/2026

O comandante associado à coluna agora recebe uma observação pessoal e limitada
das rotas que tocam a junção física atual depois de uma marcha ou detenção. O
receipt `field_route_observation` cita o evento material de movimento/detenção e
a nomeação do comandante; não é boletim, não revela rotas remotas e não é
compartilhado com a instituição ou o QG. Uma coluna detida agenda uma revisão
independente para o comandante. O menu recompõe alternativas com os relatórios
pessoais atuais, podendo manter, reencaminhar a mesma coluna ou retrair pelo
prefixo já percorrido até o assentamento de partida. A execução continua no
owner militar, que valida novamente comando delegado, ordem política, relatórios,
rota física e estado da campanha. Retirada encerra o plano como `withdrawn`;
reencaminhamento agenda nova revisão estratégica.

Uma fixture integrada prova bloqueio por criatura durante a marcha, aquisição
de observações locais, affordance pessoal de retirada, decisão por provider
falso controlado, movimento material da mesma coluna, lifecycle do plano e
save/load. A fixture de campanha/QG existente continua cobrindo a resposta
separada do QG. Foram executados 9 testes focados em
`test_medieval_campaign_creature_interference.py` e
`test_medieval_force_command.py` (9 passaram). Isso fecha o elo de decisão de
campo em fixture, mas não prova surgimento natural de campanha, provider real,
nem reação posterior do QG ou liderança política ao resultado tático. O smoke
natural longo e os gates finais seguem abertos.

### Integridade dos receipts de resultado de combate — 24/09/2026

O receipt de aftermath recebido por cada instituição agora é validado contra
os termos registrados no próprio evento `field_engagement_resolved`: condições
de preparo e suprimento da coluna, baixas da instituição e faixa de força
adversária. Os campos de preparo/suprimento também passaram a ter deltas tipados
no evento causal. Isso impede que um snapshot altere os dados apresentados a
uma decisão posterior sem contradizer a evidência material de combate. Save
schema sobe de 72 para 73; versões antigas continuam rejeitadas e preservadas,
sem migração. Um teste adversarial altera separadamente `own_prepared` e
`own_supplied` e confirma rejeição pela validação de conhecimento.

Verificação focal: 16 testes de combate/aftermath e 27 testes de persistência e
rejeição de schema passaram juntos (43 total); Ruff nos arquivos envolvidos e
`git diff --check` passaram. Isso fortalece a autoria do resultado que a
instituição conhece. Ainda não cria entrega de relatório ao titular do QG: a
resposta de aftermath existente continua sendo da instituição vencedora, sem
turno independente do QG ou reação política ao resultado.

### Plano estratégico ligado à retirada pós-combate do QG — 24/09/2026

A fixture de retirada do QG agora também parte de um plano defensivo real em
estado `mobilized`, ligado por receipt de atualização à mesma coluna e ao evento
de levantamento. Com a leitura de combate e as rotas próprias atuais, o QG pode
escolher manter (`NO_ACTION`) ou retirar; no segundo ramo, Force inicia a marcha
de retorno e só então Strategy recebe a transição causal para `withdrawn`.
Relatórios de rota obsoletos continuam removendo a opção. A fixture salva e
carrega o plano encerrado e compara seu estado final.

Verificação focal: `tests/test_medieval_field_aftermath.py`,
`tests/test_medieval_route_knowledge.py` e
`tests/test_medieval_strategy_response.py` passaram juntos (43 testes). Ruff
para o teste alterado e `git diff --check` também passaram. Continua sendo uma
fixture pressionada com provider simulado; ainda faltam a reação posterior do
titular político e a observação de formação natural da cadeia.

### Titular político reavalia mandato após boletim de combate — 24/09/2026

Quando um boletim de combate chega por canal físico ao atual titular do office
`policy`, e uma coluna institucional ligada a plano defensivo participou da
batalha, o calendário agenda um turno independente para esse titular — seja o
resultado vitória, derrota ou empate. Ele pode manter, suspender ou restaurar o
mandato do plano a partir do próprio receipt de combate.
Suspender atualiza apenas o lifecycle estratégico para `blocked`; não move,
dispensa nem reabastece a coluna. O QG segue responsável por decidir uma retirada
material. `NO_ACTION` também deixa receipt de decisão, e o mesmo resultado não
reabre uma consulta repetida a cada novo boletim. A suspensão não é desfeita por
revisão periódica automática; outra decisão política é necessária para restaurá-la.

Uma fixture cobrindo `maintain`, `NO_ACTION`, `suspend` e uma derrota observada
foi adicionada junto ao fluxo do QG. Em todos os casos, o titular usa seu próprio
boletim; a suspensão tem decisão-fonte e transição causal, e save/load preserva
o plano. Os 47 testes focados de aftermath, conhecimento de rotas e estratégia passaram juntos; Ruff
nos quatro arquivos Python alterados e `git diff --check` passaram. A prova ainda
é pressionada e usa provider simulado: não demonstra chegada natural de uma
campanha, comunicação de ordens além do boletim observado nem provider remoto.

### Reparação material de breach em retirada de campanha — 24/09/2026

Um termo `campaign_withdrawal` vencido podia permanecer `breached` mesmo se o
devedor ainda tivesse a coluna presente e posteriormente escolhesse retirá-la.
Agora, somente o devedor que recebeu aviso daquele breach ganha uma affordance
transitória de reparação, e só enquanto a mesma campanha segue `breached`, a
coluna nomeada permanece presente no assentamento e há uma rota própria atual.
A decisão exige autoridade diplomática e militar; Force revalida a rota e
inicia a retirada real. A transição de reparação aponta para o breach e para o
receipt de retirada, mantém `breach_event_id` imutável e muda a obrigação para
`remediated`. O validator exige decisão do devedor, mesmo `selected_affordance_id`,
mudança física de `present` para `marching` e receipt final com campanha,
destacamento e causas correspondentes. Memória registra a reparação sem apagar
a quebra histórica. O adapter mensal e o menu civil expõem a affordance; ela
não aparece se a instituição não conhece o breach ou se a retirada já não é
materialmente possível.

A fixture focal cobre a falha por prazo, aviso ao devedor, rota válida,
retirada escolhida, estado `remediated`, preservação do breach, rejeição de rota
obsoleta sem mutação, navegação causal e save/load. O recorte
`tests/test_medieval_siege_campaign.py` mais
`tests/test_medieval_persistent_campaign_chain.py` passou em 25 testes no schema
atual; `web/src/medieval/__tests__/diplomacy.test.ts` passou em 6 testes e o
type-check do frontend passou. A projeção PT-BR identifica esta memória como
reparação de retirada de campanha. Ruff nos arquivos envolvidos ainda aponta somente três findings
preexistentes (`F401` em imports da decisão civil e `F841` em teste de cerco);
nenhum foi introduzido por este recorte. Isso fecha uma modalidade de reparação
de compromisso, não a auditoria completa de campanhas prolongadas, múltiplas
colunas, demais concessões ou o gate natural de longo prazo.

### Contexto de produção para revisão de folha — 24/09/2026

O menu de revisão de folha já mostrava saldo da conta própria, custo atual e
proposto do vínculo e leituras datadas de produção; faltava tornar explícita a
receita da linha ligada ao receipt atual de falta de caixa. O contexto agora
inclui somente as instalações próprias referenciadas pelas affordances atuais,
com assentamento, ocupação, insumos e produtos por lote, lotes/capacidade e
limitações observadas no receipt causal. Não prevê o que ocorreria no próximo
ciclo nem transforma reduzir/suspender folha em recomendação ou execução
automática. O owner continua revalidando a decisão e os recursos. No turno de
revisão de folha, o empregador também recebe o censo e a pressão alimentar,
saúde e unrest do assentamento afetado, somente quando vierem de sua observação
local válida do dia. As fontes do censo, folha observada e produção limitada
entram nos links causais da decisão; quando presente, o receipt de alimento
inacessível também é causa navegável. Não são expostos IDs de coortes nem caixa
de outros atores.

Verificação focal: `tests/test_medieval_permanent_employment.py` e
`tests/test_medieval_institutional_agenda.py` passaram (`25 passed`); Ruff nos
dois arquivos Python tocados e `git diff --check` passaram. A fixture do menu
captura também o prompt entregue ao provider simulado e confirma que a opção
continua sendo somente um ID listado. Isso valida a transmissão do contexto no
turno composto e suas fontes auditáveis, não escolha do provider real nem
recuperação econômica natural.

### Ataque de criatura legível após observação local — 24/09/2026

Uma perda populacional por criatura já era material e causal, mas o dossier do
administrador mostrava apenas o total atualizado. Quando uma observação local
válida cita diretamente um evento recente `creature_attacked_population`, o
contexto do ator agora expõe o tipo de criatura, dia e quantidade afetada. A
leitura é derivada do receipt e limitada aos últimos 30 dias; não revela o ID
da coorte anônima, não cria uma ordem de resposta e não aparece sem a causa no
relatório que o ator conhece. O Dao continua tendo o evento canônico completo.
O mesmo resumo derivado também chega ao turno pessoal do oficiante e à decisão
independente da instituição que pode patrocinar o rito; isso informa a escolha,
mas não cria oferta, patrocínio ou ward automaticamente.

Verificação focal: o fluxo de ataque escolheu a affordance vigente, removeu
somente a população anônima engine-bounded, atualizou a observação local e
confirmou o resumo correspondente no dossier; save/load permaneceu equivalente.
`tests/test_medieval_actor_dossier.py`,
`tests/test_medieval_creature_magic_interaction.py` e
`tests/test_medieval_character_rite_policy.py` passaram (`29 passed`), assim
como Ruff nos três arquivos Python e `git diff --check`. Isso fecha a passagem
de evidência local do ataque para o contexto do oficiante/patrocinador; ainda
não prova que um ator escolherá investigar, proteger ou retaliar, e nenhuma
dessas reações é forçada.

### Contexto de aftermath para reforços próprios — 24/09/2026

Uma batalha pode agregar reforços próprios elegíveis a uma coluna-âncora, e o
executor já oferecia affordances pós-combate para cada sobrevivente. O turno do
ator, porém, apresentava somente a coluna-âncora, deixando as outras opções sem
contexto correspondente. Agora a situação pós-combate enumera todas as colunas
próprias ainda presentes no local e seu efetivo, com a âncora identificada no
resultado. Não inclui provisões nem rotas privadas; elas não são necessárias
para essas escolhas e permanecem fora do prompt.

Uma regressão compõe a batalha multicoluna real, confirma que as opções de
dissolução correspondem às duas colunas derrotadas e que a situação do ator
descreve ambas. A decisão `NO_ACTION` não muda o estado. Os arquivos
`tests/test_medieval_field_engagement.py` e
`tests/test_medieval_field_aftermath.py` passaram juntos (27 testes), além de
Ruff e `git diff --check`. Isso alinha opções e contexto em uma fixture
pressionada; ainda não prova escolhas reais do provider nem formação natural
de batalhas com reforços.

### Ajuste de legibilidade da barra de simulação — 24/09/2026

A captura local em 1280 px mostrou que o controle de opt-in de IA e a explicação
de provedor disputavam a mesma linha dos controles de tempo, comprimindo o
rótulo e quebrando a mensagem em trechos curtos. Os estados do botão agora são
compactos (`IA ligada/desligada`) e a explicação ocupa uma linha própria em
larguras intermediárias. A captura Chromium posterior confirmou a composição
sem sobreposição. `web/src/medieval/__tests__/app.test.ts` passou (13 testes),
assim como o type-check do frontend e `git diff --check`. O comando browser do
skill não pôde baixar seu CLI por indisponibilidade de rede; foi usado o
Playwright já instalado no projeto para a captura local. Isso corrige um
problema de legibilidade no observatório, mas não substitui a navegação
interativa dos dossiers de personagem, economia e campanha.

### Paginação de dossiês para observabilidade — 24/09/2026

O endpoint de dossiê aceita `after` como cursor opaco keyset e `limit` (padrão
50, máximo 100), ordena fatos pela evidência mais recentemente aprendida e
retorna `next_after` (cursor opaco ou `null`) e `has_more`. A fronteira não
deriva se fatos mais recentes chegam entre páginas. A interface carrega páginas anteriores para personagens, governos
e organizações; o painel do personagem continua mostrando os dez fatos mais
recentes já conhecidos e cada item abre a Crônica. A consulta usa o índice
transitório existente de eventos e um índice transitório de decisões por ator,
recriado quando o ledger recebe novos fatos. Ambos são reconstruíveis e não
alteram save/schema nem conhecimento do ator.

Verificação focal: paginação direta sem perda/duplicação nem vazamento de fato
desconhecido, serialização do endpoint e limite inválido foram cobertos por
`tests/test_medieval_dossier.py` e pelo teste focal de `test_medieval_api.py`
(`6 passed`). O teste focal de save/load/continuação passou (1 teste).
`web/src/medieval/__tests__/dossier.test.ts` passou (4 testes), type-check e
Ruff (ignorando o `E402` preexistente de `contracts.py`) e `git diff --check`
passaram. A paginação limita a resposta e reutiliza índices quando o ledger
está estável; o read-model ainda monta e ordena os candidatos antes de cortar
a página, então não é uma prova de custo O(página) nem fecha o gate de escala.

Medição sintética adicional: 5.000 decisões próprias no ledger, página de 50,
mediana de 45,77 ms por consulta (cinco execuções, sem profiler); `tracemalloc`
registrou pico temporário de 9.778 KiB numa execução. Essa fixture serviu apenas
como referência artificial. Em seguida medi, sem escrita, o save real do dia
480, seed 73, com 17.832 eventos. `cProfile` identificou busca linear de causas
dentro do loop de fatos; trocar a associação pela estrutura `set` já construída
reduziu as medianas locais (7 consultas por ator) de 68,59 para 15,34 ms em
Auren, 64,37 para 15,13 ms em Escarlia e 35,86 para 11,10 ms em Valedouro.
Houve um outlier de 121,67 ms em Escarlia, por isso as medianas não representam
latência máxima. Testes focados (6), Ruff e `git diff --check` passaram. A
projeção ainda monta e ordena todos os candidatos; isso não prova custo
O(página) nem fecha o gate de 3.600 dias, RSS ou saves longos.

## Dossiês no observatório — inspeção local em Chromium — 24/09/2026

Carreguei em uma instância local isolada uma cópia somente para leitura do save
do dia 480 (`17.832` eventos). No browser, Auren carregou 50 entradas, buscou a
página anterior e chegou a 100 IDs distintos; abrir `Ver causa` no dossiê
carregou o fato correspondente na Crônica. O histórico do personagem selecionado
também abriu com fatos conhecidos. A aba Finanças mostrou 91 folhas e 21
contratos de emprego.

A inspeção visual encontrou categorias internas sem tradução e pedidos de ajuda
mostrados apenas como `request`. A UI agora traduz os nomes das registries de
conhecimento e renderiza pedidos/respostas de ajuda com instituição, povoado e
quantidade presentes no aviso canônico. O teste focal do dossiê UI passou em 5
testes, type-check e build passaram, e a inspeção Chromium confirmou a tradução
no aviso real do save.

Para a campanha, gerei uma fixture atual pelo teste focal existente de cerco
com abastecimento, sem alterar o teste nem a política do mundo. No dia 32, duas
colunas estavam presentes e um cerco tinha alcançado a brecha. No browser, a
camada Campanhas abriu o detalhamento de efetivo, provisões, posição e cerco.
`Ver decisão` abriu o evento de escolha do QG, com causas incluindo adoção do
plano, autorização política e boletim conhecido; sua consequência de mobilização
abriu as mudanças materiais canônicas (`stock:campomanso · food` e
`detachment:event:183 · provisions/stage`). Assim foram verificados no browser
os elos decisão → evento → owner/deltas. Uma única regressão de campanha passou
(`1 passed`); nenhum passo foi executado pela UI, e os saves-fonte não foram
alterados.

### Linha do tempo no dossiê de personagem — 24/09/2026

O inspetor de personagem agora mostra, em seção recolhível, até dez fatos mais
recentes já presentes no dossiê daquele personagem. A lista inclui decisões
próprias e fatos que ele conhece, ordenados pelo dia de aprendizado; cada item
leva à Crônica pelo evento-fonte para abrir causas, consequências e deltas. A
UI não procura nem exibe eventos canônicos desconhecidos pelo personagem, e os
fatos não ficam duplicados na seção de dossiê geral. A API/read-model existente
continua sendo a fonte; nenhuma história paralela foi persistida.

Verificação focal: `dossier.test.ts` e `app.test.ts` passaram juntos (16
testes), cobrindo ordenação recente e navegação até o evento-fonte; type-check e
`git diff --check` passaram. Naquele ponto faltava inspeção interativa dos
fluxos de economia/campanha; isso foi parcialmente fechado pela inspeção em
Chromium documentada acima, que cobriu Finanças e uma fixture de campanha. O
limite visual de dez entradas evita despejar a lista toda no inspetor; a API já
pagina o read-model, e o custo de montar/ordenar todos os candidatos continua
pendente no gate de escala.

## Menu econômico composto no save atual — inspeção somente leitura — 24/09/2026

Carreguei em modo somente leitura `/tmp/cws-econ-followup-day510.mws` (dia
510, schema atual), direcionando logs/cache temporários para `/tmp`. O save tem
21 contratos permanentes. Ao recompor o menu mensal real de cada empregador,
Auren recebeu 64 affordances num único turno (30 de alívio, 18 revisões de
folha, 11 diplomáticas, 3 de produção e 2 de outras famílias); Escarlia recebeu
70 (30 de folha, 28 de alívio, 11 diplomáticas e 1 econômica); Valedouro recebeu
41 (15 de folha, 14 diplomáticas, 8 de alívio, 3 de produção e 1 econômica).

O fragmento de folha do próprio menu continha as opções de reduzir/suspender,
custo atual/proposto de cada contrato, leituras próprias de produção limitada,
censo e observações locais de alimento, saúde, unrest e acessibilidade. Em
Auren, por exemplo, havia 18 opções de folha e evidência datada da produção
agrícola limitada por verba. Isso confirma que a lacuna não é falta de
registro do adapter ou de composição: as affordances e evidências chegam
juntas ao turno institucional normal. A consulta continua grande (41–70
opções) e não há evidência de seleção por provider real nesse save.

Não chamei provider, não selecionei affordance nem executei owner; o save não foi
alterado. Portanto, esta inspeção não prova que um modelo real escolha reduzir
folha, investir ou aguardar, nem que qualquer opção isolada resolva a economia.
O próximo aceite econômico é validar uma escolha real autorizada e seus efeitos
materiais, sem substituir a decisão por fallback ou perfil de teste.

Verificação focal após a inspeção: `tests/test_medieval_institutional_agenda.py`,
`tests/test_medieval_institutional_decision_turn.py` e
`tests/test_medieval_permanent_employment.py` passaram (`38 passed`); o runner
usou `CWS_DATA_DIR` e cache temporários em `/tmp`. `git diff --check` também
passou. Esses testes verificam composição e execução por fixture/provider
simulado; não substituem a chamada real.

## Contexto comparativo da revisão de folha — 24/09/2026

O menu de folha agora mostra, em cada affordance, o total atual de compromissos
de emprego permanente da conta compartilhada e o total após aquela alteração
específica. A leitura exclui explicitamente folhas de instalações e não estima
receita nem produção futura. As causas da decisão também incluem os últimos
eventos de todos os vínculos dessa conta, pois eles fundamentam o total
agregado; os owners continuam revalidando e executando apenas a opção escolhida.
No save somente leitura do dia 510, Auren expôs 18 affordances de folha; uma
delas reportou seis vínculos na conta, compromisso atual de 3.260 e 2.932 após
aquela suspensão específica. Esses números descrevem contratos permanentes,
não a folha produtiva das instalações.

O executor agora também exige que a decisão contenha todos os eventos-fonte
atuais dos vínculos usados no agregado; apontar apenas ao evento de pressão não
basta. Uma decisão incompleta foi rejeitada sem mudar o contrato antes da
decisão integral, assinada pelo ator, ser aceita.

Verificação: `tests/test_medieval_permanent_employment.py` passou (`21 passed`),
incluindo contexto do menu composto, soma com dois vínculos na mesma conta e
links causais para ambos. Ruff nos dois arquivos tocados e `git diff --check`
passaram. Isso melhora as evidências fornecidas ao ator; não demonstra escolha
de provider real nem recuperação econômica natural.

## Índice do ledger nos aceites institucionais — 24/09/2026

O perfil do mesmo save somente leitura do dia 510 (`/tmp/cws-econ-followup-day510.mws`)
mostrou que `market_purchase_acceptance_options` e
`technology_sale_acceptance_options` percorriam todo `world.events` por ator
para localizar pedidos recentes. Ambos agora consultam o índice transitório
`events_of_type` e filtram pelo tipo de decisão e pela ação de pedido; venda de
técnica também inclui seu recibo explícito `technology_sale_requested`, usado
pelo caminho direto de owner/API. A deduplicação de pedidos já executados agora
deriva IDs dos recibos `sell_decided`/`technology_sale_completed`, em vez de
varrer o ledger para cada pedido. A revalidação e a autoria dos pedidos não
mudaram.

O mesmo perfil mostrou que os builders de opções diplomáticas usavam apenas
campos mecânicos de `DiplomaticContext`, embora calculassem também capacidade
estratégica e evidências destinadas ao contexto do provider. Eles agora pedem
explicitamente a projeção mecânica; o contexto completo continua sendo montado
na situação entregue ao provider quando o ator realmente tem affordances.

No menu do save (33 atores, 280 affordances), `_by_id` foi de 1,296 s para
0,701 s sob cProfile e de 0,561 s para 0,246 s sem profiler. A contagem de
opções permaneceu igual. São execuções pontuais, não benchmark estatístico nem
tempo integral do turno. Os maiores custos restantes nesse recorte são a
prévia de objetivo de suprimento (inclui cinco cópias transacionais) e a
composição de contratos de emprego; esses caminhos não foram alterados nesta
fatia.

Verificação focal: `tests/test_medieval_market_purchase_policy.py`,
`tests/test_medieval_technology_sale.py` e `tests/test_medieval_trade_embargo.py`
passaram (`21 passed`); `tests/test_medieval_diplomacy.py`,
`tests/test_medieval_strategy_response.py`, `tests/test_medieval_ai_decision.py`
e `tests/test_medieval_institutional_decision_turn.py` passaram (`59 passed`).
Ruff nos módulos de compra/venda e `ruff --ignore E701` em `diplomacy_policy.py`
passaram; o arquivo já contém linhas E701 fora desta alteração. `git diff --check`
passou.
Não houve chamada a provider, mutação do save, commit ou publicação.

## Reutilização do índice em ofertas de emprego — 24/09/2026

`_food_labor_pressure` verificava o evento atual de cada instalação agrícola
percorrendo o ledger em ordem reversa, apesar de `facility.last_event_id` já
identificar precisamente o receipt relevante. Agora consulta `event_index()` e
preserva os mesmos filtros de dia, instalação, delta e shortfall. Os testes de
emprego permanente (`21 passed`) e construção de sites (`20 passed`), Ruff e
`git diff --check` passaram. No save do dia 510, uma medição sem profiler
registrou 33 atores, 280 opções, descoberta em 0,129 s e composição em 0,232 s;
essas diferenças frente à leitura anterior são pequenas e pontuais, então não
as trato como ganho estatístico.

Também consultei apenas a disponibilidade local do provider, sem fazer chamada:
`provider_available()` retornou `False`. Assim, escolhas atuais do provider
continuam pendentes e não devem ser inferidas dos menus, das fixtures ou dos
smokes offline.

## Falha de provider coletivo não é decisão do ator — 24/09/2026

Uma auditoria do boundary compartilhado encontrou que falhas `LLMError`,
`ParseError` ou `ProviderCallError` em `interpret_domain_affordances` eram
convertidas em `maintain` com `source=rule`. No fluxo de comércio, esse receipt
podia ser interpretado como recusa deliberada da contraparte; no resumo anual
da seita, podia ser descrito como consolidação. Isso era autoria falsa, não uma
política aceitável de fallback.

Agora o intérprete lança `DomainDecisionFailed` sem criar decisão/receipt. A
exceção sobe pela fase, cujo checkpoint mensal já restaura o estado, e o loop
pausa com `required_decision_failed`, como já fazia para decisões obrigatórias
de Avatar. Test mode/offline continua podendo usar a política determinística;
resposta estruturada inválida continua sendo `llm_rejected`, não provider
indisponível. Eventos históricos em saves não foram reescritos.

O mesmo princípio foi aplicado ao boundary `single_choice`: no runtime normal,
falha de provider ou opção fora da lista não seleciona fallback (`ACCEPT`,
`REJECT` ou primeira opção) e propaga `SingleChoiceDecisionFailed`, que também
ativa a pausa do loop. Fallback configurado permanece para `test_mode`, onde é
explícito e marcado como `fallback`.

Verificação focal: `tests/test_domain_affordances.py`,
`tests/test_sect_annual_affordances.py`, `tests/test_sect_annual_rollback.py`,
`tests/test_required_decision_failed.py` e
`tests/test_institutional_commerce_vertical.py` mais
`tests/test_single_choice.py` passaram (`53 passed`); um teste material confirma
que falha durante troca de arma preserva o equipamento atual em vez de aceitar
automaticamente o item oferecido. A
regressão integrada confirma que falha da segunda seita reverte recrutamento,
tesouro, eventos e estados institucionais da primeira na mesma fase mensal.
Ruff nos dez arquivos tocados e `git diff --check` passaram. Não foi possível
executar pytest com o Python global por dependência ausente; a execução válida
usou `.venv` e `CWS_DATA_DIR=/tmp/cws-test-provider-failure`. Provider real
segue indisponível localmente, sem chamada feita.

Verificação adicional dos consumidores de `single_choice`: a classe `TestSpar`
e os testes de convite de seita, segredo, loot e tesouro passaram (`28 passed`).
O caso de Story de Spar tinha fixture obsoleta: preenchia o resultado sem o
evento-fonte que a cadeia agora exige e esperava somente Story, ignorando o
evento separado de relação. A fixture agora fornece a fonte e filtra o Story
tipado. O módulo completo de ações mútuas não foi validado; a execução agregada
parou nesse caso antes da correção e ficou sem progresso visível. Ruff padrão
nesse módulo reporta um `F841` preexistente em `res1` na linha 160; ignorando
somente `F841`, passou. `git diff --check` passou.

## Orçamento de decisões IA configurável no observatório — 24/09/2026

O config de mundo persistia `ai_calls_per_step=1` por padrão, e a interface só
permitia ligar/desligar IA. Como esse limite é compartilhado por todas as
consultas no avanço (não por instituição), um ciclo com vários atores podia
consumir a chamada inicial e pausar/reverter quando exigisse a próxima decisão.
O observatório agora permite alterar o orçamento com o mundo pausado, e o mesmo
comando persiste atomicamente `enabled` e o limite no save. A UI informa que
atingir o teto interrompe e reverte o avanço; não seleciona fallback. O limite
continua entre 0 e 256 no contrato; a interface oferece 1–256.

Verificação focal: contratos HTTP de habilitação/persistência/pausa passaram
(`3 passed` nos casos de IA selecionados) e o teste do app passou (`14 passed`),
incluindo alteração visual do limite e request HTTP resultante. Nenhum provider
foi chamado; `provider_available()` segue indisponível localmente. Isso remove a
falta de controle sobre o orçamento no frontend, não valida autonomia real nem
determina automaticamente o orçamento adequado para todos os atores de um
avanço.

## Proveniência de decisões da campanha — 24/09/2026

Decisões escolhidas pelo provider no contato armado e no aftermath eram gravadas
com `FactKind.DECISION`, mas com origem padrão determinística. Por isso o receipt
`ai_decision_interpreted` não era ligado à decisão em `decision_source`, embora
o owner executasse a affordance escolhida. A resposta do QG após boletim de
combate tinha o mesmo problema na retirada; no caminho `NO_ACTION`, ainda
persistia um ID sintético `maintain:<report>:<engagement>` em vez do valor
selecionado pelo provider.

Agora esses caminhos declaram `CausalOrigin.ACTOR_DECISION`, permitindo ao helper
comum anexar o receipt do provider e seu link causal. A decisão do QG continua
com ação sem efeito `maintain`, mas persiste `selected_affordance_id` como
`NO_ACTION`; a associação do receipt reconhece essa representação. A mesma
omissão de origem existia nas decisões provider de autorização política,
mobilização do QG, resposta política ao resultado, reencaminhamento/retirada do
QG e envio de suprimento para campanha. Elas agora também carregam autoria de
ator; recusas explícitas persistem `NO_ACTION` em vez de apenas a lista de opções
declinadas. O mesmo defeito foi corrigido na oferta de rito por personagem,
patrocínio institucional de rito e decisão individual de viagem.

Seis módulos focados passaram (`47 passed`): desescalada, aftermath, estratégia,
abastecimento da campanha, ritos de personagem e viagem. As regressões verificam
origem, `decision_source.kind=provider` e link ao receipt para escolhas
materiais; no QG também verificam a autoria do `NO_ACTION`. O teste de viagem
precisou elevar seu orçamento de fixture de 64 para 256, limite já aceito pela
configuração, porque decisões institucionais anteriores consumiam a cota
compartilhada antes da vez do personagem. Isso corrige proveniência em fixtures
com provider simulado; não prova consulta a provider real, fallback offline
nesses caminhos ou surgimento natural de campanha. Nenhum save real foi
alterado. A autoria nos demais domínios continua sem auditoria completa.

## Origem de decisões de auxílio e diplomacia — 24/09/2026

O auxílio institucional já registrava `decision_source` (`provider` ou
`routine-rules`) e ligava o receipt quando a escolha vinha do provider, mas
`_decide` deixava `causal_origin` no padrão determinístico. A função comum de
decisão diplomática fazia o mesmo, inclusive nos turnos provider e no fallback
determinístico do modo offline. Agora ambos registram `ACTOR_DECISION`; o
auxílio preserva seu marcador explícito de origem, enquanto o helper de eventos
liga decisões diplomáticas ao receipt provider imediatamente anterior.

Verificação focal: auxílio, intérprete/decisões, política diplomática e testes
de owner passaram (`52 passed`). As regressões exigem `ACTOR_DECISION` e, nos
casos provider, `decision_source` mais link ao receipt. A execução offline de
auxílio continua explicitamente marcada como `fallback/routine-rules`; nenhuma
chamada a provider real foi feita. Isso fecha a proveniência nesses dois
domínios, não a auditoria de todos os owners/fallbacks nem o gate de autonomia
econômica natural.

## Registro explícito de `NO_ACTION` nos turnos provider — 24/09/2026

Os caminhos revisados que recebiam `NO_ACTION` estavam encerrando o turno sem
registrar uma decisão do ator; permanecia apenas o receipt de interpretação.
Foi adicionado um helper comum que grava uma `DECISION` sem delta, com
`selected_affordance_id=NO_ACTION`, IDs das affordances recusadas e vínculo ao
receipt `ai_decision_declined` correspondente. Aplicado em auxílio, diplomacia,
abastecimento de campanha, viagem individual, oferta/patrocínio de rito,
decisões de criatura/tributo, contato armado e aftermath. `None` (sem escolha
disponível/retorno) não é convertido em decisão.

Verificação focal: oito módulos relacionados passaram (`59 passed`); após
adicionar uma asserção de origem e vínculo provider no caminho de contato
armado, o teste focal passou (`1 passed`). `git diff --check` passou. Ruff
continua reportando apenas `E402` preexistente em `campaign_supply.py` e
`E701` preexistentes em `diplomacy_policy.py`. A cobertura prova estes caminhos
com provider simulado; não prova provider real, todos os fluxos restantes ou
formação espontânea no mundo natural.

## Origem da decisão de emprego permanente offline — 24/09/2026

`record_permanent_employment_decision` já gravava `decision_source` com
`kind=fallback`, `policy=routine-rules` e a regra aplicada quando a contratação
era escolhida pela política offline. Porém, o evento `DECISION` ainda usava a
origem padrão determinística. Agora a decisão é marcada `ACTOR_DECISION`, sem
alterar a política, as condições de oferta ou os efeitos do owner; o payload
continua distinguindo fallback de provider.

Verificação focal: fallback de contratação, decisão provider com evidência de
meios de vida e escolha de staffing no menu institucional passaram (`3 passed`);
Ruff e `git diff --check` passaram. Isso fecha apenas a autoria desta decisão
offline, não prova autonomia econômica natural, uso de provider real ou que o
fallback escolheria corretamente em todas as trajetórias.

## Origem das escolhas econômicas de fallback — 24/09/2026

Uma varredura estática encontrou políticas que já gravavam
`decision_source.kind=fallback` / `routine-rules`, mas deixavam a origem causal
como determinística. Corrigi as decisões de fallback em provisões domésticas
(compra e consentimento/recusa do vendedor), migração e recuperação, objetivo
de abastecimento (frete/compra e resposta independente do vendedor),
contratação permanente, transição ocupacional, tarifa de exportação e serviço
de infraestrutura para `ACTOR_DECISION`. A classificação não transforma essas
políticas em provider/LLM: o payload continua dizendo `fallback` e não houve
mudança nas regras nem nos owners materiais.

Verificação: os sete módulos focados de provisões, migração, mercado bilateral,
tarifas, serviços de site, workforce e emprego permanente passaram (`102
passed`). Ruff passou ignorando `E402`/`E701` preexistentes nos arquivos
tocados e `F841` preexistente em `test_medieval_tariffs.py`; `git diff --check`
passou. A varredura mostra que o inventário geral de decisões ainda não está
fechado; não foi executado smoke econômico natural longo neste checkpoint.

## Autoria da decisão de investimento offline — 24/09/2026

`review_investment` escolhe um projeto somente no caminho offline, diante de
pressão material, equipe local, autoridade e recursos suficientes. A decisão
`expansion_decided` estava com origem determinística e sem origem declarada;
agora é `ACTOR_DECISION` e registra `decision_source=fallback`, política
`routine-rules`, regra `investment`. Não alterei o limiar nem criei expansão
automática fora das opções atuais.

Uma fixture com limitação de armazenamento percorreu a escolha e criou o
projeto. Testes focados de investimento e fundação passaram (`2 passed`); Ruff
passou ignorando `E701`/`E702` preexistentes em `test_medieval_industry.py`, e
`git diff --check` passou. Na revisão mais recente, a varredura AST encontrou
zero chamadas `record_event(..., fact_kind=DECISION)` sem origem explícita.
Isso fecha apenas a lacuna mecânica de origem omitida; a revisão semântica de
todas as origens continua necessária, pois autorização do owner não deve ser
confundida com escolha do ator.

## Proveniência das decisões de pesquisa — 24/09/2026

As decisões fallback para patrocinar pesquisa e aplicar conhecimento a uma
instalação, além da aceitação rotineira de trabalho do pesquisador, eram fatos
`DECISION` com origem determinística. Agora são `ACTOR_DECISION` e os caminhos
de rotina registram `decision_source=fallback/routine-rules`. A aceitação do
pesquisador dentro de uma seleção institucional por provider também ficava
explicitamente marcada como política determinística (`qualified_researcher_acceptance`);
naquele checkpoint, portanto, o pesquisador não recebia uma consulta provider
independente. O receipt `research_authorized` continua sendo autorização/proposta
interna do owner, não uma nova escolha de ator.

Verificação daquele checkpoint: projeto de pesquisa com save/load, política natural mensal e
compatibilidade de aplicação tecnológica passaram (`3 passed`). Ruff passou
ignorando `F401`/`F841` preexistentes em `test_medieval_research.py`;
`git diff --check` passou. A vertical de pesquisa/difusão e a agência de
consentimento do pesquisador continuavam incompletas no plano geral.

## Autoria em transferência de técnica e oferta de instrução — 24/09/2026

Os helpers `record_technology_sale_request`,
`record_technology_sale_acceptance` e `record_apprenticeship_offer` agora
marcam a decisão explícita do comprador, do vendedor e do especialista como
`ACTOR_DECISION`. Isso não cria consentimento implícito: os owners continuam
validando cada escolha independentemente.

Verificação daquele checkpoint: transferência bilateral paga de técnica com
persistência e instrução paga por especialista migrado passaram (`2 passed`).
Naquele momento, a instrução ainda era exercitada diretamente pelas fixtures e
não estava integrada ao calendário/menu; a integração posterior está registrada
na subseção seguinte.

### Oferta no turno individual e patrocínio no menu institucional — 24/09/2026

A oferta de instrução por especialista migrado agora pode aparecer no mesmo
turno individual agendado que já consulta affordances de rito. O personagem
recebe uma escolha limitada às opções recompostas de hoje, podendo selecionar
uma affordance ou `NO_ACTION`; uma recusa explícita fica registrada e a mesma
opção não é repetida sem nova evidência. A oferta não reserva trabalhadores,
estoque ou dinheiro e não concede conhecimento.

O patrocinador entrou como adapter no menu institucional mensal compartilhado.
O offer event permanece elegível em mês/dia posterior enquanto a affordance é
recomposta e materiais, autoridade, site e trabalhadores continuam válidos. O
owner ainda abre contrato datado sem pagar/conceder técnica na hora; a conclusão
material existente continua responsável por salários e difusão. O validador
agora exige a oferta do especialista em dia igual ou anterior ao início e a
decisão do patrocinador no próprio dia de início.

Verificação focal: 12 testes de apprenticeship e política de turno individual
passaram. A prova usa provider simulado e fixture preparada; não demonstra a
oferta surgindo numa trajetória natural, decisão por provider real, nem gate
econômico/escala de longo prazo. A lista de difusão tecnológica e o gate natural
continuam abertos.

## Autoria de comandos e publicação automática — 24/09/2026

`start_travel` e `start_practice` agora registram o comando explícito como
`ACTOR_DECISION`, com `actor_ref` do personagem e `decision_source=player`.
Publicações mensais de ofertas comerciais, relatórios de rota/fiscais e
assentamento continuam automáticas: os fatos `DECISION` correspondentes agora
declaram origem `DETERMINISTIC` e identificam a regra do owner `knowledge`, em
vez de sugerir que provider/personagem escolheu publicar. Os contratos e a
especificação de autonomia foram ajustados para expor essa limitação atual.

Verificação focal: engine, conhecimento de rota/assentamento, ofertas e cotação
tarifária passaram (`49 passed`); Ruff nos arquivos tocados e `git diff --check`
passaram. A varredura AST encontrou zero chamadas explícitas de `DECISION` sem
`causal_origin`, mas não substitui a auditoria semântica global nem o gate
natural longo.

O auditor causal também passou a verificar fonte em cada fato `DECISION` com
origem `ACTOR_DECISION`; se a fonte for `provider`, exige que o receipt
`ai_decision_interpreted`/`ai_decision_declined` correspondente esteja ligado à
decisão e concorde com ator e affordance selecionada; para `fallback`, exige
identificação de política e regra. Fixtures negativas cobrem fonte ausente e
fallback sem regra. No save natural de 120 dias, as
642 decisões de ator tinham fonte `fallback`, sem erros de fonte; o auditor
standalone retornou `ok=true`. A alteração é somente validação/auditoria: não
converte fallback em provider nem muda escolhas do mundo.

Verificação: auditoria causal, turno composto provider/NO_ACTION/erro e
abastecimento de campanha passaram (`20 passed`); Ruff e `git diff --check`
passaram.

## Revalidação causal offline após autoria — seed 73, 120 dias — 24/09/2026

O release gate natural do checkout atual foi rodado novamente sem provider,
com save e checkpoint no dia 120. Conservação, round-trip de save/load e
continuação passaram; o ledger tem 3.858 eventos. A auditoria retornou
`ok=true`, sem causas quebradas, transições `ACTOR_DECISION` sem decisão-fonte,
erros de autoria, Story material ou deltas de interpretação. Foram 63 eventos
materiais com origem `actor_decision`, zero interpretações LLM e zero chamadas
reais. No dia 120: 16 rações faltantes, saúde média 951,25, unrest 48,75 e zero
mortes por privação; o save final tem 2.269.184 bytes. Isso revalida a
integridade causal curta, mas não mede autonomia provider nem estabilidade
econômica de longo prazo. O resultado mantém pendente o gate de 480/3.600 dias;
não é certificado de economia resolvida.

## Proposta de pesquisa com resposta independente do pesquisador — 24/09/2026

No caminho com provider, escolher patrocínio deixou de criar um projeto e um
`research_accepted` sintético. A instituição registra uma proposta/autorização
engine-owned e agenda a resposta do pesquisador para o dia seguinte. No turno
individual compartilhado com rito e apprenticeship, ele vê técnica, local,
pagamento por trabalhador/unidade e patrocinador. As affordances são
transitórias e recompostas. O projeto só começa se o pesquisador selecionar seu
ID atual e o owner revalidar autoridade, pessoa, site, caixa, materiais e
conhecimento. Se a resposta perder validade, execução falha fechada e o mês
pode reverter; uma oferta que perdeu condições materiais recebe fato de lapse.
`NO_ACTION` não cria projeto. O caminho offline continua explicitamente
rotulado como `routine-rules`.

Ledger e agenda preservam a proposta pendente através de save/load. A decisão do
pesquisador e o início do projeto têm links para proposta, autorização e receipt
provider. Verificação focal: cinco módulos (`42 passed`) cobrindo pesquisa,
menu institucional compartilhado, apprenticeship, recrutamento e auditoria
causal. Ruff passou na implementação e nos testes, isolando findings
preexistentes (`E702` no estado e `F401`/`F841` em trechos dos testes); `git
diff --check` passou. A prova usa fixture e provider simulado; não é evidência de
provider real nem de formação espontânea numa trajetória natural.

## Contexto legível para prioridade de produção — 24/09/2026

O menu institucional composto agora explica escolhas concorrentes de prioridade
produtiva com nome da instalação/assentamento/produtos e termos materiais da
receita (entradas, saídas, capacidade, lotes/limitações observados, mão de obra
e salário). Também expõe a força de trabalho atualmente não comprometida pelo
owner Society, insumos das instalações próprias e saldo da folha própria, sem
identificadores internos. A leitura não desconta a folha do ciclo que acabou de
produzir; tampouco prevê o saldo depois de todos os demais owners agendados no
próximo ciclo. É uma leitura atual, não uma previsão completa de mão de obra.
Inclui somente a leitura datada que a própria instituição tem do assentamento,
com idade explícita; não apresenta estoques estrangeiros. Os recibos da leitura
local, grupos, folha e insumos informam a causalidade. IDs internos de estoque e
conta não são incluídos no contexto; o ID transitório selecionado também não
revela a conta.
O executor recompõe a affordance e continua a revalidar a instalação antes de
registrar a prioridade para o próximo ciclo. O contexto separa a prioridade
materialmente aplicada no ciclo anterior de uma eventual prioridade agendada e
mostra a próxima data de efeito, sem apresentar uma prioridade expirada como
atual. Nenhuma lei de produção ou política de fallback mudou.

Verificação focal: `tests/test_medieval_production_priority.py` passou (`7
passed`); a regressão percorre um ciclo: a folha paga no dia 60 reduz a
disponibilidade residual daquele ciclo, mas não é descontada da leitura atual
que orienta a próxima prioridade do dia 90. O relatório local e as fontes dos
grupos aparecem como causas da affordance. Ruff nos dois arquivos tocados e
`git diff --check` passaram. Isso prova contexto e autoria/evidência local desta
escolha, não decisão espontânea, provider real ou recuperação econômica natural.

## Pico hidrológico sustentado possível sem evento forçado — 24/09/2026

Auditei o perfil sazonal de `regional_overflow`: a lei exigia duas leituras
mensais consecutivas acima de 88, mas o perfil anterior permitia carga acima do
limiar em apenas um mês do ano. Logo, a enchente nunca poderia iniciar em uma
trajetória natural, apesar das fixtures com carga injetada. Ajustei somente a
janela sazonal para dois meses próximos do pico, mantendo variação determinística
por seed/mês/região, o limiar e a exigência de persistência. Isso torna o evento
possível, não obrigatório; não adiciona chuva por quota nem força danos em cada
mapa. A perda material continua sendo calculada pela definição engine-owned
`REGIONAL_FLOOD_SITE_INTERACTION`, com exposição, curva limitada e resistências.
Removi a constante local de dano máximo que já duplicava uma lei agora owned pelo
registro compartilhado.

Verificação: seed natural `14` percorreu os dias 210–240 sem monkeypatch, abriu
uma ocorrência somente após duas avaliações altas consecutivas na região 801 e
danificou naturalmente as Docas de Portovelho; o teste segue os links entre as
avaliações, o início da ocorrência e o delta de integridade. Seed comum segue
livre de enchente obrigatória. Uma projeção somente da fórmula
em 120 meses e oito regiões deu zero ocorrências para seed 73, duas para 101 e
duas para 137; isso mede a lei determinística, não simulação completa nem dano
material nesses seeds. A regressão de carga isolada e a prova de dano/observação/
reparo existente passaram, assim como um teste de dez anos sem overflow na seed
73 (`4 passed` em execuções focadas); Ruff e `git diff --check` passaram. Isto
prova uma cadeia hidrológica natural até dano material, preserva um mundo
tranquilo e cobre a lei sob carga sustentada; não fecha frequência/dano no gate
hidrológico/econômico completo de três seeds por dez anos.

## Leitura local da rota após dano natural às Docas — 24/09/2026

O teste natural da seed 14 agora acompanha a capacidade operacional da rota que
depende das Docas de Portovelho. O delta de integridade da enchente reduz a
capacidade derivada no owner Map; na mesma fronteira, o mantenedor recebe um
RouteReport datado de dia 240 cujo receipt cita a observação local do site e o
fato físico da rota. A leitura só é criada para proprietário/mantenedor com
SiteReport administrativo próprio do mesmo dia e se limita às rotas listadas
como dependências daquele site. Ela não é publicada nem entregue à instituição,
ao QG ou a terceiros. O auditor valida o receipt histórico referenciado, sem
depender do registro mutável do relatório mais recente.

Uma primeira execução do teste encontrou a ausência real desse relatório; após
a inclusão da observação local e sua validação causal, o teste natural passou.
Verificação focal consolidada: tests/test_medieval_route_knowledge.py,
tests/test_medieval_site_services.py, os três testes de manutenção no menu
civil e tests/test_medieval_regional_overflow.py — 39 passed; Ruff passou
nos três arquivos Python alterados e git diff --check passou.

Isto fecha, em uma trajetória natural, enchente → dano material → capacidade
de rota reduzida → leitura privada do mantenedor. A mesma trajetória também
passou com um provider de teste que escolhe a affordance atual de reparo: isso
criou somente o projeto em estágio waiting, sem restaurar integridade nem
consumir material no ato da decisão. Essa prova revelou que organizações
mantenedoras não eram incluídas no conjunto de atores do turno institucional
mensal; agora entram somente quando têm affordance atual de reparo ou
reativação.

Ao avançar mais um ciclo, o owner não reparou sem custo: o lote ficou blocked
por falta de stone, e a instalação manteve a integridade danificada. O projeto
criou o objetivo causal inputs:<stock>:stone; o fluxo desta seed ainda não
comprou nem entregou esse material. Isso deixa aberto o próximo elo: validar se
os menus bilaterais existentes conseguem levar esse objetivo a uma entrega
física, sem subsídio ou estoque criado pelo teste.

Verificação após discovery de atores: os seis testes focais de enchente/reparo,
NO_ACTION e escolha de manutenção passaram; depois da asserção adicional do
bloqueio por pedra, o teste integrado provider simulado também passou novamente.
Ruff e git diff --check passaram. O provider foi simulado, não real; não prova
escolha espontânea, entrega da pedra nem campanha/QG/reino reagindo ao atraso.
Fallback offline, seleção simulada e provider real continuam evidências
distintas.

## Reparo após enchente em smoke natural — seed 14, 480 dias — 24/09/2026

Um smoke natural offline sem decisões injetadas, `CWS_DATA_DIR` isolado e
checkpoints a cada 120 dias percorreu a mesma cadeia em uma trajetória única.
No dia 240, a segunda leitura hidrológica alta iniciou o overflow da região 801
(`event:7251` → `event:7252`); o fato `event:7253` reduziu a integridade das
Docas de Portovelho de 0,99 para 0,915. O mantenedor Liga das Barcas observou o
dano (`event:7388`) e a rota dependente, cuja capacidade operacional lida caiu
de 324 para 296,46 (`event:7506`). A política offline `routine-rules` registrou
uma escolha explícita de manutenção (`event:8012`) baseada no relatório próprio;
o owner iniciou o projeto (`event:8013`).

O projeto só terminou no dia 330: `event:11354` registra consumo de stone,
tools e wood, progresso de 100 para 116 permille e integridade do site de 0,985
para 1,0. O save final confirma o projeto completo e o site íntegro. O gate
natural terminou no dia 480 com conservação, save/load e auditoria aprovados em
17.764 eventos; houve zero chamadas reais, zero interpretações LLM, zero causas
quebradas, zero erros de autoria e zero deltas por Story/interpretação. A saída
é reproduzível por:

```bash
CWS_DATA_DIR=/tmp/cws-medieval-natural-seed14-check \
  .venv/bin/python tools/medieval_release_gate.py \
  --seeds 14 --days 480 \
  --output-dir /tmp/cws-medieval-natural-seed14-check/gate \
  --checkpoint-days 120
```

Isto comprova a cadeia física natural com a regra offline explícita de
manutenção; não comprova escolha espontânea por provider real, nem campanha/QG
reagindo à perda temporária de capacidade. A economia terminou com falta
mensal 128 e saúde média 881,62; não é prova de resiliência econômica nem
substitui o gate final de três seeds por 3.600 dias.

## Compra bilateral fecha o ciclo de reparo das Docas — 24/09/2026

A trajetória da seed 14 agora consegue atravessar o bloqueio de insumos sem
introduzir recursos: a Liga das Barcas é compradora `organization`; o objetivo
de reparo abre opções de compra de pedra e ferramentas a partir de ofertas e
relatórios de rota conhecidos. O owner recompõe quantidade, preço, conta, tarifa
e rota. A organização pede a compra, e cada vendedor continua precisando aceitar
separadamente. O pagamento abre frete físico; chegada de material permite um
lote de reparo posterior, gradual e limitado pelo owner.

A reprodução revelou uma falha de ordenação: a agenda consulta polities antes de
organizations, e os pedidos de compra só eram válidos no mesmo dia. Assim, um
vendedor polity já havia usado seu turno antes do pedido da Liga. A agenda agora
faz uma segunda consulta somente para vendedores que receberam um pedido novo
naquele boundary, expondo os termos relevantes da venda; não há transferência
sem seleção do vendedor. Os receipts detalhados `buy_decided`/`sell_decided`
propagam a origem da seleção e o ID canônico escolhido, para que autoria continue
navegável após materializar os termos.

Verificação focal: a enchente ocorre naturalmente na seed 14; o mock de provider
seleciona reparo e compras, e seleciona o aceite independente dos vendedores.
Pedra e ferramentas chegam por frete; o reparo consome material e aumenta a
integridade no horizonte até dia 390. Save/load e auditor causal do save final
passaram. O lote focal — integração enchente/reparo + política bilateral de
mercado + auditoria causal — passou (`6 passed`). Isto é uma fixture dirigida por
seleções simuladas, não provider real ou emergência autônoma das escolhas. Os
outros gates econômicos/naturais e o smoke de 3.600 dias seguem pendentes.

## Contexto informado para decisões de manutenção — 24/09/2026

O menu institucional compartilhado antes descrevia reparo apenas como
“autorizar o reparo da instalação <id>”, apesar de a escolha iniciar um
compromisso material. A família `infrastructure_maintenance` agora fornece ao
mantenedor, para cada affordance atual, o nome/tipo do site, relatório próprio e
datado de integridade, permille faltante, termos do lote padrão (materiais,
trabalhadores, salário e recuperação) e somente seus próprios saldos locais e
de tesouro. Também expõe leituras datadas de capacidade/tempo das rotas do site
que o ator já conhece; não consulta o mapa para ensinar capacidade atual, não
inclui handles internos de stock/account nem inventário alheio. A affordance,
as quantidades executadas, os custos efetivos e cada lote continuam sob
recomposição e validação dos owners.

Verificação: teste no limite JSON do provider confirma alinhamento entre
affordance e contexto, termos idênticos ao blueprint/estoque/conta próprios,
ausência de IDs privados e correspondência das leituras de rota a reports
datados. Com as regressões de elegibilidade, reparo gradual e overflow natural,
quatro testes focados passaram; Ruff e `git diff --check` passaram. O provider
foi simulado: isto melhora a decisão informada, mas não comprova escolha real
nem autonomia de longo horizonte.

## Diagnóstico de subsistência no mesmo smoke — seed 14, dia 480 — 24/09/2026

O mesmo save termina com falta mensal 128, saúde média 881,62 e zero mortes por
privação. O maior foco é Campomanso: falta 111, saúde 903. O receipt canônico
`event:16947` (`subsistence_resolved`) atribui os 111 não comprados a grupos
específicos sem saldo suficiente: 87 artesãos orcs, 9 artesãos elfos, 8 soldados
humanos, 2 soldados elfos, 2 dependentes humanos, 2 soldados orcs e 1 soldado
anão. Isso é evidência de acessibilidade/renda para aquela fronteira, não prova
de que desemprego seja a causa-raiz de toda a crise.

No estado final, Auren tem zero opções atuais de contrato novo e duas opções
válidas de construção de oficina (Campomanso e Pedra Clara); também há opções de
revisão de staffing para contratos agrícolas existentes. O smoke está em
`routine-rules`, sem consultas reais, e essas opções não foram escolhidas no
run. Logo, o próximo diagnóstico precisa acompanhar se a proposta de oficina
entra no menu do ator e comparar provider/`NO_ACTION` com os efeitos materiais;
não há base para alterar preços, criar emprego automaticamente ou injetar renda.

## Frete após dano hidrológico natural — 24/09/2026

Adicionei um teste integrado enxuto à regressão de overflow: a seed 14 chega ao
dano natural das Docas de Portovelho; depois, uma decisão auditável abre frete
real pela rota afetada. No despacho seguinte, o owner lê a capacidade reduzida
do mapa e respeita também o fluxo concorrente daquele dia: de 324 unidades
solicitadas, 294 partem e 30 permanecem em espera. O `cargo_departed` aponta ao
evento de dano da enchente. Nenhum material de origem foi criado pelo teste; o
destino é apenas um depósito vazio de fixture.

Comando focado: `XDG_DATA_HOME=/tmp/cws-test-data
CWS_DATA_DIR=/tmp/cws-test-data/world .venv/bin/pytest -q
tests/test_medieval_regional_overflow.py::test_natural_overflow_reduces_the_next_real_freight_dispatch`
— `1 passed`, incluindo save/load e auditoria causal do save final. Também
validei os testes da oficina/NO_ACTION, cadeia simulada oficina→linha→salário e
as provas separadas de overflow e interferência de criatura/campanha (`4
passed`). Isto demonstra enchente→capacidade→frete físico. A seção seguinte
acrescenta uma coluna preexistente e o despacho posterior de suas rações pela
rota danificada; continua faltando a decisão estratégica do QG/comandante. A
escolha de oficina ainda foi testada com provider simulado, não real.

## Campanha ativa atravessa enchente e precisa de suprimento — 24/09/2026

Uma coluna Auren parte de Campomanso para Portovelho antes do overflow, usando
os relatórios de rota datados e consumindo soldados, rações e salário reais. Ela
chega ao destino e continua presente quando a segunda leitura hidrológica do
dia 240 danifica as Docas; o relatório atual de Auren passa a refletir a
capacidade reduzida. A necessidade de ração da coluna abre no dia 246. No turno
seguinte, o QG atual de Auren recebe suas leituras de rota e um provider
simulado escolhe a affordance de suprimento ainda válida.
Um frete concorrente com prioridade anterior ocupa a vazão do mesmo rio e parte
da carga da campanha permanece em espera. O receipt de carga liga a limitação ao
dano natural. O teste inclui save/load e auditoria causal do save final.

Comando focal: `XDG_DATA_HOME=/tmp/cws-test-data
CWS_DATA_DIR=/tmp/cws-test-data/world .venv/bin/pytest -q
tests/test_medieval_regional_overflow.py::test_natural_overflow_limits_active_campaign_rations_on_its_known_route`
— `1 passed`. Isto prova uma composição interdomínio durante uma campanha já
ativa, usando decisões explícitas e provider simulado. Ainda não prova provider
real nem que o QG reconhece atraso e decide revisar, desviar ou retirar a
campanha; esse próximo elo de agência segue aberto.

## QG revisa bloqueio após receber seu boletim de rota — 24/09/2026

Um `route_bulletin` novo, entregue ao próprio ocupante do QG e sobre a perna
onde uma coluna de plano ativo está parada, agora antecipa a revisão estratégica
que normalmente aguardaria o intervalo periódico. O boletim apenas agenda uma
consulta no dia seguinte: não escolhe rota e não altera o plano. O QG recompõe
desvio/retirada a partir dos próprios relatórios atuais; o executor valida a
rota física no momento da ação.

A regressão integrada de interferência já escolhe o desvio depois do bloqueio,
mas agora usa a situação de agenda real, resolve o novo dia de parada e confirma
que a transição tem causa no hold e nos relatórios de rota pessoais do QG. A
escolha provider é simulada. Este caminho prova resposta a rota fechada por
criatura; **não** prova resposta estratégica a vazão reduzida/atraso parcial de
frete após enchente, nem provider real. Checagem focal: Ruff passou e
`test_drake_closure_holds_a_mobilized_column_and_food_against_open_route`
passou (`1 passed`).

## Despacho de ração é uma decisão do QG — 24/09/2026

O provider de campanha agora decide como o titular atual do QG, distinto da
instituição que possui o estoque e paga o frete. O contexto inclui somente as
leituras de rota próprias do QG relevantes às opções, com dia observado,
capacidade, tempo de viagem, fluxo e receipt de evidência. A decisão aponta
`actor_ref` ao oficial e `institution_ref` ao beneficiário. O despacho revalida
no owner o QG e sua autoridade operacional, autoridade de suprimento da
instituição, estoques próprios, opção atual e rota física. Relatórios de rota
que embasaram a escolha entram nos links causais; `NO_ACTION` usa os mesmos
fatos do receipt de recusa.

Comprovação focal: todos os testes de `test_medieval_campaign_supply.py` mais a
fixture enchente→rota→suprimento de campanha — `7 passed`; Ruff e
`git diff --check` passaram. A decisão ainda usa provider simulado. Esta etapa
faz o QG assumir o despacho operacional, mas não adiciona escolha de retirar ou
redirecionar uma coluna presente com carga parcialmente aguardando. Essa resposta
estratégica à congestão natural continua pendente.

## Um atraso de suprimento gera uma nova leitura, sem duplicar carga — 24/09/2026

O owner de logística pode reter parcialmente ou por inteiro um frete de campanha.
Se a coluna continuar abaixo do limiar depois de um `cargo_delayed`, sua nova
observação de necessidade cita o atraso material e abre uma consulta distinta ao
QG. A opção calcula espaço da bagagem depois de descontar todo o alimento que já
está em trânsito; a decisão continua sendo somente outro envio real, com estoque
e rota atuais. O aviso inicial só fica `fulfilled` quando todo o pedido chegou,
não no primeiro lote parcial.

Na fixture focal, o QG escolhe essa remessa adicional quando ela continua
possível; o prompt nomeia a própria leitura de rota e o atraso, e a decisão cita
ambos. Na trajetória com overflow natural, frete concorrente ocupa toda a vazão:
a campanha aguarda, a coluna cria aviso causal de seguimento e, na revisão do dia
seguinte, nenhuma nova remessa ainda passa a revalidação de prazo/estoque/rota.
O owner não envia comida por fallback. Esse resultado prova observação e
recomposição; não prova escolha espontânea em mundo natural, provider remoto ou
retirada estratégica. Também não altera nem redireciona o pedido original.

Validação focal: `tests/test_medieval_campaign_supply.py` e
`tests/test_medieval_regional_overflow.py::test_natural_overflow_limits_active_campaign_rations_on_its_known_route`
passaram em conjunto (`9 passed`); Ruff passou. Save/load e auditoria causal do
save final permanecem incluídos na fixture natural.

## Journal incremental para gates naturais longos — 24/09/2026

O smoke `tools/medieval_autonomy_smoke.py` agora aceita `--progress-jsonl`.
Cria um arquivo novo sem sobrescrita e grava/força a cada registro: parâmetros
de início, cada fechamento mensal, cada checkpoint depois de save/load
equivalente e a conclusão. Se uma exceção interrompe o avanço, registra dia,
quantidade de eventos e último checkpoint retomável antes de propagar a falha.
Assim, os checkpoints permanecem acompanhados pela telemetria mensal mesmo se o
processo parar; o journal de cada continuação é separado e aponta ao save de
origem. Isso não muda regras da simulação e não equivale a um gate verde.

O smoke de recuperação também não exige que uma única política de fixture
execute mercado e emprego além do alívio: o ator tem um turno por boundary e
uma affordance legítima pode reduzir a pressão antes das demais escolhas. A
fixture ainda precisa demonstrar ao menos uma resposta material composta, com
conservação e auditoria causal; uma categoria não é quota narrativa.

Validação focal: `CWS_DATA_DIR=/tmp/cws-progress-jsonl-test
.venv/bin/python -m pytest -q tests/test_medieval_autonomy_smoke.py` —
`22 passed`. Ruff e `git diff --check` passaram. O primeiro teste via Python do
sistema não coletou por ausência de `omegaconf`; o teste no ambiente virtual
inicialmente encontrou uma asserção obsoleta sobre o primeiro passo diário e
expectativas de categorias de ação fixas. Ambas foram ajustadas à semântica
atual. Ainda não rodei o gate natural de dez anos com este journal.

## QG decide após atraso de suprimento resolvido — 24/09/2026

Quando um aviso de campanha ligado a `cargo_delayed` chega a `fulfilled` e a
carga real entra na bagagem, `load_campaign_baggage` antecipa para o dia
seguinte a revisão de um plano ainda mobilizado. Com relatórios próprios e
atuais, o QG pode escolher uma rota conhecida para encerrar a campanha ou
responder `NO_ACTION`. Uma parcela física ainda pendente bloqueia a opção; um
aviso ainda aberto pode ser encerrado como `lapsed` pela própria decisão de
retirada. O owner recompõe novamente a opção, exige a autoridade do QG e da
instituição, revalida bagagem e rota física, inicia a marcha de retorno e
atualiza o plano como `withdrawn`; a decisão e a transição preservam os links
para atraso, avisos e relatórios. Nenhuma carga é teleportada ou descartada.

A prova cobre duas partes. Uma fixture de decisão usa um aviso sintético já
resolvido para confirmar retirada e bloqueio por pedido aberto. Outra fixture
integrada abre uma remessa por `open_order`, registra `cargo_delayed` no owner
logístico, cria o aviso causal de seguimento, entrega/carrega a remessa seguinte,
resolve a carga original pendente e então executa o turno agendado do QG. A
escolha encerra a campanha, inicia o retorno físico, liga decisão/movimento/plano
ao receipt de atraso e sobrevive a save/load. Não é uma trajetória natural: a
pressão na reserva e a escolha provider são controladas pela fixture. Provider
remoto e enchente natural levando uma campanha ativa até QG manter/retirar ainda
não foram validados.

Validação: `tests/test_medieval_strategy_response.py` e
`tests/test_medieval_campaign_supply.py` — `26 passed`; Ruff e
`git diff --check` passaram. Nenhuma alteração foi commitada ou enviada.

## Proveniência da oferta de instrução — 24/09/2026

Depois que `record_event` passou a exigir fonte auditável para toda decisão de
ator, a oferta de instrução por especialista migrado ainda não propagava o
receipt do provider nem seu ID entre as causas. O caminho individual agora passa
`decision_source=provider` e inclui o receipt de interpretação como causa do
evento `apprenticeship_offered`; chamadas diretas do helper precisam declarar
explicitamente sua fonte, usando `api` nas fixtures. O ledger permanece
estrito: nenhuma validação foi enfraquecida.

Validação isolada em `CWS_DATA_DIR=/tmp/cws-tech-chain-tests`:
`tests/test_medieval_apprenticeship.py`, `tests/test_medieval_technology_sale.py`
e `tests/test_medieval_research.py` — `34 passed`; Ruff nos três arquivos
alterados passou. A primeira execução isolada expôs cinco falhas de autoria,
corrigidas nesta mudança. Isto comprova a regressão de proveniência e os fluxos
focais existentes; não é prova de provider remoto, escolha espontânea nem
difusão natural em horizonte longo. WIP permanece sem commit/push.

## Planos de abastecimento bloqueados preservam a causa — 25/09/2026

Um smoke natural do schema atual expôs duas transições materiais
`supply_plan_updated` sem causal links. Ambas criavam um plano `blocked` por
falta de relatório atual para materiais de reparo, embora o projeto de reparo
fosse a origem canônica dessa necessidade. A política agora liga a atualização
aos receipts dos projetos de reparo, instalação, expansão ou pesquisa que
originam uma necessidade de insumo. Se não existe projeto/fato-fonte registrado,
ela não cria um novo plano material; uma revisão de plano existente pode citar
sua transição anterior.

Uma regressão focal confirma que a falta do relatório produz estado bloqueado
com links à decisão e ao último receipt do reparo. O smoke natural offline
seed 73/dia 120 repetiu conservação, checkpoints nos dias 60/120, save/load e
continuação ao dia 121: 3.859 eventos, falta mensal 16, saúde média 951,25,
zero mortes por privação. Auditoria causal final `ok=true`, sem causas quebradas,
erros de autoria/fonte ou efeitos materiais de Story/interpretação; os receipts
`supply_plan_updated` passaram de 143/145 para 145/145 com causal links. Isso é
prova de integridade em horizonte curto, não recuperação econômica, provider
real ou gate de 3.600 dias. A regressão nova e o teste existente de reparo
passaram (`2 passed`); Ruff e `git diff --check` passaram. Artefatos em
`/tmp/cws-procurement-causal-seed73-120*`; WIP sem commit/push.

## Autoria na cópia de técnicas — 25/09/2026

O owner que abre trabalho pago para copiar uma técnica agora exige um fato
`DECISION` do ator no dia corrente, com payload exato da affordance recomposta;
uma cópia de ID/decisão sem autoria falha antes de alterar conhecimento, caixa
ou projeto. A regressão conserva o fluxo válido de trabalho e save/load. A
primeira execução revelou um import ausente no guard e a fixture de roubo
tecnológico ainda usava uma decisão de expansão sem origem auditável; ambos
foram corrigidos sem relaxar o validador.

Verificação focal de transferência/aplicação de técnicas:
`tests/test_medieval_technique_copy.py`, `test_medieval_technology_theft.py`,
`test_medieval_technology_sale.py`, `test_medieval_technology_training_chain.py`
e `test_medieval_technology_sighting.py` — `20 passed`; Ruff nos arquivos
alterados e `git diff --check` passaram. Isto fecha autoria nesse recorte, não
a auditoria transversal dos owners, escolha de provider real ou gate natural
de horizonte longo. WIP permanece sem commit/push.

## Consentimento bilateral em provisões de coortes — 25/09/2026

Os owners de compra e venda de provisões domésticas agora exigem decisão atual
e autoria do ator nas duas pontas. Intenções internas de compra só entram no
menu do vendedor quando sua causa remonta à escolha atual da coorte; o executor
final também segue os receipts intermediários até decisões reais de comprador
e vendedor. Seleções determinísticas copiadas, mesmo com payload idêntico, não
movem estoque nem moeda. O `routine-rules` offline continua explícito como
fallback e seus eventos carregam essa origem.

Validação focal: `tests/test_medieval_household_provisioning.py` — `15 passed`,
incluindo mutação zero quando falta autoria em qualquer lado e rejeição de
affordance copiada nos adapters; Ruff e `git diff --check` passaram. Isto fecha
autoria e consentimento desta compra agregada, não autonomia econômica da
população nem resiliência natural de longo prazo. WIP sem commit/push.

## Autoria da prioridade produtiva — 25/09/2026

O owner que define a precedência produtiva agora rejeita um evento `DECISION`
com payload correto se ele não tiver origem `ACTOR_DECISION`. A prioridade
continua sendo só uma intenção para o próximo ciclo; produção e alocação de
trabalho permanecem com Economy. A regressão cobre a cópia determinística sem
mutação e preserva a aplicação material posterior após save/load.

Verificação focal: `tests/test_medieval_production_priority.py` — `8 passed`;
Ruff nos recortes de autoria trabalhados e `git diff --check` passaram. Isto
fecha a autoria deste owner, não prova que o provider escolherá prioridades
úteis nem que a economia natural ficará resiliente. WIP sem commit/push.

## Autoria ao estabelecer e retirar controle territorial — 25/09/2026

Os owners de controle territorial agora exigem decisão atual com origem
`ACTOR_DECISION` ao estabelecer ou retirar o mandato. A validação de
`SocietyState` também confere a origem da decisão persistida, impedindo que um
save valide controle baseado em payload determinístico copiado. Os testes
cobrem ambos os comandos sem alteração de estado e mantêm ocupação,
administração e presença militar independentes do mandato.

Verificação focal: `tests/test_medieval_siege_campaign.py` e
`tests/test_medieval_force_training.py` — `25 passed`; Ruff e `git diff --check`
passaram. O teste de treinamento também confirmou a autoria exigida pela
validação persistente já existente nessa mesma classe. Isto não prova
campanha espontânea ou provider real. WIP sem commit/push.

## Autoria do pagamento de suborno — 25/09/2026

O fluxo de suborno aceitava uma proposta, mas o pagamento falhava: o adapter
criava um receipt `DETERMINISTIC` sintético de autorização e o encaminhava ao
owner de obrigações, que exige a decisão `ACTOR_DECISION` atual. Removi essa
autorização intermediária. O executor agora recompõe e valida a affordance e
encaminha a decisão original até o receipt da transferência; o receipt mantém
link causal direto à escolha do pagador. Uma decisão determinística copiada,
mesmo com payload idêntico, é rejeitada antes de qualquer alteração material.

Verificação focal: `tests/test_medieval_bribery.py` — `7 passed`; Ruff nos dois
arquivos alterados e `git diff --check` passaram. Isso fecha a autoria deste
owner e sua regressão, não a auditoria transversal nem o provider real. O WIP
continua sem commit/push.

## Triagem da auditoria causal do save de 720 dias — 25/09/2026

Reauditei, sem modificar, o artefato anterior
`/tmp/cws-finalization-natural-seed14-720.mws`. Resultado estrutural:
`ok=true`, 26.423 eventos, 19.156 transições materiais, 412 materiais com
origem de ator, zero causas quebradas, erros de autoria/fonte, Story material
ou interpretação material. O inventário detalhado, porém, encontrou eventos
materiais sem links: observações de ecologia/hidrologia/rota/sítio, uma alocação
inicial de renda doméstica e uma `production_completed` inicial (event:19, dia
30). A primeira produção usa estado de bootstrap cujas instalações, contas,
sítios e estoques não têm receipts anteriores; ligar a um evento não relacionado
seria uma causa falsa. Esse é um ponto pendente da autoria da inicialização, não
um erro detectado pelo validador atual. O save antecede WIP posterior e serve
somente para priorizar auditoria; não certifica o checkout atual.

## Premissas raiz explícitas no Why — 25/09/2026

Fechei a classificação da lacuna de bootstrap sem gerar um evento histórico
fictício. Quando um fato determinístico depende de uma condição estabelecida na
criação do mundo e ainda não há um evento-pai, seu `causal_payload` agora declara
`root_premise` com tipo, domínio, referências aos owners e dia. Isso cobre a
primeira produção, o bootstrap opt-in de renda doméstica, primeira observação de
instalações/rotas, avaliação hidrológica inicial e ciclo ecológico inicial. A
Crônica mostra “Origem na premissa inicial” nesse caso e mantém “Nenhuma causa
anterior registrada” para recibos que não declaram uma raiz.

O auditor causal valida o formato da raiz e agora considera inválida qualquer
transição material sem evento-pai nem raiz explícita (eventos de origem externa
continuam com contrato próprio). O smoke natural do checkout atual, seed 14 por
120 dias, sem provider, passou conservação, dois checkpoints de 60 dias,
save/load, continuação e auditoria: 3.839 eventos, 2.738 transições materiais,
152 roots (151 `world_generation`, 1 `scenario_bootstrap`), zero raiz inválida,
transição material sem root/link, causa quebrada, erro de autoria, Story
material ou interpretação material. O save final teve 2.265.088 bytes, pico RSS
~160 MB e ~8,17 GiB livres. Métricas ao dia 120: saúde média 951,25, unrest
48,75, falta mensal 16 e zero mortes por privação; a pressão econômica
localizada continua aberta e o provider real não foi chamado.

Verificação: 40 testes focados de renda, observação local, conhecimento de rota
e auditoria passaram; os três casos pendentes da primeira seleção (decisão
fiscal com save/load, campanha sob rota danificada e frete após inundação)
passaram numa repetição focal (`3 passed`); Crônica `4 passed`, type-check,
Ruff e `git diff --check` passaram. Uma seleção combinada anterior teve cinco
falhas em fixtures com decisões determinísticas sendo usadas como se fossem
decisões de API; as fixtures foram corrigidas para declarar autoria e os casos
relevantes foram rerodados. Este gate de quatro meses não substitui os smokes
finais de três seeds por 3.600 dias. WIP continua sem commit/push.

## Smoke natural offline de 720 dias e caixa da economia — 25/09/2026

No checkout atual, retomei o save da seed 14 no dia 120 e rodei até o dia 720,
sem provider real (`routine-rules` offline). O journal registrou 26.423 eventos;
os checkpoints intermediários passaram conservação e save/load. A auditoria do
save final passou com 19.156 transições materiais, 153 `root_premise`, zero
transições materiais sem raiz/link, causas quebradas, erros de autoria,
DECISION sem fonte, Story material ou interpretação material. Save final:
7.987.200 bytes; duração: 192,58 s; pico RSS observado: ~487 MB. É evidência
para esta seed e execução, não o gate de três seeds por 3.600 dias.

No dia 720: população 10.931, falta alimentar agregada 506, saúde média 674,75,
unrest médio 145, zero mortes por privação, 128 migrações acumuladas, 69 pedidos
de ajuda e 66 cumprimentos, 59 compras de mercado. Campomanso mostra a diferença
entre disponibilidade e acesso: estoque público de 22.461 alimentos coexistia
com falta 449, e sua produção agrícola terminou limitada por `payroll_funds`.
As contas compartilhadas também carregavam compromissos mensais de emprego
superiores ao saldo final: Auren 3.124/802, Escárlia 3.754/2.667 e Valedouro
2.108/1.577 (compromisso corrente/saldo). É uma fotografia do estado, não
projeção nem prova de comportamento de IA. Como contratos são liquidados antes
da produção e compartilham a conta das instalações, a prioridade agora é
seguir caixa inicial, folha paga, recebimentos, produção limitada e acesso das
coortes em ciclos consecutivos. Sem balanceamento artificial: não subsidiar,
alterar preço nem suspender contratos automaticamente. Provider real não foi
consultado; esta execução usa somente a política offline explícita.

O smoke ganhou um read model `monthly_metrics.payroll_liquidity` por conta de
folha compartilhada: saldo, teto dos contratos, capacidade máxima das
instalações, folha realmente paga hoje, resultados dos contratos revisados e
linhas limitadas por caixa. Ele é descritivo, não altera owners e identifica
explicitamente tetos como limites, não previsões. No snapshot, Campomanso tinha
11.619 de caixa doméstico agregado, mas estimava 449 rações públicas
inacessíveis; portanto o agregado de moeda não explica sozinho quais coortes
conseguem comprar. Regressão focal de métricas de acesso/liquidez passou
(`2 passed`) e confirmou que a projeção não muta o mundo. O próximo gate deve
persistir esses valores no journal mensal e comparar ciclos sucessivos.

## Continuação da seed 14 até o dia 1.200 — 25/09/2026

Retomei `/tmp/cws-plan-current-seed14-720.mws` e avancei 480 dias em modo
offline (`routine-rules`, sem provider). Checkpoints 840/960/1080/1200 passaram
conservação e save/load. No dia 1.200, o save tinha 47.431 eventos, 36.671
transições materiais, 153 raízes, zero materiais sem raiz/link, causas
quebradas, erros de autoria, DECISION sem fonte, Story material ou interpretação
material. Save final: 13.258.752 bytes; execução: 443,24 s; pico RSS:
817.827.840 bytes. Auditoria `ok=true`; isso continua sendo um horizonte curto,
não o gate 3 seeds × 3.600 dias.

Resultado econômico/social: população 10.831, 100 mortes por privação no trecho,
saúde média 338,88, unrest 474,75 e falta agregada 509 no ciclo final. Os totais
no estado são 114 pedidos/108 cumprimentos de ajuda, 153 migrações, 100 compras
de mercado, 27 contratos de emprego e 90 transições ocupacionais. Em Campomanso,
449 rações de falta persistiram durante oito ciclos (dia 990–1200), mesmo com
estoque público caindo de 16.795 para 7.535; saúde caiu de 264 para 0. O receipt
do último ciclo aponta 338 rações não compradas do grupo de agricultores anões
e outros grupos sem saldo; esse grupo tinha 332 pessoas no snapshot depois que
as mortes do ciclo foram aplicadas.

No menu recomposto no dia 1.200, não havia nova contratação permanente ou obra
local válida nesses assentamentos; havia affordances para reduzir/suspender
contratos agrícolas existentes em Campomanso. Isso mostra uma possibilidade
causal de decisão, mas não que ela seja a resposta certa nem que IA a escolheria.
O modo offline não permite atribuir omissão a um provider. Os tetos de folha
corrente não são gastos realizados: Auren 3.124/691, Escárlia 5.486/7.014 e
Valedouro 3.332/7.101 (teto/saldo). A próxima análise precisa rastrear caixa,
pagamento efetivo, produção limitada e renda de cada coorte; não cortar
contratos, subsidiar, mudar preços ou criar emprego automaticamente.

## Correção do prazo de demanda da criatura — 25/09/2026

No ciclo da agenda, a revisão da criatura ocorria no próprio `due_day`, mas os
owners só habilitavam dano/ataque após o prazo; não existia outra revisão
agendada no dia seguinte. A enumeração, a validação de execução e o contexto da
criatura agora usam `due_day <= hoje`. Uma regressão end-to-end no
`MedievalSimulator` confirmou que, no dia exato, o provider-stub pode escolher
ataque populacional, o owner altera a coorte e expira a demanda com decisão,
delta e causa; sem essa escolha, o prazo não fecha a rota nem aplica retaliação.
Os módulos de autonomia, criatura e interação mágica passaram `23` testes;
Ruff focado e `git diff --check` passaram. Isso não comprova a vertical inteira
nem retaliação espontânea em smoke natural.

Uma segunda fixture do mesmo ciclo agendado escolhe dano a uma instalação
aquática. A capacidade operacional da rota cai; o relatório privado do
mantenedor aponta causalmente para o dano; e a engine recompõe uma affordance
válida para autorização do reparo. O mantenedor escolhe e executa reparo nessa
trajetória: uma consulta provider-stub independente autoriza o projeto, e a Economy
consome materiais e trabalho até restaurar a integridade e capacidade da rota.
A fixture começa com os materiais de reparo provisionados, sem atribuir esse
estoque ao dano ou à criatura. O recorte combinado de autonomia, criatura e
interação mágica tem `23` testes focados; a prova isolada do owner em
`tests/test_medieval_infrastructure.py::test_damage_is_observed_repaired_gradually_and_the_route_recovers`
também passou. Ainda não há seleção OAuth real nem formação espontânea dessa
cadeia em smoke natural.

Também foi corrigido o caminho de recuo: restringir a rota expirava a demanda,
mas não criava nova revisão; com a criatura já faminta e sem novos cruzamentos,
`withdraw` nunca voltava ao menu normal. Agora a restrição agenda uma única
decisão no dia seguinte. O engine prova restrição no prazo e reabertura somente
após escolha explícita da criatura. O grupo de três módulos mais o teste focal
de restauração do owner passou `24` testes; decisões são stubs, sem OAuth real.

No fechamento da mesma trajetória, incluí save/load e auditoria causal
standalone. Isso revelou seis eventos `subsistence_resolved` do ciclo inicial
sem causa nomeada: leituras materiais de subsistência da geração inicial, antes
de receipts dos owners. A Economy agora marca somente esse caso sem causa como
`world_generation/initial_subsistence`, mantendo causas canônicas quando já
existem e preservando o payload detalhado. A fixture composta passou a terminar
com auditoria limpa. O grupo focal atualizado — criatura, magia, infraestrutura,
consumo e auditoria dessa raiz — passou `43` testes; Ruff focado e
`git diff --check` passaram. Não é evidência de estoque espontâneo de reparo:
materiais seguem pré-provisionados na fixture, decisões seguem stub, e resposta
institucional/provider OAuth real e o gate natural longo permanecem abertos.

Complemento da resposta institucional: a fixture de recuo agora exige que o
`NO_ACTION` da instituição esteja ligado ao evento do aviso específico recebido
para aquela demanda, além de ser decisão atual `ACTOR_DECISION`. Depois, a
restrição e a retirada continuam escolhas independentes da criatura. O teste
focal passou (`1 passed`), assim como Ruff e `git diff --check`. A decisão usa
provider-stub; OAuth e surgimento natural seguem sem prova.

## Atomicidade do owner de alívio — 25/09/2026

Ao continuar a auditoria dos owners, reproduzi que uma falha ao atualizar
relatórios locais ocorria depois da distribuição material e deixava o mundo
parcialmente mutado, apesar da exceção. `distribute_relief` agora prepara a
execução em uma cópia e publica o estado só após a distribuição, pantries,
necessidade e leitura local concluírem. A regressão compara `world_snapshot`
antes/depois de uma falha injetada nessa etapa; o snapshot fica idêntico.
`tests/test_medieval_relief.py` + `tests/test_medieval_institutional_aid.py`:
`41 passed`. A mudança fecha essa ação do owner, não prova rollback universal
nem a auditoria completa dos demais owners. Ruff focado e `git diff --check`
passaram.

## Economia natural offline até o dia 1.290 — 25/09/2026

Retomei `/tmp/cws-plan-current-seed14-1260.mws` para um único ciclo (30 dias),
em `routine-rules`, sem provider e com `CWS_DATA_DIR` isolado. Conservação de
dinheiro/recursos e save/load equivalente passaram. O save de 14.319.616 bytes
tem 51.897 eventos; auditoria standalone `ok=true`, 40.420 transições materiais
e zero causa quebrada, autoria/fonte inválida, Story/interpretação material ou
material sem raiz. O save levou 9,52 s, load 6,28 s, o run 82,31 s e pico RSS
observado ~904 MB; espaço livre após save: 8.056.180.736 bytes.

De 1.260 a 1.290, falta agregada subiu 530→691, saúde média caiu
318,62→302,62, unrest subiu 512,38→533,38 e mortes por privação foram
162→180. Antes das distribuições do ciclo havia 2.765 rações não pagas;
fallback `routine-rules` cobriu 1.196 em Pontenegro e 878 em Ferroalto, e o
restante observado foi 691. Campomanso manteve 428 de falta com 3.158 alimentos
públicos, preço 1 e oferta observada 4.541 para demanda 1.102. Os 17.678 de
caixa doméstico agregado estavam concentrados: uma coorte agricultora de 314
pessoas tinha saldo zero, enquanto duas outras tinham 8.189 e 8.001. Isso aponta
acesso por conta/coorte e fallback restrito, não falta agregada de estoque; não
é evidência de escolha do provider. Nenhuma regra de preço, salário, pooling,
emprego ou alívio foi ajustada com base só nesse run.

O inventário causal por tipo do mesmo save conta 40.420 eventos materiais:
657 `actor_decision` e 39.763 determinísticos. Das transições sem evento-pai,
153 têm roots validadas em `creature_habitat`, `household_income`,
`infrastructure_site`, `production`, `regional_hydrology` e `route`; zero
material ficou sem link/root. Isso cobre apenas os eventos emitidos pela seed
14 nessa trajetória, não todos os owners/caminhos possíveis.

## Auditoria semântica de referências das premissas raiz — 25/09/2026

O audit causal agora resolve cada `source_ref` de root contra o owner canônico
correspondente (`Economy`, `Society`, `Map` ou `CreatureState`), incluindo
identidades `observer`; referência `scenario` é aceita apenas para
`scenario_bootstrap`. Formato/kind/id válidos sem entidade existente deixam de
ser suficientes. A regressão mantém uma root de estoque existente e rejeita
`stock:missing`. `tests/test_medieval_causal_audit.py`: `3 passed`; Ruff e
`git diff --check` focados passaram. Reauditoria do save natural seed 14/dia
1.290: `ok=true`, 153 premissas raiz, zero roots inválidas, zero transições
materiais sem causa/root e zero causas quebradas. Isso aumenta a força do
auditor para roots presentes, mas não fecha a revisão semântica de todos os
owners nem cobre caminhos que a trajetória não emitiu.

## Atomicidade da recuperação de frete — 25/09/2026

`execute_freight_recovery` revalidava o caminho, mas abria o frete sucessor
diretamente no mundo publicado. Agora executa `open_order` em
`world.transaction_copy()`, valida o owner de Economy e só publica o candidato
completo. Uma regressão injeta exceção depois que `open_order` já consumiu
estoque, registrou evento e agendou a carga; o snapshot do mundo original
permanece idêntico. O fluxo de recuperação e o audit causal passaram juntos
(`15 passed`), com Ruff e `git diff --check` focados. Isso fecha atomicidade
apenas para esse executor, não para o restante dos owners.

## Atomicidade da reativação de infraestrutura — 25/09/2026

`execute_site_reactivation` também atualizava o flag canônico no Map antes de
refresh dos relatórios locais. Agora recompõe e executa a decisão num candidato,
atualiza os relatórios e valida Knowledge antes de publicar. A regressão injeta
falha após o refresh completo e compara o snapshot: mapa, eventos e relatórios
originais não mudam. `tests/test_medieval_infrastructure.py`: `23 passed`. A
investigação do recorte com barreiras mostrou fixtures antigas que pulavam a
decisão do ator, criavam presença/administração/ocupação sem root de cenário e
registravam reparo sem autoria `ACTOR_DECISION`. As fixtures agora reproduzem
esses contratos; a validação combinada de barreiras, infraestrutura,
recuperação de frete, auditoria causal e a trajetória de retomada da cidade
passou (`41 passed`). Ruff e `git diff --check` focados também passaram. Isso
corrige a evidência dos testes e fecha atomicidade de reativação. Depois, o
executor de autorização de reparo também passou a operar em candidato:
autorização, projeto e objetivos de materiais são validados em Economy e
Strategy antes de publicar juntos. Uma falha injetada após criar projeto e
objetivos mantém o snapshot original. Barreiras + infraestrutura passaram `25`
testes após esse reforço; Ruff e `git diff --check` focados passaram. Isso fecha
três executores observados (alívio, recuperação de frete e infraestrutura),
não o rollback dos demais owners nem a transação mensal completa.

Validação integrada final do recorte relacionado: cerco/campanha, barreiras,
infraestrutura, recuperação de frete e auditoria causal — `60 passed`; Ruff e
`git diff --check` passaram. Não é a suíte inteira nem o gate de três seeds por
dez anos.

## Atomicidade de construção e expansão — 25/09/2026

Os owners `start_site_construction` e `start_expansion` agora criam projeto em
`world.transaction_copy()`, revalidam/validam Economy e publicam apenas após
sucesso. Os adapters de menu também agrupam o receipt determinístico de
autorização e a criação do projeto no mesmo candidato; se o projeto falha, nem
o receipt parcial é publicado. Regressões injetam falhas depois da mutação do
candidato e confirmam snapshot original idêntico. Construção: `21 passed`;
expansão: `18 passed`; Ruff e `git diff --check` passaram. Isso cobre somente o
início de obras/expansões, não seu progresso mensal nem os outros owners.

O início de fundação de linha produtiva agora segue a mesma fronteira: tanto o
owner direto quanto o adapter do menu criam decisão/projeto em candidato,
validam Economy e só então publicam. Falhas forçadas depois da criação do
projeto deixam o snapshot original intacto. Construção, expansão e fundação:
`39 passed`; Ruff e `git diff --check` focados passaram. Continua sendo uma
garantia por executor no início do projeto; progresso mensal, outros owners e
rollback global ainda precisam de auditoria.

## Atomicidade do progresso mensal de construção — 25/09/2026

O progresso em lote de expansão/fundação/obra também é transacional para
chamadas diretas: material, salários, coortes disponíveis e comissionamento de
site são aplicados num candidato, validados e publicados juntos. A regressão
injeta erro depois de materiais e payroll e confirma snapshot e disponibilidade
de trabalhadores inalterados. O loop mensal usa seu candidato global existente
diretamente, evitando uma cópia transacional aninhada. Construção + expansão +
fundação passaram `51` testes focados; Ruff e `git diff --check` passaram. Isso
fecha o lote mensal deste owner, não os demais owners nem o rollback integral
da simulação.

## Atomicidade da divulgação de técnica — 25/09/2026

O owner que transforma conhecimento institucional em um indício privado e
temporário agora revalida opção/decisão, grava receipt e atualiza Knowledge num
candidato; valida o owner antes de publicar. Falha injetada após o receipt
mantém snapshot e sightings originais. Divulgação, venda e pesquisa passaram
`35` testes focados; Ruff e `git diff --check` passaram. Isso não abre
espionagem nem difusão automática: cobre apenas o executor de disclosure.

## Atomicidade das provisões agregadas — 25/09/2026

A transferência bilateral para uma coorte agora publica decisão de termos,
receipt, estoque da despensa e contas de comprador/vendedor no mesmo candidato.
Tanto a chamada direta quanto o aceite do vendedor validam Economy antes de
publicar; o caminho offline do mês usa o helper interno dentro da transação
externa. Falhas injetadas após o receipt de compra preservam snapshot, estoque,
dinheiro e os receipts preparatórios. `tests/test_medieval_household_provisioning.py`:
`17 passed`; Ruff e `git diff --check` passaram. Isso cobre a compra agregada
local, não comércio de NPCs amplo nem atomicidade de todos os owners.

## Atomicidade do serviço de rota e raízes da fixture de campanha — 25/09/2026

Suspender/retomar serviço de porto/passagem agora publica receipt e alteração
do Map no mesmo candidato validado; uma falha injetada depois do update físico
preserva o mundo original. A revisão encontrou também três roots ausentes em
fixtures existentes de rota fechada, ocupação e reforço de coluna. Elas agora
declaram `scenario_bootstrap` com referências canônicas, e a auditoria da
interferência criatura → rota → campanha volta a passar. Serviço de site,
engajamento de campo e campanha de interferência: `19 passed`; Ruff e
`git diff --check` passaram. São correções de transação de um owner e de
proveniência das fixtures; não transformam fixture em formação natural.

## Gate natural atual do checkout — seed 73, checkpoint em 1.560/3.600 dias — 25/09/2026

Foi iniciado um novo smoke offline da seed `73` com o checkout atual e horizonte
de `3.600` dias, checkpoints a cada `120` dias, save/load e conservação:

```text
CWS_DATA_DIR=/tmp/cws-medieval-final-seed73-current-data
tools/medieval_autonomy_smoke.py --seed 73 --days 3600
  --output /tmp/cws-medieval-final-seed73-3600-current-20260925.mws
  --checkpoint-days 120
```

O processo foi interrompido no checkpoint válido do dia `1.560`, a pedido do
usuário. Nesse ciclo havia `65.130` eventos, falta alimentar `758`, saúde média
`276,38`, unrest médio `411,25` e `361` mortes acumuladas por privação. O
checkpoint preserva conservação e equivalência save/load. Esses números mostram
estresse material persistente; não são um gate concluído nem uma decisão de
balanceamento. O run usa `ai_enabled=false`/`routine-rules`, sem provider real.

Os saves independentes dos dias `960`, `1.200`, `1.320`, `1.440` e `1.560`
passaram a auditoria causal standalone. No dia `1.560`, foram auditados
`65.130` eventos e `49.946` transições materiais, com zero causas quebradas,
autoria inválida, decisão sem fonte, root inválida/ausente, Story material ou
interpretação material. Isso valida esses checkpoints, não todos os owners nem
o horizonte completo.

A leitura read-only do save do dia `1.200` encontrou em Campomanso `464`
rações faltantes apesar de `2.115` rações no estoque público; os saldos
domésticos estavam concentrados em coortes agricultoras, enquanto as coortes
artesãs tinham saldo quase nulo. É evidência de acesso econômico desigual a
ser investigada, não prova isolada de defeito no mercado ou autorização para
transferir renda/estoque automaticamente. O smoke chegou a `1.560/3.600` dias e
foi encerrado depois de salvar esse checkpoint; o gate e o inventário global de
owners continuam pendentes. Os demais seeds e a trajetória com provider real
ainda não foram repetidos neste checkout.

## E169-finalização — probe local com menu institucional completo — 26/09/2026

O probe de provider sobre save usava somente adapters civis, enquanto o turno
mensal real compõe também ajuda, diplomacia, abastecimento e outras famílias.
Ele agora recompõe o menu mensal completo para a oferta e para a execução no
mesmo fork em memória. Depois da escolha, valida histórico, estado e atividades;
reporta quantos eventos e deltas materiais o fork produziu. O save de origem
continua protegido por hash antes/depois, inclusive em erro.

Com provider simulado, os três casos focados passaram: `NO_ACTION`, ID atual
oferecido e ID inventado rejeitado sem tocar no save. `ruff check` passou. Uma
prévia local no save seed 73/dia 2.610 ofereceu 120 affordances de seis famílias
para Auren; a escolha simulada `NO_ACTION` gerou receipt sem deltas e nenhuma
mutação material. Não houve consulta externa nem prova de agência do provider
real; o corpus de 10 decisões e o gate de três seeds seguem abertos.

## E170-finalização — dez anos offline da seed 73 como pré-checagem — 26/09/2026

Retomei o save atual da seed 73/dia 2.610 até 3.600, sem provider ou decisões
injetadas, com oito checkpoints de 120 dias. Todos preservaram conservação e
equivalência save/load; o save final também passou continuação e auditoria
standalone: 141.888 eventos, 110.663 materiais, zero causas/autorias inválidas,
Story material ou interpretação material. Artefato: `/tmp/cws-v1-seed73-day3600-preflight-20260926.mws`
(SHA-256 `10c9eb4ef7b2289e0dff10e3affa0fb61e09966bafc4737ea0903d0311203e88`).

No trecho retomado, 33 meses tiveram p95 de avanço 44,2361 s, máximo 45,7412
s e sete meses acima de 35 s. O run completo desse trecho levou 1.413,55 s;
save final 37.814.272 bytes, gravação 26,229 s, carregamento 21,0208 s e
pico RSS 2.315.665.408 bytes. O teto p95 V1 **não passou nessa amostra**.
População final 6.389, falta alimentar mensal 1.730, saúde média 96,5 e
4.545 mortes acumuladas por privação. O mundo é causalmente íntegro no
histórico exercitado, mas não economicamente recuperado. Como `E172` mudou
o caminho mensal depois deste run, ele é histórico/preflight, não gate final.

## E171-finalização — perfil do mês tardio lento — 26/09/2026

Perfil read-only do checkpoint dia 3.450 avançou 30 dias em memória, sem
alterar o save: 23 jumps, 76,15 s sob cProfile. Custos cumulativos
sobrepostos: `review_diplomacy` 30,50 s, `transaction_copy` 25,59 s em 85
cópias, Relations.validate 17,39 s em 106 chamadas; 37 divulgações técnicas
custaram 16,05 s. Isso localiza custo, não mede latência de produção.

## E172-finalização — divulgação técnica sem fork aninhado no mês — 26/09/2026

Quando `MedievalSimulator.step` já possui candidato isolado, o fallback
diplomático executa a divulgação técnica nele e deixa a validação/publicação
para o commit mensal. Chamadas diretas continuam usando o fork próprio. O
replay pareado seed 73/dia 3.450→3.480 produziu saves SHA-256 idênticos
(`211ae40676959023b480976088154756836dbe1d9462fb0a2beefe4d1991ffa7`),
com 137.537 eventos e as mesmas métricas materiais. Avanço local: 42,7725 s
antes, 36,5748 s depois; o perfil caiu de 76,15 para 62,09 s, com cópias
85→48. São pares locais, não estimativa robusta de p95; a validação de
Relations ainda custa 17,68 s no perfil posterior.

Diplomacia, divulgação e engine: `32 passed`, incluindo falha injetada após
a divulgação que preserva snapshot, eventos, conhecimento e RNG publicados.
`git diff --check` e Ruff com `E701,E702,F401` ignorados passaram. Ruff sem
esses filtros encontrou infrações já existentes de estilo/import no módulo e
no teste; não foram reformatadas para evitar diff lateral.
Corpus real e gate longo no checkout estabilizado continuam abertos.

## E173-finalização — migração mensal sem transação aninhada — 26/09/2026

O perfil posterior a E172 ainda mostrava 15 comandos de migração usando
`execute_material` dentro do candidato mensal. A política offline agora chama
o executor in-place somente quando invocada pelo `MedievalSimulator.step`;
chamadas diretas continuam usando o limite transacional comum. Uma falha
injetada após iniciar a migração no candidato confirmou que snapshot, eventos,
RNG e jornadas do mundo publicado permanecem intactos.

No par isolado seed 73/dia 3.450→3.480, o avanço caiu de 36,5748 para 30,0601
s e o save permaneceu byte a byte idêntico. No replay contínuo de 33 meses,
dia 2.610→3.600, o p95 caiu de 44,2361 para **29,6076 s**, máximo 32,9266 s,
nenhum mês acima de 35 s. O save final SHA-256
`10c9eb4ef7b2289e0dff10e3affa0fb61e09966bafc4737ea0903d0311203e88`
é idêntico ao preflight E170 já auditado; logo, a história causal e o estado
final daquele horizonte não mudaram. O replay sem checkpoints intermediários
levou 749,38 s, save 25,4328 s, load 21,1515 s e pico RSS 2.301.587.456
bytes. O tempo total não é pareado com E170, que salvou oito checkpoints.

Migração, engine, diplomacia e sighting: `53 passed`. Ruff com exclusões das
infrações antigas `E701,E702,F401` e `git diff --check` passaram. O resultado
aprova somente o trecho tardio dessa seed offline; não demonstra p95 dos 120
meses de três seeds, provider real nem recuperação econômica.

## E174-finalização — segunda seed, pré-checagem anual — 26/09/2026

Retomei a seed 14 offline do save dia 1.440 até 1.800 no checkout pós-E173,
sem provider ou decisões injetadas. Os 12 meses tiveram p95 de avanço
17,2756 s; nenhum passou esse valor. O checkpoint do dia 1.800 preservou
conservação e save/load; o save final passou continuação. O run levou 248,34
s, save 13,8194 s, load 9,5686 s, pico RSS 1.237.393.408 bytes e arquivo
20.242.432 bytes.

O save `/tmp/cws-e174-seed14-day1800.mws` tem SHA-256
`adfbea429c50d446422ab41502c59d3511277a334f4e95f9b0c901ceaec84ab6`.
Auditoria standalone: `ok=true`, 76.274 eventos, 60.268 materiais, nenhuma
causa quebrada, autoria inválida, Story ou interpretação material. População
9.668, falta alimentar mensal 229, saúde média 189,75 e 1.263 mortes
acumuladas por privação. É prova de um ano adicional desta seed, não de
estabilidade de dez anos nem de escolha por provider real.

## E175-finalização — superfície pública focada no checkout atual — 26/09/2026

O build medieval (`vue-tsc` + Vite) passou; permanece apenas o aviso de chunk
acima de 500 kB. Cinco contratos focados de API, dossiê, observatório e
entrega do bundle medieval passaram (`5 passed`). No save seed 14/dia 1.800,
20 consultas causais distribuídas de até 100 links tiveram p95 local de
0,0835 s, abaixo do orçamento V1 de 2 s. A medição é no backend local, sem
rede/browser; não cobre toda a UI nem substitui a regressão integrada final.

## E176-finalização — fixture de campanha do corpus causalmente válida — 26/09/2026

A fixture antiga do probe de campanha apagava instalações e aumentava uma
coorte de soldados sem reduzir a população de origem. A auditoria standalone
do save anterior encontrou uma transição material sem raiz causal. O preparo
agora preserva instalações, transfere 20 pessoas de uma coorte agrícola
existente para a coorte militar existente e registra essa transferência e a
ocupação como premissas explícitas do cenário. A população total permanece
10.900; a fixture salva passa na auditoria causal.

O probe material também estava defasado: a cadeia atual exige adoção,
autorização política, escolha da força pelo QG e nomeação do comandante,
quatro decisões em vez de duas. Com provider stub que seleciona IDs oferecidos,
o save resultante contém uma decisão de força e uma coluna, passa save/load
e auditoria standalone (`ok=true`, zero eventos materiais sem raiz). Os sete
testes focados dos dois probes passaram. Isto valida o instrumento sintético,
não representa decisão espontânea do provider OAuth/Luna, mundo natural ou o
corpus de dez decisões do Gate D; nenhuma chamada externa foi feita.

## E177-finalização — seed 14 offline até dez anos, pré-checagem — 26/09/2026

Retomei o save auditado da seed 14/dia 1.800 por 60 meses, sem provider real,
decisões injetadas ou mudança de código durante o run. Os cinco checkpoints
anuais novos (dias 2.160, 2.520, 2.880, 3.240 e 3.600) passaram conservação,
save/load e auditoria causal standalone. O save final
`/tmp/cws-e177-seed14-day3600.mws` tem SHA-256
`db3ec84ac0020fbb07d7b9f99b3503d196e6924684aac34aa1e96ea1fd277892`.
Auditoria final: `ok=true`, 141.667 eventos, 112.499 materiais, zero causas
quebradas, autoria inválida, Story/interpretação material ou mutação sem raiz.

No trecho retomado, p95 mensal 21,9046 s e máximo 25,0554 s; execução com
checkpoints 1.325,52 s. Save final 36.564.992 bytes; gravação 25,3938 s,
carregamento 21,4954 s, pico RSS 2.232.664.064 bytes. Vinte consultas
backend-local de `why()` tiveram p95 0,1575 s. Esses valores passam os limites
individuais V1 medidos, mas **não** medem o tempo de um run integral desde o
dia zero nem constituem o gate final de três seeds.

O mundo permaneceu causalmente íntegro, mas economicamente frágil: população
9.668→6.160 desde a retomada, 4.771 mortes acumuladas por privação, falta
alimentar de 1.846 no último mês, saúde média 170,88 e unrest médio 597,62.
Houve 187 pedidos de ajuda, 140 cumprimentos, 436 compras de mercado e 237
transições de trabalho acumuladas; essas ações não bastaram para estabilizar
esta trajetória offline. O corpus OAuth/Luna continua não exercitado.

## E178-finalização — seed 101 integral por dez anos, pré-checagem — 26/09/2026

Rodei a seed 101 do dia zero ao 3.600 em `routine-rules`, sem provider real ou
decisões injetadas, sem alterar código durante a execução. Os dez checkpoints
anuais passaram conservação, save/load e auditoria causal standalone
(`checkpoint_count=10`, `all_ok=true`). O save final
`/tmp/cws-e178-seed101-day3600.mws` tem SHA-256
`806c27680be998c1a68fdc09988e67cbcaf015476ce5e8bc7bcf5c90b1aed413`.
Auditoria final: `ok=true`, 137.074 eventos, 105.364 materiais, zero causas
quebradas, autoria inválida, Story/interpretação material ou mutação sem raiz.

As 120 amostras mensais tiveram p95 31,9607 s, máximo 34,7465 s e nenhum mês
acima de 35 s. O run inteiro com checkpoints levou 2.326,92 s (38,8 min),
abaixo do teto de 60 min. Save final 36.675.584 bytes; gravação 24,5868 s,
carregamento 20,4558 s, pico RSS 1.922.842.624 bytes. Vinte consultas
backend-local de `why()` tiveram p95 0,1576 s. Todos esses limites medidos
passaram para esta seed isolada; não são latência de UI/rede.

O estado final conserva dinheiro/recursos e equivale após save/load, mas a
economia permaneceu pressionada: população 8.206, 2.730 mortes acumuladas por
privação, falta alimentar de 737 no último mês, saúde média 225,88 e unrest
médio 532,75. Foram registrados 281 pedidos de ajuda, 265 cumprimentos, 507
compras de mercado e 245 transições de trabalho acumuladas. A comparação com
seed 14 mostra trajetórias diferentes, não recuperação econômica garantida.
Gate D segue aberto: faltam três runs integrais no checkout estabilizado e o
corpus de decisões com provider real.

## E179-finalização — seed 73 integral por dez anos, pré-checagem — 26/09/2026

Rodei a seed 73 do dia zero ao 3.600 em `routine-rules`, sem provider real ou
decisões injetadas, com dez checkpoints anuais. Todos passaram conservação,
save/load e auditoria causal standalone (`checkpoint_count=10`, `all_ok=true`).
O save `/tmp/cws-e179-seed73-day3600.mws` tem SHA-256
`ff5348c435c5af4fa69d7651e1ef9479f403135be4530c6bda92a443f931875f`.
Auditoria final: `ok=true`, 141.888 eventos, 110.663 materiais, zero causas
quebradas, autoria inválida, Story/interpretação material ou mutação sem raiz.

As 120 amostras mensais tiveram p95 31,485 s, máximo 37,0017 s e apenas um
mês acima de 35 s; o limite fixado é p95, não máximo. O run completo com
checkpoints levou 2.287,11 s (38,1 min). Save final 37.814.272 bytes;
gravação 25,2238 s, carregamento 22,2628 s, pico RSS 1.985.359.872 bytes.
Vinte consultas backend-local de `why()` tiveram p95 0,1659 s. Conservação
de dinheiro/recursos e save/load passaram.

O resultado econômico segue grave: população 6.389, 4.545 mortes acumuladas
por privação, falta de 1.730 rações no último mês, saúde média 96,5 e unrest
médio 574,75. Foram registrados 183 pedidos de ajuda, 138 cumprimentos, 482
compras de mercado e 221 transições de trabalho acumuladas. O corpus real
continua aberto. Esta medição antecede a correção E180; não é gate final do
checkout posterior.

## E180-finalização — ordem estável de conclusão do abastecimento — 26/09/2026

Comparei o save E179 com o replay anterior E173 da mesma seed/dia. O estado
canônico final era igual, mas `world.events` divergia a partir de `event:67049`
no dia 1.614: Salgueiro/Ferramentas e Pontenegro/Madeira concluíam planos em
ordem oposta. A primeira diferença binária também mostrava chaves de preço
em ordem diferente no JSON; portanto não era correto atribuir a divergência
inteira apenas à serialização. Em `progress_supply`, a iteração seguia a ordem
de inserção do dicionário de planos, que pode mudar após save/load.

O owner agora percorre os planos por `id` estável. Uma regressão com os mesmos
dois planos inseridos em ordens opostas confirmou a mesma sequência de eventos;
o teste mensal de abastecimento também passou. No replay pareado a partir do
mesmo checkpoint do dia 1.440, inverti apenas a ordem do dicionário de planos
em uma cópia e avancei ambas até o dia 1.620: 68.134 eventos idênticos,
snapshots idênticos, nenhuma primeira divergência. Script diagnóstico:
`/tmp/cws_e180_order_probe.py`. A suíte focada de autonomia passou
(`13 passed`); Ruff dos arquivos tocados e `git diff --check` passaram.
Ainda não há novo smoke de dez anos pós-correção. Os saves E177–E179
permanecem preservados como evidência histórica, não como aprovação do
checkout atual.

## E181-documental — acompanhamento por recorte verificável — 26/09/2026

O plano canônico agora exige abrir uma caixa específica na matriz antes de
cada recorte e marcá-la somente após evidência reproduzível no diário. O Gate D
foi decomposto em preparação do corpus, ao menos dez decisões reais, checkout
congelado, três seeds integrais e integração final. Esses itens permanecem
abertos; a mudança foi apenas documental. `git diff --check` passou. Não houve
chamada ao provider, novo smoke, commit ou push neste checkpoint.

## E182-finalização — inventário local das situações do corpus — 26/09/2026

Sem consulta externa, carreguei o save natural preservado da seed 73/dia
3.600 (`/tmp/cws-e179-seed73-day3600.mws`). Os menus mensais completos
enumeraram 72 opções para Auren, 92 para Escarlia e 45 para Valedouro; entre
as famílias havia economia, ajuda, emprego, abastecimento e, em Valedouro,
prioridade produtiva. As duas criaturas tinham `condition=0`, 248
cruzamentos percebidos e opções canônicas `maintain` e `request` para a rota
fluvial. O save é pré-E180; serve para descobrir candidatos, não para aprovar
o checkout final.

Na fixture de campanha já saneada em E176, o menu mensal de Auren no código
atual ofereceu adoção de defesa, três pesquisas de irrigação e uma de doutrina
de campo. Isso prova concorrência no menu, não ainda o contrafactual material
entre alimento e prioridade militar. A partir do save natural dia 1.440,
abri apenas num fork de memória um pedido de Auren a Valedouro, citando a
decisão API e o relatório existente. Valedouro teve opções reais de rejeitar
ou aceitar 164 unidades de alimento, inclusive rota já observada. O fork não
foi salvo e nenhuma decisão da LLM foi executada.

Faltam montar e auditar o caso de compromisso perto do prazo e a disputa
material militar/alimento antes de marcar a preparação integral do corpus.
Não houve chamada ao provider, commit, push ou alteração do save de origem.

## E183-finalização — obrigação de ajuda próxima do vencimento — 26/09/2026

Criei `tools/medieval_provider_commitment_fixture.py` para preparar um caso
reproduzível sem egress. O instrumento carrega o checkpoint natural da seed
73/dia 1.440, registra pedido de Auren e aceite de Valedouro como duas decisões
API explícitas, e invoca os executores normais de ajuda. A obrigação nasce
ativa, com vencimento no dia 1.471. Depois, o simulador avança até o dia 1.470
sob um stub local declarado que responde `NO_ACTION` a todas as consultas;
isso preserva a independência e a memória dos turnos, mas **não** é uma
escolha do provider real nem uma trajetória natural. A obrigação permanece
ativa e `aid_fulfillment_options` ainda oferece um envio material válido.

O save `/tmp/cws-e183-near-due-aid.mws` tem SHA-256
`3468c143508a59ae3af5833e0f2ecbd53740ffda91b7035cac66fcaa59fc332c`.
O instrumento confirmou que o save de origem não mudou e que save/load do
fork preserva estado e eventos. Auditoria standalone do novo save:
`ok=true`, 60.871 eventos, 45.966 materiais, zero causas quebradas, erros de
autoria/fonte, premissas inválidas, mutações sem raiz ou Story/interpretação
material. `ruff check`, `py_compile` e `git diff --check` passaram. Uma
primeira execução revelou que o limite persistido de `ai_calls_per_step` é
256; o instrumento foi corrigido e a execução aprovada usou esse limite.
Nenhum provider real foi chamado. Ainda falta provar o conflito material
militar/alimento e depois executar o corpus real autorizado.

## E184-finalização — opções de alimento e defesa no mesmo turno — 26/09/2026

Criei `tools/medieval_provider_competing_priorities_fixture.py`, que carrega
o save natural seed 73/dia 1.440 sem alterá-lo. Brumafria já tinha falta de
215 rações no relatório próprio de Escarlia. A fixture declara somente uma
ocupação inicial por Auren como premissa de cenário, com delta, fonte e
relatório datado; ela não inventa alimento, exército ou decisão posterior.
O menu mensal composto passou a enumerar, para Escarlia no mesmo turno,
`aid_request` para Brumafria e `defense_adoption` para o mesmo assentamento,
entre 66 opções. Escolher uma impediria escolher a outra nesse turno, mas o
instrumento não seleciona nenhuma nem prova o contrafactual econômico/militar
posterior.

O save `/tmp/cws-e184-food-defense.mws` tem SHA-256
`38bac726de85b726fb5ccacf7b35012a5bf3f5af23e82b788060845cb177c40a`.
Save/load preservou estado e eventos. Auditoria standalone: `ok=true`,
59.307 eventos, 45.277 materiais, zero causas quebradas, erros de autoria/
fonte, premissas inválidas, mutações sem raiz ou Story/interpretação material.
`ruff check`, `py_compile` e `git diff --check` passaram. Não houve egress,
chamada ao provider, commit ou push. O corpus ainda precisa de um caso de
rota/campanha com affordance de reação atual e depois das decisões reais.

## E185-finalização — base atual da interferência rota/campanha — 26/09/2026

Reexecutei duas provas focadas no checkout atual: a crise controlada com
decisões independentes de criatura, comandante e QG após fechamento de rota,
atraso de carga e efeito civil; e a abertura de uma nova affordance de
suprimento do QG após um atraso real da logística. Resultado: `2 passed in
3.18s`. Elas comprovam que o recorte causal ainda funciona, mas não deixam
um save parado exatamente antes da consulta ao provider real. Preparar esse
checkpoint consultável é o próximo passo do corpus; não houve chamada externa.

## E186-finalização — checkpoint consultável de rota/campanha — 26/09/2026

A fixture autônoma já existente agora salva um checkpoint no dia 30, antes
da revisão datada de comandante e QG. O save preservado em
`/tmp/cws-e186-pre-route-review-fixture.mws` tem SHA-256
`e3e46c4069b36deb800dd7a6362928f704b6418fd6c11479cbc5463f88837ff5`.
A revisão do plano está agendada para o dia 31; há uma rerota e duas retiradas
atuais para o QG. A auditoria standalone do checkpoint passou: `ok=true`,
999 eventos, 603 materiais e zero causas quebradas, falhas de autoria,
premissas inválidas, Story/interpretação material ou mutações sem raiz.

Criei `tools/medieval_provider_route_review_probe.py` para carregar esse
save, avançar a data, resolver os trabalhos datados e consultar apenas as
duas revisões militares relevantes em memória, sem persistir a cópia. Com
stub local `NO_ACTION`, o probe registrou uma consulta ao comandante
(`character:002`, uma opção) e outra ao QG (`character:008`, três opções),
com recibos sem delta e fonte intacta. Um ID inventado levantou
`ProviderDecisionRequired` e o SHA-256 do save ficou igual. O teste focado
passou (`1 passed in 3.31s`); Ruff, compilação Python e `git diff --check`
passaram. Essas respostas são do stub, não do provider real; uma consulta
real ainda requer configuração e autorização. O corpus completo continua
aberto, assim como o gate longo do checkout estabilizado.

## E187-finalização — prazo conhecido pelo ator e prévia do corpus — 26/09/2026

Uma prévia local dos menus expôs uma lacuna: a affordance `aid_fulfillment`
estava disponível no menu mensal, mas o provider não recebia o prazo que a
instituição havia aceitado. `concurrent_civil_decision.py` agora deriva de
`RelationsState`, somente para o devedor atual, credor, recurso, quantidade,
`due_day` e `days_until_due`; não lê estoque estrangeiro nem altera o owner
material. No save E183/dia 1.470, o prompt local passou a mostrar a obrigação
com vencimento no dia 1.471 e `days_until_due=1`. O save de origem permaneceu
intacto. Atualizei o teste existente de ajuda para usar decisões API válidas
no contrato atual e verificar exatamente esse fragmento do prompt;
`4 passed in 1.67s` no recorte de ajuda e probe civil.

As prévias locais, com stub `NO_ACTION` e sem egress, cobriram economia (72
opções, prompt de 54.531 bytes), obrigação próxima do prazo (59 opções,
36.966 bytes antes do campo de prazo), alimento/defesa (66 opções, 56.116
bytes), criatura e rota/campanha. Nos três menus civis, todos os
`known_settlement_reports` exibidos pertenciam ao ator e a varredura não
encontrou IDs diretos de estoques ou contas de terceiros. A criatura recebeu
sua própria condição e cruzamentos percebidos; o `blocked_report_event_id`
do QG correspondeu ao relatório de rota entregue ao próprio QG no dia 30.
Esses checks são específicos dos casos do corpus: não comprovam ausência de
todo vazamento em qualquer outro fragmento, nem validam comportamento de
provider real. A preparação fica aberta até fechar esse limite de
conhecimento de forma reproduzível. Ruff e `git diff --check` passaram.

## E188-finalização — prévia reproduzível dos cinco casos — 26/09/2026

Criei `tools/medieval_provider_corpus_preview.py` para montar localmente os
prompts dos cinco casos do Gate D, sem chamar o provider nem imprimir o texto
integral. Entradas explícitas: saves E179 (natural), E183 (obrigação), E184
(alimento/defesa) e E186 (rota/campanha). A prévia passou: economia ofereceu
72 opções e quatro relatórios próprios; obrigação próxima, 59 opções e prazo
de 1 dia; alimento/defesa, 66 opções e três relatórios próprios; criatura,
duas opções e condição/cruzamentos iguais à percepção canônica; rota/campanha,
duas consultas independentes de comandante e QG com uma e três opções. O QG
possuía o relatório de rota citado; o comandante tinha nomeação real. Nenhum
dos três prompts civis continha ID direto de estoque ou conta de terceiro.
Os quatro SHA-256 de origem permaneceram iguais.

O instrumento verifica conhecimento e affordances destes casos, não todos os
fragmentos possíveis do jogo. O save natural E179 antecede a correção E180,
mas foi carregado e recomposto pelo código atual; reexecutar a prévia se o
checkout ou os saves mudarem. `ruff check`, compilação Python e
`git diff --check` passaram. A preparação local está fechada; o corpus de
ao menos dez escolhas com provider real e o gate de três seeds seguem abertos.

## E189-finalização — opções do corpus executadas pelo owner local — 26/09/2026

Em cópias em memória dos mesmos saves, um stub escolheu IDs efetivamente
oferecidos para confirmar que o corpus não contém apenas opções visíveis mas
inexecutáveis. Na crise econômica de Auren, `institutional-aid-request` gerou
um fato material e seis deltas. Na obrigação próxima do prazo de Valedouro,
`institutional-aid-fulfill` gerou dois fatos materiais e oito deltas. Na
disputa entre alimento e defesa de Escarlia, `strategy-defense-adopt` gerou
um fato material e dois deltas. A revisão de rota consultou comandante e QG:
o primeiro manteve `NO_ACTION`; o QG escolheu a rerota ofertada, com 18 fatos
materiais no avanço datado e na execução. A criatura escolheu a opção
`request`, gerando `creature_demanded_tribute`, um delta de demanda aberta e
um receipt de interpretação sem delta. A validação de histórico e snapshot
passou no caso da criatura.

Todos os IDs selecionados eram atuais, a revalidação dos owners passou e os
arquivos de origem conservaram seu SHA-256. Estes resultados são de seleção
programada por stub em forks locais. Não dizem que o provider real escolheria
essas ações, nem que as cadeias surgiriam espontaneamente; o corpus real de
dez ou mais decisões e os três runs finais continuam abertos.

## E190-finalização — preflight focado antes do Gate D — 26/09/2026

O checkout atual passou os recortes de probe civil, interferência entre
campanha e criatura e instrumento do gate de release: `9 passed in 13.50s`.
Comando: `CWS_DATA_DIR=/tmp/cws-e190-preflight-data .venv/bin/pytest -q
tests/test_medieval_provider_civil_probe.py
tests/test_medieval_campaign_creature_interference.py
tests/test_medieval_release_gate.py`. A primeira tentativa, sem namespace
isolado, não coletou testes: o logger tentou criar arquivo em
`~/.local/share/MedievalWorldSimulator-dev`, leitura apenas neste ambiente.
Repetir com `CWS_DATA_DIR` corrigiu apenas o ambiente de execução; não houve
alteração de código nem interpretação daquele erro como bug do simulador.

O comando `medieval_release_gate.py --help` confirmou que o instrumento final
aceita `--final-v1`, três seeds distintas, `--days 3600` e checkpoints. Este
preflight não executou o gate longo, não consultou o provider real e não
certifica API/UI ou desempenho final. Esses aceites permanecem abertos.

## E191-finalização — dez consultas locais distintas para o corpus — 26/09/2026

A prévia `tools/medieval_provider_corpus_preview.py` agora recebe seis saves
explícitos: seed 73/dia 3.600, as duas derivações controladas de compromisso
próximo e alimento/defesa, a revisão de rota/campanha no dia 30 e mundos
naturais das seeds 101 e 14 no dia 1.440. São sete menus institucionais de
pares ator–save distintos, a consulta da criatura e duas consultas militares
independentes (comandante e QG): **dez consultas** cobrindo os cinco tipos
requeridos. Nos quatro novos menus civis havia 45–85 opções atuais, relatórios
próprios e nenhum ID direto de estoque/conta estrangeiro. A ferramenta rejeita
duplicação de par ator–save e contagem diferente de dez.

Com `CWS_DATA_DIR=/tmp/cws-e191-preview-data`, a execução terminou com
`consultation_count=10`, `real_provider_calls=0` e
`raw_prompts_emitted=false`; os hashes dos seis saves de entrada ficaram
inalterados. `ruff check` e `git diff --check` passaram. A verificação de
conhecimento é dirigida aos campos inspecionados, não auditoria universal de
todo texto do prompt. Os saves das seeds 14/101 são checkpoints anteriores às
últimas mudanças; foram carregados e tiveram as affordances recompostas no
código atual. Se código ou saves mudarem, repetir a prévia. Esta preparação
não executa a escolha da IA real e não fecha o item 8 do plano.

## E192-finalização — integração dirigida e asserção demográfica — 26/09/2026

O recorte backend de API, dossiê, observatório e auditoria terminou com
`55 passed, 1 failed in 331.33s`. A falha ocorreu somente em
`test_public_lifecycle_creates_medieval_world_advances_a_year_and_resumes`:
o teste exigia que a população do dia 360 não superasse os 10.900 habitantes
iniciais, mas o agregado público foi 10.934. O owner de demografia permite
nascimentos determinísticos em assentamentos alimentados e com capacidade,
registrando `settlement_births`, deltas e coortes. A mortalidade pode coexistir
em outros assentamentos. Portanto, o teto fixo era uma expectativa obsoleta,
não evidência de população criada sem causa.

O teste de API agora exige população positiva e igualdade entre o total
público e a soma dos grupos canônicos do mesmo snapshot. O cenário anual,
incluindo save/load, passou isoladamente (`1 passed in 306.17s`); os dois
testes específicos de demografia também passaram. Ruff e `git diff --check`
passaram. O recorte de frontend de Crônica, dossiê e app passou (`23 passed`),
e `npm run build` concluiu; Vite avisou sobre chunk acima de 500 kB, sem
falhar. A suíte backend de 56 casos não foi repetida integralmente após a
correção, e os três runs finais, corpus provider real e aceite API/UI/`why()`
do checkout estabilizado continuam abertos.

## E193-finalização — `why()` mede vínculos e tempo — 26/09/2026

O instrumento `tools/medieval_release_gate.py` já media 20 consultas causais
distribuídas no save final, mas aceitava uma resposta rápida mesmo se o
resultado não fosse navegável. Agora cada amostra exige o evento solicitado,
exatamente os IDs de causas presentes nos links canônicos e efeitos que
apontem de volta ao evento; o orçamento V1 exige `why_links=true` além da
contagem e do p95. O teste do orçamento também reprova explicitamente
`links_verified=false`.

Os quatro testes focados do gate passaram (`4 passed in 6.26s`). No save
histórico E179 da seed 73/dia 3.600, as 20 consultas passaram com vínculos
válidos e p95 `0,1567 s`, abaixo dos 2 s congelados; SHA-256 de origem
inalterado. Ruff e `git diff --check` passaram. Esse save antecede mudanças
posteriores e não substitui a medição nos três runs do checkout final.

## E194-finalização — executor limitado para o corpus real — 26/09/2026

Criei `tools/medieval_provider_corpus_probe.py` sobre os probes e saves já
preparados. A execução padrão só repete a prévia sem egress; o caminho real
exige `--allow-provider-egress` explícito, provider configurado e limite duro
de dez chamadas no cliente. Ele consulta rota/campanha, criatura e menus civis
de pares ator–save distintos. Se a revisão militar oferecer apenas uma das
duas consultas previstas, há um oitavo contexto civil previamente checado
para ainda completar dez, sem ultrapassar o limite. Cada probe verifica ID,
receipt, histórico e save de origem conforme seu owner; o agregador confirma
os hashes dos seis saves ao final. Retorna resultados parciais tipados em
falha, sem imprimir prompt bruto nem persistir mundos. O cliente atual não
expõe uso/preço, então o campo de custo fica explicitamente indisponível;
latência e bytes de prompt são reportados.

O modo sem egress completou a prévia dos saves E179/E183/E184/E186 e das
seeds 101/14 com `real_provider_calls=0`. Três testes sintéticos passaram:
ausência de consulta sem flag, dez chamadas simuladas e rejeição da 11ª;
Ruff passou. Não houve chamada OAuth/Luna real, e a prontidão do instrumento
não fecha o corpus nem permite declarar validado o comportamento do provider.

## E195-finalização — corpus OAuth/Luna real e par causal — 26/09/2026

Após autorização do usuário para até 20 consultas com contexto ficcional dos
saves, usei o perfil temporário `codex_cli`/`gpt-6-luna` sem chave configurada.
O executor limitou a primeira rodada a dez chamadas, em forks de seis saves.
As cinco situações foram cobertas por pares ator–estado distintos. O
comandante escolheu `detachment-retreat`; essa execução encerrou a revisão
antes do turno do QG, de modo que o contexto civil reserva completou a décima
consulta sem duplicar prompt. A criatura escolheu `maintain`. Auren escolheu
um objetivo de abastecimento; Valedouro cumpriu a obrigação de ajuda na
véspera do prazo; Escarlia preferiu auxílio alimentar à adoção defensiva.
Nos contextos adicionais, Luna escolheu uma contratação de pessoal e quatro
distribuições de auxílio. Todas foram escolhas de IDs ofertados, não parâmetros
inventados; os owners revalidaram as decisões em memória.

O relatório da rodada registrou `complete=true`, `consultations=10`, zero
falhas, dez receipts válidos sem deltas de interpretação e seis saves de
origem inalterados. Os dez tempos do cliente variaram de `7,741 s` a
`11,742 s`; soma de bytes dos prompts: `384.732`. O cliente Codex CLI não
expõe uso/preço, então custo monetário é **indisponível**, não zero. Os checks
de conhecimento foram os dirigidos em E188/E191: relatórios próprios,
ausência de IDs diretos de estoque/conta estrangeiros nos menus civis,
percepção da criatura e relatório de rota/nominação militar. Isto não prova
privacidade de todo fragmento possível nem autonomia de dez anos.

Uma 11ª consulta real usou o mesmo save E183 em fork após um cumprimento
material explícito de API. A antiga affordance
`institutional-aid-fulfill:proposal:event:59253:term:0:event:59256:event:60201`
saiu do menu, que passou a ter 57 opções. Luna escolheu uma distribuição de
auxílio em Portovelho, não repetiu o ID obsoleto; receipt sem delta, owner com
efeitos materiais, histórico e snapshot válidos. Latência `13,227 s`;
SHA-256 do save E183 permaneceu
`3468c143508a59ae3af5833e0f2ecbd53740ffda91b7035cac66fcaa59fc332c`.
Os hashes dos outros cinco saves também foram conferidos após a rodada e
permaneceram iguais aos registrados em E191. O caso pareado é controlado:
o cumprimento inicial foi preparado por decisão API, não escolhido de novo
pelo provider. Falha sem mutação continua sustentada pelos testes negativos
locais, não por uma falha real de Luna neste corpus.

## E196-finalização — baseline congelado para o gate longo — 26/09/2026

Após o corpus real, o HEAD é `51c213dfd11e891f2e0e5d73f79fc54da9b09035`
na branch `codex/medieval-remote`. O worktree tem 264 entradas modificadas ou
novas, preservadas sem commit/reset. Um digest determinístico dos arquivos
listados por `rg --files` em `src`, `tests`, `tools`, `static`, `web/src`,
`web/package.json`, `web/tsconfig.medieval.json`,
`web/vitest.medieval.config.ts` e `pyproject.toml` foi
`71ad07c6d7d871b78cc6fa109e854ad6a8229d31f152509ac161e602dffae000`.
O comando de digest é:

```bash
rg --files -0 src tests tools static web/src web/package.json web/tsconfig.medieval.json web/vitest.medieval.config.ts pyproject.toml | sort -z | xargs -0 sha256sum | sha256sum
```

O host tinha 4,6 GB livres em `/tmp`, 8,3 GiB de memória disponível e swap
já bastante ocupada; execuções devem ser sequenciais. Os checkpoints
históricos anuais da seed 73 somavam aproximadamente 240 MB, sem implicar
mesma medida no checkout atual. A saída planejada
`/tmp/cws-v1-final-e196` estava ausente antes do run. Nenhum arquivo antigo
foi apagado, nenhum save será sobreposto. O digest deve ser repetido após
os três runs para afirmar que pertencem ao mesmo código.

## E197-finalização — falha real de expansão e novo gate — 26/09/2026

O primeiro gate final E196 completou as seeds 73 e 101 até o dia 3.600, mas
falhou na seed 137 no dia 1.919 antes de gerar o relatório consolidado. A
retomada isolada do checkpoint de dia 1.800 reproduziu
`ValueError: production line already exists or is planned`. O traceback apontou
para `review_research → _apply_known_techniques → start_expansion`, não para a
auditoria. Após um `start_expansion` atômico, o fallback ainda examinava uma
referência antiga de `world.economy`; uma segunda instalação no mesmo site
tentava abrir a mesma linha de produção. A decisão não gerou mutação parcial,
mas interrompeu a simulação. Os saves E196 foram preservados; dois horizontes
completos não certificam o código corrigido.

O loop agora relê a economia canônica e a instalação pelo ID a cada iteração.
Três testes focados passaram, incluindo duas instalações competindo pela mesma
linha. A seed 137 retomada do mesmo save de dia 1.800 avançou até 2.160 sem a
exceção; checkpoint e save final conservaram recursos/dinheiro e foram
equivalentes após load. A retomada de 360 dias levou 309,52 s, com save de
24.055.808 bytes, high-water de 1.472.188.416 bytes, save em 16,29 s e load
em 12,32 s. É uma prova focada, não substitui três runs integrais.

O novo digest dos mesmos arquivos de código/testes/catálogos é
`2075b04bc6a44100bbc7d233578c960647088be03dc5e7ce22b6c85d9e34a500`.
Um novo gate de três seeds/3.600 dias foi iniciado sequencialmente em
`/tmp/cws-v1-final-e197`; a matriz só será marcada após relatório, auditorias,
orçamentos e repetição do digest. A mortalidade observada no primeiro gate
continua alerta de produto, separado de causalidade e estabilidade técnica.

## E198-finalização — orçamento de tempo e validação redundante — 26/09/2026

O gate E197 rodou as três seeds até 3.600 dias no mesmo fingerprint e retornou
`natural_ok=false`, `ok=false`, sem exceção material. O orçamento da seed 73
passou (p95 mensal `31,6199 s`, run `2.318,47 s`, RSS alto `1.985.970.176`
bytes, save `37.814.272` bytes, save `25,685 s`, load `22,4742 s`, `why()`
p95 `0,1863 s`). A seed 137 registrou p95 mensal `40,8751 s`, acima do teto
pré-fixado de `35 s`; o relatório JSON completo do processo, com mais de
10 MB, foi truncado pelo terminal, então não se atribui aqui um veredito
individual não capturado à seed 101. O `ok=false` técnico não autoriza
afrouxar o limite nem declarar a V1 concluída. Os saves anuais e finais E197
permanecem em `/tmp/cws-v1-final-e197`.

Um mês tardio da seed 137, perfilado sobre o save de dia 3.600, mostrou 37
ofertas diplomáticas repetindo `RelationsState.validate(world)` sobre o
histórico inteiro; só essas validações consumiram ~7,8 s sob `cProfile`.
`MedievalSimulator.step` já mantém um candidato isolado e valida as relações
no final, antes de publicá-lo. O owner de oferta agora dispensa apenas a
validação histórica de entrada quando recebe explicitamente esse candidato
mensal; entradas diretas continuam validando. Um par sobre o mesmo save e
mês, com os mesmos `153.323` eventos de saída, mediu `28,7156 s` com a
validação antiga forçada versus `21,5387 s` com a nova, ganho de `7,1769 s`.
Os 37 testes focados de diplomacia passaram, além dos três testes de
expansão/research anteriores. `.venv/bin/ruff` não existe neste ambiente;
esse lint não foi alegado como verde.

O novo digest de código/testes/catálogos é
`2189f2b477e41caac15cf00db4c6ef7ce9bb44f39b68df46ab7fc52d80041d8f`.
O E197 é histórico para o código otimizado. O próximo gate deve rodar três
seeds completas sob o mesmo limite de 35 s, capturando somente um resumo
compacto do JSON volumoso para registrar o orçamento de cada seed.

## E198 — três seeds integrais, limite mensal ainda aberto — 26/09/2026

No fingerprint `2189f2b477e41caac15cf00db4c6ef7ce9bb44f39b68df46ab7fc52d80041d8f`, as seeds 73, 101 e 137 partiram do dia zero e chegaram ao dia 3.600. Auditorias causais e de checkpoints passaram nas três; conservação, save/load, tamanho do save, memória, tempo total e consultas `why()` ficaram dentro dos limites congelados. O p95 mensal foi `27,2243 s` (73), `30,1500 s` (101) e `38,8062 s` (137). Portanto, `natural_ok=false` e `ok=false`: a seed 137 ainda excede o teto de `35 s`. Saves e checkpoints estão em `/tmp/cws-v1-final-e198`.

A mortalidade por privação foi 4.545, 2.730 e 3.166, respectivamente; saúde média final 96,50, 225,88 e 246,75. Esses números não são aceite de saúde econômica. O perfil de um mês tardio da seed 137 apontou cópias transacionais, validações e varreduras repetidas de eventos em pesquisa/ajuda como custos a investigar. Nenhum limite será relaxado para aprovar o gate.

## E199 — resposta diplomática e leituras indexadas — 26/09/2026

O mês 3.270→3.300 da seed 137 teve 37 respostas diplomáticas e 73 validações de `RelationsState` no perfil. A resposta agora conserva validação de entrada para executor direto, mas dispensa a varredura histórica repetida quando recebe explicitamente o candidato mensal, que o finalizer valida antes do commit. No mesmo save e mês, forçar a validação antiga mediu `39,0574 s`; a chamada candidata mediu `34,9922 s`, com os mesmos `139.943` eventos finais. Leituras de autorização de pesquisa, dia de evento de ajuda e atrasos de migração passaram a usar índices transitórios já existentes. Após isso, o mês mediu `32,2580 s`, ainda com `139.943` eventos. Passaram 63 testes focados de diplomacia/ajuda e 57 de pesquisa/migração/ajuda; uma primeira execução destes últimos detectou um erro de sintaxe na compreensão de migração, corrigido antes da repetição verde. `git diff --check` passou.

O digest de código/testes/catálogos para o gate seguinte é `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28`. O gate E199 foi iniciado para três seeds desde o dia zero; o resultado completo está registrado logo abaixo.

## E199 — gate natural de dez anos aprovado — 27/09/2026

As três seeds avançaram sequencialmente do dia zero ao dia 3.600 no digest `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28`. Relatório resumido: `/tmp/cws-v1-final-e199`.

| Seed | Auditoria/checkpoints | p95 mensal | Tempo | Pico RSS | Save | Save/load | `why()` p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| 73 | passou | 24,4627 s | 1.990,59 s | 1.984.102.400 B | 37.814.272 B | 24,917/20,728 s | 0,1813 s |
| 101 | passou | 28,5377 s | 2.175,41 s | 1.984.102.400 B | 36.675.584 B | 24,381/20,013 s | 0,1809 s |
| 137 | passou | 34,0513 s | 2.427,93 s | 2.097.352.704 B | 40.468.480 B | 26,867/22,527 s | 0,2065 s |

Todas as métricas ficaram abaixo dos limites congelados; `natural_ok=true` e `ok=true`. A mortalidade por privação foi 4.545/2.730/3.166 e a saúde média final 96,50/225,88/246,75 para as seeds 73/101/137. Assim, a integridade causal e o budget técnico passaram; a resiliência e saúde econômica continuam sendo um problema de produto a avaliar e não são certificadas por este gate.

## E200 — integração final do Gate D — 27/09/2026

No mesmo checkout E199, o cenário autônomo controlado `test_prepared_crisis_runs_actor_choices_without_post_start_injection` passou (`1 passed`, 3,97 s). O ciclo público de API criou o mundo, avançou 360 dias e retomou o save (`1 passed`, 312,89 s). Dossiês, dossiê de ator, auditoria causal e testes do gate passaram (`27 passed`, 10,78 s); Crônica, dossiê, observatório e app passaram (`33 passed`, 3,44 s). Build/type-check do frontend passou; Vite manteve aviso de chunk de 772,8 kB. No save natural E199 da seed 137, `why()` respondeu às 20 consultas com vínculos válidos e p95 `0,1721 s`.

Com o provider corpus real E195, o cenário controlado e as três seeds E199, os itens finais do Gate D passaram no checkout `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28`. `git diff --check` passou. Isto fecha o aceite técnico V1 descrito no plano; não certifica a economia como saudável: as três trajetórias ainda têm mortalidade por privação alta e diferenças fortes de saúde. Também não marca como concluídas verticais explicitamente fora do escopo V1.

## E201 — crédito familiar voluntário — 27/09/2026

Foi implementado um mecanismo de empréstimo sem juros, sem criar moeda e sem
pagamento automático. O gatilho é um receipt atual de folha pública
`unpaid_funds`; a instituição autorizada decide pedir o valor que a engine
calcula a partir do saldo real de folha e do tesouro. O pedido gera avisos
datados somente para grupos presentes no mesmo assentamento. Cada grupo vê
opções calculadas de seu saldo próprio, preservando uma reserva equivalente a
um dia de alimento local; não recebe saldo privado de outros grupos.

O grupo pode emprestar por affordance própria. A execução revalida pedido,
aviso, saldo, presença e decisão no candidato mensal, transfere o principal
existente e persiste a obrigação. O prazo é 180 dias; a devolução integral do
principal só ocorre após nova escolha da instituição e quando o caixa comporta
o pagamento. Não há juros, renegociação, inadimplência automática ou crédito
criado neste recorte. Saves anteriores a Economy 17/Knowledge 9/save 75 são
rejeitados, sem migração.

Verificação focal: `tests/test_medieval_family_loans.py`,
`tests/test_medieval_permanent_employment.py` e
`tests/test_medieval_institutional_agenda.py`: 31 passaram. `ruff check` nos
arquivos Python afetados, compileall focado e `git diff --check` passaram. Uma
rodada adjacente mais ampla marcou 49/51: duas falhas em fixtures de
`test_medieval_economy.py` (transferência de ocupação idêntica, e expectativa de
falta alimentar em cenário sem contrato de folha). Elas não foram atribuídas
ao empréstimo, mas também não houve baseline limpo suficiente para classificá-
las como falhas preexistentes; permanecem como anomalias não resolvidas desta
branch WIP.

**Limite da evidência:** o teste prepara saldo de família e escolhe as decisões;
não mostra pedido, oferta ou empréstimo emergindo numa seed natural. Uma
consulta direta autorizada ao Codex OAuth/Luna recebeu o menu gerado pela
engine e escolheu o ID canônico de 100 unidades (`E202`); foi uma interpretação
externa sem executar o owner nem gerar receipt no runtime do jogo. Isso não é o
corpus provider do Gate D. A adoção natural e a capacidade do empréstimo de
alterar a trajetória econômica continuam abertas. E201 não fecha o roadmap
geral nem altera a conclusão restrita do Gate D técnico E200. Nenhum commit,
push ou deploy foi realizado neste checkpoint.

## E203 — escolha real com receipt no runtime do jogo — 27/09/2026

Uma segunda consulta limitada usou o caminho real `ai_decider.select_option`
e `call_llm_json`/`codex_cli`, com modelo `gpt-6-luna`. Para evitar alterar a
configuração persistida, um perfil `codex_cli` foi fornecido somente em memória
durante a fixture. O provedor selecionou a opção canônica de 50 unidades dentre
as duas oferecidas (50 e 100). A engine gravou um receipt
`ai_decision_interpreted`, `causal_origin=llm_interpretation`, sem deltas; a
resposta foi validada contra os IDs atuais. Nenhum owner material foi chamado,
nenhum empréstimo foi financiado e nenhum save foi escrito.

Isso fecha a sondagem curta do boundary provider para a vertical familiar,
incluindo formato de resposta e receipt sem mutação, mas não o corpus provider
representativo do Gate D, pois foi uma única decisão em fixture. Também não
prova que o provider persistido da aplicação esteja configurado (o runtime
persistido permaneceu indisponível nesta máquina), nem adoção ou efeito
econômico natural. Nenhum perfil ou segredo foi salvo.

## E204 — mês natural com Codex OAuth/Luna — 27/09/2026

Um mundo novo, seed 73, avançou do dia zero ao dia 30 sem decisões injetadas,
usando o boundary do jogo e `gpt-6-luna` via configuração `codex_cli` apenas em
memória. Foram persistidos 729 eventos e 15 receipts de decisão provider. No
dia 30 não havia evento de folha pública `unpaid_funds`, pedido familiar nem
opção de empréstimo aberta. A etapa seguinte precisou de decisão de
`character:character:002` após alcançar o limite configurado de 20 consultas;
`ProviderDecisionRequired` abortou o candidato e o mundo ficou no dia 30. Não
foi escrito save nem ocorreu alteração em mundo persistido.

O wrapper de medição tentou depois chamar `world.validate()`, API que não
existe, e saiu com `AttributeError` após imprimir o resumo. Portanto não se
alega auditoria causal standalone, save/load ou validação manual deste run; a
integridade dos passos que chegaram a commit foi responsabilidade do finalizer
normal do `MedievalSimulator`. A contagem de 15 é apenas receipt preservado no
mundo publicado; respostas em um candidato abortado não persistem e seu número
não foi registrado de forma independente. O resultado não mostra crise nem
adaptação: 30 dias foram insuficientes para alcançar o gatilho. Próximo:
preflightar sem provider o primeiro dia natural de `unpaid_funds`, então
planejar um run com orçamento de provider compatível e journal/revalidação
correta, sem injetar pedido ou empréstimo.

## E205 — preflight offline do gatilho de crédito — 27/09/2026

A seed 73 do E205 foi retomada do save E205 dia 120 até o dia 480 com o smoke
offline (`ai_enabled=false`, `routine-rules`, sem provider real). O processo
preservou checkpoints nos dias 210, 300, 390 e 480; todos passaram conservação
e save/load. O save final tem 17.984 eventos, 5,8 MB; auditoria standalone
retornou `ok=true`, com zero causas quebradas, material não enraizado, erros de
autoria/fonte, Story material ou interpretação material. Dinheiro e recursos
foram conservados. Nenhum artifact existente foi sobrescrito.

O primeiro `permanent_employment_unpaid` ocorreu no dia 480 (`event:16895`), no
contrato de Escarlia para artesãos orcs de Ferroalto, folha bruta 178. Depois
da produção daquele ciclo, a conta do tesouro terminou com 1.970; o builder
recompõe o pedido a partir do shortfall atual, então não ofereceu pedido e não
foram criados aviso/loan. No mesmo assentamento, grupos presentes tinham
saldo lendável, após reserva alimentar própria, de 4.487 (anões agricultores)
e 560 (elfos agricultores); outros grupos tinham zero. Isso mostra capacidade
potencial dos credores, não conhecimento, pedido, oferta recebida ou decisão.
O fallback offline criou 21 contratos ao longo dos 480 dias; esse comportamento
não é provider real nem preferência de política. O passo após o receipt não foi
executado com IA e a seed não testou `NO_ACTION` ou aceitação real.

Conclusão limitada: o gatilho material pode aparecer naturalmente, mas neste
caso já não havia shortfall no momento da escolha mensal. A affordance continua
aberta apenas enquanto há falta atual de caixa. O item de adoção/recusa natural
permanece aberto; não se deve declarar que famílias rejeitaram nem que
emprestaram. O próximo teste deve observar um estado em que o shortfall ainda
esteja presente na consulta, com provider/autoria válidos e orçamento
compatível, sem injetar o pedido ou qualquer escolha.

## E215 — continuação pareada sem novas escolhas injetadas — 27/09/2026

Os dois ramos do E213/E214 foram avançados offline por mais 120 dias, do dia
638 ao dia 758, sem novas decisões explícitas. O ramo de controle terminou com
falta alimentar 422, saúde média 677,75, unrest médio 134,50 e tesouro de
Escarlia 627. O ramo da pausa de staffing terminou com falta 778, saúde média
679,25, unrest médio 133,12 e tesouro 2.151. Não houve mortes por privação no
intervalo. Os resultados agregados divergiram sob políticas de rotina e
consequências subsequentes; portanto não atribuo a diferença inteira à pausa
original.

As auditorias standalone dos dois saves do dia 758 passaram (`ok=true`):
28.157/28.317 eventos, 20.062/20.191 materiais e zero causas quebradas,
erros de autoria/origem/fonte, Story material ou interpretação material. As
trilhas preservam os limites causais, mas a economia segue sob pressão; isso
não é gate natural longo nem prova de recuperação.

O diagnóstico local reforça que falta alimentar não equivale a falta agregada
de estoque. Em Cinzaverde, o ramo de staffing tinha 30.947 rações públicas para
926 moradores, preço 1, mas 401 faltantes; o evento de subsistência registra
377 domésticas e 142 rações compradas, além de grupos incapazes de pagar. A
opção canônica de construir oficina continuava disponível no menu de Escarlia,
com tesouro 2.151 e custo estimado de 168 para insumos e salários. Nenhum ator
offline a escolheu; não houve nova decisão de staffing neste trecho.

## E216 — Luna seleciona a oficina atual, sem execução do owner — 27/09/2026

Uma consulta real ao Codex OAuth/Luna (`gpt-5.6-luna`) foi feita pelo boundary
de seleção com o menu mensal completo recomposto do save clone E215, no dia
758. Entre 14 affordances canônicas, a resposta selecionou
`site-construction:polity:escarlia:cinzaverde:craft-workshop-construction:event:27986`,
oferecida pela engine. O log confirma resposta JSON válida e a leitura do
dossiê do ator mostrava, entre outros fatos, quatro linhas produtivas com
`payroll_funds`, objetivos existentes de reserva alimentar/insumos e tesouro
local da instituição.

A consulta apenas selecionou o ID: não chamou o executor, não criou decisão ou
receipt persistido, não avançou o mundo e não salvou o clone. O save de origem
permaneceu intacto. Portanto E216 prova elegibilidade atual e uma escolha real
do provider, mas ainda não prova owner revalidando essa escolha, início da
obra, nova fundação produtiva, emprego, salário ou melhora de acesso alimentar.
Próximo recorte: aplicar o ID escolhido somente a uma cópia descartável via
caminho canônico, auditar autoria/causas e acompanhar a cadeia material; manter
claro que replay isolado da resposta não equivale a um turno natural completo.

## E217 — replay auditável da seleção E216 no owner canônico — 27/09/2026

Para exercitar o limite de execução sem nova chamada externa, recarreguei o
save E215 de staffing como ramo descartável e reapresentei a resposta exata de
E216 ao turno institucional mensal completo de Escarlia. A engine recompôs o
menu e confirmou que o ID continuava válido. O turno gravou receipt
`ai_decision_interpreted` de origem `llm_interpretation`, sem deltas; em seguida
registrou a decisão do ator e o owner de construção revalidou a opção e criou
`expansion:event:28815`, stage `waiting`, no dia 758. O projeto não cria site,
linha, emprego ou renda imediatamente.

O ramo foi salvo separadamente em
`/tmp/cws-e216-luna-workshop-replay-day0758.mws`; o save de origem não foi
alterado. A auditoria causal passou (`ok=true`), com zero causas quebradas,
erros de autoria e eventos materiais de interpretação. Este replay demonstra
que a resposta real do provider atravessa o receipt, a decisão e o owner
canônico em clone; como a resposta foi reproduzida localmente e não veio de uma
consulta nova durante o turno, não é uma execução natural/provider end-to-end.
Próximo: acompanhar o projeto por fronteiras mensais e verificar materiais,
trabalho pago, conclusão, fundação separada de linha e efeito doméstico contra
controle pareado, sem injetar recursos.

## E218–E221 — frete físico, bloqueios temporários e conclusão da oficina — 27/09/2026

A cópia E217 foi avançada sem novas consultas externas e sem injetar recursos.
No dia 780, a obra bloqueou por falta de madeira. O mundo possuía fonte real em
Salgueiro (Valedouro), com estoque excedente de 6.312 unidades; Escarlia gerou
um pedido de 48 por sua política offline `routine-rules`, Valedouro aceitou
pela política offline independente, e o owner abriu o frete com custo total
96, reserva da carga na fonte e rota física via Porto Velho. Logo, esta
continuação comprova transporte material e owners bilaterais, mas não decisão
provider do comprador/vendedor.

O frete entregou as 48 madeiras no dia 792. No dia 810 a construção avançou de
0 para 1 unidade; no dia 840 chegou a 3/12. No dia 870 ficou temporariamente
`blocked` por `payroll_funds`; não houve unidades ou salário inventados nesse
turno. Após a condição de caixa voltar a permitir trabalho, a construção
progrediu nos dias 900 (7/12), 930 (11/12) e 960 (12/12), quando o owner
comissionou `site:cinzaverde:workshop` com capacidade `craftsmanship`.
Auditorias dos saves dias 788, 818, 878 e 960 retornaram `ok=true` e zero
causas quebradas; nenhuma fonte de estoque ou dinheiro foi criada. No dia 960
restaram zero madeira e duas pedras no estoque local; não existe ainda linha de
produção no sítio.

O estado com oficina concluída recompõe uma affordance `line_foundation`
canônica para `craft-workshop-foundation` e mostra 76 opções concorrentes no
menu mensal completo de Escarlia. Uma consulta real Codex OAuth/Luna para esse
menu foi iniciada como E222 e interrompida após mais de dez minutos sem
resposta visível. O log não registrou `LLM_INTERACTION`/receipt e nenhum save
de saída foi criado; como o owner só executa depois da resposta, a cópia E221 e
o mundo original ficaram intactos. Não repetir automaticamente nem contar como
escolha. A cadeia continua sem prova de fundação de linha, produção, emprego,
salário, compra doméstica ou redução da falta alimentar.

O motivo da latência ainda é desconhecido. O menu tinha 76 opções; a medição
local sem rede foi registrada em E223 para separar payload excessivo de
falha/latência do provider. Nenhum segredo foi impresso nem enviado nessa
medição.

## E223 — diagnóstico local de prompt e OAuth — 27/09/2026

A recomposição sem rede do mesmo estado gerou prompt de 53.860 bytes (53.578
caracteres), com 76 opções e 19 fragmentos de situação; o maior foi
`employment_staffing`, 16.994 bytes. O tamanho não é enorme e, sozinho, não
explica a espera. `codex login status` retornou código 0 e indicou sessão local
autenticada; nenhuma identidade ou token foi impressa. Naquele ponto o client
usava `subprocess.run(..., timeout=180)` para Codex CLI e `max_parse_retries=3`;
E224 depois trocou para `Popen` e encerra o grupo no timeout. O processo do
provider não retornou erro legível, então a causa do E222 permanece
desconhecida.

## E224 — timeout do Codex CLI encerra o grupo de processos — 27/09/2026

Um reproducer local demonstrou que encerrar somente o processo direto pode
deixar helpers ativos. O client agora inicia Codex CLI numa sessão própria e,
no timeout, encerra o grupo, aguarda o processo direto e fecha os pipes sem
esperar EOF de helpers destacados. O limite segue 180 segundos; nenhum
comportamento de decisão ou retry mudou. O teste focal também cobre um helper
em nova sessão que mantém os pipes abertos.
`tests/test_llm_codex_cli.py`: `3 passed`; `git diff --check`: limpo.

Isto corrige o vazamento reproduzido, mas não prova que era a causa da espera
de E222: o timeout de 180 segundos deveria ter retornado, e essa divergência
segue sem explicação. Não houve nova consulta OAuth/Luna; nenhuma affordance foi
selecionada, nenhum save foi alterado e os gates econômicos permanecem abertos.

## E225 — nova sonda controlada sem resultado — 27/09/2026

A sonda do dossiê completo foi executada contra o save E221/dia 960, com uma
consulta no máximo, candidato em memória e verificação de hash do save-fonte.
Uma tentativa inicial falhou antes do provider porque `CWS_DATA_DIR` isolava as
configurações. Na repetição, um perfil temporário apontou para Codex OAuth/Luna;
nenhuma chave real foi fornecida ou gravada. Mesmo com a correção E224, a
chamada ficou mais de sete minutos sem saída e foi interrompida (código 130).
Não há resultado/receipt; a sonda não grava o mundo candidato. Isso confirma
que o timeout ainda não está governando o caminho observado, mas não localiza
qual estágio bloqueia. Não repetir até instrumentar os limites entre agenda,
`asyncio.to_thread`, processo CLI e resposta.

## E226 — experimento de timeout pelo wrapper assíncrono — 27/09/2026

Uma ampliação temporária do teste tentou percorrer `call_llm_json` e
`asyncio.to_thread` com CLI falso. O caso ficou parado no event loop; o
faulthandler mostrou a thread worker ociosa e o loop aguardando. Reproducer
isolado em Python 3.11 e 3.14 confirmou que `asyncio.run()` pode ficar preso no
`shutdown_default_executor` quando a coroutine capturou uma exceção do worker;
o desligamento manual do mesmo executor encerrou normalmente. Isso torna
plausível que o probe escondesse um timeout/erro do provider durante o
encerramento, mas não prova que foi a causa observada em E225.

## E227 — runner one-shot do probe — 27/09/2026

O probe local agora usa um event loop próprio e encerra explicitamente o
`ThreadPoolExecutor` antes de fechar o loop, evitando depender do caminho de
shutdown de `asyncio.run()`. Um teste faz `asyncio.to_thread()` levantar uma
exceção capturada e confirma que o runner retorna; outro usa Codex CLI falso,
processos auxiliares no mesmo grupo e um auxiliar destacado que mantém os pipes
abertos. `CWS_DATA_DIR=/tmp/cws-e227-test-data .venv/bin/pytest -q
tests/test_llm_codex_cli.py`: `4 passed`; `py_compile` nos três arquivos
alterados e `git diff --check` passaram. Isso valida somente o harness e o
transporte local, não o provider real nem a causa de E225. Próximo: uma consulta
limitada no clone E221, com hash do save fonte verificado.

## E228 — consulta OAuth/Luna ainda sem resposta — 27/09/2026

A tentativa inicial de invocação falhou antes de executar por falta de
`PYTHONPATH`; nenhum prompt foi enviado. Repeti com a raiz do projeto no
`PYTHONPATH`, perfil efêmero Codex CLI/Luna e timeout externo de 230 segundos.
Após carregar o contexto do projeto, não houve resposta ou saída do probe; o
limite externo encerrou o processo (124). Portanto não existe decisão, receipt
ou execução material. Não repetir até localizar com CLI falso qual fronteira
continua presa; o runner local, embora passe seu teste de erro, não resolveu a
sonda real. O arquivo fonte foi aberto apenas para leitura pelo script; seu
SHA-256 observado depois da tentativa é
`648db6bec7e58afa4c6841eddbc5814d2b4a9989fd9dae492f4a88bfffdff810`.
Nenhum processo `codex` ou probe ficou remanescente na verificação posterior.

## E229 — wake do worker Codex e probe falso completo — 27/09/2026

Com CLI falso, o worker de `_call_codex` concluía em milissegundos, mas o loop
às vezes seguia esperando no selector até algum timer futuro; um polling de
50 ms na espera do provider Codex fez o resultado ser observado. O ajuste é
restrito ao formato `codex_cli`; outros providers mantêm `asyncio.to_thread`
normal. Teste assíncrono focal somado aos testes anteriores:
`CWS_DATA_DIR=/tmp/cws-e232-test-data .venv/bin/pytest -q
tests/test_llm_codex_cli.py` = `5 passed`; `py_compile` e `git diff --check`
passaram.

O probe oficial completo com CLI falso respondeu `NO_ACTION` para o menu de 76
opções de Escarlia, gravou apenas receipt zero-delta no candidato, passou
validações e retornou `persisted=false`; SHA-256 fonte
`648db6bec7e58afa4c6841eddbc5814d2b4a9989fd9dae492f4a88bfffdff810`, idêntico
ao observado após E228. Isso valida a cadeia local com fake, não uma decisão da
IA real.

## E230 — Codex OAuth bloqueado pelo sandbox read-only — 27/09/2026

Uma tentativa real após E229 encerrou rapidamente com código 1. O Codex CLI
aceitou o prompt local, mas falhou ao inicializar o app-server porque não pôde
criar aliases/configuração no filesystem read-only (`Operation not permitted`).
Não houve resposta do modelo, receipt ou execução de owner. O login OAuth existe,
mas esse processo sandbox não pode usar o diretório de configuração como o CLI
espera. Não copiar credenciais para `/tmp` nem contornar a proteção; uma chamada
posterior só pode usar o diretório local gravável sob execução autorizada.

## E231 — consulta Codex OAuth/Luna no menu civil — 27/09/2026

Com execução autorizada para o CLI inicializar seu app-server no diretório
OAuth existente, uma consulta real foi concluída em 8,55 s. Escarlia recebeu
menu institucional completo de 76 opções e Luna selecionou o ID canônico
`supply-objective:polity:escarlia:supply:ferroalto:960`, rotulado “Executar o
abastecimento disponível para um assentamento pressionado.” O receipt
`ai_decision_interpreted` não continha deltas. O owner gerou dois eventos/deltas
no candidato em memória; não foi persistido. `source_sha256_unchanged` foi
`648db6bec7e58afa4c6841eddbc5814d2b4a9989fd9dae492f4a88bfffdff810`. Esta é
uma escolha real válida no checkout atual, mas não é o corpus de 10 decisões.

## E232 — replay isolado da decisão real — 27/09/2026

A primeira tentativa de replay falhou fechada por ausência de configuração de
provider no `CWS_DATA_DIR` isolado; o perfil não foi herdado. Repeti com perfil
Codex/Luna efêmero e `call_llm_json` local devolvendo exatamente o ID E231 (sem
segunda consulta). Menu recomposto ainda oferecia o ID. O turno completo
registrou receipt `ai_decision_interpreted` sem delta, executou o owner de
abastecimento e persistiu apenas em
`/tmp/cws-e232-luna-supply-objective-replay.mws`. O clone tem 4 eventos novos,
2 eventos materiais e 2 deltas; validações de histórico, estado e atividades
passaram. `tools/medieval_causal_audit.py` retornou `ok=true`, zero causas
quebradas, erros de autoria ou Story/interpretation-material. SHA-256 do save
fonte manteve o valor acima. O replay preserva o output real do provider mas não
equivale a uma segunda decisão real nem a evolução natural.

## E233 — opção de abastecimento repetida sem nova carga — 27/09/2026

No clone E232, Luna recebeu 76 opções e selecionou novamente o mesmo ID
`supply-objective` (consulta real, receipt sem delta). O replay exato no mesmo
estado criou zero novos IDs de frete. O sufixo foi apenas receipt de decisão,
decisão do turno e dois `supply_plan_updated`; o plano continuou
`await_delivery` com os mesmos fretes `34705` e `37672`. A opção era redundante:
`_would_open_an_order` inferia materialidade do estágio `await_delivery`, que
também é mantido por pedidos existentes. Não é uma ação material escolhida que
deva contar como progresso da cadeia.

## E234 — prévia de abastecimento exige frete novo — 27/09/2026

`_would_open_an_order` agora compara os IDs de `economy.freight_orders` antes e
depois de executar a política real na cópia descartável. Um teste focado foi
executado antes da correção e falhou reproduzindo o falso positivo; após a
correção, `CWS_DATA_DIR=/tmp/cws-e234-regression-after .venv/bin/pytest -q
tests/test_medieval_concurrent_civil_decision.py` retornou `24 passed` em
10,98 s e `git diff --check` passou. A recomposição do clone E232 mostra 75
opções e nenhuma `supply-objective` redundante. Nenhum save ou estoque foi
alterado pelo diagnóstico. Próximo: uma consulta real não orientada no menu
corrigido, se houver opção atual; então manter o objetivo econômico em foco.

## E235 — consulta não direcionada Luna após correção — 27/09/2026

O menu do clone E232 foi recomposto com o código atual: 75 opções e nenhuma
affordance redundante de `supply-objective`. Uma consulta real Codex OAuth/Luna
escolheu o ID canônico
`relief-distribute:escarlia:ferroalto:653:event:37411:event:37013`, para
distribuir 653 rações de ajuda gratuita a Ferroalto. Receipt
`ai_decision_interpreted` sem delta; owner executou apenas no candidato em
memória: 22 eventos materiais e 40 deltas; `persisted=false`. O hash do clone
fonte foi `a09241ba14ffbc2405a3bfc086a11d7a983e7d24d1d3331eaa31ec9b436b8f5d`.
Esta é uma segunda família de escolha positiva no menu corrente, não fecha o
corpus de dez decisões nem prova adoção natural.

## E236 — primeira tentativa de replay sem provider configurado — 27/09/2026

A reprodução local exata do ID E235 falhou antes da seleção com
`ProviderDecisionRequired`: o `CWS_DATA_DIR` isolado não tinha perfil ativo de
provider. Não houve chamada externa, execução material ou save de saída. A
classificação é falha de configuração do harness de replay; a correção mínima
foi iniciar um diretório efêmero com a configuração Codex/Luna já usada nos
probes e interceptar localmente a resposta para impedir egress.

## E237 — replay material do auxílio e auditoria causal — 27/09/2026

Com o perfil efêmero, o replay local do ID exato E235 foi aceito pelo menu e
gravado apenas no clone `/tmp/cws-e235-luna-relief-replay.mws`; nenhuma nova
consulta ao provider ocorreu. O owner emitiu `relief_distributed`: estoque
público de Ferroalto `1563→910`, falta alimentar `653→0`, saúde `611→631`,
unrest `385→365`, além de distribuir alimento às coortes locais. O receipt LLM
continuou sem deltas. `validate_history`, `__post_init__` e
`validate_activities` passaram. A auditoria standalone terminou com `ok=true`,
zero causas quebradas, erros de autoria, eventos materiais sem raiz,
Story-material ou interpretation-material. Hash do save-fonte E232 permaneceu
`a09241ba14ffbc2405a3bfc086a11d7a983e7d24d1d3331eaa31ec9b436b8f5d`. O recorte
prova capacidade material de resposta à falta corrente em uma decisão replay;
não demonstra persistência da recuperação, continuidade natural, contraponto
sem ação ou fechamento do Gate B.

## E238 — contrafactual NO_ACTION no mesmo save-base — 27/09/2026

Recompus o mesmo menu corrigido de 75 affordances no clone-fonte E232 e
reproduzi `NO_ACTION` via resposta local fixa, sem egress. O receipt foi
`ai_decision_declined`, com dois eventos de sufixo e zero eventos/deltas
materiais; o clone de controle foi salvo em
`/tmp/cws-e238-luna-no-action-control.mws`. SHA-256 do save-base permaneceu
`a09241ba14ffbc2405a3bfc086a11d7a983e7d24d1d3331eaa31ec9b436b8f5d`. A
auditoria standalone passou: `ok=true`, dia 960, 37.851 eventos, zero causas
quebradas, erros de autoria, Story/interpretation-material ou eventos
materiais sem raiz. Em comparação com E237, a escolha material altera o estado
enquanto a inação não; é contrafactual controlado, não comportamento emergente
natural.

## E239 — runtime shadow indisponível na sessão — 27/09/2026

O contrato da tarefa exige acompanhamento MetaGame/Laya em shadow quando o
runtime local está disponível. Não há ferramenta correspondente no catálogo
desta sessão (`ALL_TOOLS` sem entradas de observer/Laya/MetaGame), e
`HERDR_ENV=1 herdr pane list` retornou `Operation not permitted`. Nenhum
observer foi iniciado; não atribuir sinal Laya a este recorte. A pendência é de
acesso ao runtime, não de decisão do mundo, e não impede a implementação local.

## E240 — corpus provider histórico rejeitado por schema — 27/09/2026

A prévia sem egress do corpus de dez consultas foi tentada com os seis saves
usados em E195/E194 (E179, E183, E184, E186, seed 101 e seed 14). O primeiro
save falhou em `load_world` com `Unsupported Medieval World Simulator save`;
portanto nenhuma prompt foi enviada nem consulta consumida. É evidência de que
o corpus preparado não é reutilizável no schema deste checkout, não prova
defeito no loader atual. Próximo: gerar novos cenários/fixtures sobre saves
schema atual e repetir a prévia local antes de qualquer egress.

## E241 — inventário de fontes atuais para corpus — 27/09/2026

Uma leitura read-only de metadados encontrou 28 saves locais com produto e
schema atuais (`medieval-world-simulator`, 76). E210 (dia 480), E214/E215 e
E221 são candidatos carregáveis. No E210, Auren, Escarlia e Valedouro têm
affordances de `relief`, mas não `aid_request`; cada polidade também possui
notices de pedidos de ajuda ainda abertos que ocupam os provedores disponíveis.
Isso explica por que os fixtures antigos não recompõem o mesmo menu. Não alterei
nenhum arquivo-fonte. A preparação deve resolver ou selecionar notices pelos
owners canônicos antes de pedir nova affordance; não remover o guardrail de
pedidos pendentes.

## E242 — continuação pareada E237/E238 por 30 dias — 27/09/2026

Avancei os dois clones do dia 960 ao 990, desabilitando provider e mantendo a
mesma política offline `routine-rules`. O primeiro controle de conservação
usou incorretamente estoque invariável e rejeitou consumo material legítimo;
nenhum output foi salvo nessa tentativa. A repetição usou
`resource_totals = inicial + ledger_resource_effects` e saldo agregado de
moeda, conforme o smoke do projeto. Em ambos os ramos: conservação de recursos
e dinheiro passou, save/load ficou equivalente, zero mortes por privação e
falta alimentar final zero. Ramo com auxílio: saúde `631→603`, unrest
`365→393`, household food `653→873`, 39.886 eventos. Controle: saúde
`611→548`, unrest `385→448`, household food `0→1526`, 39.856 eventos. No
intervalo, o fallback também tomou decisões materiais (3 distribuições de
auxílio no controle, 4 no ramo E237 e 27 compras domésticas em cada); logo a
diferença final não pode ser atribuída exclusivamente à escolha Luna. Isso
mostra que o efeito relativo inicial sobreviveu neste horizonte sob a mesma
política fallback, não que a economia esteja saudável ou natural.

## E243 — auditoria dos dois ramos continuados — 27/09/2026

Auditorias standalone dos saves E245 terminaram com `ok=true`. O ramo de
auxílio tem 39.886 eventos/29.872 materiais e o controle 39.856/29.840.
Ambos: zero broken causes, decision authorship/source errors, root premise
errors, Story-material, interpretation-material e unrooted material events.
São evidências apenas dessas duas trajetórias fixture/fallback, sem provider
novo e sem gate natural amplo.

## E256 — corpus atual preparado e prévia sem egress — 27/09/2026

O corpus foi reconstruído sobre saves schema 76: seeds 101/14 no dia 480 com
checkpoints, conservação e save/load; fixtures de pedido foram preparadas por
respostas dos owners aos notices pendentes; a campanha/rota veio de teste
focado existente. A prévia final recompôs dez contextos atuais sem egress,
conferiu affordances/IDs oferecidos, conhecimento do ator e ausência de
handles de estoque/conta alheios. Nenhum save-fonte foi modificado. Os saves
locais são `/tmp/cws-e252-schema76-seed101-day0480.mws`,
`/tmp/cws-e253-schema76-seed14-day0480.mws`,
`/tmp/cws-e254-schema76-seed101-request-ready.mws`,
`/tmp/cws-e255-schema76-seed14-request-ready.mws` e
`/tmp/cws-route-corpus-fixture/test_prepared_crisis_runs_acto0/pre-route-review.mws`.
São fixtures/corpus de provider, não o gate natural final.

## E257 — probes reais de campanha e defeito de evidência da criatura — 27/09/2026

Uma chamada Codex OAuth/Luna selecionou uma retirada oferecida ao comandante;
o receipt foi válido e zero-delta, e a execução permaneceu num clone. Uma
segunda resposta selecionou a affordance canônica de demanda de criatura, mas
o owner falhou porque usou como percepção um `creature_ecology_tick` em vez da
travessia de carga observada. Nenhuma alteração foi gravada no save original.
Isso identificou defeito material real; não foi contado como execução válida
da demanda.

## E258 — percepção de rota da criatura corrigida e regressões focadas — 27/09/2026

O owner agora procura a última percepção de carga ligada à rota específica e
só oferece/aceita a demanda quando essa evidência existe. O evento da demanda
aponta para a percepção canônica. A resposta live anterior foi reproduzida em
clone sem nova consulta e passou `validate_history` e validação do snapshot.
Verificação focal: criaturas, campanha/criatura, observatório e probe,
`9 passed`; testes adjacentes de autonomia de criatura, interação mágica e
sabotagem, `27 passed`. Não houve mutação de save-fonte.

## E259 — criatura e QG com decisões independentes — 27/09/2026

Uma consulta Luna posterior escolheu `maintain` no menu atual da criatura; o
owner produziu receipt válido e zero-delta, em clone. Uma consulta separada
somente ao QG escolheu reroute entre três affordances correntes; gerou receipt
válido zero-delta e candidato material somente em memória. O probe do QG não
repetiu nem reaproveitou o contexto do comandante. Fontes permaneceram
intactas. Isto valida seleções situadas, não uma campanha natural completa.

## E260 — decisões civis atuais do corpus OAuth/Luna — 27/09/2026

Oito consultas independentes cobriram economia de Auren, obrigação próxima do
prazo e disputa alimento/defesa em Escarlia, além dos atores Auren, Escarlia e
Valedouro nas duas seeds preparadas. As respostas selecionaram IDs existentes
nos menus. Todos os receipts de interpretação tiveram zero delta; a simulação
material foi restrita a clones e as fontes mantiveram o hash. Em conjunto com
comandante, QG e criatura, esta rodada totalizou 12 consultas reais (uma delas
revelou o erro do owner antes de sua correção); três consultas anteriores já
haviam sido contabilizadas contra a autorização máxima de 20.

## E261 — preview final e testes do checkpoint atual — 27/09/2026

A prévia do corpus de dez contextos passou novamente sem egress. Testes focados
de criatura/campanha/observatório/probe passaram `9`; os adjacentes passaram
`27`; compilação dos arquivos alterados e `git diff --check` passaram. Os
resultados cobrem os owners e cenários indicados, não todos os owners nem os
gates de economia natural, campanha multissistema emergente ou dez anos.

## E262 — estado do gate depois do corpus — 27/09/2026

O corpus provider atual está exercitado com escolhas Luna em cenários
preparados, mas isto não fecha o Gate D completo nem o aceite V1: falta
reestabilizar o código e executar novamente as três seeds por 3.600 dias com
checkpoints, conservação, save/load/continuação, auditoria e limites
operacionais. Gate B ainda precisa fechar capacidade adaptativa no mundo
natural; Gate C ainda não observou a cadeia política/comando/logística/social
completa surgindo naturalmente. Nenhum commit, push ou deploy foi feito.

## E263 — relief contrafactual em save atual — 27/09/2026

No save schema 76 E252, o relatório que Auren publicou/conhece para
Campomanso registra falta alimentar 223 e health 823, enquanto o estoque
público contém 27.502 rações. Uma affordance vigente oferece relief de 223
(ou 111). Em clone, uma decisão API auditável selecionou a opção de 223; o
owner consumiu 223 do estoque público, distribuiu às pantries, reduziu falta
`223→0`, elevou health `823→843` e reduziu unrest `69→49`. História e snapshot
validaram, o controle carregado da fonte permaneceu em falta 223 e o hash
SHA-256 do save fonte não mudou. Isso atualiza a prova de capacidade adaptativa
aguda no checkout atual; não demonstra adoção natural nem sustentabilidade.

## E264 — diagnóstico de caixa da oficina e efeito confundido — 27/09/2026

No mesmo dia 480, a projeção mostra cash agregado por ocupação de 5.907 para
agricultores e 12 para artesãos; o menu de Auren possui 66 affordances,
incluindo relief e oficina em Campomanso, além de redução de contratos de
staffing. Não havia pedido de empréstimo familiar porque não existia contrato
de payroll elegível com `unpaid_funds`. Uma comparação canônica de 30 dias
selecionou obra, comprou e recebeu 48 madeiras pela rota Salgueiro–Campomanso,
mas a obra concluiu zero unidades e ficou `blocked/payroll_funds`. No controle
e na intervenção, a falta caiu para zero e health terminou em 788; ambos
receberam 223 rações por frete/relief no avanço offline. Assim o horizonte não
isola benefício da oficina, e o bloqueio de caixa no dia de execução impede
contar a construção como resposta eficaz neste caso. Fonte continua intacta.

**Conclusão do Gate B neste checkpoint:** existe resposta material corrente
para falta aguda, mas a adaptação estrutural de renda/acesso e a concorrência
por caixa da folha seguem em diagnóstico. O próximo teste deve isolar uma
alternativa existente (staffing/financiamento) e medir produção, salários e
acesso por janela apropriada, sem misturar política offline como se fosse
resposta do provider.

## E282 — relief recorrente em menu mensal composto — 28/09/2026

O contrafactual partiu do clone E277 após a fronteira comum do dia 450 e avançou
seis turnos mensais (480–630). A engine foi executada com `ai_enabled=true`,
mas selectors de provider foram interceptados em todos os módulos carregados:
nenhuma chamada externa ocorreu. O controle registrou decisão API `NO_ACTION`
para menus disponíveis; o tratamento fez o mesmo para todos os atores exceto
Auren, que selecionou somente a maior affordance de relief vigente para
Campomanso. O tratamento encontrou opção em quatro turnos (dias 510, 570, 600
e 630; quantidades 448, 518, 275 e 518); nos outros dois não havia opção atual.
Todos os atores compartilharam o menu mensal composto, e o owner revalidou a
opção antes da execução. Nenhuma escolha foi feita após o turno.

No dia 630, Campomanso terminou com falta `0` no tratamento contra `791` no
controle API `NO_ACTION`, health/unrest `854/44` contra `658/235`. As 1.759
rações foram retiradas do estoque público e alocadas a pantries; moeda agregada
permaneceu 76.000. A comparação por assentamento contra `NO_ACTION` atribui a
redução somente a Campomanso; os demais assentamentos tiveram delta zero.

Também foi rodado o fallback offline normal a partir do mesmo dia 450. Em seis
meses, ele produziu 18 receipts de relief e distribuiu 14.742 rações. Terminou
com falta agregada 433 (Campomanso 0), contra 5.823 no tratamento API limitado
a Auren/Campomanso. A diferença do ramo API contra offline ficou em `+5.390`
rações agregadas, concentradas nos outros assentamentos (Cinzaverde +481,
Ferroalto +1.440, Pedra Clara +1.480, Montenegro +243, Portovelho +1.347,
Salgueiro +399; Brumafria e Campomanso sem diferença). Isto não indica
transferência material causada pelo relief de Campomanso: revela que o desenho
controlado manteve os demais atores em `NO_ACTION`, enquanto o fallback offline
executou as decisões dos demais. Logo, o owner/affordance está provado, mas o
teste não aprova uma política de ator único como agência sistêmica.

As affordances existiram em 4/6 turnos (`510, 570, 600, 630`); não existiam em
`480` e `540`. `validate_history` e validações de Economy/Knowledge passaram em
cada ramo; os testes focados de relief/decision-turn passaram `28` após ajustar
os toy adapters de teste para incluir `actor_ref` e `selected_affordance_id`,
exigidos pelo contrato de autoria. Reavaliação do aceite limitado de M1: o ponto
de partida contém o empréstimo voluntário e a prioridade de produção de E277;
no ramo pareado, a única diferença de decisão é relief posterior. Com E208
(crédito paga folha e gera salário), E277 (prioridade usa caixa existente) e
este contrafactual, a cadeia preparada demonstra acesso material sustentado por
seis ciclos, sem crédito de dinheiro/alimento. `test_relief_only_reaches_households_with_unpaid_rations`
verifica que a distribuição vai somente a grupos com ração não atendida. O ramo
de ator único não demonstra política sistêmica: os demais atores escolheram
`NO_ACTION`, e o fallback offline agiu em 18 casos. Revalidação focal no checkout
atual: `CWS_DATA_DIR=/tmp/cws-m1-focused-20260928 PYTHONPATH=. .venv/bin/python
-m pytest -q tests/test_medieval_relief.py tests/test_medieval_family_loans.py
tests/test_medieval_production_priority.py
tests/test_medieval_institutional_decision_turn.py` — `42 passed in 11.05s`.
M1 fecha apenas para o cenário preparado; provider real, escolha independente
sistêmica, emergência natural, outros seeds e Gate B natural permanecem sem
prova para M8. Nenhum save-fonte foi alterado; sem commit, push ou deploy.

## E284 — seleção contextual de E139 e raízes das fixtures de campanha — 28/09/2026

Fingerprint de base: HEAD `e6ac8d374e8d0726c2567e18f54b5ada7e097dce`; SHA-256
do diff dos dois arquivos de teste alterados:
`6a043669bfa016b5d629ddbe6bbff67e6a7310a263202a20796bc5e4d5f7bc33`.
O stub controlado da crise E139 passou a escolher entre os textos e o papel do
ator no menu atual, sem consultar prefixo de affordance nem contador. As
fixtures persistentes agora declaram `root_premise` para o estoque inicial,
chegada da guarnição e interrupção de rota, que a auditoria havia apontado como
eventos materiais sem raiz.

Verificação reproduzível, com estado de teste isolado:
`CWS_DATA_DIR=/tmp/cws-m2-focused-20260928 PYTHONPATH=.
.venv/bin/python -m pytest -q tests/test_medieval_campaign_creature_interference.py
tests/test_medieval_garrison_policy.py tests/test_medieval_garrison_supply_objective.py
tests/test_medieval_persistent_campaign_chain.py` — `27 passed in 20.23s`;
`git diff --check` passou. O provider não estava configurado (`provider_available()
== False`), nenhuma consulta externa foi feita. Isto melhora a validade de
fixtures e fecha somente o sub-recorte de seleção sem IDs; não prova provider
real, ocorrência natural nem integra ainda operação, guarnição paga em ciclos
e saída bilateral na mesma trajetória. Próximo: completar a integração M2 e
contrafactual conforme o checkbox da matriz.

## E285 — conservação de população na guarnição preparada — 28/09/2026

Fingerprint de base: HEAD `ebc1324a49d04a85faf65337f5b2f7877c0dfbcc`; SHA-256
do diff de `tests/test_medieval_persistent_campaign_chain.py`:
`e83744d4b1070b4039aec57a25310897a7b8ca5825e36a0de0a635e72f78de78`.
O bootstrap de guarnição não copia mais uma coorte civil para uma identidade
militar que pode substituir soldados já existentes. Ele reduz uma coorte civil
local em 20 e aumenta a coorte militar existente em 20, mantendo o total
populacional idêntico; o mesmo receipt inclui ambos os deltas e a premissa do
cenário. As 600 rações do destacamento seguem como estoque inicial explícito da
fixture, não como carga entregue nem como evidência de logística emergente.

Verificação reproduzível no namespace isolado:
`CWS_DATA_DIR=/tmp/cws-m2-garrison-20260928 PYTHONPATH=.
.venv/bin/python -m pytest -q tests/test_medieval_campaign_creature_interference.py
tests/test_medieval_garrison_policy.py tests/test_medieval_garrison_supply_objective.py
tests/test_medieval_persistent_campaign_chain.py` — `28 passed in 20.50s`.
As trajetórias da campanha do módulo continuam executando auditoria causal nos
seus saves finais. Isto fecha somente conservação de pessoas na premissa da
guarnição; operação, abastecimento e saída política ainda não foram compostos
na mesma trajetória autônoma exigida pelo M2.
