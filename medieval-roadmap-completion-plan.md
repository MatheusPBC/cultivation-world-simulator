# Plano de conclusão do roadmap medieval

### Matriz natural de três seeds — 19/09/2026

O gate natural de 360 dias foi repetido para `73`, `101` e `137`. Os três
artefatos passaram conservação de dinheiro/recursos, save/load/continuação e
auditoria causal (`ok=true`, sem causas quebradas e sem Story material). O
horizonte terminou pressionado em todos os casos e chegou a aproximadamente
235 segundos por seed. O resultado não fecha o gate de dez anos nem a
resiliência econômica.

O modo comparativo econômico foi interrompido depois de iniciar a fixture de
socorro, porque repetiria quatro horizontes longos; essa limitação é
operacional, não um resultado verde ou vermelho da economia.

### Checkpoint do harness e da folha fiscal — 19/09/2026

O smoke de autonomia normaliza `str` e `Path` na entrada, evitando que uma
sondagem válida que chega ao save/load falhe apenas ao chamar `.resolve()` no
retorno. Uma regressão focada cobre o contrato de caminho.

O fixture fiscal agora verifica a causalidade correta: o evento `wages_paid`
deve debitar do tesouro exatamente `Payroll.gross`, e o boletim de exportação
deve republicar a taxa/policy event realmente vigente após o boundary. A
regressão combinada de tarifas, smoke, ajuda, concessão e cerco passou em 52
testes. Esse checkpoint remove uma expectativa de saldo final incompatível com
outros owners mensais; não é aceite de resiliência econômica nem do gate de
dez anos.

### Regressão material das ondas 3–5 — 19/09/2026

Depois do checkpoint anterior, a regressão focalizada que cobre produção e
pesquisa, apprenticeship por migração, venda/roubo de tecnologia, cerco,
força/guarnição, cessar-fogo, escassez de rota, recuperação de frete e
alfândega passou em **93 testes** (`35,77s`). Isso confirma que as fatias locais
continuam coerentes; não fecha a resiliência econômica de longo prazo, a
campanha geral, o provider remoto ou o gate de dez anos.

O probe operacional do provider real foi executado separadamente e terminou
com `RuntimeError: real provider is not configured or is disabled in this
runtime`, antes de iniciar uma decisão. Esse é o comportamento fail-closed do
harness, não evidência de autonomia real.

Foram adicionadas duas regressões ao próprio probe: provider ausente falha
antes de criar o mundo e orçamento não positivo é rejeitado antes de qualquer
consulta. O recorte de provider/turno institucional passou em **31 testes**;
`compileall` e `git diff --check` também passaram.

### Alternativas de socorro por rota — 19/09/2026

Transferências alimentares interurbanas agora enumeram duas coberturas
engine-owned do shortfall atual (integral e metade), assim como o socorro local,
em vez de forçar a transferência remota a cobrir somente metade. O ator ainda
seleciona um ID opaco; rota, estoque, tarifa e quantidade são recompostos e
revalidados pelo owner. A regressão de relief/turno/provider passou em 30
testes. Isso amplia as opções de recuperação sem distribuir comida ou resolver
escassez automaticamente.

O fallback determinístico também ordena essas affordances pela maior cobertura
atual e depois por destino/ID estável; não interpreta o ID opaco nem cria uma
prioridade narrativa. O recorte ampliado de relief, turno e smoke passou em 36
testes.

### Checkpoint de fallbacks após o turno composto — 19/09/2026

Tarifas, manutenção, abastecimento, provisões, migração e serviços agora
executam depois da consulta institucional quando o provider está habilitado e
ignoram somente atores presentes em `covered`. Isso evita mutação automática
depois de `NO_ACTION` e mantém uma saída determinística para atores sem slot de
orçamento. Transferências de relief usam IDs opacos no prompt, sem expor
estoques ou rotas privadas; o owner recompõe os termos.

As regressões focadas passaram em 50 testes, com `compileall` e `git diff --check`
limpos. A expectativa histórica do fixture fiscal que compara saldo e folha
continua falhando (`283` contra `120`) e precisa ser resolvida antes do gate
financeiro; não foi mascarada.

### Checkpoint de fallback sob orçamento de provider — 19/09/2026

Os fallbacks de workforce e emprego permanente agora distinguem provider
disponível de ator efetivamente consultado. Atores cobertos pela consulta ficam
fora da política determinística; atores que perderam o slot do orçamento ainda
podem selecionar uma affordance atual e o owner revalida os termos. A regressão
conjunta passou em 50 testes. O smoke de 120 dias com `mobilidade` reduziu a
falta alimentar final de 6.273 para 4.276, mas a onda de resiliência econômica
continua aberta.

### Checkpoint de mobilidade local sob escassez — 19/09/2026

Quando uma coorte pode aceitar várias ofertas agrícolas válidas, o fallback
determinístico agora prioriza a instalação do próprio assentamento pressionado
antes de comparar o tamanho das ofertas remotas. Nenhum destino é inventado:
o relatório de demanda já publicado fornece a localização e o owner continua
revalidando rota, conta, coorte e termos. A regressão focada passou em 37
testes; o smoke curto ainda demonstra pressão alimentar e a onda econômica
continua aberta.

### Checkpoint de escolha de mobilidade sob shortfall — 19/09/2026

O fallback determinístico de workforce agora ordena ofertas de farmer pela
maior quantidade engine-owned quando uma coorte possui múltiplas demandas
concorrentes. A decisão continua aceitando somente um ID enumerado por grupo,
com pagamento, reserva e conclusão física no owner existente. Workforce e
harness passaram em 36 testes; o smoke curto ainda termina com escassez, então
isso é uma correção de priorização, não o fechamento da economia resiliente.

### Checkpoint de descoberta de atores militares institucionais — 19/09/2026

`garrison_actors` agora considera também organizações com office militar
vigente, em vez de consultar somente polities. A opção segue sendo enumerada
por `force.garrison_options` e executada pelo mesmo owner, portanto a mudança
apenas fecha uma lacuna de descoberta no boundary institucional. Regressão
focada: 7 testes. Isso não fecha campanha persistente nem solução política
ampla.

### Checkpoint de pressão material do cerco — 19/09/2026

Cada avanço datado de uma `SiegeCampaign` agora consome uma ração adicional
por soldado da guarnição cercada, depois do consumo diário normal do owner de
força. A quantidade é limitada pelo estoque real da coluna; nenhuma baixa,
ocupação ou vitória é inferida dessa pressão. O receipt de progresso/brecha
contém o `StateDelta` de provisões e mantém as causas da campanha, guarnição,
coluna e investimento. A regressão focada de cerco, suprimento e força passou
em 23 testes. Ainda faltam guerra prolongada, manutenção/controle fora do
recorte e solução política ampla.

### Evidência do smoke de resiliência — 19/09/2026

O smoke natural com `seed=73` e perfil `desatento` não permanece estável: a
falta de comida surge no mês 2 e as primeiras mortes por privação aparecem no
mês 11. Isso é o comportamento esperado de uma política que escolhe
`NO_ACTION`, mas prova que a resiliência econômica ainda não está fechada. O
perfil `socorro` agora também reconhece IDs `relief-transfer` enumerados; a
execução de 120 meses foi interrompida depois de capturar essa falha, sem ser
reportada como smoke verde.

A regressão do helper de smoke/relief/agenda passou em 17 testes. Uma execução
provider-free de 120 dias com `socorro` passou com conservação de recursos e
dinheiro, zero mortes, save/load equivalente e nenhum call real de IA; ela não
substitui o gate natural de 120 meses. Distribuição ampla, recuperação social e
o gate final continuam pendentes.

O perfil `mobilidade` também atravessou 120 dias sem mortes e abriu vínculos de
emprego/transições materiais, mas a falta acumulada persistiu. Isso confirma
que renda e workforce são causas reais da cadeia, porém ainda não constituem
resiliência econômica suficiente sozinhas.

### Checkpoint de transferência alimentar interurbana — 19/09/2026

Relief agora enumera transferência de excedente entre estoques próprios quando
há reserva local preservada, falta alimentar observada no destino e rota fiscal
conhecida. O ator escolhe o ID; o owner abre um `FreightOrder` real, consome o
estoque de origem e só a descarga futura altera o estoque de destino. A decisão
não cria comida nem resolve o déficit por prosa, e todas as leituras/rotas são
revalidadas.

A mesma affordance também aparece no catálogo civil determinístico, usando o
mesmo owner de frete e a mesma revalidação. A regressão focada de
relief/logística/ajuda/catálogo/agenda passou em 30 testes, com `compileall` e
`git diff --check` limpos. A resiliência econômica ampla e o smoke de longo
prazo continuam pendentes.

### Checkpoint de contexto dos planos próprios — 19/09/2026

O dossier do ator agora informa o ciclo de vida dos objetivos/planos que ele
próprio possui (`stage`, `blocker`, alvo e última revisão). Handles de estoque,
frete e planos estrangeiros continuam ocultos; a projeção é derivada dos
registros persistidos e não cria planner ou reserva material.

A regressão focada de dossier/capacidade/turno institucional passou em 26 testes,
com `compileall` e `git diff --check` limpos. Provider remoto, capacidade
estratégica mais ampla e as demais ondas continuam pendentes.

### Checkpoint de resposta a acusação — 19/09/2026

O sujeito de uma acusação privada agora recebe duas affordances transitórias:
`deny` ou `request_review`. A escolha produz uma ocorrência causal com decisão
real e referência ao aviso; não decide culpa, não limpa o finding e não aplica
retaliação. O mesmo aviso/resposta não pode ser repetido. A família usa os
adapters existentes e o boundary mensal compartilhado, inclusive para
organizações.

A ocorrência da resposta é incluída no contexto estratégico somente para o
acusado e o acusador, sem duplicar o owner de Knowledge. A regressão focada de
sabotagem/investigação/agenda/suborno/dossier passou em 21 testes, com
`compileall` e `git diff --check` limpos. A intriga operacional ampla,
perseguição e consequências materiais continuam pendentes.

### Checkpoint de descoberta de conflito organizacional — 19/09/2026

O boundary mensal agora inclui organizações não-polity quando elas possuem
uma affordance material corrente de sabotagem, investigação ou acusação. Os
adapters já existentes continuam sendo a única superfície de execução; a
alteração apenas evita que uma opção canônica fique sem consulta por não estar
no conjunto base de atores.

A regressão focada de sabotagem, agenda institucional e suborno passou em 16
testes. Intriga geral, provider remoto e as ondas amplas posteriores seguem
pendentes.

### Checkpoint de evidência estratégica no dossier — 19/09/2026

O dossier que compõe a consulta institucional agora carrega findings
estratégicos que o ator conhece: espionagem, investigação, roubo tecnológico e
acusações canônicas. A leitura é filtrada por `recipient_ref` no owner de
Knowledge e não inclui causas desconhecidas, inventário ou planos estrangeiros.
Nenhuma decisão é criada por esse campo; ele apenas torna evidência privada
disponível para a interpretação da affordance já enumerada.

A regressão focada de dossier/API/diplomacia passou em 24 testes. Provider
remoto, intriga material e o gate final continuam pendentes.

### Checkpoint de persuasão bilateral — 19/09/2026

A affordance `persuade_proposal` agora é enumerada para o proponente ou para a
contraparte que recebeu a proposta e ainda possui autoridade diplomática. A
execução continua zero-delta: registra a decisão e a tentativa causal, reemite
o aviso canônico e não aceita, altera ou cria obrigação. O limite por ator,
proposta e dia e a revalidação do ID permanecem engine-owned.

A regressão focada de diplomacia, negociação, persistência e turno institucional
passou em 45 testes. Isso fecha a assimetria da affordance, não a intriga
operacional nem a solução política ampla.

### Checkpoint de cache da geometria de rota — 19/09/2026

O centróide `center_loc` das regiões authored agora é calculado uma vez por
instância de `SettlementRegion`. Como `cors` não é runtime mutável no fork
medieval, buscas de rota e viagem deixam de repetir a mesma redução geométrica;
nenhum relatório, rota ou affordance é persistido pelo cache.

Rotas, viagem, engine e suprimento passaram em 31 testes. Isso reduz custo do
gate sem alterar a cadeia causal ou o resultado material.

### Checkpoint de remoção da validação duplicada de Knowledge — 19/09/2026

O simulador não repete a validação histórica completa de `KnowledgeState` no
início do step. Como o mundo publicado foi validado no commit anterior e as
operações pré-step não alteram conhecimento, a mesma validação permanece
obrigatória no candidato final antes de salvar/publicar; rollback e falha
atômica continuam preservados.

Engine/persistência/histórico passaram em 37 testes. O gate natural de 120 dias
caiu de aproximadamente 14 s para 12 s, sem alterar o resultado material. É
uma redução de custo, não o aceite do horizonte final de dez anos.

### Limite de custo revalidado no gate natural — 19/09/2026

O gate natural de `3600` dias da seed `73` alcançou o dia `420` sem crash ou
falha causal/conservação no trecho observado. O custo acumulado ficou em cerca
de cinco minutos por ano simulado e acelerou com o volume de eventos; a
execução foi encerrada antes do horizonte. O resultado é evidência parcial de
estabilidade, não aceite do gate final de três seeds por dez anos.

### Checkpoint de integração do cessar-fogo de campanha — 19/09/2026

As opções engine-owned de oferta, resposta e cumprimento do cessar-fogo agora
participam do turno institucional mensal. A integração não cria uma segunda
engine: cada opção recompõe a campanha, a obrigação e a rota e delega ao owner
existente; somente o cumprimento material inicia a retirada.

A regressão focada de cerco, cessar-fogo e turno institucional passou em 30
testes. A solução política ampla, manutenção prolongada e o gate final ainda
não estão fechados.

### Checkpoint de revalidação da rota fiscal do abastecimento — 19/09/2026

O owner de procurement não troca mais silenciosamente a rota fiscal que havia
publicado uma oferta pela primeira rota recomputada. A execução busca a mesma
sequência de rota entre as opções atuais e bloqueia de forma auditável quando
ela ficou obsoleta; nenhuma quantidade, conta ou estoque é inventada.

A regressão focada de rotas, procurement, ajuda e decisão civil passou em 49
testes. Isso corrige a fidelidade da escolha material, mas não fecha a
resiliência econômica de longo prazo nem o gate final.

### Checkpoint de inclusão de organizações com suborno — 19/09/2026

Organizações que possuem affordance material de oferta, resposta ou pagamento
de suborno agora entram no conjunto de atores do turno institucional mensal.
Isso corrige a integração sem criar opção, planner ou mutação nova: o menu e o
owner de bribery continuam sendo os existentes e a decisão segue selecionando
apenas o ID enumerado.

A regressão focada de bribery/agenda/turno passou em 21 testes. A lacuna de
integração foi fechada; campanhas políticas e persuasão gerais continuam fora
do aceite do roadmap.

### Checkpoint de remediação de ensino após breach — 19/09/2026

Um compromisso de ensino que já recebeu o pagamento, mas venceu sem entrega,
agora pode gerar uma nova affordance de renegociação para o professor. A nova
proposta contém somente o termo de ensino, preserva o breach e não cobra o
pagamento novamente. A contraparte aceita independentemente; professor e
aprendiz ainda precisam registrar consentimento/aceitação atuais, e Knowledge
só é alterado pelo cumprimento material.

A regressão de diplomacia e renegociação passou em 23 testes, incluindo
persistência. Isso é uma remediação específica, não o fechamento de tratados
sociais gerais.

### Checkpoint de remediação de cessão administrativa — 19/09/2026

Uma transferência administrativa pós-ocupação que sofre breach agora pode
abrir uma nova affordance de remediação quando o ocupante ainda mantém
controle, guarnição abastecida e relatório atual. A nova proposta carrega o
evento do breach como causa, exige aceitação e cumprimento independentes e não
altera o estado da obrigação histórica. A administração só muda no owner após
o cumprimento material.

A regressão focada de administração e observabilidade passou em 17 testes.
Isso fecha apenas a remediação da cessão; compromissos sociais gerais,
renegociação e campanhas persistentes permanecem na fila.

### Checkpoint de oferta agrícola escalada por escassez — 19/09/2026

O owner de workforce agora pode publicar uma oferta de retorno a `farmer` de
até metade da coorte quando o relatório de Economy registra falta de comida;
fora desse estado, a política continua em um quinto e não muda outras
ocupações. A decisão permanece somente o ID da affordance, e o executor
revalida stipend, saldo, disponibilidade e conclusão física.

A regressão focada passou em 41 testes. O smoke natural de 120 dias conservou
recursos, preservou save/load e manteve auditoria causal limpa, mas a escassez
final (`missing_food=4.221`) mostra que isso é uma capacidade de recuperação,
não o aceite da resiliência econômica de longo prazo.

### Checkpoint de alvo observável das soluções políticas — 19/09/2026

O read model do atlas passou a expor o assentamento afetado por cada proposta
política ativa. A engine deriva o alvo do `settlement_id` do termo administrativo
ou do `standoff` material da desescalada; a API e a UI exibem essa referência
sem criar estado paralelo. A regressão backend e a suíte medieval da UI passaram.

### Checkpoint de solução política pós-ocupação — 19/09/2026

Um ocupante que mantém controle territorial, guarnição abastecida e relatórios
atuais agora pode selecionar uma affordance de cessão administrativa
pós-guerra. A instituição administradora decide independentemente aceitar ou
recusar; se aceitar, nasce uma obrigação de transferência e o owner só altera a
administração após o cumprimento explícito pelo administrador atual. A nova
opção não presume retirada, paz, controle ou recursos, e não substitui o fluxo
de contato armado já existente, que mantém seus termos de cessão e retirada.

Cinco testes focados passaram. A vertical ainda não equivale à solução política
completa: persuasão, espionagem, suborno, sabotagem e campanhas políticas mais
amplas permanecem abertas.

### Checkpoint de emprego escalado por pressão — 19/09/2026

O owner de emprego permanente agora dimensiona a oferta pela pressão material
do assentamento: um grupo estável continua limitado a um quinto da coorte,
enquanto falta de comida, saúde baixa ou descontentamento permite até metade.
O ID transitório não carrega novos termos; o owner revalida autoridade, site,
coorte, saldo e payroll. A regressão de emprego/workforce passou em 41 testes.
No smoke natural de 120 dias (`seed=73`), `missing_food` caiu de 4.224 para
4.020 e a saúde média subiu de 899,38 para 903,00, sem quebrar conservação,
save/load ou auditoria causal. A resiliência de longo prazo permanece aberta.

### Checkpoint de folha material de guarnição — 19/09/2026

A manutenção diária de uma guarnição passou a pagar a coorte de soldados que
originou o destacamento: o owner debita o tesouro do proprietário e credita a
conta doméstica da coorte no mesmo evento `garrison_maintained`. A operação
continua exigindo presença, autoridade, ração, conta válida e saldo; qualquer
falha lapeia a guarnição em vez de inventar pagamento. A regressão focada de
força, cerco e decisões civis passou em 40 testes. Isso é um avanço da
manutenção militar material, não o aceite da campanha territorial completa.

### Checkpoint de execução — índice transitório de rotas (19/09/2026)

A revisão de migração passou a construir uma leitura transitória dos relatórios
de rota por coorte e reutilizá-la ao avaliar destinos e recuperação no mesmo
turno. Isso remove reconstrução repetida de topologia sem criar cache persistido,
planner ou nova capacidade; as opções e os owners continuam usando os mesmos
relatórios datados e revalidando a marcha. A regressão focada de migração,
conhecimento e menu passou em 41 testes. O smoke de 360 dias com `seed=73`
terminou em 180,74 s, conservou dinheiro/recursos, preservou save/load e passou
na auditoria causal (`broken_cause_ids=[]`, nenhum Story material). O gate de
dez anos e a resiliência econômica permanecem pendentes.

Atualizado em 19/09/2026 (checkpoint de release de 360 dias). Este é um plano de lacunas, não uma declaração de
conclusão. O estado canônico continua em `docs/handoff/medieval-current-state.md`
e a intenção de produto em `docs/handoff/medieval-roadmap.md`.

A aplicação tecnológica de `irrigation-works` agora exige também a capacidade
física authored `water_management` no site. A opção e o owner revalidam essa
capacidade antes de iniciar a obra, e cada progresso bloqueia de forma
auditável se ela deixar de existir; a regressão focada de apprenticeship,
industry e expansion passou em 28 testes.

## Objetivo

Levar as verticais V1 existentes a um mundo observável e persistente em que
comércio, diplomacia, pesquisa, campanhas, magia e criaturas possam produzir
resultados diversos por affordances, decisões e owners reais — sem transformar
LLM ou narrativa em causa material.

O menu econômico composto agora compartilha uma situação pública entre
abastecimento e compra: relatórios próprios, assentamentos, recursos e rotas
conhecidas. Handles privados e termos materiais continuam fora do prompt e
voltam a ser recompostos somente pelo owner. Esta é uma melhoria de agência e
privacidade da onda econômica, não o aceite da economia resiliente completa.
Ofertas concorrentes agora são distinguíveis no contexto por índice, origem
pública, rota e cotação datada, sem revelar quantidade ou saldo; a execução
continua sendo revalidada pelo owner.

As leituras datadas de rota agora também carregam o fluxo agregado de volume
observado naquele dia (`daily_flow_bulk`). Isso expõe trânsito físico público
para a escolha entre rotas sem revelar ordem, estoque, conta ou proprietário;
o fluxo continua sendo derivado de `RouteFlow` e não cria uma segunda capacidade
ou planner. A regressão de rotas/logística/menu passou em 50 testes, além de
`compileall`, `git diff --check`, `vue-tsc` e 9 testes web focados.

O gate econômico de 120 dias agora compara quatro políticas de fixture
(`desatento`, `alivio`, `mercado`, `mobilidade`). Seed 73 terminou com cada
alternativa materialmente exercitada, conservação de dinheiro/recursos,
save/load equivalente e resultados diferentes (`ok=true`). A escassez e a
recuperação social continuam abertas, e o teste não substitui o gate natural
de dez anos.

Contratos de emprego permanente agora derivam o salário da facility authored
compatível com a ocupação (mantendo o piso V1 somente para sites sem facility),
em vez de inventar um valor fixo separado do payroll produtivo. O owner ainda
revalida saldo, autoridade, disponibilidade e agenda antes de cada pagamento.
Regressão focada de emprego: 10 testes.

O mercado agora persiste `observed_supply` e `observed_demand` por recurso e
assentamento. Esses mapas são derivados pelo owner a partir de estoques,
população, instalações, obras, pesquisa e reparos, publicados como deltas
causais do `market_updated` e preservados no save/load. Isso fecha a leitura
local necessária para decisões econômicas sem confundir pressão observada com
estoque estrangeiro ou executar qualquer compra automaticamente. A regressão
focada passou em 14 testes. O smoke preparado de comércio agora explicita o
reforço do tesouro comprador por uma decisão de pagamento auditada antes da
remessa, e a cadeia bloqueio → escassez → recuperação passa conservando
dinheiro, comida e save/load.

O contexto público compartilhado do menu civil agora anexa a leitura local
datada de oferta/demanda a cada oportunidade de abastecimento/mercado. O
provider pode considerar essa evidência ao selecionar uma affordance, enquanto
quantidade, fornecedor, conta, estoque e rota executável continuam sendo
recompostos pelo owner. A regressão do menu civil passou em 21 testes.

O Inspector do observatório também mostra essas leituras por assentamento,
incluindo preço e dia observado; o type-check e os 65 testes frontend medievais
passaram. Isso fecha a primeira superfície de observabilidade dessa leitura,
não a economia resiliente de longo prazo.

### Checkpoint de implementação — 19/09/2026

O fallback offline de workforce passou a ordenar as affordances pela pressão
material correta: com falta de comida, uma oferta enumerada cujo destino é
`farmer` é preferida a ofertas artesanais ou mercantis. A correção elimina uma
comparação com tupla aninhada que nunca classificava a agricultura como
prioridade; não cria população, renda ou comida. A regressão focada de
workforce/emprego passou em 38 testes e o smoke de 120 dias conservou
dinheiro/recursos e save/load. Isso melhora uma decisão de mobilidade, mas a
resiliência econômica e o gate de dez anos continuam pendentes.

O fallback de emprego permanente também desempata affordances da mesma pressão
em favor de `farmer` quando falta comida. A regra permanece offline/test-only,
usa somente IDs enumerados e deixa a execução/revalidação com Economy. A
regressão conjunta de emprego, workforce e smoke passou em 45 testes; isso não
fecha a resiliência econômica de longo prazo.

O modo offline/test agora também aceita transições ocupacionais já publicadas
quando um assentamento pressionado tem falta de mão de obra material. A política
é conservadora (pressão observada, ordenação estável e um ID enumerado); o owner
continua revalidando stipend, conta, disponibilidade, rota e agenda. Isso fecha
uma lacuna de mobilidade da economia, mas não transforma a escassez em equilíbrio
automático. A regressão focada de workforce/engine/history passou em 54 testes.

O gate pressionado/econômico de 120 dias da seed 73 voltou a passar após essa
mudança (`ok=true`, `natural_ok=true`, `pressured_ok=true`), conservando dinheiro
e recursos, com save/load equivalente e auditoria sem causas quebradas ou Story
material. A comparação econômica selecionou alívio, mercado e mobilidade; a
mobilidade agora registra transições ocupacionais materiais. O gate de três seeds
por dez anos e o provider remoto continuam pendentes.

O dossier compartilhado do turno institucional agora inclui leituras
institucionais conhecidas e capacidade estratégica derivada dos owners. Isso
fecha a passagem de memória estratégica para qualquer affordance do menu
composto, sem persistir score, affordance ou planner. A regressão focada de
dossier, decisão institucional e diplomacia passou em 29 testes. Provider
remoto, campanhas amplas, magia/ecologia geral e o gate final continuam
pendentes.

O clone transacional agora compartilha a topologia authored do mapa e copia
somente seu runtime mutável; rotas, sites, interdições e fila de updates ficam
isolados entre candidato e mundo publicado. A igualdade de `WorldEvent` também
compara sequências JSON como listas/tuplas, preservando a equivalência de
save/load sem alterar o formato dos payloads dos executores. O gate pressionado
de 120 dias com seed 73 voltou a passar (`ok=true`, `natural_ok=true`,
`pressured_ok=true`) após essa correção.

Na mesma data, ocupação pós-brecha, controle territorial e concessão
administrativa passaram a compartilhar o turno mensal de campanha; os owners
continuam separados e a administração só muda após cumprimento material.
Essa integração foi coberta pela regressão focada de campanha/menu (38 testes
acumulados entre as verticais).

O tick ecológico também passou a derivar estresse da capacidade operacional da
rota e de suas dependências físicas, distinguindo fechamento de degradação
parcial e mantendo decisão de criatura separada. A regressão dessa vertical
passou em 8 testes; generalização de escolas mágicas, territórios e ecologia
continua pendente.

O plano não reabre a espinha dorsal causal. `medieval-roadmap.md` e
`docs/handoff/medieval-current-state.md` continuam sendo a referência funcional;
este arquivo organiza somente o que ainda falta.

### Limite operacional do gate prolongado — 19/09/2026

Uma tentativa do gate natural de uma seed por 3.600 dias chegou ao dia 180
(mês 6) sem crash, mutação parcial observada ou erro de auditoria no trecho
executado, mas foi interrompida por custo operacional: essa configuração levou
cerca de 69 segundos para seis meses, o que projetaria muitas horas para dez
anos. Portanto o gate de dez anos continua **não executado**, e a interrupção
não deve ser registrada como falha causal nem como aceite final.

O clone transacional do mundo agora compartilha somente o prefixo de eventos
append-only entre candidatos e mantém uma lista própria para novos fatos; os
registros de estado, agenda, RNG e owners continuam em cópia profunda. O perfil
de 18 passos caiu de 14,5 s para 11,4 s, e o gate natural de uma seed por 120
dias terminou com `ok=true`, conservação econômica, save/load equivalente e
auditoria sem causas quebradas ou Story material. Isso melhora a viabilidade do
gate longo, mas não o substitui.

O gate comparativo de 120 dias foi executado depois desse checkpoint com as
seeds naturais 73, 101 e 137, a fixture pressionada `socorro` e os perfis
econômicos. O resultado passou com conservação de dinheiro/recursos,
save/load equivalente e auditoria causal limpa; a fixture registrou 9 pedidos
e 6 cumprimentos. O mesmo resultado mostra que a economia ainda termina com
déficit alimentar/pressão social, portanto o gate comprova operação causal e
diversidade de escolhas, não resiliência de longo prazo. O gate natural de
10 anos continua pendente.

A mesma fronteira de provider agora troca affordance IDs que contêm `stock:`,
`treasury:`, `account:`, `payroll:` ou `household-stock:` por tokens opacos no
prompt e remapeia a resposta ao ID canônico antes da revalidação. O dossier de
capacidade estratégica também expõe somente status e contagens ao ator; IDs de
objetivo/plano/fonte continuam disponíveis apenas ao Dao/API. A regressão de
IA, recourse, dossier, capacidade e diplomacia passou em 32 testes.

Na onda econômica, procurement agora preserva todas as rotas fiscais conhecidas
como alternativas distintas de oferta. A política mensal continua escolhendo a
melhor candidata por ordenação engine-owned, enquanto o menu institucional pode
selecionar qualquer caminho enumerado; quantidade, tarifa, cotação e rota são
recompostos pelo owner antes da abertura do frete. As escolhas mostram a rota
pública no rótulo, enquanto o ID continua sendo a única resposta aceita. A
regressão focada de procurement, roteamento, escassez, ajuda e recuperação
passou em 56 testes.

## Plano restante executável

### Demanda agrícola dimensionada pela escassez — 19/09/2026

O owner de workforce agora combina o sinal typed de limitação da produção com
`SettlementNeeds.missing_food`. Quando a facility agrícola está pressionada,
o relatório enumera a quantidade de trabalhadores necessária para os lotes
authored que cobririam o déficit observado; sem escassez, o comportamento
conservador de um lote permanece. As ofertas continuam limitadas a 20% da
coorte e a decisão/pagamento/conclusão física continuam independentes.

O evento de observação registra o delta engine-owned de quantidade, e a
validação de Knowledge exige esse recibo quando a demanda supera o shortfall
do lote mínimo. A regressão de workforce, emprego e engine passou em 46 testes.
O gate natural de 120 dias com `seed=73` caiu de 5.948 para 4.224 unidades de
comida ausentes e manteve conservação; isso é uma melhora material, não prova
de resiliência econômica ou de conclusão do gate final.

### Perseguição ritual no turno institucional — 19/09/2026

`assembly_denial_adapters()` agora compõe a negação/liberação de assembleias
rituais no menu mensal junto das demais decisões institucionais. A opção só é
enumerada para uma instituição com autoridade militar, coluna própria
preparada e abastecida, observação local recente e rito ainda em curso; não há
evento aleatório nem inferência por prosa. O provider escolhe o ID opaco e o
owner de Society recompõe tudo antes de executar, preservando o payload
`religious_persecution`, a pressão social posterior e os elos causais.

Regressão focada: `tests/test_medieval_rites.py` passou em 3 testes; a
regressão conjunta de ritos, decisão institucional, força e observatório
passou em 30 testes. Isso fecha somente a integração da vertical ritual no
turno comum; perseguição religiosa ampla e intriga operacional continuam
pendentes.

### Limite operacional atualizado do gate natural — 19/09/2026

Uma execução da seed `73` por `3600` dias alcançou o dia `450` sem crash ou
quebra de conservação observada, mas levou cerca de 355 s para esse trecho e
foi interrompida antes do horizonte final. A fome e a mortalidade cresceram sob
o perfil natural, o que mantém a resiliência econômica aberta. Esse artefato é
diagnóstico, não aceite: três seeds por dez anos, fixtures pressionadas e o
provider remoto continuam necessários.

### Checkpoint de lei ecológica por espécie — 19/09/2026

Os parâmetros de condição e pressão de habitat foram retirados do executor
como tabelas hardcoded e passaram ao registro engine-owned
`CREATURE_SPECIES`. Cada criatura persistida precisa apontar para uma definição
válida; narrativa não pode inventar metabolismo. `river_drake` e
`river_serpent` mantêm as leis authored atuais, e a regressão de criaturas e
hazards passou em 15 testes. Isso é uma base para ampliar ecologia, não o
encerramento de habitats, negociação ou magia geral.

### Checkpoint de probe operacional do provider — 19/09/2026

`tools/medieval_provider_probe.py` agora oferece a sondagem mínima separada do
smoke prolongado: recompõe uma affordance institucional atual, consulta o
provider real apenas sob execução explícita e rejeita resposta fora do conjunto
de IDs ou diferente de `NO_ACTION`. O probe também exige receipt de
`LLM_INTERPRETATION` sem delta e não executa o owner material. Sem credencial,
o comando falha explicitamente; a prova real continua pendente. A regressão
focada de AI, smoke e menu passou em 28 testes.

### Checkpoint de menu institucional único para ajuda — 19/09/2026

Respostas, cumprimentos e reparações de ajuda institucional agora são
affordances do mesmo menu mensal composto que já reunia pedidos, mercado,
pesquisa, campanha e manutenção. O executor de `institutional_aid` permanece
inalterado como owner dos termos materiais; a engine apenas deixou de abrir
uma segunda consulta para a mesma polity no mesmo boundary. Uma revisão
datada continua sendo usada quando há prazo físico a resolver. A regressão
focada do menu passou em 22 testes, com seleção por ID opaco e fulfillment
material de uma obrigação existente. Provider remoto real e o gate longo
continuam pendentes.

### Checkpoint de tecnologia agrícola — 19/09/2026

Foi adicionada uma segunda cadeia authored de tecnologia: `crop_rotation`
exige `irrigation`; depois de conhecida, `crop-rotation-works` converte uma
facility `irrigated_harvest` em `rotated_harvest`. A regressão focada prova a
ordem causal pesquisa → conhecimento → obra → produção, com consumo de
ferramentas/madeira, salários, trabalhadores e autoridade revalidados pelos
owners. O efeito observado é aumento de produção de alimento por lote, sem
alterar população ou criar recursos fora dos executores. Isso é avanço da onda
4, não encerramento da difusão tecnológica geral.
O release gate comparativo de 120 dias com seed 73 foi reexecutado após o
catálogo (`ok=true`), com conservação, save/load equivalente e auditoria causal
limpa nos perfis natural, pressionado e econômicos.

### Checkpoint de hazard por espécie — 19/09/2026

O owner de criaturas deixou de montar o payload de dano populacional ou de
instalação a partir de constantes específicas do drake. O efeito e os perfis de
resistência agora são derivados do `HazardInteractionDefinition` registrado para
a espécie escolhida, mantendo a lei engine-owned e a evidência navegável. Uma
regressão também percorre a segunda espécie authored (`river_serpent`) por
travessia material, fome, demanda vencida, decisão explícita e perda limitada de
uma coorte anônima. A regressão de criaturas/autonomia passou em 14 testes,
além de `compileall` e `git diff --check`; isso amplia a vertical de criaturas,
mas não fecha ecologia geral ou magia ampla.

O read model do observatório mantém o contrato `dict[str, bool]`: cada perfil
resistente ativo aparece como chave booleana no payload, sem colocar listas
transitórias no contrato público. A regressão composta de pesquisa, campanha,
criaturas/autonomia e decisão institucional passou em 47 testes após essa
correção.

O gate curto foi reexecutado depois dessa alteração (`seed 73`, 120 dias,
natural + `socorro` + comparação econômica) e terminou com `ok=true`:
conservação de dinheiro/recursos, equivalência de save/load e auditoria limpa;
os perfis econômico, de alívio, mercado e mobilidade produziram resultados
materiais distintos. Isso continua sendo um gate de regressão, não o gate final
de três seeds por dez anos.

A regressão consolidada das fatias de pesquisa, logística de campanha, cerco,
criaturas/autonomia e contrato de decisão do provider também foi reexecutada
depois desse catálogo: `45 passed` (`tests/test_medieval_research.py`,
`test_medieval_campaign_supply.py`, `test_medieval_siege_campaign.py`,
`test_medieval_creatures.py`, `test_medieval_creature_autonomy.py` e
`test_medieval_ai_decision.py`). Isso confirma a integração focada dessas
verticais e seus limites causais; não prova provider remoto, ecologia geral,
campanha territorial completa ou o gate de dez anos.

O recorte de integração institucional/econômica também foi reexecutado depois
do mesmo checkpoint: `85 passed` cobrindo agenda mensal, menu civil composto,
economia, migração, alfândega e conflito cívico. Esses testes comprovam os
owners e a revalidação das fatias existentes, mas não substituem provider
remoto nem a simulação natural de dez anos.

A vertical mágica ganhou uma contramedida authored específica para a segunda
espécie: `rite-of-serpent-countermeasure` consome reagentes/cristais, exige
qualificação e assistentes, dura 40 dias e registra o perfil engine-owned
`serpent_countermeasure`. A lei de hazard do `river_serpent` consulta esse
perfil, podendo reduzir sua exposição abaixo do limiar, enquanto a lei do
`river_drake` permanece inalterada. A regressão de ritos/hazard passou em 18
testes; escolas mágicas gerais e ecologia ampla continuam pendentes.

Na campanha, uma coluna atacante que já rompeu a resistência da guarnição pode
agora escolher retirada material antes de ocupar o assentamento. O owner aceita
as fases `sieging` e `breached`, recompõe rota e suprimento, encerra investimento
e preserva administração/ocupação; a transição `breached → withdrawn` ganhou
validação de proveniência própria. A regressão de cerco, ocupação e controle
passou em 28 testes; isso fecha uma saída pós-brecha, não guerra prolongada ou
solução política ampla.

O mesmo estado pós-brecha agora permite uma proposta formal de cessar-fogo
unilateral: a contraparte aceita ou recusa, o compromisso guarda a retirada da
coluna e o owner só conclui após marcha material. Cessar-fogo mútuo continua
restrito ao cerco ainda ativo, pois uma guarnição colapsada não pode prometer uma
retirada que o owner não consegue executar. A regressão de campanha passou em
29 testes.

Esta é a ordem de trabalho para concluir o roadmap sem transformar fatias V1 em
declaração de autonomia geral. Cada onda só avança depois do aceite indicado.

### Checkpoint de reativação de infraestrutura — 19/09/2026

Instalações interditadas por um fato material agora têm uma affordance
`reactivate_infrastructure_site` separada do reparo. O maintainer precisa
observar a instalação recuperada, possuir autoridade e presença local, escolher
o ID enumerado e passar pelo owner de Map; somente então `enabled` volta a
`true`, os relatórios de rota são recompostos e o evento registra a causa. Isso
fecha a lacuna de “integridade restaurada, mas operação nunca retomada” sem
reativação automática. A regressão focada de infraestrutura/menu passou em 23
testes. O fixture de travessia foi depois estabilizado para limitar a nova
facility agrícola de Cinzaverde no cenário preparado; a regressão conjunta de
infraestrutura, serviços de site e menu passou em 48 testes. O roadmap continua
parcial e o gate operacional permanece pendente.

### Checkpoint de catálogo PT-BR da observabilidade — 19/09/2026

Os componentes de inspeção e capacidade institucional deixaram de manter
strings próprias para mercado local, oferta/demanda e dimensões/status de
capacidade. Esses rótulos agora são derivados do catálogo `pt-BR`, preservando
a projeção read-only e sem alterar contratos ou estado do motor. O type-check
medieval e `app.test.ts`/`chronicle.test.ts` passaram em 12 testes. Isso fecha
somente essa fatia de produto; UI PT-BR integral, provider remoto e o gate final
continuam abertos.

### Checkpoint de payload causal persistente e navegação do Why — 19/09/2026

`WorldEvent.causal_payload` passou a ser campo explícito do contrato medieval,
incluído em `record_event`, `model_dump` e save/load. Antes, payloads anexados
por `model_copy(update=...)` podiam existir somente em memória e desaparecer
da persistência. A API agora entrega o campo e a Crônica o apresenta como
evidência estruturada no detalhe causal, sem transformar prosa em causa. A
regressão de persistência/criaturas/ritos passou em 22 testes e a regressão da
Crônica passou em 4; provider remoto, UI integral e gate final continuam
pendentes.

O contrato também bloqueia `StateDelta` escondido em `causal_payload` quando a
origem é `LLM_INTERPRETATION`; a LLM continua restrita à interpretação/seleção,
e somente owners emitem mutações. A regressão conjunta de persistência,
autoria e engine passou em 27 testes.

1. **Estabilização e prova operacional** — manter rollback/save-load sob execução
   persistente, repetir a prova com mais seeds e executar uma sondagem pequena com
   provider remoto (erro, orçamento, `NO_ACTION` e affordance stale). O checkpoint
   natural e pressionado de seed 73 por 360 dias já terminou sem crash e com
   auditoria causal limpa; ainda não substitui o provider operacional nem o gate
   de três seeds por dez anos. **Aceite:** nenhum crash, nenhuma mutação parcial e
   auditoria causal limpa.
2. **Agência institucional completa** — consolidar objetivos/planos e memória
   conhecida no turno único já existente; fechar persuasão ampla, compromissos
   sociais, traição/violação deliberada, descoberta por evidência e reparação
   sem apagar o breach histórico. Uma investigação privada atribuída agora pode
   gerar uma acusação institucional explícita, entregue ao sujeito como notice
   persistente; isso não presume culpa nem cria retaliação. A memória institucional agora é criada para
   qualquer termo bilateral concluído (pagamento, ensino, frete, retirada ou
   administração), não apenas ajuda; sua leitura continua derivada de fatos
   conhecidos e sem score persistido. **Aceite:** decisões independentes alteram
   obrigações e relações somente por owners, com cadeia navegável.
3. **Economia e mobilidade** — concluir renda/emprego das coortes, efeitos de
   escassez sobre saúde, migração e descontentamento, além de pedágio, trânsito,
   bloqueio e detecção de contrabando; manter alfândega e retorno/apreensão como
   affordances, nunca como resolução automática. Uma chegada migratória bloqueada
   agora também pode recompor uma rota para outra cidade conhecida quando os
   relatórios e a capacidade residencial atuais a tornam válida; a população só
   muda na chegada física posterior. **Aceite:** rota interrompida e
   rota alternativa produzem estoques, população e pressão social diferentes.
   As leituras locais de oferta/demanda já são canônicas; falta demonstrar que
   atores as usam para escolher alternativas materiais que reduzam escassez sem
   subsídio automático.
4. **Tecnologia e produção** — ampliar a árvore além de `field_drill`/`siegecraft`
   e demonstrar descoberta, instalação, operador, manutenção e treinamento em
   uma cadeia que altere comércio, defesa ou campanha. **Aceite:** sem instalação,
   autoridade ou suprimento, conhecimento sozinho não produz efeito material.
5. **Campanha e solução política** — generalizar manutenção/guarnição, combate,
   cerco, ocupação e controle já existentes para uma campanha persistente; fechar
   administração pós-ocupação, negociação de cessar-fogo e retirada. **Aceite:**
   ocupação sem guarnição/abastecimento não vira controle duradouro e uma solução
   política exige decisão e termos executáveis.
6. **Magia e criaturas** — transformar os ritos/hazards estreitos em definições
   engine-owned de escola, custo, alcance, duração e contramedida; adicionar mais
   de uma criatura com território, necessidades, memória, negociação e ataque
   material sem catástrofe obrigatória. **Aceite:** cada efeito tem resistência,
   recuperação, alvo e evidência física revalidáveis.
7. **Intriga, religião e observabilidade do jogador** — adicionar perseguição,
   conspiração e persuasão apenas quando pressão, organização, liderança,
   conhecimento e ações materiais existirem; a acusação baseada em finding já é
   uma primeira ação de intriga zero-delta, com evidência e aviso navegáveis.
   O `CampaignView` agora também recompõe ameaças ativas de cerco, rebelião e
   demandas de criaturas a partir dos owners canônicos, com alvo, severidade,
   status e evento-fonte; o atlas pode desenhá-las sem criar registro paralelo.
   Completar dossier multi-salto, mapa de controle/rotas/forças/ameaças/planos
   e UI PT-BR. **Aceite:** Dao vê a
   verdade completa, cada ator vê somente seu conhecimento, e o jogador consegue
   navegar do resultado às causas sem receber prosa como prova.
8. **Verificação final e release gate** — rodar regressões focadas por onda,
   fixtures pressionadas e três seeds naturais por dez anos; auditar causalidade,
   conservação, rollback, agenda/RNG, save/load e custo de IA. **Aceite:** mundos
   naturais estáveis são válidos; cadeia multietapas é obrigatória apenas nas
   fixtures pressionadas; nenhum delta nasce de Story/LLM.

### Nota operacional da onda 3

O owner de relief agora está registrado no menu civil composto; ajuda recebida
pode ser distribuída somente quando a instituição escolhe a affordance
`relief-distribute:*`. O smoke de 120 dias preservou recursos e save/load, e o
harness possui o perfil comparativo `alivio`, que executou nove distribuições
na mesma seed em que `desatento` executou zero. A fixture `socorro` continua
priorizando a cadeia de ajuda. A comparação confirmou trade-off material, mas
alternativas de oferta e resiliência econômica ampla ainda estão abertas.

As ondas 3 e 4 podem ocorrer em paralelo depois da onda 2. As ondas 5 e 6
dependem dos owners materiais estabilizados; a onda 7 depende dos contratos e
projeções; a onda 8 é sempre a última. Nenhuma onda autoriza declarar o roadmap
inteiro concluído a partir de um teste focado.

## O que ainda falta, em ordem prática

### Correção de revalidação de tecnologia — 19/09/2026

O fallback determinístico de aplicação de tecnologia agora aplica também
`required_site_capabilities` antes de criar um `ExpansionProject`, alinhado ao
mesmo owner de `expansion_options`. Uma regressão específica cobre site
authored incompatível; pesquisa/expansão passou em 33 testes e o gate de 360
dias com seed 73 terminou com conservação, save/load equivalente e auditoria
limpa. O horizonte natural de dez anos permanece pendente; a pressão
econômica observada no gate curto não foi mascarada como resiliência.

### Bloqueios imediatos antes de abrir novas verticais

- [x] Corrigir o limite de privacidade das consultas de recourse: IDs enviados
  ao provider não carregam `stock`, `treasury`, contas ou outros
  identificadores privados; os caminhos de recourse têm regressão focada sem
  sanitizar o prompt globalmente.
- [x] Reexecutar a regressão focada de recourse, diplomacia e decisão
  institucional depois da correção. A validação local passou; permanece apenas
  a execução operacional com provider remoto.
- Fazer uma execução operacional pequena com provider remoto, orçamento,
  indisponibilidade, `NO_ACTION` e affordance stale; registrar limites sem
  declarar autonomia geral. A sondagem local de 30 dias em 19/09/2026 falhou
  explicitamente antes de iniciar porque não há provider real configurado;
  isso confirma o fail-closed do harness, mas não substitui a validação remota.

1. **Fechar a vertical cívica e os contratos de fundação**: a anistia formal
   pós-negociação já possui estado persistente, save/load, API e UI; a distinção
   entre `NO_ACTION`, ausência de affordance e falha de provider já é validada
   na UI, e o contrato rejeita fato sem delta como mutação material. Resta
   apenas a validação operacional com provider remoto.
2. **Agência institucional utilizável**: concluir objetivos/planos persistentes,
   capacidade estratégica por dimensão e memória que entre no contexto de decisões
   futuras, sem criar um segundo planner. Persuasão agora também é uma affordance
   explícita sobre proposta aberta: registra tentativa causal e reavisa a
   contraparte sem aceitar, alterar termos ou executar compromisso.
3. **Economia de subsistência**: dar owner a emprego/renda recorrente das coortes
   sem instalação produtiva e fechar efeitos materiais de escassez, migração,
   descontentamento, bloqueio, contrabando e detecção. A classificação de carga
   contrabandeada, sua evidência privada e retorno explícito ao estoque de origem
   já existem em V1; apreensão agora também é uma affordance explícita do
   operador, limitada por classificação canônica, autoridade e capacidade de
   estoque, sem confisco automático.
4. **Difusão de tecnologia**: ampliar a árvore tecnológica e demonstrar descoberta
   → produção → treinamento → alteração observável em comércio, defesa ou
   campanha. Roubo e apprenticeship já têm caminhos materiais; migração agora
   também pode carregar prática institucional quando a chegada, a origem do
   conhecimento e a habilidade atual do residente são evidências canônicas.
5. **Campanhas e controle**: completar manutenção ampla, queda/rotação de
   guarnições, controle territorial sustentado e solução política; cerco,
   combate parcial, retirada voluntária material e o mandato explícito de
   controle já existem. A retirada encerra as interdições próprias, abandona
   suprimento pendente sem mover carga e inicia uma marcha física, sem transferir
   ocupação ou administração. Um cessar-fogo bilateral estreito agora reutiliza
   `DiplomaticProposal` com uma obrigação de retirada por coluna; cada owner
   aceita/recusa e cumpre sua própria marcha. A gestão do dever agora também
   entra na consulta mensal do próprio proprietário, mesmo sem contato
   estrangeiro; ainda faltam manutenção ampla, guerra prolongada e solução
   política pós-guerra mais ampla.
6. **Magia e criaturas**: generalizar hazard para escolas, custo, alcance, duração
   e contramedidas; depois adicionar múltiplas criaturas, ecologia, negociação e
   ataques à população sem criar catástrofe obrigatória.
7. **Conflito social e intriga**: depois da anistia, completar perseguição
   religiosa, conspiração, persuasão ampla e descoberta somente com pressão,
   organização, liderança, conhecimento e ações materiais reais. Protesto,
   greve, tumulto, movimento, rebelião e revolução V1 já existem; a negociação
   agora pode carregar uma oferta alimentar real do administrador, mas ainda
   faltam solução política mais ampla, perseguição religiosa e intriga
   operacional.
8. **Observabilidade e operação**: dossiers privados agora incluem fatos próprios
   e elos causais que o ator também conhece; ainda faltam perspectivas
   investigáveis mais ricas, mapa de controle/rotas/forças/ameaças/planos, provider remoto com orçamento e
   stale-ID/`NO_ACTION`, UI PT-BR e validação operacional.
9. **Verificação final**: suíte focada por onda; três seeds naturais por dez anos;
   fixtures pressionadas; auditoria de causalidade, conservação, rollback,
   persistência de agenda/RNG e custos de IA. Natural estável é válido; cadeia
   multietapas só é obrigatória nas fixtures pressionadas.

## Estado de partida

- [x] Economia material V1, mercado, tarifas, frete e procurement enumerado.
- [x] Barganha, espionagem, suborno e sabotagem em verticais causais estreitas.
- [x] Forças, combate voluntário, abastecimento, ocupação e guarnição V1.
- [~] Criaturas: drake, tributo, restrição, dano de instalação e investigação.
  O mapa V1 contém dois indivíduos independentes no único corpo d'água
  authored (`rio-lume`), agora com espécies engine-owned `river_drake` e
  `river_serpent`; ampliar para outro território exige primeiro uma nova
  premissa geográfica real (corpo d'água/território e rotas), não um spawn
  automático. Metabolismo mensal por espécie agora reduz condição de forma
  determinística e só agenda uma revisão quando cruza o limiar; ecologia de
  território e necessidades de habitat mais diversas permanecem pendentes.
- [~] Sociedade: protesto, greve, tumulto, movimento, rebelião, revolução e
  anistia formal pós-negociação V1; ainda faltam solução política ampla,
  perseguição religiosa e intriga operacional. A negociação cívica V1 já
  persiste a oferta alimentar no próprio `CivicMovement` até a decisão posterior
  da liderança; a entrega e o alívio só ocorrem na aceitação material, sem
  transformar a proposta em anistia ou vitória automática.
  Repressão militar de uma rebelião agora gera pressão social engine-owned
  limitada (`civic_suppression_pressure`) antes do receipt de supressão; isso
  não cria movimento sucessor nem altera administração.
  A negação material de assembleia ritual também carrega classificação causal
  engine-owned de `religious_persecution`, sem transformar prosa em causa ou
  criar uma rotina automática de perseguição.
- [~] Diplomacia e memória: propostas/obrigações, recusa deliberada e descoberta
  limitada por notices já existem; ainda falta memória estratégica ampla e
  reparação social além das verticais materiais atuais.
- [~] Pesquisa: apprenticeship existe; venda, roubo, migração e cadeia produtiva
  ampla ainda não estão fechados.
- [~] Cerco e campanha persistente têm fatia causal: `SiegeCampaign` agora
  desgasta a endurance da guarnição por força, provisões e pressão diária;
  controle territorial agora possui owner Society próprio e decisão explícita
  após ocupação/guarnição paga; combate amplo e solução política ainda não
  estão fechados.
- [~] Escolas mágicas, contramedidas gerais, múltiplas criaturas e ataques à
  população. Restauração, proteção e contramedida específica agora são escolas
  derivadas do blueprint; generalização de escolas, criaturas e ecologia ainda
  permanece pendente.
- [~] Observabilidade completa, provider remoto validado e smoke de dez anos em
  três seeds naturais. O observatório já projeta controle territorial,
  objetivos/planos, ameaças materiais (incluindo interdições físicas de rota,
  perseguição religiosa material, dano de hazard em instalação e migração
  bloqueada) e fontes
  canônicas; ainda faltam a
  validação operacional do provider remoto e o gate de dez anos.

## Ondas de implementação

- [~] **1. Higiene da fundação e contratos restantes** — Handoffs já registram
  as verticais recém-entregues. A reparação de ajuda preserva o receipt de
  `breach`, requer uma nova decisão/rota/estoque atuais e abre um novo frete;
  save/load, validação de proveniência e rejeição de affordance stale têm
  cobertura focada. O ownership físico existente é somente o conveyance bilateral
  de workshop: Map é dono da identidade/site e Economy dos vínculos de estoque e
  folha. Não introduzir `PropertyTitle` ou arrendamento até existir um owner
  canônico para direito patrimonial, prazo e seus efeitos materiais; não há
  fallback ou registro paralelo nesta onda. A crônica agora recebe datas humanas
  canônicas; a consulta institucional registra ausência de affordance sem chamar
  LLM e o observatório separa esse receipt, falha técnica e `NO_ACTION`. O
  contrato medieval agora também rejeita `STATE_TRANSITION` sem pelo menos um
  `StateDelta`, evitando promover texto/receipt vazio a mutação material. A UI
  agora valida e exibe separadamente os cinco contadores de decisão (consulta,
  recusa, falha técnica, ausência de affordance e ID obsoleto); ainda falta
  validação operacional com provider remoto.

- [~] **2. Estratégia institucional de longo prazo** — Renegociação de obrigação
  de pagamento quebrada já é uma affordance independente, preserva o breach e
  exige aceitação do outro ator. Objetivos e planos persistidos agora expõem uma
  capacidade estratégica derivada em três dimensões (reservas, insumos e defesa)
  dentro da consulta mensal existente. A memória institucional direcional já entra
  no contexto diplomático somente quando o ator possui notice e fato canônico
  correspondentes, sem expor termos estrangeiros e sem persistir um segundo score;
  conclusões de pagamento, ensino, frete, retirada e transferência administrativa
  agora também criam memórias para as duas partes, sempre ligadas ao receipt
  canônico. Ainda faltam memória estratégica ampla e compromissos sociais mais
  ricos; a distinção entre repudiar deliberadamente e falhar por prazo agora
  também altera, de forma engine-owned, a saliência direcional (-6 contra -4)
  somente com notice/fato canônico. A consulta de adoção defensiva agora também
  recebe as leituras institucionais que o ator conhece, com evidência canônica;
  isso ainda é contexto, não um score ou planner. O contexto diplomático também
  expõe a capacidade estratégica derivada do próprio ator, sem revelar inventário
  ou capacidade estrangeira. Não há planner
  paralelo nem execução automática criada por esse read model.
  O contexto cívico do administrador agora também inclui as leituras direcionais
  de memória que ele conhece, com IDs de fatos canônicos e sem saldo/estoque;
  isso fecha a entrada de memória na decisão cívica sem criar score ou planner.

  O read model de capacidade estratégica agora também recompõe, quando recebe
  o mundo canônico, `administrative_bandwidth`, `diplomatic_bandwidth`,
  `military_command`, `project_capacity` e `logistics_capacity` a partir dos
  contratos, propostas, forças, projetos e cargas já persistidos. As dimensões
  não reservam recursos nem criam objetivos; a regressão de estratégia e
  diplomacia passou em 18 testes.
  A projeção `GovernanceView` agora expõe essas dimensões por ator ao
  observatório Dao, com IDs dos registros-fonte e sem inventário privado; o
  contrato TypeScript e o `vue-tsc` também foram atualizados.
  O observatório agora mostra um painel PT-BR de capacidades em curso por
  instituição, explicitamente rotulado como leitura derivada; a UI medieval
  passou a 62 testes.

- [~] **3. Economia e escassez completas** — Interrupção de rota agora chega à
  evidência de subsistência sem criar ajuda automática; a entrada de runtime/API
  pode optar por uma única renda domiciliar inicial, financiada pelos tesouros e
  registrada como premissa factual, para que a primeira compra seja material.
  Contratos Economy-owned de emprego permanente agora permitem a uma instituição
  escolher um site local que ela possui, uma coorte, limite engine-owned e salário;
  cada mês revalida site, autoridade, coorte disponível e saldo, usando o payroll
  canônico ou registrando não pagamento. Uma chegada de migração agora recompõe a
  pressão social com dados materiais: alivia de forma limitada o `unrest` da origem
  conforme a fração que realmente chegou e transfere a pressão observada para o
  destino, tudo no receipt causal de `migration_arrived`; retorno físico não inventa
  esse efeito. Ainda faltam efeitos completos sobre migração e descontentamento,
  bloqueio/detecção e separação patrimonial mais ampla. A alfândega agora
  classifica recursos contrabandeados a partir do catálogo e preserva essa
  leitura no aviso/Why; o proprietário pode escolher devolver a carga ao estoque
  de origem quando a rota e a capacidade ainda forem válidas, ou o operador pode
  apreendê-la em estoque local após uma decisão própria. Declaração, evasão,
  pagamento, retorno e apreensão agora entram na consulta institucional mensal
  como affordances materiais, sem resolução automática.
  O
  protesto cívico já reserva trabalho e uma recusa eleva `unrest`; uma resposta
  material comprovada agora aplica alívio limitado pelo owner de Economy. O smoke
  natural continua necessário antes de declarar a onda fechada. Bloqueios
  repetidos de uma jornada agora recompõem, a cada sete atrasos físicos, um
  aumento limitado de `unrest` na origem, com delta de subsistência e causas na
  rota/jornada; a migração não é criada nem forçada por essa condição. A
  chegada bloqueada agora recompõe affordances transitórias de reroute para
  outra cidade conhecida, exigindo relatórios atuais, rota alternativa e
  capacidade habitacional; a execução só altera a jornada, não população ou
  estoque. A regressão de migração passou em 12 testes. Ainda faltam efeitos
  completos sobre migração e descontentamento, bloqueio/detecção e separação
  patrimonial mais ampla.
  Uma chegada que permanece bloqueada por falta de moradia agora também eleva,
  de forma limitada, o `unrest` do destino pela fração de pessoas impedidas.
  O delta pertence ao owner de subsistência e aponta para a jornada/rota; não
  abre tumulto, retorno ou reroute automaticamente. A política de recuperação
  não interpreta esse próprio delta como motivo suficiente para devolver a
  jornada no mesmo turno. A regressão de migração, conhecimento e engine passou
  em 26 testes; a resiliência econômica geral continua pendente.
  A demanda de workforce agora usa a ocupação real da facility: uma colheita
  limitada por trabalhadores pode oferecer a uma coorte
  artisan uma transição paga de volta para farmer, com o mesmo notice, stipend,
  reserva de pessoas e conclusão física; não há aumento de população nem comida
  gratuita. Para uma facility `harvest`, o limite de trabalhadores do receipt
  pode ser oferecido em lote bounded pelo shortfall engine-owned, enquanto as
  demais transições continuam em ofertas unitárias conservadoras.
  Emprego permanente também passou a exigir que o site escolhido tenha uma
  facility authored compatível com a ocupação da coorte (ou seja um site sem
  facility específica); salário não pode mais ser criado por proximidade apenas.

  O mapa authored agora também contém uma facility `harvest` local em cada
  assentamento, usando estoque público, tesouro, folha e owner/maintainer já
  existentes. A folha agrícola authored paga 4 por trabalhador, igual ao
  preço-base da ração, sem criar dinheiro fora do payroll de Economy. O smoke
  `socorro/73` por 120 dias passou sem mortes por privação (saúde média 880,5),
  registrou 9 pedidos, 6 cumprimentos e 3 migrações iniciadas por affordances
  materiais. Isso corrige a premissa de produção e abre mobilidade sem criar
  distribuição ou migração automática: a reserva doméstica continua exigindo
  renda, oferta conhecida, rota atual e decisão da coorte. O artefato foi
  auditado com 3.330 eventos, `broken_cause_ids=[]` e
  `story_material_events=[]`.

  O prolongamento pressionado de 360 dias com a mesma premissa agrícola
  (`socorro/73`) terminou com 13.527 eventos, população 10.717, 28 migrações
  iniciadas e 24 chegadas; não houve morte de personagem e a auditoria
  permaneceu limpa. Ainda assim, três cidades chegaram a
  `health=0`/`unrest=1000`. Isso é evidência de uma cadeia material de emprego,
  renda, rota e migração, não de economia resiliente: distribuição de excedente,
  alternativas de abastecimento e recuperação social continuam pendentes nesta
  onda.

  A reprodução no dia 30 mostrou que o déficit não é simplesmente ausência de
  comida: alguns assentamentos mantêm estoque público, mas as coortes locais
  não têm saldo doméstico para comprar a ração, enquanto agricultores migraram
  para ofertas de trabalho/estoque de outras cidades. A lacuna seguinte deve
  ser uma affordance real de renda, requalificação ou mobilidade, com payroll,
  mercado e chegada física como owners; não uma distribuição gratuita implícita.
  O turno institucional agora fornece ao provider um fragmento público de
  emprego permanente: pressão observada do assentamento, coorte, ocupação, site,
  limite e salário da affordance já enumerada. Saldos de conta, estoque e
  demais termos privados continuam apenas no owner, que recompõe e revalida a
  oferta antes de criar o contrato. Isso melhora a decisão sem transformar
  emprego em renda automática; ainda falta provar, com provider operacional e
  fixture pressionada, se a escolha recorrente reduz a escassez sem mascarar
  bloqueios de rota.
  No modo offline/teste, a mesma affordance agora tem fallback conservador: uma
  instituição escolhe no máximo um vínculo atual quando seu relatório público
  mostra fome, saúde baixa ou descontentamento. A decisão usa o ID transitório,
  e `create_permanent_employment` ainda recompõe autoridade, site, coorte,
  estoque e saldo antes de persistir o contrato; não há renda ou distribuição
  criada pelo fallback. A regressão de emprego passou em 9 testes e a regressão
  de engine/transação/renda em 33 testes. Isso melhora a recuperação offline,
  mas não fecha a resiliência econômica nem substitui o provider operacional.
  Recuperação de frete também entrou no mesmo menu civil: diante de carga
  interna realmente bloqueada, o proprietário pode escolher esperar ou abrir
  uma remessa sucessora por outra rota fiscal conhecida. O pedido original não
  é reescrito, não é pago novamente e a opção continua sendo revalidada por
  Economy/Map antes de abrir o novo order.
  Compras bilaterais bloqueadas também foram ligadas ao menu: o comprador pode
  solicitar reenvio por rota sem tarifa e o vendedor aceita ou recusa em turno
  independente. A resolução retorna a carga original ao estoque do vendedor e
  abre somente uma sucessora material; nenhum pagamento antigo é duplicado.
  Ofertas de transição ocupacional também passaram a entrar no mesmo menu
  mensal do grupo populacional, com contexto público de pressão e termos do
  notice; aceitar continua exigindo a decisão datada do grupo, pagamento do
  stipend e conclusão física posterior. O smoke determinístico responde
  `NO_ACTION` para essa família por escopo, portanto não finge que a lacuna de
  resiliência já foi resolvida.
  Migração e recuperação de jornadas agora também usam o contrato único do
  menu: o ator recebe somente `action`, `actor_ref` e
  `selected_affordance_id`; o owner recompõe contagem, ração, rota e relatórios
  atuais antes de executar. A decisão direta ainda é aceita por testes e
  entradas internas, mas a autorização material é criada pelo owner quando os
  termos precisam persistir. A regressão de migração passou em 12 testes e a
  integração de agenda/engine em 11, preservando proveniência da jornada,
  recuperação por rota conhecida e chegada física. Isso fecha a forma do
  contrato, não a resiliência econômica completa.
  O pagamento material de suborno e a abertura de alfândega também deixaram de
  carregar contas, valores ou equipe na decisão do ator. O owner recompõe esses
  termos e registra uma autorização interna antes de transferir dinheiro ou
  criar o posto; as regressões focadas passaram em 4 testes de suborno e 18 de
  alfândega.
  A proposta bilateral de transferência de workshop também passou a carregar
  somente o ID da affordance no consentimento do vendedor; o comprador deriva
  o destinatário e todos os vínculos atuais do owner de Map/Economy antes de
  aceitar. A aceitação bilateral segue a mesma forma ID-only. A regressão de
  conveyance passou em 11 testes.
  O novo perfil de fixture `mobilidade` exercita a mesma costura sem provider
  real: em 120 dias criou 20 contratos permanentes, liquidou 28 folhas e
  registrou 2 não-pagamentos, conservando dinheiro/recursos; a auditoria teve
  `broken_cause_ids=[]` e nenhum Story material. Isso prova a vertical de
  escolha e payroll, não resiliência geral nem comportamento natural.
  O evento `subsistence_resolved` agora preserva payload estruturado com demanda
  total, parcela pública, consumo doméstico, compras pagas, déficit e IDs das
  coortes; isso melhora o `Why` econômico sem criar consumo gratuito ou expor
  saldos privados ao contexto de atores.

- [~] **4. Conhecimento, produção e difusão** — Venda tecnológica já tem oferta do
  comprador, consentimento independente do detentor, pagamento canônico e receipt
  causal; a técnica só é aprendida depois da transferência e da validação de
  instalação, capacidade, autoridade e saldo. Roubo agora tem affordance própria:
  agente nomeado, presença física, sighting e relatório de instalação atuais,
  resultado `success`/`failure`/`discovered`, finding privado e canal `stolen`
  somente após execução. Apprenticeship agora aceita apenas recibos materiais
  `migration_arrived`/`migration_returned` do owner de migração; uma mudança de
  residência arbitrária não libera difusão. Um teste integrado agora demonstra
  venda → conhecimento → decisão de aplicação → construção paga → receita
  produtiva alterada, mantendo a cadeia navegável. A árvore militar agora tem
  `field_drill → siegecraft`: pré-requisitos são revalidados no owner de
  conhecimento e cada técnica conhecida acrescenta no máximo um passo de força
  de campo, demonstrado por teste. A migração agora também pode abrir
  apprenticeship para um residente habilidoso que chegou por jornada material,
  mesmo quando outro pesquisador concluiu o projeto de origem; a oferta aponta
  para o receipt de chegada e para o fato de conhecimento da instituição de
  origem. Ainda faltam uma árvore tecnológica ampla e efeitos observáveis fora
  desta defesa V1. A expansão de instalações agora também é uma affordance
  transitória do menu civil: em mundo com IA habilitada, uma facility ociosa e
  com capacidade cheia não inicia construção por política automática; o owner
  recebe apenas opções materialmente financiáveis, escolhe um ID e
  `start_expansion` recompõe a opção antes de criar o projeto. A adaptação de
  técnica já conhecida segue o mesmo caminho; o fallback automático permanece
  somente em mundos determinísticos.
  O patrocínio de pesquisa segue a mesma regra: em mundo com IA habilitada,
  o menu recompõe site, estoque, conta, pesquisador qualificado, pré-requisitos
  e orçamento; só a escolha da opção cria o aceite datado do pesquisador e o
  `ResearchProject`. A política mensal continua somente em mundos determinísticos;
  um mundo com IA sem provider permanece fail-closed.

  O início de cerco também foi ligado ao turno institucional mensal: somente
  uma coluna abastecida, investimento ativo e guarnição rival presentes entram
  no menu; a escolha é revalidada pelo owner de Society antes de agendar
  progresso. A ocupação pós-brecha continua separada e explícita. Uma concessão
  administrativa bilateral permanece disponível depois da ocupação quando o
  contato, a coluna e a pressão material ainda são atuais; a transferência
  continua sendo uma obrigação que o administrador precisa cumprir. Ainda
  faltam cessar-fogo amplo, manutenção fora do recorte e solução política
  posterior mais rica.

- [~] **5. Campanhas persistentes e controle territorial** — `SiegeCampaign` já
  persiste sobre investimento ativo e guarnição rival, revalida affordance,
  autoridade, força e suprimento, agenda progresso diário e reduz endurance por
  condições materiais reais. Ao atingir endurance zero, a owner de Society
  colapsa a obrigação de guarnição em fato separado, preservando a coluna rival
  presente e sem transferir ocupação/administração; a base pode também caducar
  antes disso. Save/load, validação e proveniência estão cobertos.
  Combate de campo agora registra, além da força, leituras engine-owned de
  terreno físico, fadiga de implantação e moral tática derivada de preparo e
  suprimento, com deltas próprios na resolução.
  A resolução agora registra moral tática engine-owned e, após uma brecha,
  recompõe uma affordance separada para ocupar materialmente o assentamento;
  isso ainda não transfere administração. Controle territorial agora é
  persistido separadamente: exige decisão atual, relatório local, ocupação e
  guarnição paga; a perda material dessa guarnição encerra o controle sem
  mudar administração. A instituição também pode retirar explicitamente o
  mandato de controle sem mover automaticamente a coluna. A retirada voluntária
  da guarnição agora é outra affordance: encerra apenas o dever e o controle que
  dependia dele, preservando coluna, ocupação e administração. A manutenção
  agora também recompõe uma affordance explícita de rotação: outra coluna
  própria, presente, abastecida e financiável substitui a duty ativa sem mover
  ocupação/controle; o ciclo antigo permanece `withdrawn` e o novo vínculo
  nasce com decisão e receipt próprios. Uma regressão agora prova que a
  concessão administrativa continua enumerável depois da ocupação pós-brecha,
  sem mudar administração até o cumprimento bilateral. Ainda faltam manutenção
  ampla, resolução de guarnições fora do cerco e solução política ampla. A projeção
  `CampaignView` agora expõe propostas vivas de desescalada/concessão
  administrativa com termos, estado e evento-fonte, e o Atlas as torna
  navegáveis; isso é observabilidade, não execução automática.

- [~] **6. Magia, criaturas e ação individual** — A primeira lei engine-owned de
  hazard de criatura já está registrada: a retaliação do drake contra instalação
  consulta resistência de ward, limita a magnitude e grava hazard/exposição/
  resistência na evidência causal. Os ritos atuais agora também expõem escola,
  custo material, alcance e duração como metadados derivados do blueprint, sem
  criar um registro de feitiços paralelo. O teste integrado cobre dano com e sem ward.
  Uma segunda lei engine-owned agora permite ao drake atacar uma coorte anônima
  real em um dos extremos observados da rota: a decisão expira a demanda, limita
  a perda, preserva moradores nomeados e emite deltas/cadeia causal no owner de
  Society; a projeção de hazard navega esse alvo como `population_group`.
  A resposta institucional agora também pode negociar em duas etapas: tributo
  parcial reduz o saldo da exigência sem encerrá-la, e uma entrega posterior
  liquida somente o restante; cada parcela consome estoque real e registra sua
  própria decisão/delta. A projeção de escola agora distingue restauração,
  proteção e contramedida sem criar catálogo paralelo, e o painel de pesquisa
  exibe esse catálogo derivado ao Dao. Ainda faltam escolas
  mágicas gerais, custo/alcance/
  duração amplos e ecologia. O segundo habitante authored agora é uma
  `river_serpent` real, com leis engine-owned próprias de resistência e
  magnitude para instalação/população, compartilhando apenas o habitat/rota
  física; não existe spawn automático. A primeira extensão de
  contramedida agora usa um perfil de resistência engine-owned distinto
  (`river_countermeasure`) em um rito de proteção real; o hazard consulta o
  perfil persistido da ward, sem registrar leis pela LLM. A ecologia mensal
  também recompõe pressão de habitat a partir de travessias canônicas fechadas:
  a espécie sofre somente o estresse engine-owned correspondente e o tick aponta
  para o fato de fechamento da rota; nenhuma demanda ou ataque nasce sem a
  decisão posterior da criatura. O tick também carrega payload estruturado de
  espécie, rotas fechadas, estresse, decaimento-base e decaimento total para o
  `Why`, sem usar prosa como prova.
  Criaturas agora mantêm uma memória curta de até 32 IDs de eventos canônicos
  que vivenciaram; o turno recompõe tipo/data somente desses fatos e o nested
  `CreatureState` avançou para schema 4, sem compatibilidade com saves antigos.
  A regressão focada de criaturas, autonomia, hazard e observatório passou em
  26 testes. Isso fecha memória local da vertical, mas escolas mágicas gerais,
  custo/alcance/duração amplos e ecologia ainda permanecem pendentes.

- [~] **7. Conhecimento privado, IA e observabilidade** — As projeções de API e
  observatório já expõem os receipts de venda tecnológica, campanhas de cerco e
  evidência de hazard para navegação causal/Why, mantendo leitura sem mutação.
  A consulta `/api/v2/query/dossier/{actor_kind}/{actor_id}` agora projeta a
  perspectiva privada de um ator a partir apenas de notices/facts que o engine
  já marcou como conhecidos, além de conhecimento técnico, memórias e planos
  próprios; inclui apenas elos causais cujo evento também é conhecido pelo ator,
  e não expõe inventário ou plano estrangeiro. O dossier agora também informa
  `causal_depth` para cadeias conhecidas que ligam decisões próprias a fatos
  observados, sem expandir causas desconhecidas; ainda falta validação de
  provider remoto sob erro, orçamento,
  affordance stale e `NO_ACTION`. A revalidação agora registra
  `institutional_decision_stale_affordance` quando o ID desaparece ou o owner
  rejeita a execução, sem criar decisão material ou delta.
  Uma recusa administrativa de demanda cívica agora também gera, pelo owner de
  Economy, um incremento limitado de `unrest` com receipt causal apontando para o
  encerramento do protesto; isso alimenta futuras affordances de migração/protesto,
  mas não abre revolta automaticamente. `organized_strike` agora existe como
  paralisação local de três dias, limitada por unrest observado e participação
  real da coorte; tumulto material V1 também existe e danifica apenas um alvo
  observado. Um movimento cívico V1 agora pode ser formado por dois ou mais grupos
  locais com relatórios atuais, catalisador recente, liderança nomeada e
  participantes reservados; a liderança pode dissolvê-lo após um prazo material,
  liberando os participantes. Uma greve geral V1 agora reserva trabalhadores
  adicionais por três dias e os libera por agenda. Uma rebelião V1 pode ser
  declarada apenas depois de mobilização concluída, pressão `800+` e liderança
  presente; ela conserva a administração e deixa a Economy registrar pressão
  causal, sem criar facção ou vitória automática. A administração agora pode
  oferecer negociação preventiva a um movimento ativo, ou suprimir/oferecer
  negociação sob autoridade militar e observação local;
  a liderança pode aceitar a negociação, liberar participantes e obter alívio
  limitado. Revolução V1 agora exige rebelião persistente, mobilização concluída
  e pressão `900+`, mantendo administração intacta. A anistia formal é uma
  decisão posterior do administrador, ligada à negociação aceita e ao movimento
  dissolvido; não apaga a rebelião histórica nem libera participantes novamente.
  Depois disso ainda falta solução política ampla. Uma negação material de
  assembleia ritual agora também passa pelo owner de Economy: a interrupção do
  rito registra `rite_interruption_pressure` com delta limitado de `unrest` e
  causas na negação/interrupção; isso apenas alimenta affordances cívicas
  futuras e não cria movimento automaticamente.

- [~] **8. Produto e operação** — `/api/v2` e observatório agora projetam campanhas,
  vendas tecnológicas, hazard impacts, movimentos cívicos, greves gerais e anistias,
  com save schema 60 e
  documentação atualizada;
  a UI passou a tipar as campanhas persistentes, paralisações cívicas e anistias,
  e exibir separadamente consultas,
  recusas, falhas técnicas e ausência de affordance. A projeção da anistia deve
  entrar no mesmo contrato, sem persistir affordances transitórias. O observatório
  também exibe ameaças ativas com fonte navegável, colore controle territorial no
  mapa e marca assentamentos com objetivos/planos canônicos; a projeção continua
  read-only e não cria affordances. Ainda faltam UI PT-BR integral, validação com
  provider remoto e o gate final. O serving do bundle medieval e a proteção
  contra fallback legado têm teste operacional verde.

- [ ] **9. Verificação final** — Executar a suíte focada por onda e, somente ao
  final, três seeds naturais por dez anos mais fixtures pressionadas para cada
  vertical. Auditar zero causas quebradas, zero deltas originados em Story/LLM,
  conservação econômica, persistência de agenda/RNG e pelo menos uma cadeia
  multiescala nos cenários pressionados. Registrar seeds, revisão, duração,
  eventos, custo de IA e limitações; não declarar a suíte global verde a partir de
  recortes.

- [x] **Checkpoint intermediário de múltiplas seeds** — a matriz natural de
  360 dias para as seeds `73`, `101` e `137` concluiu sem provider real. As três
  linhas passaram conservação de dinheiro/recursos, `save_load_equivalent` e
  auditoria (`broken_cause_ids=[]`, `story_material_events=[]`). Evidência em
  `/tmp/cws-release-gate-360-3`; isso ainda não substitui o gate de dez anos
  nem a sondagem operacional do provider.

- [x] **Fixture pressionada de múltiplas seeds** — a execução persistente de 360
  dias também concluiu `socorro/73` sem crash, com conservação de
  dinheiro/recursos, save/load equivalente e auditoria causal limpa. A fixture
  produziu protestos e cumprimentos de ajuda materialmente rastreáveis, mas
  terminou com escassez severa (10.422 unidades de comida ausentes, saúde média
  33 e 296 mortes por privação). O resultado valida pressão e cadeia causal;
  não valida resiliência da economia e mantém a vertical de escassez/mobilidade
  aberta. Artefatos: `/tmp/cws-release-gate-current`.

- [x] **Reparação material de pagamento** — uma obrigação monetária quebrada
  agora oferece ao devedor conhecido uma affordance transitória somente quando
  há autoridade de comércio e saldo corrente. `transfer_money` permanece o
  owner do movimento de contas; a transição final preserva o breach histórico,
  registra `payment_obligation_remediated` e atualiza as memórias canônicas.
  Evidência: 31 testes focados em pagamentos, renegociação, memória, ritos e
  civic; isso não fecha ainda remediação de todos os tipos de compromisso.

- [x] **Tecnologia aplicada à campanha** — `fortification` foi adicionada após
  `field_drill → siegecraft`. O conhecimento não cria tropas: somente quando o
  defensor conhece a técnica antes do início, o owner de Society aplica um
  bônus engine-owned limitado de +2 à endurance inicial do cerco (12 → 14),
  com receipt e validação persistentes. Evidência: 37 testes focados de cerco,
  engajamento, indústria e pesquisa.

- [x] **Tecnologia aplicada ao abastecimento** — `field_logistics` depende de
  `field_drill` e altera somente a capacidade engine-owned de ração/bagagem da
  coluna (+5 dias) quando o proprietário conhece a técnica. O aprendizado não
  cria comida nem desloca estoque; o dispatch continua uma affordance e o
  freight continua owner de Logistics. Evidência: 24 testes focados de supply,
  cerco e pesquisa.

- [x] **Pressão causal da repressão cívica** — a supressão escolhida pelo
  administrador agora passa pelo owner de Economy e aumenta `unrest` em no
  máximo 120, com decisão, delta e causa navegável; os participantes são
  liberados apenas pelo owner de Society. Evidência: 21 testes focados de
  civic, ritos e engine.

- [x] **Evidência de perseguição ritual** — `assembly_denied` agora expõe um
  payload canônico de conflito social com `kind=religious_persecution`, site,
  assentamento, observação e ator; o fato continua sendo uma negação militar
  material com pressão posterior do owner de Economy. Evidência: 18 testes de
  ritos, alcance e civic.

## Dependências críticas

```text
1 → 2 → 3/4 → 5/6 → 7 → 8 → 9
```

Ondas 3 e 4 podem avançar em paralelo depois da onda 2. A onda 7 depende dos
contratos estáveis das ondas materiais; a onda 9 é sempre a última.

## Próximo checkpoint executável

- [x] **A. Fechar anistia formal** — owner, validação de proveniência,
  schema/save-load, API, observatório, UI e um teste de negociação → dissolução
  → anistia. Verificar que participantes não são ressuscitados, administração
  não muda e o breach/rebelião continuam navegáveis. Evidência focada: teste
  cívico de negociação/anistia, 17 testes de API sem lifecycle, 58 testes de
  frontend, type-check, `compileall` e `git diff --check`.
- [x] **B. Rodar a matriz curta de regressão** — os recortes cívicos/material
  (30), API sem lifecycle (17), persistência (8), observatório (7), frontend
  (58), type-check, `compileall` e `git diff --check` passaram. O serving do
  bundle foi ajustado para resposta ASGI determinística; a asserção antiga de
  população foi alinhada à lei engine-owned de nascimentos e os planos de
  abastecimento aceitam `await_delivery` material.
- [x] **C. Escolher uma única vertical material para a próxima onda** — a
  escassez por rota interrompida, customs, retorno/apreensão explícita de
  contrabando e o efeito limitado de treinamento de campo já estão fechados;
  cerco, controle, rotação de guarnição e a primeira contramedida mágica foram
  adicionados sem engine paralela. O recorte escolhido foi difusão tecnológica
  por migração: a chegada e o conhecimento de origem agora são causas exigidas
  pela oferta de apprenticeship. O próximo recorte deve escolher entre árvore
  tecnológica ampla, solução política, magia adicional ou observabilidade.

Cada checkpoint deve terminar com evidência registrada (comando, revisão, seed,
resultado e limitações). Um recorte focado aprovado não autoriza declarar o
roadmap inteiro concluído.

### Evidência incremental de 18/09/2026

- [x] A lei de criatura foi ampliada sem rotina automática: depois de uma
  exigência vencida, o drake pode escolher `creature_attack_population` entre
  as affordances atuais. O owner de Society remove somente população anônima,
  em magnitude engine-owned, expira a demanda e grava o alvo/causa no payload
  de hazard. O contrato do observatório aceita `population_group` como alvo.
- [x] Verificação focada: `tests/test_medieval_creature_magic_interaction.py`,
  `tests/test_medieval_creatures.py`, `tests/test_medieval_creature_autonomy.py`
  e `tests/test_medieval_observatory.py` — 16 passed; `compileall` e
  `git diff --check` passaram.
- [x] Smoke natural preparado com seed 73, 180 dias e perfil determinístico
  reativo: recursos/dinheiro foram conservados e save/load/continuação foram
  equivalentes; a pressão de subsistência cresceu e produziu protestos. Isso é
  evidência de comportamento causal do cenário, não fechamento do smoke final
  de dez anos nem prova de autonomia geral.
- [x] Campanha: `withdraw_garrison` é uma decisão separada de dissolver a
  coluna. O owner persiste `garrison_withdrawn`, encerra controle territorial
  apoiado pela guarnição e conserva ocupação/administração; regressão de força,
  cerco e observatório: 16 passed.
- [x] Negociação de criatura: `CreatureDemand.food_received` permite uma
  entrega parcial engine-owned antes da liquidação. A affordance seguinte é
  recomposta com o saldo restante; a segunda entrega encerra a demanda e só
  então registra `settled_by_ref`. Teste focado cobre parcial, saldo aberto e
  quitação; a regressão conjunta de criaturas/autonomia/hazard/observatório
  ficou em 17 passed.
- [x] Difusão militar V1: `siegecraft` depende de `field_drill`, e o owner de
  pesquisa bloqueia aprendizado sem pré-requisitos. O efeito é limitado ao
  cálculo engine-owned de `field_strength`, sem transformar conhecimento em
  tropas ou vitória.
- [x] Smoke focado de subsistência até o dia 120 (seed 73) conservou dinheiro,
  recursos e save/load. A consulta de sabotagem deixou de assumir `site_id` em
  `ExpansionProject` e agora deriva o site por sua facility; o smoke anterior
  havia encontrado essa regressão no mês 7. A pressão segue material e pode
  colapsar um cenário natural, portanto isto não é um smoke final verde de dez
  anos.
- [x] Rotação de guarnição: uma segunda coluna própria já presente e abastecida
  pode substituir a duty ativa por decisão explícita; o owner mantém ocupação e
  controle territorial, encerra o vínculo antigo como `withdrawn` e persiste o
  novo `garrison:{detachment_id}` com causalidade. Testes de força, contato,
  cerco e comandos: 12 passed; `compileall` e `git diff --check` passaram.
- [x] Contramedida mágica V1: `rite-of-river-countermeasure` exige custo,
  habilidade, site e duração canônicos, persiste o perfil `river_countermeasure`
  na ward e o registro engine-owned de hazard aplica sua resistência limitada;
  a affordance não cria dano, criatura ou recurso e a regressão de ritos/hazard
  ficou em 13 passed.
- [x] Privacidade e difusão: IDs de suborno enviados ao provider deixaram de
  carregar contas/tesouros; a regressão de recourse, diplomacia, decisão
  institucional e pesquisa passou em 53 testes. Uma migração material agora
  pode levar prática institucional a um residente habilidoso que não foi o
  pesquisador original, desde que o conhecimento da origem e a chegada sejam
  fatos canônicos; a oferta de apprenticeship registra ambos como causas.
  A regressão de apprenticeship/migração passou em 14 testes e a regressão
  adicional de venda, roubo, combate e criaturas em 16 testes. Waypoints e
  atrasos de migração agora também emitem deltas materiais, corrigindo receipts
  `STATE_TRANSITION` sem delta.
- [x] Auditoria read-only inicial: `tools/medieval_causal_audit.py` carrega um
  save, executa a validação canônica de histórico e reporta causas quebradas,
  materialidade de Story e receipts de interpretação LLM. Ele não reexecuta
  decisões nem substitui o smoke final de longa duração.
- [x] O smoke de autonomia agora possui sondagem explícita de provider real:
  `--real-provider` não aceita perfil determinístico misturado, respeita
  `--ai-calls-per-step`, informa chamadas reais e falha sem fallback quando o
  provider não está configurado. Regressão do harness: 2 testes; a sondagem
  local confirmou a falha explícita esperada, portanto a validação remota
  continua pendente.
- [x] Cumprimentos de ajuda material agora criam memória institucional para
  as duas partes e uma leitura positiva direcional (+3) no credor, preservando
  a fronteira de conhecimento e a decadência da saliência. A memória aponta
  para o receipt canônico `institutional_aid_fulfilled`; regressão de memória
  e ajuda: 26 testes.
- [x] Contrato único de decisão nas opções institucionais: pesquisa, expansão,
  abastecimento, alfândega, socorro, workforce e recuperação de frete/compra
  registram no turno apenas `action`, `actor_ref` e
  `selected_affordance_id`. Tecnologia, instalação, conta, estoque, rota,
  quantidade e notice são recompostos pelos owners; quando a validação
  histórica exige termos completos, um receipt de autorização engine-owned
  aponta para a decisão do ator. A regressão focada dessas verticais passou em
  95 testes, além de `compileall` e `git diff --check`.
- [x] O fallback de compra de provisões domésticas agora é explicitamente
  determinístico: em mundos com `ai_enabled`, ele não executa compras por trás
  do grupo populacional; a compra continua dependendo de uma affordance e de
  decisões bilaterais futuras. A regressão de household provisioning, engine e
  menu institucional passou em 33 testes.
- [x] Serviço de porto/passagem entrou no mesmo turno institucional: em mundos
  com IA habilitada, suspensão/retomada exige a affordance atual do proprietário
  e revalidação pelo owner de Map; o fallback automático permanece apenas em
  mundos determinísticos. A regressão de serviços, agenda e engine passou em 17
  testes.
- [x] A política de tarifa de exportação também foi composta no turno
  institucional. Com provider consultável, a administração escolhe uma tarifa
  enumerada por affordance; sem provider, o fallback fiscal conservador continua
  disponível. O executor recompõe política, tesouro e relatório antes de alterar
  a taxa; o teste histórico de caixa insuficiente permanece uma expectativa WIP
  antiga e não foi mascarado.
- [x] Smoke pós-alterações: seed 73 por 30 dias com perfil determinístico
  `reativo` terminou com exit 0, `food_conserved=true`,
  `money_conserved=true`, `all_resources_accounted=true`,
  `save_load_equivalent=true`, 506 eventos e 0 causas quebradas na auditoria;
  `story_material_events` permaneceu vazio. Isso é regressão curta, não o gate
  natural de dez anos.
- [x] Reexecução natural após as mudanças recentes: seed 73 por 120 dias,
  `2268` eventos, conservação de dinheiro/recursos, save-load equivalente e
  auditoria com `broken_cause_ids=[]`, nenhuma Story material e 161 interpretações
  LLM em test mode. O provider real continua fora deste resultado.
- [x] A tentativa anterior limitada pelo harness foi substituída por uma execução
  persistente do release gate: seed 73 natural por 360 dias terminou em
  `horizon_complete`, com 13.103 eventos, conservação de dinheiro/recursos,
  `save_load_equivalent=true` e auditoria com `broken_cause_ids=[]` e
  `story_material_events=[]`. A dinâmica permaneceu materialmente pressionada
  (10.427 unidades de comida ausentes, saúde média 31,88, unrest médio 968,12 e
  296 mortes por privação); isso é resultado do cenário, não um crash.
- [x] O atlas da UI ganhou camada `Campanhas`: assentamentos mostram ocupação
  e controle territorial, rotas interditadas ficam destacadas e destacamentos
  presentes exibem sua contagem; planos conhecidos, cercos e instalações
  danificadas também recebem marcadores. A camada é apenas projeção do `CampaignView`,
  sem criar estado de mapa paralelo. `vue-tsc` e os 60 testes medievais da UI
  passaram.
- [x] Persuasão diplomática V1: uma instituição proponente pode escolher uma
  tentativa datada sobre proposta aberta; o fato é zero-delta, aponta para a
  decisão e para a proposta, e a contraparte recebe novo aviso. A proposta
  permanece `offered` até sua própria resposta. Política/negociação focada:
  45 testes passaram.
- [x] Gestão de guarnição pelo próprio proprietário: estabelecimento, retirada e
  rotação agora são adapters da consulta mensal da instituição, além do fluxo
  de contato bilateral. O owner continua sendo `Society/force`; nenhuma agenda
  ou estado paralelo foi criado. Regressão focada: 1 teste.
- [x] Negociação cívica material V1: a oferta administrativa enumera estoque e
  quantidade atuais, persiste os termos no movimento e só consome alimento
  quando a liderança aceita. Estoque alterado torna a aceitação stale; o
  alívio social continua sendo derivado pelo owner de Economy. Regressão cívica:
  10 testes passaram.
- [x] Investigação privada V1: o dossier inclui decisões do próprio ator e,
  para cada fato conhecido, somente os elos causais cujo evento também está no
  conjunto conhecido; a cadeia completa permanece no endpoint causal do Dao.
  `tests/test_medieval_dossier.py`: 3 passed.
- [x] Smoke natural persistente: seed 73 por 360 dias com perfil determinístico
  `reativo` terminou em `horizon_complete`, com 7.698 eventos, conservação de
  dinheiro/recursos e `save_load_equivalent=true` no save
  `/tmp/cws-natural-360.mws`. A escassez evoluiu materialmente até 316 mortes,
  saúde média 8,38 e unrest médio 991,62; isso é dinâmica observada, não crash.
  A auditoria do save encontrou `broken_cause_ids=[]`,
  `story_material_events=[]`, 666 interpretações LLM e 3.793 eventos materiais.
  `aid_requests_total=0` é limite do decisor determinístico do smoke (ele cobre
  socorro direto e protesto), não evidência de que a affordance de pedido não
  exista; provider real ainda requer sondagem operacional.
- [x] O harness ganhou o perfil de fixture `socorro`, que seleciona somente IDs
  enumerados da cadeia de ajuda institucional (resposta, cumprimento ou pedido)
  antes do socorro direto. Seed 73 por 120 dias terminou com 3.496 eventos,
  9 pedidos, 5 cumprimentos, conservação econômica, save/load equivalente e
  auditoria com `broken_cause_ids=[]` e nenhuma Story material. A regressão do
  harness passou em 3 testes.
- [x] Findings privados de espionagem, investigação e roubo tecnológico agora
  entram no contexto diplomático somente para o `recipient_ref` canônico, com
  resultado, alvo e eventos de evidência; nenhum saldo, estoque ou segredo
  estrangeiro é copiado para o contexto. A regressão focada de diplomacia,
  espionagem e roubo passou em 21 testes.
- [x] A projeção `/api/v2` de diplomacia agora expõe ao Dao os findings
  estratégicos canônicos (espionagem, investigação e roubo tecnológico),
  preservando `recipient_ref`, resultado e eventos de evidência para navegação
  causal. A UI/mapper tipa e valida o novo campo, e o painel de diplomacia
  lista cada finding com seu destinatário e o evento causal navegável; type-check e os 61 testes
  medievais da UI passaram, e a regressão da API/observatório passou em 21 testes.
- [x] A validação do ledger causal no commit do engine passou a validar apenas
  o sufixo de eventos acrescentado ao candidato isolado; load/auditoria continuam
  usando a varredura completa. A regressão de persistência/eventos passou em 102
  testes, e o smoke natural de 120 dias continua com conservação e
  `save_load_equivalent=true`. O smoke de dez anos foi iniciado, chegou ao dia
  420 sem crash, mas foi interrompido por custo operacional (não é aceite final).
- [x] O teste de persistência do engine foi alinhado às agendas datadas atuais:
  doze passos podem atravessar dias de frete/recourse sem equivaler a doze
  meses. A verificação agora exige igualdade exata entre a linha contínua e a
  linha save/load, além de progresso real da prática; `tests/test_medieval_engine.py`
  passou em 6 testes. Isso corrige uma expectativa obsoleta do teste, não fecha
  o smoke natural de dez anos.
- [x] Recusa deliberada de ajuda agora deixa memória social no lado que pediu
  auxílio. O evento de rejeição continua sem delta material além do status do
  pedido, mas declara a memória canônica, é entregue por notice especializado e
  produz leitura direcional limitada (`-2`) contra o provedor; o provedor não
  recebe ressentimento automático. A regressão de ajuda/memória passou em 27
  testes e a validação aceita notices especializados como fronteira de
  conhecimento, sem duplicar o conteúdo privado.
- [x] A leitura de caixa diplomático passou a proteger uma folha corrente, em
  vez de duas, antes de enumerar contrapropostas. A escolha continua sendo
  somente uma affordance; pagamentos revalidam saldo e autoridade no owner.
  A regressão de barganha/ensino passou em 14 testes, incluindo a tentativa
  zero-delta e a cadeia contraproposta → aceitação → pagamento → ensino.
- [x] Workforce de subsistência: uma facility `harvest` limitada por `labor`
  agora publica demanda de `farmer` bounded pelo shortfall; coortes `artisan`
  podem aceitar a transição paga de retorno e concluir fisicamente a mudança.
  A rotação mensal prioriza grupos com affordances vigentes, e o smoke
  `mobilidade/73` em 120 dias registrou 9 transições iniciadas e 7 concluídas,
  com conservação econômica e save/load equivalente. A escassez permanece
  aberta como problema de escala e oferta, não como mutação gratuita.
- [x] A vertical mágica ganhou uma segunda contramedida engine-owned para outra
  causa real: `rite-of-flood-control` é um ward material com custo, qualificação,
  duração de 30 dias e perfil `flood_control`; a definição de enchente já
  consulta esse perfil ao calcular resistência de infraestrutura. O rito não
  cria integridade nem cancela a enchente, e a regressão de ritos/hazard passou
  em 12 testes.
- [x] O atlas passou a destacar demandas abertas de criaturas na camada de
  campanha: a rota conhecida recebe uma linha de ameaça e um marcador no ponto
  médio. A UI deriva isso de `CreatureView.demands`; não persiste affordances,
  não revela inventário e não transforma uma demanda em ataque automático. O
  type-check e os 61 testes medievais do frontend passaram.
- [x] A criação de um segundo indivíduo do Rio Lume revelou e corrigiu um
  acoplamento da agenda: revisões de criatura agora usam
  `creature-review:{creature_id}:{day}` e o executor atende somente os IDs
  agendados, em vez de consultar todos os habitantes do rio. Cada demanda
  continua ligada ao próprio `last_event_id`, sem fan-out de decisões ou
  efeitos; criaturas/autonomia/hazard passaram em 11 testes.
- [x] Smoke natural pós-multiplicidade (seed 73, 120 dias) terminou com 2.815
  eventos, conservação de dinheiro e recursos, save/load equivalente e
  auditoria `broken_cause_ids=[]`, sem Story material. A pressão de subsistência
  continua observável (`missing_food=10.145`, saúde média 731,25 e unrest médio
  268,75); isso é evidência curta, não o gate final de dez anos.
- [x] O novo `tools/medieval_release_gate.py` consolidou o smoke natural e a
  fixture pressionada em uma única verificação auditável. A execução da seed 73
  por 120 dias com `--pressured` preservou comida/dinheiro/recursos, manteve
  save/load equivalente e auditoria sem causas quebradas nem Story material,
  além de exercitar pedidos e cumprimentos institucionais de ajuda. Isso fecha
  apenas um gate curto de release; continuam pendentes o provider real e as
  três seeds naturais por dez anos.
- [x] Checkpoint anual pressionado: a fixture `socorro` da seed 73 por 360 dias
  terminou em `horizon_complete`, com 17.406 eventos, conservação de
  dinheiro/recursos e auditoria causal limpa (`broken_cause_ids=[]`, nenhuma
  Story material). A fixture produziu 33 pedidos e 29 cumprimentos de ajuda;
  portanto a cadeia institucional foi exercitada sem transformar ajuda em
  automação do motor. O resultado é uma prova de 1 ano/1 seed, não o aceite
  final de três seeds por dez anos.
- [x] O teste de persistência do engine foi alinhado às agendas datadas atuais:
  doze passos podem atravessar dias de frete/recourse sem equivaler a doze
  meses. A verificação agora exige igualdade exata entre a linha contínua e a
  linha save/load, além de progresso real da prática; `tests/test_medieval_engine.py`
  passou em 6 testes. Isso corrige uma expectativa obsoleta do teste, não fecha
  o smoke natural de dez anos.
- [x] A campanha pós-brecha ganhou uma regressão explícita da solução política
  que existe no recorte V1: depois de ocupar materialmente o assentamento, o
  atacante ainda recompõe uma affordance de concessão administrativa baseada em
  contato, coluna e pressão atuais; nenhum `administrator_id` muda antes do
  cumprimento bilateral. A regressão conjunta de cerco e concessão passou em
  11 testes.

## Fora deste plano

Não criar DSL mecânica nova, facção política isolada, tesouro imperial,
logística profunda, guerra territorial independente, doença ou uma segunda
engine/planner para cada vertical. Novas features devem compor owners,
affordances, decisões, compromissos, fatos e deltas já existentes.
