# Registro de trabalho histórico — fechamento do Medieval

> Este arquivo longo preserva anotações/evidências acumuladas e não é mais o
> plano operacional. Use [medieval-finalization-plan.md](docs/handoff/medieval-finalization-plan.md)
> para tarefas e gates, [medieval-closure-matrix.md](docs/handoff/medieval-closure-matrix.md)
> para status por requisito e [medieval-current-state.md](docs/handoff/medieval-current-state.md)
> para resultados e evidências. Não continue anexando progresso aqui.

## Arquivo histórico (conteúdo abaixo não é instrução vigente)

Atualizado em 25/09/2026, com base no roadmap de produto e no handoff do
checkout atual. Objetivo: terminar o jogo medieval existente; Industrial Warfare,
torneios e novas verticais laterais ficam fora. Este é um plano de fechamento,
não uma declaração de que o roadmap já foi concluído. Há WIP amplo no checkout;
preservar tudo e não inferir que cada mudança local já foi revisada ou validada.

## Direção

Não abrir sistemas novos antes de fechar e observar os já iniciados. A cadeia
continua sendo:

```text
estado e evidência → affordances válidas → decisão do ator
→ owner revalida/executa → fatos e deltas → conhecimento/memória
→ decisões posteriores
```

Sem quota de drama ou recuperação: paz, `NO_ACTION`, crise e resultados ruins
são válidos quando explicados pelas causas. Fixtures pressionadas provam
mecanismos; não contam como formação espontânea no mundo natural. Provider,
fallback e decisão simulada devem ser reportados separadamente. MetaGame/Laya pode
acompanhar em shadow mode se a implementação está desviando desses contratos;
não decide regras nem substitui owner, revisão ou evidência.

## Sequência de retomada — fechar o principal sem deriva para correções locais

Esta sequência substitui a continuação ad hoc de correções owner por owner.
Cada etapa tem um gate de saída; só se avança com evidência. Não abrir novas
verticais durante este fechamento.

### Gate A — inventário causal transversal e checkpoint revisável

1. Preservar o checkout e registrar a base observada: branch, HEAD, arquivos
   modificados/não rastreados e evidências já existentes. O WIP atual é amplo;
   não atribuir todas as mudanças a uma única etapa nem descartar nada.
2. Montar um inventário finito dos emissores materiais: combinar os caminhos
   estáticos de emissão/mutação com os tipos de evento material encontrados nos
   saves. Para cada família registrar owner, fontes de causa permitidas,
   decisão/affordance ou causa física, revalidação, delta e fonte, atomicidade,
   e uma verificação negativa representativa.
3. Classificar cada linha como `verificada`, `parcial`, `falha reproduzida` ou
   `não exercitada`. Corrigir violações concretas por lote relacionado; não
   continuar encontrando e remendando owners sem atualizar o inventário.
4. Preparar um checkpoint revisável que preserve o WIP e sincronize handoff,
   matriz e evidências. Commit/push/deploy são operações separadas e exigem
   pedido explícito.

**Gate de saída:** todos os emissores conhecidos estão inventariados e
classificados; exceções têm justificativa explícita; cada classe crítica possui
um teste/sonda negativa; não há divergência inexplicada entre cobertura estática
e eventos observados. “Inventariado” não deve ser reportado como “provado em
runtime” quando não foi exercitado.

### Gate B — diagnóstico causal da crise econômica, sem consertos mágicos

Usar o checkpoint existente de seed 73 no dia 1560 como evidência inicial e
reproduzir apenas os recortes necessários. Seguir, por assentamento e coorte,
uma cadeia única:

```text
caixa do empregador → folha de pagamento → emprego/produção
→ renda doméstica → acesso/oferta/compra de alimento
→ déficit alimentar → saúde → mortalidade
```

Em cada elo, apontar owner, estado canônico, evento/receipt e affordances que o
ator tinha naquele momento. Para o primeiro elo que falha, distinguir:

- ator não conhece o fato;
- conhece, mas não recebe affordance;
- affordance existe, mas autoridade, caixa, estoque ou rota impedem agir;
- ação válida existe, mas a decisão/política a pretere;
- ação executa corretamente, mas sua escala/efeito é insuficiente;
- indicador é projeção do Dao e não necessidade/estoque canônico do owner.

Conferir separadamente saldo disponível versus teto contratual/orçamentário,
contas de empregadores versus dinheiro das famílias, e `routine-rules` versus
decisão de provider. Corrigir somente a causa dominante demonstrada. Não criar
subsídio, estoque, salário, emprego, compra, recuperação ou meta de prosperidade
automáticos para melhorar métricas.

**Gate de saída:** causa dominante e elo causal limitante são reproduzíveis e
documentados com evidência; qualquer correção altera o resultado por ação/owner
material normal, com contrafactual focado. Uma economia ainda pobre pode passar
se sua trajetória for explicável; zero mortes não é requisito.

### Gate C — uma cadeia medieval multissistema em trajetória contínua

Com owners e affordances já existentes, provar primeiro numa fixture pequena e
contrafactual, depois procurar a mesma composição em mundos naturais sem exigir
que toda seed a produza:

```text
ameaça/objetivo político
→ decisão do QG e plano persistente
→ força e carga material reais
→ ambiente/rota interfere
→ relatórios locais chegam aos atores pertinentes
→ QG e comandante reconsideram independentemente
→ campanha muda ou continua por decisão válida
→ comércio/população recebem consequência material rastreável
```

Não introduzir um planner central, nova vertical ou regra que force a cadeia.
Identificar claramente fixture, fallback e provider real; fixture ou fallback não
contam como emergência natural nem como prova de provider. Usar pelo menos um
contrafactual de rota/suprimento/conhecimento e preservar a mesma campanha/força
entre etapas. A UI/observabilidade deve permitir navegar de decisão a fonte,
owner, delta e consequência.

**Gate de saída:** numa única trajetória multietapas, a interferência material
ou informacional muda a decisão/resultado; atores agem apenas sobre evidências
que lhes pertencem; a alteração atravessa pelo menos dois domínios existentes;
causas, ownership e deltas são auditáveis. A fixture prova o mecanismo; relato
natural só é feito se observado sem decisões injetadas.

### Gate D — fechamento e validação final do Medieval

Só após A–C, ordenar as pendências já aprovadas na matriz/roadmap por
dependência e fechar uma vertical existente por vez. Não puxar Industrial
Warfare, torneios ou ideias novas para dentro do critério de conclusão.

No checkout estável final, executar os gates em separado:

1. smoke natural de três seeds por 3600 dias, com checkpoints, conservação,
   save/load/continuação, auditoria causal e medidas de tempo, memória e disco;
2. fixture pressionada para cadeias que o smoke natural não tem obrigação de
   produzir;
3. validação curta do provider real apenas se houver autorização/configuração
   disponível, separada de fallback e `NO_ACTION`;
4. verificação focada de UI/API e custo operacional dos dossiers/histórico.

Não chamar o gate antigo de atual se o código mudou desde sua execução. Publicar
resultados por seed e por modo de decisão, incluindo falhas e limitações. O
aceite exige integridade causal, não um mundo sem crise, fome, conflito ou
`NO_ACTION`.

### Limites de escopo durante a retomada

- Não implementar Industrial Warfare, torneios ou novas verticais.
- Não fazer hardening owner por owner sem inventário e falha concreta.
- Não confundir diagnóstico omnisciente do Dao com conhecimento dos atores.
- Não tratar smoke offline, fixture pressionada ou consulta pontual ao provider
  como prova intercambiável.
- Não corrigir métricas por quotas de drama, prosperidade ou sobrevivência.
- Não commitar, subir ao remoto ou deployar sem pedido explícito.

## Próximos checkpoints executáveis

1. **Fechar a auditoria de autoria dos owners.** Continuar a varredura
   transversal de toda transição material: exigir decisão real do ator ou
   fallback explicitamente declarado, affordance atual recomposta, autoridade e
   evidência-fonte; testar que seleção determinística copiada falha sem mutação.
   Atualizar a matriz/handoff apenas com os recortes realmente verificados. A
   auditoria avançou por vários owners em 25/09, mas continua incompleta.
   **Avanço em 25/09:** pedido/aceite/recusa de ajuda institucional,
   proposta/aceite de transferência produtiva e ensino bilateral agora exigem
   autoria nos owners; Knowledge também rejeita receipts de ajuda persistidos
   com origem adulterada. Os recortes dos fluxos e consumidores passaram (`74
   passed`); a cobertura transversal ainda não está fechada.
   **Novo recorte em 25/09:** recuperação de compra bloqueada e pressão manual
   de campanha agora carregam autoria material explícita; encerramentos
   automáticos por perda física continuam determinísticos e ligados à causa.
   Regressão de recuperação, investimento, cerco e cadeia persistente passou
   (`35 passed`). A auditoria ainda precisa percorrer os demais owners.
   **Novo recorte de comando em 25/09:** mobilização, preparo, nomeação,
   doutrina e despacho/frete de campanha também propagam autoria ao receipt
   material. Força, posição, comando, abastecimento e campanha persistente
   passaram em `37` testes focados; isso não fecha o inventário global.
   **Continuação de compromissos em 25/09:** cumprimento e reparação de recurso
   e cessão de administração também registram ator/affordance no receipt final
   (e no frete quando aplicável). Concessão, supply recíproco e ajuda passaram
   em `43` testes focados; falta auditar os outros owners.
   **Agência individual em 25/09:** iniciar viagem agora liga o receipt à
   affordance e decisão do próprio personagem; chegada permanece consequência
   datada. Viagem e comando passaram em `13` testes focados. A auditoria global
   segue incompleta.
   **Manutenção em 25/09:** `repair_started` agora liga explicitamente a
   seleção do mantenedor ao receipt material; teste focal de reparo, desgaste,
   serviços e campanha passou (`40 passed`). Encerramento de autoria continua
   parcial até o inventário transversal.
   **Recorte cívico em 25/09:** formação/adesão de movimento e declaração de
   rebelião exigem as decisões dos grupos e receipts atuais; repressão só é
   oferecida com destacamento presente e abastecido e consome provisão real.
   Acrescentei regressão negativa em que uma decisão determinística copia a
   affordance de repressão: o owner rejeita e o snapshot permanece idêntico.
   Formação multigrupo + rebelião/repressão passaram em dois testes focados;
   Ruff passa ignorando `F841` preexistente no módulo. É um recorte cívico, não
   fechamento da autoria de todos os owners nem prova de pressão natural.
   **Compromisso de suborno em 25/09:** o executor do pagamento criava uma
   autorização `DETERMINISTIC` sintética e a repassava ao owner de obrigações,
   que exige a decisão autoral corrente. A aceitação podia ser registrada, mas
   o pagamento válido falhava. Agora o owner valida a affordance recomposta e
   passa a decisão original `ACTOR_DECISION` até o receipt do pagamento; a
   regressão também prova que payload copiado com origem determinística falha
   sem mutação. `tests/test_medieval_bribery.py` passou (`7 passed`), Ruff e
   `git diff --check` passaram. Isso fecha apenas este owner, não a auditoria
   transversal.
   **Raízes de estado inicial:** o inventário no save anterior de 720 dias
   encontrou produção inicial e observações sem evento-pai. O bootstrap do
   mundo é uma premissa canônica pré-simulação, não um evento fictício; falta de
   link não é, sozinha, causa quebrada. Agora as receipts sem evento-pai em
   produção, renda inicial, observações de sítio/rota, carga hidrológica e ciclo
   ecológico declaram `root_premise` estruturada com domínio, referências de
   owners e dia, enquanto preservam as métricas/limites do owner. A Crônica
   diferencia essa origem da mensagem “nenhuma causa anterior registrada”. Isso
   não aceita ausência de link quando uma causa factual existe, nem substitui a
   auditoria do evento-fonte. O auditor também rejeita transição material sem
   evento-pai nem root válida. Smoke natural atual (seed 14, 120 dias, sem
   provider): 3.839 eventos, 2.738 transições materiais, 152 roots (151
   `world_generation`, 1 `scenario_bootstrap`), zero roots inválidas ou
   transições materiais sem root/link, zero causas quebradas/autoria inválida/
   Story/Interpretação material; conservação e save/load passaram. 40 testes
   focados de renda, observação local, conhecimento de rota e auditoria passaram;
   Crônica `4 passed` e type-check passaram. Três testes focados adicionais de
   round-trip fiscal/campanha/frete passaram após corrigir fixtures sem autoria.
   A trajetória ainda mostra pressão local (saúde média 951,25, unrest 48,75,
   falta 16 no dia 120), portanto economia natural continua aberta. O gate é de
   120 dias (quatro meses), não substitui três seeds × 3.600 dias; o save de 720
   dias permanece evidência antiga, não certificado do checkout atual.
   **Temporalidade e autoria no auditor/ledger:** todo evento não `DECISION` com
   origem `ACTOR_DECISION` precisa ter uma decisão real do mesmo dia entre suas
   causas; se houver delta, o payload também precisa corresponder exatamente a
   essa decisão, ator e affordance. Antes, o auditor verificava autoria direta
   só quando havia delta e não exigia temporalidade de causa em ocorrências.
   Casos negativos cobrem vínculo stale e ocorrência sem receipt; o evento real
   `diplomatic_bargain_attempted` continua válido por apontar para a decisão
   contemporânea que o causou. O save natural seed 14/dia 120 continua limpo (90
   transições materiais de ator, zero erros). Isso fortalece a auditoria do histórico, mas
   não substitui a validação de affordance atual dentro de cada owner nem fecha
   o inventário global. A origem `provider` também exige que seu receipt de
   interpretação/recusa seja do mesmo dia da decisão; uma seleção de ontem não
   autoriza a decisão de hoje. A regra agora também é enforced no ledger ao
   registrar eventos e ao validar save/load: receipts provider e decisões-fonte
   stale são rejeitados antes da mutação ou na leitura. Trinta testes focados de
   autoria runtime, auditoria e diplomacia passaram; o save natural do dia 120
   passa com zero erro. O antigo save natural do dia 720 agora carrega sem erro
   de autoria (zero), mas continua inválido como gate por 153 transições sem
   causa/root explícita, anteriores à instrumentação de premissa raiz.
2. **Reconciliar o estado do checkout e validar o provider.** Comparar WIP,
   roadmap, handoff e evidências, separando comprovado, parcial, pendente e fora
   de escopo. Depois, obter uma decisão real do provider em
   opções econômicas concorrentes no schema atual; seguir seus efeitos em
   produção, folha, acesso a alimento, saúde e migração. Diagnosticar antes de
   mudar regras. Provider indisponível, erro e `NO_ACTION` são resultados
   explícitos, não fallback disfarçado. Consultas externas exigem autorização
   vigente e payload sintético/minimizado; não reportar uma escolha simulada
   como chamada real.
3. **Fechar a economia natural sem balanceamento artificial.** Observar
   emprego/folha, produção, compras, estoques, acesso doméstico, saúde,
   migração e mortalidade em horizonte crescente. Comparar decisões reais do
   provider separadamente do fallback e investigar causas antes de alterar
   regras; não injetar dinheiro, comida, emprego ou recuperação obrigatória.
4. **Completar a prova do elo ambiental e conectá-lo à campanha:** a cadeia
   natural dano → capacidade de rota → leitura privada do mantenedor → affordance
   válida → decisão → execução material já foi observada na seed 14. Uma fixture
   mantém uma coluna levantada antes da enchente; após o dano, ela recebe ração
   por decisão simulada, parte do frete espera pela capacidade compartilhada e,
   quando a carga chega, o QG recebe um turno próprio e escolhe retirar a coluna
   com base em seus relatórios. O caso não cria `StrategicPlan` retroativo. Não
   exigir ocorrência em toda seed nem inventar reparo automático.
   **Progresso em 24/09:** as provas de frete após dano e de campanha ativa
   atravessando o overflow passaram juntas (`2 passed`, 55,32 s); Ruff e
   `git diff --check` passaram. A coluna já existia antes do evento natural, e
   a decisão posterior de suprimento é de provider simulado. O menu/decisão do
   QG para retirar força existente já não depende apenas de relatório de
   combate: agora há também
   revisão logística para coluna direta sem `StrategicPlan`: depois de a carga
   atrasada chegar, o QG pode retirar com rota e posição conhecidas e encerrar
   avisos abertos por decisão explícita. O QG agora despacha
   suprimento usando suas próprias leituras de rota. Enquanto uma parcela
   ainda está fisicamente em trânsito, a retirada continua indisponível; a
   decisão posterior só ocorre após resolução/carregamento da carga. Uma
   mudança nesta continuação fecha outro elo da rota bloqueada: ao receber um
   `route_bulletin` próprio sobre a perna onde uma coluna planejada está parada,
   o owner agenda a revisão do QG para o dia seguinte, antecipando a revisão
   periódica; não escolhe ação nem consulta estado do mapa pelo ator. A prova
   integrada exercita a agenda real, a escolha provider simulada e a revalidação
   pelo owner de rota alternativa, com causal links ao bloqueio e aos relatórios
   pessoais do QG. Isso usa fechamento por criatura, não enchente.
   **Atualização nesta continuação:** uma remessa de campanha realmente atrasada
   agora pode gerar novo aviso causal à coluna/QG, sem reescrever o frete original.
   O menu considera apenas estoque/rota próprios, desconta do espaço da bagagem
   todo o alimento que já está em trânsito e conserva a decisão do QG ligada ao
   receipt `cargo_delayed`. A fixture focal mostra uma segunda remessa escolhida
   quando ainda cabe no prazo e na bagagem. Na trajetória natural de enchente, a
   vazão concorrente segura toda a carga; quando a próxima revisão chega, a
   combinação atual de ração, fonte, rota e prazo não deixa opção válida, então
   nenhum envio é criado. O fato/aviso permanece causal até a necessidade cessar.
   Campanha e overflow passaram em nove testes focados, incluindo save/load e
   auditoria da trajetória natural. Isso não valida provider remoto, escolha
   espontânea ou campanha longa natural. **Avanço nesta continuação:** quando
   um frete atrasado é integralmente resolvido e carregado, a revisão estratégica
   do plano é antecipada para o dia seguinte. O QG pode manter (`NO_ACTION`) ou
   escolher retirada entre destinos/rotas que conhece; o owner bloqueia cargas
   despachadas/em trânsito, mas permite que a mesma decisão encerre avisos de
   suprimento ainda abertos como `lapsed`. Revalida autoridade, bagagem e rota,
   inicia retorno físico e liga plano/retirada ao atraso e aos relatórios. A
   fixture integrada prova que a parcela bloqueia antes da entrega e que, depois
   da entrega, o QG pode retirar e causar o lapse do pedido aberto. Uma fixture
   integrada adicional agora percorre frete
   aberto por `open_order` → atraso emitido pelo owner logístico → aviso causal
   de seguimento → segundo frete e carregamento real → resolução do primeiro
   frete pendente → turno antecipado do QG → retirada com causas até o atraso;
   o save/load final também passou. A asserção agora identifica o aviso de
   seguimento exato encerrado pela retirada; uma carga em trânsito ainda impede
   a affordance. O menu agora diz explicitamente ao QG quais avisos abertos
   cada rota encerrará, para que escolha conhecendo a consequência; a validação
   focal dos dois módulos foi repetida (`26 passed`). A fixture seed 14 passou
   end-to-end após a extensão (`1 passed` em 28,58 s). Mobilização e frete
   concorrente foram preparados pela fixture, então isto prova interferência
   ambiental e resposta do QG, não formação espontânea de campanha; provider
   remoto continua pendente.
5. **Completar a cadeia de campanha e comando:** integrar decisões próprias do
   titular político, QG e comandante com relatórios datados, atraso/invalidação,
   suprimento, retirada e aftermath. As fixtures já provam vários elos; falta
   demonstrar composição persistente/natural e corrigir apenas lacunas reproduzidas.
   **Progresso em 24/09:** o despacho das rações de campanha agora é decidido
   pelo ocupante atual do QG, não pela instituição abstrata. O menu mostra ao
   QG apenas leituras próprias e datadas das rotas usadas; a decisão identifica
   `actor_ref` do oficial e `institution_ref` do beneficiário. O executor exige
   que o mesmo QG ainda detenha autoridade operacional e recompõe estoque,
   autoridade institucional e rota antes de abrir frete. As leituras usadas
   também ficam como causas da decisão. Campanha/suprimento e enchente passaram
   em nove testes focados após a continuação. A decisão e o notice adicional
   agora citam o atraso real; quantidade em trânsito reserva capacidade física
   antes de oferecer suplemento, e entrega parcial não encerra obrigação como
   `fulfilled`. Ainda falta uma trajetória em que essa affordance suplementar
   siga válida até o turno do QG no mundo natural; a fixture artificial cobre a
   seleção válida, enquanto a seed natural chega corretamente a nenhuma opção
   após revalidar estoque, provisões e prazo. A composição real de atraso até
   retirada está coberta por fixture; provider real e integração desse ramo
   com uma trajetória natural continuam pendentes. Os dois arquivos de teste
   de campanha/suprimento e resposta estratégica passaram em conjunto
   (`26 passed`) nesta continuação.
6. **Fechar as verticais já previstas no roadmap, sem abrir novas:** terminar
   os aceites materiais pendentes de economia/diplomacia; depois avançar em
   tecnologia/difusão; por fim magia, criaturas e conflito social. Para cada fatia:
   affordance → decisão independente → execução do owner → fato causal → save/load.
   Não tratar uma fixture estreita como conclusão de uma categoria inteira.
7. **Concluir observabilidade, escala e espaço em disco.** Tornar investigáveis
   no observatório as relações decisão/fonte/owner/delta; medir tempo por mês,
   RSS, tamanho e duração de save/load, crescimento do ledger e espaço livre
   antes/depois de gates longos. Otimizar apenas gargalos medidos. Preservar o
   histórico causal completo e seus índices; não truncar eventos nem apagar
   saves/evidências automaticamente. Limpeza de temporários só após inventário,
   identificação do conteúdo e confirmação de que há cópia íntegra quando
   necessária.
8. **Rodar os gates finais uma vez, no checkout estabilizado:** três seeds
   naturais até 3.600 dias com checkpoints, conservação, save/load, continuação e
   auditoria causal; fixtures pressionadas separadas para exigir cadeias
   multietapas; validação provider real curta e identificada separadamente.

**Checkpoint atual:** a cadeia natural de overflow → dano → leitura local →
reparo material já foi comprovada em uma seed e em 480 dias com fallback
explícito. Fixtures também compõem partes da campanha e do QG, mas mobilização,
decisões simuladas e condições pressionadas não demonstram formação espontânea
nem provider remoto. A auditoria de autoria avançou por vários owners em
25/09/2026 e tem regressões negativas com ausência de mutação, mas falta concluir
o inventário transversal. O WIP ainda é extenso, sem commit/push neste
checkpoint; gates antigos ficaram stale após alterações posteriores.

O problema de espaço precisa ser acompanhado junto dos gates, sem sacrificar
causalidade: em 25/09 o volume tinha 8,3 GiB livres (97% usado), o checkout
ocupava 937 MiB e `/tmp` 121 MiB observados; nenhuma remoção foi feita. Isso não
prova que saves futuros caberão. O próximo gate deve registrar espaço livre, tamanho do save,
tempo de save/load e pico RSS por checkpoint. O schema mantém histórico causal
completo e comprimido; qualquer redução deve preservar IDs, sequência, links e
capacidade de auditoria.

Evidência detalhada da seed natural 14: o overflow do dia 240 danificou as
Docas (integridade 0,99 → 0,915), reduziu a leitura local da rota (324 → 296,46)
e foi observado pela Liga das Barcas. Sem escolhas injetadas, a regra offline
`routine-rules/maintenance` autorizou o reparo; o owner consumiu stone, tools e
wood e concluiu o projeto no dia 330, restaurando integridade a 1,0. O smoke de
480 dias passou conservação, save/load e auditoria em 17.764 eventos. Isso prova
a cadeia física natural sob fallback explícito, não escolha por IA: não houve
provider real nem interpretações LLM. Uma fixture separada usa decisões
simuladas para testar compra bilateral e aceites independentes. Ainda faltam
   validar provider real, economia resiliente, formação espontânea de campanhas
   e os gates longos de três seeds por 3.600 dias. A fixture focada já
mantém uma coluna em campanha antes da enchente do dia 240 e compõe, no dia 246
em diante, conhecimento de rota atualizado, decisão de suprimento, disputa de
vazão e carga parcialmente aguardando; foi validada com save/load e auditoria
causal. A extensão posterior comprova, em fixture com overflow natural e
provider simulado, que o QG pode responder após a carga real ser resolvida; não
comprova formação espontânea da campanha nem escolha de provider real.

**Revalidação após os receipts de autoria de 25/09:** rodei novamente a seed
natural 73 por 120 dias, sem provider real, no checkout atual. O save do dia 120
teve 3.859 eventos e 2,27 MB; conservação, checkpoint, save/load equivalente e
continuação até o dia 121 passaram. A auditoria do save retornou `ok=true`, com
zero causas quebradas, erros de autoria, decisões sem fonte, interpretação
material ou evento Story material; encontrou 90 transições materiais
`ACTOR_DECISION` e 2.666 determinísticas. A população ficou em 10.919, sem
mortes por privação; o ledger registrou 9 pedidos e 6 cumprimentos de ajuda,
7 alívios, 7 compras, 4 contratações e 51 transições ocupacionais. O total de
falta no último relatório foi 16, mas saúde média caiu para 951,25 e unrest
médio chegou a 48,75: Ferroalto, Pedra Clara e Porto Velho chegaram a unrest
90/141/140 após episódios datados de escassez e alívio. Isso é sinal para
continuar o diagnóstico econômico por causa/assentamento, não justificativa
para reduzir unrest ou injetar recuperação. Este run curto não satisfaz o gate
de 3 seeds × 3.600 dias nem prova provider real ou autonomia natural de IA.
Uma segunda seed natural (14), também até o dia 120 no mesmo checkout e sem
provider, repetiu exatamente os indicadores agregados de saúde/unrest/falta e a
mesma concentração de pressão em Ferroalto, Pedra Clara e Porto Velho; o ledger
teve 3.839 eventos, auditoria limpa e save de 2,27 MB. Isso torna menos provável
que o sinal seja um acidente exclusivo da seed 73, mas duas seeds por quatro
meses ainda não estimam convergência secular. O snapshot de disco após o save
mostrou cerca de 8,2 GiB livres; os dois saves temporários são pequenos, mas
nada aqui projeta o espaço requerido por dez anos de ledger.
**Horizonte de um ano:** estendi a seed 14 até o dia 360 no checkout atual,
offline, com checkpoints nos dias 120/240/360. O run conservou recursos,
passou os três round-trips e continuações save/load, e a auditoria final ficou
limpa: 12.658 eventos, 8.943 transições materiais (250 com origem de ator), sem
causa quebrada, autoria inválida, Story material ou interpretação LLM. O save
final tem 4,48 MB, save/load levou 2,18/1,45 s, pico RSS ~268 MB e restaram
~8,2 GiB livres. A condição não converge uniformemente: ao dia 360, saúde média
917,75 e unrest 75,62; Pedra Clara ficou com saúde 690/unrest 260, Porto Velho
740/260, enquanto Ferroalto recuperou a 1000/0. Sem mortes, houve 33 pedidos de
ajuda, 30 cumprimentos, 24 alívios e 6 migrações iniciadas. A trajetória reforça
que a pressão econômica é localizada e material, mas ainda não identifica se a
causa dominante é renda, emprego, folha, preços ou rota. Este gate de um ano não
substitui as três seeds de 3.600 dias nem valida provider real.
**Leitura do snapshot da seed 73 (dia 120):** esses três assentamentos ainda tinham 3.513, 5.037 e
4.121 unidades de alimento em estoque público, mas vários grupos artesãos tinham
saldos domésticos de 0–5 moedas (e havia folhas limitadas por `payroll_funds`);
o desemprego/acesso e a distribuição de renda são candidatos mais fortes que
ausência agregada de alimento. Isso é uma hipótese apoiada pelo snapshot, não
causa raiz fechada: a próxima investigação deve ligar emprego, folha, preço e
compras domésticas nos meses 60–120 antes de alterar qualquer regra. A trilha
dos receipts reforça essa hipótese: em Ferroalto/Pedra Clara/Porto Velho, folhas
artesanais pagavam 1–2 moedas por trabalho, contra alimento chegando a 4 por
ração em compras anteriores; alguns grupos gastaram praticamente todo o saldo.
No dia 120 também houve transições autorais de grupos artesãos para `farmer`.
Portanto, o déficit localizado aparece ligado a poder de compra/ocupação com
estoque público disponível e já começou a provocar adaptação; ainda é cedo para
classificar isso como falha de regra ou recuperação suficiente.

**Continuação de dois anos (seed 14, dias 361–720):** o save terminou com
26.423 eventos e passou conservação, checkpoints de 120 dias, round-trip,
continuação e auditoria (`ok=true`; zero causas quebradas, autoria inválida,
decisões sem fonte, efeitos materiais de Story ou interpretação). O save ficou
com 7,99 MB, RSS máximo ~498 MB, save/load 4,67/2,95 s e ~8,2 GiB livres. O
quadro social piorou: saúde média 674,75, unrest 145, falta mensal 506 e ainda
zero mortes; houve 69 pedidos/66 cumprimentos de ajuda, 60 alívios e 128
migrações. No dia 720, estoques públicos continuavam grandes (22.461 em
Campomanso, 29.309 em Cinzaverde, 7.479 em Pedra Clara e 7.333 em Porto Velho),
com preço 1 nesses quatro; ao mesmo tempo, 449 pessoas de Campomanso não tinham
cash para a parcela de ração estimada e o déficit do relatório era 449. O
diagnóstico no snapshot encontrou 11 instalações limitadas por `payroll_funds`
e 66 affordances atuais de reduzir/suspender contratos (18/15/33 por polidade),
embora nenhuma tenha sido escolhida pelo fallback offline. Não é necessária uma
affordance paralela de staffing: essas opções já chegam pelo
`employment_staffing` do menu composto. Isso comprova pressão material e opção
válida disponível, mas não comprova decisão por provider; a chamada externa
autorizada anteriormente era de uso único e já foi consumida. A divergência
permanece aberta entre
riqueza concentrada (no snapshot, 56.927 moedas em grupos populacionais, 14.027
em organizações e 5.046 em polities), affordability e capacidade de payroll.
Não adicionar crédito/subsídio nem escolher por rotina para mascarar o estado.
O smoke só mede fallback; provider real permanece pendente.
Os três testes focados de suspensão sob receipt de folha não paga, decisão de
staffing no menu institucional único e redução após limitação real passaram no
checkout atual (`3 passed`). Isso prova que o menu/owner suportam a escolha; não
prova que um provider remoto a selecionou.

**Instrumentação do smoke:** o relatório mensal agora também registra por
assentamento estoque público, preço, caixa doméstico, estimativa de ração
pública inacessível ao preço atual e instalações limitadas por folha. A
estimativa não substitui `missing_food`: antecede provisões privadas e alívio.
Um teste focal verifica o contrato e os valores básicos; não muda estado nem
política. Assim, a próxima sondagem pode diferenciar estoque, renda e payroll
sem uma consulta ad hoc ao save.

## Trabalho restante, em ordem

1. **Consolidar o checkpoint antes de novas verticais.** Reconciliar o WIP,
   testes, roadmap e handoff; classificar cada requisito como concluído,
   parcial, ausente ou fora de escopo. Preservar mudanças existentes: sem reset,
   commit ou publicação como parte deste plano.
   **Progresso:** corrigi no roadmap uma afirmação antiga de que erro do provider
   retorna ao fallback: no runtime atual, modo IA bloqueia/reverte; fallback
   determinístico fica no modo offline. Também corrigi o intérprete coletivo:
   falha técnica agora propaga `DomainDecisionFailed`, não cria `maintain` ou
   recusa sintética; `single_choice` também não converte falha/ID inválido em
   opção material. Ambos propagam falha, revertem o mês e pausam o loop; fallback
   explicitamente permanece em test mode. Regressões provam rollback de ação
   coletiva anterior quando a seguinte falha e impedem troca material de
   equipamento por fallback. Seis módulos de testes focados passaram
   (`53 passed`). A validação remota continua pendente.
   Nos caminhos offline já revisados — alívio/auxílio, emprego, transição,
   provisões, compra/venda de abastecimento, tarifa, serviço de site, migração e
   diplomacia — decisões identificam `decision_source.kind=fallback`,
   `policy=routine-rules` e a regra aplicada. Isso distingue fallback de
   seleção pelo provider; não reescreve histórico nem prova autonomia
   econômica. A autorização offline de reparo também é marcada; a decisão
   provider é propagada da affordance até a autorização, e cada lote posterior
   identifica execução pelo owner Economy, não uma nova escolha de ator. A
   auditoria de todos os outros turnos offline ainda está aberta.
   **Aceite:** cada afirmação de conclusão aponta para código atual e evidência
   reproduzível; documentos não confundem fixture, smoke, fallback e provider.
   **Auditoria focal em 25/09:** a adoção da defesa estratégica e a prioridade
   de abastecimento de guarnição agora validam no owner a origem `ACTOR_DECISION`,
   o ator e a affordance recomposta. Quatro variantes divergentes por owner são
   rejeitadas sem mutação; o recorte combinado passou em 57 testes. A auditoria
   semântica dos demais owners continua aberta.
   **Alfândega em 25/09:** abertura de posto, resolução de carga, apreensão e
   pagamento agora exigem origem `ACTOR_DECISION` e affordance atual. A regressão
   de abertura determinística preserva snapshot; alfândega/tarifas/embargo
   passaram juntos (`40 passed`), além de Ruff e diff-check. Não fecha a
   auditoria dos demais owners.
   **Criatura em 25/09:** o owner exige decisão atual `ACTOR_DECISION` antes de
   executar qualquer opção da criatura. Uma regressão determinística confirma
   snapshot inalterado; criatura/autonomia/sabotagem passaram (`17 passed`) e
   Ruff/diff-check passaram. Isso não é prova de interferência natural durante
   campanha; os demais owners seguem pendentes.
   **Intriga em 25/09:** espionagem, suborno e sabotagem agora rejeitam no owner
   uma decisão determinística, mesmo quando o payload coincide com a affordance
   atual. Um teste negativo por vertical confirma snapshot inalterado; os três
   módulos passaram juntos (`22 passed`), com Ruff e diff-check limpos. Os
   demais owners permanecem pendentes.
   **Auditoria de procurement/logística em 25/09:** frete interno, compra de
   mercado, objetivo de abastecimento, recuperação bilateral e despacho para
   campanha agora rejeitam seleção material cuja origem não seja
   `ACTOR_DECISION`; decisões de ator diretas em fixtures identificam `api`.
   A revisão também corrigiu um plano bloqueado sem causa: inventário local
   vencido agora é ligado como evidência canônica, e a fixture exercita a leitura
   stale. Regressões negativas cobrem frete, compra, objetivo e provisão de
   campanha sem mutação. Os seis módulos afetados passaram juntos (`70 passed`);
   Ruff e `git diff --check` passaram. Isso fecha os caminhos exercitados, não a
   auditoria de autoria dos demais owners.
   **Continuação em 25/09:** Force também exige autoria `ACTOR_DECISION` nas
   decisões diretas, inclusive mobilização por plano. A affordance de ocupação
   usa o relatório conhecido pelo ator, enquanto o owner revalida a presença
   rival canônica. Um teste negativo confirma que decisão determinística não
   ergue coluna; a fixture de retirada cruza o limiar de suprimento atual. O
   recorte de campanha/Force passou em 69 testes, e oito módulos consumidores
   passaram em outros 50; Ruff/diff-check passaram. A varredura de autoria nos
   demais owners e a formação natural das cadeias seguem abertas.
   **Manutenção/reparo em 25/09:** `start_repair` exige agora que a autorização
   determinística do projeto tenha como causa direta uma escolha atual do
   mantenedor por affordance recomposta; a affordance e a reativação também
   exigem `ACTOR_DECISION`. A política offline registra fallback explicitamente
   e os lotes identificam execução pelo owner Economy. Uma fixture de chamada
   direta foi migrada para o caminho normal; reparo, desgaste, cópia de técnica
   e a regressão de reparo após overflow passaram juntos (`27 passed`), com Ruff
   e `git diff --check` limpos. Uma fixture de frete stale também foi alinhada à
   autoria de API exigida pelo owner de logística. Isto fecha esse recorte,
   não a auditoria global dos owners.
   **Pesquisa em 25/09:** patrocínio e consentimento do pesquisador precisam
   agora ser `ACTOR_DECISION`; o executor da affordance rejeita payload exato
   determinístico, e opções de resposta não aceitam patrocínio sem autoria.
   Regressões confirmam ausência de mutação; pesquisa, apprenticeship, venda de
   técnica e fail-closed passaram juntos (`48 passed`). Isso não fecha a árvore
   tecnológica, difusão natural ou a auditoria global. Ruff e diff-check foram
   executados; F401/F841 preexistentes em arquivos de teste continuam fora do
   recorte.
   **Ritos em 25/09:** patrocínio e cancelamento agora passam pelo helper que
   exige decisão de ator atual; uma affordance válida copiada em evento
   determinístico não inicia o rito. O teste negativo confirma snapshot
   inalterado; o conjunto de pesquisa/difusão/ritos passou (`52 passed`). Isto
   fecha somente os owners exercitados; a auditoria geral continua aberta.
   **Migração em 25/09:** partida e recuperação exigem escolha atual do grupo
   ou autorização interna diretamente causada pela affordance de ator. Payload
   determinístico idêntico é bloqueado; autorização usada não pode ser repetida.
   A fixture de redirecionamento atravessa o executor composto e mantém os
   relatórios como evidência. Migração/conhecimento passaram (`23 passed`). Isso
   não fecha migração espontânea nem sua composição de difusão tecnológica.
   **Diplomacia em 25/09:** o validador compartilhado exige agora
   `ACTOR_DECISION` para ofertas, respostas, pagamentos, ensino/compromissos e
   decisões correlatas. Corrigi sete fixtures de recourse/repudiação que ainda
   criavam decisões determinísticas. Os três casos de abastecimento recíproco
   dependiam de planos bloqueados sem relatório atual de estoque; as fixtures
   agora publicam inventários, esgotam os estoques alimentares próprios e só
   então revisam a política. O owner de abastecimento recíproco também rejeita
   explicitamente decisão determinística. Seis módulos consumidores passaram
   juntos (`43 passed`), incluindo regressão que tenta copiar uma affordance
   válida e confirma snapshot inalterado; Ruff e `git diff --check` passaram.
   Isso fecha autoria e integração nos módulos exercitados, não negociação
   espontânea, provider real, memória influenciando escolha futura nem auditoria
   global de todos os owners.
   **Viagem individual e negação de assembleia em 25/09:** os owners agora
   exigem `ACTOR_DECISION` além de affordance/data/ator atuais. Regressões com
   payload idêntico determinístico confirmam que personagem não viaja e coluna
   não inicia negação material. Viagem e a cadeia de assembleia/religião passaram
   (`6 passed`); Ruff e diff-check também passaram. A transferência de dinheiro
   também exige agora `ACTOR_DECISION` do titular da conta. Testes de pagamento,
   renegociação, remediação de compromisso e cadeia de rota passaram (`13
   passed`). Num grupo maior de economia/diplomacia, cinco falhas ligadas à nova
   autoria (pagamento e quatro fixtures de renegociação) foram corrigidas; duas
   falhas restantes eram cenários não relacionados de workforce/consumo. Repeti
   apenas os casos afetados e passaram; a suíte ampla da economia não está
   verde. A
   varredura seguinte encontrou guards na família cívica e no consumo de
   rações; ambos foram fechados em recortes focados antes de declarar autoria
   global fechada.
   **Cadeia cívica em 25/09:** protesto/recusa, tumulto, movimento/adesão,
   greve, rebelião, resposta e anistia agora exigem decisão `ACTOR_DECISION`.
   As fixtures passaram a declarar `api`; a repressão usa a coorte militar já
   existente, sem duplicar população. O conjunto de protesto/política passou
   (`16 passed`), incluindo caso negativo em que payload determinístico idêntico
   não abre protesto e preserva snapshot. Isso fecha autoria nos cinco owners
   cívicos exercitados, não a varredura global.
   **Consumo de ração e comando de força em 25/09:** a compra doméstica bilateral
   exige agora decisões de ator tanto do grupo comprador como do vendedor; o
   owner de nomeação/doutrina/liberação do comandante exige decisão atual do
   ator. Regressões de payload determinístico provam bloqueio sem mutação. Os
   recortes de consumo, comando de força, engajamento, mortalidade e cadeia
   cívica passaram (`55 passed`); Ruff e diff-check passaram.
   **Mais owners materiais em 25/09:** distribuição/transferência de alívio,
   ocupação explícita após breach de cerco e roubo de técnica agora exigem
   decisão atual `ACTOR_DECISION`; regressões com affordance copiada não alteram
   o estado. Divulgação voluntária de técnica exige autoria também quando é
   acionada por proposta de ensino. Workforce transitória, recrutamento militar,
   criação de emprego permanente e revisão do alvo de contratação também
   revalidam origem de ator. Recortes do primeiro grupo passaram (`46 passed`),
   sighting/ensino/diplomacia passaram (`24 passed`) e workforce/emprego passou
   (`59 passed`); Ruff e diff-check passaram nos arquivos tocados. Uma falha
   intermediária foi fixture desatualizada de decisão diplomática/comando, não
   regressão de execução; fixtures foram alinhadas e recortes relevantes
   reexecutados. Claims/reconhecimento passaram em dois testes, incluindo cópia
   determinística recusada sem mutação. Apprenticeship também passou a exigir
   decisão atual de ator; o recorte passou (`8 passed`), incluindo recusa sem
   mutação para affordance copiada. A mudança da tarifa de exportação também
   exige decisão atual; seus testes focados passaram (`10 passed`), incluindo
   affordance copiada sem efeito. Isso ainda não fecha autoria global: outros
   owners precisam de leitura individual, assim como o gate natural longo do
   checkout atual.
   **Obras, serviços e consentimento bilateral em 25/09:** fundação de linha,
   construção de sítio e expansão agora requerem decisão de ator ou recibo
   determinístico causalmente ligado à seleção atual exata; os adapters não
   transformam uma escolha real em autorização sem origem. Recortes de expansão,
   fundação e construção passaram (`47 passed`). Suspender/retomar serviço de
   sítio e mudar imposto de renda também exigem decisão `ACTOR_DECISION`; sítio
   e tarifa passaram juntos (`17 passed`). Mercado bilateral exige autoria
   independente de comprador e vendedor; tentativas com payload idêntico sem
   autoria não movimentam dinheiro nem carga. Recortes de mercado e venda
   tecnológica passaram (`29 passed`), e o smoke preparado de comércio também
   foi revalidado no grupo (`21 passed`). Embargo comercial revogável agora usa
   diretamente a decisão atual `ACTOR_DECISION`, sem criar decisão
   determinística intermediária; affordance copiada é recusada sem efeito (`13
   passed`). Ruff e diff-check passaram nos arquivos tocados. A autoria global e
   o smoke natural longo continuam pendentes.
   **Progresso em 24/09:** fechei outra lacuna de autoria: decisões `NO_ACTION`
   precisam citar o receipt `ai_decision_declined` do mesmo ator, dia e menu.
   O helper valida e liga o receipt à decisão, e o menu institucional composto
   usa a mesma regra. Uma proposta de pesquisa recusada pelo pesquisador não
   abre projeto nem reapresenta a mesma affordance. Treze módulos focados
   passaram (`123 passed`), Ruff e `git diff --check` passaram. Isso não fecha a
   auditoria de todos os owners, o provider real ou os gates naturais longos.

2. **Fechar a agência econômica no estado atual.** A folha agora expõe custo
   contratado, produção limitada, pressão local e affordances de revisão; ainda
   falta observar uma decisão real do ator/provider entre opções concorrentes e
   sua execução material no owner. Investigar escolhas ignoradas, contexto,
   autoridade e orçamento antes de alterar leis econômicas. Repetir horizonte
   natural suficiente para entender falta, renda, produção, compras, saúde,
   migração e mortalidade. Não criar dinheiro, alimento, emprego, subsídio ou
   recuperação automática para satisfazer métricas.
   **Aceite:** decisão/`NO_ACTION` e seus efeitos têm receipts e fontes; a
   trajetória permanece conservada e explicável mesmo sem recuperação.

   **Contexto de folha permanente — 25/09:** o dossiê local do administrador
   agora distingue trabalhadores pagos por instalações daqueles pagos por
   contratos permanentes próprios. A leitura só inclui payroll do dia corrente
   cujo receipt precede a observação populacional, agrega por ocupação e inclui
   o receipt como fonte; não revela IDs de coorte, contas ou saldos e exclui
   contratos de outros empregadores. Quatro regressões focadas de dossiê e
   emprego passaram (`4 passed`), cobrindo leitura datada, privacidade e
   contexto/causalidade do menu. Isso melhora a informação disponível para
   decisões de staffing, mas não demonstra escolha do provider nem corrige por
   si só a crise alimentar observada até o dia 1.200.

   **Correção de affordance nesta continuação:** sob `production_limited`, os
   alvos de redução passam a ser frações do staffing atual e precisam ser
   estritamente menores; uma segunda crise não oferece aumento de pessoas
   baseado no limite antigo do contrato. Os helpers de criação/revisão por
   comando direto agora exigem `decision_source`. O módulo de emprego passou
   completo (`22 passed`), incluindo staffing já reduzido e audit causal do
   save. Isso corrige a opção e sua autoria, não demonstra escolha natural do
   provider nem recuperação econômica.

   **Validação focada em 24/09:** confirmei no código e rodei novamente o teste
   em que a seed inicial oferece a oficina no menu institucional concorrente,
   junto à leitura local datada de moradores e folha própria. O provider
   simulado escolhe `NO_ACTION`; nenhuma obra é criada. Um segundo teste percorre
   construção, fundação de linha e folha até artesãos receberem salário e
   comprarem alimento, sem recursos adicionados à seed. Ambos passaram. Isso
   prova que a opção e a cadeia material estão acessíveis em fixture com
   seleções simuladas; **não** prova que um provider real a escolherá nem que o
   fallback natural abrirá a oficina. O smoke offline da seed 14 continua
   mostrando escassez localizada, sem justificar mudança de regra antes de
   observar uma decisão real.

   **Contexto da decisão de prioridade produtiva — 24/09:** opções concorrentes
   agora mostram nomes de instalação, assentamento e produtos, unidades, insumos
   próprios disponíveis, capacidade, lotes/limitações anteriores, força de
   trabalho atual não comprometida no owner Society e custo salarial por lote.
   Essa leitura não desconta a folha do ciclo que acabou de produzir e não é uma
   previsão do saldo após os demais owners agendados no próximo ciclo. O contexto
   inclui o saldo da própria
   folha e somente o relatório datado do ator, com idade; não inclui estoque
   estrangeiro nem IDs de estoque/conta. A evidência da leitura local, grupos,
   folha e insumos entra na causalidade da escolha. O owner ainda recompõe e
   valida a instalação escolhida; o contexto distingue a prioridade aplicada no
   ciclo anterior da próxima data em que uma nova escolha terá efeito. A mudança
   não altera produção nem a política offline.
   `tests/test_medieval_production_priority.py`: 7 testes passaram; Ruff e
   `git diff --check`
   passaram. Isso melhora agência informada, mas não prova escolha provider real,
   decisão espontânea ou recuperação econômica.

   **Contexto da manutenção — 24/09:** a affordance de reparo agora vem
   acompanhada de um fragmento próprio: relatório datado/integridade do site,
   materiais e trabalhadores por lote padrão, salário, saldo local dos insumos,
   tesouro próprio e somente leituras de rota já conhecidas pelo mantenedor. IDs
   internos de estoque/conta e inventário de terceiros permanecem fora do prompt;
   o executor continua dono de quantidades e custos efetivos. A regressão cruza
   o limite JSON e compara cada número com os owners, inclusive a leitura de
   rota datada. Quatro testes focados passaram, Ruff e `git diff --check`
   passaram. É contexto validado com provider simulado, não escolha real de IA.

   **Diagnóstico no smoke natural — 24/09:** no dia 480, Campomanso concentra
   111 das 128 unidades de falta mensal. O receipt `event:16947` atribui as 111
   não compradas a coortes sem saldo suficiente (87 artesãos orcs, 9 artesãos
   elfos e grupos menores de soldados/dependentes). Auren tem duas affordances
   correntes de construção de oficina em Campomanso/Pedra Clara, mas o smoke
   offline não as escolhe; não há ainda escolha real ou `NO_ACTION` do provider
   que permita dizer se o ator as avaliou. O próximo passo é observar o menu e
   uma decisão provider atual, mantendo causa e efeitos materiais separados;
   nenhum balanceamento foi feito.

   **Progresso em 24/09:** o observatório agora permite ajustar o orçamento
   compartilhado de consultas por avanço enquanto o mundo está pausado. Antes,
   a configuração persistida era `1` por padrão, mas a UI só tinha o botão de
   ligar/desligar IA; um ciclo com vários atores podia gastar a chamada e então
   pausar/reverter ao encontrar a próxima decisão. A API salva
   `ai_calls_per_step` com o restante da configuração. Isso torna o limite
   explícito e ajustável, mas não prova decisão espontânea, provider real ou
   recuperação econômica.

   **Progresso adicional:** receipts de emprego permanente, transição
   ocupacional, provisões, abastecimento, tarifas, serviços, migração e
   diplomacia verificam autoria `routine-rules`; a contratação de emprego
   permanente agora também é `ACTOR_DECISION` (antes já marcava fallback no
   payload, mas mantinha a origem determinística); provisões mantêm a fonte após
   save/load, e a diplomacia por provider continua marcada `provider`. Os grupos
   focados com auditoria causal passaram (`69 + 28 + 31 passed`). Ruff passou
   nos arquivos tocados, isolando apenas findings anteriores: `E701` em
   `diplomacy_policy.py`; `E701`/`E702`/`F401` em
   `test_medieval_diplomacy_policy.py`; e `F841` em
   `test_medieval_tariffs.py`. `git diff --check` passou.
   A auditoria de manutenção/reparo também passou em 43 testes focados; Ruff
   passou isolando somente um `F841` preexistente em
   `test_medieval_concurrent_civil_decision.py`. Nesta continuação, corrigi
   ainda a origem das decisões de auxílio e diplomacia: seu `decision_source`
   já existia, mas a decisão continuava marcada como determinística; agora é
   `ACTOR_DECISION`, com receipt provider causal quando aplicável. Quatro
   módulos focados passaram (`52 passed`). O inventário transversal dos demais
   `select_option` e fallbacks segue aberto.
   **Continuação:** escolhas explícitas `NO_ACTION` agora geram fatos
   `DECISION` sem delta, associados ao receipt `ai_decision_declined` e às
   affordances recusadas nos turnos de auxílio, diplomacia, abastecimento de
   campanha, viagem, ritos, criatura/tributo, contato armado e aftermath.
   Ausência de provider continua sem ser tratada como escolha do ator. O teste
   de contato armado valida origem `ACTOR_DECISION` e vínculo causal com o
   receipt. Oito módulos focados passaram (`59 passed`) e esse teste focal
   passou novamente após a asserção. Ruff encontrou somente `E402` preexistente
   em `campaign_supply.py` e `E701` preexistentes em `diplomacy_policy.py`;
   `git diff --check` passou. Isso fecha esse contrato nos caminhos revisados,
   não a auditoria transversal de todos os turnos/provider nem os gates naturais.
   **Continuação da auditoria:** a política offline `review_investment` também
   seleciona capacidade a expandir como decisão institucional, mas o evento
   vinha com origem determinística e sem declarar fallback. Agora registra
   `ACTOR_DECISION` e `decision_source=fallback/routine-rules/investment`. Uma
   fixture de pressão de armazenamento percorreu a decisão e criou o projeto;
   dois testes focados passaram. Uma nova varredura estática reduziu de 23 para
   22 os `record_event(..., fact_kind=DECISION)` sem `causal_origin` explícita;
   esses casos restantes incluem autorizações internas e escolhas que precisam
   ser classificadas individualmente, não alteradas em lote. Ruff passou
   ignorando `E701`/`E702` preexistentes em `test_medieval_industry.py` e o diff
   está limpo.
   **Continuação econômica:** encontrei decisões de fallback que já carregavam
   `decision_source.kind=fallback`, mas ainda eram marcadas como determinísticas.
   Corrigi a origem para `ACTOR_DECISION` nas escolhas offline de contratação
   permanente, provisões domésticas (comprador e vendedor), migração/recuperação,
   abastecimento/compra e resposta de vendedor, transição ocupacional, tarifa e
   serviço de site. Os sete módulos econômicos focados passaram (`102 passed`);
   Ruff passou ignorando `E402`/`E701` existentes e o `F841` em
   `test_medieval_tariffs.py`; `git diff --check` passou. Aquele checkpoint
   ainda tinha chamadas `DECISION` sem origem explícita; a revisão posterior
   abaixo zerou essa lacuna estática. Segue pendente a revisão semântica global
   das origens já declaradas e comprovar economia natural no horizonte planejado.

   **Auditoria de autoria — publicação e comandos do personagem:** os comandos
   diretos de viagem/prática agora persistem `ACTOR_DECISION` com
   `decision_source=player` e referência explícita ao personagem. Boletins de
   mercado, rota, rota fiscal e assentamento permanecem automáticos no refresh
   mensal; em vez de atribuí-los falsamente ao ator/provider, registram origem
   `DETERMINISTIC` e a regra do owner `knowledge` em `causal_payload`. A
   especificação e o contrato local agora deixam essa limitação explícita. Uma
   varredura AST encontrou zero chamadas `record_event(..., fact_kind=DECISION)`
   sem `causal_origin` explícita; isso não substitui a revisão semântica de cada
   origem nem prova autonomia. Os módulos de boletins e o fluxo de ações
   passaram em conjunto com os testes de engine (`49 passed`); Ruff e
   `git diff --check` passaram.

   **Gate de autoria das decisões:** o auditor causal agora aponta fatos
   `DECISION` de ator sem `decision_source` e valida que um source `provider`
   cite e corresponda ao receipt de interpretação/recusa ligado à escolha; para
   `fallback`, exige política e regra nomeadas. Fixtures negativas cobrem fonte
   ausente e fallback incompleto. No save natural do dia 120,
   as 642 decisões `ACTOR_DECISION` tinham fonte `fallback`; a auditoria
   standalone continuou `ok=true`, com arrays de autoria vazios. O recorte de
   testes de auditoria, menu institucional e abastecimento passou (`20 passed`).
   Isso fecha a observabilidade dessa regra no gate, não a autonomia provider
   nem a revisão semântica completa dos owners.

   **Fechamento do enforcement no ledger — 24/09:** `record_event` agora rejeita
   imediatamente decisão `ACTOR_DECISION` sem fonte auditável, e
   `validate_history` repete a regra ao reler o histórico. Fonte `provider`
   precisa citar receipt anterior de interpretação/recusa, sem delta, que
   corresponda ao ator e à affordance escolhida; `fallback` exige política e
   regra. Decisões `player`/`api` continuam explícitas. Isso fecha também os
   helpers de ritos e vendas de técnicas, em vez de deixar a auditoria detectar
   a ausência só depois.

   O ajuste revelou e corrigiu uma falsa autoria no ensino de técnicas: oferecer
   ensino já revela a técnica à contraparte, então o receipt de conhecimento é
   consequência da decisão de oferta, não uma segunda decisão de divulgação
   inventada. A validação aceita tanto a affordance explícita de divulgação
   quanto uma oferta de ensino canônica, mantendo o evento do owner ligado à
   decisão original. Testes focados de diplomacia, validação de conhecimento,
   autoria e auditoria passaram (`35 passed`); Ruff passou ignorando apenas
   `E701`, `E702` e `F401` preexistentes nesses arquivos; `git diff --check`
   passou. Ritos, alcance, política de rito, interação com criatura, venda de
   técnica, autoria e auditoria passaram em outro recorte (`39 passed`). Esse
   recorte mais amplo também revelou fixtures de treinamento que duplicavam uma
   coorte soldier já existente e uma asserção de schema obsoleta (72 em vez de
   74). Ajustei os destacamentos de fixture para usar coortes reais existentes
   e quantidades disponíveis, e sincronizei a expectativa do observatório com o
   schema corrente. Os módulos de treinamento e a projeção do observatório
   passaram juntos (`8 passed`). A auditoria semântica de todos os owners
   continua aberta.

   **Vínculo entre mutação e escolha humana/actor — 24/09:** endureci a regra
   do owner de eventos. Uma mutação marcada `ACTOR_DECISION` não pode mais usar
   como decisão-fonte uma autorização determinística que por acaso repete o
   mesmo ator e affordance; a fonte precisa ser um `FactKind.DECISION` com
   origem `ACTOR_DECISION`, e o payload da mutação precisa corresponder a ele.
   A regressão negativa cobre a tentativa de atribuir ao ator uma autorização
   gerada pelo owner. Ajustei também as fixtures de comandos diretos para
   declararem `decision_source=api`, e o stub de seleção provider agora emite
   um receipt de interpretação anterior em vez de pular essa fronteira. O
   recorte de autoria, infraestrutura/serviço, workforce, comando militar e
   engajamento passou (`82 passed`). Isto valida o contrato nos owners tocados;
   não fecha a auditoria semântica dos demais nem os gates naturais longos.

   **Propagação da autoria às fixtures de outros owners:** a mesma validação
   estrita mostrou decisões de API em fixtures de reativação de infraestrutura,
   transição ocupacional, comando/engajamento, rito e resposta de criatura que
   estavam sendo registradas com origem default determinística. Corrigi esses
   chamadores para declarar `ACTOR_DECISION`/`decision_source=api`; seleções
   simuladas por provider gravam receipt correspondente. Um recorte de
   diplomacia, conhecimento, rito, criatura, venda, autoria e auditoria passou
   (`67 passed`). O Ruff focado passou ignorando só `E701`/`E702`/`F401`
   preexistentes e `git diff --check` passou. O mecanismo está enforced para os
   tipos de mutação, mas o inventário e revisão semântica dos owners ainda
   precisam ser concluídos.

   **Smoke natural após o enforcement — 24/09:** seed 73, 120 dias, offline,
   sem provider real ou perfil de governo. O run fechou com 3.859 eventos,
   população 10.919, falta agregada 93, saúde média 951,25, unrest médio 48,75,
   zero mortes por privação; 9 pedidos/6 cumpridos, 7 alívios, 7 compras, 4
   contratações e 51 transições de workforce. Moeda e recursos foram
   conservados, o round-trip e a continuação até o dia 121 passaram; os saves
   dos dias 60 e 120 também passaram. A auditoria em ambos checkpoints e no
   save final retornou `ok=true`, com zero causas quebradas, fontes de decisão
   inválidas, transições sem decisão de ator ou mutações Story/interpretação.
   O run expôs um bug no auditor: fallback nomeado passava pela regra própria,
   mas caía no branch de tipo desconhecido. Corrigi o classificador e adicionei
   regressão para `fallback` válido. Isto é validação curta de integridade após
   a mudança, não o gate de 3.600 dias, não autonomia provider e não prova
   resiliência econômica; a pressão local em saúde/unrest continua visível.

3. **Validar o uso atual de IA sem confundi-lo com autonomia geral.** Com
   autorização vigente para chamadas externas e payload sintético mínimo,
   validar escolhas de economia e campanha no schema corrente, inclusive
   `NO_ACTION`, erro/timeout e affordance stale. O owner recompõe opções e
   revalida a escolha. Se não houver autorização, manter esse item explicitamente
   pendente; não substituir a evidência por mock ou `routine-rules`. A sonda foi
   ampliada para usar o menu mensal institucional completo e exige uma polity com
   duas ou mais opções concorrentes de prioridade produtiva no mundo natural; ela
   não executa a affordance. `provider_available()` retornou `True` em checagem
   anterior, mas a autorização era de uso único e já foi consumida. Nenhuma
   chamada remota foi feita nesta continuação. A recomposição completa expôs e
   corrigiu uma colisão de chave: prioridade produtiva e construção usavam
   `production`, mas apenas o contexto de construção era mantido; agora o
   provedor recebe contextos separados para ambas as famílias. Vinte e um testes
   focados da sonda, prioridade, agenda e cadeia de oficina passaram; a escolha provider
   real segue pendente. O
   observatório expõe o orçamento
   compartilhado por avanço, sem aumentar o padrão nem trocar falha por fallback.
   **Aceite:** receipts provam chamadas reais atuais, nenhuma interpretação
   altera estado e falhas não deixam mutação parcial.

4. **Fechar a composição de campanha e comando, sem criar outro sistema.** As
   fixtures já atravessam policy/titular, QG, comandante, coluna, rota, carga,
   criatura, combate e aftermath em decisões separadas. Auditar gaps restantes
   de campanha persistente, ordens/relatórios atrasados, suprimento, retirada,
   cessar-fogo, controle territorial e save/load; corrigir somente casos
   reproduzidos. Depois observar a cadeia em mundo natural, sem exigir que guerra
   aconteça em toda seed.
   **Aceite:** mudar uma causa material ou uma decisão muda o resultado pela
   mesma campanha/coluna; cada ator usa seu próprio conhecimento e autoridade.

   **Correção de autoria em 25/09:** o owner da prioridade de abastecimento da
   guarnição agora rejeita evento de decisão com origem, ator, ação ou affordance
   divergentes da opção canônica recomposta. A regressão também verifica ausência
   de mutação em todas as rejeições. Isso fecha um caminho direto de owner; não
   substitui a varredura semântica completa nem prova a formação natural da
   cadeia de comando.

   **Verificação focada em 24/09:** passaram o teste de ocorrência hidrológica
   natural da seed 14 até redução de capacidade/relatório datado e o teste
   composto já existente em que uma criatura fecha rota, interrompendo a marcha
   da coluna e afetando a carga alimentar enquanto a rota alternativa permanece
   aberta. São duas provas úteis, mas distintas: ainda não houve uma única
   trajetória em que o dano natural de enchente altere um frete/campanha ativo e
   provoque uma decisão posterior do QG ou comandante. Não atribuir ao teste da
   criatura uma composição com enchente. Nesta continuação, acrescentei um elo
   intermediário reproduzível: depois do overflow natural da seed 14, uma
   decisão material de frete tentou usar o trecho danificado; o owner de
   logística limitou a saída pela capacidade atual e deixou o restante esperando.
   O evento de partida cita o dano da enchente como causa. No dia do teste,
   tráfego concorrente consumiu parte da vazão: 294 de 324 unidades partiram e
   30 ficaram preservadas em espera. Save/load e auditoria causal do save final
   também passaram. Uma segunda fixture mantém a coluna ativa antes do evento:
   Auren a mobiliza com seus próprios soldados, ração e folha usando relatórios
   datados; ela chega a Portovelho antes do overflow natural do dia 240. Quando
   sua necessidade de rações abre (dia 246), o menu de suprimento usa o relatório
   atual pós-enchente. Um provider simulado seleciona essa affordance; carga
   concorrente consome a vazão e deixa parte das rações esperando. Save/load e
   auditoria causal também passam. Isto demonstra, numa trajetória composta
   com decisões explícitas, enchente durante campanha ativa→relatório atualizado
   →decisão independente de suprimento→frete limitado. Ainda não é uma escolha
   de provider real nem uma decisão estratégica do QG de revisar/desviar/retirar
   a campanha.

   **Progresso nesta continuação:** a situação dirigida ao QG após o titular
   político autorizar agora inclui a referência da ordem, emissor, data e escopo
   autorizado; o teste percorre save/load antes dessa consulta e confirma que a
   decisão seguinte é feita pelo QG. Substituí mocks que pulavam `ai_decider`
   por respostas JSON simuladas no limite do provider na cadeia de interferência.
   Isso revelou que escolhas do QG entre várias rotas podiam duplicar IDs de
   receipt e abortar; `ai_decider._receipt` agora deduplica causas compartilhadas
   no boundary central, preservando a rejeição de referências desconhecidas, e
   os chamadores normalizam listas compostas com `_causes`. A fixture
   política→QG→comandante, criatura→rota fechada→coluna parada→retirada,
   save/load e auditoria causal passou em três testes focados; a regressão
   central de receipt mais os testes focados de decisão/QG passaram em conjunto
   (`15 passed`), com Ruff e `git diff --check`. Continua sendo fixture com
   provider simulado; formação natural da cadeia e provider real permanecem sem
   prova.

   **Progresso em 24/09:** decisões do provider em contato armado, aftermath,
   resposta do QG após boletim, cadeia titular→QG, despacho de suprimento,
   patrocínio/oferta de rito e viagem individual agora são registradas com
   `CausalOrigin.ACTOR_DECISION`; `record_event` as liga ao receipt real da
   seleção. O `NO_ACTION` do QG deixa de ser representado por um affordance ID
   sintético e continua semanticamente registrado como `maintain`. Seis módulos
   focados passaram (`47 passed`). A fixture de viagem teve seu orçamento de
   chamadas atualizado para o teto suportado (256), pois o menu institucional
   compartilhado consumia o antigo limite 64 antes do turno do personagem. Isso
   corrige autoria/proveniência nessas decisões, mas não prova provider real,
   formação natural de campanha nem auditoria de todos os domínios.

5. **Fechar o inventário das verticais principais, uma por vez.** Comparar o
   roadmap com o código atual antes de escolher a próxima fatia. Prioridade:
   (a) tecnologia e difusão ainda ausentes no aceite do roadmap — conservação,
   aço, pólvora/artilharia, vapor e logística, sem ampliar catálogo por si só;
   (b) magia, ecologia e criaturas além das fatias V1 já existentes;
   (c) intriga, religião e conflito civil com evidência, conhecimento e ação
   material. Reusar affordances, owners, autoridade e memória; não criar
   minigames nem eventos obrigatórios.
   **Aceite por fatia:** decisão válida → execução do owner → efeito material →
   fato causal navegável → save/load e regressão focal. Não declarar a categoria
   inteira concluída por uma fixture estreita.
   **Correção hidrológica em 24/09:** a estação anterior tinha apenas um mês
   possível acima do limiar embora a lei exigisse dois meses consecutivos; assim,
   o overflow era impossível sem fixture forçada. A janela sazonal agora permite
   dois meses altos raros para certos pares de seed/região, sem quota nem dano
   obrigatório. Um teste natural integrou os dias 210–240 e percorreu a cadeia
   até dano de integridade nas Docas de Portovelho, somente após as duas
   leituras altas; as provas de não recorrência e de dano/resistência sob carga
   sustentada também passaram. Seed 73 pode ficar
   sem ocorrência durante 120 meses; uma projeção da lei em 8 regiões registrou
   0/2/2 ocorrências nas seeds 73/101/137. A projeção não é smoke mundial; dano
   natural foi provado na seed 14, mas frequência e efeitos em horizonte longo
   seguem pendentes.
   **Progresso de proveniência tecnológica:** as decisões explícitas de patrocínio
   fallback de pesquisa, aceitação do pesquisador e aplicação offline agora são
   `ACTOR_DECISION` e identificam suas regras `routine-rules`. O receipt interno
   `research_authorized` continua uma autorização do owner, não uma segunda
   escolha atribuída ao ator. Três testes focados passaram (incluindo persistência
   do projeto e política natural); Ruff passou ignorando `F401`/`F841` já
   existentes em `test_medieval_research.py`, e `git diff --check` passou.
   No caminho offline, a aceitação continua explicitamente sob `routine-rules`.
   No caminho provider, a instituição agora cria apenas uma proposta datada; o
   personagem recebe uma affordance individual no calendário, pode aceitá-la ou
   escolher `NO_ACTION`, e o projeto só começa após essa decisão. A resposta usa
   remuneração/escopo authored, é revalidada pelo owner e sobrevive a save/load
   antes do consentimento. A evidência atual usa provider simulado, não confirma
   disponibilidade real nem formação natural.
   **Continuação da difusão:** os receipts próprios de pedido/consentimento de
   venda de técnica e a oferta de instrução por especialista migrado agora
   declaram `ACTOR_DECISION` em vez de herdar origem determinística. Dois testes
   de transferência bilateral de técnica e instrução paga passaram. Isso ajusta
   a autoria desses contratos/helpers; não prova integração da oferta de
   instrução no calendário/menu natural, nem fecha difusão tecnológica.
   **Progresso em 24/09:** a oferta do especialista agora entra no turno
   individual mensal já existente, junto às affordances locais de rito; o
   especialista pode escolher uma delas ou `NO_ACTION`, e opções recusadas não
   são reapresentadas sem nova evidência. O patrocínio foi registrado como mais
   uma família no menu institucional compartilhado, sem consulta/planner
   paralelo. Corrigi a validação do contrato para permitir oferta anterior e
   exigir que a decisão do patrocinador coincida com o início material. Doze
   testes focados de apprenticeship/turno individual passaram; o teste novo
   verifica oferta por turno agendado, recusa sem repetição e patrocínio no menu
   institucional em dia posterior. Isso usa provider simulado e fixture; ainda
   não prova emergência em mundo natural nem provider real/horizonte longo.
   **Agência do pesquisador em 24/09:** removi a aceitação sintetizada no
   executor provider. A proposta institucional agora fica pendente em evento +
   agenda; no dia seguinte o próprio pesquisador vê uma affordance com técnica,
   local, pagamento e patrocinador. Só aceitar chama o owner para criar o
   projeto; `NO_ACTION` não cria contrato, e mudança material invalida/lapsa a
   proposta. O aceite do pesquisador continua determinístico e nomeado apenas
   no fallback offline. Cinco módulos focados passaram (`42 passed`), incluindo
   menu mensal compartilhado, resposta individual, save/load pendente, rejeição
   do owner e auditoria causal. Não é evidência de provider real nem de escolha
   espontânea num mundo natural.

   **Enforcement de autoria após integração — 24/09:** a auditoria estrita do
   ledger revelou que a oferta de instrução do especialista ainda registrava
   `ACTOR_DECISION` sem `decision_source` e sem ligar o receipt de interpretação
   ao fato. O caminho do calendário agora propaga o receipt do provider como
   causa; chamadas diretas exigem fonte explícita (`api` nas fixtures). Sem
   relaxar o guard, apprenticeship, venda de técnica e pesquisa passaram em
   conjunto (`34 passed`), e Ruff passou nos arquivos tocados. Isso fecha essa
   lacuna de proveniência, não comprova decisão/provider real ou difusão
   tecnológica natural.

   **Causalidade do procurement no smoke — 25/09:** a auditoria do save de 120
   dias revelou duas transições `supply_plan_updated` sem causa, ambas de
   objetivos de reparo bloqueados por falta de relatório atual. A política agora
   liga bloqueios aos receipts dos projetos de reparo, instalação, expansão ou
   pesquisa que criaram a necessidade; se não houver fonte canônica, não cria
   novo plano material. Uma regressão focal passou. No smoke natural offline
   seed 73/dia 120, conservação, checkpoints, save/load e continuação passaram;
   a auditoria retornou `ok=true`, sem causa quebrada, autoria/fonte inválida,
   mutação de Story/interpretação e com `supply_plan_updated` em 145/145 eventos
   ligados a causas (antes 143/145). O horizonte curto ainda tem falta mensal
   16 e saúde média 951,25; isso é integridade causal, não economia resolvida.

6. **Concluir observabilidade e viabilidade operacional.** Verificar no app/API
   PT-BR a navegação entre decisão, evento, owner, deltas e evidências para
   economia, personagens/instituições, campanha e ameaças. Medir custo de
   consulta, tempo de avanço, RSS e tamanho de save; reduzir gargalos medidos sem
   truncar causalidade necessária.
   **Progresso:** no save natural do dia 510 (18.947 eventos), o menu mensal
   caiu de 4,10 s para 1,94 s após eliminar quatro scans redundantes do ledger,
   mantendo os mesmos 33 atores e 280 opções. Isso é uma medição única, não fecha
   o gate longo; composição de opções e agenda ainda dominam. Uma medição
   instrumentada posterior encontrou scans históricos nos aceites de compra e
   venda de técnica, e cálculo de contexto estratégico em builders diplomáticos
   que só precisavam de campos mecânicos. Após usar o índice transitório e
   separar os contextos, o mesmo save caiu de 1,296 s para 0,713 s em `_by_id`
   sob cProfile e de 0,561 s para 0,246 s sem profiler, mantendo 33 atores e as
   mesmas 280 affordances. Ainda é medição pontual; prévia de suprimento e
   contratos de emprego agora dominam esse recorte. Em nova medição do mesmo
   save do dia 510, `StrategyState.capacity_for` caiu de 0,305 s para 0,090 s
   após evitar leituras dinâmicas de campos Pydantic ausentes; o menu passou de
   1,469 s para 1,252 s, mantendo 33 atores e 280 affordances. É uma comparação
   pontual sob profiler, não benchmark estável; a composição de opções continua
   dominante.
   **Aceite:** o Dao consegue investigar causas no produto, e limites de
   desempenho são medidos e reportados no checkout atual.

7. **Executar o gate final uma única vez após estabilizar o checkout.** Rodar
   regressões focadas dos owners tocados, API/frontend/build e auditoria causal;
   então três seeds naturais por 3.600 dias com checkpoints, conservação,
   save/load/continuação. O smoke agora pode gravar meses, verificações dos
   checkpoints e conclusão/interrupção num journal JSONL durável, criado sem
   sobrescrita; isso preserva evidência de um run longo interrompido, mas não
   substitui retomada nem auditoria causal. Rodar separadamente fixtures
   pressionadas para exigir cadeias multietapas.
   **Aceite:** zero causas quebradas, erros de autoria, mutações por Story/
   interpretação ou rollback incompleto; reportar economia, provider, tempo,
   memória e saves. Uma seed natural estável ou sem guerra continua válida.

## Fora deste ciclo

Industrial Warfare, torneios e outras features laterais; novas abstrações sem
gap comprovado; balanceamento para forçar prosperidade/drama; fallback que
escolhe a opção “certa”; e qualquer narrativa que substitua decisão ou efeito
material.

## Evidência de partida e limites

No checkout atual, smoke natural schema 74 da seed 73 chegou ao dia 480 com
conservação, save/load e auditoria causal aprovados em 17.832 eventos, mas
terminou com falta mensal 355 e saúde média 870,88; continuação até o dia 510
agravou para falta 378 e saúde 861,50. Não houve provider real nesse smoke. Há
fixtures compostas de campanha e economia, mas elas não demonstram formação
espontânea. Os smokes antigos de dez anos ficaram stale após mudanças de schema
e regras; precisam ser repetidos no checkout estabilizado.

Referências canônicas: `docs/handoff/medieval-roadmap.md` (escopo do produto),
`medieval-roadmap-general-remaining-plan.md` (lacunas detalhadas) e
`docs/handoff/medieval-current-state.md` (evidências do checkout). O estado
Git/WIP continua amplo e deve ser preservado durante a execução.

## Checkpoint natural offline de 720 dias e diagnóstico econômico — 25/09/2026

O checkout atual foi retomado do save da seed 14 no dia 120 e avançou mais 600
dias, até o dia 720, com `routine-rules` offline e sem provider real. O journal
registrou 26.423 eventos; checkpoints intermediários conservaram recursos e
passaram save/load. A auditoria final passou: 19.156 transições materiais,
153 raízes explícitas, zero causa quebrada, material sem raiz/link, erro de
autoria, DECISION sem fonte, Story material ou interpretação material. O save
final mede 7.987.200 bytes; a execução levou 192,58 s e o pico observado de RSS
foi aproximadamente 487 MB. Este checkpoint atualiza a evidência do smoke curto,
mas ainda não substitui três seeds por 3.600 dias.

No último ciclo havia população 10.931, falta agregada 506, saúde média 674,75,
unrest médio 145 e zero mortes por privação; foram registradas 128 migrações,
69 pedidos e 66 cumprimentos de ajuda e 59 compras de mercado. O quadro revela
restrição de acesso/caixa em vez de simples ausência de estoque: Campomanso
tinha 22.461 alimentos públicos e 449 de falta, com folha agrícola limitada por
`payroll_funds`; em snapshots da mesma data, os compromissos mensais atuais dos
contratos de emprego somavam 3.124 contra saldo 802 na tesouraria de Auren,
3.754 contra 2.667 em Escárlia e 2.108 contra 1.577 em Valedouro. Esses valores
são leitura de um estado final, não previsão de folha nem diagnóstico universal.
Os contratos pagam trabalhadores antes da produção e compartilham as contas das
instalações; receita posterior de compras/mercado não financia retroativamente
a produção daquele ciclo. O próximo passo econômico é rastrear, por ciclo e por
conta, caixa inicial, salários realmente pagos, recebimentos, produção limitada
e acesso doméstico; não reduzir compromissos, subsidiar ou alterar preços sem
reproduzir um defeito ou identificar uma decisão/affordance ausente. A trajetória
é fallback offline e não prova que um provider real escolheria manter ou
reestruturar esses vínculos.

**Instrumentação para a continuação econômica:** o smoke agora inclui
`monthly_metrics.payroll_liquidity`, agrupado pela conta empregadora
compartilhada. O read model distingue saldo, teto de folha dos contratos,
capacidade máxima de folha das instalações, folha realmente paga no dia,
resultado dos contratos revisados e instalações limitadas por caixa. O mesmo
snapshot mostrou que caixa agregado não explica acesso por si só: Campomanso
tinha 11.619 de saldo doméstico agregado e estimativa de 449 rações públicas
inacessíveis. Os tetos não são previsão; a projeção não altera owners. Dois
testes focados passaram (`2 passed`), inclusive snapshot invariável. O próximo
smoke pode agora preservar essa série por ciclo no journal para localizar
quando a liquidez diverge da folha e do acesso doméstico.

## Continuação econômica até 1.200 dias — 25/09/2026

O smoke retomado no dia 720 concluiu mais 480 dias (seed 14, modo offline,
`routine-rules`, sem provider) até o dia 1.200. Os checkpoints 840/960/1080/1200
conservaram recursos e passaram save/load. O save final tem 47.431 eventos e
13.258.752 bytes; duração do trecho: 443,24 s; pico RSS observado: 817.827.840
bytes. Auditoria do save atual: `ok=true`, 36.671 eventos materiais, 153 raízes
válidas, zero material sem raiz/link, causa quebrada, erro de autoria, DECISION
sem fonte, Story material ou interpretação material. Não é o gate de dez anos.

O quadro social piorou: população 10.831, 100 mortes por privação no trecho,
saúde média 338,88, unrest 474,75 e falta do ciclo final 509. Até o dia 1.200,
foram acumulados 114 pedidos/108 cumprimentos de ajuda, 153 migrações, 100
compras de mercado, 27 contratos de emprego e 90 transições de workforce. Em
Campomanso, a mesma falta de 449 persistiu nos oito ciclos de 990 a 1.200,
enquanto o estoque público caiu de 16.795 para 7.535 e a saúde foi de 264 para
0. O receipt de subsistência atribui o déficit principalmente ao grupo de
agricultores anões (338 rações no cálculo do dia 1.200), além de artesãos e
soldados; os grupos afetados tinham saldo zero, enquanto coortes agrícolas
empregadas conservavam saldo. A população já refletia mortes ao fim do ciclo,
por isso o grupo de 338 no receipt aparece com 332 no snapshot posterior.

O menu recomposto no dia 1.200 não oferecia novo vínculo de emprego nem obra
local nesses assentamentos, mas expunha opções atuais para reduzir/suspender
contratos agrícolas existentes em Campomanso; portanto há um caminho causal de
decisão possível, ainda não observado como escolha de provider. Os tetos de
folha dos contratos não são despesa realizada: por exemplo, Auren tinha teto
3.124 e saldo final 691, Escárlia 5.486/7.014 e Valedouro 3.332/7.101. Não
concluir que o teto é dívida, nem que cortar empregos seja a solução correta.
Como o turno é offline, não sabemos se um provider escolheria reestruturar
folha, abrir uma obra depois de liberar caixa ou manter `NO_ACTION`. Próxima
investigação: seguir a decisão e o caixa antes/depois por conta e coorte; obter
consulta real somente com autorização vigente. Não adicionar subsídio, renda,
estoque, emprego ou cota de recuperação.

Desde a instrumentação de 25/09, cada amostra mensal preserva o read model de
liquidez no journal. `tests/test_medieval_autonomy_smoke.py` focados passaram
(`2 passed`) e `git diff --check` passou. O smoke 720→1.200 é continuação do
mesmo estado e do mesmo fallback, não uma seed natural independente.

**Rastreamento do caixa em Campomanso — 25/09/2026:** reabri o save do dia
1.200 e comparei payrolls, grupos, produção e subsistência. A conta de Auren
termina em 691; o vínculo de agricultores anões não existe, enquanto os três
vínculos permanentes existentes pagaram no dia 1.200 apenas 109 elfos, 77
humanos e 8 orcs. A instalação agrícola Campos do Lume registrou zero lotes por
`payroll_funds` (o bloqueio é de caixa, não de trabalhadores, integridade,
insumos ou capacidade). O mercado ainda tinha 7.535 alimentos a preço 1, mas
691 de 1.140 rações foram compradas; 449 faltaram, concentradas em coortes sem
saldo, principalmente agricultores anões. Isso aponta para renda e caixa mal
distribuídos e uma disputa real entre folhas, não para falta física total de
alimento. Ainda não determina qual vínculo deveria ser reduzido nem demonstra
uma escolha de IA: o estado veio do fallback `routine-rules`. A próxima prova
precisa acompanhar decisão, conta, payroll, lotes e compras no ciclo seguinte,
com provider real apenas mediante autorização vigente.

O dossiê privado do administrador foi complementado para mostrar, separadamente
da folha de instalações, a quantidade local paga por contratos permanentes
próprios, agrupada por ocupação e ligada ao receipt do payroll. Uma prova focal
agora exercita essa leitura dentro do menu de staffing e confirma que a decisão
cita o receipt como causa, sem expor IDs de coorte. Dossiê/emprego: `17 passed`;
uma repetição específica do fluxo de staffing e da leitura agregada: `3 passed`;
`git diff --check` passou. Isso fecha uma lacuna de contexto causal, não a
investigação da economia nem a auditoria de autoria de todos os owners.

O journal do smoke também registra agora saldo doméstico e estimativa de rações
públicas inacessíveis agregados por ocupação, preservando os totais anteriores.
É diagnóstico offline, não contexto de ator nem regra econômica; não persiste
IDs de coorte e não altera o mundo. A regressão confirma que cada distribuição
fecha exatamente com seu agregado e que a projeção permanece read-only. Isso
permite comparar emprego/renda e falta por ocupação no próximo horizonte sem
confundir estoque público com acesso das famílias.

Aplicado ao save existente do dia 1.200, o read model deu 17.661 moedas
domésticas agregadas em `farmer`, mas ainda estimou 332 rações públicas
inacessíveis nessa mesma ocupação; artesãos tinham 93, soldados 15 e dependentes
2. A estimativa total (442) não é o déficit real de subsistência (449): ela é
calculada antes de provisões privadas e relief e deve continuar identificada
como projeção. O contraste mostra que ocupação sozinha não explica quem tem
renda dentro de um grupo ocupacional, mas é uma série agregada útil e sem IDs.

**Confirmação do journal no horizonte retomado — 25/09/2026:** a seed 14
avançou do dia 1.200 ao 1.230 em 30 dias offline (`routine-rules`, zero
chamadas reais de IA). O journal contém os dois agregados por ocupação; para
Campomanso, no dia 1.230, `farmer` concentra 17.668 de caixa agregado e 326
rações estimadas inacessíveis, enquanto `artisan` tem 92 e `soldier` 15. A
estimativa é anterior a provisões/alívio e não equivale à falta real. No mesmo
trecho, a falta total reportada passou de 509 para 848, a saúde média de 338,88
para 325,88 e houve 18 mortes por privação. Moeda/recursos, checkpoint,
save/load e auditoria do ledger passaram; no dia 1.230 o auditor encontrou
48.780 eventos, zero causa quebrada, autoria inválida, Story/interpretação
material ou material sem raiz/link. É continuação do mesmo estado e fallback,
não uma seed independente nem evidência sobre o que um provider real escolheria.

## Seguimento econômico natural até 1.260 dias — 25/09/2026

Retomei esse mesmo save por mais 30 dias, ainda offline (`routine-rules`, sem
provider), até o dia 1.260. Conservação monetária/de recursos e save/load
passaram; o save tem 50.295 eventos e 13.934.592 bytes. O causal audit atual
retornou `ok=true`, sem causas quebradas, erros de autoria, Story/interpretação
material ou material sem raiz. Não é seed independente nem gate de dez anos.

O retrato ficou misto, não uma recuperação: falta de comida total caiu de 848
para 530, enquanto saúde média caiu de 325,88 para 318,62, unrest subiu de
474,75 para 512,38 e mortes por privação acumuladas subiram de 118 para 162
(+44). Em Campomanso havia 4.841 alimentos públicos a preço 1 e 435 de falta;
o grupo ocupacional `farmer` tinha 17.664 moedas agregadas, mas a projeção
estimava 428 rações públicas inacessíveis no assentamento. Essa estimativa não
é falta real nem identifica famílias, e a observação confirma que estoque e
caixa agregados não bastam para explicar acesso individual.

Auren encerrou com 674 moedas; no ciclo, o payroll pagou 740, quatro vínculos
foram pagos, dois falharam por fundos e três instalações limitaram produção
por `payroll_funds`. O menu atual do ator tinha 18 opções de ajuste de folha,
incluindo suspensão dos contratos sem fundos, mas não houve decisão de ajuste
no ciclo. Como `ai_enabled=false`, isso demonstra disponibilidade da affordance
e ausência de seleção do fallback offline — não recusa do ator nem o que um
provider escolheria. Não vou adicionar uma escolha determinística de corte,
pois isso confundiria a política offline com a decisão de IA e poderia reduzir
renda sem evidência de benefício às famílias. A validação dessa decisão ainda
requer provider real autorizado; em paralelo, o gate econômico natural longo
segue aberto.

## Breach material por venda incompatível — 25/09/2026

Fechada uma fatia específica da lacuna de commitments: quando uma venda
bilateral autorizada pelo dono consome o estoque e recurso explicitamente
prometidos em uma obrigação de entrega vigente, o owner de mercado agora
conclui essa obrigação como breach material, ligado ao consentimento do
vendedor e ao receipt de frete. A contraparte recebe os notices/memórias
canônicos; o dossiê diplomático distingue `materially_breached` de repudiação
explícita e lapso de prazo, e a API expõe
`commitment_materially_breached`. Nada reserva ou transfere bens no futuro; a
quebra só é registrada quando a venda incompatível realmente executa.

A regressão focal passou. Ao rodar os recortes conjuntos, o teste da
repudiação revelou 20 relatórios iniciais de assentamento com deltas sem
antecedente: eram observações do mundo recém-gerado antes de existirem receipts
dos owners. O produtor agora registra uma raiz explícita de
`world_generation/settlement_observation` somente nesse caso; observações com
histórico continuam citando as causas reais. O teste integrado de
save/load/auditoria passou depois da correção. Recorte conjunto de mercado,
abastecimento recíproco, repudiação e memória: `38 passed`. Ruff passou com
`E701` ignorado para as linhas compactas já existentes em `diplomacy_policy.py`;
`git diff --check` passou.

Ampliei a verificação de auditoria para a fixture de investimento de
assentamento: o único evento restante sem raiz era a presença inicial da
coluna criada pela própria fixture. Ela agora declara `scenario_bootstrap` com
referências ao cenário e ao grupo mobilizado, sem enfraquecer o audit nem
simular uma causa histórica. Em conjunto, causal audit, investimento de
assentamento, mercado, abastecimento recíproco, repudiação e memória: `44
passed`; Ruff focado e `git diff --check` passaram.

## Prazo de demanda da criatura e retaliação escolhida — 25/09/2026

O ciclo real de agenda revelava uma opção inalcançável: `creature_policy`
revisava a criatura no próprio `due_day`, mas `creature_options` e os executores
de dano/ataque só aceitavam demandas com `due_day < hoje`. A affordance
material surgia apenas no dia seguinte, para o qual não havia nova revisão
agendada. Alinhei enumeração, revalidação dos owners e contexto do ator para
`due_day <= hoje`; isso mantém o prazo como oportunidade de decidir, nunca como
gatilho automático.

Uma regressão percorre `MedievalSimulator` desde a percepção real do frete,
pedido e prazo até a escolha provider-stub de atacar uma coorte anônima no dia
do prazo. O evento cita a decisão e a demanda, contém delta de população e
expira a demanda; a rota permanece aberta. Na trajetória de dano a instalação
no mesmo prazo, a capacidade cai, o mantenedor recebe observação causal e uma
consulta provider-stub independente escolhe a affordance válida de reparo. A
Economy consome materiais e trabalho ao longo do ciclo, conclui a obra e
restaura a capacidade da rota. Esta fixture começa com os materiais locais de
reparo provisionados; não os cria como efeito da criatura. `tests/test_medieval_creature_autonomy.py`,
`tests/test_medieval_creatures.py` e
`tests/test_medieval_creature_magic_interaction.py` mais a regressão específica
do owner de infraestrutura: `24 passed`. Ruff nos arquivos de código/teste e
`git diff --check` passaram. Também foi corrigido um ciclo sem saída: restringir
a rota expirava a demanda e não agendava nova decisão, tornando o recuo
inalcançável no engine; agora há um único follow-up no dia seguinte, e a rota só
reabre se a criatura escolher `withdraw`. A fixture prova essa sequência, mas
usa decisões stub, não escolha espontânea nem provider OAuth real. Próximo:
compor resposta institucional explícita à exigência e continuar a auditoria de
autoria/efeitos, sem automatizar retaliação.

## Fechamento causal da trajetória criatura→reparo — 25/09/2026

O recorte final foi ampliado para salvar e auditar a mesma trajetória composta.
Isso encontrou seis eventos iniciais `subsistence_resolved` sem causa nomeada:
eram leituras materiais de subsistência do primeiro ciclo, antes de qualquer
receipt de owner, e não efeitos do dano/reparo. A Economy agora anexa uma raiz
`world_generation/initial_subsistence` apenas quando a leitura inicial tem
deltas e nenhuma causa canônica; preserva causas existentes e o payload
detalhado. Não transforma déficit posterior em premissa nem mascara eventos
sem origem.

Com a correção, a fixture completa salva/carrega e executa a auditoria causal
standalone, sem causa quebrada, autoria inválida, Story/interpretação material
ou transição sem raiz/link. A verificação focada conjunta de criatura, magia,
infraestrutura, consumo e validação dessa classe de raiz terminou com `43
passed`; Ruff focado e `git diff --check` também passaram. A trajetória de
reparo ainda começa com materiais provisionados explicitamente e usa decisões
provider-stub. Isso fecha uma composição causal de fixture, não a oferta natural
de materiais, resposta institucional à demanda, escolha OAuth atual ou gate
econômico natural de longo prazo.

Na sequência, a regressão do prazo passou também a exigir que a instituição
recusante registre `NO_ACTION` com autoria `ACTOR_DECISION` e link direto ao
aviso canônico da demanda que recebeu. A criatura então escolhe restrição no
prazo e retirada no dia seguinte; não há fechamento nem reabertura automática.
O teste focal passou (`1 passed`) e Ruff/diff-check passaram. Isso demonstra a
resposta explícita para a fixture com provider-stub, não interação com OAuth ou
uma resposta surgindo numa seed natural.

## Atomicidade da distribuição pública de alívio — 25/09/2026

A auditoria do owner de alívio achou uma falha transacional reproduzível: a
distribuição consumia estoque e atualizava o déficit/pantries antes de atualizar
as observações locais; se essa última etapa falhasse, o erro escapava deixando
evento e estado parcialmente aplicados. O owner agora trabalha em uma cópia
candidata e só publica o estado quando todas as etapas terminam. O teste injeta
falha no refresh e compara o snapshot integral, que permanece idêntico.
`tests/test_medieval_relief.py` e `tests/test_medieval_institutional_aid.py`
passaram juntos (`41 passed`); isso cobre atomicidade do ato de alívio e
regressões de aid/transferência, não o rollback global do mês. Próxima varredura
de autoria/atomicidade continua nos demais owners.

## Continuação natural da seed 14 até o dia 1.290 — 25/09/2026

Retomei o save do dia 1.260 em diretório isolado e avancei mais 30 dias com
`routine-rules`, sem provider, para observar a economia atual sem injetar
decisões. Conservação de recursos/dinheiro e equivalência save/load passaram.
O save final tem 51.897 eventos e 14.319.616 bytes; o auditor standalone
retornou `ok=true`, com 40.420 transições materiais e zero causas quebradas,
autoria inválida, Story/interpretação material, raiz ausente ou erro de fonte.
O checkpoint levou 21,63 s para salvar, o run 82,31 s e o pico RSS foi cerca de
904 MB; havia 8.056.180.736 bytes livres após o save.

A economia não recuperou: de 1.260 para 1.290, falta agregada foi de 530 para
691, saúde média de 318,62 para 302,62, unrest de 512,38 para 533,38 e mortes
por privação acumuladas de 162 para 180. O ledger do ciclo registrou falta
pré-alívio de 2.765 rações; fallback aplicou duas distribuições — 1.196 em
Pontenegro e 878 em Ferroalto — deixando 691 sem cobertura. Campomanso ainda
teve 428 não compradas apesar de 3.158 alimentos públicos e preço local 1.
Caixa agregado de 17.678 não representa poder de compra de todas as coortes:
uma coorte agricultora de 314 pessoas não tinha saldo, enquanto duas outras
coortes agricultoras concentravam 8.189 e 8.001. Há estoque local, mas ele não
é economicamente acessível a grupos sem saldo; o gargalo observado é caixa
desigualmente distribuído por conta/coorte e a política offline limitada, não
escassez agregada nesse assentamento. Isso é evidência de uma
trajetória fallback, não prova de como um provider reagiria. Não alterei
preços, renda, pooling de contas, emprego ou quantidade de alívio. Próximo
passo econômico: avaliar a decisão real entre opções com autorização vigente e
acompanhar as mesmas contas/coortes; manter aberta a revisão da mecânica até
esse diagnóstico distinguir autonomia insuficiente de regra material inadequada.

### Inventário causal do save de 1.290

A auditoria por tipo do mesmo save contabiliza 40.420 eventos materiais: 657
com origem `actor_decision` e 39.763 determinísticos (execução de owner, leis
físicas/econômicas e observações). As 153 transições sem evento-pai têm roots
válidas nos seis domínios `creature_habitat`, `household_income`,
`infrastructure_site`, `production`, `regional_hydrology` e `route`; não há
transição material sem link/root. Isso é inventário do que esta trajetória
emitiu, não valida semanticamente cada caminho possível nem fecha auditoria dos
owners ausentes do save.

## Validação semântica das referências raiz — 25/09/2026

O causal audit agora confirma que `source_refs` resolve para registros
canônicos de Economy, Society, Map ou CreatureState; `observer` resolve pela
identidade tipada e `scenario` só é válido em `scenario_bootstrap`. A regressão
aceita um estoque real e rejeita ID forjado. O save natural seed 14/dia 1.290
continua `ok=true`, com 153 roots válidas, zero inválidas, zero causa quebrada e
zero material sem link/root. Validação focada: 3 testes, Ruff e `git diff
--check` aprovados. Próxima etapa segue sendo auditoria semântica dos owners e
rollback além do owner de alívio; esta regra não valida caminhos que o save não
exercitou.

## Atomicidade da reativação de infraestrutura — 25/09/2026

O owner agora altera o Map, atualiza relatórios locais e valida Knowledge no
candidato transacional; publica tudo apenas após sucesso. Regressão injeta erro
depois do refresh e confirma snapshot inalterado. Infraestrutura: `23 passed`.
As falhas iniciais dos testes de barreira eram fixtures que não registravam
escolha do ator, raízes `scenario_bootstrap` e autoria de reparo. Depois de
alinhá-las ao contrato vigente, o recorte combinado passou `41` testes; Ruff e
`git diff --check` passaram. O alerta foi resolvido para esses caminhos; a
atomicidade transversal dos outros owners segue em aberto.

## Atomicidade na recuperação de frete — 25/09/2026

O owner agora executa a abertura do sucessor em `world.transaction_copy()`,
valida Economy e publica só após sucesso. A regressão força falha depois da
mutação candidata e confirma snapshot original idêntico. Recuperação de frete
+ causal audit: `15 passed`; Ruff e `git diff --check` passaram. Isso fecha mais
um executor material, não substitui a auditoria de rollback dos demais owners.

## Atomicidade da autorização de reparo — 25/09/2026

O executor compõe decisão de owner, projeto de reparo e objetivos de materiais
num candidato transacional, valida Economy/Strategy e publica só depois. A
regressão injeta falha após a criação dos objetivos e confirma snapshot
original intacto. Barreiras + infraestrutura: `25 passed`; Ruff e
`git diff --check` passaram. Atomicidade transversal e rollback mensal seguem
pendentes.

Integração posterior deste recorte: campanha/cerco, barreiras, infraestrutura,
recuperação de frete e causal audit — `60 passed`; Ruff e `git diff --check`
passaram. Ainda é validação focada, não suíte completa nem smoke de três seeds
por dez anos.

## Atomicidade do início de construção e expansão — 25/09/2026

Os owners iniciam projetos em candidato transacional; os adapters mantêm o
receipt de autorização junto do projeto no mesmo commit. Falhas injetadas depois
da criação do projeto preservam o snapshot original. Construção: `21 passed`;
expansão: `18 passed`; Ruff e `git diff --check` passaram. O progresso mensal
das obras e atomicidade dos demais owners permanecem fora desta fatia.

## Fundação de linha produtiva — 25/09/2026

O owner direto e o adapter de fundação agora também revalidam e registram a
decisão/projeto em candidato transacional antes de publicar. As regressões
injetam falha após a criação do projeto e confirmam snapshot intacto. O recorte
consolidado de construção, expansão e fundação passou `39` testes; Ruff e
`git diff --check` focados passaram. Próximos itens continuam sendo execução
mensal/rollback entre owners e o gate natural longo — não abrir outra vertical.

## Progresso mensal das obras — 25/09/2026

`progress_expansions` agora agrupa mutações de materiais, payroll, disponibilidade
de coortes e comissionamento de site em candidato transacional para chamadas
diretas; valida Economy e infraestrutura antes de publicar. Uma falha injetada
depois do payroll preserva o snapshot e o mapa de trabalhadores disponível. O
loop mensal do engine reaproveita o candidato que já possui, sem cópia aninhada.
Construção/expansão/fundação passaram `51` testes focados, Ruff e diff-check.
Próximo: continuar auditoria dos owners não cobertos e manter pendente o gate
natural 3 × 3.600 dias até o checkout estabilizar.

## Divulgação institucional de conhecimento — 25/09/2026

O executor de sighting tecnológico agora registra evento e fato em candidato,
valida Knowledge e publica os dois juntos. Uma falha injetada após o receipt
não deixa evento nem conhecimento parcial no mundo. Divulgação/venda/pesquisa
passaram `35` testes focados, Ruff e diff-check. É atomicidade de uma mutação
Knowledge com decisão atual; não valida outros owners, a árvore tecnológica ou
o gate longo.

## Compra agregada de provisões — 25/09/2026

O aceite do vendedor e a transferência doméstica agora são uma transação só:
decisões bilaterais recompostas, receipt, estoque público, pantry e saldos são
validados por Economy antes da publicação. Falhas injetadas após a emissão do
receipt não deixam autorização preparatória nem estado parcial. O caminho
fallback reaproveita a transação mensal externa. O módulo de provisões passou
`17` testes focados, Ruff e diff-check. Isso fortalece a economia das coortes,
mas não prova comércio generalizado, formação natural de recuperação ou
rollback dos demais owners.

## Serviço de rota e proveniência de fixtures — 25/09/2026

O owner de serviço de porto/passagem agora atualiza o Map e grava o receipt em
um candidato validado; falha depois da mutação do Map não publica nenhum dos
dois. Ao validar o cenário persistente de interferência, o auditor achou três
transições de fixture sem root (`rota fechada`, `ocupação`, `coluna de reforço`);
os testes agora declaram premissas `scenario_bootstrap` tipadas e resolvíveis.
A cadeia composta passou a auditoria; os recortes de campo, campanha e serviço
passaram `19` testes, Ruff e diff-check. Isso não muda a etiqueta da cadeia:
decisões/condições de campanha vêm de fixture, então a prova segue pressionada,
não natural.

## Revalidação econômica natural do checkout — seed 14, 480 dias — 25/09/2026

Rodei novamente desde o dia 0 no checkout atual, offline em `routine-rules`,
com dados e save isolados em `/tmp`. O mundo chegou ao dia 480 com 17.279
eventos; conservação, round-trip/continuação do save e auditoria causal
passaram. O auditor encontrou zero causas quebradas, decisões sem autoria,
roots inválidas/ausentes ou deltas de Story/interpretação. Não houve chamadas
reais de provider; isto não é evidência de escolha por IA. O teste focal de
folha/emprego passou `22` casos.

O resultado não foi economicamente resiliente: população 10.934, falta no ciclo
230, saúde média 888, unrest médio 102 e zero mortes por privação. A falta
física concentrou-se em Cinzaverde (163), Pontenegro (50) e assentamentos
menores; Pedraclara e Portovelho tinham `missing_food=0`, mas saúde 610/712 e
estimativas de 1.615/1.281 rações públicas inacessíveis ao saldo das coortes.
Ambos mantinham estoque público expressivo e preço 1. O relatório mostra
acesso/renda desigual, não falta agregada de produção.

No mesmo estado final, Auren e Valedouro ainda tinham uma affordance atual cada
para construir oficina em Pedraclara e Portovelho. A affordance não cria linha
produtiva ou emprego: ainda seria necessária decisão posterior de fundação e
execução material. `routine-rules` não escolheu essas obras; não atribuir essa
omissão a um provider. A trilha de construção existente e o contexto genérico
do dossier já expõem opções e leituras conhecidas, então esta medição não
justifica alterar preços, renda, empregos ou a política do owner. Próximo passo
econômico é uma consulta concorrente ao provider, se houver autorização
vigente, e rastreamento de sua decisão; em paralelo, manter o diagnóstico
transversal de autoria. O gate de três seeds × 3.600 dias continua pendente.

## Leitura pública de acesso alimentar — 25/09/2026

A projeção que o smoke usava para diferenciar estoque público de capacidade
doméstica de compra agora é compartilhada com o read model da API e o painel
Finanças. O Dao vê preço/estoque atuais, dinheiro por ocupação, estimativa de
rações públicas que os grupos disponíveis não cobririam e os receipts dos
componentes consultados. A UI identifica isso como projeção — não déficit
efetivo, renda, compra, nem conhecimento disponível aos NPCs — e permite abrir
os eventos dos componentes. Nenhuma regra material ou escolha de ator mudou.
API focada: 1 teste passou; Finanças: 5; smoke: 2; type-check/build passaram e
Ruff passou ignorando E402 preexistente em contracts.py. A economia continua
sem validação de decisão provider real ou recuperação longa.

**Proveniência da disponibilidade populacional — 25/09/2026:** a projeção
também usa `Society.available_count`, que desconta grupos em jornadas,
transições ocupacionais, destacamentos, protestos, movimentos e greves. Esses
receipts e o último evento de cada grupo local agora aparecem entre as fontes
consultáveis pelo Dao; continuam sendo componentes usados na estimativa, não
causal links inventados. Uma regressão com jornada migratória ativa verifica a
presença da fonte e que a consulta não altera o snapshot. O smoke focal passou
2 testes, a regressão de migração passou 1, e Ruff/diff-check passaram. Isso
melhora `why` da projeção pública;
não muda necessidade, consumo ou elegibilidade dos atores.
