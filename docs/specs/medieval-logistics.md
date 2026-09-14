# Circulação material e mercados

Detalhamento executável da etapa2 aprovada. `EconomyState` continua o único owner
material. `FreightOrder` guarda intenção, quantidade contratada e total entregue;
`CargoParcel` guarda a quantidade física ainda fora de armazéns. A soma das cargas
ativas mais o entregue deve igualar a quantidade da ordem. O total entregue é
histórico, não estoque adicional. Os itens saem do estoque na abertura da ordem.

Percursos são sequências de IDs de `Map.routes`, contíguas entre origem e destino,
sem ciclos. Não existe rede paralela. Cada trecho usa a escala de deslocamento já
existente: 10km/célula, 20km/dia por estrada, 40km/dia por rio, ajustada pela qualidade.
Capacidade operacional é carga despachada por dia, compartilhada nos dois sentidos;
ela não limita quantos viajantes individuais existem. Campanhas/cargas futuras
devem consumir este mesmo registro de vazão para materiais.

Ordens entram na agenda para o dia seguinte. Cargas são despachadas em ordem de
criação, divididas se excederem a vazão disponível. Passagem entre trechos espera
ao menos um dia para novo despacho. Fechamento, destruição ou restrição impedem
passagem; tentativa seguinte ocorre no próximo dia. Armazém cheio descarrega só
o que couber e mantém o restante no destino, sem perder ou duplicar bens. Entregas
datadas precedem produção/consumo quando coincidem com fechamento mensal.

Transferência interna requer decisão do dono de ambos os estoques. Comércio exige
decisões independentes de comprador/vendedor para os mesmos parâmetros. Nesta
unidade, a compra é à vista antecipada: dinheiro passa ao vendedor e propriedade
da carga ao comprador na aceitação; atraso não desfaz unilateralmente a venda.
Os parâmetros são conferidos contra preço atual, saldo, dono e quantidade, com
antirreplay. Autoridade pública/negociação permanece na etapa3 e no runtime único;
estes são executores internos, não comandos de intervenção do observador.

Preço por recurso/povoado é atualizado mensalmente pela disponibilidade local e
demanda (rações e insumos produtivos). Alvo limitado a 1/4–4 vezes preço base;
movimento mensal limitado a 10% arredondado para cima, mínimo uma unidade. Preço
não transfere recursos. Catálogo e preços persistem no save, agora schema3.

Provas: conservação estoque+carga, divisão por capacidade, dois sentidos, múltiplos
trechos, bloqueio/desbloqueio, descarga parcial, save/load em trânsito, erro sem
publicação parcial, dinheiro conservativo, consentimento bilateral e antirreplay,
preços limitados. Ainda faltam tarifas, contrabando, consumo monetário e compradores
autônomos e negociação de obrigações; esta unidade não encerra A2.

## Recuperação de frete bloqueado

`src/sim/medieval/freight_recovery.py` nunca reescreve, reroteia ou reexecuta a
`FreightOrder` original: rotas, quantidade, decisões e recibos permanecem
imutáveis para sempre. Enquanto a carga fica retida numa passagem sem
capacidade, o dono pode reconstruir apenas duas opções a partir do que sabe
agora: `wait` (aguardar) ou `successor` (abrir uma remessa nova por outra rota
fiscal válida). Essas opções são transitórias e enumeradas pelo engine a cada
chamada — nunca persistidas; a decisão do ator só nomeia o ID de uma opção
(`FreightRecoveryOption.decision()`), nunca inventa destino, recurso ou
quantidade.

Por ora, somente uma transferência interna não paga e ainda não entregue é
recuperável (dono da ordem, do estoque de origem e do de destino coincidem, e
nenhuma decisão da ordem está em `economy.payments`). Uma compra bilateral
bloqueada não é recuperável por este módulo: ela exige uma decisão bilateral
futura própria e não é rerroteada aqui — recuperar uma compra pertence a uma
vertical própria descrita abaixo.

Escolher `successor` retira estoque novo (nunca do pedido bloqueado) e abre uma
`FreightOrder` própria, com vínculos causais explícitos para a decisão e para o
último evento da ordem bloqueada; não há restituição nem duplo pagamento sobre
a ordem original, que continua com sua quantidade/entregue/decisões intactas.
Escolher `wait` não move nada material; a única mudança é o registro da própria
decisão. Não há rotina automática de recuperação, força, confisco ou bloqueio
militar nesta vertical — apenas o dono decide, e só entre as opções acima.

## Recuperação bilateral de compra pré-paga

`src/sim/medieval/purchase_recovery.py` cobre, na V1, somente uma compra já
paga, sem tarifa, sem entrega parcial e com o frete integralmente bloqueado. O
comprador solicita uma rota fiscal alternativa por opção transitória; o vendedor
recebe opções para aceitar ou recusar aquela solicitação em decisão independente.
Não há despachante de affordances, automaticidade, UI ou API pública para abrir
o caso, e os atores só podem selecionar opções enumeradas pelo engine.

A ordem, o pagamento, o recibo de venda e a carga originais são história
imutável: não são reescritos, rerroteados, reexecutados, reembolsados nem
tarifados novamente. Ao aceitar, o vendedor precisa ter estoque novo e espaço
para receber a carga pendente; a parcela original é explicitamente retirada do
trânsito e devolvida ao estoque do vendedor, enquanto a ordem sucessora é aberta
com estoque novo e sem novo pagamento. A resolução registra deltas e vínculos
causais para as decisões, o pagamento, a abertura original e os bloqueios.
Recusar apenas fecha o caso e não move bens ou dinheiro. Não há entrega parcial,
refund, tarifa ou recuperação unilateral nesta V1.
