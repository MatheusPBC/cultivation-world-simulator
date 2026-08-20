# Customizacoes PT-BR, Codex e interface mobile

Este diretorio documenta a variante mantida em `MatheusPBC/cultivation-world-simulator`,
baseada no projeto original `4thfever/cultivation-world-simulator` v4.2.1.

## Escopo implementado

- localizacao completa da interface e do conteudo estruturado para `pt-BR`;
- instrucao global para que novos textos gerados por LLM sejam escritos em portugues brasileiro;
- provider `codex_cli`, que reutiliza uma sessao OAuth do Codex sem copiar tokens para o codigo;
- suporte a mapas e snapshots localizados;
- Diario do Mundo com resumo deterministico e linha do tempo completa;
- interface mobile dedicada para mundo, avatares e roleplay;
- correcao de overflow horizontal e textos longos em telas estreitas;
- testes de contrato, localizacao, provider Codex, mapas, diario e layout mobile.

## Documentos

- [Localizacao e textos gerados por IA](./localization-and-llm.md)
- [Interface mobile e Diario do Mundo](./mobile-and-world-journal.md)
- [Execucao na VPS](./vps-deployment.md)

O estudo de produto que orientou o Diario do Mundo permanece em
[`world-journal-study.md`](../../world-journal-study.md).

## Mapa rapido do codigo

| Area | Arquivos principais |
|---|---|
| Registro de idiomas | `static/locales/registry.json` |
| Backend i18n | `src/i18n/`, `static/locales/pt-BR/` |
| Frontend i18n | `web/src/locales/pt-BR/` |
| Provider Codex | `src/utils/llm/client.py`, `src/utils/llm/validation.py` |
| Instrucao de idioma da LLM | `src/utils/llm/prompt.py`, `static/locales/*/templates/llm_output_language.txt` |
| Diario no backend | `src/server/services/game_queries.py`, `src/server/api/public_v1/query.py` |
| Diario no frontend | `web/src/stores/worldJournal.ts`, `web/src/components/game/panels/WorldJournalPanel.vue` |
| Shell mobile | `web/src/components/mobile/`, `web/src/composables/useIsMobile.ts` |
| Mapas localizados | `src/run/map_source.py`, `src/run/map_snapshot.py`, `tools/migrate_map_snapshot_v2_to_v3.py` |

## Limites de seguranca

- saves, `settings.json`, `secrets.json`, `.env` e o diretorio OAuth nao pertencem ao Git;
- o volume `/codex-home` contem autenticacao e deve permanecer somente na VPS;
- o resumo do Diario usa eventos e estado reais. A LLM narra, mas nao decide resultados da simulacao;
- a interface nao traduz retroativamente textos livres ja gravados em saves antigos.
