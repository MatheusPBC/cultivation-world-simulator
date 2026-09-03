# Clima e hidrologia V1

## Objetivo

Adicionar clima físico mensal e observações hidrológicas regionais ao mapa
causal sem roteirizar enchentes nem dar às métricas autoridade para alterar o
mundo.

```text
Geografia física estática
        +
Clima regional do mês
        +
Infraestrutura hídrica real
        ↓
Projeção hidrológica read-only
        ↓
MetricReadings grounded
        ↓
Descoberta e condições semânticas existentes
```

## Propriedade do estado

`World.climate_state` é a única dona do clima físico dinâmico. Para cada região,
ela guarda a precipitação e a saturação do solo do mês atual, a saturação
anterior e o evento-fonte. O estado é serializável e participa do checkpoint e
rollback normais do mês junto com o restante de `World`.

`Map.geography` continua sendo a única dona de terreno, elevação e corpos
d'água. Infraestruturas de manejo de água continuam pertencendo a
`Map.infrastructure_sites`. Nenhum desses dados é copiado para o estado
climático.

## Atualização mensal

A fase `update_regional_climate` roda uma vez por mês antes da avaliação
semântica. Ela calcula deterministicamente cada leitura a partir do
`playthrough_id`, mês, pegada regional e geografia física. A precipitação e a
saturação ficam sempre no intervalo `0..1`; a saturação do mês anterior
participa do cálculo seguinte.

A atualização produz um único `Event` público agregado, com `StateDelta`s por
região e invalidações mecânicas `CLIMATE_CHANGED`. Reexecutar a fase no mesmo
mês não produz outro evento. O cálculo não altera população, economia, rotas,
sites, terreno ou qualquer condição semântica diretamente.

## Projeção hidrológica

`RegionalHydrologyProjection` é uma leitura transitória. Ela combina:

- precipitação e saturação canônicas do mês;
- drenagem associada aos terrenos físicos da pegada regional;
- variação de elevação;
- rios, lagos e mares que tocam a região; e
- sites ativos com capacidades `water_management`, `drainage` ou
  `flood_control`.

Sem clima canônico para a região no mês atual, a projeção não existe. Ela nunca
grava números no mapa ou na região.

## Linguagem mecânica

A projeção expõe quatro perguntas mensuráveis, todas em `ratio`:

- `LOAD(region, precipitation, kind=regional_climate)`;
- `LOAD(region, soil_water, kind=regional_climate)`;
- `CAPACITY(region, drainage, kind=regional_hydrology)`;
- `RISK(region, flooding, kind=regional_hydrology)`.

Precipitação e água do solo são leituras exatas do estado climático. Drenagem e
risco de inundação são derivados da combinação grounded. Todas carregam
referências de estado e o evento climático ou de infraestrutura que as
sustenta.

`RISK(..., flooding)` não significa que houve uma inundação. Ele pode ser
usado por descoberta semântica e por futuros interpreters, mas somente um
domain owner com affordance validada poderá produzir dano, deslocamento,
fechamento de rota ou qualquer outra mutação material.

## Ocorrência regional de enchente

`World.regional_flood_state` é o dono das enchentes físicas ativas e das
janelas de persistência usadas para ativá-las ou resolvê-las. O sistema roda
depois do clima e da projeção hidrológica:

- risco de inundação `>= 0.72` por dois meses consecutivos ativa uma ocorrência;
- risco `<= 0.45` por dois meses consecutivos resolve a ocorrência;
- leitura ausente quebra a janela, mas nunca é tratada como risco baixo;
- saltar um mês também quebra as janelas, pois elas exigem observações
  consecutivas;
- somente começo e resolução produzem evento, delta e invalidação; a presença
  continuada não gera spam mensal.

Cada transição aponta para os eventos climáticos e de infraestrutura que
fundamentaram as leituras. A ocorrência entra no contexto regional, de Avatar e
de Seita como perigo material ativo. A ocorrência não altera outro domínio
diretamente. Uma etapa genérica posterior calcula `HazardExposure` para sites
espaciais reais e produz `HazardImpactProposal`s tipadas. Antes de aceitar uma
proposta, a engine recalcula exposição e magnitude; somente então o dono
`Map.infrastructure_sites` pode reduzir a integridade de um site através de sua
operação existente.

Na integração inicial, uma enchente recém-iniciada pode afetar apenas sites da
região cuja posição, elevação e proximidade das células de água produzam
exposição suficiente. Capacidades declaradas como `water_management`,
`drainage` e `flood_control` reduzem essa exposição. O impacto cria seu próprio
evento, delta e link para a ocorrência. Não existe escolha por nome de cidade,
tipo narrativo de site ou número inventado pela IA.

## Fora da V1

- nível e vazão dinâmica de rios;
- propagação de água entre células ou regiões;
- erosão, seca, tempestades nomeadas e previsão;
- alteração automática de produção, saúde, população ou rotas; infraestrutura
  só pode perder integridade pelo contrato genérico de exposição validada;
- `CityInterpreter` ou `PopulationInterpreter` reagindo ao risco hidrológico.

Essas próximas verticais deverão consumir o estado e as métricas desta V1, sem
reimplementar clima ou inferir consequências por nome de cidade.
