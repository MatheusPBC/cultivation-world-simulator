# Estado atual — Medieval World Simulator

## Nova série natural com o fallback corrigido — 23/09/2026

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
foi feita durante a série. O gate natural está fechado, mas os gates de
provider real, produto e funcionalidades amplas do roadmap continuam abertos.

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

- Ainda não há provedor de IA real integrado às decisões do mundo. A política atual
  de abastecimento/barganha usa regras determinísticas; isso é deliberado para
  testes, não equivale a autonomia inteligente.
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

### Medição natural de um ano no schema 67

A seed 73, sem provider real e sem reforço artificial, completou 360 dias no
checkout atual. Os checkpoints de 90/180/270/360 dias e o save final passaram
round-trip; o final tem 13.024 eventos e 4.448.256 bytes. A auditoria causal
do save final retornou `ok=true`, sem causas quebradas, autoria de decisão
inválida, interpretação material ou Story material. No dia 360 havia 10.949
habitantes, falta de 37 unidades de alimento, saúde média 934 e zero mortes por
privação nessa seed. Isso é uma medição de um ano, não o gate natural de três
seeds por dez anos e não mede escolhas de um provider real.
