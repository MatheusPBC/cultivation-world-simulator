# Contrato de conclusão do Medieval

28/09/2026 — execução em andamento; M0 preservado em checkpoint local
`6f78ea11`; aceite controlado de M1 registrado em E282; Gate B natural segue
aberto para M8.
Na criação do checkpoint, a branch estava 27 commits à frente de
`github-personal/codex/medieval-remote`. E275 foi registrado em `2eb1f9e3`; a
branch agora está 28 commits à frente e continua sem push.
E268 audita dois saves de continuação até o dia 1.110 sob o schema e fingerprint
daquele recorte; não fecha M1, não é carregável no schema atual e não valida
outros seeds.

## Resultado e autoridade documental

Entregar um medieval fantástico jogável e investigável: instituições, personagens,
povos e criaturas decidem com conhecimento próprio e meios reais. Economia,
campanha, tecnologia, magia e religião funcionam dentro do mesmo mundo. O Dao
enxerga a verdade e consegue investigar por que as coisas aconteceram.

Este contrato é a ordem de fechamento solicitada em 28/09 e substitui a redução
de escopo do [plano V1](docs/handoff/medieval-finalization-plan.md). O
[roadmap](docs/handoff/medieval-roadmap.md) conserva requisitos, a
[matriz](docs/handoff/medieval-closure-matrix.md) conserva cobertura e o
[estado atual](docs/handoff/medieval-current-state.md) conserva evidências.
Não criar outro plano concorrente. Checks históricos não certificam código novo.
Registro local `.agent/` não substitui este contrato versionável.

Conclusão exige todos os marcos abaixo. Não exige todas as combinações possíveis
de guerras, sociedades ou feitiços. Cada capacidade tem recorte explícito;
nenhuma pendência obrigatória pode ser adiada silenciosamente para fechar gate.

## Diagnóstico atual

| Área | Base confirmada | Lacuna de fechamento |
|---|---|---|
| Causalidade | Eventos, owners, auditoria, inventário e transação comum | Revalidar caminhos alterados; não certificar owners inteiros por um teste |
| Economia | Salários, mercado bilateral, frete, auxílio, oficina, crédito familiar | E264 recebeu madeira mas bloqueou obra por `payroll_funds`; auxílio nos dois ramos confundiu resultado; falta adaptação estrutural |
| Política/campanha | Offices, planos, coluna persistente, comando, cerco, relatórios | Continuidade autônoma, revisão, controle sustentado e efeito civil investigáveis |
| Tecnologia/intriga | Pesquisa, aplicação, difusão, espionagem, suborno, sabotagem, compromissos | Capacidades nominais restantes e composição aplicada; catálogo não basta |
| Povos/raças | `human`, `elf`, `dwarf`, `orc` em personagens, coortes e geração | Diferenciação material delimitada, convivência, demografia, agência e UI integradas |
| Magia | Skills elemental/proteção/restauração/evocação; restauração, wards, contramedidas, recuperação e observação | Skill declarada não prova feitiço executável; elemental/evocação e ameaça/resposta compostas abertas |
| Religião | Ordens/cultos, Ordem da Aurora, patrocínio e negação de assembleia | Identidade religiosa, adesão, decisões e consequências institucionais próprias |
| Criaturas | Drake/serpente fluviais, metabolismo, memória, tributo, restrição e dano | Negociação/recuo/contramedida e consequência composta; não ecologia universal |
| Produto/operação | Atlas, Crônica, dossiês, `why()`, saves segmentados e corpus OAuth | Cobertura dos marcos novos, navegação humana e gate no checkout final |

Fontes: `src/classes/society/models.py`, `society/demography.py`,
`src/classes/research/models.py`, `src/classes/environment/creature.py`,
`static/game_configs/medieval/{society,research}.json`,
`src/sim/medieval/{rites,assembly_denial,ai_decider,material_execution}.py` e matriz.
O roadmap de 14/09 e linhas antigas da matriz contêm estados superados;
reconciliar essas afirmações é parte de M0, não repetir sua implementação.

## Invariantes

```text
estado → observação datada → opções canônicas concorrentes → decisão independente
→ owner revalida → transação → fatos/deltas → informação/memória → próxima decisão
```

- IA seleciona ID válido ou `NO_ACTION`; não escreve números, leis ou evidência.
- Aceite bilateral continua independente; obrigação não executa transferência.
- Dao onisciente não ensina atores. Mensagens precisam de canais e datas reais.
- Magia tem leis engine-owned; crença e texto religioso não comprovam milagre.
- Novos comandos materiais usam `execute_material`; fases usam o candidato
  do simulador. Falha não publica mutação parcial.
- Estado pertence aos owners existentes. Não duplicar inventário, tesouro,
  população, planner ou conhecimento para acomodar novas áreas.
- Não impor guerra, conversão, perseguição, variedade ou atividade por quota.
- Relevância de memória pode cair; o histórico causal não é apagado para caber.

## Sequência única

```text
M0 checkpoint/inventário → M1 economia → M2 campanha/comando
→ M3 tecnologia/intriga restantes → M4 povos → M5 magia/criaturas
→ M6 religião → M7 experiência integrada → M8 validação/entrega
```

Uma frente material ativa por vez. UI mínima e persistência acompanham cada
marco; M7 integra a experiência. Dependência bloqueante é corrigida no owner
responsável e o trabalho retorna ao marco original.

### M0 — Checkpoint recuperável e lista finita

- [x] Preservar WIP em checkpoint local recuperável após conferir status e
  arquivos não rastreados. E265 criou um snapshot reversível em
  `/tmp/medieval-m0-checkpoint.refkrM/`; o checkpoint revisável seguinte é o
  commit local `6f78ea11` (`wip: checkpoint medieval completion work before E275`),
  feito na branch `codex/medieval-remote`. Ele registra 275 arquivos e mantém o
  estado anterior recuperável; não houve push, merge ou deploy.
- [x] Reconciliar gates atuais com E199/E200 históricos e E256–E266. E266
  auditou dez saves recuperáveis dos artefatos E244–E255; E244/E246/E250
  ficaram classificados como sem output recuperável. Isso não certifica gates
  nem torna as decisões nesses saves evidência natural.
- [x] Vincular as sete seções do roadmap a M0–M8, owners/integradores e
  estado da evidência na matriz (E267). Requisitos internos permanecem abertos
  nos checklists de seus marcos; o crosswalk não os declara concluídos.

Aceite: base recuperável, nenhuma obrigação sem marco e próxima tarefa única.
Inventário finito; não abrir nova caça irrestrita a owners.

### M1 — Economia adaptativa

- [x] Isolar caixa → folha → emprego → produção → renda → compra → saúde e
  distinguir conhecimento, opção, autoridade, meios, prioridade e escala.
  E208 prova crédito voluntário → folha → salário; E264/E275 localizaram a
  disputa real pelo caixa; E277 adicionou escolha de prioridade sem criar
  produção; E282 percorreu o mesmo estado preparado até relief e subsistência.
- [x] Fechar a resposta estrutural usando owners existentes, sem mecânica nova:
  empréstimo voluntário e prioridade de produção abrem meios reais; relief é uma
  decisão separada que move estoque público a pantries. A composição de seis
  ciclos é E282; limites de fixture/API/fallback permanecem explícitos abaixo.
- [x] Comparar resposta/controle por seis ciclos mensais desde o mesmo save e
  com a mesma política offline de fundo (E269). A contratação API de 31 artesãos
  orcs melhorou o resultado final em 65 rações de falta e 13 pontos de saúde,
  mas restaram 237 de falta; não prova adoção autônoma ou estabilização.
- [x] Mapear a pressão residual por coorte e verificar affordances existentes,
  orçamento, emprego e compra no save do dia 1.110 (E270); nenhuma resposta
  estrutural adicional estava disponível sem reduzir contratos/realocar renda.
- [x] Inventariar as opções de staffing no mesmo checkpoint e reconstituir
  a pressão de payroll que as habilita (E271); há uma realocação financiável,
  mas ela reduz o salário de uma coorte sem falta atual e precisa de contrafactual.
- [x] Executar o contrafactual pareado E272: apenas o ramo de intervenção reduz
  Ponte Negro de 180 para 90 trabalhadores; os dois avançam seis ciclos com a
  mesma política `routine-rules`, sem outra decisão injetada. O fallback cria
  vaga para 27 artesãos humanos nos dois ramos (dia 1.200 no controle, 1.230 na
  intervenção), portanto a opção normal foi adotada, mas a realocação não provou
  adaptação sustentada: a soma de falta nos seis fechamentos foi 13.785/13.840
  rações (controle/intervenção); o grupo de agricultores anões de Ponte Negro
  acumulou 135/207 rações não atendidas, e a coorte humana agricultora cortada
  terminou com caixa 5.171/2.180. A produção de Campomanso/Ponte Negro aumentou
  de 61/27 para 87/65 lotes, enquanto as mortes por privação acumuladas ficaram
  em 192 em ambos. Experimento concluído, aceite econômico falhou; não é provider
  nem decisão natural. Evidência detalhada: E272 no estado atual e matriz.
- [x] Recompor o menu vigente ao fim de E272 (`E273`): a única nova vaga local
  era para 3 artesãos anões; não havia pedido de empréstimo nem prioridade de
  produção concorrente. Também havia alívio agudo (15/7 rações) e 42 opções de
  reduzir vínculos. Isso delimita o próximo diagnóstico, sem concluir que não
  existam respostas em outros dias.
- [x] M1/E274 encerrado como experimento, não como solução estrutural: o contrato
  de empréstimo foi estendido para recibo atual `production_limited` de alimento,
  com `payroll_funds` como único limite e principal de um lote. Famílias recebem
  aviso com finalidade e decidem em separado; não há criação de dinheiro,
  reserva futura nem produção automática. O par de seis ciclos não mostrou
  recuperação sustentada e a instalação-alvo produziu os mesmos batches nos dois
  ramos. A capacidade permanece disponível como affordance causal, mas não conta
  como aceite de adaptação M1. Ver E274.a/b no diário.
- [x] E274.a confirmou a lacuna e estendeu o mesmo pedido para um lote futuro de
  alimento, limitado por folha e com os demais limites capazes. Decisão e
  contribuição continuam independentes; emprestar não reserva caixa nem produz.
  38 testes focados de empréstimos, observatório e persistência passaram,
  incluindo rejeição de saves 76/77 e estados Economy 18/Knowledge 9.
- [x] E274.b, par natural seed 73 dia 270→450: houve decisão API de Auren e uma
  família local, sem provider; dinheiro conservado em 76.000, credora preservou
  a reserva, mas a instalação-alvo produziu 30 batches nos dois ramos, a falta
  final foi 427 vs 364 e o alimento produzido foi 21.300 vs 25.400. A intervenção
  não demonstra resposta sustentada; ver ferramenta e estado atual. O M1 segue
  aberto e a affordance não deve ser tratada como solução de adaptação.
- [ ] Demonstrar uma resposta normal viável cuja melhora se sustente sem
  transferir privação a outra coorte; seguir acesso, renda, produção, caixa,
  saúde e as decisões por coorte. A vaga observada em E272 não fecha esse aceite.
- [x] E275, diagnóstico de uma fronteira, com cenário regenerado seed 73 e
  clones em memória: o empréstimo de 40 elevou `treasury:auren` de 2.903 para
  2.943, mas esse caixa é compartilhado por três fazendas. No dia 300, o pool
  financiou 29 lotes em Pedra Clara (28 no controle) e 3 em Ponte Negro nos dois
  ramos; ao avaliar Campos do Lume havia 22 moedas, abaixo dos 40 do próximo
  lote, e o alvo ficou em zero nos dois ramos. Trabalho (87), capacidade, local,
  integridade e armazenamento permitiam produzir; só `payroll_funds` limitou.
  O fluxo é honesto como crédito de caixa fungível para folha de produção
  alimentar, não como promessa de produção naquela instalação. O contexto e os
  rótulos agora deixam claro que não há earmark nem resultado garantido. A
  intervenção gerou 100 alimentos extras no outro local sem reduzir a falta
  agregada no fechamento (129 em ambos); não prova adaptação sustentada. Detalhes
  e limites em E275 no diário.
- [x] E276, recompor as opções na fronteira natural de seed 73 (dia 270,
  `event:8158`): `production_priority_options` de Auren retornou vazio. O alvo
  Campos do Lume não tem outra instalação concorrente no mesmo assentamento e
  ocupação; as outras fazendas compartilham o tesouro, mas ficam em assentamentos
  diferentes. O engine rotaciona a ordem entre todas as instalações do account,
  enquanto a affordance atual cobre apenas conflito local de trabalho. Assim,
  o ator não tem opção para escolher qual cidade recebe o caixa compartilhado.
  Evidência de recomposição adicionada ao trace do utilitário E275; nenhuma ação
  foi escolhida nesse recorte.
- [x] E277, estender `ProductionPriority` para permitir ao owner priorizar uma
  instalação entre concorrentes do mesmo payroll account somente após receipt
  atual `production_limited` com `payroll_funds`. A prioridade é decision-backed,
  limitada ao próximo boundary, persistida sob Economy schema 20/save schema 79,
  e muda a ordem de avaliação sem reservar caixa ou garantir output. No
  contrafactual API seed 73, dia 270→300, selecionar `works:campos-do-lume`
  direcionou 22 lotes a Campomanso; a produção total do pool não aumentou, foi
  deslocada das outras fazendas. Falta agregada permaneceu 129 e a local 6.
  Saldo monetário total ficou conservado em 76.000 nos três ramos. O fluxo agora
  oferece a escolha que faltava, mas não prova adaptação alimentar; Gate B segue
  aberto. Ver E277 no diário.
- [x] E278, diagnóstico do ciclo do dia 300: produção prioritária elevou o
  estoque de Campomanso a 41.600/43.000, preço permaneceu 1; mesmo assim, das
  1.101 rações requeridas, famílias compraram 1.095. Faltaram 6, todas atribuídas
  no receipt a grupos de soldados sem saldo e uma dependente sem conta; grupos
  agrícolas/artesãos compraram a própria quota. Há affordance atual engine-owned
  de relief por 6 (ou 3), com estoque público suficiente e relatório atual de
  Auren. Assim, o gargalo imediato não é preço, estoque físico ou produção, mas
  acesso de grupos sem renda/conta; existe uma ação material de relief ainda a
  ser exercida/testada no boundary seguinte. Nenhum preço/estado foi alterado
  nesta medição. Próximo E279 testa essa resposta existente em clone por mais
  um ciclo, sem atribuir a escolha ao provider ou mundo natural.
- [x] E279, no clone de dia 300, decisão API escolheu relief atual de 6; receipt
  `event:10072` distribuiu o estoque público para cinco pantries (1/1/1/2/1)
  e foi causado pela decisão, report `event:9485` e falta observada `event:9107`.
  Ao dia 330, as pantries tinham sido consumidas, mas Campomanso terminou com
  falta 0, health +12 e unrest -12 frente ao controle sem relief (falta 6).
  Dinheiro total não mudou. Isso prova resposta material de um ciclo, não
  escolha autônoma nem adaptação durável; Gate B segue aberto.
- [x] E280, continuidade offline sem ação injetada até dia 330: `ai_enabled=false`,
  não houve `relief_distributed`; a falta 6 reapareceu e as opções 6/3 estavam
  atuais após a revisão. O fallback declara `FALLBACK_MIN_SHORTFALL=20`, logo não
  seleciona esse resto pequeno e não emite decisão/NO_ACTION. Isso é resultado da
  política offline, não evidência do provider. Nesta execução `provider_available`
  também era falso. O adapter de relief participa do menu institucional provider-
  enabled por código, mas não houve consulta live; a consulta real fica para o
  gate do provider.
- [x] E281, rastrear a falta residual de E278 contra os owners atuais, sem nova
  affordance: renda doméstica nasce de trabalho efetivamente pago; grupos
  `dependent` não recebem oferta de emprego permanente, e uma transição só é
  possível após demanda datada de trabalho, notice conhecido e conta doméstica.
  Soldados recebem salário quando recrutados/servidos em guarnição ativa; isso
  não equivale a renda recorrente de toda coorte de reserva. Relief continua uma
  decisão material pontual, limitada a estoque e relatório próprio. O código não
  oferece hoje um vínculo familiar entre grupos que faça o saldo de adultos
  sustentar dependentes. Isso demonstra uma lacuna de representação/integração,
  não autoriza dinheiro, renda ou emprego automáticos. Ver E281 no diário; M1
  estrutural continua aberto.
- [x] E282, contrafactual controlado em clone E277: seis fronteiras mensais no
  mesmo caminho do engine, após empréstimo voluntário e prioridade de produção
  decididos, com menu composto atual e decisões API explícitas para relief.
  O controle escolhe `NO_ACTION`; o tratamento escolhe o maior relief vigente
  para Campomanso quando existe. Ambos usam `ai_enabled` no engine com todos os
  selectors interceptados (zero egress). Houve opção em 4 de 6 turnos; o ramo
  API entregou 1.759 rações em Campomanso e reduziu sua falta `791→0` contra
  `NO_ACTION`, sem mudar moeda e sem aumentar falta em outros assentamentos
  frente a esse controle. O controle offline pareado executou 18 reliefs,
  totalizando 14.742 rações em vários assentamentos; terminou com falta
  agregada 433, enquanto o ramo API limitado a Auren/Campomanso terminou com
  5.823. Portanto a experiência valida o owner e a opção atual, mas não aprova
  a política de ator único como resposta do mundo: ela retém decisões dos demais
  atores e é pior que o fallback offline neste cenário. Isso não invalida o ramo
  pareado: ele prova a resposta em cenário elegível quando a autoridade escolhe
  relief; o teste focal `test_relief_only_reaches_households_with_unpaid_rations`
  confirma que o owner aloca apenas a grupos com ração não atendida. Causalidade,
  conservação, Economy/Knowledge e história passaram. E208/E277/E282 em conjunto
  fecham a aceitação de M1 no cenário preparado usando somente crédito, prioridade
  e estoque já existentes. Não provam provider real, adoção natural ou outros
  seeds; o Gate B natural permanece em M8.
E283 (proposta anterior de diagnóstico por coorte) foi retirada antes da
execução por correção de escopo do usuário. Nenhum teste ou resultado E283 existe;
não retomar essa proposta como próxima tarefa. O registro E282 continua sendo a
evidência mais recente de M1.

Aceite: resposta viável reduz pressão de forma sustentada no cenário elegível,
sem criar riqueza nem esconder privação transferida a outra coorte. Um cenário
sem meios pode falhar; prosperidade universal não é requisito.

### M2 — Política, QG, comandante e consequência civil

- [ ] Preparar condições iniciais com autoridade, QG, comandante e ator civil
  distintos; após começar, nenhuma escolha de ação pelo teste.
- [ ] Fechar objetivo → autorização → ordem/relatório → mobilização → suprimento
  → operação → revisão/retirada/manutenção, com a mesma coluna e plano.
- [ ] Ambiente ou criatura altera rota/carga; informação datada chega e gera
  pelo menos duas decisões independentes e uma consequência fora do militar.
- [ ] Sustentar ocupação por guarnição paga por vários ciclos e saída política
  bilateral; perda material dos meios altera controle.

Aceite: cenário autônomo controlado e contrafactual de rota/informação alteram
trajetória ou resultado. Política não pode encenar etapas por IDs ou contador
do teste. Atraso de agenda não é apresentado como trânsito físico de mensagem.
Não exigir vitória, desacordo ou guerra em toda seed natural.

### M3 — Tecnologia, diplomacia e intriga restantes

- [ ] Auditar e fechar conservação alimentar, aço, pólvora, artilharia, vapor,
  logística, barreiras e doutrina do roadmap: requisito → pesquisa/difusão →
  instalação/equipamento → operação/manutenção → efeito material.
- [ ] Ensino, venda, roubo e migração chegam à aplicação; reaproveitar provas
  existentes e completar apenas ligações ausentes.
- [ ] Persuasão/barganha, espionagem, suborno, sabotagem, investigação e acusação
  têm caminho utilizável com conhecimento próprio; suspeita não vira culpa.
- [ ] Compromisso → quebra deliberada/impossibilidade → aviso → reparação/recusa
  → memória influencia contexto de decisão posterior, sem apagar a quebra.
- [ ] Confirmar tarifas, embargo, contrabando/detecção e transferência de
  patrimônio produtivo nos menus normais e observatório.

Aceite: cada capacidade nomeada tem consumidor material e prova; uma cadeia
pode cobrir várias linhas. Sem meios, técnica não concede efeito. Não ampliar
para propriedade universal, espionagem ilimitada ou cenário industrial.

### M4 — Quatro povos integrados

- [ ] Preservar humanos, elfos, anões e orcs em geração, nascimento/maturação,
  personagens/coortes, migração, trabalho, recrutamento e save/load, sem duplicação.
- [ ] Fechar catálogo pequeno de propriedades físicas com consumidores reais
  (por exemplo maturação/tolerância ambiental). Especificar poucos valores e
  efeitos auditáveis no início do marco; não inventar bônus universais.
- [ ] Separar povo, habilidade aprendida, personalidade, instituição e fé;
  nenhuma raça determina moralidade, profissão, lealdade ou religião.
- [ ] Provar convivência na mesma cidade/instituição e acesso a trabalho,
  aprendizado, migração e escolhas; explicar diferenças aplicadas na UI.

Aceite: identidade sobrevive às transições e diferenças declaradas produzem
efeitos limitados verificáveis. Conflito racial não é comportamento obrigatório.

### M5 — Magia utilizável e criaturas persistentes

- [ ] Fechar restauração, proteção, elemental e evocação: ao menos uma operação
  material completa de cada capacidade já declarada em `Skills`. Contramedida
  não substitui elemental/evocação apenas por outro nome.
- [ ] Toda operação declara técnica/praticante, insumos, alvo, alcance, tempo,
  recuperação, efeito limitado, observação e contramedida. Reusar atividades,
  projetos e resistências existentes onde correspondem ao domínio.
- [ ] Restauração/wards: custo, expiração e recuperação; elemental: uma
  interação física ofensiva ou ambiental limitada; evocação: uma manifestação
  temporária com origem, custo, duração e encerramento explícitos, sem bens
  permanentes ou população gratuita. Detalhar leis antes de implementá-las.
- [ ] Ameaça ritual → detecção válida → intervenção independente → interrupção,
  resistência ou efeito; opções competem com prioridades não mágicas.
- [ ] Drake e serpente existentes: necessidade/habitat/memória → decisão →
  negociação/tributo/recuo ou dano → resposta institucional e civil.

Aceite: alcance, recuperação, custo insuficiente e ID stale bloqueiam sem
mutação; contramedida muda resultado. Conhecer magia não executa magia; raça não
concede técnica automaticamente. Sem DSL ou novo bestiário durante fechamento.

### M6 — Religião com agência e consequência

- [ ] Reutilizar ordens/cultos, offices e membros; fechar identidade religiosa
  e adesão de personagens/grupos sem confundir raça e fé ou duplicar conhecimento.
- [ ] Duas tradições coexistentes permitem alternativas e contrapartes;
  doutrina orienta decisões, sem alterar física por texto.
- [ ] Oferta/participação/patrocínio/ensino e adesão usam decisões próprias,
  fontes e meios reais; pregação não converte automaticamente toda a população.
- [ ] Assembleia observada → permitir/negar → presença/força/custo → resposta
  independente de grupo, ordem ou governo → proteção, negociação, protesto
  ou deslocamento, reutilizando os mecanismos cívicos existentes.
- [ ] Alegação de agir pelo Dao permanece alegação; UI separa crença, fato e
  efeito mágico materialmente confirmado.

Aceite: religião influencia decisão posterior por interesse/conhecimento/memória
e tem consequência rastreável. Não exigir perseguição ou revolta, nem criar
cosmologia, divindade autônoma ou milagre livre.

### M7 — Experiência investigável e agência composta

- [ ] Dossiê mostra atividade, objetivo, cargo, informação datada, escolha/opções
  registradas, custos, resultado e pendências. Justificativa retrospectiva não
  pode aparecer como pensamento real do personagem.
- [ ] Atlas → campanha/rota/rito; Crônica → resumo → dossiê → `why()` → fatos,
  decisão, fontes e consequências. Povos, religiões e magia aparecem em PT-BR.
- [ ] Verificar no navegador pausa, avanço, save/load e retomada das cadeias.
- [ ] Cenário composto M1–M6, com disputa pelos mesmos recursos e decisões
  próprias. Cenários preparados complementam capacidades raras não escolhidas;
  nenhuma partida precisa acionar todo o catálogo.

Aceite: acompanhar uma história causal sem ler logs de desenvolvimento.
Inspiração AgentWorld: papéis assimétricos, traces por ator e verificadores
objetivos. Sem importar framework, alianças unilaterais, chat onisciente,
prompt anti-idle ou métrica causal inferida pela LLM como verdade do mundo.

### M8 — Checkout congelado, gates e entrega

- [ ] Congelar fingerprint após M0–M7; revalidar famílias alteradas e negativos
  críticos de autoria, opção stale, conservação e publicação atômica.
- [ ] Corpus real limitado cobre decisões novas e composição. Reutilizar provas
  recentes de contratos intactos; contar tentativas e saldo da autorização de
  consultas. Autorização anterior não vira orçamento ilimitado.
- [ ] Três seeds naturais por 3.600 dias no mesmo checkout, sequenciais, com
  checkpoints, conservação, auditoria, save/load e continuação.
- [ ] Build/type-check, regressão medieval apropriada e navegador; relatar
  falhas/exclusões legadas sem declarar suíte inteira verde.
- [ ] Revisão final da matriz, commits revisáveis, push/merge/deploy conforme
  autoridade operacional vigente; backup e smoke da versão implantada.
  Aguardar publicação é “pronto para entrega”, não “implantado”.

Budgets preservados: 3.600 dias/seed ≤60 min; RSS ≤4 GiB; save ≤512 MiB;
save/load ≤60 s cada; p95 mês tardio ≤35 s; p95 `why()` ≤2 s/até 100 links.
Registrar host, tamanho do mundo e método. Não relaxar limites após falhar.
Conferir disco antes; não duplicar saves desnecessariamente. Remover/externalizar
somente artefatos identificados/autorizados com cópia verificada. Saves reais
antigos continuam preservados; sem migração destrutiva automática.

Smoke natural pode ser pacífico: mede integridade, adaptação observada e custo.
Cenários autônomos controlados provam capacidades raras. Ambos obrigatórios,
com resultados e limitações separados; não impor cota narrativa às seeds.

## Progresso, evidência e parada

Cada caixa é uma entrega. Na matriz, abrir só o recorte executável corrente;
ao concluir registrar E, fingerprint, arquivos, comando/cenário, resultado,
limite e próximo item, então marcar `[x]`. “Procuramos” não é “a cadeia surgiu”.
Estados: aberto, em execução, implementado sem prova, verificado, falhou,
evidência histórica. Marco exige todas as caixas aceitas.

TDD opcional; testes dos riscos principais. Reusar cadeias/contrafactuais;
não testar cada helper nem milhares de combinações. Mudança invalida evidência
afetada, não autoriza repetir toda a validação após cada patch.

Ao fechar marco: informar entrega visível, provas, limites e restante. Pausa
solicitada ocorre no checkpoint seguro, com retomada registrada. Laya disponível
revisa desvio de escopo como consultor de implementação; indisponibilidade fica
explícita e não bloqueia trabalho autorizado. Não integra a IA dos NPCs.

Fora do fechamento: torneios, Industrial Warfare, novo motor/framework,
marketplace de plugins, povos adicionais e escolas além das quatro contratadas.
Pólvora/artilharia são recorte do roadmap medieval fantástico, não autorização
para guerra industrial. Não reescrever módulos por preferência arquitetural.

Próximo trabalho: M1 foi aceito no cenário preparado por E208/E277/E282; Gate B
natural permanece explicitamente para M8. Não executar a proposta E283 retirada.
Prosseguir para M2: integrar hierarquia política, QG, comandante, campanha,
ambiente/logística e consequência civil conforme os aceites acima, começando por
uma única trajetória autônoma controlada. Limites de M1: sem provider real,
emergência natural ou outras seeds. Sem commit, push, merge ou deploy neste
checkpoint.
