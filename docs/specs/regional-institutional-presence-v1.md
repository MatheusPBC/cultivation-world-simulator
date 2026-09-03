# Presença Institucional Regional V1

## Objetivo

Expor, na mesma leitura regional, a governança urbana explícita e o alcance
espacial atual das seitas. A projeção permite que mapa, detalhes e interpreters
percebam sobreposições institucionais sem criar uma nova autoridade sobre o
mundo.

Esta entrega não implementa conquista territorial, guerra por território,
tributação regional nova ou troca automática de governo.

## Donos canonicos

- `CityState.governance` continua sendo a única verdade sobre quem administra
  uma `CityRegion` e sobre sua capacidade administrativa.
- `SectManager` calcula a influência espacial atual das seitas a partir das
  seitas, membros, sedes e mapa existentes.
- `Map.region_cors` continua sendo a forma territorial de cada `Region`.
- a Presença Institucional Regional não é salva e não possui mutações próprias.

Uma seita pode possuir alta influência espacial dentro de uma cidade governada
pela dinastia. Isso representa sobreposição política potencial, não uma troca
de soberania.

## Projeção regional

Para cada região, a projeção pública informa:

- identidade, tipo e quantidade de células da região;
- governança, somente quando houver uma `CityRegion` com controlador explícito;
- participação de cada seita nas células da região;
- a seita com maior participação, apenas como leitura derivada.

A participação de uma seita é calculada por:

```text
células atuais de influência da seita dentro da região
------------------------------------------------------
            total de células da região
```

Empates são resolvidos apenas para ordenação determinística. `dominant_sect_id`
não significa proprietário, governante nem vencedor de uma disputa.

## Uso causal

```text
membros, poder ou sede de uma seita mudam
                    |
                    v
alcance espacial da seita é recalculado
                    |
                    v
participação regional muda
          +---------+---------+
          |                   |
          v                   v
contexto da seita      projeção visual do mapa
```

```text
governança canônica da cidade muda
                    |
                    v
contexto do governo e camada institucional mudam
```

Os interpreters recebem essa leitura como contexto. Nesta V1 ela não cria uma
ação nova, não muda affordances e não aplica efeitos globais. Uma futura ação
territorial deverá pertencer ao domínio que realmente puder executá-la e gerar
`Event`, `StateDelta` e links causais.

## API e interface

`GET /api/v1/query/world/institutional-presence` retorna a projeção atual por
região. O frontend valida o contrato e falha fechado para IDs, proporções,
células ou referências inconsistentes.

O mapa oferece uma camada PT-BR separada de "Influência das seitas":

- a governança urbana explícita é exibida sem alterar o mapa físico;
- a sobreposição de influência sectária pode ser indicada visualmente, mas não
  substitui a cor de governança;
- a camada é somente leitura e não captura a interação da região.

## Fora da V1

- disputa ou transferência de soberania;
- controle gradual de rotas, impostos ou recursos;
- ocupação militar e guerra territorial;
- facções políticas como nova entidade;
- criação automática de condições ou eventos por sobreposição;
- logistica profunda e cadeias espaciais de suprimento.

## Aceite

1. A mesma região pode expor governo dinástico e influência sectária sem
   confundir os conceitos.
2. Mudanças nas entradas canônicas recompõem a projeção sem persistir estado
   duplicado.
3. Governo e seita recebem apenas o contexto que lhes é relevante.
4. API, mapper, store e camada visual rejeitam projeções inconsistentes.
5. Save/load não ganha uma seção de Presença Institucional Regional.
