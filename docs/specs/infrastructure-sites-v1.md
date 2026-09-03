# Infrastructure Sites V1

## Objetivo

Transformar infraestrutura espacial relevante em entidade canônica navegável,
sem antecipar a logística profunda nem duplicar os donos de estado já
existentes.

O ciclo mínimo desta vertical é:

```text
mapa-fonte
  -> InfrastructureSite canônico
  -> save/load
  -> query pública e projeção no mapa
  -> mudança validada de condição
  -> Event + StateDelta + link causal
  -> capacidade operacional de rota derivada
  -> invalidação de domínio
```

## Dono canônico

`Map.infrastructure_sites` é o único registro dos sites espaciais. Cada site
possui ID estável, tipo extensível, nome, células explícitas, regiões, condição
física e referências por ID.

Os limites de propriedade são obrigatórios:

- `Route` continua dona de endpoints, capacidade, qualidade e habilitação de
  transporte;
- `CityState` e `UrbanAsset` continuam donos de serviços e ativos internos da
  cidade;
- `RegionalEconomyState` continua dona de estoque, produção, demanda e
  reservas;
- `GeographyLayer` continua dona de terreno, elevação e água;
- formações continuam em `Map.region_formations`;
- POIs continuam sendo entidades descobríveis como túmulos e tesouros.

Um site pode referenciar esses donos. Ele não copia nem altera o estado deles.

## Contrato

Um `InfrastructureSite` declara:

- `id`, `kind` e `name`;
- `cell_refs` e `region_ids`;
- `route_ids`, `water_body_ids` e `capability_ids`;
- `owner_ref` e `maintainer_ref` opcionais;
- `integrity`, `enabled` e `last_event_id`.

`kind` é vocabulário extensível, não uma enumeração fechada. A V1 autorada pode
usar pontes, portos, fazendas, minas, irrigação e santuários. Formação não é um
tipo de site nesta coleção.

O status público é derivado:

- `active`: habilitado e íntegro;
- `impaired`: desabilitado ou com integridade parcial;
- `destroyed`: integridade zero.

## Validação espacial

- IDs, células e referências internas não podem se repetir;
- toda célula deve estar dentro do mapa;
- regiões referenciadas devem existir e corresponder à pegada espacial do site;
- rotas referenciadas devem existir e conectar regiões declaradas pelo site;
- corpos d'água referenciados devem existir e tocar a localização declarada;
- integridade permanece no intervalo de zero a um.

Ausência de referência produz erro. O runtime não inventa rota, água ou região
a partir do texto do site.

## Mutação causal

`change_infrastructure_site_condition` é a fronteira material desta V1. Ela
recebe um site existente, uma nova condição validável e um evento-fonte.

A operação muda somente `integrity`, `enabled` e `last_event_id` do site. Ela
produz:

- `FactKind.STATE_TRANSITION`;
- `CausalOrigin.DETERMINISTIC`;
- um `StateDelta` por campo alterado, com
  `owner_kind=infrastructure_site`;
- link `TRIGGERED_BY` para o evento-fonte;
- `INFRASTRUCTURE_CHANGED` para cada região afetada;
- atualização da projeção enviada ao frontend.

Condições semânticas e interpreters podem observar a invalidação no futuro,
mas esta operação não aplica qualquer consequência em cascata por conta
própria.

## Dependência operacional de rota

Quando um site referencia uma rota por `route_ids`, ele declara uma dependência
física real, não uma associação narrativa. `Route.capacity` continua sendo a
capacidade nominal da conexão e `Route.quality` continua pertencendo à rota.

A capacidade utilizável é derivada deterministicamente:

```text
fator do site = integrity, quando enabled
fator do site = 0, quando disabled

fator da rota = menor fator entre os sites ligados, ou 1 sem dependências

capacidade operacional = capacity * quality * fator da rota
```

O menor fator representa o gargalo de uma sequência física. A projeção não
copia condição para a rota e não altera sua capacidade nominal. Uma mudança
real na capacidade operacional produz evento e `StateDelta` próprios da rota,
ligados causalmente ao evento que mudou o site, e invalida as regiões dos
endpoints.

O fluxo econômico existente consome essa capacidade operacional para limitar
uma transferência. Ele registra os sites e eventos materiais que fundamentaram
o limite, mas continua sendo o único dono da mudança de estoque. Não há reserva
de throughput, congestionamento, cadeia de suprimentos ou escolha multimodal
nesta vertical.

## Capacidade operacional observável

Uma região pode expor a chave dinâmica
`CAPACITY(region, capability, kind=infrastructure_site)` quando ao menos um
site canônico na região declara aquela `capability`. A unidade é
`site_equivalents`: cada site habilitado contribui com sua integridade e cada
site desabilitado contribui com zero.

A leitura é derivada, determinística e inclui referências para os sites que a
fundamentam e seus últimos eventos materiais. Uma capacidade sem site
correspondente permanece `unknown`; a engine não inventa um zero mensurável.

Essa métrica mede presença operacional comparável. Ela não representa tamanho,
produção, throughput, estoque, serviço urbano nem efeito econômico. Outros
donos de domínio podem consumi-la futuramente como evidência, mas somente eles
podem calcular e aplicar seus próprios resultados materiais.

A leitura entra no contexto semântico de qualquer região consultada e, por essa
via, no contexto de atores que observam a região. Definições regionais já
aceitas são avaliadas automaticamente em `CityRegion`, `NormalRegion` e
`CultivateRegion`; uma leitura `unknown` não cria condição nem conta como
reutilização da definição.

A capacidade mensurável de um site também pode originar descoberta semântica
em `NormalRegion` ou `CultivateRegion`. A seleção usa a superfície dinâmica
real, deduplica regiões equivalentes e respeita budget e cooldown; a proposta
continua observacional e só entra no registry após validação determinística.
O fallback de test mode produz uma leitura operacional limitada a `[0, 1]`
sem chamar provider real.

Descobrir ou avaliar uma definição em região não urbana pode produzir uma
condição e seu evento causal, mas não autoriza intérpretes de cidade, população
ou governo. Organização só pode reagir pela política regional já existente,
quando a condição for uma adversidade mecânica elegível e houver membro
presente. A capacidade operacional simples de um site não é, por si só, uma
adversidade.

## Persistência e transação

O mapa-fonte schema v6 e o snapshot schema v5 persistem a coleção. Apenas IDs
atravessam referências entre donos. Como os sites fazem parte do grafo
canônico do `World`, o checkpoint mensal restaura condição e fila de projeção
quando o mês falha; eventos e deltas seguem o commit atômico existente.

## Projeção pública

`/api/v1/query/world/map` expõe a coleção em ordem estável. A posição do
marcador usa a primeira célula declarada; isso é uma âncora de visualização,
não uma nova geografia.

O frontend mantém uma camada Pixi separada de terreno, landmarks e POIs. O
marcador reflete o status, aceita seleção e abre o detalhe `type=site`. Updates
mensais atualizam a projeção sem transferir autoridade ao cliente. A fila só é
confirmada depois de um broadcast bem-sucedido; falha de envio conserva o
update para a tentativa seguinte. O último evento material aparece como fonte
navegável no detalhe e abre a consulta causal “Por quê?”.

Rotas expõem `operational_capacity` e `dependency_site_ids` como projeções do
mapa. Quando um site ligado muda, o mesmo tick atualiza a rota afetada e o Pixi
redesenha sua intensidade a partir da razão entre capacidade operacional e
capacidade nominal utilizável. O frontend valida que a relação site-rota seja
bidirecionalmente consistente, mas não recalcula a capacidade.

No editor de presets, rotas e `route_ids` são autoria explícita. Uma rota declara
seus dois endpoints e propriedades próprias; um site só pode referenciá-la se
esses endpoints pertencerem às regiões declaradas pelo site. Nenhum vínculo é
inferido. O preset `classic` exercita o contrato com a Ponte do Tianhe Central:
sua célula toca o rio canônico e ela referencia explicitamente a rota
`classic-301-405`.

O detalhe `type=route` expõe capacidades nominal e operacional, endpoints,
recursos permitidos, sites dependentes e eventos materiais provenientes desses
sites. Site e rota são navegáveis nos dois sentidos, e os eventos abrem o fluxo
causal “Por quê?”.

## Fora da V1

- impacto direto do site sobre preço, estoque, produção ou população;
- throughput compartilhado, congestionamento ou capacidade reservada;
- cadeia de suprimentos e escolha de rotas alternativas;
- dano por guerra ou personagem; clima pode afetar integridade somente pela
  exposição espacial e proposta validada descritas em `climate-hydrology-v1.md`;
- agente de logística;
- construção, demolição ou captura de sites;
- geometria detalhada de estrada célula a célula.

Essas capacidades só entram em verticais posteriores, consumindo o site
canônico e seus vínculos em vez de criar registradores paralelos.
