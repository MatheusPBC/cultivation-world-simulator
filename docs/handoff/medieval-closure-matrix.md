# Matriz de fechamento do fork medieval

> Fechamento vigente: [contrato de conclusão](../../medieval-completion-contract.md),
> de 28/09/2026, marcos M0–M8 incluindo povos, magia e religião. Checks E históricos
> permanecem evidência do recorte descrito, não conclusão do contrato ampliado.

## M0 — referência do roadmap ao contrato atual

| Requisito do roadmap | Marco atual | Owners e integração exigida | Cobertura e evidência autoritativa |
|---|---|---|---|
| 0. Estabilizar fundação: autoria, affordances, causalidade, rollback, runtime | M0/M7/M8 | `material_execution`, `events`, owners canônicos e `MedievalSimulator`; decisão/causa, revalidação e publicação atômica | Base e limites em E265/E266; inventário e testes por família nas linhas Gate A. Cobertura global parcial; regressão final nas superfícies alteradas. |
| 1. Economia e informação material: preço/demanda, mercado, tarifa, bloqueio, contrabando, escassez e propriedade | M1/M3/M7 | `economy`, `markets/procurement`, `logistics/routing`, `tariffs/embargo`, `society/demography`, `KnowledgeState` | Módulos e provas estreitas existem; E263 prova alívio agudo; E264 mostra oficina bloqueada por `payroll_funds` e controle confundido pelo fallback offline. Adaptação sustentada aberta. |
| 2. Estratégia/diplomacia: objetivos, concessão, negociação, commitments, persuasão, espionagem, suborno e sabotagem | M2/M3/M6 | `StrategyState`, `AuthorityState`, `KnowledgeState`, `diplomacy*`, `commitments`, `espionage`, `bribery`, `sabotage` | Fixtures e escolhas OAuth/Luna situadas em E257–E261; composição autônoma entre autoridade, comando e memória posterior não demonstrada. Ver M2/M3. |
| 3. Conhecimento, produção e poder: pesquisa, conservação, aço/pólvora/artilharia/vapor/logística/barreiras/doutrina; difusão e aplicação | M3/M5 | `ResearchState`, `economy`, `workforce`, `KnowledgeState`, `technology_*`, `teaching/apprenticeship` | Pesquisa/difusão/treino têm recortes, mas catálogo não equivale a consumidor material. Cada tecnologia nomeada ainda precisa de integração/prova no M3. |
| 4. Campanhas/território: força, recrutamento, manutenção, comando, reconhecimento, suprimento, combate, retirada, cerco, ocupação e solução política | M2/M7 | `StrategyState`, `AuthorityState`, `force*`, `campaign_*`, `siege_campaign`, `logistics`, `territorial_control`, owners de população/economia | Fixtures persistentes e interferência são evidência histórica; M2 exige cenário autônomo com autoridade/QG/comandante e efeito civil após decisões independentes. Não extrapolar fixture para emergência natural. |
| 5. Magia, criaturas e ação individual | M4/M5/M6 | Society/Research owners e `rites`, `site_services`, `creature*`, `character_*`, `assembly_denial` | Quatro povos e recortes de rito/ward/drake/serpente existem. Diferenciação material, elemental/evocação, ameaça/contramedida e agência religiosa continuam abertos. |
| 6. IA, observabilidade, save/load e calibração | M7/M8 | `ai_decider`, contexto de Knowledge, `queries`, API medieval, UI Atlas/Crônica/dossiers/`why()`, persistence/event chunks | E256–E261 registra corpus e limites; E199/E200 é histórico. Experiência integrada e gates no checkout estabilizado seguem abertos. |

- [x] M0 crosswalk: mapear as sete seções (0–6) do roadmap a M0–M8,
  owners/integradores e evidência/limites acima. Os requisitos internos têm
  checklists próprios em M1–M8; esta tabela não declara capacidades concluídas.

- [x] Preservar o WIP do HEAD `51c213df` em snapshot local recuperável: patch
  binário dos arquivos rastreados, arquivo dos 23 arquivos não rastreados,
  status/branch/HEAD e hashes em `/tmp/medieval-m0-checkpoint.refkrM/` (`E265`).
- [x] Revisar individualmente o conjunto recuperável E244–E255 e classificar
  limites (`E266`): dez saves E245/E247–E249/E251–E255 passaram a auditoria
  causal atual. E244, E246 e E250 não têm output reproduzível preservado; manter
  esses registros como histórico sem prova, sem inventar resultado.
- [x] Mapear as sete seções do roadmap para M0–M8 e registrar estado corrente
  versus histórico; a revisão das linhas detalhadas de cada requisito continua
  vinculada aos itens específicos do contrato.

Atualizada em 28/09/2026. O checkout usa save schema 78, Economy schema 19 e Knowledge schema 10; saves anteriores continuam rejeitados. Esta matriz acompanha o plano V1 histórico, o diário de evidências e o roadmap. `Verificado` vale somente para o recorte descrito; `Existente` não comprova o aceite amplo; `Lacuna` indica prova ou implementação ausente. E1–E243 estão registrados antes deste adendo; E256–E264 documentam o corpus atual. E244–E255 foram classificados individualmente no diário E266 quando havia artefatos recuperáveis; E244, E246 e E250 não têm output reproduzível. E222, E225, E228 e E230 não produziram decisão live do provider.

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
- [ ] Gate B, localizar uma resposta viável que reduza pressão de forma
  sustentada sem deslocar privação; medir acesso, renda, produção, caixa e saúde
  por coorte e registrar a escolha/recusa no fluxo normal. E272 mostra que a
  política fallback já cria emprego em ambos os ramos, mas não fecha esse aceite.
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
- [ ] E275, diagnóstico read-only: rastrear as 40 moedas emprestadas pela
  primeira fronteira de produção; localizar a destinação, comparar a ordem das
  facilities e explicar por que o alvo continuou bloqueado. Decidir se o
  affordance atual representa crédito operacional geral com transparência ou
  precisa ser restringido/removido. Não implementar earmark/reserva futura.
- [ ] Gate B estrutural: isolar adaptação de renda/payroll e medir produção,
  salário e acesso sem confundir a resposta com a política offline.
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
| 3 — catálogo e dependências tecnológicas | `static/game_configs/medieval/research.json`, ResearchState | existente | Catálogo inclui irrigação, rotação, metalurgia, aço, vapor, treino, cerco, fortificação, logística e barreiras defensivas; aço/vapor têm prova material (`tests/test_medieval_industry.py`), paliçada construída/reparada e testada em cerco (E138), e `field_drill` foi pesquisada com soldados do mundo gerado, insumos e salário reais (E141). Em 25/09, os owners de pesquisa passaram a exigir decisão de ator tanto no patrocínio como no consentimento; quatro módulos de pesquisa/difusão passaram (`48 passed`). | Pólvora, artilharia, conservação e doutrina permanecem ausentes ou sem aceite material; conhecimento de barreiras foi premissa da fixture, não descoberta natural. A autoria foi verificada no recorte, não a árvore ampla, difusão natural ou provider real. Não chamar a árvore ampla de completa. |
| 3 — difusão por ensino, venda, roubo e migração | `teaching.py`, `technique_copy.py`, `technology_sale.py`, `technology_theft.py`, KnowledgeState | existente | Testes focados para as quatro vias. Roubo exige produção técnica recente (E121) e requer `ACTOR_DECISION`; cópia paga também valida decisão atual do ator e affordance recomposta (`20 passed` na regressão conjunta com roubo, venda, treino e sighting). Divulgação/sighting voluntária exige autoria, inclusive na proposta de ensino (`24 passed` em recorte de tecnologia/diplomacia). Ensino exige consentimento atual `ACTOR_DECISION` do docente e aprendiz; payload determinístico exato falha sem alterar conhecimento. Venda bilateral de `field_drill` → treino pago/datado → força da coluna (E122); ensino → conhecimento → treino local → força após conclusão com save/load/auditoria (E137). O grupo focal de 25/09 para pesquisa, ensino, treinamento, ajuda e patrimônio produtivo passou `74` testes. | Ensino é transferência imediata de conhecimento, não curso institucional; migração e roubo ainda precisam de composição aplicada equivalente. São fixtures com decisões injetadas, não prova de difusão ampla nem provider real. |
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
