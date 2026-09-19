# Estado atual — Medieval World Simulator

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
