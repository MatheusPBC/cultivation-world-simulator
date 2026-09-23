# Plano de conclusão do medieval

Data: 2026-09-22. Status: implementação em curso; gates finais ainda incompletos. Evidência atual e limites em `.agent/tasks/medieval-closure-plan/` (registro local) e `medieval-current-state.md`.

## Objetivo e limites

Concluir o produto medieval existente com cadeias materiais completas, decisões de atores, investigação pelo observador e persistência confiável. Industrial warfare está fora do escopo. Não introduzir Laya na IA dos NPCs: seu papel neste plano é acompanhar o trabalho de implementação, identificar desvio de objetivo e apoiar checkpoints.

Este documento organiza a execução do roadmap em `medieval-roadmap.md` e das correções em `../../medieval-corrections-and-finalization-plan.md`. Não elimina requisitos pendentes nem declara os sistemas parciais concluídos. O diário de evidências permanece em `medieval-current-state.md`.

## Revisão da especificação

- Há muito WIP sobre HEAD `a244e4cd`. Testes anteriores são evidência histórica: precisam ser vinculados ao conteúdo testado antes de serem usados como gate atual.
- O fork medieval tem runtime próprio (`src/sim/medieval`, API `/api/v2`, `web/src/medieval`). O handoff mistura contexto ancestral de cultivation com o medieval; não reativar o runtime legado.
- Fechar economia não significa garantir prosperidade ou remover toda escassez. Significa conservação, causas explicáveis e alternativas materialmente possíveis quando seus pré-requisitos existem. Recusa, erro estratégico e colapso material são resultados válidos.
- A primeira cadeia não precisa ganhar outro planner. Reutilizar objetivos, planos, decisões e owners atuais; corrigir somente lacunas demonstradas.
- Efeitos físicos/datados legítimos não precisam de uma decisão nova por tick. A auditoria distingue início deliberado, resolução de ação anterior e processos físicos; exige a origem correta para cada um.
- Produto concluído exige observação utilizável, save/load e execução com provider real; testes de owners isolados são insuficientes.
- O planejamento foi concluído e a implementação está em andamento; o estado de cada gate deve ser lido nas evidências atuais, não inferido deste texto inicial.

## Regra de execução

Uma cadeia principal em implementação por vez. A próxima etapa abre quando a atual cumpre o aceite ou apresenta uma dependência concreta documentada. Dependências podem receber correções limitadas; isso não autoriza abrir uma nova vertical inteira.

Cada item do roadmap deve estar em uma matriz com: requisito, owner/arquivo atual, estado (`existente`, `lacuna`, `verificado`), evidência, limite e gate de encerramento. Quantidade de testes, arquivos ou checkpoints não é porcentagem de produto pronto.

A [matriz de fechamento](medieval-closure-matrix.md) registra esses estados e limites por requisito. Atualizá-la com evidência do checkout final; uma fatia verificada não promove automaticamente a linha ampla do roadmap.

## Etapa 0 — baseline e fechamento do contrato causal

**Entrega:** inventário finito de requisitos e owners materiais do runtime medieval, com estado do WIP e matriz de causalidade.

1. Registrar HEAD, diff e arquivos novos; preservar mudanças anteriores.
2. Mapear os emissores materiais e seus caminhos públicos/de execução. Para cada um, identificar decisão atual ou processo físico/datado autorizado, revalidação, delta, fontes e rollback.
3. Auditar os limites compartilhados e corrigir bypasses demonstrados: decisão fantasma, ator errado, opção stale, narrativa como causa e fallback oculto em modo IA.
4. Revisar divergências entre AGENTS/specs/handoff e código atual, inclusive schemas e funcionalidades descritas como ainda inexistentes. Atualizar somente após comprovar no código.
5. Restaurar o observador Laya separado do jogo e registrar uma inferência real de início/checkpoint; ausência deve permanecer visível.

**Aceite:** todos os owners inventariados têm classificação e evidência ou pendência nomeada; nenhum defeito crítico conhecido de autoria/transação fica escondido. Regressões dos limites compartilhados e dos bypasses corrigidos passam. Gate de execução completo exige Laya funcional, sem alegar sucesso por fallback.

## Etapa 1 — fechar economia e agência institucional ponta a ponta

**Cadeia:** pressão → percepção por canal válido → objetivo → alternativas concorrentes → pedido/negociação → resposta independente → compromisso → produção/estoque/transporte → entrega → consequência → memória → decisão posterior.

1. Reproduzir o gargalo conhecido de seed 73 e separar produção, trabalho, payroll, poder de compra, armazenamento, rota e política escolhida.
2. Conferir prioridade produtiva, relief, compra bilateral, emprego e workforce no menu real. Recursos existentes e opções válidas precisam estar acessíveis aos atores pelos seus relatórios, sem conhecimento estrangeiro privado.
3. Corrigir somente impedimentos materiais/decisórios comprovados. Não criar subsídio, estoque ou ajuste automático para alcançar uma meta de teste.
4. Exercitar cumprimento, recusa, prazo perdido e reparação usando os mesmos owners. Memória deve ter fonte canônica e participar do contexto de decisão futura, sem obrigar o ator a retaliar ou ajudar.
5. Validar replay/save-load em pontos de pedido, compromisso e carga em trânsito; falha de provider não publica meia transação.
6. Consultar provider real nesta cadeia antes de expandir campanhas; verificar contexto, seleção válida, latência, custo e pausa em falha.

**Aceite:** fixture recuperável demonstra entrega e melhora material; fixture com recusa ou obstáculo demonstra consequência correspondente. O histórico explica o déficit residual. A decisão posterior recebe memória/evidência correta. A cadeia pode ser inspecionada no observatório. Não exigir recuperação de todo mundo natural.

## Etapa 2 — campanha medieval persistente

**Cadeia:** ameaça conhecida → objetivo → decisão de mobilizar → força/provisões → deslocamento → decisões sucessivas → combate/cerco/retirada → controle/cessar-fogo → consequência e revisão do plano.

- Reutilizar `force`, `campaign_supply`, `siege_campaign`, `campaign_ceasefire`, guarnições e estratégia; identificar o elo ausente antes de criar estruturas.
- Manter a campanha por vários turnos com objetivo, posição, suprimento, comando, fadiga e fontes atuais.
- Permitir manutenção, negociação, retirada e interrupção por impossibilidade material.
- Controle territorial depende de presença/capacidade reais; proposta aceita não efetua retirada ou transferência por texto.
- Aprendizado mínimo é revisar objetivos/pressupostos com evidência adquirida. Não exige criar agora um sistema novo de doutrina automática.

**Aceite:** campanha sobrevive a save/load; alteração controlada de suprimento/informação/terreno muda consequências explicáveis; retirada e cessar-fogo têm execução real; atores não recebem onisciência.

## Etapa 3 — fechar os requisitos restantes, uma composição por vez

Esta etapa preserva o roadmap inteiro. Não marcar como opcional algo anteriormente aprovado apenas para declarar conclusão.

| Ordem | Fechamento | Aceite material |
|---|---|---|
| 3A | Tecnologia: pesquisa e difusão por ensino/venda/roubo/migração, aplicação e manutenção | Conhecimento muda produção ou defesa somente com instalação, operador e recursos; perda desses meios remove o efeito |
| 3B | Diplomacia/intriga: influência, suborno, espionagem, sabotagem, acusação e quebra deliberada | Evidência chega por canal válido; contrapartes decidem independentemente; breach/reparação permanecem navegáveis |
| 3C | Conflito civil/religião: pressão, organização, liderança, perseguição e resposta | Tumulto não vira rebelião sem meios; repressão e proteção consomem capacidade real |
| 3D | Magia/ecologia/criaturas já previstas | Custos, alcance, duração, resistência, habitat e respostas têm owners; ameaça pode negociar/recuar e não é evento obrigatório |
| 3E | Lacunas econômicas do roadmap ainda não cobertas | Bloqueio, tarifas, contrabando/detecção e patrimônio recebem recorte explícito e aceite; não desaparecem por omissão |

Cada linha começa pelo inventário do que já existe, integra a primeira cadeia completa e encerra antes da seguinte. Não adicionar novas espécies, escolas, modalidades de guerra ou formas de governo além do necessário ao aceite já acordado.

## Etapa 4 — produto observável e entrega

- Observador: resultado → evento → decisão → owner → fontes; distinguir fato, relato, memória e interpretação.
- Personagem/instituição: mostrar atividade atual, objetivo, alternativas/decisão registradas e consequências; crônica continua resumida.
- UI PT-BR para os fluxos existentes, pausa que drena operação em andamento, retomada e save/load.
- Verificar API e UI em navegador nos fluxos principais; testes de backend não comprovam usabilidade.
- Rodar regressão integrada do medieval e build/type-check. Contratos legados devem ser classificados; não exigir ou alegar compatibilidade xianxia.
- Consolidar WIP, commits e documentação por resultado funcional. Publicação e deploy seguem a autorização aplicável na retomada e incluem conferência do SHA e smoke do ambiente.

## Verificação final

1. Fixtures pressionadas de economia, campanha, tecnologia, intriga e ecologia produzem suas cadeias materiais, com condições e decisões explícitas.
2. Três seeds naturais por dez anos, com checkpoints intermediários para memória, disco, latência e conservação. Começar com horizonte curto e ampliar uma vez que os riscos sejam resolvidos; não repetir simulações longas a cada alteração.
3. Natural estável é válido. Medir escassez, saúde, produção, renda, rotas, escolhas e custos; não impor quota de drama ou vitória.
4. Separar replay determinístico com decisões gravadas de nova execução com provider: LLM não precisa gerar a mesma decisão em consultas novas. Save/load deve preservar estado e decisões já confirmadas.
5. Auditoria causal sem fontes quebradas, sem Story/LLM material, sem autoria falsa; rollback preserva estado, agenda, RNG e histórico.
6. Provider real: amostra representativa, limites de custo e falhas verificadas. Smokes longos com provider falso não serão anunciados como dez anos com IA real.
7. Gate final publica revisão/diff testado, comandos, resultados e limites. Evidência anterior a mudanças relevantes é marcada stale e somente o recorte afetado é repetido.

## Laya acompanhando a implementação

### Responsabilidade

Laya é o avaliador auxiliar de trajetória do agente programador. O agente principal continua responsável por plano, síntese, código e verificação. Laya não executa ferramentas, não aprova merges, não decide ações de NPCs e não valida física ou causalidade por opinião.

O runtime existente já chama `LayaDecisionModel` antes do fallback em `DecisionCascade`, tanto em `initial_decision` quanto em `checkpoint`. A configuração inicial permanece `shadow`: sinais são lidos pelo agente e recebem disposição explícita; o observer não controla processos automaticamente. Isso é acompanhamento contínuo de decisão, não somente recuperação de erro.

### Quando consultar

- Depois da revisão de especificação e antes de iniciar a etapa.
- Antes de abrir outro subsistema ou mudar o plano.
- Ao repetir uma falha/hipótese sem progresso.
- Ao concluir cada subtask e antes de declarar um gate fechado.
- No limiar de ações significativas configurado no runtime, para evitar longos intervalos sem checkpoint.

### Contexto enviado

Objetivo curto, etapa ativa, próximo resultado, critérios pendentes, resumo factual do progresso, falhas/retrabalho, dependências novas e amplitude da mudança. Manter o resumo limitado e atualizado; contadores sozinhos não explicam desvio. Não enviar segredos, código bruto ou conversa inteira.

Perguntas de acompanhamento: estamos avançando no aceite atual? a próxima mudança é necessária? abrimos outra frente sem fechar a anterior? estamos repetindo testes sem nova evidência? há verificação suficiente para concluir? Usar as perguntas tipadas existentes; adaptar o contrato somente se uma lacuna real for observada.

### Como usar o sinal

Registrar modelo/checkpoint, resposta, confiança, latência, `used_fallback`, recomendação e decisão do agente (`aceita`/`rejeitada` com motivo/evidência). Um alerta abre inspeção local e correção de trajetória; não cria automaticamente outro refactor. Confiança do modelo não substitui verificador.

Se Laya falhar, registrar `unavailable` e manter revisão explícita do agente. Fallback nunca é contabilizado como inferência Laya. Recuperar o serviço é pendência operacional visível; não instalar ou baixar modelos grandes silenciosamente.

### Situação verificada neste planejamento

Runtime: `.agent/skills/task-orchestration/runtime/` do workspace. Modelo configurado: `convaiinnovations/laya-typed-decisions`. Consulta ao socket `/tmp/metagame-local.sock` retornou conexão encerrada; `/tmp/metagame-medieval-c100.sock` recusou conexão. Não houve inferência Laya confirmada. A recuperação do observer/túnel é o primeiro item operacional antes de anunciar acompanhamento ativo.

## Critério contra dispersão

Toda próxima mudança deve responder: qual critério pendente esta mudança fecha, e qual evidência mostrará isso? Se não houver resposta, fica no backlog. O checkpoint ao usuário informa resultado fechado, evidência, limite e próximo gate; não termina apenas com contagem de testes.
