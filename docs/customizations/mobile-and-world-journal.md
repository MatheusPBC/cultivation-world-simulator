# Interface mobile e Diario do Mundo

## Shell mobile

`web/src/composables/useIsMobile.ts` ativa o shell dedicado ate 768 px. `web/src/App.vue`
mantem o desktop original e renderiza `MobileGameShell.vue` no celular.

O shell possui tres areas:

1. cabecalho com data e controle de pausa;
2. conteudo vertical rolavel;
3. barra inferior fixa com Diario, Avatares e Roleplay.

Os componentes ficam em `web/src/components/mobile/`. O frontend evita carregar a musica do
mapa automaticamente no celular, reduzindo trafego e tempo de entrada.

## Diario do Mundo

O Diario substitui a lista cronologica como porta de entrada, sem remover o historico.

### Agora

Consulta um resumo deterministico por `1`, `3` ou `12` meses. Exibe:

- quantidade de eventos, acontecimentos importantes e historias;
- personagens ativos no periodo;
- mudancas importantes;
- acoes atualmente em andamento.

O endpoint e:

```http
GET /api/v1/query/world/journal?period_months=1
```

O backend agrega os eventos em `src/server/services/game_queries.py`. A LLM nao participa
dessa agregacao e nao cria fatos para o resumo.

### Linha do tempo

Reutiliza `EventPanel.vue` e `EventStreamList.vue`, mantendo filtros por seita, tipo e
importancia, paginacao e navegacao por personagem/seita.

Em telas estreitas:

- filtros usam duas colunas e o terceiro ocupa uma linha inteira;
- data e texto aparecem em linhas separadas;
- todos os containers flex/grid aceitam encolhimento com `min-width: 0`;
- identificadores longos usam `overflow-wrap: anywhere`;
- nenhum gesto horizontal e necessario para ler um evento.

## Roleplay e avatares

- `MobileAvatarList.vue` e `MobileAvatarCard.vue` oferecem navegacao compacta por personagem;
- `MobileRoleplay.vue` reutiliza o estado de roleplay e reserva espaco para a barra inferior;
- nomes continuam sendo links coloridos para manter a leitura de participantes da narrativa.

## Testes

| Teste | Cobertura |
|---|---|
| `WorldJournalPanel.test.ts` | periodos, resumo e alternancia para timeline |
| `MobileDashboard.test.ts` | integracao do Diario no shell mobile |
| `publicApiModules.test.ts` | chamada do endpoint do Diario |
| `tests/test_api_events.py` | agregacao e contrato do backend |
| `web/e2e/mobile-layout.spec.ts` | viewport de 360 px e quebra de texto longo |

O teste E2E injeta um identificador sem espacos semelhante aos eventos antigos e verifica que
o documento continua com a mesma largura da viewport.
