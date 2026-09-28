# Plano para terminar o roadmap medieval

Atualizado em 27/09/2026, iniciado sobre `codex/medieval-remote` no checkpoint
local `ed13e80a`. Este plano define o trabalho que falta; não declara o roadmap
concluído. Fatos e resultados detalhados ficam em
`docs/handoff/medieval-current-state.md`; o produto desejado, em
`docs/handoff/medieval-roadmap.md`; checkpoints históricos, em
`medieval-roadmap-completion-plan.md`.

## Direção

Não abrir novas verticais enquanto as existentes não formarem um mundo
observável e sustentável. A regra continua:

```text
estado e evidência canônicos → affordances válidas → decisão independente
→ owner revalida/executa → fatos e deltas → conhecimento/memória → próximas decisões
```

Sem quotas de drama: estabilidade, `NO_ACTION`, crise ou guerra podem ser
resultados válidos. Pressões de teste podem ser construídas em fixtures, mas
eventos narrativos não podem forçar a trajetória natural.

## Checkpoints acompanhados

- [x] Implementar a affordance voluntária de empréstimo familiar ligada a uma
  folha pública atual `unpaid_funds`: pedido institucional, aviso local datado,
  opção do grupo limitada ao saldo próprio após reserva alimentar de um dia,
  transferência conservada, obrigação sem juros e devolução somente por nova
  decisão após 180 dias; teste focal e save/load passaram (E201). Isso prova o
  mecanismo preparado, não adoção natural nem resiliência econômica.
- [x] Consultar uma vez o Codex OAuth/Luna com o menu familiar canônico em
  fixture; o provider escolheu um ID oferecido e nenhuma affordance foi
  executada (E202). Essa sonda direta não cria receipt no runtime do jogo nem
  fecha o corpus real do Gate D.
- [x] Consultar o Codex OAuth/Luna através do `ai_decider.select_option` real:
  resposta correspondeu a ID ofertado e gerou receipt `LLM_INTERPRETATION` sem
  deltas; nenhum owner executado (E203). Perfil só em memória; uma chamada não
  equivale ao corpus provider do Gate D nem a comportamento natural.
- [x] Rodar um mês natural sem decisões injetadas, seed 73, com provider real e
  teto de 20 chamadas: dia 30, 729 eventos/15 receipts persistidos, zero folha
  `unpaid_funds`, pedido ou oferta de empréstimo; a tentativa seguinte parou
  pelo orçamento sem commit (E204). O resumo pós-run chamou um método de
  validação inexistente, portanto este recorte não tem auditoria/save-load.
- [x] Preflight offline seed 73/dia 0→480, sem provider, com conservação,
  save/load e auditoria causal verdes: surgiu receipt `unpaid_funds` no dia 480,
  mas após produção o tesouro escarliano estava em 1.970 para folha 178;
  nenhuma opção de pedido existia. Grupos presentes tinham saldos lendáveis de
  4.487 e 560, mas nenhum pedido/aviso. É gatilho transitório já resolvido no
  momento do turno, não decisão ou adoção natural (E205).
- [x] Dois preflights offline adicionais (seeds 101 e 137) até dia 480 também
  encontraram receipts transitórios de `unpaid_funds`, mas nenhuma opção de
  crédito no menu posterior; checkpoints, save/load e auditoria passaram (E206).
- [x] Corrigir financiamento parcial: contribuições de famílias independentes
  são limitadas ao saldo restante, cada grupo contribui uma única vez e as
  opções restantes persistem até o pedido ser totalmente financiado ou expirar;
  fixture de duas famílias, validação econômica e save/load passaram (E207).
- [x] Contrafactual pareado de caixa familiar: empréstimo integral paga a folha
  do ciclo seguinte e transfere salário real ao grupo empregado; sem empréstimo,
  o mesmo owner registra nova folha `unpaid_funds` (E208). Prova eficácia da
  affordance em fixture, não escolha ou adoção natural.
- [x] Revalidar rejeição explícita dos schemas substituídos: save 75 continua
  intacto após tentativa de load, Economy 17 é recusado e a consulta observacional
  faz save/load no schema 76 atual (E209).
- [x] Smoke natural offline no schema 76, seed 73, dia 0→480: os quatro
  checkpoints conservaram recursos e passaram save/load; auditoria standalone
  final `ok=true` (17.984 eventos, 12.313 materiais, sem causas quebradas,
  material sem raiz, erros de autoria/fonte, Story material ou interpretação
  material). Zero mortes por privação; ainda houve 1.148 unidades de falta e
  saúde média 865. Isso é somente um smoke curto, não fecha resiliência natural,
  adoção de crédito nem o gate de 3.600 dias (E210).
- [x] Continuar o mesmo mundo naturalmente do dia 480 ao 600, sem provider:
  houve 22 receipts `unpaid_funds` no total, mas no checkpoint do dia 510 a
  conta de Escarlia tinha 1.670 moedas para cinco contratos com folha bruta
  agregada de 1.424; as affordances atuais de empréstimo corretamente não
  apareceram. Dia 600: zero pedidos/empréstimos, auditoria limpa e 0 mortes,
  a soma de falta alimentar nesses quatro meses foi 3.244 (E210 somava 1.148
  em 16 meses, janelas diferentes), e a saúde média final caiu a 775,75
  (E211). Isso refuta a hipótese de déficit persistente de caixa como explicação
  suficiente para os receipts; a pressão doméstica segue real.
- [x] Diagnóstico read-only do save schema 76/dia 600: estoques públicos locais
  totalizavam 158.613 alimentos para 10.879 moradores, enquanto a falta do mês
  somava 815. Em cinco contratos sem fundos de Escarlia no dia 510, a folha
  agrícola veio antes dos contratos artesãos de Ferroalto; no dia 600 a leitura
  do próprio empregador já expunha payroll comprometido (3.626) acima do saldo
  (2.661), recibos atuais de produção limitada, relatórios datados de falta e
  30 opções válidas de revisão de folha (10 suspensões/20 reduções). A projeção
  do Dao também mostra caixa muito concentrado em agricultores e quase zero
  entre artesãos em Pedraclara, Portovelho e Ferroalto. Não foi chamada LLM nem
  executada opção. Isso identifica a camada atual do problema (compromissos de
  folha, renda desigual e acesso apesar do estoque), não prova qual escolha um
  provider faria (E212).
- [x] Contrafactual pareado E213/E214: a partir do mesmo save natural do dia
  600, suspender via decisão explícita de API o contrato agrícola de Brumafria
  reduziu a falta observada no ciclo comparável de 846 para 681; saúde média
  passou de 758,88 para 760,00 e unrest de 123,12 para 122,00. A primeira
  execução revelou que a produção não citava a decisão que liberava o caixa.
  O owner agora liga recibos `permanent_employment_paused` do mesmo caixa e dia
  à produção. Teste focal verificou o caminho decisão → mudança de staffing →
  pausa → produção → salários → compras → subsistência; os dois ramos passaram
  auditoria (`ok=true`, zero causas quebradas, erros de autoria/fonte, Story ou
  interpretação material). Isso é intervenção contrafactual, não seleção
  espontânea de ator nem provider real. Saves: `/tmp/cws-e214-control-day0638.mws`
  e `/tmp/cws-e214-choice-day0638.mws`.
- [ ] Medir no mundo natural se um ator pede crédito quando há folha não paga e
  se algum grupo com caixa realmente escolhe emprestar; registrar também
  `NO_ACTION`, falta de elegibilidade ou ausência de caixa sem forçar resultado.

## Estado comprovado no checkpoint

- O kernel causal e fatias materiais de economia, auxílio, mobilidade,
  diplomacia, pesquisa, forças/campanhas, criaturas, ecologia e observação já
  existem; vários continuam V1/parciais.
- Houve escolhas reais curtas de Luna em um menu econômico natural (alívio, não
  oficina) e para um comandante em contato (`hold`). Isso valida chamadas
  delimitadas, não autonomia contínua nem escolha da melhor política econômica.
- O smoke natural schema 70 da seed 73 chegou ao dia 1440 sem provider: auditoria
  causal e conservação passaram, mas houve 452 mortes por privação, saúde média
  321,62/1000 e unrest 449,75/1000. Não é sucesso econômico nem gate final.
  Schema 71 passou a permitir suspender um vínculo sob pressão atual de folha por
  decisão do empregador. O schema 73 validou os recibos
  factuais de combate. No checkout atual, um smoke de 120 dias e
  sua continuação natural até o dia 480 passaram conservação/save-load/auditoria
  sem provider real. No dia 480: 0 mortes por privação, saúde média 877,62,
  unrest 81,75, falta mensal 173 e 1.226 unidades de falta acumuladas. A causa
  observável inclui incapacidade de compra em assentamentos sem falta física atual.
  Após as correções atuais de folha e autoria, um novo run schema 74 até o dia
  480 passou nos checkpoints de 120 dias, conservação, save/load e auditoria
  final em 17.832 eventos: zero causas quebradas, erros de autoria ou efeitos
  materiais por interpretação. No final: saúde média 870,88, unrest 47,38, falta
  mensal 355, 52 migrações e zero mortes; houve 12 receipts sem provider,
  agora classificados corretamente como determinísticos, com zero interpretação
  LLM e zero chamadas reais. A divergência ante schema 72 reforça que o estado
  econômico ainda está em aberto, não que houve recuperação. Uma continuação
  offline do mesmo save até o dia 510 também passou conservação, save/load e
  auditoria em 18.947 eventos, mas a falta subiu para 378 e a saúde média caiu
  para 861,50. O ledger mostra contratos permanentes consumindo quase todo o
  caixa público antes da produção (`payroll_funds=0` em dez instalações); as
  compras domésticas recompõem parte do caixa depois da produção. O empregador
  já recebe affordances atuais para reduzir/suspender contrato após esse recibo,
  mas o fallback offline deliberadamente não escolhe staffing. Isso deixa a
  recuperação dependente de decisão do ator/provider, ainda não validada no
  schema atual com IA real; não é motivo para criar crédito ou autoajuste.
  O dossiê agora oferece os termos econômicos da oficina já enumerada; nenhum
  run ainda demonstra escolha espontânea dela nem efeito macroeconômico. Um
  recibo atual `unpaid_funds` agora também oferece ao próprio empregador a
  opção de suspender o compromisso; o save natural recomputado tinha 13 dessas
  opções em três organizações. Isso não injeta dinheiro nem prova recuperação.
  Na revisão de staffing sob pressão de produção, os alvos positivos agora são
  estritamente menores que o quadro vigente, não frações do limite original que
  poderiam oferecer aumento depois de um corte anterior. Os helpers de comando
  direto também exigem `decision_source`; a fixture de emprego voltou a passar
  audit causal. Isso corrige elegibilidade/autoria, mas ainda não prova escolha
  espontânea nem resiliência econômica.
- A interferência campanha–criatura–comércio foi provada em fixture pressionada;
  e agora uma fixture única segue titular político → QG → mobilização → rota
  fechada por criatura → boletins físicos ao QG → reencaminhamento da coluna →
  frete civil atrasado → diferença de subsistência → contato armado → comandante
  nomeado decide postura. Sem os boletins próprios do QG, o desvio não existe,
  ainda que a instituição conheça as rotas. O boletim local agora também pode
  levar ao QG, por publicação e alcance físico, um resumo tipado de combates
  resolvidos nos últimos 30 dias; o receipt de observação aponta ao fato
  material, e o inspetor do Observatório exibe a leitura com navegação ao
  evento-fonte. No dia seguinte à entrega, o QG pode decidir manter ou iniciar
  a retirada da própria coluna sobrevivente após vitória ou empate por um
  caminho que ele próprio conhece; o owner
  revalida materiais e rota, a transição física carrega autoria `ACTOR_DECISION`,
  e, se houver plano estratégico ativo vinculado à coluna, o owner só o passa a
  `withdrawn` quando a marcha começa. A fixture cobre provider simulado, rota
  obsoleta, plano defensivo mobilizado ligado à mesma coluna, lifecycle
  `withdrawn` e save/load. O titular de policy agora também recebe um turno
  próprio após boletim válido de vitória, derrota ou empate e pode manter ou
  suspender o mandato;
  suspensão bloqueia o plano, mas não move a coluna, e uma decisão posterior
  do QG continua sendo necessária para retirar a força. Isso fecha esses elos
  de decisão em fixture, mas não a cadeia de comando inteira. Essa composição usa escolhas
  simuladas e premissas de fixture para rival/comandante; não demonstra
  formação natural nem provider real.
  A seed 14 também agora atravessa overflow natural → frete de campanha atrasado
  → chegada física → revisão independente do QG para uma coluna levantada sem
  `StrategicPlan`; o provider simulado escolhe retirada e o owner lapa o aviso
  aberto, sem alterar carga física. O evento ambiental é natural, mas mobilização
  e frete concorrente são condições da fixture; isso não prova formação
  espontânea nem provider real.
  A resposta de aftermath que já existia é uma decisão da instituição
  vencedora, não substitui o novo turno separado do QG. Uma segunda fixture
  prova que o comandante nomeado pode observar
  o bloqueio na junção física, escolher pessoalmente a retirada e fazer o owner
  recolher a mesma coluna pelo trecho já percorrido. O limite de staffing já
  mostra custos/saldo do empregador à IA, mas sua escolha espontânea ainda não foi
  medida. Após combate, os sobreviventes de ambos os lados agora permanecem
  materialmente presentes e recebem turnos privados por instituição; o derrotado
  pode retirar/dissolver suas próprias colunas, e reforços participantes também
  têm affordances próprias. Rótulos nomeiam coluna, destino e rota para não
  obrigar o provider a distinguir escolhas materiais pelo ID opaco. Os contatos
  da batalha são encerrados sem dispersar tropas; a ocupação rival segue
  bloqueada até a presença inimiga sair. Isso tem
  prova focal com provider simulado e causal links, mas não fecha campanha
  prolongada, surgimento natural ou resposta de campanha de horizonte longo.
- Os gates de três seeds por dez anos, provider real em horizonte representativo,
  integração ampla e escala/save/load no checkout final continuam abertos.
- O gate natural offline do checkout anterior não concluiu: seu último checkpoint
  observado foi o dia 3.240/3.600 (população 8.500, 2.440 mortes por privação,
  falta mensal 41, saúde 177,38, unrest 266,75) e sua última linha viva chegou
  ao dia 3.270. O handle e os artefatos em `/tmp` desapareceram sem relatório
  final ou auditoria causal. Reexecutar o gate completo somente após estabilizar
  as correções, com diretório de saída persistente.
  A leitura local do checkpoint anterior (dia 2.520)
  mostra causas distintas: Campomanso tinha 9.040
  alimentos públicos com falta 73/saúde 247; Pontenegro, 289 públicos com falta
  111/preço 6; Ferroalto, 11.959 públicos sem falta corrente mas saúde 44. Isso
  diferencia escassez, acesso e dano acumulado; não autoriza uma transferência
  automática nem caracteriza o comportamento de provider real. O recibo causal
  do dia 2.520 atribui 64/73 rações não compradas de Campomanso ao grupo de
  artesãos orcs; em Pontenegro, 91/111 pertencem a agricultores (48 humanos,
  43 orcs); em Ferroalto, 22/46 pertencem a artesãos orcs. A causa por coorte
  está evidenciada, mas ainda falta ligar isso às affordances que o ator
  conhecia e à sua decisão/omissão. A consulta ao save encontrou opções válidas
  de oficina, auxílio local e transferência para a polity Auren, mas
  `ai_enabled=False`; o alívio observado veio de `review_relief_fallback`, que
  ordena falta/cobertura em modo offline, não de escolha por provider. Não usar
  esse run para afirmar que a IA conheceu e rejeitou a oficina.

## Trabalho restante, em ordem

1. **Diagnóstico econômico e prova material — concluído sem balancear.** A evidência
   localiza falta física e incapacidade de compra em assentamentos distintos;
   em Pedra Clara, report atual do dia 120 tinha 1.847 unidades não compradas
   apesar de `missing_food=0`, e o censo datado mostrava artesãos sem folha
   própria paga. A oficina já era affordance válida, e agora seu contexto mostra
   termos de investimento e limite do que a obra faz; a decisão de construção
   cita os receipts de materiais, caixa, relatório/acessibilidade e censo/folha
   que fundamentam a leitura. Contratos cujo empregador não conseguiu pagar
   sequer um salário agora podem ser suspensos por escolha
   após recibo atual; isso reduz o compromisso de folha, mas não cria recursos.
   Uma comparação pareada offline de 120 dias, com uma suspensão explicitamente
   escolhida em Auren, mostrou cinco eventos extras de produção, +4.500 comida
   total rastreada (estoques, cargas e provisões) e melhora pequena nas leituras
   de falta, saúde e unrest;
   população/mortes não mudaram. Isso mede um efeito contrafactual num estado,
   não uma escolha espontânea nem uma solução geral. Uma comparação same-seed
   schema 72 (120 dias) deu mais resolução: `desatento` terminou com 6.266
   rações faltantes; `mercado`, após quatro compras, 6.259; `mobilidade`, após
   24 vínculos e 47 transições, 4.694; `alivio`, após nove distribuições, 68.
   Todos tiveram zero mortes nesse horizonte e auditoria causal limpa. Isso
   indica que emprego/mobilidade sozinhos não resolvem acesso alimentar
   imediato; os perfis são políticas determinísticas de teste, não IA real. O
   contexto de emprego agora mostra incapacidade de compra, censo local e folha
   própria paga com fontes datadas e causalmente ligadas à decisão, sem saldos
   privados. Uma inspeção do save também identificou que Pedra Clara e
   Portovelho tinham populações artesãs sem instalação artesanal local e baixa
   renda doméstica, enquanto Ferroalto tinha mina limitada por integridade e
   linha de ferramenta sem caixa de folha. Auren e Valedouro tinham uma
   affordance de oficina local válida, ainda não escolhida. Isso explica a
   falta de renda acessível sem atribuí-la a falta física de comida, mas não
   torna uma obra automaticamente correta. Dois testes focados da seed intacta
   também provaram a cadeia
   controlada oficina → linha de ferramenta → salário de artesãos → mais compra
   e melhor saúde contra `NO_ACTION`, sem estoque/tesouro/população adicionados;
   aos 390 dias ainda havia falta. Isso fecha a demonstração de viabilidade
   material, mas não escolha espontânea nem resiliência. Nenhum balanceamento
   ou subsídio foi introduzido. Não criar dinheiro, comida, emprego ou resgate
   automático. Uma auditoria adicional removeu opções de emprego em sites sem
   instalação: em Auren, 8 de 16 opções iniciais pagavam/reservavam pessoas
   para locais sem tarefa produtiva representada; agora cada vínculo exige uma
   instalação cuja receita usa aquela ocupação. Os 40 testes focados de emprego
   e construção passaram. O smoke natural schema 74 por 120 dias foi repetido
   após a correção: conservação, save/load e auditoria causal passaram; 4
   contratos de emprego, zero mortes, saúde média 951,25 e falta mensal 16.
   Essa seed curta não fecha resiliência econômica; a queda de saúde em relação
   ao run anterior fica registrada, sem compensá-la com renda roteirizada.
   **Aceite:** contrafactual controlado muda a causa e, por ela, a consequência;
   custo, trabalho, estoque, saúde e população continuam conservados e navegáveis.

2. **Validar decisões reais nos menus atuais.** Há escolhas reais históricas
  curtas de Luna (alívio entre opções econômicas) e de comandante (`hold`).
  Testes locais agora verificam `NO_ACTION`, erro/timeout, orçamento esgotado,
  ID stale/inventado, zero efeito da interpretação e rollback integral em
  timeout. Eles usam provider simulado. O opt-in de IA agora está disponível
  no observatório/API, aplica a configuração completa à criação/carregamento e
  valida provider ao habilitar e retomar; os testes mockam disponibilidade. Ainda falta uma sondagem real no schema
  atual para observar escolha entre affordances concorrentes; owner sempre
   recompõe opções. Um smoke schema 74 de 480 dias não tem chamada real e agora
   audita 12 falhas de consulta como determinísticas, não como interpretação
   LLM. Falhas técnicas no intérprete coletivo agora propagam
   `DomainDecisionFailed`, sem gerar `maintain`/recusa fictícia, restauram o
   checkpoint mensal e pausam o loop. `single_choice` também não converte mais
   provider indisponível nem opção inválida em escolha material; seu fallback
   configurado fica marcado e restrito a test mode. 53 testes focados cobrem
   intérprete, negociação, seita, rollback, bounded choice e runner. Isso fecha
   a classificação local de falha, não
   prova disponibilidade nem escolha de provider real. Não equiparar provider e
   fallback.
   **Aceite:** receipts/auditoria provam cada caminho e uma execução curta no
   schema atual mede escolhas com affordances concorrentes. Consulta externa só
   com autorização vigente e payload sintético/minimizado.

3. **Fechar uma economia natural utilizável.** Depois da correção causal escolhida
   no item 1, fazer preflight reproduzível no schema atual e acompanhar renda,
   produção, compras, estoques, saúde, falta, migração e mortalidade; usar o
   provider separadamente quando habilitado. O preflight schema 72 antigo da
   seed 73 por 480 dias passou conservação, save/load/continuação e auditorias,
   mas terminou com falta mensal 173 e saúde média 877,62. O novo schema 74,
   após remover empregos sem tarefa produtiva, também passou conservação,
   save/load/continuação e auditoria causal, mas terminou com falta mensal 355,
   saúde média 870,88 e unrest 47,38. São trajetórias materialmente íntegras,
   mas não economia resiliente; a continuação até o dia 510 agravou a falta
   mensal para 378 e baixou a saúde média para 861,50. Zero mortes nesse
   horizonte curto não fecha o gate de longo prazo. Após a etapa de aftermath,
   o gate natural seed 73/dia 120 também foi repetido no checkout atual:
   conservação, save/load e auditoria passaram em 3.858 eventos, com zero
   chamadas reais, falta mensal 16, saúde 951,25 e zero mortes. Na revalidação
   de 24/09 após a auditoria de autoria, `decision_origin_without_source` e
   `decision_authorship_errors` também ficaram vazios. O auditor agora também
   valida fonte em fatos `DECISION` de ator e receipt causal para fonte provider;
   no save, `decision_source_errors` ficou vazio. É somente
   revalidação curta, não substitui 480/3.600 dias nem autonomia real. O run atual ainda usa
   fallback sem provider real. O gate natural pós-correções foi interrompido
   sem relatório: último checkpoint dia 3.240 e última linha viva dia 3.270 da
   seed 73. Falta executar o gate completo após estabilizar o checkout e gerar
   as auditorias de checkpoints antes de julgar a integridade do horizonte.
   Nenhuma política recebe prioridade porque o teste exige recuperação.
   **Aceite:** recuperação é possível por decisões e owners materiais, sem
   apagar crises legítimas; toda deterioração continua explicável. Se não houver
   estabilidade em toda seed, registrar diferenças e causas — não mascarar.

4. **Completar a cadeia de comando institucional.** Compor líder político,
   titular de policy, QG/operations e comandante como atores/autoridades
   distintos: objetivo, plano/ordem válida, transmissão ou relatório datado,
   decisão tática e resposta ao resultado. Implementar apenas os elos ausentes;
   não simular mensagens instantâneas, obediência, discordância ou sucesso por
   prosa. A fixture integrada já compõe titular político → QG → mobilização →
   interferência de rota → reencaminhamento → chegada → contato → nomeação de
   comandante → decisão tática em turnos separados. O comandante agora também
   pode observar e reagir a um bloqueio enquanto marcha, usando relatórios
  pessoais locais e escolhendo desvio ou retirada; essa reação está provada em
  fixture, não em formação natural. O QG agora recebe leitura própria e pode
  responder ao resultado com retirada material da coluna por rota conhecida.
  O titular de policy também recebe seu próprio boletim e decide manter ou
  suspender o mandato de um plano ativo ligado à coluna; a suspensão não move a
  força, e o QG ainda precisa agir. Esses turnos já têm prova focal, mas a
  formação natural da cadeia, provider real e resposta política a campanhas em
  horizonte mais amplo continuam abertos. A resposta institucional de aftermath
  existente não equivale à leitura pessoal do QG.
   A base física
   de presença foi acrescentada: o QG pode nomear um comandante no dia de
   saída, antes do primeiro trecho; a ligação acompanha a coluna, impede ações
   locais/viagem individual e a chegada atualiza a localização do personagem.
   A nomeação não concede ação irrestrita durante o percurso: a affordance vem
   de bloqueio observado pelo próprio comandante, e a execução revalida comando,
   ordem política, relatórios pessoais, rota e estado da coluna.
   **Aceite:** cada decisão tem ator, conhecimento, autoridade e receipt
   próprios; atraso/relatório velho e `NO_ACTION` podem alterar o curso por owners
   reais; save/load preserva ordens e pendências.

5. **Provar composição de campanha sem roteiro.** Integrar uma campanha já ativa
   com ao menos uma interferência material existente (rota/clima/criatura),
   abastecimento, resposta do comandante/QG e consequência econômica ou social.
   Uma fixture prova no mesmo curso rota fechada → coluna parada → boletins
   próprios para o QG → decisão de reencaminhar a mesma coluna → carga na rota
   original atrasada → diferença de subsistência → contato → nomeação do
   comandante → decisão tática. A reação do comandante ao bloqueio em marcha
   agora está implementada e provada em fixture; falta a reação posterior dos
   outros atores ao resultado. Também é preciso observar runs naturais sem
   exigir que o evento ocorra. O comandante pode estar fisicamente associado à
   mesma coluna e receber uma decisão de campo baseada em seus próprios
   relatórios.
   **Aceite:** mudar rota, carga, relatório ou decisão muda o resultado material;
   nenhuma fixture injeta o resultado, e uma seed tranquila continua válida.

6. **Fechar campanha e saída política.** A auditoria confirmou que rotação e
   folha de guarnição já têm owners e que controle territorial é revogável
   tanto por decisão quanto quando sua base material some. Um teste focal novo
   compõe controle ativo do defensor → brecha → colapso de guarnição → controle
   `lapsed`, sem transferir ocupação/administração e com causal link ao colapso.
   Outro gap foi fechado na negociação: não se pode propor novo acordo para a
   mesma campanha enquanto houver cessar-fogo oferecido ou termo aceito ainda
   ativo, evitando obrigações concorrentes sobre a mesma coluna. Agora uma
   obrigação de retirada vencida pode ser reparada quando o próprio devedor,
   após receber aviso do breach, ainda controla uma coluna presente e tem rota
   válida: a decisão executa a retirada no owner militar, muda somente o estado
   atual para `remediated` e mantém o evento/ID histórico de breach. Validação,
   memória institucional, adapter mensal, menu civil e save/load cobrem esse
   caminho. Uma regressão com duas colunas reais confirma a consulta composta
   por proprietário com affordances executáveis para duas colunas reais,
   despachos materiais em turnos consecutivos e save/load da revisão adiada.
   Em concessões pós-ocupação, oferta/resposta agora ficam vinculadas à
   contraparte administrativa atual; mudança de administrador entre a proposta
   e a resposta invalida a affordance antiga. Ainda não prova campanha
   prolongada com várias colunas abastecidas. Continuam a auditar esses casos e
   situações restantes de cessar-fogo/retirada/concessão;
   reparação não é possível se o ativo já não estiver materialmente disponível. Implementar só
   gaps demonstrados na auditoria; propostas e compromissos nunca executam
   sozinhos.
   Uma lacuna concreta foi fechada: quando uma coluna `marching` fica parada
   por rota fechada, o QG agora recebe affordances independentes para seguir por
   caminho alternativo conhecido ou encerrar o plano e retornar a território
   próprio por relatórios atuais. A posição no mapa é derivada do prefixo de
   rota já percorrido; o owner substitui apenas o trecho futuro, revalida a
   rota física e não move a carga. O plano registra `withdrawn`, sem reabrir-se
   automaticamente. Uma fixture cobre escolha, execução, causalidade e
   save/load. O restante da auditoria de rotação/manutenção, campanha
   prolongada, controle revogável, cessar-fogo, concessão e remediação continua
   aberto.
   **Aceite:** força sem suprimento/guarnição perde capacidade material;
   aceite político só altera realidade após cumprimento independente e válido.

7. **Concluir verticais restantes do roadmap, sem novos minigames.** Completar a
   cadeia tecnologia → conhecimento → instalação/operação/manutenção; generalizar
   leis engine-owned de magia/ecologia/criaturas; finalizar intriga, religião e
   investigação com evidência/conhecimento/ação material. Reusar affordances,
   autoridade, commitments, memória e owners atuais.
   **Aceite:** cada vertical tem uma cadeia ponta a ponta causal, save/load e
   regressão focada; efeitos especiais não são inventados por LLM nem disparados
   por quota narrativa.

8. **Tornar a causalidade legível e passar os gates finais.** Completar os
   dossiers PT-BR para navegar decisão → evento → owner → evidência em economia,
   campanha, comando, relações e ameaças; medir custo de simulação, RSS e saves.
   Ao estabilizar o schema/regras, rodar três seeds naturais por 3.600 dias com
   checkpoints, conservação, save/load/continuação e auditoria causal; registrar
   progresso mensal e checkpoints em JSONL durável para que interrupções não
   apaguem a evidência já observada; rodar
   fixtures pressionadas separadas para exigir cadeias multietapas. Executar por
   fim regressões focadas, type-check/build e gates de API/frontend.
   **Aceite:** zero causa quebrada, delta originado em Story/interpretação ou
   mutação parcial; runs tranquilos são válidos; custo/memória/saves ficam
   reportados e dentro do limite operacional acordado.

## Dependências e controle de escopo

```text
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
```

Uma etapa só fecha com evidência do owner e estado atuais. Teste focal prova
contrato local; fixture prova mecanismo sob pressão; smoke natural mede a
trajetória daquela política/seed; provider stub ou fallback não prova IA real.
Não começar Industrial Warfare, nem abrir torneios ou novas features laterais
antes do item 8.
