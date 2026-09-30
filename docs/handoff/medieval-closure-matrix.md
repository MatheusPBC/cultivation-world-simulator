# Matriz de fechamento do fork medieval

> Fechamento vigente: [contrato de conclusão](../../medieval-completion-contract.md),
> de 28/09/2026, marcos M0–M8 incluindo povos, magia e religião. Checks E históricos
> permanecem evidência do recorte descrito, não conclusão do contrato ampliado.

## M0 — referência do roadmap ao contrato atual

| Requisito do roadmap | Marco atual | Owners e integração exigida | Cobertura e evidência autoritativa |
|---|---|---|---|
| 0. Estabilizar fundação: autoria, affordances, causalidade, rollback, runtime | M0/M7/M8 | `material_execution`, `events`, owners canônicos e `MedievalSimulator`; decisão/causa, revalidação e publicação atômica | Base e limites em E265/E266; inventário e testes por família nas linhas Gate A. Cobertura global parcial; regressão final nas superfícies alteradas. |
| 1. Economia e informação material: preço/demanda, mercado, tarifa, bloqueio, contrabando, escassez e propriedade | M1/M3/M7 | `economy`, `markets/procurement`, `logistics/routing`, `tariffs/embargo`, `society/demography`, `KnowledgeState` | M1 preparado aceito em E208/E277/E282; a adaptação natural continua aberta para M8. E263 prova alívio agudo e E264 mostra que a oficina ficou bloqueada por `payroll_funds`. |
| 2. Estratégia/diplomacia: objetivos, concessão, negociação, commitments, persuasão, espionagem, suborno e sabotagem | M2/M3/M6 | `StrategyState`, `AuthorityState`, `KnowledgeState`, `diplomacy*`, `commitments`, `espionage`, `bribery`, `sabotage` | Recortes controlados M2/E294, M3/E320 e M6/E332 aceitos; memória/decisões independentes e autoria verificadas nos recortes. Escolhas OAuth/Luna E257–E261 são situadas, não composição natural. Corpus atual e gates naturais em M8. |
| 3. Conhecimento, produção e poder: pesquisa, conservação, aço/pólvora/artilharia/vapor/logística/barreiras/doutrina; difusão e aplicação | M3/M5 | `ResearchState`, `economy`, `workforce`, `KnowledgeState`, `technology_*`, `teaching/apprenticeship` | M3/E320 aceito pelos recortes materiais referenciados em seu checklist; E295–E318 conectam aquisição/aplicação, inclusive E300–E308 pólvora/artilharia. Catálogo sozinho não conta; generalização/naturalidade não são inferidas desses recortes. |
| 4. Campanhas/território: força, recrutamento, manutenção, comando, reconhecimento, suprimento, combate, retirada, cerco, ocupação e solução política | M2/M7 | `StrategyState`, `AuthorityState`, `force*`, `campaign_*`, `siege_campaign`, `logistics`, `territorial_control`, owners de população/economia | M2/E294 e composição M7/E335 provam cenários controlados com autoridade/QG/comandante, interferência e consequência civil, sem escolha de ação pós-início pelo teste. Não extrapolar política stub para provider real ou emergência natural. |
| 5. Magia, criaturas e ação individual | M4/M5/M6 | Society/Research owners e `rites`, `site_services`, `creature*`, `character_*`, `assembly_denial` | M4/E324.d, M5/E328 e M6/E332 aceitos em recortes controlados: trabalho dos quatro povos, elemental/evocação com custos e contramedidas, adesão independente e resposta social. Composição/navegabilidade E335; gates amplos continuam M8. |
| 6. IA, observabilidade, save/load e calibração | M7/M8 | `ai_decider`, contexto de Knowledge, `queries`, API medieval, UI Atlas/Crônica/dossiers/`why()`, persistence/event chunks | Experiência integrada controlada M7/E333–E335 aceita, com navegador/retomada; E336 regressão apropriada e corpus real limitado fechado em E336.h. E199/E200 é histórico; E337 reprovado. Novo gate natural e custos em execução em M8/E343 após E339/E342. |

- [x] M0 crosswalk: mapear as sete seções (0–6) do roadmap a M0–M8,
  owners/integradores e evidência/limites acima. Os requisitos internos têm
  checklists próprios em M1–M8; esta tabela não declara capacidades concluídas.

- [x] Preservar o WIP do HEAD `51c213df` em snapshot local recuperável (`E265`)
  e depois em checkpoint Git local `6f78ea11` na branch
  `codex/medieval-remote` (275 arquivos; `git diff --cached --check` limpo).
  O commit está local, sem push/merge/deploy; o WIP do checkpoint permanece
  revisável e o histórico remoto não foi alterado.
- [x] Revisar individualmente o conjunto recuperável E244–E255 e classificar
  limites (`E266`): dez saves E245/E247–E249/E251–E255 passaram a auditoria
  causal atual. E244, E246 e E250 não têm output reproduzível preservado; manter
  esses registros como histórico sem prova, sem inventar resultado.
- [x] Mapear as sete seções do roadmap para M0–M8 e registrar estado corrente
  versus histórico; a revisão das linhas detalhadas de cada requisito continua
  vinculada aos itens específicos do contrato.
- [x] M0/E286: reconciliar o cabeçalho do contrato, a matriz e o diário com o
  checkout limpo em `3c6e590e`, E284–E285 e a referência local de upstream;
  registrar limites de atualidade e manter M2 como próxima frente sem reabrir
  E283 cancelado. A referência é local, não confirmação do remoto ao vivo.
- [x] M0/E301: preservar e reconciliar o novo checkpoint `3c6e590e` + WIP
  E286–E311, com o estado parcial de E300, schema e próxima tarefa alinhados
  entre contrato, matriz e diário. Evidência exigida: snapshot recuperável do
  diff rastreado e arquivos não rastreados, hashes, status/branch/HEAD e limites.
- [x] M1/E302: retomar o diagnóstico da adaptação econômica natural a partir
  do bloqueio de folha/renda, sem alterar regras antes de localizar causa,
  conhecimento, affordance, autoridade, recursos, política e efeito em famílias.
  Usar a evidência E264/E269–E282 como baseline, não como prova de recuperação
  natural; registrar um diagnóstico reproduzível antes de qualquer solução.
  Reconciliado com o checkout atual: owners de subsistência, labor, emprego,
  workforce, demografia, relief, renda inicial, empréstimo e prioridade estão
  sem diff; a alteração econômica corrente é perda material do excedente público
  por conservação (E298), não uma nova fonte de renda. E281 segue diagnóstico
  read-only autoritativo do mecanismo; saves dessa série são históricos e não
  foram carregados no schema 80. Conclusão: bloqueio estrutural de renda própria
  para coortes sem trabalho pago/dependentes agregados, mais caixa institucional
  comprometido; relief/crédito/preferência não provaram adaptação natural. M1
  segue aceito somente no cenário preparado; Gate B natural segue aberto em M8.
- [x] M0/E305: preservar o WIP integrado até E304 antes do próximo recorte.
  Branch `codex/medieval-remote`, HEAD `3c6e590e`, 31 tracked modifications e
  quatro untracked; snapshot local em `/tmp/medieval-resume-e304-20260929.patch`
  (SHA-256 `36f83c2e0deb65316c5e1af0099b1fdaad8c249ffa0d5bcfaeaa424f40c1bd3e`)
  e `/tmp/medieval-resume-e304-20260929-untracked.tar.gz` (SHA-256
  `3a3e1d04b9113d236e208fcb779d57b72779aa8aa71b92c98d625f61444a8713`).
  Cópia local recuperável, sem commit/push/deploy. Contrato, matriz e diário
  reconciliados para E304; próximo recorte único é E306 dentro de E300.
- [x] M0/E321: checkpoint recuperável criado antes da reconciliação; contrato,
  matriz e diário agora registram M3 fechado em E320. Naquele ponto M4/E322 era
  o próximo recorte; a auditoria E322 abaixo o concluiu e abriu E323. O snapshot
  pré-edição contém todo o WIP rastreado e não rastreado;
  veja hashes e limites no contrato e na entrada E321 do diário. Sem commit,
  push, merge ou deploy.
- [x] M4/E322-audit: mapear a identidade dos quatro povos através de geração,
  nascimento/maturação, personagem/coorte, migração, trabalho, recrutamento,
  persistência e superfícies de observação. `People` é um enum de quatro valores,
  o gerador inclui todos em cada assentamento, os owners transferem pela coorte
  preservando `people`, e DTO/UI exibem os nomes PT-BR. A bateria focal passou
  `17 passed`; detalhes e limitações no E322 do diário.
- [x] M4/E323.a: remover a correlação acidental de worldgen entre posição da
  personagem e povo do membro da organização; comprovar uma instituição mista
  em seed fixa sem selecionar membros com base no povo. `src/run/medieval_society.py`
  embaralha as pessoas elegíveis com RNG determinístico namespaced por seed e
  distribui-as em round-robin; seed 73 passou a ter organizações com composição
  mista. Novo assert no teste de worldgen; grupo focal da identidade:
  `17 passed`.
- [x] M4/E323.a-ui: listar membros nomeados no inspector como links para os
  dossiers de personagem e exibir povo traduzido PT-BR; organização sem membros
  nomeados tem estado vazio traduzido. Teste do dossier: `5 passed` e
  `npm run type-check` passou; isso cobre exibição, não alteração de filiação.
- [x] M4/E323.b: maturação de coortes para trabalho conforme os valores de lore
  autorizados: humano 15, elfo 25, anão 20, orc 12 anos (360 dias/ano). Persistir
  a duração efetivamente aplicada à coorte; provar due dates, transição material,
  save/load, rejeição explícita do schema antigo e explicação na UI. `BirthCohort`
  persiste duração e data, o evento de nascimento registra ambas, a maturação
  agendada produz delta de população, Society schema 22/save schema 81 rejeitam
  formatos antigos, e a API/inspector mostram a idade. Demografia focada:
  `3 passed`; API: `1 passed`; dossier: `6 passed`; type-check passou. Veja E323.b
  no diário para os comandos e limites.
- [x] M4/E324.a: exercitar as quatro identidades pelo mesmo caminho de mudança
  ocupacional e migração, verificando conservação e identidade de povo no
  destino. Regressão: `tests/test_medieval_society.py` → `14 passed`.
  Escopo: contrato do owner Society, sem alegar affordance/política,
  aprendizagem ou diferença fisiológica.
- [x] M4/E324.b: executar o cenário de migração material já existente para cada
  povo, mantendo a pressão observada, decisão/fallback, saldo e provisões,
  save/load, chegada e identidade no destino. O mesmo teste passou para os
  quatro valores: `4 passed`. Não adicionada regra racial.
- [x] M4/E324.c: exercitar seleção de affordance de aprendizagem e instrução
  paga para um especialista de cada povo, com habilidade equivalente e a mesma
  configuração causal. O teste parametrizado passou para os quatro povos
  (`4 passed`). A fixture posiciona personagens e registra uma chegada preparada;
  não conta como migração causal (coberta separadamente por E324.b), nem prova
  maturação, recrutamento ou elegibilidade universal a emprego.
- [x] M4/E324.d: parametrizar a decisão por affordance de trabalho remunerado
  para os quatro povos sob a mesma demanda, autoridade e recursos; confirmar
  pagamento, ocupação e causalidade, sem bônus por povo. Humano, elfo, anão e
  orc selecionaram ID oferecido num teste do provider stub; o owner pagou o
  estipêndio, concluiu a transição e preservou povo. Regressão combinada de
  workforce, Society e demografia: `59 passed`. Fixture controlada, sem provider
  remoto ou execução natural.

M4 fechado em recortes controlados no E324.d: identidade, maturação 15/25/20/12,
composição institucional, migração, instrução e escolha de trabalho dos quatro
povos têm evidência. Isso não implica bônus racial, discriminação emergente nem
prova natural; M5 é o próximo marco, sem abrir novas vertentes fora do contrato.
- [x] M5/E325: inventariar, sem alterar regras, cada Skill mágica declarada, o
  owner que executa o efeito, custos/alcance/recuperação e testes existentes;
  selecionar uma operação já prevista para fechar primeiro, registrando o que
  já está materialmente provado e o que é só skill/ritual nominal. Ritos de
  restauração e wards/contramedidas têm owners/blueprints/testes materiais;
  `elemental_magic` e `evocation_magic` existem só em `Skills`, sem operação
  medieval registrada. Os quatro módulos de ritos/alcance/política/interação
  com criaturas passaram `26 passed`.
- [x] M5/E326: implementar o rito elemental de conformação de terra para reparar
  `Passagem Negra` quando danificada: só Auren como mantenedor, com relatório de
  sítio próprio e atual, personagem presente com `elemental_magic >= 35`, 4
  reagentes + 1 cristal, 2 artesãos pagos, 6 dias, recuperação de 3 dias e
  integridade +0,10 no máximo. Usar decisão independente de oficiante e
  patrocínio, mesmo owner Map/Economy e validação de save; não reativar sítio
  interditado, não duplicar projeto de reparo, sem recurso/rota gratuito. Provar
  com contrafactual que o estado/dano corrente, custo insuficiente ou observação
  stale remove/bloqueia a opção; não criar DSL, feitiço genérico ou estado de
  mundo novo. Entregue no owner de ritos existente, com observação local própria
  do praticante, patrocínio transacional pelo caminho comum, efeito de Map,
  consumo/folha de Economy e save schema 82/Research 4. O turno de personagem e
  o patrocínio do dia seguinte selecionam IDs atuais em prova provider stub.
  Negação militar observada interrompe o rito antes da recuperação. Evidência
  E326 no diário: `94 passed`, type-check, negativos e contrafactuais controlados.
- [x] M5/E327: fixar e implementar uma manifestação evocada temporária usando
  os owners existentes, com origem causal, praticante, custos, alvo/alcance,
  duração/recuperação, efeito físico limitado e encerramento datado explícito.
  Sua contramedida precisa mudar o resultado; não substituir evocação por um
  ward apenas renomeado nem criar população, bens permanentes ou novo bestiário.
  Lei E327 fixada antes de codar: `rite-of-evoked-bulwark`, praticante residente
  com `evocation_magic >= 35`, sítio aquático local habilitado com transporte,
  proprietário/patrocinador explícito e observações próprias; 6 reagentes,
  2 cristais, 2 artesãos pagos a 2 moedas, 4 dias e recuperação de 2 dias.
  Research possui a manifestação vinculada ao rito/sítio por até 12 dias:
  absorve metade de um golpe de drake/serpente no sítio, limitado a 0,05 de
  integridade, e se dissolve nesse impacto; sem golpe, expira por agenda.
  Nenhum efeito sobre população, outros sítios ou rotas nominalmente; a lei
  hazard original continua calculando o golpe. Relatórios locais registram a
  presença visível; negação de assembleia impede a formação. Provar custo,
  seleção independente, consumo/encerramento, contrafactual, save/load e UI.
  Evidência E327 no diário: 72 testes Python, 5 testes UI e type-check passaram;
  decisões provider stub independentes, expiração e impacto com dissolução,
  dano pareado 0,05/0,10 e negação no dia de conclusão. Save 83/Research 5/
  Knowledge 11. Prova preparada, sem provider real nem emergência natural.
- [x] M5/E328: reconciliar os cinco aceites de M5 com E325–E327 e provas de
  drake/serpente, negociação/recuo, memória e resposta civil. Fechar somente
  ligações ainda ausentes; não abrir nova criatura ou escola de magia.
  Revisão inicial: quatro capacidades materiais exercitadas nos 72 testes
  E327; drake tem tributo/memória/recuo e dano com ward/anteparo. Serpente tem
  ecologia e dano civil exercitados, mas sua resposta institucional por tributo
  ainda precisa de uma trajetória focada antes do aceite agregado M5.
  Trajetória adicional executada: pedido da serpente → escolha própria de
  Auren → consumo real de alimento → memória → save/load, `1 passed in 1.06s`.
  Cinco aceites reconciliados no E328 do diário. M5 fechado por capacidades
  controladas; integração ampla/naturalidade continuam em M7/M8.
- [x] M6/E329: inventariar identidade religiosa, instituições, membros e adesão;
  fechar a primeira ligação real ausente com escolhas próprias e duas tradições
  coexistentes, sem inferir fé por povo nem criar conversão automática.
  Lei do recorte: Aurora e Coro preservam identidade/doctrina próprias. Uma
  instituição com autoridade diplomática, membro fisicamente local disponível
  e relatório próprio recente pode convidar um residente/grupo presente no
  mesmo lugar. Knowledge possui o convite local privado (válido por sete dias);
  Society possui apenas a adesão escolhida pelo destinatário, nunca deduzida
  de membership, raça ou fé da coorte. Não há ganho material, conversão em
  massa por texto ou mudança de membership/autoridade. Recusa/NO_ACTION não
  gera adesão; troca de tradição exige outro convite aceito. Provar duas
  decisões, causalidade, stale/ausência de presença, rollback e save/load.
  Owner direto, Knowledge/Society, save 84/Society 23/Knowledge 12 e API/UI
  implementados. Prova focada: 47 testes Python, teste de projeção repetido
  (1 passed), 7 testes UI e type-check. Duas tradições no mesmo cenário e escolha
  independente por API; nenhum provider/naturalidade. Menu normal ainda ausente.
- [x] M6/E330: integrar convite e resposta religiosa aos turnos concorrentes
  existentes (instituição, personagem e coorte), apresentando somente convite
  próprio/doctrina divulgada e adesão própria. Revalidar NO_ACTION/recusa,
  escolhas independentes em datas diferentes e influência na decisão posterior;
  não criar uma consulta paralela exclusiva nem converter pela política offline.
  Evidência E330: sete módulos, 58 passed; cinco provas de religião repetidas
  após contrafactual adicional. Convite institucional e resposta amanhã nos
  turnos existentes; aceitação/NO_ACTION de personagem/coorte, save/load do
  convite pendente, privacidade e doutrina/adesão prévia no contexto. Stub
  explícito condicionado à doutrina; não coerência de provider real ou emergência.
- [x] M6/E331: fechar uma cadeia religiosa de resposta social: assembleia
  observada, decisão de permitir/negar com força/custo reais e resposta
  independente da ordem/grupo/governo por mecanismo cívico existente. Inventariar
  informação já emitida pela interrupção antes de adicionar outro estado; nenhuma
  perseguição, protesto ou conversão obrigatória.
  39 testes focados passaram. Pressão material renova só observadores locais já
  presentes; dossiê mostra interferência pública com fonte, não contrato/caster.
  Grupo escolhe greve limitada ou NO_ACTION; governo escolhe levantar a negação.
  Reagentes perdidos não retornam, rito não ressuscita; save/load e história
  validados. Premissa pressionada e menus chamados explicitamente com stub;
  não trajetória espontânea ou calendário autônomo completo.
- [x] M6/E332: reconciliar oferta/participação/patrocínio/ensino dos mecanismos
  existentes com instituições religiosas e adesão; fechar somente ligação
  contratada ausente. Verificar crença versus fato/efeito na UI antes de concluir
  M6, sem criar escola de magia, cosmos ou conversão coletiva automática.
  48 testes Python, 7 UI e type-check passaram. Ordem recebe técnica por ensino
  anterior e depois oferece/negocia/cobra/ensina com decisões independentes nos
  menus existentes; aluno escolhe aceitar, nenhuma fé/matéria/capacidade nasce.
  Oferta/oficiante e patrocínio de Aurora revalidados no módulo de iniciativa.
  ResearchView/API/UI agora expõem execuções e wards reais com estágios e fontes,
  separados do catálogo/doutrina. Cinco aceites M6 reconciliados no E332 do diário:
  fechado no escopo controlado, não em mundo espontâneo ou provider real.
- [x] M7/E333: auditar e completar a navegação da cadeia religiosa/mágica no
  dossiê do personagem/instituição e why(): informação datada, decisões próprias,
  fonte e custo/resultado. Não apresentar explicação retrospectiva como pensamento
  real. Preparar a verificação humana no navegador com cadeias persistidas reais.
  - [x] E333.1: adesão própria e data no dossiê, decisão canônica própria no
    histórico e convite/decisão via why, sem decisão privada de outro ator.
    13 testes Python, 8 UI, type-check e diff-check passaram. Prova owner/API
    preparada e componentes, não navegador.
  - [x] E333.2: atividade/resultado do rito no dossiê do oficiante e patrocinador,
    preservando privacidade de estoque/conta do patrocinador na perspectiva do
    personagem. Completar fontes de custo/efeito e navegação Dao antes do browser.
    11 testes Python, 9 UI e type-check passaram. Ritual_activity mostra papel,
    início/prazo, stage e materiais planejados públicos. Resultado/decisão têm
    fonte; recibo do oficiante omite deltas de estoque/conta privados, enquanto
    patrocinador/Dao mantêm evidência completa. Nenhum contexto de ator é
    alimentado pelo observatório. E333 fechado nesse recorte, não M7 inteiro.
- [x] M7/E334: revisar cargos, atividades, objetivos e fontes nos dossiês dos
  personagens/instituições; fechar lacunas de produto sem inferir intenção ou
  conceder conhecimento de planos da instituição só porque alguém ocupa cargo.
  Preparar trajetória persistida e browser Atlas/Crônica/why/save/load.
  - [x] E334.a: projetar atividade própria, cargo/escopos/vigência e comando
    próprio; melhorar objetivos/planos PT-BR e retirar corte silencioso de dez
    fatos carregados. Provas de privacidade, ausência de fonte inventada e
    paginação: 21 Python, 8 UI, type-check e diff-check. Não fecha navegador.
  - [x] E334.b: preparar trajetória isolada e verificar navegador integrado,
    Atlas/Crônica/dossiê/why e pausa/avanço/save/load/retomada. Conferir disco
    primeiro: E334.a registrou somente 149 MiB livres; não duplicar saves grandes.
    - [x] E334.b1: build atual, dois smokes existentes de personagem/causa e
      save/load/continuar/pausar, mais navegador do rito preparado pendente →
      conclusão material no dia 10 → why com delta → reload pendente → retomada
      e mesma conclusão. Zero page errors. Somente runtime isolado local, sem
      mock HTTP; decisões iniciais de rito por API/fixture, offline depois.
    - [x] E334.b2: conectar execução ritual ao local selecionado no Atlas e
      navegar local → rito → oficiante/dossiê → why. 15 UI, build/type-check,
      browser Chromium com clique real no mapa e zero page errors. Widget
      compartilhado filtra povoado/site e preserva escolhas/receipt; não muta.
- [x] M7/E335: compor os marcos M1–M6 num cenário controlado persistido,
  reutilizando campanha/interferência/efeito civil existentes e incorporando
  povos, magia e religião com decisões próprias e disputa por recursos reais.
  Depois verificar a trajetória no observatório/Atlas/Crônica/dossiês/why.
  Não converter fixture em prova natural ou provider real nem impor atividade.
  - [x] E335.a: ampliar a trajetória controlada existente de campanha/criatura/
    efeito civil/cessar-fogo com adesão independente, povos e ritos concorrentes
    por estoque real. Sem injeção depois da linha de início. Exigir que a
    falha por falta material aponte ao consumo canônico, não só ao contrato.
    Evidência E335.a: 23 testes focados passaram; ambos os ramos preservam
    adesão independente, rito concluído/concorrente sem meios, save/load e audit.
    Cenário preparado e provider stub, sem injeção material depois do início.
  - [x] E335.b: carregar os ramos persistidos no navegador real e investigar
    Atlas → campanha/rota, local → ritos concorrentes → why e personagens.
    Reutilizar projeções/controles existentes; sem provider real ou nova física.
    Navegador real: ok=true, dia 90, zero page errors. Rito falho → consumo
    concorrente; Atlas → rota/relatório; governo → coluna sem provisões;
    controle → acordo bilateral → execução material da retirada.
  - [x] E335.c: reconciliar a composição com os aceites M1/M3 existentes e
    demonstrar aplicação tecnológica material na mesma trajetória, reutilizando
    pesquisa/ensino/treinamento existentes. Não contar catálogo como aplicação
    nem pressão econômica isolada como adaptação sustentada.
    Mesmo mundo por 240 dias: treinamento abastecido de guarnição, obra/
    fundação escolhidas pelo governo, oficina, folha e compra causal de alimento;
    dois ramos com save/load/audit ok. Browser Finanças → folha → why passou.
    Ensino prévio é premissa explícita, não nova prova de pesquisa paga.
    M7 fechado no escopo controlado E333–E335; natural/provider/finais são M8.
- [x] M8/E336: preservar checkpoint revisável e congelar fingerprints do
  código M0–M7; levantar regressões/gates ainda devidos e saldo real de consultas,
  sem apagar falhas conhecidas nem usar execução histórica stale como aceite.
  Preflight de disco: externalizar/remover somente artefatos identificados,
  autorizados e com cópia verificada; concluído em E336.h. Checkpoint documental
  local 700fede5; gate natural permanece separado e aberto em E337.
  - [x] E336.a: preservar patch/untracked e reproduzir a falha de conservação
    da migração no fechamento mensal. Diagnóstico soma receipts fora do ledger:
    perda pública de armazenamento -303, exatamente a divergência. Incluir o
    fato canônico no verificador, sem mudar recursos/lei de perdas; testar
    migração e conservação alimentar antes de congelar novo fingerprint.
    Patch/untracked verificados em /tmp/cws-e336-checkpoint-lWKBOj. Falha
    76014 ≠ 76317 reproduzida; correção somente no verificador, 2 passed.
  - [x] E336.b: validar inventário de emissores/contratos e famílias alteradas
    no candidato atual; conferir cobertura material do ledger e provas críticas
    sem declarar suíte legada verde. Gerar fingerprint após qualquer correção.
    - [x] E336.b1: cruzar inventário com o save composto dia 240 e revalidar
      o gate operacional. 86 tipos materiais/203 grupos de delta; audit ok.
      Nove premissas fixture e dois nomes dinâmicos explicam os 11 nomes sem
      correspondência estática. Quatro testes do release gate passaram.
    - [x] E336.b2: regressão final das famílias selecionadas M0–M7 e UI, no
      fingerprint atual; separar contratos obsoletos de falhas materiais reais.
      - [x] Interface medieval: 89 testes/17 módulos, build/type-check; teste
        fiscal agora seleciona o cartão pelo botão da política, não primeiro
        stock-card. Sem mudança de UI/regra fiscal. Aviso chunk >500 kB mantido.
      - [x] Backend: famílias materiais/causais selecionadas, negativos críticos,
        persistência e API; não equivale à suíte legada inteira verde.
        - [x] Autoria/engine/save/load, demografia/migração, pesquisa/indústria,
          magia/religião/dossiês: 162 passed em 17 módulos, 60.69s, E336.b2-backend-A.
        - [x] Bilateralidade, authority/Knowledge, instituição/campanha e API:
          194 passed / 2 failed inicialmente; perdas físicas de armazenamento
          explicam ambas. Corrigidos somente teste/verificador; mercados e
          preservação revalidados: 17 passed. Sem provider real nem gate longo.
    - [x] E336.b3: prévia e corpus limitado dos contratos novos/composição:
      fé sem adesão anterior, fé com memória própria, iniciativa elemental,
      evocação e menu institucional do save integrado. Reusar os turnos nativos,
      fontes intactas e receipts sem deltas; prévia não conta como provider real.
      - [x] Prévia de cinco casos passou, opções 1/1/2/2/41, fonte intacta.
      - [x] Corpus real: duas adesões anteriores e três novos casos válidos em
        E336.h. A nova autorização permitiu exatamente três tentativas sem
        retries. A falha histórica e a incerteza do transporte antigo continuam
        registradas; não reutilizamos saldo presumido da autorização E260.
  - [x] E336.c: preparar/verificar backup local em tmpfs dos quatro diretórios
    de teste E196–E199; sem cópia adicional no disco principal e sem apagar
    originais. Upload/remoção autorizados em E336.h, ainda não concluídos;
    metadata do backup remoto de 23/09 não cobre esses diretórios atuais.
    Archive SHA-256 952de40e2681d276898b23ea1575430c9da074256fe35644c95489660c47d557;
    tar --compare passou. Cópia tmpfs não é persistente nem backup externo.
    - [x] Upload autorizado e verificado, seguido de remoção somente dos quatro
      originais identificados; só então preflight das três seeds finais.
      E336.h: quatro partes + manifesto em `/VPS Backups/`, todos completed e
      content_hash remoto idêntico ao local. `tar --compare` repetido exit 0;
      hash completo intacto. Somente E196–E199 removidos (2.936.693.295 bytes
      lógicos), recuperáveis pelo backup. Disco após limpeza: 9.0 GiB livres.
  - [x] E336.d: reconciliar caixa M1 com o aceite controlado explícito E282 e
    registrar UI/browser verificados em M8, sem converter essas provas em
    adoção natural, provider completo ou validação de dez anos.
  - [x] E336.e: preservar fonte/configurações ficcionais/testes/UI e scripts de
    navegador em commits locais revisáveis; registrar hashes e exclusões
    geradas, sem publicar branch ou alegar M8 concluído.
    Código: 5b4b5227, 109 arquivos, cached diff-check passou; screenshots e
    estado do runner permanecem locais. Documentação acompanha separadamente.
  - [x] E336.f: revalidar famílias materiais alteradas restantes fora dos
    grupos A/B antes de congelar M8: alfândega, aprendizagem/trabalho,
    embargo/intriga/propriedade e consumidores militares/mágicos adjacentes.
    Reusar módulos existentes; registrar falhas reais sem novos smokes longos.
    204 passed em 16 módulos, 75.65s; candidato congelado c13f4e/source 5b4b5227.
    Não fecha provider, gates naturais ou publicação.
  - [x] E336.g: permitir selecionar somente os três casos provider pendentes,
    com teto por tentativa sem retries e prévia sem egress. Testar o guard com
    cliente falso, preservar fonte/configuração e registrar fingerprint da
    ferramenta, sem nova consulta ou alteração da engine congelada.
    5 testes passaram e preview dos três casos completo, 0 egress. Commit local
    4f1df5f0; fingerprint global 1c2e7f, runtime/src/static/UI sem alteração.
  - [x] E336.h: executar as três novas consultas autorizadas ao Luna
    (elemental, evocação e composição), sem retries; enviar o arquivo E196–E199
    a `/VPS Backups/`, verificar a cópia remota e somente então remover os
    quatro diretórios originais explicitamente autorizados. Registrar tentativas,
    preservação do save, resultado do upload e espaço efetivamente recuperado.
    - [x] Provider: três tentativas sem retries; elemental/evocação selecionaram
      ofertas atuais (2 opções cada), composição selecionou relief entre 41
      opções. Receipts sem deltas; owners geraram 11 eventos materiais apenas
      no fork composto. Hash do save original preservado. Upload multipart
      e manifesto verificados; remoção somente dos quatro diretórios autorizados.
  - [ ] E337: após backup e preflight, executar `medieval_release_gate.py`
    com seeds 73/101/137, 3600 dias, checkpoints anuais e `--final-v1`, no
    fingerprint congelado 1c2e7f. Registrar cada seed, auditorias, conservação,
    retomada e budgets sem relaxá-los; offline não conta como provider real.
    Gate reprovado por orçamento no candidato 1c2e7f: até mês 94 já havia sete
    amostras acima de 35s; portanto o p95 de 120 amostras necessariamente excede
    o teto. Processo encerrado após checkpoint anual 2880 seguro, exit 143;
    não considerar execução incompleta como gate final nem relaxar limites.
  - [ ] E338: perfilar um horizonte de 30 dias em cópia de memória do checkpoint
    natural 2880, sem provider/reescrita do save. Reutilizar o profiler existente,
    identificar o maior custo antes de alterar fonte e provar equivalência da
    otimização com testes focados. Novo candidato exige novas três seeds completas.
    - [x] Medir baseline: 43.400713s instrumentados; cópia 11.663214s.
    - [x] Auditar fonte preservada: 125.148 eventos, `ok=true`, exit 0.
    - [x] Regressão focada: 67 testes de cópia/engine/material/persistência.
    - [x] Comparar snapshot/RNG/história completa em dois experimentos de
      30 dias; ambos idênticos, saves originais intactos.
    - [x] Rejeitar frozen-leaf sharing: benchmark alternado de cinco amostras
      por variante mostrou CPU 0.093646s → 0.103338s por cópia (regressão).
    - [ ] Provar ganho no candidato restante e custo mensal aceitável antes
      de repetir as três seeds; equivalência dos experimentos não fecha budget.
    - [x] Retirar também o fast path de primitivos sem ganho comprovado.
      Fonte restante apenas isola payloads extras/privados; cinco testes passaram.
    - [x] Medir custos agregados sem cProfile por valor: mês 34.38s, cópia
      7.22s, relações 5.74s, economia 4.47s; fonte preservada.
  - [x] E339: discriminar o custo real da cópia durante o mesmo horizonte
    natural 2880→2910 por owner/Map/rebind de Knowledge, sem profiler por valor
    ou alteração de física. Corrigir só o custo dominante identificado, provar
    isolamento/rollback e equivalência da história antes de novo candidato M8.
    - [x] Medição por owner concluída: RelationsState concentrou o custo da
      cópia em dois outliers; Map/rebind são pequenos. Fonte preservada.
    - [x] Correlacionar picos ao GC sem alterar thresholds: 5.85s de CPU
      coletando ciclos, duas varreduras geração 2, fonte intacta.
    - [x] Eliminar referência forte de registry ao KnowledgeState, preservando
      epochs/deepcopy/rollback; medir efeito e comparar história/snapshot/RNG.
      80 testes focados passaram; estado, RNG e 126.201 eventos idênticos.
      Coleta geração 2: 45.930→0 objetos. Tempo 88.50→31.39s sujeito a carga;
      relatório completo, exit code do comando não recuperado após retomada.
  - [x] E340: continuação natural offline 2880→3060 no candidato E339,
    sem alterar o save original. Seis meses medidos, conservação/save-load e
    auditoria; evidência tardia limitada, não substitui o gate final 3×3.600 dias.
    - [x] Conservação, save/load + continuação e auditoria passaram, exit 0;
      131.559 eventos, original intacto, sem provider real.
    - [ ] Performance aceitável: reprovada, p95 limitado 69.4166s >35s;
      pressão de host observada, sem atribuição exclusiva ou relaxamento.
  - [x] E341: perfil em memória de 30 dias após o sucessor 3060, sem provider
    ou nova física, para discriminar custo restante antes de repetir gates.
    Exit 0, fonte intacta, 3060→3090/132.631 eventos. Cópia 18.46s, relações
    17.70s, buscas de causas de rota 6.41s e concessões 5.69s (instrumentados,
    cumulativos sobrepostos). Próximo recorte: somente busca de causas de rota,
    sem substituir validação integral por cache de consulta.
  - [x] E342: indexar apenas a proveniência consultada das rotas sobre o ledger
    append-only, sem persistir cache nem usar o índice para aprovar integridade.
    Provar equivalência com a busca anterior, atualização por append/substituição
    do último evento, isolamento de candidato e ganho medido no save tardio.
    47 testes do recorte e 49 de migração/persistência passaram. Causas iguais;
    50 consultas: CPU 4.046743→0.000666s; cold quase igual. Par natural
    3060→3090 preservou snapshot/RNG e 132.631 eventos, CPU 30.28→29.57s.
    Não equivale a budget final aprovado; corpus real não foi repetido.
  - [ ] E343: novo gate final natural 73/101/137 ×3.600 dias, sequencial,
    checkpoints anuais, fingerprint bdffc18991756f621881ea12cc80ca1fe3136040814779695381711913f7eba9.
    Fonte congelada; nenhuma nova alteração durante execução. Conservação,
    auditoria, save/load/continuação e budgets originais precisam passar todos.
  - [ ] E344: revisão final de conclusão contra o contrato, sem mudar fonte
    durante E343. Vincular requisitos M0–M7 aos recortes e regressões atuais,
    distinguir fixture/offline/provider/natural e fechar M8 apenas com relatório
    integral, fingerprint estável e autoridade/evidência de entrega.
    - [x] Revisão read-only dos contratos de seleção, execute_material e
      persistência: ID enumerado/NO_ACTION, execução em candidato, validação
      antes de publicação e caches excluídos do snapshot.
    - [x] Regressões apropriadas registradas: E336 backend A inclui magia,
      demografia e religião; B inclui bilateralidade, campanha e API; C inclui
      consumidores tecnológicos/criaturas. E339/E342 revalidam alterações
      transacionais/de consulta posteriores; não afirmar suíte legada inteira.
    - [ ] Resultados completos E343, adaptação observada e limites operacionais.
    - [ ] Entrega remota conforme autoridade vigente, backup e smoke implantado.
- [x] M0/E332: preservar patch binário e arquivos não rastreados do checkpoint
  que fecha M6, com hashes verificáveis em /tmp, sem apagar/alterar os anteriores
  nem publicar dados. Registrar limites de commit/push e inventário do WIP.
  `/tmp/cws-e332-checkpoint-BBa3yR`: worktree.patch SHA-256
  `87ef50b2eb464672c8c705744e5ac179684706e871c302d15e8e67bac82a9394`;
  untracked.tar.gz `cc3d77a4711f52a9954696a43f8f4a47e6a3616a623c9416dd893f8d13bcb72a`.
  Reverse apply --check passou sem aplicar; tar listing confirmou 17 arquivos.
  102 caminhos no WIP; snapshot antecede apenas esta anotação de hashes/check.
- [x] M0/E325: preservar snapshot local do WIP ao fechar a auditoria mágica.
  Branch `codex/medieval-remote`, HEAD `3c6e590e`, 67 caminhos no worktree;
  patch `/tmp/cws-medieval-e325-20260929.patch` SHA-256
  `4cb0ea6cc857c1b0225fec90f2e882315e0d1dbe2b1bfba1d51e6aa8e0a50e02` e tarball
  dos cinco untracked SHA-256
  `c87c26cb537aa02f841150dcb3dfe88ffae57ebb721fff83f300f07d714b05b1`. Local,
  sem commit/push/merge/deploy.
- [x] M3/E303: pré-posicionar artilharia/pólvora em bagagem de força presente
  por Freight comum, usando relatório atual do QG, antes de o ator investir o
  assentamento; depois iniciar cerco e consumir pólvora em bombardeio. Investir
  fecha a rota e invalida a escolha anterior sem mutação parcial. Evidência no
  diário; é cenário preparado com estoque-premissa e API, não fecha produção
  real→campanha, provider/naturalidade ou E300 completo.
- [x] M3/E304: ligar output de linhas pagas de produção ao estoque de origem
  realmente despachado para a bagagem da mesma instituição e força; a prova
  precisa percorrer produção → estoque/causa → rota conhecida → Freight → cerco
  → consumo, sem equipamento-premissa e sem misturar proprietários. A prova
  integrada `test_paid_mineral_separation_feeds_gunpowder_research_and_two_real_lines`
  conclui em E304; tropa/defensor são premissas explícitas da fixture. Continua
  aberto o restante de E300 (rota interrompida, equipamento ao mover/dissolver,
  provider real quando disponível e contrafactual pareado).
- [x] M3/E306: cobrir a interrupção de uma rota depois da partida de artilharia
  por Freight e sua retomada após decisão independente de levantamento. A carga
  permaneceu em trânsito, `cargo_delayed` citou a interdição e conservou
  quantidade/entrega zero; depois da abertura, `cargo_delivered` passou a citar
  a causa corrente da rota e a cadeia chegou ao disparo do mesmo cerco. A
  fixture declara a permanência da coluna como premissa; o teste é separado da
  integração de produção paga E304 e não prova por si só a emergência natural.
  Regressão: artilharia, logística e interdição, `21 passed`; `git diff --check`
  limpo. E300 continua aberto para contrafactual pareado e provider real quando
  disponível.
- [x] M3/E307: mover bagagem de artilharia/pólvora com a retirada real de uma
  coluna e dissolvê-la depois, preservando o estoque no destino, sem duplicação
  nem perda tácita. A marcha/chegada agora também cita os eventos causais da
  rota atravessada. A prova round-trips save/load e passa `validate_history`.
  Incluída na regressão focada de campanha/cerco, logística e interdição:
  `44 passed in 21.05s`; `git diff --check` limpo.
- [x] M3/E308: comparar duas cópias do mesmo estado com ambos os fretes já em
  trânsito: rota aberta entrega no prazo e permite investimento/cerco/disparo;
  interdição atrasa as duas cargas, impede investimento e cerco naquele prazo,
  e não altera endurance por bombardeio. Round-trip no estado interditado,
  depois levantamento, entrega e disparo no ramo de intervenção; auditoria nos
  dois ramos. `provider_available()` retornou `False`, sem egress; não houve
  consulta externa. A prova de produção paga de E304 foi revalidada separada.
  Aceite E300 limitado: E304 `1 passed`, regressão E306–E308 `44 passed`,
  `git diff --check` limpo. Cenário preparado, não emergência natural ou
  provider real; M3 permanece aberto para outras capacidades.
- [x] M3/E309: cruzar os requisitos de M3 (conservação, aço, vapor, pólvora,
  artilharia, logística, barreiras, doutrina, difusão, intriga, compromissos,
  comércio e patrimônio produtivo) com owners e testes existentes. Quatro grupos
  focados passaram: indústria/preservação/barreiras/treino/difusão `38 passed`;
  diplomacia/intriga/tarifas/embargo/logística/comando/conveyance `96 passed`;
  alfândega/contratos/ajuda/memória diplomática `72 passed`; migração/ensino
  aplicado `10 passed`. A auditoria achou que E138 exercita a paliçada com
  conhecimento introduzido por `learn_technology`, não pesquisa paga nem ensino
  bilateral; o próximo elo é tornar verificável uma rota legítima de aquisição
  de `defensive_barriers`, sem chamar conhecimento inserido diretamente de
  pesquisa executada. Limites: provas em cenários controlados, não ocorrência
  natural ou provider real. E309 não fecha M3.
- [x] M3/E310: o breach conhecido de ensino gera memória direcional; numa nova
  proposta equivalente, o provider de teste recebeu a memória no prompt canônico
  e escolheu rejeitar, enquanto a cópia sem histórico escolheu aceitar. A
  engine/owner executou respostas diferentes, sem texto como causa nem deltas
  do receipt LLM. O menu também expôs renegociação e remediação de breach; a
  primeira passagem revelou e corrigiu `_choice` para os dois tipos de opção
  sem `action`. Dois testes de aceitação passaram; regressão de diplomacia,
  memória e indústria `62 passed`; `git diff --check` limpo. Provider é mock
  local; nenhum egress. M3 permanece aberto.
- [x] M3/E311: pesquisa paga de `defensive_barriers` por Auren no site próprio
  `passagem-negra`, com consentimento independente do pesquisador, consumindo
  seis ferramentas e pagando folha; depois a obra paga em Pedra Clara consome
  materiais/trabalho e cita o evento da pesquisa como causa. A cadeia prévia
  `field_drill` → `siegecraft` → `fortification` é premissa declarada da fixture;
  não prova sua pesquisa emergente. Round-trip save/load passou. Regressão
  focal de barreira, pesquisa e indústria: `38 passed`; `git diff --check`
  limpo. Efeitos de cerco seguem nos testes separados anteriores; não houve
  provider nem egress.
- [x] M3/E312: o teste integrado da cadeia aço/vapor agora seleciona
  metalurgia, aço e engenharia a vapor pelas affordances correntes; pesquisador
  aceita separadamente. A pesquisa conclui antes de fornos/linhas consumirem os
  materiais e máquinas correspondentes. Recursos, carvão inicial, linhas-base e
  instalação são premissas preparadas; não prova surgimento natural. Regressão
  focada indústria/pesquisa/barreira: `38 passed`; `git diff --check` limpo.
  HEAD-base `3c6e590e`; SHA-256 do arquivo alterado:
  `52dca9d537148961d126a2bd9eef108e2e8da94b42b67807f10c8826ec28b807`.
- [x] M3/E313: registrar transferência produtiva bilateral no turno mensal
  existente. O vendedor aparece no menu composto; oferta recém-escolhida gera
  depois uma consulta limitada à contraparte, independente e ligada à decisão
  do vendedor. Teste prova transferência e owner de produção; sem broker ou
  estado de planner.
- [x] M3/E314: Observatório `/api/v2` e `why()` mostram transferência produtiva
  real, tarifas, embargo/recusa e alfândega/contrabando pela superfície genérica
  já existente; sem UI ou projeção paralela. E314a/b abaixo registram evidência
  e limites. Dossier de ator continua limitado a conhecimento próprio.

Atualizada em 29/09/2026. No início de E286, o checkout estava limpo em `3c6e590e`; E286–E314 deixam alterações locais não commitadas. O checkout agora usa save schema 80, Economy schema 20 e Knowledge schema 10; saves anteriores continuam rejeitados sem migração. A referência remota não foi consultada nesta rodada. Esta matriz acompanha o contrato vigente, o diário de evidências e o roadmap. `Verificado` vale somente para o recorte descrito; `Existente` não comprova o aceite amplo; `Lacuna` indica prova ou implementação ausente. E1–E243 estão registrados antes deste adendo; E256–E282 documentam o corpus e os recortes econômicos; E284–E314 registram recortes recentes de campanha, difusão tecnológica, conservação alimentar, pólvora, decisão diplomática por memória, aquisição canônica de tecnologia, transferência produtiva e observabilidade causal de eventos materiais. E244–E255 foram classificados individualmente no diário E266 quando havia artefatos recuperáveis; E244, E246 e E250 não têm output reproduzível. E222, E225, E228 e E230 não produziram decisão live do provider.

## Checklist de execução

- [x] Recriar saves/fixtures carregáveis no schema atual por caminhos canônicos
  e passar preview sem egress para dez contextos situados (`E256`). Os smokes
  de 480 dias são rotina offline; não fecham saúde adaptativa nem Gate D.
- [x] Exercitar seleção real OAuth/Luna em campanha, criatura, QG e oito
  decisões civis; IDs selecionados pertenciam aos menus correntes e receipts
  LLM não carregaram deltas (`E257`, `E259`, `E260`). Uma resposta válida
  inicialmente revelou falha no owner de criatura, corrigida em `E258`.
- [x] Corrigir a fonte de percepção de carga da demanda de criatura e passar
  testes focados/adjacentes (`E258`, `E261`).
- [x] Gate B, response capability em estado atual: escolha API por affordance
  de relief removeu 223 de falta alimentar, transferiu exatamente 223 rações
  às famílias e alterou saúde/unrest via owner (`E263`). Clone auditado; fonte
  intacta. Não demonstra adoção natural nem adaptação estrutural.
- [x] Gate B, localizar o bloqueio do recorte de oficina: chegada material de
  madeira confirmada, mas projeto ficou `blocked/payroll_funds`; a trajetória
  offline também entregou alimento no controle e intervenção (`E264`). Não
  atribuir efeito diferencial à oficina.
- [x] Gate B, auditar os dois saves de continuação no dia 1.110 (`E268`): ambos
  passaram a auditoria causal; a trajetória com cortes de vínculos agrícolas,
  oficina e produção terminou com saúde 498/falta 302 contra saúde 571/falta 0
  no controle. Os ramos não têm o mesmo checkpoint inicial nem isolam uma única
  decisão; é evidência negativa exploratória, não contrafactual causal limpo.
- [x] Gate B, executar contrato de emprego local versus controle desde o mesmo save
  do dia 930, sob a mesma política offline por seis ciclos (`E269`). A escolha
  API foi uma affordance atual em Campomanso para 31 artesãos orcs, folha bruta
  62/ciclo. A cadeia pagou salários e chegou a compras familiares/subsistência;
  no dia 1.110, falta caiu 302→237 e saúde subiu 498→511, mas falta 237 persistiu.
  Primeiro ciclo piorou (398→434), depois cinco foram iguais/melhores; não houve
  provider, adoção natural ou prova de equilíbrio. Estoque público terminou
  17.679→17.316, então acompanhar custo/estoque segue necessário.
- [x] Gate B, rastrear a falta residual de Campomanso no dia 1.110 por grupo
  (`E270`). `unmet_by_group` soma 237: sobretudo 166 anões agricultores e 54
  humanos artesãos; os grupos sem saldo não tinham opção de compra doméstica.
  Nenhum empregador tinha affordance local de contratação: o caixa de Auren era
  2.223 contra compromissos permanentes de 2.432/ciclo. Não havia folha impaga
  vigente nem pedido/offer de empréstimo familiar; opções de staffing atuais
  apenas reduziam contratos existentes. Conclusão limitada ao checkpoint: a
  próxima resposta exigiria realocação explícita de folha/renda; relief não é
  contabilizado como solução estrutural.
- [x] Gate B, inventariar opções de staffing e pressão que as habilita (`E271`):
  Auren tem caixa 2.223 e folha permanente 2.432/ciclo; uma opção vigente em
  Ponte Negro reduz o contrato humano agricultor 180→90, economizando 360/ciclo.
  O grupo tem 5.584 de caixa e nenhuma falta no fechamento local (mas 90 pessoas
  perderiam esse vínculo). A causa habilitante é `production_limited` da oficina
  de Campomanso (`payroll_funds=0`). Essa redução deixaria a conta em 2.072/ciclo,
  suficiente para uma contratação local de artesãos humanos de 54/ciclo caso a
  oferta continue válida. É oportunidade com custo distributivo, não aceite.
- [x] Gate B, comparar a realocação de staffing com controle por seis ciclos
  desde o mesmo save do dia 1.110 (`E272`). Só a intervenção recebe a decisão
  API de reduzir o vínculo humano agricultor de Ponte Negro 180→90 (economia
  nominal de 360/ciclo); depois ambos usam `routine-rules`, sem novos atos
  injetados. O fallback estabelece emprego para 27 artesãos humanos em ambos:
  dia 1.200 controle (`event:46647` decisão fallback → `event:46648` contrato),
  dia 1.230 intervenção (`event:47813` → `event:47814`). No dia 1.290, a coorte
  agricultora humana de Ponte Negro tinha caixa 5.171/2.180 e contrato 180/90;
  a falta acumulada nas seis leituras por todas as cidades foi 13.785/13.840
  rações, e a coorte de agricultores anões de Ponte Negro acumulou 135/207
  rações não acessíveis. A produção acumulada no recorte em Campomanso/Ponte
  Negro foi 61/27 lotes no controle e 87/65 na intervenção; mortes por privação
  acumuladas terminaram 192 em ambos. O aumento de produção e a melhora do
  último fechamento (falta mundial 481→387; Ponte Negro 96→0) coexistem com
  falta mais alta em checkpoints anteriores e +55 rações de falta somadas nas
  seis leituras. Resultado: intervenção causal e auditável, mas não satisfaz
  adaptação sustentada nem ausência de transferência de privação. Não marcar
  M1 concluído.
- [x] Gate B, recompor menu após E272 (`E273`, consulta read-only): em ambos os
  ramos, Auren enumerava só uma nova vaga em Campomanso, 3 artesãos anões a
  salário 2; havia 42 reduções de staffing, zero pedidos de empréstimo familiar,
  zero prioridades de produção e duas affordances de alívio agudo (15 e 7
  rações). Não havia vaga para agricultores no menu vigente. `household_provision_options` não é compra
  alimentar cotidiana: só prepara estoque pré-pago para migração; consumo e
  compras do ciclo pertencem ao owner de subsistência. Isso vale para o snapshot
  final d1290, não prova ausência de opções em outras datas.
- [x] Gate B/M1, resposta material viável em cenário preparado (`E208`, `E277`,
  `E282`): crédito familiar voluntário paga folha e salário, prioridade direciona
  caixa compartilhado sem criar produção, e decisão separada de relief move
  alimento público apenas a grupos com ração não atendida. E282 sustentou a
  resposta por seis ciclos contra seu controle, sem aumentar falta nos outros
  assentamentos nem alterar moeda; testes de relief validam que a distribuição
  não debita outra coorte. Aceite limitado a este cenário, sem provider ou
  emergência natural; Gate B natural continua aberto em M8.
- [x] Gate B/E274, experimento completo, mas não aceito como recuperação estrutural:
  avaliar primeiro e, se a lacuna se confirmar no contrato,
  estender o crédito voluntário existente para uma instalação de alimento cuja
  única limitação atual seja `payroll_funds`. Limitar a um lote financiável,
  credores locais independentes com reserva de alimento, sem produção automática
  ou expansão para crédito genérico; comparar por seis ciclos e auditar qualquer
  efeito sobre quem empresta e quem recebe salário/alimento.
- [x] E274.a confirmou que o contrato antigo só aceitava receipt de salário
  permanente impago. O mesmo fluxo agora aceita `production_limited` alimentar
  sob limite exclusivo de folha, para um lote, sem reserva/produção automática;
  os 38 testes focados de empréstimo/observatório/persistência passaram,
  rejeitando saves 76/77 e Economy 18/Knowledge 9. A comparação
  emparelhada E274.b concluiu sem evidência de benefício sustentado. Seed 73,
  dia 270→450, seis ciclos: fonte `event:8158`, alvo `works:campos-do-lume`, um
  empréstimo API de 40 de `pop:campomanso:orc:farmer`; reserva alimentar do
  credor preservada e dinheiro total 76.000 nos dois ramos. Alvo produziu 30
  batches em ambos; falta final 364 controle/427 intervenção; produção alimentar
  total 25.400/21.300; empréstimo ainda ativo no vencimento. O histórico divergiu
  (16.394/16.017 eventos), então os deltas totais são evidência de uma trajetória,
  não uma estimativa generalizável. A affordance não fecha adaptação M1.
- [x] E274.b executado com a ferramenta reproduzível a partir de uma fronteira
  natural no schema atual; nenhum save antigo foi carregado ou alterado.
- [x] E275, rastrear em clone seed 73 a aplicação das 40 moedas até a produção
  do dia 300. `treasury:auren` é compartilhado por três fazendas: o controle
  produziu 28 lotes em Pedra Clara, 3 em Ponte Negro e 0 em Campos do Lume; a
  intervenção produziu 29, 3 e 0. O extra foi 100 alimentos em Pedra Clara;
  quando o alvo foi avaliado, restavam 22 moedas frente ao custo de 40 por lote.
  Trabalho (87), capacidade, integridade e armazenamento não limitavam. A
  affordance permanece somente como crédito fungível de folha alimentar, sem
  promessa ou reserva de instalação; contexto do credor e rótulos passaram a
  declará-lo. Falta agregada do fechamento foi 129 nos dois ramos. Ver E275 no
  diário; nenhuma mutação ou save original foi feito.
- [x] E276, recompor `production_priority_options` de Auren no source day 270 de
  E275 (`event:8158`): menu vazio. O alvo Campos do Lume não tem concorrente na
  mesma cidade/ocupação, embora três fazendas de assentamentos diferentes usem
  `treasury:auren` e disputem caixa na rotação do próximo ciclo. A affordance atual
  só deixa o ator ordenar conflito local de trabalho; não representa esse
  conflito de caixa entre cidades. Sem decisão injetada ou provider neste recorte.
- [x] E277, prioridade de uma instalação entre as próprias que compartilham
  payroll account, ofertada apenas por receipt atual limitante de folha. No
  contrafactual API seed 73, escolher Campomanso colocou sua instalação primeiro
  no dia 300 e produziu 22 lotes; Pedra Clara e Montenegro receberam 9 e 1, em
  vez de 29 e 3 no ramo só com empréstimo. O total do pool não subiu e a falta
  permaneceu 129 no mundo/6 em Campomanso; não houve earmark nem recursos novos.
  A affordance fecha a lacuna de decisão sobre precedência, não a adaptação do
  acesso. Gate B continua aberto.
- [x] E278, trace do dia 300: Campomanso ficou com 41.600/43.000 de alimento,
  preço 1; 1.095/1.101 rações foram compradas. Os seis grupos com falta eram
  soldados sem saldo e uma dependente sem conta. Auren tinha opções atuais de
  relief por 6 ou 3, apoiadas pelo próprio estoque e relatório; não há patch de
  economia. E279 verificará essa affordance em clone.
- [x] E279, a decisão API no clone distribuiu 6 rations do estoque de
  Campomanso para cinco pantries (1/1/1/2/1); receipt ligado à decisão,
  relatório e falta; dinheiro conservado. Até dia 330, pantry foi consumida,
  mas falta local ficou 0 versus 6 no controle, health +12/unrest -12. Prova uma
  resposta causal por ciclo, não sua escolha autônoma ou sustentação secular.
- [x] E280, continuidade offline até dia 330 sem resposta API: não há receipt de
  relief; falta local 6 e opções atuais 6/3 permanecem. O fallback determinístico
  exige shortfall ≥20, então ignora a opção e não registra decisão/NO_ACTION.
  `ai_enabled=false`; isso não prova o que provider real escolheria.
- [x] Gate B/E281 diagnóstico de renda e acesso (read-only): rastrear contas,
  payroll, empregos/transições, salário militar, maturação e relief nos owners
  atuais para as coortes de E278. A lacuna não é falta de affordance de relief:
  grupos sem renda própria não têm renda recorrente salvo trabalho efetivamente
  pago; dependentes não recebem emprego permanente e o modelo não relaciona seu
  saldo ao de adultos. Nenhuma nova ação/dinheiro foi criado. Ver E281 no diário;
  o aceite de adaptação sustentada continua aberto.
- [x] Gate B/E282 experimento controlado: seis menus compostos mensais em clone;
  Auren/Campomanso escolheu relief vigente em 4 deles (1.759 rações). Contra
  API `NO_ACTION`, falta local `791→0`, sem falta adicional nos outros
  assentamentos, com moeda conservada. Contra o fallback offline pareado, porém,
  o recorte de ator único terminou com falta agregada 5.823 versus 433 e suprimiu
  18 reliefs que a política offline aplicou aos demais atores. O ramo de ator
  único não é comparação de política sistêmica; ainda assim, contra seu próprio
  controle pareado, a resposta local foi sustentada por seis ciclos. Com o
  contrato do owner testado em `test_relief_only_reaches_households_with_unpaid_rations`,
  isso fecha somente o aceite preparado de M1. Zero egress; validações e 42
  testes focados passaram no checkout atual. O gate natural de M8 segue aberto.
  Ver E282 no diário e a revalidação focal desta execução.
- [ ] Registrar e revisar individualmente E244–E255 no diário versionado; os
  artefatos existem localmente, mas seu histórico detalhado não foi sincronizado.
- [ ] Gate B natural: demonstrar capacidade adaptativa e rastrear a cadeia
  econômica completa no checkout estabilizado.
- [ ] Gate C natural integrado: observar política/QG/comandante e consequência
  econômica/social reagindo a interferência ambiental sem decisão injetada.
- [ ] Gate D final: três seeds naturais por 3.600 dias no checkout final, com
  checkpoints, conservação, save/load/continuação, auditoria e budgets.

- [x] Economia pós-V1: empréstimo familiar voluntário com autoria do pedido,
  aviso local e escolha do grupo, transferência sem criação de dinheiro,
  obrigação persistida, vencimento/reembolso independente e save/load (`E201`).
  O aceite é apenas fixture preparada; escolha espontânea e efeito natural
  continuam abertos.
- [x] Uma consulta direta Codex OAuth/Luna escolheu um ID válido do menu
  familiar em fixture (E202); não executou a ação nem substitui o corpus do
  provider no runtime.
- [x] Uma consulta adicional passou pelo `ai_decider.select_option` real e
  gravou receipt LLM zero-delta para ID oferecido, sem execução material (E203).
- [x] Preflight natural com Luna seed 73 até dia 30: zero gatilho/loan; teto de
  20 chamadas alcançado no início do passo seguinte, sem commit (E204). Não
  fecha adoção natural nem tem auditoria/save-load.
- [x] Preflight offline até dia 480 encontrou receipt de folha sem fundos, mas
  sem opção de empréstimo após recuperação do tesouro; conservação, save/load e
  auditoria causal passaram (E205). Não mostra recusa nem empréstimo natural.
- [x] Dois preflights offline adicionais até dia 480 reproduziram recibos de
  folha sem opção de pedido no turno (E206); são diagnóstico de timing, não
  evidência de recusa ou adoção.
- [x] Pedidos familiares aceitam vários credores voluntários, limitam cada
  contribuição ao saldo restante, mantêm avisos dos demais durante o
  financiamento parcial e fecham somente ao cobrir o principal; fixture de duas
  famílias e save/load passaram (E207). A adoção espontânea continua aberta.
- [x] Crédito familiar em fixture pareada paga materialmente a próxima folha e
  remunera a coorte; o controle sem empréstimo permanece sem fundos (E208).
  Isso prova eficácia possível do mecanismo, não decisão/adoção natural.
- [x] Após o bump para schema 76/Economy 18, saves schema 75 seguem rejeitados
  sem alteração dos bytes, Economy 17 é recusado e a consulta observacional usa
  save/load do schema atual (E209).
- [x] Smoke natural offline atual: seed 73 por 480 dias em schema 76, quatro
  checkpoints com conservação/save-load e auditoria final limpa; saúde média
  865, falta alimentar acumulada 1.148 e zero mortes por privação (E210).
  Resultado curto não fecha adaptação econômica natural nem gate de dez anos.
- [x] Continuação natural do mesmo save até dia 600: auditoria/conservação e
  save/load passaram. Os receipts de folha sem fundos persistiram, mas a conta
  de Escarlia já cobria as folhas agregadas no checkpoint do dia 510, então não
  existia affordance de crédito válida. Sem pedidos/empréstimos; soma de falta
  alimentar nos quatro meses: 3.244, contra 1.148 em 16 meses no E210 (janelas
  diferentes); saúde média final 775,75 (E211). Não demonstra
  escolha familiar nem resolve o diagnóstico da pressão doméstica.
- [x] Diagnóstico causal read-only no dia 600: 158.613 alimentos em estoques
  públicos para 10.879 moradores; falta mensal 815. Escarlia mostra folha
  comprometida 3.626 versus caixa 2.661, e opções atuais para reduzir/suspender
  compromissos após falha de payroll; 30 opções válidas foram recompostas com
  relatórios datados. Artesãos concentram os saldos domésticos mais baixos na
  projeção do Dao. Nenhuma affordance foi executada; projeção não é conhecimento
  do ator (E212). Ainda falta provar escolha independente de provider/política.
- [x] Contrafactual pareado E213/E214 suspende um vínculo por decisão API:
  reduziu a falta comparável 846→681. Corrigido e testado o elo decisão → pausa
  → produção do mesmo caixa/dia → salários; no save pareado, `why()` também
  alcança compras e subsistência. Os dois ramos no dia 638 passaram auditoria
  causal completa. É intervenção explícita, não decisão espontânea/provider;
  efeito natural e autonomia econômica continuam abertos.

- [x] E215 avançou os dois ramos por mais 120 dias, sem nova escolha injetada;
  save/load, conservação e auditorias causais passaram no dia 758. A divergência
  posterior não pode ser atribuída somente à pausa inicial. Estoque público
  elevado coexistiu com falta por incapacidade doméstica de compra em Cinzaverde;
  a trajetória permanece economicamente pressionada.
- [x] E216 consultou Codex OAuth/Luna com o menu mensal atual de Escarlia; o
  provider selecionou o ID canônico para construir oficina em Cinzaverde. Nenhum
  owner foi executado e não houve receipt persistido ou save. Escolha real
  confirmada, cadeia material após a escolha ainda aberta.
- [x] E217 reproduziu a resposta E216 somente numa cópia: o menu foi recomposto,
  o ID revalidado, o receipt LLM permaneceu sem delta e o owner canônico abriu
  projeto `waiting`. Save/auditoria causal passaram. Não houve nova consulta,
  consumo material ou avanço do projeto; conclusão, linha, salário e efeito
  alimentar continuam abertos.
- [x] E218–E221 seguiram apenas a cópia: política offline criou pedido e aceite
  bilateral de 48 madeiras com rota/frete material; a oficina passou por falta
  real de insumo e pausa temporária de caixa, depois concluiu no dia 960. Quatro
  auditorias causais passaram. Não houve decisão live do provider para comércio;
  ainda faltam linha, produção, renda familiar e efeito alimentar.
- [x] E222 preparou o menu completo atual (76 affordances, prompt local de
  53.860 bytes) e iniciou uma consulta Codex OAuth/Luna. Após mais de dez
  minutos sem resposta/log/receipt, o processo foi interrompido; não houve
  mutação nem save. A tentativa está registrada, mas não conta como decisão ou
  evidência de escolha. Não repetir automaticamente.
- [x] E223 diagnosticou o client sem rede: prompt de 53.860 bytes, OAuth CLI
  local autenticado, timeout nominal de 180s e três retries de parse. A causa
  do travamento não foi identificada; login saudável não é prova de latência
  ou resposta do provider.
- [x] E224 reproduziu e corrigiu o escape de subprocessos descendentes no
  timeout do Codex CLI; teste focal `3 passed`. Isto não explica E222 nem
  substitui uma decisão real ou fecha Gate B/D.
- [x] E225 repetiu uma consulta limitada no clone E221 usando configuração
  OAuth/Luna temporária; continuou sem retorno por mais de sete minutos e foi
  interrompida. Nenhum save mudou. Provider real e causa do bloqueio continuam
  sem validação; não repetir antes de localizar o estágio preso.
- [x] E226 reproduziu que `asyncio.run()` pode travar no encerramento após uma
  exceção de `asyncio.to_thread`; a causa específica no E225 ainda era hipótese.
- [x] E227 testou o runner one-shot com exceção de worker e o timeout Codex
  com helpers anexados/destacados (`4 passed`); isso valida o harness local, não
  o provider real nem a causa do E225.
- [x] E228 tentou uma consulta limitada no clone E221; o runner one-shot ainda
  ficou sem retorno em 230 s. Não conta como escolha provider.
- [x] E229 reproduziu que o worker Codex podia terminar sem acordar o selector
  do loop até outro timer; polling de 50 ms e probe completo com CLI falso
  passaram (`NO_ACTION`, 76 opções, zero deltas, hash-fonte estável).
- [x] E230 repetiu uma consulta real após E229, mas Codex CLI falhou ao iniciar
  app-server por filesystem read-only; não houve resposta do provider.
- [x] E231 usou OAuth/Luna com execução autorizada: entre 76 opções, selecionou
  o objetivo atual de abastecimento para Ferroalto. Receipt sem deltas; dois
  deltas do owner existem somente no candidato em memória.
- [x] E232 reproduziu o mesmo ID no clone E221, persistiu em arquivo separado e
  auditou (`ok=true`); o save fonte permaneceu intacto. Replay não é nova
  inferência nem prova de continuação natural.
- [x] E233 mostrou Luna repetindo o mesmo objetivo; replay criou zero novos
  fretes e apenas atualizou o plano pendente. Isso revelou que a prévia tratava
  ordens existentes como se fossem nova ação material.
- [x] E234 passou a comparar IDs de fretes antes/depois da prévia; a affordance
  redundante sumiu do clone E232 (76→75 opções). Teste negativo falhou antes da
  correção e a regressão focada passou (`24 passed`).
- [x] E235 consultou Luna sem direcionamento no menu corrigido de 75 opções;
  escolheu a affordance válida de distribuir 653 rações em Ferroalto. Receipt
  LLM sem delta; owner gerou 22 eventos materiais/40 deltas apenas no candidato
  em memória, sem persistir o clone (`E235-finalização`).
- [x] E236 registrou a primeira tentativa de replay falhando fechada por falta
  de provider no `CWS_DATA_DIR` isolado; nenhuma mutação ou save produzido.
- [x] E237 reproduziu o ID E235 em clone com perfil efêmero, salvou separado e
  auditou causalidade (`ok=true`). O owner reduziu falta alimentar 653→0,
  elevou saúde 611→631 e reduziu unrest 385→365; save-fonte permaneceu intacto.
- [x] E238 comparou o mesmo save-base: `NO_ACTION` foi aceito no mesmo menu de
  75 opções, criou receipt de recusa e zero eventos/deltas materiais; a ação
  replay E237 alterou materialmente os indicadores. Ambos os ramos passaram
  auditoria causal, mas o par é fixture contrafactual, não adoção natural.
- [x] E239 tentou consultar `herdr pane list` para shadow Laya; o processo foi
  negado com `Operation not permitted`. Nenhum observer foi iniciado nesta
  sessão; o requisito de acompanhamento shadow permanece aberto.
- [x] E240 repetiu a prévia local do corpus com saves E179/E183/E184/E186 e
  seeds 101/14; `load_world` rejeitou o save E179 como schema não suportado.
  Nenhuma consulta externa ocorreu. Corpus provider permanece aberto até
  preparar fixtures compatíveis com schema atual.
- [x] E241 inventariou saves locais compatíveis com schema 76: 28 encontrados.
  E210 é reutilizável como baseline, mas suas consultas atuais de ajuda já
  estão pendentes; menus de Auren/Escarlia/Valedouro têm `relief`, não
  `aid_request`, pois notices ativos ocupam os possíveis provedores.
- [x] E242 avançou por 30 dias os clones E237/E238 com provider desligado e a
  mesma política offline `routine-rules`: ambos chegaram ao dia 990 sem falta
  alimentar ou mortes por privação. O ramo com auxílio terminou com saúde
  603/unrest 393; o controle, 548/448. O efeito relativo persistiu, mas houve
  decisões fallback e relief em ambos; não atribuir toda a diferença somente
  à decisão Luna nem contar fallback como provider real.
- [x] E243 confirmou conservação pelo ledger do smoke, dinheiro constante,
  save/load equivalente e auditorias `ok=true` nos dois ramos; zero causas
  quebradas, autoria inválida, Story/interpretation-material ou eventos
  materiais sem raiz. A cadeia natural e o corpus provider seguem abertos.
- [x] Gate D provider real, subaceite de corpus no checkout atual:
  reconstrução/preview sem egress de dez contextos e escolhas OAuth/Luna em
  campanha, criatura, QG e oito menus civis (`E256`–`E261`). Uma resposta
  inicialmente válida revelou falha do owner de criatura, corrigida e coberta
  por testes. Não fecha o smoke final; E244–E255 ainda precisam ser
  normalizados no diário versionado.
- [x] Tornar obrigatório um check por recorte verificável e decompor o Gate D
  em corpus, três seeds e integração final (`E181-documental`). Esta edição
  organiza acompanhamento; não valida provider nem gate longo.
- [x] Revisar critérios do plano: separar plano/matriz/diário e explicitar
  adaptação, composição multissistema, V1 e performance (`E127`). Isso não fecha
  gate técnico.
- [x] Estender auditoria do histórico exercitado com agrupamento
  `event_type × owner × aspect × origin`; teste focal passou (`E126`).
- [x] Gate B, diagnóstico inicial: seguir receipts de caixa, payroll, compra e
  falta em Campomanso/Cinzaverde; evidência `E128`. A origem mais bem
  demonstrada é acesso/distribuição de renda, mas o aceite diagnóstico amplo e
  o contrafactual adaptativo continuam abertos.
- [x] Gate A: enumerar callsites candidatos materiais e associar os tipos
  nomeados aos 183 grupos runtime observados (`E129`); seis pontos dinâmicos e
  161 tipos candidatos não exercitados seguem para classificação.
- [x] Gate A: explicar divergências/não exercitados e classificar cobertura por
  família na matriz (`E130`). A classificação é parcial e não fecha o Gate A.
- [x] Gate A: selecionar o limite transacional mínimo, provar falha sem
  publicação parcial e vinculá-lo a novos comandos diretos materiais V1
  (`E136`). Isso não declara owners antigos auditados.
- [x] Gate A: reproduzir autorização órfã na migração, aplicar primeiro uso do
  limite transacional comum e provar rollback antes/depois da mutação (`E131`).
  Outros owners e a obrigatoriedade para novos caminhos ainda estão abertos.
- [x] Gate A: reproduzir falha tardia na recuperação direta de migração e
  aplicar o mesmo limite transacional (`E133`).
- [x] Gate A: fechar a classificação finita das famílias estáticas/runtime na
  matriz, incluindo 52 módulos com nomes não exercitados e negativos de
  força, alfândega e criatura reexecutados (`E137`). Parcial não é verde.
- [x] Gate D, pré-checagem: verificar que recusa bilateral de mercado não
  consulta o vendedor novamente com orçamento de duas chamadas (`E132`).
  Não equivale ao corpus provider real.
- [x] Gate B: rastrear a cadeia econômica em Campomanso e Cinzaverde no save
  dia 1.560 (`E135`), separando falta de renda, folha/caixa e affordance
  disponível mas não escolhida na política offline.
- [x] Gate B: revalidar ao menos uma resposta material com meios existentes e
  contrafactual (`E134`): oficina → linha → emprego → salário → compra reduz
  falta na seed 73. Esse recorte isolado não fechava a entrega 5; o save
  crítico foi comparado depois em `E140-finalização`.
- [x] Gate B: comparar no checkpoint dia 1.560 a obra e a compra bilateral de
  madeira contra `NO_ACTION` em Campomanso (`E140-finalização`); falta 150 vs
  164 e saúde 423 vs 422 após 30 dias, com salário material da obra. O recorte
  não demonstra recuperação longa nem a escolha espontânea do ator.
- [x] Gate C: montar fixture autônoma reproduzível, sem decisão injetada após
  início, com papéis independentes de autoridade, QG, comandante e sociedade/
  economia (`E139-finalização`).
- [x] Gate C, recorte parcial: executar política/QG/criatura e consequência
  civil no mesmo cenário sem escolha injetada após o início; preservar `why()`
  e save/load (`E138-finalização`). Falta comandante e contrafactual no mesmo
  cenário; isso não fecha as duas caixas seguintes.
- [x] Gate C: exercer interferência externa, decisões independentes, efeito
  extramilitar, `why()` e save/load nessa trajetória (`E139-finalização`).
- [x] M2 próximo recorte (fechado em E294): estender E139 em uma trajetória integrada, sem
  escolhas injetadas depois do início e sem política que seleciona etapas por
  prefixo de affordance ou contador. A interferência datada de rota/carga deve
  alterar decisões independentes do comandante e QG; continuar pela operação,
  ocupação sustentada por guarnição efetivamente paga em ciclos sucessivos e
  saída política bilateral. Um contrafactual de rota/informação deve mudar a
  trajetória ou o controle material. Reusar owners atuais de campanha, Force,
  logística e desescalada; provider stub controlado não será chamado de provider
  real nem de ocorrência natural. E294 registra a trajetória, o contrafactual,
  o efeito civil, o ciclo de guarnição, a saída bilateral e save/load/`why()`/
  auditoria; M2 fecha somente o aceite controlado.
- [x] M2/E287: `_start_siege` transfere a diferença de efetivo de uma coorte
  civil da mesma raça para a coorte militar, com dois deltas e premissa causal;
  o headcount é verificado invariável. Fingerprint de base `3c6e590e`, diff
  SHA-256 `9233f826d5fe8d3872a55fb1f76d0b7f363c49658a8c91805ddc87ba22c6fd9c`;
  os módulos de campanha persistente e política de guarnição passaram (8 testes).
  Isso corrige a raiz da fixture de mobilização; não integra ainda operação,
  interferência, guarnição sustentada e saída bilateral numa trajetória.
- [x] M2/E288: reexecutar no checkout atual a composição já registrada de
  interferência da criatura e campanha: o teste focal passou com stub seletor,
  decisões independentes de comandante/QG, bloqueio real da rota, atraso de
  carga e efeito civil; o controle sem bloqueio avançou mais; save/load, `why()`
  e auditoria passaram. Ver E288 no estado atual. Limite: não integra ocupação
  sustentada e saída bilateral à mesma trajetória; M2 continua aberto.
- [x] M2/E289 — cenário controlado derivado da preparação de E288, agora com
  força defensora física: soldados
  preexistentes e conta/provisões formam a premissa; `garrison_options` e
  `establish_garrison` do owner criam a obrigação real. Sem escolhas injetadas
  após o start, o stub escolhe pela situação/descrições; a mesma coluna reroteia,
  chega e cria contato datado. O controle sem restrição chega antes. A guarnição
  continua ativa com pelo menos três pagamentos reais; ambos os ramos salvam,
  recarregam e passam auditoria (`11 passed` no grupo focal). Detalhes e hash em
  E289 no estado atual. Limite: sem batalha/cerco, captura, guarnição vencedora
  sustentada ou saída bilateral na mesma trajetória.
- [x] M2/E290 — desde o contato de E289, a mesma coluna usa menus correntes
  para preparar posição, investir o assentamento, iniciar e sustentar cerco,
  romper a defesa e escolher ocupação; o owner altera `occupier_id`. O controle
  pareado sem bloqueio chega à ocupação, enquanto a rota fechada impede a
  operação. O preparo e carregamento da coluna agora criam observação de rotas
  locais datada e reabrem a revisão institucional; a decisão é ligada ao recibo
  de preparo/observação. Nenhum resultado posterior ao início é escrito pela
  fixture. Save/load e auditoria passaram em ambos os ramos. Ver E290 no estado
  atual. Limite: cenário preparado com provider stub, não ocorrência natural,
  provider real, guarnição vencedora sustentada nem saída bilateral; M2 continua
  aberto.
- [x] M2/E291 — após a transição de ocupação de E290, a alteração material
  reabre uma decisão de campo; o ator escolhe separadamente estabelecer
  guarnição, o owner revalida provisões/tesouro, e a mesma coluna registra ao
  menos três recibos reais de manutenção paga. Quando as provisões acabam, o
  owner encerra a guarnição e remove o ocupante, com delta causal. Save/load e
  auditoria causal continuam válidos nos ramos pareados; grupo focal militar →
  `97 passed`. Evidência de cenário preparado e provider stub, não manutenção
  por vários meses nem campanha natural. M2 segue aberto para saída política
  bilateral.
- [x] M2/E292 — integrar cessar-fogo mútuo da campanha ao turno atual de
  contato físico: após início/progresso/brecha, somente as instituições cujas
  colunas estão presentes recebem revisão datada. Atacante pode propor, a
  contraparte conhece e aceita/recusa em decisão independente, e cada devedor
  escolhe seu próprio cumprimento por rota atual; owner retira apenas sua força
  e revalida obrigação, autoridade e caminho. O teste do turno real inclui a
  brecha antes das retiradas: o atacante sai primeiro, removendo materialmente
  o investimento, e a coluna defensora — ainda presente embora sua garrison
  tenha colapsado — escolhe depois sua própria rota. O controle administrativo
  continua com a defensora e a ocupação fica vazia; não há transferência
  automática. Sem decisão injetada após o start; save/load e auditoria causal
  passaram. Grupo focado de cerco, contato, campanha, rotas, comando, suprimento
  e guarnição: `97 passed` (E292). Limite: cenário inicial preparado e provider
  stub; não prova ocorrência natural nem provider real, e M2 continua aberto.
- [x] M2/E293 — cobrir a retirada bilateral depois da ocupação, quando a coluna
  atacante está vinculada a uma guarnição ativa e paga: o cumprimento da própria
  obrigação precisa encerrar essa duty pelo owner antes de mover a coluna, sem
  deixar guarnição ativa em força ausente. A defensora colapsada, ainda presente,
  recebe opção e decide sua retirada somente depois que o atacante libera a rota.
  Preservar administrador, limpar ocupação apenas pela saída material, ligar os
  dois movimentos às decisões corretas e provar save/load/auditoria. `98`
  testes focados passaram (E293). A política usa provider stub em cenário
  preparado; provider real e ocorrência natural continuam fora deste recorte.
  É extensão do lifecycle já aberto em M2, sem regra nova de guerra ou sistema
  paralelo.
- [x] M2/E294 — unir E288–E293 na mesma trajetória controlada derivada de E139:
  o mesmo plano/QG/comandante, criatura alterando rota/carga, operação que muda
  controle, guarnição paga e retirada bilateral depois da ocupação. Nenhuma
  decisão nem resultado pode ser injetado após a linha de início; o stub escolhe
  apenas affordances correntes por papel e contexto. O ramo sem bloqueio e seu
  controle contrafactual precisam terminar com controle diferente; o ramo
  bloqueado continua sem captura. `why()`, save/load e auditoria no estado final.
  O teste integrado registra a rota/carga atrasada no ramo da criatura, diferença
  material de entrega/falta/saúde no assentamento, quatro manutenções diárias da
  mesma guarnição antes da proposta e duas retiradas independentes com decisões
  e movimento físico. Um re-preparo legítimo da mesma posição revelou que a
  validação exigia um único evento de início histórico; agora a posição corrente
  ancora-se no início mais recente, mantendo todas as tentativas no ledger.
  Verificação focal e regressão de campanha/contato/cerco anexadas em E294 no
  diário. Limite: cenário controlado com provider stub, não emergência natural
  nem validação de provider real.
- [x] M3/E295 — provar uma via completa de tecnologia por migração material
  real: o owner `start_migration`/resolução move um especialista nomeado para
  outra instituição; conhecimento prévio na origem habilita oferta e instrução
  paga no destino; a tecnologia aprendida abre um consumidor material existente
  (irrigação), ainda sujeito a local, insumos e trabalho. Preservar a técnica na
  origem e ligar migração, decisões, aprendizado e aplicação por eventos/causas.
  Evidência: `test_real_migration_carries_technique_into_paid_irrigation_application`
  e `test_a_migrated_specialist_instructs_for_real_wages_before_any_technique_exists`
  passaram junto com o módulo de aprendizagem e um teste do owner de migração
  (`10 passed`; E295, `CWS_DATA_DIR=/tmp/cws-e295-focused`). Cenário controlado;
  sem prova de emergência natural, provider real ou fechamento do catálogo M3.
  Reusar owners existentes; sem tecnologia ou capacidade gratuita.
- [x] M3/E296 — compor roubo bem-sucedido de `metallurgy` com consumidor
  material existente: o alvo mantém uma linha de carvão operante e observada;
  o ator rouba apenas com agente/relatório/conhecimento válidos; a técnica
  habilita `efficient-furnaces` numa linha própria de ferro; obra consome
  materiais e folha, muda a receita, e a produção posterior muda materialmente.
  Verificar a cadeia de causas e o ramo sem conhecimento antes do roubo.
  Evidência: `test_stolen_metallurgy_unlocks_a_paid_local_production_upgrade`
  incluído na regressão `tests/test_medieval_technology_theft.py` (`7 passed in
  1.83s`; E296, `CWS_DATA_DIR=/tmp/cws-e296-final`). Cenário controlado com API,
  sem alegar provider real ou ocorrência natural.
- [x] M3/E297 — compor a pesquisa custeada de `field_drill`, o consentimento
  independente do pesquisador, o treinamento pago e abastecido de uma coluna
  existente e o aumento de força usado pelo cálculo de combate. Conhecimento
  institucional sozinho não concede força; pesquisa sem consentimento, falta
  de ferramenta/ração ou treino incompleto também não. Provar causas, decisão
  datada e round-trip do save. `tests/test_medieval_force_training.py::test_paid_field_drill_research_and_training_reach_a_material_field_battle`
  passou com auditoria causal no save; regressão de pesquisa/treino:
  `29 passed` (E297). Recorte preparado com decisões API; não declarar decisão
  espontânea/provider real ou fechar M3 inteiro.
- [x] M3/E298 — fechar conservação alimentar em um recorte público limitado:
  estoque acima da necessidade mensal sofre perda determinística de 0,5% por
  ciclo, arredondada para baixo; estoque necessário ao ciclo atual nunca apodrece.
  Pesquisa `food_preservation` habilita construir um smokehouse mantido pelo
  proprietário, cuja capacidade efetiva deriva de integridade física e reduz
  somente o excedente exposto. Dano reduz proteção; reparo pago a recompõe.
  Provar pesquisa → obra → operação/perda menor → dano → reparo → recuperação,
  com contrafactual idêntico sem preservação, conservação, causal links,
  rollback de rejeição e save/load. Recorte não afeta alimentos domésticos,
  estoques em trânsito, migração ou comida abaixo da reserva mensal; fixture não
  prova provider real, ocorrência natural nem calibração global.
  Evidência E298: `tests/test_medieval_food_preservation.py` compõe pesquisa,
  consentimento independente, obra paga, perda de 238→228 no par controlado,
  dano (perda 231), reparo pago e recuperação da capacidade; round-trip do save,
  `validate_history` e rollback passam. Regressão focal de seis módulos:
  `107 passed in 85.41s`. SHA-256s registrados no diário E298. Provider real,
  causalidade natural e calibração de longo horizonte continuam fora da prova.
- [x] M3/E299 — inventariar o menor caminho material de pólvora e artilharia
  usando Force/cerco/economia existentes; antes de codar, fixar o consumidor
  físico e o contrafactual. E299 confirmou `SiegeCampaign.garrison_endurance`
  (`src/sim/medieval/siege_campaign.py::_garrison_wear` e
  `resolve_siege_campaigns`) como consumidor: uma decisão explícita de
  bombardeio pode reduzir endurance em passo limitado, enquanto o dono mantém a
  pressão diária existente. O contrafactual pareado deverá diferir somente pela
  presença/uso de artilharia e munição: sem conhecimento, equipamento ou
  pólvora a opção não aparece; com ambos, uma decisão atual consome pólvora,
  preserva a peça de artilharia e produz delta de endurance, com fontes causais
  e save/load.
  Inventário: `economy.json` já declara `sulfur` e `saltpeter`, mas nenhum deles
  tem receita/facility de produção; também não existem recursos/receitas de
  pólvora ou artilharia. `Recipe` e linhas de produção por `ExpansionBlueprint`
  já suportam insumo/produção paga e bloqueio por tecnologia. `campaign_stock`
  é um `Stock` canônico co-localizado com a coluna e pode guardar mercadorias,
  mas `load_campaign_baggage()` (`campaign_supply.py`) carrega apenas alimento;
  não há decisão de transferência de munição/equipamento ao estoque da coluna.
  O modelo de `SiegeCampaign` ainda não persiste bateria e não deve receber um
  booleano redundante: presença é derivável do equipamento real na bagagem.
  E299 é somente inventário e fixação do consumidor/contrafactual; não prova
  produção, transporte, pesquisa, decisão nem efeito de artilharia. E300 é o
  próximo recorte de implementação: fonte material de salitre/enxofre → pesquisa
  custeada de pólvora → linha paga de munição/peça → despacho por logística
  existente para uma coluna → escolha atual de bombardear → consumo de pólvora e
  dano limitado à endurance de cerco. Reusar estoque/bagagem, receitas, frete,
  pesquisa e cerco; não criar classe de unidade ou combate paralelo. Se a
  limitação de transporte exigir owner novo, registrá-lo como parte de E300 e
  usar `execute_material` para seu comando direto.
- [x] M3/E300 — implementar pólvora e artilharia sobre Economy, Freight,
  bagagem de campanha, Research e o consumidor de cerco fixado em E299. O mapa
  declara o depósito mineral real; mão de obra/insumos pagos produzem salitre e
  enxofre; pesquisa requer esses produtos; receitas tecnológicas produzem
  pólvora e uma peça; o QG decide despachar carga por rota conhecida à bagagem;
  só então o atacante pode decidir bombardear uma campanha ativa. O tiro consome
  pólvora, mantém a peça, reduz endurance em incremento limitado e pode causar
  brecha somente ao zerar o mesmo estado de cerco; sem tecnologia, peça ou
  munição, opção/delta ausentes. Bagagem com artilharia só se move junto da
  coluna por caminho físico permitido, e equipamentos não desaparecem ao
  dissolver a força. Comparar controle e intervenção da mesma fixture, incluindo
  frete, rota interrompida, consumo, links, rejeição/rollback, save/load e
  auditoria; incluir ao menos um menu real provider quando disponível. Sem nova
  classe de força ou combate paralelo. Isso fecha apenas o recorte de pólvora e
  cerco, não árvore tecnológica nem M3 inteiro.
  - [x] Catálogo atual: recurso/site de extração, pesquisa `gunpowder`, receitas
    e linhas pagas de separação mineral, pólvora e artilharia; bump explícito
    para save schema 80, sem compatibilidade ou migração.
  - [x] Contrato do owner de campanha: opções atuais de despacho por estoque,
    rota/relatório e capacidade; frete normal para bagagem co-localizada; tiro
    material via `execute_material`, com consumo de pólvora e endurance limitada.
  - [x] Prova controlada de produção: pesquisa paga de `metallurgy`, separação
    paga de salitre/enxofre, pesquisa paga de pólvora, linhas pagas e produção
    física; `validate_history` e save/load passam (`test_paid_mineral_separation_feeds_gunpowder_research_and_two_real_lines`).
  - [x] Prova controlada de campanha: peça e pólvora chegam por frete real à
    bagagem, a opção de pólvora só surge depois da peça, um disparo consome uma
    carga, preserva a peça, causa delta de endurance e um ID stale é rejeitado
    sem mutação parcial; round-trip do save (`tests/test_medieval_campaign_ordnance.py`).
  - [x] E304 integrou a produção paga do mesmo ator, o estoque causal de origem,
    rota/report do HQ, Freight à bagagem, investimento, cerco, consumo de
    pólvora e delta de endurance no mesmo mundo (`test_paid_mineral_separation_feeds_gunpowder_research_and_two_real_lines`).
  - [x] E306/E307 cobrem interrupção/retomada de Freight, conservação e entrega
    causal da carga, movimento da bagagem com retirada, permanência institucional
    após dissolução, save/load e auditoria. São fixtures controladas com
    tropas/defensor preparados; não provam emergência natural.
  - [x] E308 compara duas cópias do mesmo estado com ambos os fretes já em
    trânsito: rota aberta entrega a tempo e permite investimento/cerco/disparo;
    interdição atrasa as duas cargas, impede investimento e cerco naquele prazo,
    e não altera endurance por bombardeio. Round-trip no estado interditado,
    depois levantamento, entrega e disparo no ramo de intervenção; auditoria nos
    dois ramos. `provider_available()` retornou `False`, sem egress; não houve
    consulta externa. Produção integrada de E304 foi revalidada separadamente.
  - [x] Aceite E300 limitado: teste integrado E304 passou `1 passed`; regressão
    focal campanha/cerco, logística e interdição passou `44 passed`;
    `git diff --check` limpo. E300 conclui somente pólvora/artilharia; M3 segue aberto para
    as demais tecnologias e intriga. Cenários preparados não provam emergência
    natural nem decisão provider real.
- [x] M3/E309: cruzar os requisitos remanescentes de M3 com consumidores e
  testes existentes, rodar os grupos focados e selecionar a próxima ligação
  ausente. A evidência e os limites estão registrados acima; M3 não fecha.
- [x] M3/E310: provar que memória institucional direcional de breach altera
  uma escolha provider em proposta posterior, sem deltas no receipt, e permitir
  NO_ACTION com opções de remediação/renegociação. Prova local mockada; sem
  egress. O detalhe e os limites estão no diário e no contrato.
- [x] M3/E311: pesquisa paga de `defensive_barriers` por Auren no site próprio
  `passagem-negra`, com consentimento independente do pesquisador, consumindo
  seis ferramentas e pagando folha; depois a obra paga em Pedra Clara consome
  materiais/trabalho e cita o evento da pesquisa como causa. A cadeia prévia
  `field_drill` → `siegecraft` → `fortification` é premissa declarada da fixture;
  não prova sua pesquisa emergente. Round-trip save/load passou. Regressão
  focal de barreira, pesquisa e indústria: `38 passed`; `git diff --check`
  limpo. Efeitos de cerco seguem nos testes separados anteriores; não houve
  provider nem egress.
- [x] M3/E312: no teste integrado aço/vapor, a metalurgia inicial e as
  pesquisas de aço/vapor agora usam IDs selecionados de menus atuais, com
  consentimento separado. Regressão indústria/pesquisa/barreira `38 passed`;
  recursos/instalações são premissas preparadas, sem provider ou naturalidade.
  Hash do teste e limites acima.
- [x] M3/E313: transferência produtiva registrada em `monthly_adapters` e
  `monthly_actors`; ofertas novas de organizações recebem uma consulta posterior
  do comprador em adapter limitado àquela oferta, pois o ordenamento normal
  consulta polities antes de organizações. A escolha do seller oferece, o buyer
  aceita independentemente e o owner revalida/transferiu os bindings; não cria
  estado/planner adicional. A verificação revelou também recusa de pesquisa
  persistente por busca no tipo errado de evento; `_offer_was_declined` agora
  exige decisão atual authored e o ID exato recusado.
  Regressão focal `tests/test_medieval_productive_conveyance.py
  tests/test_medieval_research.py tests/test_medieval_industry.py
  tests/test_medieval_technology_sale.py
  tests/test_medieval_knowledge_verticals_fail_closed.py
  tests/test_medieval_institutional_aid_policy.py`: `73 passed`;
  `git diff --check` limpo. Provider mock, sem egress. Base HEAD `3c6e590e`;
  SHA-256s: `productive_conveyance_policy.py`
  `256e4d3ab092e03586f259073e17940baa696b45e4dacfa5c43ba3dd7bb491e8`,
  `institutional_agenda.py`
  `9ae57325083fdc24e08e105285fcd8d4a683f971874a3f19be8b1f403ae49795`,
  `research.py` `d2a5d6061626a02a80d089ffec1f89836481879f353e03c966eacb0103f04502`,
  `test_medieval_productive_conveyance.py`
  `8e4812d59ab51066e1c202faa50c286a741f57b943aadc198e6326d51416bde1`.
- [x] M3/E314a: provar pela API ativa `/api/v2` que o snapshot do Observatório
  reflete owner/maintainer e bindings após transferência real, e que `why()` do
  recibo navega às decisões bilaterais e expõe os quatro deltas de controle.
  `tests/test_medieval_observatory.py::test_productive_conveyance_is_visible_in_observatory_and_why`
  passou. GET público cobre snapshot e causal query, sem mutar o mundo.
- [x] M3/E314b: o mesmo `causal_view` navega tarifa cobrada, embargo que causa
  recusa de carga, classificação de contrabando e detecção de evasão. `why()` é
  global para o Dao; dossier privado não é ampliado nem recebe conhecimento
  implícito. `tests/test_medieval_trade_embargo.py::test_only_the_named_counterparty_is_refused_and_goods_are_conserved`,
  `tests/test_medieval_trade_embargo.py::test_declaring_and_lifting_is_one_dated_policy_transition`,
  `tests/test_medieval_tariffs.py::test_export_quote_collects_once_without_losing_the_seller_alias_or_delivery`
  e testes focados em `tests/test_medieval_customs.py` cobrem os recibos. Regressão
  dos cinco módulos Python: `71 passed`; `web/src/medieval/__tests__/chronicle.test.ts`:
  `4 passed`; `git diff --check` limpo. Base HEAD `3c6e590e`; hashes E314:
  `customs.py` `4e8d719a8f80000c6eef217dbd48f48feb6eccd150b2af3a8a2f0889ba85dafb`,
  `embargo.py` `48b856f0fd458521e05e7902e5017cd42a009b969a5c7d91b797a941728b4fa6`,
  `test_medieval_observatory.py` `df2cebe232dcf5a30a932202056c615f08958f949a6acf94bba79f242095f8a3`.
- [x] M3/E315: reconciliei as cinco linhas do M3 com owners e provas atuais:
  conservação/tecnologia/operação (E298, E300–E312), difusão/aplicação
  (E295–E297, E311–E312), diplomacia/intriga (E310 e provas de persuasão,
  espionagem, suborno, sabotagem/investigação/acusação), compromissos/memória
  (E310 e aid remediation), e fiscalidade/transferência (E313–E314). Uma seleção
  de 19 testes focados passou nesta revisão. Não encontrei capacidade sem owner;
  encontrei lacuna de prova no menu mensal completo para tarifa/customs. Isso não
  fecha M3: E316 cobre essa lacuna e os aceites do marco continuam abertos.
- [x] M3/E316: exercitar opções atuais de tarifa e customs pelo menu mensal
  institucional completo (não somente adapters de família), com atores elegíveis
  e decisão selecionada por ID corrente; conferir seus efeitos materiais e
  preservar o turno único/consulta independente. Tarifa e evasão aduaneira foram
  selecionadas em menu completo por mock local; detecção atualiza estado/receipt.
  Contrabando catalogado usa retorno/apreensão e tem cobertura própria, não uma
  opção ilegal de evasão. Regressão dos cinco módulos: `72 passed`, E316.
- [x] M3/E317: completar escolha e efeito do embargo na trajetória do menu
  mensal. O owner agora registra `ACTOR_DECISION`, ID da affordance e decisão
  fonte na mudança de política; uma carga posterior do alvo é recusada e o
  `why()` chega à declaração. Novo teste no menu composto; cinco módulos:
  `73 passed`. Isso não fecha a linha M3 toda nem demonstra mundo natural.
- [x] M3/E318: provar a decisão de treinamento de `field_logistics` no menu
  mensal completo (sem API injetada), após premissas datadas de conhecimento e
  treino-base. O provider recebe token opaco, não ID canônico com `stock:`, e a
  engine o resolve para affordance atual; ferramentas são consumidas, três dias
  abastecidos decorrem, e a capacidade material da bagagem aumenta. Regressão
  force-training + campaign-supply: `15 passed`.
- [x] M3/E319: selecionar apreensão de contrabando catalogado pelo menu mensal
  completo do operador, em vez de somente chamar o owner diretamente; provar
  consumo/transferência física para estoque, autoria da decisão e `why()` da
  detecção/apreensão. Contrabando não pode escolher a affordance de evasão.
  Provider mock selecionou a opção atual; apreensão moveu a carga real ao estoque
  civil do posto. O owner emite `ACTOR_DECISION` com decisão/ator/affordance, sem
  causar a mutação diretamente pelo receipt de interpretação. Cinco módulos:
  `73 passed`.
- [x] M3/E320: reconciliar cada aceite M3 com prova corrente no checkout; os
  cinco requisitos têm consumidor e evidência focada (`27 passed` + `7 passed`);
  M3 fechado em cenário controlado/provider mock. Não prova naturalidade,
  provider real ou composição dos marcos M1/M2/M4–M8.
- [x] M2 sub-recorte de seleção: o stub de E139 passou a usar papel do ator e
  descrições das opções recompostas, sem ler IDs nem contador de consultas;
  `test_prepared_crisis_runs_actor_choices_without_post_start_injection`
  passou em E284. É evidência controlada, não provider real, e não fecha a
  operação, guarnição sustentada nem saída bilateral exigidas pelo item M2 acima.
- [x] M2 sub-recorte de autoria das fixtures de campanha: premissas materiais
  de estoque, presença inicial da guarnição e rota interrompida agora declaram
  `root_premise`; o grupo focal que cobre interferência, operação, guarnição e
  saída bilateral passou (`27 passed` nos quatro módulos, E284). São provas em
  cenários distintos dentro da suíte, não uma mesma trajetória integrada. Isso
  torna as fixtures auditáveis, mas não as converte em ocorrências naturais nem
  fecha a integração autônoma exigida pelo item M2 acima.
- [x] M2 sub-recorte (E285): o bootstrap da guarnição transfere vinte pessoas
  de uma coorte local civil para a coorte militar existente, com deltas de
  contagem nos dois grupos e headcount total invariável; `6` testes da campanha
  e `28` do grupo focal passaram, incluindo as auditorias causais já presentes.
  As `600` rações continuam declaradas como condição inicial preparada, não
  como entrega logística. Remove-se criação gratuita de pessoas das premissas;
  a integração M2 completa segue aberta.
- [x] Gate C, observação limitada: inventariar saves naturais já existentes e
  registrar ausência da cadeia política completa sem transformá-la em cota
  de drama (`E141-finalização`). Todos os saves inspecionados usam
  `ai_enabled=false`; isso não fecha o item 7.
- [x] Gate D, medição preliminar: repetir um mês tardio, save/load, RAM,
  tamanho do save e consultas `why()` no host atual (`E142-finalização`).
  A amostra não ratifica os limites nem fecha o item 9.
- [x] Gate D, gargalo localizado: atualizar o índice transitório de eventos
  por append isolado em cada candidato, provar rollback e repetir o mesmo
  mês com save byte a byte idêntico (`E143-finalização`). O tempo mensal
  ainda excede o limite provisório.
- [x] Gate D, segundo gargalo localizado: manter índice de tipos por append
  transacional e usar `research_authorized` indexado na validação de pesquisa;
  28 testes focados e save idêntico no mês pareado (`E144-finalização`).
- [x] Gate D, amostra sequencial: avançar três meses tardios sem provider,
  preservar save dia 1.710 e auditar causas, autoria, Story e conservação
  (`E145-finalização`). A variação mensal e a crise econômica mantêm o gate
  aberto; três observações não estabelecem p95 longo.
- [x] Gate B/C, leitura do mundo offline: separar affordances econômicas
  atuais de consultas não realizadas na seed 73/dia 1.710 (`E146-finalização`).
  Opção existente sem provider não equivale a recusa deliberada do ator.
- [x] Gate D, conectividade sintética: Codex OAuth/Luna respondeu a uma
  fixture sem dados de save (`E147-finalização`). Consulta canônica externa
  foi negada pela revisão de permissões antes de executar; corpus segue aberto.
- [x] Gate D, instrumento local: probe do menu civil real passou com provider
  stub para `NO_ACTION` e ID oferecido, sem persistir o save (`E148-finalização`).
  Isso não substitui o corpus com provider real.
- [x] Gate D, baseline ampliado: medir seis meses tardios seed 73/dia
  1.710→1.890, preservar save e auditoria, sem aprovar o orçamento de 20 s
  que a amostra refutou (`E149-finalização`).
- [x] Gate D, remover varredura repetida do ledger nas demandas de trabalho:
  usar índice transitório, passar 43 testes focados e obter save de seis meses
  byte a byte idêntico com tempo menor (`E150-finalização`).
- [x] Gate D, segunda seed curta: medir seed 14/dia 1.260→1.440 no mesmo
  checkout, com save/load e auditoria (`E151-finalização`). Esse horizonte é
  anterior ao trecho tardio da seed 73 e não fecha orçamento ou gate longo.
- [x] Gate D, indexar relatórios de conhecimento por destinatário uma vez
  por epoch do registro, preservando ordem; 49 testes focados e save de seis
  meses byte a byte idêntico (`E152-finalização`).
- [x] Gate D, estender a seed 73 offline por mais seis meses, do dia
  1.890 ao 2.070, salvar e auditar o checkpoint (`E153-finalização`). A
  medição continua insuficiente para ratificar orçamento ou fechar o gate.
- [x] Gate C/D, inspecionar no save do dia 2.070 os planos militares,
  pedidos de ajuda e o perfil do mês seguinte sem alterar o checkpoint
  (`E154-finalização`). Registrar ausência e gargalos sem fechar gates.
- [x] Gate D, retirar duas validações pré-tick redundantes sem tocar na
  validação final; provar rollback, auditoria e save idêntico no mesmo mês
  (`E155-finalização`). Isso não ratifica o orçamento.
- [x] Gate D, repetir os mesmos seis meses tardios após a mudança, com
  conservação, save/load, auditoria e comparação byte a byte
  (`E156-finalização`). Registrar p95 ainda acima do limite provisório.
- [x] Gate D, repetir em outra seed/idade do mundo e confrontar o save
  original, sem agregar p95 de estágios diferentes (`E157-finalização`).
- [x] Gate D, medir 20 consultas causais distribuídas e 20 de alto fanout
  no save tardio, com limite 100 (`E158-finalização`). Esta medição local
  não representa latência de UI/rede nem aprova todo o orçamento.
- [x] Gate B/D, avançar mais um ano natural com checkpoint semestral,
  separar custo de save do tempo mensal e diagnosticar a crise econômica
  observada (`E159-finalização`). Não chamar de gate de dez anos.
- [x] Gate D, pré-checagem pública focada: build/type-check medieval e cinco
  contratos API/observatório/`why()` (`E160-finalização`). Não chamar de
  regressão final ou suíte completa.
- [x] Gate D, negativo local do instrumento: resposta com ID inventado é
  rejeitada e o save de origem permanece inalterado inclusive em erro
  (`E161-finalização`). Não conta como decisão do corpus provider real.
- [x] Gate D, localizar o custo de um mês tardio sem alterar o save: perfil
  dia 2.430→2.460 e cópias por owner (`E162-finalização`). Não ratifica p95
  nem autoriza mudar regras diplomáticas por desempenho.
- [x] Gate D, fixar orçamento pré-gate: mais seis meses da seed 73, auditoria
  do save dia 2.610 e p95 dos 18 meses tardios (`E163-finalização`). Limite
  mensal passa de 20 s provisórios para 35 s fixos; o smoke final deve provar
  cumprimento, não reajustar o alvo depois.
- [x] Gate D, usar índice de tipo no pedido de ajuda em aberto e repetir o
  mesmo horizonte de seis meses (`E164-finalização`): save byte a byte idêntico,
  testes focados e benchmark local passam; orçamento final ainda não passou.
- [x] Gate C: buscar composição natural sem cota de drama e classificar
  explicitamente fixture, fallback, provider real e observação natural
  (`E165-finalização`). Nenhuma campanha surgiu nas duas trajetórias atuais;
  isto fecha a busca, não prova guerra espontânea.
- [x] Gate D, prévia local de egress: compactar contexto repetido de emprego
  sem perder escolhas nem evidência (`E166-finalização`). Prompt mensal caiu
  de 75.264 para 55.797 bytes; nenhuma chamada externa foi feita.
- [x] Gate D, prévia local dos 11 menus institucionais do save tardio
  (`E167-finalização`): contabilizar tamanhos/aliases sem egress nem declarar
  privacidade universal.
- [x] Gate D, instrumentar o aceite operacional (`E168-finalização`): tempo
  mensal sem checkpoint, p95, 20 consultas `why()` e reprovação pelos limites
  V1 apenas com `--final-v1`; o gate longo não foi executado.
- [x] Gate D, alinhar o probe local de save ao menu mensal institucional
  completo e validar o candidato após a decisão (`E169-finalização`):
  `NO_ACTION`, ID oferecido e ID inventado passaram nos testes focados;
  nenhuma chamada externa ou persistência do fork ocorreu.
- [x] Gate D, pré-checagem natural seed 73/dia 2.610→3.600 (`E170`):
  oito checkpoints válidos, conservação, save/load e auditoria causal final;
  p95 tardio 44,24 s reprova o teto desse recorte. Foi antes de `E172` e
  não conta como o gate final do checkout atual.
- [x] Gate D, perfilar um mês lento sem alterar o save (`E171`): custo
  concentrado em diplomacia, cópias transacionais e validação de Relations.
- [x] Gate D, eliminar cópia redundante de divulgação dentro da transação
  mensal (`E172`): 32 testes focados, incluindo falha após divulgação sem
  publicação parcial, e replay de um mês com save byte a byte idêntico;
  tempo pareado 42,77→36,57 s, sem declarar orçamento aprovado.
- [x] Gate D, reutilizar a transação mensal na migração offline (`E173`):
  chamada direta mantém rollback próprio; 53 testes focados incluem falha
  tardia, o save de dez anos ficou byte a byte idêntico e o p95 dos 33 meses
  tardios caiu de 44,24 para 29,61 s. Ainda não é o gate de três seeds.
- [x] Gate D, pré-checagem independente da seed 14/dia 1.440→1.800 (`E174`):
  doze meses, p95 17,28 s, checkpoint e save/load válidos; auditoria final
  limpa. A seed ainda não chegou a dez anos e não fecha o gate.
- [x] Gate D, pré-checagem da superfície pública (`E175`): build medieval,
  cinco contratos API/observatório e 20 consultas `why()` distribuídas no
  save seed 14/dia 1.800 passaram. Não é regressão completa nem browser real.
- [x] Gate D, sanear a fixture de campanha do corpus (`E176`): soldados são
  transferidos de uma coorte existente, ocupação e transferência recebem
  premissas causais explícitas, e o probe percorre adoção → autorização
  política → QG → nomeação. Sete testes focados e auditoria standalone do
  save material passaram com provider stub; nenhuma chamada externa ocorreu.
- [x] Gate D, pré-checagem natural da seed 14 até dez anos (`E177`): retomar
  dia 1.800→3.600 sem provider, validar e auditar cinco checkpoints anuais,
  medir 60 meses, save/load, RAM e 20 consultas `why()`. O recorte passou nos
  limites individuais medidos, mas não mede o run completo desde o dia zero
  nem fecha o gate final de três seeds.
- [x] Gate D, pré-checagem integral da seed 101 (`E178`): dia 0→3.600 sem
  provider, dez checkpoints anuais auditados, 120 meses medidos, conservação,
  save/load, RAM e 20 consultas `why()` dentro dos limites V1. É uma seed
  completa isolada, não o gate conjunto de três seeds nem o corpus real.
- [x] Gate D, pré-checagem integral da seed 73 (`E179`): dia 0→3.600 sem
  provider, dez checkpoints anuais auditados, 120 meses medidos, conservação,
  save/load, RAM e 20 consultas `why()` dentro dos limites V1. O run precede
  a correção E180 e não aprova o checkout posterior.
- [x] Gate D, corrigir ordem causal instável (`E180`): comparar o run integral
  com replay anterior revelou planos de abastecimento concluídos em ordem
  diferente após save/load; `progress_supply` agora ordena por ID. Regressão
  com inserção oposta dos mesmos planos e replay pareado até depois do dia
  divergente passaram; smokes anteriores ficam históricos, não finais.
- [x] Gate D, inventário local do corpus (`E182`): no save natural da seed 73
  há menus econômicos e opções de duas criaturas; o cenário controlado de
  campanha oferece defesa, irrigação e doutrina militar ao mesmo ator. Um
  pedido real de ajuda no fork do save dia 1.440 gerou aceite e recusa válidos.
  Ainda faltam um compromisso perto do prazo e a comparação material entre
  alimento e prioridade militar; nenhum provider foi chamado.
- [x] Gate D, compromisso perto do prazo (`E183`): preparar via decisões API
  e owners reais uma obrigação de ajuda a partir do save dia 1.440; avançar
  com política local explícita `NO_ACTION` até um dia antes do vencimento,
  preservar opção de cumprimento, save/load e auditoria causal. É fixture,
  não decisão real do provider nem formação natural do atraso.
- [x] Gate D, prioridades concorrentes (`E184`): no mesmo menu mensal de
  Escarlia, uma falta de 215 rações observada oferece pedido de ajuda enquanto
  uma ocupação inicial explicitamente factual oferece adoção de defesa.
  Save/load e auditoria passam; nenhum resultado material posterior nem
  escolha real do provider foi inferido desse menu.
- [x] Gate D, base de rota/campanha (`E185`): reexecutar a fixture autônoma de
  criatura → rota → carga atrasada → decisões datadas de comando/QG e o teste
  isolado de nova affordance de suprimento após atraso. Ambos passaram no
  checkout atual; falta extrair uma situação pronta para o corpus real.
- [x] Gate D, checkpoint rota/campanha (`E186`): salvar a fixture causal no
  dia 30 antes da revisão datada e sondar somente comandante/QG em fork.
  Stub `NO_ACTION` produziu duas consultas válidas (1 e 3 opções); ID
  inventado bloqueou sem alterar o save. Nenhuma consulta real ocorreu.
- [x] Gate D, contexto do compromisso (`E187`): expor no menu composto apenas
  prazo, quantidade e credor da obrigação de ajuda aceita pelo próprio ator.
  Na fixture a leitura mostra vencimento em 1 dia; quatro testes focados
  passaram. Prévia local dos cinco casos checou relatórios próprios e
  identidades de estoque/conta estrangeiros; é verificação dirigida, não
  certificação universal de todos os fragmentos de prompt.
- [x] Gate D, corpus local preparado (`E188`): crise econômica, rota/campanha,
  compromisso perto do prazo, exigência de criatura e conflito alimento/defesa
  possuem saves/affordances atuais e prévia reproduzível dos prompts. As
  checagens de conhecimento dos cinco casos passaram sem egress; isto não é
  auditoria universal dos demais prompts nem decisão do provider real.
- [x] Gate D, execução local das opções (`E189`): em cópias dos cinco casos,
  um stub selecionou IDs ofertados para pedido de ajuda econômica, entrega de
  ajuda aceita, adoção de defesa, rerota pelo QG e exigência de tributo pela
  criatura. Os owners revalidaram e emitiram fatos materiais com deltas;
  hashes dos saves de origem permaneceram iguais. O comandante manteve
  `NO_ACTION` na sonda de rota. Isto prova executabilidade local, não escolha
  independente de provider real nem desfecho natural.
- [x] Gate D, preflight focado do checkout (`E190`): probes civis, interferência
  campanha/criatura e verificador de release passaram (`9 passed`) com dados
  isolados em `/tmp`. Sem `CWS_DATA_DIR`, a coleta falhou por tentativa do
  logger de escrever fora do sandbox; não foi falha do simulador. Este recorte
  não substitui corpus real, três seeds nem integração final.
- [x] Gate D, dez contextos locais distintos (`E191`): a prévia agora combina
  os cinco tipos de situação em dez consultas ator–estado, usando saves das
  seeds 73, 101 e 14. A unicidade, as opções atuais e as checagens dirigidas
  de conhecimento passaram sem egress; nenhuma consulta ao provider ocorreu.
- [x] Gate D, integração dirigida API/UI (`E192`): 55 de 56 testes focados de
  API/dossiê/observatório/auditoria passaram; o único erro era um teto fixo de
  população no teste anual, incompatível com nascimentos materiais. O teste
  agora confere a soma dos grupos canônicos e passou isoladamente, assim como
  demografia (`2 passed`). Crônica/dossiê/app no frontend passaram (`23 passed`)
  e o build concluiu com aviso de chunk grande. A suíte backend completa não
  foi repetida após a correção; isto não fecha a integração final.
- [x] Gate D, instrumento `why()` (`E193`): o medidor agora exige que as 20
  consultas distribuídas devolvam o evento correto, todas as causas esperadas
  e efeitos ligados ao fato consultado; o orçamento reprova vínculos inválidos.
  No save histórico E179, p95 `0,1567 s`, vínculos válidos e fonte intacta;
  quatro testes focados passaram. Repetir no save do checkout final.
- [x] Gate D, executor limitado do corpus (`E194`): sem flag explícita ele só
  executa a prévia; com autorização externa futura, limita a dez chamadas,
  registra decisões/receipts/latência sem prompt bruto e verifica que os seis
  saves de origem não mudaram. Três testes sintéticos passaram, inclusive
  bloqueio da 11ª chamada; modo sem egress repetiu a prévia real dos saves.
  Nenhuma chamada real foi feita e o custo monetário não é exposto pelo cliente.
- [x] Gate D, corpus real (`E195`): 10 decisões OAuth/Luna em pares ator–save
  distintos cobriram as cinco situações; uma 11ª consulta pareada ocorreu após
  cumprir a obrigação em fork e remover a opção antiga. Todos os IDs foram
  ofertados, receipts sem delta, owners revalidaram e os seis saves originais
  mantiveram seus hashes. Houve retirada do comandante, então o QG não teve
  segundo turno naquele probe; isso não é falha. Latência por consulta foi
  registrada; custo monetário ficou indisponível porque o cliente não expõe
  uso/preço. Checks de conhecimento e falha fechada são dirigidos, não prova
  universal nem autonomia longa do provider.
- [x] Gate D, checkout final preparado (`E198`): o E196 revelou e corrigiu
  referência econômica obsoleta em expansão (seed 137/dia 1.919); a retomada
  real passou até 2.160. O rerun E197 chegou a 3.600 dias nas três seeds e
  auditou os saves, mas `natural_ok=false`: seed 137 teve p95 mensal 40,8751 s
  contra 35 s congelados. O perfil tardio mostrou validação histórica repetida
  em 37 ofertas dentro do mesmo candidato mensal. A entrada direta ainda
  valida; no candidato isolado, o finalizer valida antes do commit. Um mês
  pareado do mesmo save caiu de 28,72 para 21,54 s, com 37 testes focados
  verdes. Novo digest de código/testes/catálogos:
  `2189f2b477e41caac15cf00db4c6ef7ce9bb44f39b68df46ab7fc52d80041d8f`.
  O gate integral precisa ser repetido sem alterar o limite, e o digest deve
  ser conferido novamente ao fim.
- [x] Gate D, evidência E198 registrada: três seeds chegaram ao dia 3.600 com
  auditorias e demais orçamentos aprovados; p95 mensal de 73/101 passou
  (`27,2243`/`30,1500 s`), mas 137 falhou (`38,8062 s` > `35 s`). O gate
  integral permanece aberto; mortalidade e saúde final também exigem leitura
  de produto separada da integridade causal.
- [x] Gate D, otimização E199 verificada em recorte: resposta diplomática no
  candidato mensal manteve validação no finalizer e caiu de `39,0574` para
  `34,9922 s` no mesmo mês; leituras indexadas reduziram para `32,2580 s`,
  sem mudar os `139.943` eventos. 120 testes focados passaram. O gate integral
  E199 passou no mesmo digest `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28`.
- [x] Gate D, seeds naturais 1–3 (`E199`): as três avançaram do dia zero a
  3.600 no mesmo digest, com auditoria causal e de checkpoints aprovadas.
  p95 mensal 73/101/137: `24,4627`/`28,5377`/`34,0513 s`; tempo total
  `1.990,59`/`2.175,41`/`2.427,93 s`; pico RSS máximo `2.097.352.704 B`;
  saves de `36,7–40,5 MB`; p95 de `why()` `0,1809–0,2065 s`. Todos os limites
  congelados passaram. Mortalidade por privação (4.545/2.730/3.166) e saúde
  média (96,50/225,88/246,75) permanecem alerta econômico, sem invalidar a
  auditoria causal nem provar resiliência. Evidência em `/tmp/cws-v1-final-e199`.
- [x] Gate D, fingerprint E199: `983e0b69833b66b9dbef62eea7c68e6720e3b4d209b4967f942b52bf76231c28` conferido após o gate.
- [x] Gate D, integração final E200: cenário autônomo sem decisão posterior
  injetada (`1 passed`), ciclo público de API com avanço anual e retomada
  (`1 passed`, 312,89 s), dossiês/auditoria/gate (`27 passed`), frontend
  Crônica/dossiê/observatório/app (`33 passed`), build/type-check e 20 consultas
  `why()` válidas no save E199 (p95 `0,1721 s`). Vite reportou chunk de
  772,8 kB. `git diff --check` passou.
- [x] Gate D, aceite técnico V1 E200: corpus real E195, cenário controlado,
  três seeds integrais E199, integração final e budgets passaram no mesmo
  fingerprint. Isto fecha o escopo técnico definido no plano, não declara a
  economia saudável; a mortalidade e saúde finais seguem como alerta de produto.

Em E127, os critérios do plano foram apertados para capacidade adaptativa
econômica, cadeia autônoma entre autoridade/QG/comandante, transação comum para
novos owners materiais e budgets antes do gate longo. Esta atualização não
altera os estados técnicos da matriz; o inventário transversal e os gates B–D
continuam abertos.

E128 adiciona diagnóstico read-only do save dia 1.560: Campomanso mostra falta
por coortes sem renda apesar de estoque, e Cinzaverde mostra payroll limitado
por caixa antes de privação. Isso qualifica a linha de economia como lacuna de
acesso/adaptação a investigar; sem contrafactual pareado e reprodução pelo
agente principal, o Gate B permanece aberto.

**Gate A — classificação de famílias (E130–E131).** O cruzamento E129 não
encontrou tipo material observado sem fonte nominal. Os 161 tipos estáticos
ausentes do save são **não exercitados nessa seed**, não defeitos inferidos;
ficam discriminados por arquivo/linha em `tools/medieval_material_inventory.py
--details`. Os seis nomes dinâmicos estão delimitados nos callers: encerramento
cívico, conclusão de obrigação, dissolução de força, liberação de comando,
falha/interrupção de rito e término de cerco. A leitura de fonte/testes existentes
classificou produção, consumo, compras domésticas, mercado, frete, construção,
infraestrutura, alívio, ajuda, diplomacia, alfândega, autoridade, força, campanha
e desordem cívica como **parciais**: há owners, deltas e provas focadas de
revalidação em vários subcaminhos, mas nem todos os executores têm teste
negativo nem estão no save. Migração direta foi **falha reproduzida**: viajante
inválido deixava autorização órfã. Recuperação direta também publicava estado
parcial após falha tardia. Os dois comandos agora usam candidato; o recorte
conjunto passou `33` testes (E131–E133).
Essa era a leitura parcial E130. E136/E137 concluíram o limite para comandos
diretos novos e o inventário finito; executores antigos classificados como
parciais não ganharam certificação semântica por isso.

**Mercado bilateral (E132):** a proteção já presente no checkout suprime a
segunda consulta quando o vendedor recebeu e recusou o mesmo pedido. Uma
regressão integrada com orçamento de exatamente duas chamadas passou: pedido
do comprador, `NO_ACTION` do vendedor, nenhuma terceira chamada nem pagamento.
O achado P2 da revisão anterior não se reproduz neste checkout; isto não prova
o corpus de decisões do provider real exigido pelo Gate D.

**Gate B — adaptação material parcial (E134):** reexecutei um contrafactual de
390 dias da seed 73 sem acrescentar recursos iniciais. Escolhas por affordance
ID construíram oficina e linha, depois contratos; salários e compras reduziram
a falta contra `NO_ACTION`. Save/load e auditoria causal passaram. Isto prova
**um** caminho disponível, não recuperação geral: saúde chega ao piso em ambas
as trajetórias, e Campomanso/Cinzaverde seguem em diagnóstico.

**Gate A — limite comum para comandos diretos (E136):**
`material_execution.execute_material` mantém candidato isolado, exige ao menos
um receipt de transição com delta e causa, valida owners/atividades/sufixo
causal e só então publica. `start_migration` e `recover_migration` são os dois
comandos já migrados. Negativos compartilhados impedem mutação sem receipt e
evento material sem causa; os negativos de migração impedem publicação após
erro tardio. `AGENTS.md` obriga novos comandos diretos materiais V1 a usar o
limite. A transação mensal já existe no engine; nenhum executor antigo não
migrado é declarado correto por isso.

**Inventário Gate A por família (E137).** Em 52 módulos há 161 nomes estáticos
não observados no save; os maiores blocos são força (22), alfândega (10),
criaturas (9), abastecimento de campanha (8) e movimento cívico (8).
`tools/medieval_material_inventory.py --details` dá a lista exata de
arquivo/linha/tipo. A classificação abaixo é de cobertura, não uma alegação
de que todo caminho foi executado. “Focal” distingue teste existente da
trajetória observada no save.

| Família / owner de estado | Origem e conhecimento; revalidação | Deltas, transação e negativa | Classificação |
|---|---|---|---|
| Produção, consumo, salário e imposto — Economy | Lei mensal usa estoque, facility, caixa, trabalho e preço atuais; relatórios datados só entram nas escolhas de prioridade. | Deltas de stock/account/subsistence em candidato do engine; testes focais de pagamento, conservação e consumo. | Parcial: ciclo observado, variantes não. |
| Compra, provisão doméstica e relief — Economy | Comprador/vendedor ou administrador escolhem IDs atuais; revalidam dinheiro, estoque, rota, decisão e oferta privada. | Cash/stock/freight/subsistence com candidatos nos executores diretos; negativos bilaterais e de alívio. | Parcial: principais fluxos observados, remediações não. |
| Frete, recuperação e infraestrutura — Economy/Map | Ordem e rota conhecidas, dano físico ou decisão do mantenedor; owner recalcula capacidade, material, trabalho e jurisdição. | Cargo/route/site/repair com candidato mensal ou direto; negativos de rota stale, reparo e save falho. | Parcial: envio/reparo observados, várias recuperações só em fixture. |
| Construção, emprego e pesquisa — Economy/Research | Decisão atual com office, stock, payroll, ocupação e leitura local; projeto não contrata nem pesquisa por si. | Project/facility/account/workforce/research com candidatos; negativos de recurso insuficiente e decisão copiada. | Parcial: obra/emprego/pesquisa observados, tipos especializados não. |
| Ajuda, diplomacia e compromissos — Relations/Economy | Duas decisões independentes, relatórios próprios, authority e termos/estoque atuais; obrigação nunca transfere recurso sozinha. | Obligation/memory/freight/account em candidatos; negativos de opção stale, recusa, prazo e reparação. | Parcial: pedido/aceite/cumprimento observados, reparação não nesta seed. |
| Authority, política fiscal e customs — Authority/Economy | Claims, tarifa e manifesto exigem decisão/mandato/jurisdição; inspeção e resultado são engine-owned. | Claim/tax/cargo/account; parte direta e parte no engine/candidato. Negativos de autoria, manifesto stale e commit falho; três recortes reexecutados em E137. | Parcial: tarifa observada, customs/claims não neste save. |
| Migração, força e campanha — Society/Strategy/Map/Economy | Grupo, instituição, QG e comandante usam decisões/relatórios próprios; rota, pessoas, comando e suprimento são revalidados. | Migration/detachment/plan/stock/route com candidato direto ou tick; negativos de migração E131/E133, decisão de força copiada e prazo/rota. | Parcial: migração observada; maior parte militar só em fixture. |
| Civismo, ritos e criaturas — Society/Research/Map | Grupo/instituição/criatura escolhe opção própria; pressão física, prazo e alcance são fatos, não prosa. | Protest/movement/rite/site/population em candidato ou engine; negativos focais de opção determinística/stale e criatura, reexecutados em E137. | Parcial: ecologia observada, conflito/ritos majoritariamente fixture. |

Os seis nomes dinâmicos não são um sétimo tipo de owner: `_close` cívico,
`conclude_obligation`, `_dissolve` de força, `_release_command`, `_forfeit` de
rito e `_finish` de cerco recebem variantes fechadas de seus callers. A
ausência de 161 tipos é cobertura **não exercitada**, não falha; as falhas
concretas reproduzidas nesta rodada foram as duas migrações já corrigidas.

**Gate B — primeiro elo limitante em dois assentamentos (E135):** no save
dia 1.560, Campomanso possui 9.313 rações públicas a preço 1, mas 164 de
falta; 153 artesãos, dois dependentes e nove soldados têm caixa zero, enquanto
agricultores concentram 16.070 moedas. O único facility local paga agricultores;
nenhum artesão aparece na leitura de trabalho pago. Em Cinzaverde,
`event:64122` levou o tesouro de Escárlia de 3 para 0 no payroll em Ferroalto;
`event:64177` limitou a produção local por `payroll_funds`, antes de vendas
posteriores reabastecerem o tesouro. As duas administrações têm leitura local
datada e affordance válida para oficina no estado atual, mas nenhum emprego
artesão atual; o save tem `ai_enabled=False`. Logo, o gargalo imediato é renda
do trabalho/ordem da folha, não ausência física geral de comida, e a ausência
de escolha da oficina nesse run offline não prova falta de affordance. É um
diagnóstico localizado, não balanço econômico global nem provider real.

**Gate C — cenário autônomo controlado parcial (E138-finalização):** uma nova
regressão prepara fatos iniciais e depois avança somente pelo engine e escolhas
de affordance pelo provider stub. Autoridade política, QG e criatura decidem;
restrição da rota atrasa carga e aparece na falta alimentar civil, com causas
navegáveis e save/load preservados (`1 passed`). Ainda não há nomeação/decisão
independente do comandante nessa trajetória, nem contrafactual pareado no
mesmo cenário. Isso não é observação natural nem validação do provider real.

**Gate C — cenário controlado fechado, formação natural aberta
(E139-finalização):** a nomeação do comandante agora é uma escolha institucional
após mobilização, não efeito automático. A fixture posterior prepara sua
presença, mas não injeta escolhas após começar: política autoriza, QG mobiliza
e nomeia, criatura bloqueia, carga atrasa, população perde acesso alimentar,
comandante mantém posição após observação local e QG mantém o plano após
relatório próprio. As duas decisões posteriores descendem do bloqueio; o
`why()` imediato, save/load e auditoria sobrevivem. O teste físico anterior
com rota aberta/fechada prova o contrafactual material, mas não é segunda
trajetória autônoma. `31 passed` no recorte afetado. Item 6 fechado neste
escopo; itens 7/8 e gates B/D continuam abertos.

**Gate B — resposta material eficaz no save crítico (E140-finalização):**
Campomanso/dia 1.560 tinha obra elegível, caixa de 5.148 e madeira local zero.
Uma decisão de construção seguida de compra bilateral aceita por Valedouro
abriu frete de 48 madeiras por 96 moedas numa rota física de uma aresta. No
fechamento seguinte, o projeto avançou 4/12, pagou 24 a 12 artesãos e reduziu
a falta de 164 no controle para 150; saúde 422 no controle versus 423 na
intervenção. O diagnóstico versionado carrega o mesmo save em ambos os ramos
e não o sobrescreve. O caso prova adaptação **possível e pequena**, não
resiliência natural ou recuperação geral. Cinzaverde tem affordance de obra e
quatro opções de madeira após iniciá-la, mas não recebeu o contrafactual
mensal. O Gate B mínimo V1 está fechado; estabilidade de dez anos é Gate D.

**Gate C — inventário de trajetórias naturais (E141-finalização):** três saves
de duas seeds, todos `ai_enabled=false`/`routine-rules`, têm atrasos de carga
e a seed 14 tem overflow, mas nenhum receipt `strategy_defense_*`, comando
de coluna ou rota restringida por criatura. Isso registra a ausência sem cota
de drama; não demonstra que atores com provider real enfrentariam ou evitariam
uma campanha. A cadeia natural parcial de dano/reparo permanece distinta da
fixture integrada. Item 7 segue aberto.

**Gate D — baseline e índice de eventos (E142–E143-finalização):** a medição
preliminar de um mês tardio seed 73 deu 42,31 s antes e 35,33 s depois do
append incremental no `event_index`, com candidatos transacionais isolados.
Os saves resultantes são byte a byte iguais, e testes focados do cache passaram.
No baseline, save/load foram 12,012/9,088 s, pico RSS 1,139 GB, save 18,47 MB
e vinte consultas `why()` tiveram p95 0,073 s. Uma amostra não estabelece p95
mensal nem aprova o limite provisório de 20 s; Gate D continua aberto.

**Gate D — segunda otimização e horizonte curto (E144–E145-finalização):**
índice de tipos incremental isolado e consulta de autorização de pesquisa
indexada mantiveram o save do mês pareado byte a byte idêntico e reduziram a
medição mensal para 27,12 s. Três meses sequenciais posteriores custaram
22,30/36,13/23,79 s, com conservação, save/load e auditoria causal verdes no
dia 1.710 (72.217 eventos). Essa amostra de uma seed offline não ratifica p95
nem orçamento; a saúde caiu e as mortes por privação cresceram.

**Gate B/D — disponibilidade não é escolha (E146–E147-finalização):** no
save seed 73/dia 1.710, Campomanso, Cinzaverde e Pedra Clara oferecem
oficina válida, mas `ai_enabled=false`; seis consultas falharam no intervalo
e nenhuma interpretação de provider foi persistida. O Codex OAuth/Luna
respondeu apenas a uma fixture sintética. A revisão de permissões impediu
enviar um menu derivado do save ao provider externo sem autorização específica;
o probe canônico não foi executado. Não contar isso como `NO_ACTION`, corpus
real ou formação natural adaptativa.

**Gate D — instrumento pronto, inferência pendente (E148-finalização):** o
probe canônico funciona em cópia de memória com stub tanto para `NO_ACTION`
quanto para ID oferecido; receipt não material e save intacto foram testados.
Sem autorização externa específica e sem chamada real sobre esse menu, o
corpus de provider permanece não exercitado.

**Gate D — seis meses e demanda de trabalho (E149–E150-finalização):** a seed
73/dia 1.710→1.890 levou 231,38 s nos fechamentos mensais; um mês atingiu
49,61 s, refutando a meta provisória p95 ≤20 s. O perfil localizou uma busca
linear no ledger em `workforce._event`; índice transitório reduziu os seis
meses a 158,25 s e o maior mês a 31,67 s, com save final byte a byte igual,
43 testes focados e auditoria causal do baseline verdes. Ainda não há base
multisseed nem ratificação de novo orçamento; a economia offline seguiu em
declínio material.

**Gate D — segunda seed e Knowledge (E151–E152-finalização):** seed 14/ano 4
teve seis meses entre 14,29 e 19,17 s, auditoria/save-load verdes. Na seed
73/ano 6, projeção de relatórios por destinatário reduziu seis meses de
158,25 para 146,96 s, com save byte a byte igual e 49 testes focados. O
limite provisório p95 ≤20 s segue refutado pela seed tardia; estágio das
seeds é diferente e não há orçamento novo aprovado.

**Gate D — horizonte tardio estendido (E153-finalização):** seed 73/ano 6,
dia 1.890→2.070, avançou seis meses offline em 159,69 s (p95 mensal da
amostra 34,74 s), salvou 89.366 eventos/23.613.440 bytes e passou
conservação, save/load/continuação e auditoria causal standalone. Saúde
média 147,62 e 1.605 mortes por privação acumuladas: a capacidade de
resposta demonstrada por contrafactual no Gate B ainda não se traduziu em
recuperação natural nesta trajetória. O limite provisório de 20 s segue
refutado; orçamento V1 e gate longo permanecem abertos.

**Gate C/D — inspeção do save tardio e perfil (E154-finalização):** no
intervalo natural offline 1.891→2.070 não houve campanha ou comando;
os 36 objetivos existentes são apenas de abastecimento/insumos. Houve
pedidos de ajuda e três recusas por `routine-rules`; um pedido final tinha
aceite material enumerado, mas a memória institucional era negativa.
O perfil read-only do próximo mês apontou cópia transacional e validações
de Economy/Relations como maiores custos. Nenhum desses fatos fecha
formação natural multiescala, corpus real ou orçamento.

**Gate D — validação pré-tick redundante removida (E155-finalização):**
Economy/Relations seguem validadas no candidato final antes do commit; a
validação repetida na entrada do tick foi removida porque o estado publicado
já entrou validado. Dois testes negativos de falha final/rollback elevaram o
conjunto focado para 39 testes verdes. Mesmo horizonte seed 73/dia
2.070→2.100: 14,83→12,61 s, saves idênticos byte a byte e auditoria causal
verde. É melhora localizada, não aprovação do p95 ou do gate longo.

**Gate D — reexecução de seis meses (E156-finalização):** no mesmo save de
entrada seed 73/dia 1.890, o avanço até 2.070 caiu de 159,69 para 138,70 s,
com p95 amostral 34,74→31,39 s. Save final byte a byte igual, conservação,
save/load, continuação e auditoria causal verdes. O limite provisório de
20 s segue não atendido, e uma seed de seis meses não aprova o orçamento V1.

**Gate D — segunda seed pareada (E157-finalização):** seed 14/dia
1.260→1.440 caiu de 94,72 para 73,33 s em seis meses, p95 amostral
19,17→15,75 s; save byte a byte igual, conservação e auditoria verdes.
Esse horizonte de ano 4 não apaga o p95 acima de 20 s da seed 73/ano 6,
nem substitui três seeds de dez anos no checkout final.

**Gate D — consulta causal local (E158-finalização):** no save de 89.366
eventos, 20 consultas distribuídas de `causal_view(limit=100)` tiveram p95
0,106 s; outras 20 consultas sobre os fatos de maior fanout, retornando
100 efeitos cada, tiveram p95 0,105 s. O limite provisório de 2 s passa
nesse backend/save, sem certificar UI, rede, dez anos ou o orçamento completo.

**Gate B/D — horizonte adicional e lacuna de circulação (E159-finalização):**
seed 73/dia 2.070→2.430 avançou um ano natural, com 100.921 eventos,
auditoria causal limpa e p95 mensal 23,28 s após separar checkpoint de
save/load. Saúde média 83,88 e 2.668 mortes por privação coexistem com
76.000 moedas conservadas: 46.567 nas quatro coortes agricultoras de
Campomanso, tesouro de Escarlia zerado e três fazendas paradas por
`payroll_funds`. Existem opções de ajuda e ajuste de staffing, mas a
produção não reiniciou nessa trajetória. O Gate B mínimo contrafactual
segue registrado; resiliência natural e orçamento de dez anos não passaram.

**Gate D — pré-checagem pública focada (E160-finalização):** build medieval
com `vue-tsc` e Vite passou; cinco testes selecionados de API, observatório,
paginação causal, dossiê e bundle passaram. O grupo amplo de 33 testes foi
interrompido antes do primeiro resultado após vários minutos por conter
um lifecycle público de um ano; não foi declarado verde. A regressão final
do checkout estabilizado permanece aberta.

**Gate D — negativo local do instrumento (E161-finalização):** a sondagem
de um menu civil preserva o hash do save também quando o provider falha.
Uma resposta simulada com `affordance_id` inventado é rejeitada sem alterar
o arquivo de origem; três testes focados, Ruff e `git diff --check` passaram.
É prova local de falha fechada, não uma decisão do corpus OAuth/Luna.

**Gate D — perfil de custo tardio (E162-finalização):** um mês in-memory da
seed 73/dia 2.430 levou 22,39 s sob `cProfile`, preservando o hash do save.
As maiores fatias acumuladas foram cópia transacional (6,53 s), revisão
diplomática (4,24 s) e validação de Relations (3,06 s), com sobreposição
entre chamadas; não são parcelas somáveis. Sem profiler, as cópias dos nove
owners custaram cerca de 0,05 s juntas numa única execução. O save tinha 906
propostas (767 rejeitadas); isso identifica superfície de investigação, não
um defeito comprovado nem justificativa para mudar decisões.

**Gate D — orçamento pré-gate fixado (E163-finalização):** a seed 73 avançou
sem provider ou decisões injetadas do dia 2.430 ao 2.610. Os seis meses
levaram 12,73/12,70/17,04/25,51/30,90/18,25 s (sem save/load). Juntando aos
12 meses contíguos anteriores, o p95 nearest-rank é 30,90 s, média 16,86 s.
O limite de 20 s foi refutado; fica fixado em 35 s antes do gate final. O save
de 28,30 MB levou 18,71 s para gravar e 15,06 s para recarregar; pico RSS
1,75 GB; 106.994 eventos, save/load e conservação passaram. Auditoria causal
standalone retornou `ok=true` com zero causas/autorias/roots inválidas e zero
Story ou interpretação material. A economia continuou degradada (saúde média
71,38, 3.100 mortes por privação), sem prova de resposta adaptativa natural.
O save tem 36 planos, mas zero destacamentos e nenhum evento de campanha ou
cerco: não surgiu a cadeia militar natural, sem que isso invalide a seed.
O orçamento está definido, não comprovado para dez anos ou três seeds.

**Gate D — leitura indexada da cadeia de ajuda (E164-finalização):**
`_own_open_chain` usa o índice transitório de eventos `institutional_aid_requested`
em vez de percorrer todo o ledger para cada consulta. No save do dia 2.610,
30 consultas repetidas caíram de 0,569 s para 0,036 s; nove testes focados
passaram. O replay dos mesmos 180 dias gerou save byte a byte idêntico ao
anterior (SHA-256 `93355de1…4d4285f`) e conservação/save-load equivalentes.
O tempo mensal acumulado caiu de 117,13 s para 115,54 s nesse par; é ganho
pequeno no horizonte e não prova o orçamento de dez anos. Escarlia ainda
tem opções de pedir ajuda, mas caixa e produção seguem críticos.

**Gate C — busca natural classificada (E165-finalização):** os saves atuais
seed 14/dia 1.440 e seed 73/dia 2.610 usam `ai_enabled=false`, política
`routine-rules` e nenhuma escolha injetada após a geração. Têm respectivamente
35/36 planos e 0/0 destacamentos; nenhum possui evento de campanha ou cerco.
Ajuda, relatórios de rota e transições ocupacionais ocorreram. A cadeia física
enchente→reparo da seed 14 pertence a um checkout anterior e não é atribuída
ao save atual. Item 6 continua prova em fixture autônoma com stub; item 8,
provider real, continua não exercitado neste checkout. A ausência de guerra
natural é observação válida, não êxito de uma campanha inexistente.

**Gate D — prévia e compactação do prompt (E166-finalização):** no save
seed 73/dia 2.610, o menu mensal de Escarlia possui 120 affordances, incluindo
47 alvos de staffing. Antes, o contexto repetia salário, caixa e recibos de
cada contrato em cada alvo: 39.205 bytes só nessa família e prompt total de
75.264 bytes. Os dados comuns agora aparecem uma vez por contrato, mantendo
os 47 alvos e as 120 escolhas; a família caiu a 19.738 bytes, o prompt a
55.797 bytes. IDs brutos de opção não são duplicados no contexto de staffing;
os tokens de escolha continuam na lista canônica. O módulo de emprego passou
22 testes, inclusive seleção material e negativos, mais teste focal de
cardinalidade; Ruff/diff-check passaram. É um preflight local sem envio externo,
não evidência de uma decisão OAuth/Luna ou de custo real do provider.

**Gate D — prévia dos atores institucionais (E167-finalização):** no save
seed 73/dia 2.610, três polities e oito organizações tinham menus mensais
com 10–120 opções e prompts de 3.350–55.797 bytes. Escarlia foi a maior;
Ofícios da Serra teve 31 aliases privados, Escarlia 51. Uma varredura destes
11 prompts não encontrou os cinco marcadores conhecidos de identificador
material privado. Isso não certifica todos os atores, outros estados ou
ausência de dados sensíveis por outras formas. O provider está configurado,
mas nenhuma consulta externa foi feita sem autorização.

**Gate D — verificador operacional preparado (E168-finalização):** o smoke
agora expõe duração de cada mês sem a gravação/recarga de checkpoint e p95
nearest-rank. `medieval_release_gate.py --final-v1` exige três seeds distintas,
3.600 dias e checkpoints anuais ou mais frequentes, recusa sobrescrever saves
finais e reprova tempo total, RAM, save, save/load, p95 mensal e p95 de 20
consultas `why()` contra os limites fixados. Quatro testes focados passaram;
20 consultas reais no save dia 2.610 deram p95 backend-local de 0,1218 s;
Ruff/diff-check passaram. Ferramenta pronta não é gate de dez anos verde.

| Roadmap / requisito | Owner ou superfície atual | Estado | Evidência atual | Limite e gate de fechamento |
|---|---|---|---|---|
| 0 — decisão, autoria, delta e rollback | `src/sim/medieval/events.py`, `engine.py`, `material_execution.py`, `tools/medieval_causal_audit.py`, `tools/medieval_material_inventory.py` | existente | Auditoria de autoria/rollback (E5, E8–E9, E27, E86, E101–E104). Save seed 73/dia 1.560: 61 tipos materiais, 183 grupos de delta, `ok=true`, 0 violações; teste focal `3 passed` (E126). Inventário estático: 226 callsites candidatos, 222 tipos nomeados; todos os 61 tipos e 183 grupos observados têm fonte nominal, seis pontos seguem dinâmicos e 161 tipos candidatos não foram exercitados (E129). Classificação parcial das famílias e dos seis nomes dinâmicos em E130. Migração direta não publica autorização nem materiais quando validação posterior falha (`26 passed`, E131). | Os callsites são sobreaproximação; nome não prova owner/autorização/atomicidade. Revisar negativos por classe crítica e integrar o limite comum aos novos caminhos materiais V1; não atribuir essa prova a todos os owners. |
| 0 — API, persistência e frontend sem runtime xianxia | `src/server/medieval/`, `src/sim/medieval/persistence.py`, `web/src/medieval/` | existente | API `/api/v2`, save/load e navegador focados (E29–E35) | Regressão integrada e build do checkout final; não alegar compatibilidade do legado. |
| 0 — custo de armazenamento causal | `src/sim/medieval/persistence.py`, `tools/medieval_autonomy_smoke.py` | existente; medição de três anos histórica | A medição histórica do schema 68 preservou eventos comprimidos em blocos indexados e rejeitou saves antigos sem apagá-los. No checkout anterior, a seed 73 chegou a 1080 dias/42.390 eventos: save de 12.009.472 bytes, save/load, conservação e auditoria causal verdes; terceiro ano levou 438,26 s e atingiu 716 MB de pico RSS. Índices transitórios nas validações Map/Relations reduziram o mesmo avanço de 30 dias sob profiler de 75,968 s para 55,751 s, mantendo snapshot/eventos idênticos. | O schema atual é 74; repetir a medição nele. Faltam dez anos e outras seeds, além do custo de consulta. Tempo/RAM atuais não foram medidos. Não arquivar nem truncar fatos antes de evidência. |
| 1 — produção, salários, preços/demanda e subsistência | `src/sim/medieval/economy.py`, `production_priority.py`, `consumption.py`; Economy/Society | existente | Cadeia econômica material e comparação de políticas (E7, E11, E39); smokes naturais E86/E101–E107; opções locais remanescentes E112. E150 refutou recrutamento agrícola isolado; E152 juntou contagem ocupacional e payroll produtivo próprio datados às opções de oficina; E153 provou escolha por stub e projeto aberto sem efeito grátis. E155 compôs duas decisões por IDs válidos, obra e fundação pagas, salário, compra e menor falta/saúde maior contra mundo sem obra. E156 atravessou turnos completos do `MedievalSimulator`, achou/corrigiu uma consulta de projeto sem âncora e passou save/load/auditoria. Em 25/09, pagamentos, distribuição/transferência de alívio, aceites/revisões de trabalho e compras de provisões domésticas exigem decisões autorais nos owners exercitados; household provisioning passou `15` testes de autoria bilateral. Prioridade produtiva agora também rejeita payload copiado sem `ACTOR_DECISION` (`8` testes focados). | As cadeias E155–E156 são fixtures com recursos ampliados e escolhas por stub; não demonstram escolha espontânea do provider nem recuperação econômica natural. A privação cresceu em três seeds de checkout anterior; repetir gate natural no checkout atual. O fallback offline permanece explícito; não criar subsídio automático. |
| 1 — mercado bilateral, compromisso e entrega | `markets.py`, `market_purchase_policy.py`, `diplomacy.py`, `logistics.py`; Economy/Relations | verificado | Compra depende de resposta independente do vendedor; `markets.purchase` agora exige autoria `ACTOR_DECISION` independente dos dois lados. Fixtures de entrega, recusa, autoria e save/load passaram (`29 passed` em mercado e venda tecnológica; `tests/test_medieval_markets.py`, `test_medieval_market_purchase_policy.py`, `test_medieval_technology_sale.py`). | Reexecutar recorte afetado por mudança em menu, frete ou consentimento; cadeia continua preparada e não prova emergência natural. |
| 1 — rota interrompida, recuperação e informação datada | `route_intelligence.py`, `freight_recovery.py`, `purchase_recovery.py`, `logistics.py` | verificado em fixtures | Fixture contrafactual: rota fechada piora falta/saúde versus aberta; decisão abre remessa sucessora, compra e relief melhoram condição, original fica imutável, save/load e auditoria passam (E113). Em 25/09, pedido/resposta/execução de recuperação de compra e abertura do frete sucessor passam a registrar autoria material explícita; regressão conjunta com pressão de assentamento/campanha: `35 passed`. | Aceite verificado em cenários pressionados, com decisões injetadas por IDs válidos; não prova todas as rotas, convergência natural ou provider real. |
| 1 — tarifa, bloqueio, contrabando/detecção | `customs.py`, `embargo.py`, `tariffs.py` e respectivos owners | verificado | Recortes canônicos de cobrança, apreensão/evasão, embargo e rollback (E27–E28; `tests/test_medieval_customs.py`, `test_medieval_tariffs.py`, `test_medieval_trade_embargo.py`). Em 25/09, mudança da tarifa de exportação requer autoria `ACTOR_DECISION` (10 testes focados); embargo revogável usa a escolha atual diretamente, sem decisão intermediária (13 testes focados, incluindo seleção copiada sem autoria sem efeito). | V1 não é sistema geral de guerra econômica; verificar na regressão final. |
| 1 — patrimônio produtivo | `src/sim/medieval/productive_conveyance.py`, Map/Economy | verificado | Proposta e aceite independentes, ambos exigem `ACTOR_DECISION`; payload determinístico copiado é rejeitado sem alterar controle ou bindings. Produção posterior/save-load e os negativos passaram (`13 passed` em `tests/test_medieval_productive_conveyance.py`, rechecado em 25/09). | V1 cobre transferência de workshop, não títulos genéricos, arrendamento ou captura; helper atual é API, não escolha espontânea do provider. |
| 2 — objetivos, alternativas e plano institucional | `strategy.py`, `strategy_response.py`, `concurrent_civil_decision.py` | existente | Menu concorrente e adoção defensiva real (E15, E17–E18). Plano mobilizado persiste a coluna, reavalia perda e fecha após relatório próprio; reocupação posterior bloqueia fechamento stale (E123–E124). Uma fixture pressionada compõe o mesmo plano e coluna até retomada material e revisão posterior (E126; `tests/test_medieval_persistent_campaign_chain.py`). Em 25/09, claims/reconhecimento rejeitam decisão determinística sem autoria de ator (2 regressões focadas). | A cadeia de retomada usa decisões injetadas por IDs canônicos e premissa de alimento suficiente; falta observar planejamento político amplo e provider real, sem forçar vitória em mundos escassos. |
| 2 — interferência entre campanha, criatura, comércio e população | `strategy_response.py`, `force.py`, `creatures.py`, `logistics.py`, `procurement.py`, Economy | verificado em fixture | Travessia fechada por decisão da criatura reteve a coluna mobilizada e atrasou compra bilateral na mesma rota; no fechamento mensal, Portovelho teve mais falta e pior saúde que a cópia aberta. O menu de compras agora usa a localização canônica do estoque, inclusive acampamento, sem presumir ID de cidade (`tests/test_medieval_campaign_creature_interference.py`; 7 testes focados verdes). | Ocupação, estrada alternativa fechada e escassez inicial são premissas; não há ainda reação independente de QG/rei ou prova natural/provider real. |
| 2 — barganha, recusa, contraparte e compromisso | `diplomacy.py`, `diplomacy_policy.py`, `administration_concession.py`, `reciprocal_supply.py`, RelationsState | existente | Respostas independentes e retirada bilateral em quatro turnos (E20); cadeia de ajuda e reparação (E7, E11). Em 25/09, autoria do cumprimento/remediação de recursos chega ao receipt e ao frete; a transferência de administração exige e registra a decisão atual do administrador. A validação de autoria compartilhada e abastecimento recíproco passou com recourse, repudiação, concessão e desescalada (`43 passed`). Pedido, aceite e recusa da ajuda propagam `ACTOR_DECISION` + `selected_affordance_id`; Knowledge rejeita receipts adulterados. | Negociação multi-termo e autoria estão cobertas nos módulos exercitados; ainda falta escolha espontânea/provider real e decisão futura influenciada pela memória. Não é prova da integração diplomática longa em mundo natural. |
| 2 — protesto, movimento cívico e rebelião | `civic_protest.py`, `civic_movement.py`, `civic_strike.py`, Society/Economy | verificado em fixture | Protesto gera demanda limitada; recusa/lapso pode catalisar movimento; cada grupo que adere escolhe separadamente; greve organizada precede rebelião, sem transferir administração. Repressão só é enumerada com destacamento próprio presente e abastecido, consome provisão e eleva unrest. Em 25/09, adicionei regressão em que origem determinística copiando a affordance de repressão é recusada sem mutação; formação multigrupo e cadeia rebelião/repressão passaram (`2 passed` em recorte focal). | Não prova formação espontânea nem resposta de provider real; não modela combate/casualidades de repressão nem revolução completa; não impor revolta por seed. |
| 2 — influência, espionagem, suborno, sabotagem e acusação | `espionage.py`, `investigation.py`, `sabotage.py`, `bribery.py` e políticas | existente | Testes focados de consentimento, descoberta e owners (E23, E28); Luna escolheu `NO_ACTION` em suborno | Falta uma cadeia material representativa de intriga com provider real sem forçar escolha; não contar recusa espontânea como pagamento executado. |
| 2 — quebra deliberada e repercussão futura | RelationsState/commitments, mercados, conhecimento e memória | vertical material verificada em fixture | Repudiação explícita → notice/memória → recourse escolhido → destacamento (E114). Em 25/09, venda bilateral que consome o estoque/recurso nomeado por uma obrigação de entrega agora cria breach ligado à decisão do vendedor e ao receipt de frete; a contraparte notificada lê `materially_breached` e a API distingue `commitment_materially_breached` (`tests/test_medieval_reciprocal_supply.py::test_material_sale_of_the_promised_stock_records_an_authored_breach`). | A prova cobre venda de estoque prometido, não toda ação econômica concorrente; preservar distinção entre incompatibilidade deliberada, impossibilidade e lapso de prazo. Fixture não prova frequência natural nem escolha de provider real. |
| 3 — catálogo e dependências tecnológicas | `static/game_configs/medieval/research.json`, ResearchState | verificado em recortes | Catálogo inclui irrigação, rotação, metalurgia, aço, vapor, treino, cerco, fortificação, logística, barreiras e `food_preservation`; aço/vapor têm prova material (`tests/test_medieval_industry.py`), paliçada construída/reparada e testada em cerco (E138), `field_drill` pesquisada com soldados do mundo gerado, insumos e salário reais (E141/E297). E297 compõe pesquisa paga → consentimento independente → treino pago/abastecido → força citada no combate. E298 compõe pesquisa paga de `food_preservation` → casa de defumação → perda menor do excedente, dano e reparo pago; regressão focal de economia/consumo/pesquisa/obra/reparo: `107 passed`. Em 25/09, owners de pesquisa passaram a exigir decisão de ator no patrocínio e consentimento (`48 passed`). | Pólvora e artilharia permanecem ausentes. Barreiras ainda usam conhecimento preparado na prova de aplicação. E297 cobre a doutrina `field_drill`, não conecta `hold`/`press` a pesquisa/instrução. E298 é fixture/API e uma lei de deterioração pública limitada, não prova calibração global, provider real ou emergência natural. Árvore ampla, difusão natural e provider real continuam sem prova. Não chamar a árvore tecnológica ampla de completa. |
| 3 — difusão por ensino, venda, roubo e migração | `teaching.py`, `technique_copy.py`, `technology_sale.py`, `technology_theft.py`, `apprenticeship.py`, KnowledgeState | verificado em recortes | Testes focados para as quatro vias. Roubo exige produção técnica recente (E121) e requer `ACTOR_DECISION`; E296 liga `metallurgy` roubada a obra paga de `efficient-furnaces` e maior saída de ferro pela linha local, com conhecimento datado e sem efeito quando ausente. Cópia paga também valida decisão atual e affordance recomposta (`20 passed` na regressão conjunta com roubo, venda, treino e sighting). Divulgação/sighting voluntária exige autoria, inclusive na proposta de ensino (`24 passed` em recorte de tecnologia/diplomacia). Ensino exige consentimento atual `ACTOR_DECISION` do docente e aprendiz; payload determinístico exato falha sem alterar conhecimento. Venda bilateral de `field_drill` → treino pago/datado → força da coluna (E122); ensino → conhecimento → treino local → força após conclusão com save/load/auditoria (E137). E295 completa o recorte de migração material → instrução paga → conhecimento no destino → obra de irrigação → produção maior. E297 liga pesquisa paga → instrução da coluna → efeito em combate para `field_drill`. | E295–E297 são cenários preparados/API, não emergência natural nem provider real. As tecnologias restantes, árvore ampla, difusão natural e roubo de outras capacidades continuam incompletos. |
| 3 — aplicação, operador, equipamento e manutenção | Research/Economy/Map/Force | existente | Metalurgia → forno → +98 ferro com Luna e owners (E22); cerco defensivo exige posição e provisões (E115); produção avançada cai sem trabalho/sítio (E116). Treino de campo por coluna exige técnica, decisão, ferramentas e três dias abastecidos; combate cita conclusão (E119). `field_logistics` só expande bagagem/provisões após treino (E120). Paliçada exige obra paga, altera resistência em cerco apenas enquanto operante e volta após reparo pago (E138). Em 25/09, `repair_started` propaga a decisão/affordance do mantenedor ao lado do receipt owner dos termos; teste focal de reparo, desgaste, serviços e campanha: `40 passed`. | Árvore tecnológica ampla e difusão aplicada permanecem parciais. As provas são fixtures; smokes naturais anteriores não validam este checkout. |
| 4 — força, marcha, provisões e comando | `force.py`, `force_command.py`, `campaign_supply.py`, `garrison_policy.py` | existente | Mobilização e despacho reais com Luna, carga física e save/load (E18–E19); plano defensivo sobrevive à mobilização e reage à perda da coluna (E123). A mesma coluna marchou, recebeu frete real, cercou e permaneceu até a revisão do dia 31 em fixture abastecida (E126). Estoque baixo faz o cerco expirar sem ocupação (E127); fechamento físico de acesso também o interrompe (E130). Menu de defesa permite 10/40 dias com custo real; 30 dias de consumo/agenda preservam a coluna e elevam fadiga (E134), alterando perdas em combate posterior controlado (E135). A abertura do mundo possui pequenas coortes de ocupação militar dentro da população total, sem colunas ou salários gratuitos; as três instituições têm opções de mobilização após relatórios atuais (E139). Em 25/09, mobilização, preparo em posição, nomeação de comandante, doutrina e despacho/frete de campanha passam a carregar autoria material explícita; regressão focal com retirada e campanha persistente: `37 passed`. | Recrutamento por iniciativa de campanha e campanha natural longa ainda não foram provados; decisões de provider real não foram validadas neste checkout. |
| 4 — recrutamento e reposição de pessoas | Society/Knowledge, `workforce.py`, `research.py`, `strategy_response.py`, `force.py` | existente | E142 compõe falta real de assistentes em pesquisa → oferta → decisão de grupo → conversão sem criar população. E144 compõe soldados comprometidos em outras colunas → plano defensivo sem força → falta tipada só com rota/ração/caixa válidos → escolha da instituição de convidar → escolha independente do grupo → bolsa/30 dias → nova decisão de mobilizar a coorte formada. Save/load e auditoria causal passam; `NO_ACTION` e ID forjado não criam oferta. | A prova de campanha é fixture com decisões injetadas, não escolha de provider real. Guarnição já permite rotação material; o roadmap não define efetivo-alvo para reposição após perdas, então não criar quota automática sem decisão de produto. O smoke natural curto não inclui esta pressão. |
| 4 — terreno, informação, moral/fadiga e combate | `field_engagement.py`, `field_aftermath_policy.py`, `force_contact_policy.py`, Map/Knowledge | existente | Contato é datado e limitado; E20 comprova decisões bilaterais. Floresta versus planície altera modificador e baixas com demais fatos iguais (E131). Sem relatórios próprios de ambos os acessos, investimento não abre; observação nova cria opção válida e ID anterior é recusado (E132). Expedição longa atinge fadiga 1 por 30 dias de consumo real (E134); combate tardio da mesma força, ainda abastecida, sofre mais baixas que combate imediato e registra fadiga 0/1 (E135). Save/load/auditoria nos cenários. | São contrafactuais controlados, não planejamento geográfico amplo, provider real ou campanha natural longa; o rival do combate tardio é premissa da fixture. |
| 4 — cerco, ocupação, guarnição e solução política | `siege_campaign.py`, `settlement_investment.py`, `garrison_policy.py`, `campaign_ceasefire.py` | existente | Fatias materiais de cerco/guarnição/cessar-fogo (E11, E20). Cidade própria ocupada por rival permite investimento baseado em relatório (E125). A cadeia E126 parte da decisão de plano até breach/retomada. E128 parte da mesma mobilização, registra consentimento independente ao cessar-fogo, retirada material separada dos dois lados e fechamento do plano após observação. Fechamento físico de acesso levanta o investimento com link ao fato causador, sem ocupação (E130). Em 25/09, ocupar após breach e estabelecer/retirar controle territorial exige decisão atual `ACTOR_DECISION`; seleção copiada falha sem mutação e a validação de Society também verifica a origem persistida (`25` testes focados de cerco/treino). | São fixtures com decisões injetadas por IDs canônicos, não escolha de provider real; ainda faltam controle de longo prazo, informação/terreno e negociação surgindo em mundo natural. |
| 5 — ritos com custo, alcance e interrupção | ResearchState, `character_rite_policy.py`, Society/Map | existente | Ritos restaurativos e alcance material em testes focados (E24). Em 25/09, o owner de patrocínio/cancelamento passou a exigir `ACTOR_DECISION`; uma escolha determinística que copia affordance válida é recusada sem mutação (`tests/test_medieval_rites.py`). | Escolas mágicas gerais, recuperação, contramedidas e ameaça ritual/defesa de vila permanecem lacunas de produto; este recorte não valida escolhas espontâneas de provider. |
| 5 — criatura com território, necessidade e decisão | `creatures.py`, `creature_policy.py`, Environment/Map | existente | Drake percebe frete real e Luna escolheu demanda sem dano automático (E26). Regressão end-to-end percorre o prazo agendado pelo `MedievalSimulator`: no `due_day`, o menu recomposto oferece ataque; o provider stub escolhe e o owner aplica perda de coorte, expira a demanda e registra decisão/delta/fonte, sem fechar a rota. Outra trajetória escolhe dano de instalação no prazo; o owner reduz integridade/capacidade, publica observação causal ao mantenedor e recompõe affordance válida de reparo. Os três módulos de criatura passaram `22` testes focados. Separadamente, `test_damage_is_observed_repaired_gradually_and_the_route_recovers` passou e prova obra material paga e recuperação da rota pelo owner. | Escolhas injetadas; o teste de reparo é fixture separada, não uma única trajetória contínua criatura→mantenedor→recuperação. Negociação, recuo e formação espontânea permanecem sem prova composta. Não exigir ameaça em seed natural. |
| 6 — provider real escolhe só opções válidas | `ai_decider.py`, `concurrent_civil_decision.py` | verificado | OAuth Codex/Luna escolheu affordances em economia, campanha, tecnologia e criatura; ID stale/recusa falham fechados (E14–E26) | Amostras limitadas não são dez anos com IA; orçamento, latência e falhas precisam de gate final representativo. |
| 6 — observador onisciente, dossiers e crônica causal | API `/api/v2/query`, `web/src/medieval/` | existente | API/Vitest e Playwright reais para dossiê → causa e save/load (E29–E38). A tela Trabalho aceita agora as cinco origens canônicas, localiza pesquisa/alfândega/recrutamento, nomeia ocupação e mantém “Por quê?”; 3 testes focados, type-check e build passam (E146). | Navegação humana em navegador e cobertura observável das demais cadeias ainda precisam do gate final. |
| 6 — três seeds naturais por dez anos, offline | `tools/medieval_autonomy_smoke.py`, `medieval_causal_audit.py` | existente | Seeds 73/101/137 completaram o gate em checkout anterior, com saves anuais, conservação, save/load e auditoria standalone (E86, E106–E107). No schema 67, a seed 73 chegou a 1080 dias; o dia 420 expôs opção de migração sem conta doméstica, filtrada sem criar recursos, e a auditoria final passou. | O schema 68 e a decisão tática do comandante tornam esse gate histórico: repetir as três seeds por dez anos no checkout final. A saúde média anterior caiu para 477,75; a oficina continuava ofertada, mas `routine-rules` não a escolhia. Esse stress offline não representa provider real. |
| 6 — MetaGame/Laya como observador do trabalho | `.agent/skills/task-orchestration/runtime/` | verificado | Sessões shadow com `primary_signal.provider=laya`, baixa confiança e decisão efetiva neutra (E48, E54, E69, E90, E110, E121, E124, E133) | Sinal não valida código nem altera NPCs; repetir checkpoint antes de encerrar gate, mantendo observer efêmero. |

Na seed 73 sem reforço de recursos, a oficina já aparece no menu mensal junto da leitura local datada de emprego; `NO_ACTION` não a constrói. Uma consulta real a Luna no dia 30 ofereceu essa oficina entre 29 opções e recebeu a escolha canônica de emprego agrícola em Pontenegro. O owner criou o contrato e o contrafactual offline até o dia 360 melhorou falta/saúde locais, mas não recuperou a saúde média mundial. Outra consulta real no dia 720, com 1.495 pessoas sem poder comprar comida em Pedraclara e falta de 81 rações em Pontenegro, escolheu socorro em Pontenegro entre 46 opções; o owner executou e a auditoria causal passou. Uma nova fixture da seed 73 **sem reforçar recursos** fez um stub escolher oficina, fundação e contratos de trabalho em meses distintos: houve salário e mais compras; no dia 390 a falta caiu de 2.264 para 1.604 rações contra `NO_ACTION`, mas a saúde chegou ao piso em ambos. Save/load e auditoria passaram. Isso verifica a possibilidade material de resposta e seu limite, não escolha espontânea da oficina, autonomia longa ou equilíbrio econômico.

A conclusão de transição ocupacional agora move a fração proporcional do saldo doméstico com as pessoas, registrando deltas e conservando moeda. O smoke offline no schema 68 chegou a 120 dias com auditoria limpa, mas Pedraclara e Portovelho ainda ficaram em 862/860 de saúde. Portanto a lacuna de resiliência econômica permanece aberta; o teste corrigiu um mecanismo específico de empobrecimento sem garantir prosperidade.

Na cadeia militar, a instituição agora nomeia/libera a pessoa, enquanto o comandante atual escolhe `hold`/`press` em um turno separado após contato local. A fixture comprova essa separação e a revalidação pelo owner, não substitui objetivo político do rei, planejamento do QG, transmissão de ordens ou campanha espontânea multissetorial. A linha de comando/campanha acima continua `existente`, não `verificado` em escopo amplo.

Próxima leitura: fechar os aceites materiais ainda abertos antes de repetir o gate natural no checkout final. A leitura de acesso à comida e a validação do menu militar com provider real seguem pendentes; rotação de guarnição não justifica inventar efetivo-alvo. Uma suíte focada verde não altera sozinha o estado de outra linha.

**Atualização da vertical da criatura — 25/09/2026:** a evidência mais nova
supersede o limite de “fixture separada” descrito na linha 5. Uma mesma trajetória
agora cobre dano da instalação no prazo, queda da capacidade, relatório causal ao
mantenedor, escolha provider-stub do reparo, consumo de material/trabalho e
recuperação da rota. O material local já estava provisionado pela fixture; isso
não prova cadeia natural nem provider OAuth.

Outra regressão prova demanda sem tributo → restrição no prazo → uma revisão
agendada única no dia seguinte → recuo escolhido pela criatura. A rota fica
fechada até essa escolha. Isso atualiza a lacuna de “recuo” da linha 5; a
resposta institucional `NO_ACTION` com causa está verificada na fixture, mas
comportamento espontâneo continua pendente. O
grupo final de três módulos da criatura mais a regressão focal de reparo passou
`24` testes.

**Auditoria da trajetória e raiz do ciclo inicial — 25/09/2026:** save/load e
auditoria standalone da mesma fixture encontraram seis leituras materiais
iniciais `subsistence_resolved` sem causa nomeada. A Economy agora atribui
`world_generation/initial_subsistence` somente se não houver causa canônica,
preservando os receipts e o payload de subsistência. A trajetória completa
termina com auditoria limpa; o conjunto focal de criatura, magia,
infraestrutura, consumo e auditoria passou `43` testes. Materiais de reparo
continuam pré-provisionados e as decisões são stubs. Resposta institucional,
formação espontânea e provider OAuth não foram demonstrados.

**Resposta institucional explícita — 25/09/2026:** a trajetória já registrava
`NO_ACTION`; o teste agora valida autoria `ACTOR_DECISION` e link causal desse
receipt ao aviso da demanda visto pela instituição recusante. A regressão focal
passou (`1 passed`). A resposta é de provider-stub, não prova OAuth nem
comportamento natural. O total `43 passed` da validação de criatura/economia
continua sendo o recorte conjunto anterior; este teste foi rodado isoladamente
após o reforço da asserção.

**Atomicidade do alívio — 25/09/2026:** reproduzi falha parcial quando a
atualização de observações locais lança após o owner consumir estoque e atualizar
pantries/necessidade. `distribute_relief` agora só publica a cópia candidata
após todo o fluxo concluir. Regressão injeta a falha e exige snapshot integral
inalterado; relief + institutional aid passaram `41` testes. Isso não atesta
atomicidade de todos os owners nem rollback global mensal.

**Gate econômico curto atualizado — seed 14 até 1.290, 25/09/2026:** save/load,
conservação e causal audit `ok=true` (51.897 eventos, 40.420 materiais, zero
violações). No último ciclo, déficit agregado 530→691, saúde 318,62→302,62,
unrest 512,38→533,38 e mortes acumuladas 162→180. O caso de Campomanso tinha
estoque público/preço/oferta suficiente (3.158/1/4.541) e ainda 428 de falta;
contas por coorte mostram saldo muito concentrado. O fallback destinou duas
ajudas às maiores faltas (Pontenegro/Ferroalto), não ao caso menor. Isso mantém
a lacuna de agência/acesso aberta e não autoriza balanceamento automático nem
conclui comportamento do provider.

No mesmo save, o inventário dos 40.420 eventos materiais separa 657 de origem
`actor_decision` e 39.763 determinísticos; as 153 raízes sem evento-pai foram
validadas em seis domínios, com zero material sem link/root. A evidência é só do
que a seed emitiu; a auditoria semântica dos owners e de caminhos não exercidos
continua aberta.

**Referências de premissa raiz — 25/09/2026:** o auditor agora valida a
existência do owner citado por cada root, não apenas seu formato. Teste focal
aceita `stock:one` existente e rejeita `stock:missing`; save natural seed 14/dia
1.290 revalidado com 153 roots válidas e zero erro. Auditoria semântica de
owners e caminhos não exercidos segue aberta.

**Atomicidade da recuperação de frete — 25/09/2026:** o executor agora abre o
sucessor em cópia transacional e publica somente após validação. Falha injetada
depois da abertura do frete deixa snapshot, eventos, estoque e agenda originais
inalterados. Recuperação de frete + causal audit: `15 passed`; auditoria de
atomicidade dos demais owners permanece aberta.

**Reativação de infraestrutura — 25/09/2026:** o owner agora reativa no
candidato transacional, atualiza leituras e valida Knowledge antes de publicar.
Falha injetada após o refresh preserva o snapshot original; suíte focal de
infraestrutura: `23 passed`. Duas falhas no teste combinado eram fixtures
defasadas: faltavam a decisão causal da construção, roots das premissas de
cenário e autoria do reparo. Após ajustá-las ao contrato atual, o grupo
barreiras + infraestrutura + recuperação de frete + causal audit passou
`41 passed`; Ruff e `git diff --check` passaram. Atomicidade dos demais owners
continua aberta.

**Autorização de reparo — 25/09/2026:** criação da decisão do owner, projeto de
reparo e objetivos de materiais agora ocorre em candidato transacional e só é
publicada após validar Economy/Strategy. Falha injetada depois de criar projeto
e objetivos preserva o snapshot. Barreira + infraestrutura: `25 passed`; a
mudança não prova atomicidade de outros executores nem rollback mensal global.

**Integração do recorte — 25/09/2026:** cerco/campanha, barreiras,
infraestrutura, recuperação de frete e causal audit passaram `60` testes; Ruff e
`git diff --check` passaram. Não substitui a suíte completa nem o gate longo.

**Início de construção/expansão — 25/09/2026:** owners e adapters agrupam
receipt de autorização e projeto em candidato transacional; falha injetada após
criar o projeto preserva snapshot original. Construção `21 passed`, expansão
`18 passed`; validação cobre início do projeto, não seu progresso mensal.

**Fundação de linha produtiva — 25/09/2026:** owner direto e adapter agora
agrupam decisão/projeto em candidato transacional e publicam após validar
Economy. Falhas injetadas após criar o projeto preservam o snapshot original.
Construção + expansão + fundação: `39 passed`; Ruff e `git diff --check`
focados passaram. Progresso mensal e atomicidade transversal permanecem abertos.

**Progresso mensal de obra — 25/09/2026:** chamadas diretas agora agrupam
consumo de materiais, folha/coortes disponíveis e comissionamento do site em
uma transação; falha após payroll deixa mundo e workforce intactos. O loop
mensal reutiliza sua transação externa para evitar cópia aninhada. Construção,
expansão e fundação passaram `51` testes; Ruff/diff-check passaram. Rollback dos
outros owners e do mês completo ainda não está demonstrado.

**Divulgação de conhecimento — 25/09/2026:** receipt e sighting de técnica são
publicados juntos num candidato validado por Knowledge; falha após o receipt
preserva o estado original. Divulgação/venda/pesquisa: `35 passed`; Ruff e
diff-check passaram. Não comprova a auditoria transacional global.

**Provisões agregadas — 25/09/2026:** intenção, aceite bilateral e transferência
de alimento/dinheiro são publicados juntos. Falha depois do receipt deixa o
mundo inalterado; o recorte de provisões passou `17` testes, Ruff e diff-check.
Não é prova de rollback global ou mercado amplo.

**Serviço de rota e roots de campanha — 25/09/2026:** mutação do Map e receipt
do mantenedor agora são atômicos; regressão falha após update sem publicar
mudança parcial. Corrigidas três roots de fixture (`scenario_bootstrap`) que
faziam a auditoria da cadeia campanha-criatura falhar. Campo/campanha/serviço:
`19 passed`; Ruff/diff-check passaram. A fixture continua pressionada e não
prova surgimento natural.

**Leitura pública de acesso alimentar — 25/09/2026:** a API e Finanças expõem
estoque/preço públicos, saldo agregado por ocupação, ração pública estimada
inacessível e receipts dos componentes da projeção. É uma leitura onisciente,
não uma falta canônica nem conhecimento dos atores. API, smoke e painel têm
validações focadas; type-check e build passaram. A economia permanece sem
decisão espontânea de provider atual e sem gate natural de longo prazo.

O conjunto de fontes agora inclui receipts de grupos e de jornadas,
transições, destacamentos, protestos, movimentos e greves que explicam o
`available_count` usado na estimativa. Uma migração ativa comprova navegação
até seu receipt e a consulta permanece read-only; teste focal do smoke: `2
passed`; migração: `1 passed`. Isso não converte os receipts em causal links
nem altera a simulação.
