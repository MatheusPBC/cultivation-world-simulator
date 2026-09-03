# Sistema de mapa regional com geografia física

Status: geografia física e projeções visuais V1 implementadas.

Este documento descreve como o mapa organiza espaço, regiões e conexões. O
contrato detalhado das primitivas físicas está em
`docs/specs/physical-geography-v1.md`; a decisão arquitetural está em
`docs/adr/0003-separate-physical-geography-from-regions.md`.

## Objetivo

O mapa deve explicar relações causais espaciais sem simular cada objeto do
mundo. Ele usa regiões como unidade principal da simulação e uma grade física
coarse-grained para responder perguntas como:

- qual terreno existe sob uma região;
- qual é a elevação local;
- quais rios, lagos ou mares atravessam ou tocam uma região;
- quais regiões são vizinhas na malha;
- quais conexões explícitas permitem transporte e fluxo.

Geografia informa possibilidades. Ela não cria enchentes, escassez, migração ou
qualquer outra consequência por conta própria.

## Camadas

```text
Map
├── GeographyLayer
│   ├── terrain_rows
│   ├── elevation_rows
│   └── water_bodies
├── region_rows / Region footprints
├── routes
├── landmarks
└── region_overrides
```

### Geografia física

É verdade estática pertencente ao `Map`:

- `terrain_rows`: terreno físico por célula;
- `elevation_rows`: altitude em metros por célula;
- `water_bodies`: corpos d'água identificáveis, com células explícitas.

Um terreno nunca representa cidade, seita, caverna ou ruína. Esses conceitos
são sites ou regiões semânticas sobrepostos à geografia.

### Regiões

`region_rows` mantém a pegada territorial de cada `Region`. Uma região pode
cobrir vários terrenos físicos, e o mesmo terreno pode aparecer em regiões
diferentes. O valor `-1` significa apenas “sem região”, não “planície” nem
“mar”.

Regiões continuam sendo a unidade de clique, detalhe e grande parte da
simulação agregada. A fronteira regional não altera a geografia sob ela.

### Rotas

`Map.routes` é o registro explícito de conexões entre regiões. Cada `Route`
mantém identidade, endpoints, modo, capacidade, qualidade, disponibilidade e
restrições de recurso. Adjacência na grade é uma consulta geográfica, não uma
rota implícita.

Quando um `InfrastructureSite` referencia uma rota, sua condição participa da
capacidade operacional derivada da conexão. A rota preserva a capacidade
nominal; o menor fator entre os sites ligados funciona como gargalo físico. A
mudança é registrada causalmente antes de qualquer domínio consumidor decidir
ou aplicar uma consequência própria.

### Landmarks e overrides

Landmarks são âncoras visuais de cidades, seitas e outros pontos importantes.
Não fornecem capacidades mecânicas. `region_overrides` aplica textos específicos
do preset e deve sobreviver ao save/load.

## Fonte oficial schema v6

```json
{
  "schema_version": 6,
  "id": "classic",
  "version": 3,
  "width": 84,
  "height": 60,
  "region_rows": [[-1, 101]],
  "geography": {
    "terrain_rows": [["sea", "plain"]],
    "elevation_rows": [[-20, 120]],
    "water_bodies": [
      {
        "id": "eastern-sea",
        "kind": "sea",
        "cell_refs": [[0, 0]],
        "navigable": true
      }
    ]
  },
  "landmarks": {},
  "region_overrides": {},
  "routes": []
}
```

As três matrizes devem ter exatamente `width × height`. Elevação aceita valores
entre -12.000 e 10.000 metros. Corpos d'água precisam de IDs únicos, células
dentro do mapa e terreno compatível; rios também exigem uma direção não nula.

Não existe parser compatível com schemas anteriores. Os campos
`wilderness_tile` e `region_tile_overrides` são inválidos.

## Runtime

O loader segue esta ordem:

1. valida o source v5;
2. cria `GeographyLayer`;
3. cria os tiles visuais a partir de `terrain_rows`;
4. cria e associa regiões usando `region_rows`;
5. instala landmarks, overrides e rotas;
6. mantém a fonte normalizada para consultas e ferramentas.

Todo `Map` nasce com uma geografia física mínima coerente, usada por mundos
unitários ou de teste. Um preset oficial a substitui imediatamente pela
geografia autoral validada.

Consultas disponíveis na V1:

- terreno e elevação por célula;
- corpos d'água por célula;
- corpos d'água que intersectam ou tocam uma região;
- regiões vizinhas por aresta ortogonal;
- relação upstream/downstream quando duas regiões compartilham inequivocamente
  o mesmo rio.

## Persistência

O snapshot do mapa usa schema v4 e salva:

- ID, nome e versão do preset;
- dimensões;
- `region_rows` atuais;
- terreno, elevação e águas;
- landmarks e overrides.

Rotas possuem estado mutável e continuam sendo persistidas na seção canônica do
mundo. O carregamento recompõe o mapa sem consultar novamente o preset em disco.
Assim, um save preserva exatamente a geografia da campanha.

## API, editor e previews

A query pública do mapa usa terreno físico em `data` e expõe uma estrutura
`geography` com elevação e águas. Ela também entrega, como campos obrigatórios:

- `territory_rows`, projeção serializada de `Map.region_cors`;
- `routes`, projeção em ordem estável do registro `Map.routes`.

O frontend normaliza essas estruturas em tipos fortes e não aceita o contrato
anterior incompleto.

### Projeções visuais V1

O mapa possui controles PT-BR para alternar terreno, elevação, corpos d'água,
fronteiras regionais, rotas, territórios de seitas, presença institucional e
nomes. Terreno, água, fronteiras, rotas, seitas, presença institucional e nomes
iniciam visíveis; elevação inicia desligada.

Cada camada continua sendo apenas uma leitura de seu dono canônico:

- elevação colore deterministicamente `geography.elevation_rows`;
- hidrografia destaca somente células de `geography.water_bodies` e usa a
  direção explícita dos rios;
- fronteiras são calculadas de `territory_rows`;
- rotas ligam as âncoras de seus dois endpoints e usam modo, qualidade, estado e
  capacidade operacional derivada apenas no estilo;
- seitas continuam consumindo a projeção territorial já fornecida pelo domínio
  de organizações.
- presença institucional combina somente, como leitura, a governança canônica
  das cidades e a influência espacial derivada das seitas; ela não declara
  soberania nem possui estado próprio. O contrato completo está em
  `regional-institutional-presence-v1.md`.

A linha de uma rota é topológica: prova que duas regiões estão conectadas, mas
não afirma por quais células uma estrada, ferry ou passagem percorre. Nenhum
toggle e nenhum renderer modifica o mundo.

O editor lê e salva schema v6, preserva elevação, águas, rotas, sites e metadados
e não deriva terreno de região. O painel de rotas cria e edita IDs, endpoints,
modo, capacidade nominal, qualidade, habilitação e recursos permitidos. O
painel de infraestrutura cria um site em uma célula e o vincula explicitamente
a uma rota existente; só oferece rotas cujos dois endpoints estejam declarados
nas regiões do site. O backend repete a validação completa antes de salvar e
impede remover uma rota ainda referenciada. O editor não infere conexões pela
aparência ou adjacência. Validator, quality audit, PNG e SVG também consomem
`terrain_rows`.

## Fora da Physical Geography V1

- erosão e consequências urbanas, econômicas ou populacionais da inundação;
  clima mensal, risco, ocorrências e impacto validado sobre sites espaciais são
  definidos em `climate-hydrology-v1.md`;
- estradas desenhadas célula a célula;
- efeitos logísticos automáticos de pontes, portos, minas e fazendas; a
  identidade espacial desses sites agora é coberta por
  `infrastructure-sites-v1.md`;
- distritos adicionais;
- overlays de população, comércio, Qi/Yin, risco ou guerra;
- geração procedural de geografia.

Essas capacidades devem ser adicionadas sobre os donos canônicos existentes,
sem guardar projeções ou narrativas dentro da geografia estática.

## Aceite

1. Os três presets oficiais carregam com geografia completa e distinta das
   regiões.
2. Save/load preserva exatamente geografia, consultas espaciais e textos locais.
3. Rotas continuam com identidade e estado preservados.
4. API e frontend recebem terreno, território, elevação, águas, rotas e sites
   de infraestrutura sem fallback regional.
5. Editor, validator, quality audit e previews usam a mesma verdade física.
6. Schemas e campos obsoletos são rejeitados.
7. Camadas visuais podem ser alternadas sem duplicar estado ou alterar a
   interação region-first.
