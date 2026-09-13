# Estado atual — Medieval World Simulator

Atualizado em 13/09/2026. Este documento descreve o WIP local que será publicado
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

- Runtime medieval separado, configuração persistente e save schema 16 (Society2,
  Economy8); dados de execução usam namespace próprio e saves schema 15 e anteriores são rejeitados,
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
- Conhecimento datado de rotas (schema16, `route_reports`): observação
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
- Tarifas de exportação são cotação pública e histórica da jurisdição que administra
  o estoque de origem. `TaxPolicy.export_rate_permille` usa
  `export_policy_event_id` próprio, separado de renda e de `last_event_id`.
  O comprador vê taxa/fato/coletor, nunca saldo estrangeiro; na abertura bilateral
  paga base mais tarifa uma vez, com base ao vendedor e tarifa ao tesouro da origem.
  Não há tarifa doméstica/frete próprio, pedágio, trânsito ou bloqueio.

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

**Etapa1 do roadmap está PARCIAL.** O que já existe (fundação, informação
datada, abastecimento/logística/mercados, diplomacia determinística, conhecimento
de rotas, migração temporal/provisão e obrigação material de reparo) está coberto pelos recortes de teste
acima. Ainda faltam, explicitamente: hazards naturais, clima e desgaste,
mobilidade/treinamento de força de trabalho (as vilas são todas farmer, então
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
- Criaturas autônomas, ameaças dinâmicas e o dragão não existem no runtime atual.
- Demografia profunda, herança, famílias individualizadas e patrimônio além de
  dinheiro/provisões, pedágios, trânsito, bloqueios, contrabando e
  calibração econômica de longo prazo continuam abertos. Preços locais já existem
  no fluxo mensal limitado de `markets.py`; isso não equivale a um
  mercado local completo.
- O executor de reparo material existe apenas para os kinds catalogados; não há
  dano natural, clima ou desgaste que o acione, nem reativação automática de
  instalações interditadas.
- O observatório ainda não mostra campanha, criatura, estratégia geral ou todas as
  cadeias de informação. Testes de backend não substituem inspeção visual e mundos
  naturais de longa duração.

## Handoff Git

A branch real desta execução é `codex/medieval-remote`, HEAD `85fe9717`, com WIP
local não commitado além desse ponto. Não há autorização de commit, push ou
deploy nesta preparação. O remote `github-personal` é o GitHub pessoal do
usuário; `origin` aponta para a VPS e não deve ser confundido com o destino de
publicação. Nenhuma alteração deve ser enviada à `main`, mesclada ou publicada
como release por este handoff. Arquivos de cache, `web/dist-medieval` e
`.test-data` não pertencem ao commit.
