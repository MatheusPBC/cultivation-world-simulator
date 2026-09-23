# Runtime público medieval

Unidade de integração das etapas1/7: servidor FastAPI exclusivamente medieval,
`/api/v2/query/*` e `/api/v2/command/*`. Não há rotas de intervenção material,
cultivo, seitas ou personagens controlados pelo observador. `src.server.main`
é a montagem pequena deste servidor. O observatório Vue/Pixi já usa o contrato v2;
o bundle xianxia antigo não é servido como se fosse compatível.

## Contrato de execução

Uma instância de MedievalRuntime possui mundo, simulador, pausa, velocidade,
erro técnico, revisão e ID de sessão. Uma trava serializa comandos, consultas e
passos automáticos. Consultas constroem DTOs sob a trava, nunca expõem referências
mutáveis. Pausar aguarda o salto em andamento; depois da resposta não há novos
saltos. Avanço manual exige pausa e executa exatamente um salto híbrido.

Criar/carregar publica candidato somente após validação e autosave. Cada salto
salva antes da publicação. Falha técnica pausa, preserva mundo/save anteriores
e retorna código estável sem caminhos, segredos ou traceback. Erro de entrada não
é tratado como decisão estratégica. Fechamento do app encerra o único loop.
Velocidade significa saltos por segundo real, nunca mudança na duração simulada.

Configuração persistente medieval contém seed, contagem inicial de personagens
(padrão12, 1–60), locale pt-BR e política determinística; não finge IA integrada.
Saves usam schema60; schemas anteriores são rejeitados e preservados, sem
sobrescrita ou migração. IDs de
sessão/pausa/velocidade/locks continuam apenas no runtime.
EconomyView inclui expansion_blueprints/expansions; folhas podem pertencer a obras
ou instalações e projetos de pesquisa. Finanças identifica a origem de cada folha.
ExpansionBlueprint expõe additional_recipe_id/new_capacity para linhas adicionais,
mutuamente exclusivas com alteração da âncora; Recipe expõe required_technology_id.
Os DTOs projetam o catálogo salvo, não concedem conhecimento nem criam produção.
Diretório default usa MedievalWorldSimulator(-dev), preservando CWS_DATA_DIR como
override existente. Saves medievais ficam em saves/medieval; não procurar saves do
clone-fonte. Nomes são IDs seguros, não caminhos; symlinks/traversal/nomes de
dispositivo Windows são recusados. Sobrescrita manual exige overwrite=true.
Autosaves são slots independentes por sessão, nunca sobrescrevem saves manuais.

## Endpoints

Envelope `{ok:true,data:...,revision:N}`; erro HTTP não-2xx com
`{ok:false,error:{code,message},revision:N}`. Mensagens da API em PT-BR.

Objetivos de governança expõem `stock_id`, `resource_id` e `target_quantity`
derivado do estado atual. O alvo de insumos não é população×meses; usa entradas
das receitas e capacidades das instalações no estoque. Relatórios nomeiam o
recurso observado. DTOs não persistem nem possuem quantidades materiais.

- GET query/status: mundo disponível, pausa, erro, dia, sessão e velocidade.
- GET query/observatory: status, world, society, economy, map, governance, research, diplomacy, creatures e
  campaigns do mesmo instante, serializados sob uma única trava/revisão; evita misturar meses no observatório.
  `research.technology_sales` reúne apenas vendas concluídas e seus recibos de pedido, aceite, pagamento e
  aprendizado para navegação pelo Why. `campaigns.siege_campaigns` projeta o estado canônico de cada cerco,
  incluindo a endurance da guarnição e o colapso defensivo quando ela chega a zero,
  sem transferir automaticamente controle territorial ou administração. Uma
  guarnição também pode terminar por retirada voluntária (`withdrawn`), mantendo
  a coluna e a ocupação física separadas do dever militar.
  `campaigns.territorial_controls` projeta controles persistidos somente após
  decisão explícita e guarnição material, separados de `occupations` e da
  administração do assentamento. `creatures.hazard_impacts` expõe o impacto engine-owned registrado
  (origem, alvo, magnitude, exposição e resistência), inclusive alvos
  `population_group` quando uma criatura ataca uma coorte anônima; isso não
  publica automaticamente esse fato como conhecimento dos atores.
  `campaigns.political_settlements` projeta apenas propostas vivas de
  desescalada e concessão administrativa, com termos, estado e eventos-fonte;
  a projeção não executa transferência, retirada ou controle.
- GET query/options: configuração inicial e mapa disponíveis nesta versão.
- GET query/world: resumo do mundo e configuração persistente.
- GET query/society: personagens, povos, governos, organizações e povoados.
- `SocietyView.migrations` lista jornadas ativas; `SettlementView.population`
  (residentes) e `present_population` são distintos.
- GET query/economy: catálogo, estoques, contas, produção, últimas folhas salariais, necessidades, mercados,
  ordens pendentes, cargas, `customs_checkpoints` e `cargo_manifests`; ordens concluídas permanecem rastreáveis por eventos.
  O catálogo inclui `repair_blueprints`, `repairs`, contratos `employment_contracts`, postos civis de alfândega e manifestos
  (economia schema 14); custos, limites de trabalhadores e salários são definidos pelo engine, não pelo cliente.
  Cada contrato também expõe o `work_site_id` próprio do empregador, a coorte,
  o resultado do último ciclo e os recibos causais; a projeção não cria nem
  renova vínculos.
- `EconomyView.migration_provisions` expõe provisões e seu `MoneyAccount`; o
  observador apenas projeta a transferência bilateral e não controla famílias.
- GET query/map: geografia, território, rotas e instalações canônicas.
- `research.rite_blueprints` expõe apenas metadados derivados de cada blueprint
  (`school`, `cost`, `range`, `duration_days`); o cliente não registra nem executa
  uma árvore de feitiços.
- GET query/governance: cargos, políticas tributárias, objetivos, planos, relatórios de
  suprimento, `SiteReport`, `customs_notices` privados e relatórios datados de rotas por ator. Cada aviso alfandegário
  também expõe a `classification` engine-owned (`ordinary` ou `contraband`), derivada do catálogo do recurso e
  preservada no receipt de apresentação; o proprietário pode escolher o retorno
  (`returned`) quando a rota original e a capacidade de origem ainda forem válidas;
  o operador também pode registrar uma apreensão explícita (`seized`) para
  contrabando classificado, desde que possua autoridade e estoque local; isso
  não executa confisco ou rerroteamento automático. Relatórios e
  ofertas de estoque incluem a cotação histórica de exportação da origem (taxa,
  fato de política e coletor), nunca saldo da conta coletora; `SiteReport`
  registra a presença local do mantenedor e permanece privado, não sendo
  broadcast automático; consulta
  onisciente do observador, não contexto permitido de um ator do mundo. Um
  relatório de rota ausente ou com 30 dias ou mais não é inferido do mapa
  canônico; ver medieval-autonomy.md. Cada leitura também expõe
  `daily_flow_bulk`, o volume agregado observado no dia, sem identidade de
  carga, estoque, conta ou proprietário.
- A mesma projeção expõe `fiscal_route_reports` recebidos pelo ator e seus recibos
  de publicação/entrega. O observatório pode ver todos os relatórios, mas essa
  visão não concede conhecimento a atores. Opções fiscais são recompostas pelo
  engine na abertura de nova ordem; IDs inventados ou vencidos são rejeitados e
  ordens já contratadas não podem ser redirecionadas.
- `GovernanceView.settlement_reports` expõe observações datadas com residentes e
  presentes; isso não é canal de controle para o observador.
- GET query/research: catálogo, projetos e conhecimento técnico por instituição;
  consulta onisciente, não transferência de conhecimento entre atores.
- GET query/diplomacy: listas planas de propostas, obrigações e notices (o
  agrupamento por proposta/cláusula é responsabilidade do cliente); o mesmo
  payload também está no campo `diplomacy` de query/observatory. Consultas
  separadas não garantem a mesma revisão entre si se o mundo avançar; apenas uma
  chamada a query/observatory é atômica entre todos os seus campos. Consulta
  onisciente; não concede conhecimento a parte não notificada e não expõe
  comando material de barganha.
- GET query/dossier/{actor_kind}/{actor_id}: perspectiva privada derivada do
  conhecimento já entregue ao ator, incluindo notices/relatórios/finding com
  `recipient_ref` correspondente, os receipts factuais conhecidos, conhecimento
  técnico próprio, memórias institucionais e objetivos/planos próprios.
  Inventário, plano e observação de outra instituição não são copiados. Cada
  entrada factual pode listar `cause_event_ids`, mas somente quando o evento
  causal também pertence ao conjunto conhecido pelo ator; a cadeia completa
  segue navegável pelo endpoint causal do Dao.
- `GET query/society` agora inclui `civic_protests`, `civic_movements` e
  `civic_strikes`, com estágio, coorte,
  participação reservada, demanda e receipts de decisão/relatório. A projeção é
  somente leitura; não abre nem encerra paralisações.
- O observatório também distingue receipts `institutional_decision_stale_affordance`:
  uma escolha envelheceu antes da revalidação do owner, o que não é `NO_ACTION`
  nem falha do provider.
- GET query/events?after=0&limit=50: fatos em sequência, página máxima100.
- GET query/causal/{event_id}: fato, causas diretas e efeitos diretos paginados.
- GET query/saves: IDs dos arquivos, data/tamanho e metadados de compatibilidade.
- POST command/create: seed, character_count, replace=false.
- POST command/step: um salto; POST command/pause e command/resume.
- POST command/speed: jumps_per_second de1 a20.
- POST command/save: save_id e overwrite=false; POST command/load: save_id.

Servidor local por padrão. Comandos exigem JSON e recusam Origin remoto; CORS
limitado ao ambiente localhost de desenvolvimento. Isso não é autenticação para
exposição pública. Não publicar na rede sem uma camada de autenticação.

Provas: lifecycle por HTTP, doze meses/save/load, erros sem estado parcial,
serialização real de concorrência, pausa drena salto, limites de paginação,
confinamento de arquivos e ausência de comandos materiais na superfície pública.
Build/inspeção e limites do observatório constam em medieval-observatory.md.
Pesquisa/ensino/aplicação e seus limites estão em medieval-research.md.
Abastecimento autônomo por regras, incluindo o conhecimento datado de rotas,
está em medieval-autonomy.md; barganha diplomática determinística e sua
exposição via API/observatório estão descritas em medieval-diplomacy.md. Etapa1
do plano permanece PARCIAL: faltam hazards naturais/clima/desgaste, mobilidade e
treinamento de força de trabalho, pedágio/trânsito/bloqueios/contrabando e IA real;
ver medieval-runtime.md e
docs/handoff/medieval-current-state.md para o estado e a evidência centralizada.
