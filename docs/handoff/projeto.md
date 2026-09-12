# Guia do projeto e transferência de ambiente

## O que estamos construindo

Fork de Cultivation World Simulator: simulação de cultivo, personagens, cidades, seitas, dinastia, economia e ambiente. O usuário é Heavenly Dao, observador onisciente com caminhos de interação explícitos. O objetivo é acompanhar atores com personalidade tomando decisões e acumulando consequências, não gerar uma novela por sorteio.

Avatares mantêm ações e relações pessoais. Instituições sustentam compromissos através de sucessões. População é agregada. Engine calcula possibilidades/resultados; LLM escolhe possibilidades válidas e interpreta. A crônica é uma seleção legível, não o banco de verdade nem um substituto dos detalhes de cada personagem.

## Arquitetura e mapa do código

Backend Python/FastAPI, frontend Vue 3/TypeScript/Vite/Pinia, mapa PixiJS. Consulte dependências reais em `requirements.txt`, `requirements-runtime.txt` e `web/package.json` antes de adicionar bibliotecas.

| Responsabilidade | Entrada no repositório |
| --- | --- |
| World, Avatares, seitas e estado material | `src/classes/core/` e `src/classes/environment/` |
| Instituição/office/claim e estados separados | `src/classes/institution/` |
| Eventos e armazenamento causal | `src/classes/event.py`, `src/classes/event_storage.py` |
| Affordances e decisão coletiva | `src/classes/domain_affordance.py`, `src/systems/domain_affordance_registry.py`, `src/systems/domain_decision_interpreter.py` |
| Administração anual da seita | `src/classes/sect_decider.py` |
| Ações individuais e interações | `src/classes/action/`, `src/classes/mutual_action/` |
| Autoridade efetiva | `src/systems/institution_authority.py` |
| Ajuda, comércio, termos, memória | `src/systems/institutional_aid.py`, `institutional_commerce.py`, `institutional_resource_commitment.py`, `institutional_memory.py` |
| Guerra e paz institucionais | `src/systems/institutional_war.py`, `institutional_peace.py` |
| Hidrologia | `src/systems/regional_hydrology.py` |
| Narrativa e crônica | `src/classes/story_event_service.py`, `src/systems/chronicle_service.py` |
| Orquestração mensal | `src/sim/simulator.py`, `src/sim/simulator_engine/phase_registry.py`, `finalizer.py` |
| Pré-história | `src/sim/simulator_engine/prehistory.py` |
| Save/load | `src/sim/save/`, `src/sim/load/` |
| API estável | `src/server/api/public_v1/` |
| Projeção de cadeia institucional | `src/server/assemblers/institutional_chain.py` |
| Frontend | `web/src/components/`, `web/src/stores/`, `web/src/api/`, `web/src/types/` |
| Configuração e dados declarados | `src/config/`, `static/config.yml`, `static/game_configs/` |

Nomes curtos agrupados na tabela pertencem à mesma pasta do primeiro arquivo da célula. O mapa é uma rota de investigação, não licença para centralizar lógica nesses arquivos.

### Fronteiras essenciais

- Owners existentes aplicam recursos, população, relações e infraestrutura. Não duplicar estado em planners, memórias ou projeções.
- `Simulator.step()` orquestra fases; finalizer/transaction protegem o commit mensal. Erro após mutação deve chegar ao rollback, não ser engolido.
- Story tem fonte factual e nenhum delta. Comando de jogador/API que produz ação precisa de autoria real, não decisão inventada retrospectivamente.
- Casa real e linhagem usam IDs na Dynasty; relações familiares pertencem aos Avatares. Consorte não vira linhagem sanguínea por casamento. Sucessão não gera sucessor mensal automático.
- Conhecer região não a ocupa automaticamente; ocupação passa por ação `Occupy`.
- Rito popular não equivale a patrocínio institucional; este exige decisão e fonte. Não inferir audiência a partir de prosa.
- Mapa oficial schema v6 separa território (`region_rows`), geografia física, rotas e sites; mantenedor explícito não pode ser deduzido por proximidade.
- API separa query/command, serializa mutações e projeta dados canônicos. Não recolocar toda lógica em `src/server/main.py`.
- Frontend segue DTO → mapper → store/composable → componente. O Dao não perde informação porque um ator desconhece um fato.

## Documentação de aprofundamento

- [Plano e invariantes](plano-principal.md).
- [Kernel causal](../specs/causal-world-kernel.md).
- [Configuração](../specs/config-architecture.md).
- [API e módulos do servidor](../specs/external-control-api.md).
- [Mapa](../specs/region-first-map-system.md).
- [StoryEventService](../specs/story-event-system.md).
- [Roleplay](../specs/avatar-roleplay-mode.md) e [escolhas unificadas](../specs/single-choice-unified-framework.md).
- [ADRs](../adr/) e [vocabulário/checkpoints](../../CONTEXT.md).

## Preparar outro ambiente

Fork de trabalho: `https://github.com/MatheusPBC/cultivation-world-simulator.git`. Não confundir com upstream. O código-base deste handoff é `896c0359`.

```bash
git clone https://github.com/MatheusPBC/cultivation-world-simulator.git
cd cultivation-world-simulator
git status --short
git log -1 --oneline
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web
npm ci
cd ..
```

No clone novo, `origin` normalmente será o GitHub. Na máquina de origem deste trabalho, `github-personal` apontava ao GitHub e `origin` à VPS: **sempre conferir `git remote -v` antes de publicar**.

Executar backend de desenvolvimento, seguindo o [README](../../README.md):

```bash
export CWS_DATA_DIR="$(mktemp -d /tmp/cws-handoff-dev.XXXXXX)"
.venv/bin/python src/server/main.py --dev
```

Para executar Vite separadamente, em outro terminal dentro de `web`, usar `npm run dev`; conferir as portas e o proxy em `web/vite.config.ts`. Os comandos são instruções de reprodução; instalação e inicialização não foram executadas para produzir este pacote.

### Configuração e isolamento

`static/config.yml` contém defaults versionados. Configuração do aplicativo vive no data root (`settings.json`/`secrets.json`); `RunConfig` captura parâmetros do mundo e é persistido. Não copiar segredos para templates, commits, logs públicos ou este handoff.

Use data root isolado em desenvolvimento/testes. Configure `RunConfig.test_mode` nos mundos de teste; esse modo não pode chamar provider real nem checar conectividade. Não basta um prompt dizer “teste”. Credenciais e acesso à VPS precisam ser provisionados separadamente, não via Git.

## Verificação proporcional

Priorizar testes das fronteiras alteradas. TDD não é obrigatório para cada mudança; não criar milhares de testes duplicados. Exemplos de execução a partir da raiz:

```bash
export CWS_DATA_DIR="$(mktemp -d /tmp/cws-handoff-tests.XXXXXX)"
.venv/bin/pytest tests/test_domain_affordances.py tests/test_sect_annual_affordances.py tests/test_month_transaction.py tests/test_institution_persistence.py
.venv/bin/python tools/institutional_smoke.py --scenario natural --months 120 --seed 20260904 --output /tmp/cws-handoff-natural120.json
.venv/bin/python tools/institutional_smoke.py --scenario pressured --months 120 --seed 20260904 --output /tmp/cws-handoff-pressured120.json
```

Em `web`, `npm run test -- <arquivo>` executa seleção Vitest e `npm run build` faz TypeScript + Vite. Para mudança visual, inspecionar a tela real: build verde não prova legibilidade.

Smokes são cenários institucionais focados: declarar seed, fixture/política, meses, revisão, chamadas ao provider e invariantes auditadas. Não declarar toda a suíte verde com esses resultados. Se sandbox bloquear TestClient/threadpool, registrar a limitação e repetir somente com permissão adequada; não ajustar produção para mascarar infraestrutura de teste.

## Persistência e produção

O checkpoint entregue usa save schema 6 e rejeita saves antigos explicitamente; schema do mapa é outra coisa. Saves podem depender de sidecar SQLite: copiar apenas JSON não garante um backup recuperável. Há limitação registrada de crescimento de sidecars antigos; não fazer limpeza automática de dados reais.

Deployment histórico usa Docker Compose, backend/frontend separados e bind de `docker-data` em `/data`. Verificar `docker-compose.yml` e `deploy/` na revisão alvo. O bind de rede depende de `CWS_BIND_IP`; não expor uma instalação privada à internet por acidente.

Em 09/09/2026 foi registrado deploy de `896c0359`, backup restrito de `docker-data` e imagens anteriores guardadas para rollback. Este pacote **não consultou a VPS**, não contém chaves e não atesta que aquela revisão ainda está rodando. Solicitar acesso operacional separadamente.

Antes de um deploy autorizado: verificar runtime/revisão, pausar e drenar se necessário, salvar mundo, fazer backup consistente de todo data root e verificar recuperação, guardar imagem/revisão anterior, construir/publicar e validar backend, frontend e proxy/API. Incompatibilidade de save exige decisão humana; nunca converter ou apagar dados reais automaticamente. Rollback deve considerar tanto código quanto dados.

## Diagnóstico sem alterar o mundo

Rotas úteis sob `/api/v1/query/`:

- `runtime/status`, `world/state`, `world/journal?period_months=12`.
- `events?limit=1000` com paginação quando houver cursor; esse feed público não representa necessariamente todos os fatos internos.
- `events/{event_id}/causal` para investigar autoria e consequências.
- `world/institutional-chain?owner_kind=sect&owner_id=12&limit=100` (substituir instituição válida).
- `avatars/overview`, `mortals/overview`, `dynasty/overview`, `saves`.

Consultar o contrato atual antes de usar rotas ou parâmetros. Inspeção não autoriza avançar meses, regenerar narrativa, chamar LLM, criar mundo, editar saves ou fazer deploy.

## Como colaborar na retomada

Preservar WIP, aplicar diffs pequenos e separar fato, hipótese e decisão. Delegação não é automática: quando autorizada, tarefas delimitadas e arquivos sem sobreposição; responsável principal integra e verifica. Preferências históricas do usuário: Luna para tarefas leves, Terra para complexas e Claude via herdr quando disponível/autorizado. Nenhuma dessas ferramentas é requisito para rodar o projeto ou continuar o trabalho.

O próximo responsável deve ler [pendências](estado-e-pendencias.md), confirmar evidências atuais e entregar um caminho completo por vez. Não declarar a visão de “mundo vivo” concluída só porque suas classes e contratos existem.
