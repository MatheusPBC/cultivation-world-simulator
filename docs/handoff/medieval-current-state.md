# Estado atual — Medieval World Simulator

Atualizado em 14/09/2026. Este documento descreve o WIP local que será publicado
na branch de trabalho; não é uma declaração de produto concluído.

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

- Runtime medieval separado, configuração persistente e save schema 32 (Society4,
  Economy11); dados de execução usam namespace próprio e saves antigos são rejeitados,
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
- Núcleo de diplomacia: propostas, contrapropostas, aceitação sem transferência,
  obrigações de pagamento/ensino, prazos, expiração, quebra, dispensa e avisos
  privados. Cumprimento material ainda exige uma decisão nova e autorização atual.
  Barganha determinística por contexto de ator, `GET /api/v2/query/diplomacy` e o
  DiplomacyPanel do observatório já estão integrados; IA real de negociação não.
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
  8 possui `repair_blueprints` e `repairs`: uma obrigação de projeto, não um
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
  Campanha, batalha, cerco, comando e solução política continuam fora deste slice.
- Ritos restaurativos V1 são trabalho material delimitado: oficiante residente,
  site capaz, reagentes próprios, assistentes pagos e testemunhas. A conclusão
  reduz saúde registrada dentro do limite do blueprint; interrupção/cancelamento
  perde os reagentes e não cria recursos, pessoas, capacidade ou controle.
- Criaturas agora existem no runtime em uma vertical estreita: o drake do Rio Lume
  percebe somente cargas que cruzam sua rota, pode pedir tributo, restringir sua
  própria passagem e recuar; instituições recebem aviso e respondem com alimento
  próprio. A decisão por provider V1 escolhe apenas IDs enumerados e registra
  interpretação sem delta; fallback/indisponibilidade não fecha a rota. Não há
  ainda um sistema geral de monstros, ameaças, magia ou dragões múltiplos.

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

- Ainda não há provedor de IA real integrado às decisões do mundo. A política atual
  de abastecimento/barganha usa regras determinísticas; isso é deliberado para
  testes, não equivale a autonomia inteligente.
- Objetivos e planos estratégicos gerais, informação secreta, espionagem, suborno,
  sabotagem, persuasão e traição descobrível ainda não compõem uma vertical completa.
- Não há campanha territorial completa: contingentes, reconhecimento, comando,
  suprimento militar, posições, táticas, cerco, ocupação e acordo político posterior
  continuam pendentes.
- Magia é apenas uma direção arquitetural do produto; rituais, custos, detecção,
  proteção e contramedidas ainda não foram implementados como sistemas completos.
- O drake autônomo do Rio Lume e sua decisão por provider já existem nesta vertical
  estreita; ainda faltam criaturas múltiplas, ameaças dinâmicas, dragões adicionais,
  ecologia geral e o sistema amplo de magia/criaturas.
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

## Handoff Git

A branch real desta execução é `codex/medieval-remote`, com WIP
local não commitado além desse ponto. Não há autorização de commit, push ou
deploy nesta preparação. O remote `github-personal` é o GitHub pessoal do
usuário; `origin` aponta para a VPS e não deve ser confundido com o destino de
publicação. Nenhuma alteração deve ser enviada à `main`, mesclada ou publicada
como release por este handoff. Arquivos de cache, `web/dist-medieval` e
`.test-data` não pertencem ao commit.
