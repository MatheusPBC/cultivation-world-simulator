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

Save11 exige RelationsState e notices; schemas1–10 são preservados e rejeitados.
Validação liga condições ao recibo original e status ao próprio evento de mudança;
obrigações aceitas, pagamento/ensino e prazos mantêm referências causais.

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
