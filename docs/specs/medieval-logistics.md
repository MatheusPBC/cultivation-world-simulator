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
