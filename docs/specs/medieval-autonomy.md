# Autoridade, informação e abastecimento autônomo

Primeira política institucional executável das etapas2/3. Não equivale a toda a
estratégia/diplomacia do plano nem à integração de LLM.

## Owners e autorização

`MedievalWorld.authority`, `.knowledge` e `.strategy` são objetos separados da
sociedade e da economia. Modelos/validação/serialização vivem em
`src/classes/governance`; execução em `src/sim/medieval`.

AuthorityOffice registra instituição, titular, escopos e vigência em dias.
`can_actor_act_for` consulta cargos atuais: títulos/riqueza não autorizam.
O corpo administrativo da própria instituição pode ser titular coletivo;
nenhum personagem fictício é criado para completar cargos quando count=1.
Um titular pessoal morto não autoriza a instituição. Sucessão e reivindicações
concorrentes ainda precisam de operações próprias; alterar registros de teste
não é uma opção pública do observador.

Compra e remessa interna revalidam autorização antes do executor material.
As instituições falam como EntityRef próprio, com cargo/titular como fundamento
da autorização. Não há concessão de controle territorial por ocupar um cargo.
Os modelos herdados dependentes de Avatar, dinastia e datas mensais não são um
segundo runtime medieval. Os novos valores usam dias explicitamente.

## Informação limitada por canal

KnowledgeReport é observação datada, não estoque/conta duplicados ou reservados.
`refresh_reports` entrega inventário administrativo ao dono e publica somente
excedentes por recurso dos estoques públicos e de instalações produtivas. Boletins
comerciais alcançam governos e organizações com objetivos daquele recurso em
locais conectados por rotas abertas. Inventários ficam com seus donos; estoques
privados sem instalação ativa e saldos alheios não são divulgados. Canal mensal
abstraído, sem tempo de
mensageiro nesta unidade. Isto não autoriza compartilhar todo o histórico.

Ofertas têm quantidade anunciada, preço, data e evento. Publicar zero retrai a
oferta conectada; observações com 30dias ou mais não orientam novas compras.
Planejador não vê excedente estrangeiro surgido após o relatório. O executor
usa a verdade atual para validar, nunca para atribuí-la retrospectivamente ao ator.
Segredos, crenças, relatos falsos, espionagem e redes de comunicação com atraso
permanecem pendentes; a observação pública do jogador continua onisciente.

## Intenções, contraparte e execução

Cada governo começa com objetivos recorrentes de manter dois meses de alimento
em seus povoados. Três objetivos adicionais repõem insumos das instalações
existentes (madeira na mina, madeira/ferro na oficina). Objetivo nomeia estoque,
recurso, finalidade e horizonte; alvo deriva das pessoas ou das entradas/capacidades
produtivas atuais. Objetivo guarda motivação, alvo e critério; plano guarda etapa,
impedimento e referências de pedidos. Não armazena estoques nem affordances.

Após produção/consumo/preços mensais: coletar relatórios, reavaliar cada objetivo,
contabilizar pedidos ainda pendentes e escolher suprimento conhecido. Remessas
internas precedem compras; ofertas externas são ordenadas por preço e extensão
do caminho. `supply_path` deriva o caminho de menor duração em Map.routes, sem
manter outra rede, respeitando permissão e carga unitária do recurso. Alimentação
precede insumos; dentro da finalidade a prioridade é determinística por ID nesta
política; justiça distributiva, prioridade emergencial e negociação política
não estão calibradas.

O comprador registra intenção. `consider_sale` decide independentemente segundo
autoridade, cotação atual e preservação da reserva alimentar/produtiva local. Pode recusar. Aceite
leva ao executor de compra já existente: caixa e carga física publicados juntos,
entrega posterior com filas/capacidade/distância. Não há gratuidade estrangeira,
crédito invisível ou reposição de dinheiro. Recusa entra como causa do plano
impedido; caixa, estoque, relatório e compra conservam seus vínculos próprios.

Planos aguardam carga; promessa não satisfaz reserva. Recebimentos podem mudar
etapa sem nova chamada estratégica diária. No mês seguinte o objetivo é revisto,
inclusive quando há pedidos atrasados. Roteamento de novas ordens considera
alternativas abertas; redirecionar carga já contratada não foi implementado.
Falha técnica de execução/save aborta o salto inteiro, não vira recusa do vendedor.

## Persistência e observação

Schema8 inclui alvos/relatórios por recurso e projetos econômicos. Schemas1–7 experimentais são preservados e
rejeitados, sem migração silenciosa. Load confere identidades, referências,
proveniência e canais; retomada mantém observações/intenções/pedidos/RNG.

`query/governance` e `query/observatory.governance` projetam cargos, objetivos,
planos, políticas tributárias e relatórios. ObjectiveView deriva target_quantity.
Painel Abastecimento identifica recurso/unidade/finalidade/estoque e distingue reserva desejada, estoque,
carga pendente, etapa, impedimento, data da avaliação e boletins conhecidos.
Ver causa navega para os eventos canônicos. Nenhum novo comando material público.

## Evidência e limites

`tests/test_medieval_autonomy.py` cobre autorização revogada/morte, informação
privada/sem divulgação, reserva do vendedor, falta de dinheiro, caminho alternativo,
referências inválidas, rollback de todos os owners e retomada da execução natural.
Testes HTTP cobrem consulta e ano medido por dias, não por número de saltos.

```powershell
$env:CWS_DATA_DIR = Join-Path (Get-Location) '.test-data'
.\.venv\Scripts\python.exe tools/medieval_autonomy_smoke.py --days 180 --output .test-data/autonomous-proof/world.mws
```

Seed73/dia180 anterior (schema7) demonstrou conservação de todos recursos,47pedidos
(34alimento/11madeira/2ferro) e retomada equivalente. Algumas
cidades perderam saúde: capacidade conjunta das saídas de Campomanso é menor que
a demanda externa mensal. Consumo doméstico já devolve renda aos fornecedores,
mas a oficina esgota caixa sem demanda por ferramentas. Não corrigir isso injetando
bens/moedas. Faltam produção distribuída, investimentos mais amplos, demanda multissetorial mais
ampla, demografia e negociações condicionais.
Salários produtivos e imposto sobre essa renda já executam com limites de caixa;
o painel Finanças permite inspecionar folhas. Novas taxas ainda não são escolhidas
pela política autônoma, embora o executor validado exista.

A rotina atual de investimento usa operações próprias: instalação produzindo no
limite, saída abaixo da reserva de dois meses, trabalhadores para nova capacidade,
artesãos, site íntegro e orçamento estimado de materiais/salários mais dois meses
de folha operacional. Não usa estoques privados estrangeiros. Estimativa não é
escrow nem garantia; concorrência por dinheiro/materiais pode impedir a obra.
Projetos ativos acrescentam demanda restante de madeira/ferramentas aos objetivos,
sem duplicação com insumos regulares. No schema8/seed73/dia180, mina ampliada60→70,
oficina5/10bloqueada por caixa;45pedidos e conservação/retomada verificadas.

Teste anual HTTP com autosave levou vários minutos. O custo de copiar/validar/
reescrever histórico em cada salto cresce; há medição opcional --profile no
smoke. Otimização com prova de rollback/imutabilidade é necessária antes das
três seeds de dez anos. A1 permanece funcional; A2–A9 não estão encerrados.
