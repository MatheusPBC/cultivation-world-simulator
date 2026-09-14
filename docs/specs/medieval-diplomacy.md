# Diplomacia — propostas e compromissos

Implementação incremental da etapa3 do plano aprovado; não encerra A3.
Primeiro acordo concreto: pagamento por ensino institucional. A estrutura aceita
termos tipados, não instruções mecânicas inventadas por prosa. Acordos territoriais,
proteção, fornecimento, não agressão e concessões de acesso continuam necessários.

## Fronteiras

RelationsState possui propostas imutáveis quanto às condições e obrigações por
termo. Não possui moeda, estoque, tecnologia ou autoridade. EconomyState transfere
dinheiro; KnowledgeState recebe conhecimento via ensino bilateral. AuthorityState
inclui mandato diplomacy. O observador continua sem comandos materiais.

Uma oferta contém proponente, contraparte, expiração e até oito cláusulas. Cada
cláusula nomeia devedor/credor, prazo absoluto e dependências em cláusulas anteriores.
PaymentClause nomeia contas e valor positivo; TeachingClause nomeia técnica.
Os dois atores são distintos e todas as cláusulas pertencem às mesmas duas partes.
O prazo de cumprimento é posterior à expiração da oferta. Dependências não formam
ciclos e não vencem depois da cláusula dependente.

Uma decisão atual/exata e autoridade permitem oferecer; contraproposta cria outra
oferta e marca a anterior como superada, preservando condições e fatos anteriores.
Aceitação/recusa vêm apenas da contraparte com autoridade atual. Aceitar cria
obrigações, nunca move bens nem concede conhecimento. A proposta aceita conserva
suas condições mesmo se um terceiro possuir dinheiro ou se o governante mudar.

Cumprir requer nova decisão material no dia atual, intenção exata, dependências
cumpridas e autoridade vigente. Pagamento usa transfer_money; ensino exige as duas
novas decisões de teach/learn e usa teach_technology. Cada recibo material cumpre
somente uma obrigação. Falta de saldo/conhecimento/autoridade não vira pagamento
ou ensino fictício. A transação do simulador preserva rollback sob erro de save.

Oferta expira na data marcada; obrigação pode ser executada até seu due_day e é
apurada no dia seguinte. A agenda híbrida acorda nessas datas, não somente no mês.
Descumprimento cria fato de quebra, sem multa automática. Obrigação condicionada
a outra quebrada é dispensada, sem acusar o credor inocente de uma nova quebra.
Isso ainda não é prova de traição deliberada, descoberta por terceiros ou reputação.

Propostas são interações entregues diretamente entre as partes; KnowledgeState
registra notices dos fatos comunicados somente aos participantes. O observador
onisciente não transforma esses registros em conhecimento público. A difusão e a
descoberta por terceiros precisam de canais próprios em uma unidade posterior.

## Persistência e provas

O save atual exige `RelationsState`, notices e memória institucional no schema
28; schemas anteriores são preservados e rejeitados, sem migração ou sobrescrita.
Validação liga condições ao recibo original e status ao próprio evento de mudança;
obrigações aceitas, pagamento/ensino e prazos mantêm referências causais.

### Conhecimento e memória institucional

`KnowledgeState` é o owner do conhecimento factual: cada parte recebe seu
`DiplomaticNotice` privado. `RelationsState` não copia o conteúdo do fato; ele
persiste somente a `InstitutionalMemory` ativa (`id`, `institution_ref`,
`event_id`, `recorded_day`, `last_reinforced_day`). A memória precisa apontar
para o evento canônico de transição conhecido e para o receipt/delta que registra
sua criação ou reforço. Saliência e view são derivadas na leitura, com decaimento
linear em 360 dias, sem mutar o estado. Na V1, apenas ajuda alimentar tem view
direcional: o credor lê breach como -4 e remediação como +2. Não existe score
social genérico salvo, fator de LLM, UI/API, IA real ou estratégia geral.

Testes preparados em tests/test_medieval_diplomacy.py provam contraproposta100→80, oferta anterior não aceitável,
aceitação sem transferência, pagamento80 pelo owner econômico, ensino dependente
do pagamento, reexecução recusada, autoridade perdida, prazo em dia intermediário,
dispensa de dependência, save/load e rollback. A política determinística de
barganha (contextos por ator, ofertas mensais, prazos e reoferta) já está
integrada e coberta por tests/test_medieval_diplomacy_policy.py; API/observatório
e o painel visual também estão conectados (ver seções abaixo). Sem IAreal ou
cota de acordos obrigatórios; isto não fecha a etapa nem o plano geral. Evidência
de execução (contagens, evidência manual e status da suíte ampla) está centralizada
em docs/handoff/medieval-current-state.md; este documento descreve apenas o contrato.

O núcleo está implementado e coberto por testes focados. Ele não foi exposto como comando
material público. Recibos das duas partes são notícias privadas, mas reputação,
intenção de trair e descoberta por terceiros ainda não têm política/executor.
Ensino continua institucional e imediato quando executado, não curso com duração.
Propostas superadas/aceitas deixam o lembrete de expiração na agenda: ele é
consumido sem efeitos, podendo produzir um salto intermediário inócuo.

## Ajuda alimentar institucional (vertical preparada)

A ajuda alimentar é um executor direto delimitado, não uma política automática nem
uma conclusão da Stage 2. O solicitante recompõe opções transitórias apenas a partir
do seu próprio `SettlementReport` atual com `missing_food`; as affordances são
objetos transitórios e não são persistidas. O ID selecionado persiste somente na
decisão, no receipt e na proveniência causal. O pedido entrega ao provedor somente
um aviso privado, e a aceitação ou recusa produz uma resposta privada ao
solicitante; nenhum desses avisos revela oferta, estoque estrangeiro ou rota. O
único valor quantitativo persistido é `requested_food`, calculado pelo engine a
partir do relatório causal atual do requester, não um report vivo; o provider
avalia-o contra seu próprio stock e relatórios fiscais datados.
O provedor decide aceitar ou recusar de forma independente.

Aceitação não movimenta estoque, dinheiro ou frete. Uma decisão posterior, atual e
de abastecimento do provedor recompõe os termos com autoridade, oferta e relatórios
fiscais datados de rota, revalida a rota válida, abre o frete de comida e marca a
obrigação como cumprida no despacho; a chegada e qualquer bloqueio posterior
continuam pertencendo à logística. Se o despacho não ocorrer, a quebra persiste.
Sua remediação exige nova decisão do provedor, aviso privado da quebra, autoridade,
estoque e rota atualmente válidos; abre um novo frete e nunca apaga a quebra
original. Não há decisão por IA real, mutação pública por UI/API ou divulgação de
inventário estrangeiro nessa vertical. O fallback `routine-rules` faz no máximo uma
ação por polity/revisão, na prioridade `respond`, `fulfill`, `remediate`, `request`;
request usa apenas plano bloqueado, shortfall atual e uma cadeia/settlement aberto,
e as demais ações exigem opções atuais válidas. A agenda permite request N, reply
N+1 e fulfillment N+2.

## Integração autônoma determinística (implementada)

Decisor determinístico recebe contexto isolado por instituição: conta própria,
técnicas próprias, capacidades de sites próprios, catálogo público e propostas
entregues via notices. Não recebe caixa, técnicas ou estoques privados estrangeiros.
Interesse inicial é operacional (poder aplicar ou pesquisar a técnica nas próprias
instalações), não interpretação mecânica da prosa dos interesses institucionais.

Preço-base usa custo local estimado de pesquisa (materiais e trabalho). Oferta pede
esse custo; comprador aceita até80% dele, limitado ao caixa livre após reserva de
dois meses de folha produtiva. Vendedor aceita contraproposta até60% de seu custo.
Esses parâmetros são uma política inicial calibrável, não resolução geral de persuasão.
Conhecimento recebido não cria instalações; comprador sem capacidade/pré-requisitos
ou já conhecedor recusa. Orçamento insuficiente permite contraproposta, não dívida.

Novas ofertas são mensais. Revisão entregue acorda no dia seguinte; contraproposta,
aceitação, pagamento e ensino têm passos distintos. Oferta expira em15dias;
pagamento vence em20 e ensino em25, condicionado ao pagamento. Política não assina
cláusulas fora desse formato implementado. Revalida autoridade e recursos antes de
cada cumprimento. Impedimento material mantém obrigação ativa até recuperação/prazo.
Falha técnica propaga para rollback; não é interpretada como recusa ou traição.

Não repetir oferta a mesma contraparte/técnica durante180dias; ensino já cumprido
e comunicado impede reoferta. Essa memória usa apenas negociações conhecidas pelo
ator. Identidades e contas de recebimento institucionais são endereços públicos;
seus saldos não entram no contexto alheio. API/UI projetam condições, obrigações,
partes informadas e causas sob snapshot único, sem novos comandos materiais.

## API, observatório e painel conectados

GET `/api/v2/query/diplomacy` retorna `DiplomacyView` como listas planas
(`proposals`/`obligations`/`notices`); o mesmo payload aparece no campo
`diplomacy` de `query/observatory`. O agrupamento por proposta/cláusula não
acontece na API — é feito no composable `useDiplomacy.ts`, que indexa
obrigações por `proposal_id:clause_index`, resolve nomes por `entityName` e
abre a crônica causal a partir de `decision_event_id`, `last_event_id` e
`material_event_id` de cada obrigação. Notices exibidos são apenas os do próprio
evento (`event_id`), preservando a regra de que a visão onisciente do observador
não transforma um registro privado em conhecimento de um ator não notificado.

Consultas separadas (`query/diplomacy`, `query/economy` etc.) compartilham a
mesma trava/contrato de serialização, mas cada requisição não garante a mesma
revisão que outra requisição feita em outro instante — o mundo pode avançar
entre elas. Apenas uma única chamada a `query/observatory` é atômica entre todos
os seus campos (incluindo `diplomacy`).

Evidência de execução (contagens de testes, prova manual e status da suíte
ampla) está centralizada em docs/handoff/medieval-current-state.md.
