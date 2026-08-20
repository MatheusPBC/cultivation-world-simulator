# Localizacao e textos gerados por IA

## Objetivo

O locale `pt-BR` cobre tanto a interface Vue quanto os textos estruturados do backend.
Novos textos livres gerados pela LLM recebem uma instrucao de idioma comum para produzir
portugues brasileiro natural e preservar fatos, participantes e resultados fornecidos pela
simulacao.

## Fontes de traducao

### Backend

As fontes editaveis ficam em:

- `static/locales/pt-BR/modules/*.po` para mensagens da simulacao;
- `static/locales/pt-BR/game_configs_modules/*.po` para nomes e descricoes dos CSVs;
- `static/locales/pt-BR/game_configs/*.csv` para dados localizados dedicados;
- `static/locales/pt-BR/templates/*.txt` para prompts.

Os arquivos em `static/locales/pt-BR/LC_MESSAGES/` sao artefatos consolidados. Depois de
alterar as fontes, execute:

```bash
python tools/i18n/build_mo.py
```

O carregamento usa uma cadeia de fallback, testada em
`tests/test_i18n_fallback_chain.py`, para que uma chave ausente em `pt-BR` ainda possa ser
resolvida sem exibir o identificador cru.

### Frontend

Os JSONs ficam em `web/src/locales/pt-BR/`. O registro unico de idiomas e
`static/locales/registry.json`; menus e configuracoes nao mantem uma segunda lista manual.

## Instrucao global de saida da LLM

`src/utils/llm/prompt.py` anexa o template `llm_output_language.txt` ao prompt enviado ao
provider. Essa camada pede que a resposta:

- use portugues brasileiro claro e natural;
- explique a cena de forma coerente;
- preserve os fatos e personagens recebidos;
- nao invente participantes nem resultados ausentes.

A instrucao afeta somente novas geracoes. Textos livres existentes em um save nao sao
reescritos automaticamente. Para uma conversao explicita de campos de personagem em uma
copia de save, existe `tools/localize_save_avatar_texts_ptbr.py`.

## Provider Codex CLI com OAuth

O formato `codex_cli` em `src/utils/llm/client.py` executa o Codex em modo nao interativo:

```text
codex exec --ephemeral --skip-git-repo-check --sandbox read-only
```

O prompt entra por `stdin` e a resposta final e lida de um arquivo temporario. A chamada:

- nao exige API key;
- usa `CODEX_HOME` montado no container;
- nao registra nem devolve o token OAuth;
- tem timeout de 180 segundos;
- executa com sandbox somente leitura e diretorio de trabalho `/tmp`.

Variaveis do container:

| Variavel | Funcao |
|---|---|
| `CWS_CODEX_BIN` | Caminho do script do Codex CLI |
| `CWS_CODEX_NODE` | Binario Node usado para executar o CLI |
| `CWS_CODEX_HOME` | Diretorio OAuth visto dentro do container |

O teste principal e `tests/test_llm_codex_cli.py`. A obrigatoriedade de API key e coberta por
`tests/test_llm_validation.py`, e o idioma de saida por `tests/test_llm_output_locale.py`.

## Mapas e snapshots

Nomes e descricoes de regioes usam `map_regions.po`. Os mapas oficiais guardam overrides
localizaveis e o snapshot atual evita transformar uma traducao em dado canonico do mapa.
`tools/migrate_map_snapshot_v2_to_v3.py` converte snapshots anteriores quando necessario;
sempre trabalhe sobre copia do save.
