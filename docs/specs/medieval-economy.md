# Economia material medieval

Detalhamento da etapa 2 do plano aprovado. Este subsistema não substitui comércio,
contratos, transporte ou política: fornece os recursos sobre os quais eles atuam.

## Contrato

`EconomyState` é o único dono de estoques e contas monetárias. Um estoque tem ID,
proprietário `EntityRef`, povoado e capacidade em unidades de carga. Cada recurso
tem peso inteiro positivo nessa unidade. Dinheiro usa unidades monetárias inteiras;
não é mercadoria e não ocupa armazém. Nenhum saldo pode ser negativo.

Receitas versionadas especificam insumos, produtos, ocupação, trabalhadores por
lote e capacidade espacial requerida. Instalações produtivas referenciam o site
do mapa e um estoque do mesmo proprietário/local. O mapa continua dono da
integridade e disponibilidade; não recebe inventários ou uma segunda rede.

No fechamento mensal, produção precede consumo. Instalações são processadas por
ID estável, compartilhando o contingente local de cada ocupação. Cada trabalhador
contribui no máximo para uma instalação nesse fechamento; recrutamento reduz o
contingente produtivo no próximo fechamento. Treino pessoal é atividade fora do
expediente nesta primeira regra de trabalho agregado. A capacidade mensal é
reduzida pela integridade, falta de insumos e espaço líquido após transformação.
Insumos produzidos por instalação anterior podem ser usados no mesmo fechamento.
Essa ordem é explícita e reproduzível, não uma cadeia ilimitada de fabricação.

Alimento é uma ração pessoa/mês; cada pessoa viva residente exige uma ração,
incluindo personagens nomeados uma única vez. Consumo usa o estoque público
designado do povoado, não confisca estoques privados. Falta de alimento reduz
saúde e eleva descontentamento proporcionalmente à fração não atendida; atendimento
integral recupera gradualmente esses indicadores. Saúde e descontentamento usam
inteiros de 0 a 1000. Nesta unidade não há mortes ou migração automáticas: esses
efeitos serão executados pela demografia, preservando a contabilidade de pessoas.
Em migrações temporais, `population` continua residente na coorte de origem e
`present_population` desconta os viajantes; pantry e `MoneyAccount` da família
viajam por transferência bilateral entre donos, não por consumo de subsistência.

Produção, consumo, alterações de saúde e transferências monetárias geram deltas
separados de decisões, com causas apontando para os fatos que alteraram os insumos
ou o site. O último evento por recurso é proveniência, nunca estoque duplicado.
Cada instalação registra os lotes e fatores limitantes do último fechamento.
Mesmo sem produção, o fato pode ligar dano/indisponibilidade à escassez local.
Operações inválidas validam antes de aplicar. O fechamento ocorre no candidato
transacional do simulador: falha de save não publica economia parcial.

O save incorporou catálogo, receitas, instalações, inventários, contas,
abastecimento e proveniência no schema2; o formato atual é save19/Economy10, incluindo
folhas, políticas tributárias, reparos, provisões de jornadas e postos civis de alfândega. Saves experimentais anteriores
não são migrados ou sobrescritos silenciosamente. O catálogo inicial é ajustável no JSON;
seus números ainda não representam calibração das simulações de dez anos.

## Provas desta unidade

Testes com valores manuais cobrem: transformação com insumos limitados; trabalhadores
compartilhados/recrutados; instalação danificada; armazém cheio; consumo sem dupla
contagem; escassez e recuperação; transferência monetária conservativa; erro sem
mutação; equivalência entre execução contínua e retomada; rollback do fechamento.
Entregas e mercados têm suas provas em medieval-logistics.md. Pedágios, trânsito,
bloqueios, contrabando, consumo de outros bens e financiamento além de obras
próprias permanecem no plano.

Pagamentos avulsos exigem intenção explícita do proprietário da conta de origem:
`action=pay`, `actor_ref`, `source_id`, `target_id` e `amount`, sem campos extras.
O executor revalida a autorização `trade` atual antes de registrar o efeito; uma
decisão anterior não preserva um mandato revogado ou expirado. Titulares individuais
podem dispor de seus próprios recursos enquanto vivos. A mesma decisão não pode
ser reaplicada após save/load. Não há comando público de transferência: essa é uma
operação interna para os futuros fluxos financeiros, não intervenção do observador.

## Trabalho remunerado e imposto de renda

Instalações têm `payroll_account_id` do proprietário e `wage_per_worker` inteiro
positivo. São acordos de trabalho iniciais do conteúdo autoral, como as instalações
e reservas iniciais; não são decisões inventadas pela narrativa. Alterações futuras
de emprego/salário exigirão fluxos próprios de negociação e autoridade.

Antes de produzir, cada lote exige caixa para o salário bruto dos trabalhadores.
O limite `payroll_funds` participa do mínimo com insumos, mão de obra, integridade
e capacidade. Falta de autorização patronal `trade` limita produção a zero;
não vira exceção técnica nem trabalho não remunerado. Imposto a receber depois
não serve como crédito antecipado. Não há dívida, emissão ou saldo negativo.

Os trabalhadores efetivos são alocados por ID estável entre grupos da ocupação
e povoado, compartilhando disponibilidade entre instalações. Cada lote consome
trabalho e remunera exatamente essa quantidade. Personagens já pertencem aos
grupos; não ganham um segundo pagamento. Dependentes e trabalhadores não empregados
nessas instalações não recebem salário automático. Não é simulação individual
de mercado de trabalho, escolha de emprego ou custo de deslocamento.

Contas `household:<group_id>` pertencem a `population_group`. Começam zeradas,
conservando as76000unidades iniciais distribuídas entre tesouros. Pagamento bruto
debita empregador e credita grupos; o fato aponta para a produção que utilizou
seu trabalho. Grupos novos podem receber uma conta zerada quando são remunerados,
sem copiar patrimônio. Migração monetária, herança e liquidação de grupos ainda
precisam de executores: mover pessoas no owner populacional não move poupança.

`AuthorityState.tax_policies` registra política por governo e conta receptora,
separada do dinheiro em EconomyState. A taxa inicial é100/1000 (10%), aplicada
somente a cada salário bruto novo, com arredondamento inteiro para baixo por grupo
e por folha. O administrador atual do povoado precisa de mandato `taxation` vigente;
ocupação/reivindicação não basta. Sem mandato ou sem salário não há arrecadação,
e poupança acumulada não é tributada por esse fluxo.

`set_income_tax` exige decisão exata do governo (`action`, `actor_ref`, `polity_id`,
`income_rate`), taxa0..1000 e autoridade atual. Reaplicar uma decisão já executada
é recusado, inclusive após retomada. Alterar taxa produz um efeito de política,
não transferência monetária; arrecadação futura aponta para essa política e para
o pagamento. O simulador autônomo ainda não escolhe novas taxas: o executor está
disponível para os futuros planos fiscais, sem comando material do observador.

## Tarifa de exportação de origem

`TaxPolicy.export_rate_permille` é independente de `income_rate` e seu fato
canônico é `export_policy_event_id`, separado de `last_event_id`. Assim, uma
alteração de imposto de renda não invalida a cotação exportadora ainda publicada.
Só a administração do povoado do estoque de origem pode definir a tarifa. A oferta
e o relatório carregam metadados históricos da cotação - taxa, fato de política e
`export_collector_ref` - sem expor saldo, reserva ou outra informação privada da
jurisdição estrangeira.

A cotação é zero quando origem e destino têm a mesma administração. Frete entre
estoques do mesmo dono não é compra e não cobra esta tarifa, inclusive entre
administrações distintas. Para vendas entre administrações distintas, a abertura da ordem
bilateral cobra uma vez o preço-base mais a tarifa ad valorem arredondada: a base
vai ao vendedor e a tarifa ao tesouro da origem. Quando vendedor e coletor usam a
mesma conta, a soma dos deltas conserva o crédito líquido sem criar cobrança dupla.
Revalidação, reserva e entrega continuam no executor de mercado; a tarifa não cria
pedágio, regra de trânsito ou bloqueio.

## Alfândega civil material

`EconomyState.customs_checkpoints` registra um posto em `port` ou
`mountain_pass`. Ele só é ativo quando seu proprietário atual possui mandatos
`supply`, `trade` e `taxation`, o site está íntegro/habilitado/com serviço aberto
e a equipe local indicada recebeu salário no ciclo. Abrir o posto não cobra nem
retém bens; a folha consome dinheiro e força de trabalho reais.

Antes de partir, uma carga encontra o posto ativo e entra em `held`. Quantidade,
dono, rota e estoque de origem não mudam. O aviso privado permite apenas declarar
o manifesto canônico exato ou tentar evadir a taxa. A engine consome uma vaga de
inspeção da equipe paga e resolve a tentativa com RNG canônico salvo; se não for
detectada, a mesma parcela volta à fila no dia seguinte. Se declarada, a taxa exata
fica devida e o pagamento material a libera. Não há confisco, força militar,
alteração de rota, quantidade ou propriedade nesta vertical; rerroteamento fiscal ainda
não existe.

### Transição de equipe do checkpoint

Um checkpoint só produz demanda de trabalho `merchant` quando está materialmente
ativo, sua capacidade de inspeção paga foi realmente esgotada no dia e não há
merchant local plenamente disponível. A engine emite o `labor_shortfall` tipado
do próprio checkpoint e calcula demanda, oferta, `target_occupation`, quantidade
e estipêndio; nenhum desses termos vem da prosa ou do ator.

A oferta privada só alcança um grupo local de farmers totalmente disponível. A
decisão contém apenas os IDs atuais do aviso e da opção. Ao aceitar, Society
revalida caixa, autoridade, demanda e disponibilidade, paga o estipêndio e
reserva a fração por 30 dias. Depois, a resolução converte a fração em
`merchant` e a vincula como `staff_group` do checkpoint para payroll futuro.
Não há educação genérica, população, migração, autoaceite, UI/API ou outras
ocupações nessa V1.

## Desgaste por uso

Integridade continua sendo estado físico dono do Map. O ciclo medieval aplica
uma lei determinística de uso apenas a instalações com recibos canônicos de
produção ou de carga material acima do limiar definido pela engine; não existe
desgaste causado por clima, narrativa ou sorte. A redução é limitada a 0,01 de
integridade por janela de 30 dias e preserva a evidência dos recibos que a
causaram. O `SiteReport` produzido no mesmo ciclo torna a condição observável ao
mantenedor, mas não executa reparo nem reativa `enabled=false`: a recuperação
continua sendo um lote explícito de `repair_batch_decided`, com seus materiais,
salários e capacidade revalidados.

## Conveyance produtiva V1

Uma conveyance é uma decisão bilateral sobre um workshop já comissionado. O site
do mapa é a identidade física que permanece; o proprietário/mantenedor atual
apresenta uma opção transitória determinística, e uma contraparte elegível recebe
uma opção de aceitação reconstruída a partir dessa decisão. O executor canônico
recompõe a opção no dia atual e revalida owner, maintainer, autoridade `supply` e
`trade`, integridade, ausência de projeto ativo e os vínculos locais da instalação.

Ao concluir, somente o owner e o maintainer do site e os `stock_id` e
`payroll_account_id` da instalação são atualizados. O estoque, seu conteúdo, as
contas monetárias, projetos e demais recursos continuam pertencendo aos seus
donos; a operação tem preço zero nesta V1. Os eventos de proposta, aceitação e
execução preservam as decisões e suas causas, e as affordances não são persistidas.

Esse fluxo não introduz `PropertyTitle` nem um mercado imobiliário: não cobre
arrendamento, herança, captura militar, guerra, ocupação, transferência genérica
de patrimônio ou controles no observatório/UI. Ele existe apenas para provar a
mudança bilateral de controle de uma instalação produtiva real e seus vínculos
operacionais.

## Mobilidade produtiva V1

Uma limitação `labor` em recibo material de produção artesanal é a única base
para uma demanda local de transição. O engine limita a demanda a uma pessoa por
observação e calcula o estipêndio; não infere educação pela prosa. Ofertas são
privadas, datadas e destinadas a agricultores locais, no máximo 20% do grupo.
Elas não reservam pessoas nem moeda. Uma decisão corrente paga o estipêndio e
cria indisponibilidade por 30 dias; a resolução revalida fonte, autoridade,
contas e disponibilidade antes de mover a fração agregada para `artisan`.
Esta vertical não modela escola, aprendizagem individual, migração especializada,
aceitação autônoma ou IA real.

## Relatório fiscal de rota

`FiscalRouteReport` registra a observação datada de um posto civil pelo seu
operador e a posterior publicação física (`fiscal_route_bulletin`). Ele contém
apenas a identidade do checkpoint e a cotação válida naquele dia; não duplica
saldo, estoque ou capacidade do mapa. Ao iniciar uma carga, o comprador recebe
opções enumeradas para rotas conhecidas, incluindo uma rota legal sem posto com
taxa zero. O owner recompõe a opção e revalida o posto, o relatório e a rota
antes de criar a ordem. A escolha não altera ordens existentes, quantidade,
propriedade ou rota já contratada.

### Comprovantes de trabalho e limites históricos

`EconomyState.payrolls` guarda a última liquidação por instalação: data, trabalhadores
por grupo, salário unitário, bruto, imposto e evento de origem. É um comprovante,
não outra conta. A mesma instalação não produz/paga duas vezes na mesma data,
incluindo após save/load. Todos os efeitos continuam dentro do candidato do salto;
falha de save preserva estado, dinheiro, pessoas, RNG e histórico anteriores.

Prova preparada da fase produtiva isolada:20trabalhadores a2 custam40; imposto4
deixa36líquidos. Empregador público com50 termina14 antes do consumo. Com19 não
financia lote de20; com20 financia exatamente um. O smoke anterior, sem compras
domésticas, tinha3858eventos no dia180 e Valedouro sem caixa; é evidência histórica
das regras anteriores, não resultado esperado da circulação atual.

## Consumo doméstico e distribuição pública

O estoque público designado continua atendendo até uma ração por pessoa/mês.
Rações disponíveis são divididas proporcionalmente entre os grupos residentes:
quociente inteiro, maiores restos, empate por ID. Pessoas nomeadas já pertencem
ao grupo. Saldo maior não compra a parcela de alimento destinada a outro grupo.
Não se busca alimento em estoque privado ou distante por acesso onisciente.

A rotina do grupo decide comprar até sua parcela e seu saldo, à cotação local
vigente (a atualização de preços ocorre depois do consumo). O fornecedor decide
aceitar sua venda à mesma cotação, por conta própria e com mandato trade vigente.
Sem fornecedor autorizado, a rotina não cobra e mantém a distribuição pública.
O atendimento não comprado continua ajuda pública: essa regra inicial mantém a
subsistência preexistente, não pretende representar toda política medieval nem
uma escolha política universal. Políticas variáveis de provisão ainda estão no plano.

`buy_rations` exige decisões exatas e atuais `buy_rations`/`sell_rations`, com
actor_ref, group_id, stock_id, quantity, unit_price e seller_account_id. O executor
verifica grupo/local, proprietários das contas, cotação, caixa, estoque e mandato
atual do vendedor. Não concede mandato institucional ao grupo populacional.
Seu evento `household_purchase_completed` retira a comida consumida e transfere
moeda entre as contas, com causas para as duas decisões, saldo e cotação prévios.
Ambas as decisões recebem comprovante em payments; reutilização é recusada.

O fechamento `subsistence_resolved` retira somente o alimento da ajuda pública;
mostra total atendido, quantidade comprada, ajuda e falta. Aponta para os eventos
de compra. O último fechamento impede repetir consumo na mesma data, inclusive
após load. Todos os efeitos continuam no candidato transacional mensal.
Consumo foi introduzido no schema6/economy3, usando contas, eventos, payments e
proveniência existentes. O schema7 introduziu objetivos/relatórios por
recurso; schema8/economy4 acrescenta obras e catálogo, e Economy8 é o formato
corrente. Save exige os dois recibos de cada compra,
sem apagar arquivos antigos.

Provas preparadas:10moedas compram2rações a4 e deixam2; fornecedor recebe8.
Cinco rações para grupos480/480/960/480 são divididas1/1/2/1; riqueza não altera
a parcela. Sem alimento não há cobrança. No circuito local isolado, caixa50
paga40de salários, recebe4de imposto e36de vendas; termina50 e financia o próximo
mês. Na rodada natural seed73/180dias houve34pedidos,3984eventos salvos e retomada
181equivalente4006eventos; moeda76000 e alimentos conservados. Caixas dos governos:
Auren53500, Valedouro3988 e Escárlia2798. Isso não elimina falta de abastecimento,
nem prova calibração de dez anos. Investimento, produção distribuída, recuperação
de migração, políticas de provisão e trocas dos demais bens continuam necessários.

## Reposição produtiva por recurso

As instalações iniciais geram objetivos de insumos por estoque/recurso: madeira
da mina e madeira/ferro da oficina. `productive_demand` soma as entradas mensais
das receitas por capacidade nominal das instalações que compartilham o estoque.
O objetivo guarda horizonte de reserva, não inventário nem alvo material duplicado;
alvo é recalculado quando a capacidade muda. Produção continua limitada por mão de
obra, caixa, integridade, armazenamento e entradas realmente entregues.

Donos de estoques públicos ou instalações em operação divulgam excedentes por
boletim. Seus insumos são protegidos por dois meses de demanda nominal (ou pelo
horizonte do objetivo correspondente); saldo privado e inventário estrangeiro não
entram no contexto do comprador. Reposição alimentar tem prioridade sobre compras
produtivas na rotina inicial; não representa planejamento econômico ótimo.

Compra local também usa carga e entrega agendada, não crédito instantâneo de
estoque. Prova preparada:120ferro a12 custam1440, conta da oficina2000→560,
estoque vendedor500→380, destino0até entrega31→120. Retomada é equivalente.
No smoke histórico schema7/180,34remessas de alimento/11madeira/2ferro preservam moeda76000
e todos os recursos contabilizados. Mina termina produzindo60lotes; oficina possui
insumos mas caixa1 impede salários. Não há demanda suficiente por ferramentas:
projetos de expansão/investimento foram acrescentados na unidade abaixo.

## Expansão financiada (schema8/economy4)

EconomyState possui ExpansionBlueprint e ExpansionProject. Blueprint inicial:
10unidades de obra, máximo5por mês; cada unidade consome2madeiras/1ferramenta e
usa2artesãos pagos a2. Conclusão consome20madeiras/10ferramentas, paga40bruto e
acrescenta10lotes à capacidade nominal. Não cria trabalhadores, estoque ou moeda;
produção ampliada ainda exige insumos, caixa, site e demanda reais. Conteúdo salvo
é independente do catálogo instalado posteriormente.

Decisão exata do dono e mandatos supply/trade autorizam a obra; não alteram
capacidade. No fechamento mensal, construção precede produção e ambas partilham
disponibilidade por grupo. Renda/impostos usam settle_work, o mesmo executor da
produção. Recursos apenas prometidos não contam. Progresso, data, impedimento e
evento persistem; recibo material é exigido pelo save. Repetição não refaz trabalho.

Objetivos somam materiais restantes uma única vez à reserva operacional. Ofertas
preservam essa reserva. Preços locais incluem demanda de obras. Política inicial
de investimento é conservadora, não planejamento ótimo ou financiamento em escrow;
caixa pode ser gasto no abastecimento e interromper a obra depois de autorizada.

Prova preparada: ferramentas ausentes geram compra10da oficina, entrega31,
trabalho60/90e produção70lotes na mina. Outra prova divide1800artesãos:10na obra,
1790na produção (179lotes), sem dupla contagem. Populações rurais do preset não
têm artesãos; obra local pode ficar impedida. Migração/contratação especializada
ainda são necessárias para expansão distribuída.

Smoke natural seed73/dia180:2projetos, mina concluída60→70 e produz70, oficina5/10
impedida por caixa.45pedidos (34food/10wood/1iron),4590eventos salvos e continuação
181/4615equivalente;76000moedas e todos recursos auditados. Ferramentas iniciais
suprem obras nesse cenário, portanto ele não prova compra externa de ferramentas;
essa cadeia é coberta pelo cenário preparado, sem afirmar economia calibrada.

## Linhas industriais (schema10/economy6)

Novas linhas de carvão, aço e motores compartilham site, estoque, conta e trabalho,
mas não substituem a instalação original. Aplicação mecânica exige obra; operações
avançadas exigem conhecimento e insumos. O bombeamento consome motores ao construir
e carvão ao operar. Custos, receitas, cenário preparado e limitações naturais estão
em medieval-research.md. Metas produtivas incluem insumos das linhas novas.
Finanças distingue capacidade própria de capacidade da âncora e identifica os
produtos das linhas nas folhas salariais. Equipamentos militares, manutenção,
operadores especializados e economia calibrada continuam no plano integral.
