# Geografia física V1

## Objetivo

Transformar o mapa region-first em substrato espacial grounded sem introduzir
simulação célula a célula. Uma célula pode pertencer a uma região e, ao mesmo
tempo, ter terreno físico, elevação e água independentes.

## Propriedade do estado

```text
Map
├── GeographyLayer       verdade física estática
├── Region footprints    território semântico
├── Routes               conexões explícitas entre regiões
├── InfrastructureSites  entidades espaciais separadas da geografia
├── landmarks            âncoras de apresentação
└── runtime overlays     somente projeções
```

`GeographyLayer` é a única dona do terreno base, da elevação e da geometria dos
corpos d'água. `Region` não copia esses valores. Cidade, seita, ruína ou caverna
é um site que ocupa um terreno; nunca é um tipo de terreno.

`Route` continua sendo a única conexão autoritativa entre regiões. A geografia
pode explicar ou validar uma rota proposta, mas adjacência e coordenadas nunca
criam uma rota implicitamente.

## Source schema v6

A fonte oficial permanece em
`static/game_configs/maps/<map_id>/map.json`. Ela contém uma matriz semântica e
uma camada física independente:

```json
{
  "schema_version": 6,
  "id": "classic",
  "version": 3,
  "width": 84,
  "height": 60,
  "geography": {
    "terrain_rows": [["water"]],
    "elevation_rows": [[120.0]],
    "water_bodies": [
      {
        "id": "tianhe",
        "kind": "river",
        "cell_refs": [[0, 0]],
        "navigable": true,
        "region_id": 106,
        "flow_direction": [1, 0]
      }
    ]
  },
  "region_rows": [[106]],
  "routes": [],
  "landmarks": {},
  "region_overrides": {}
}
```

As matrizes possuem exatamente `height` linhas e `width` colunas. Elevação é um
número finito em metros no intervalo `[-12000, 10000]`. Terreno usa valores
físicos de `TileType`; `city`, `sect`, `cave` e `ruin` são inválidos porque são
sites.

`wilderness_tile` e derivação de terreno por região foram removidos do contrato.
Uma célula com `region_rows[y][x] == -1` continua significando espaço sem região
ou sem interação, mas seu terreno vem de `geography.terrain_rows[y][x]` como em
qualquer outra célula.

## Corpos d'água

Um corpo d'água é um rio, lago ou mar estável, com células explícitas dentro do
mapa. Ele pode referenciar a região que o representa semanticamente. Rios exigem
direção cardinal ou diagonal não nula; lagos e mares não possuem direção.

A presença da água não cria sozinha chuva, inundação, navegação, comércio ou
dano. Clima e risco hidrológico agora combinam esta geografia com estado
grounded conforme `climate-hydrology-v1.md`; consequências materiais continuam
dependendo de ações validadas pelo dono do domínio.

## Consultas espaciais determinísticas

O runtime expõe terreno e elevação por coordenada, corpos d'água por célula ou
região, regiões vizinhas pela fronteira de suas pegadas e relações
upstream/downstream entre regiões que compartilham inequivocamente um rio.

As consultas retornam vazio ou `None` quando não há evidência. Elas não inferem
rio por texto, rota por adjacência nem risco por baixa elevação.

## Persistência e transações

O snapshot guarda a `GeographyLayer` completa. O estado mutável de rotas continua
na persistência canônica de rotas. Save/load deve preservar exatamente terreno,
elevação, identidades das águas, pegadas regionais e resultados das consultas.

Geografia física é estática na V1, portanto o rollback mensal não ganha um novo
dono mutável. Qualquer mutação futura de terreno ou água deverá participar da
transação completa do mês com `Event`, `StateDelta` e links causais.

## Exclusões explícitas

- nível e vazão dinâmica dos rios; a ocorrência material de inundação pertence
  à vertical posterior descrita em `climate-hydrology-v1.md`;
- erosão e fluidos;
- pontes, portos, estradas ou fazendas como entidades dentro da
  `GeographyLayer`; sites espaciais adicionados depois pertencem ao registro
  canônico separado descrito em `infrastructure-sites-v1.md`;
- geometria e throughput compartilhado de rotas;
- fields dinâmicos de Qi/Yin;
- overlays dinâmicos políticos, comerciais, migratórios, bélicos ou de risco;
- geração procedural de mapas.

Essas capacidades serão construídas sobre este substrato, em novas verticais,
sem virar campos narrativos dentro da geografia V1.

Terreno, elevação, água, fronteiras e rotas já podem ser projetados visualmente.
Essas projeções leem a query pública descrita em
`docs/specs/region-first-map-system.md`; não pertencem à `GeographyLayer` e não
ganham autoridade mecânica.
