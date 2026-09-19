# Plano restante do roadmap medieval

Atualizado em 19/09/2026. Este documento é uma fila de execução; não declara o
roadmap concluído. O estado canônico e o histórico detalhado continuam em
`docs/handoff/medieval-current-state.md` e
`medieval-roadmap-completion-plan.md`.

## Atualização de planejamento — horizonte longo

Uma tentativa natural de 3.600 dias com a seed `73` havia caído no quinto mês
em `research_policy._apply_known_techniques`, quando uma técnica conhecida
tentou iniciar uma expansão em um site sem as capacidades authored exigidas.
O fallback agora aplica a mesma pré-condição de `expansion_options`; uma
regressão específica impede projeto incompatível e a matriz focada de pesquisa
e expansão passou em 33 testes. A execução causal de 360 dias com os perfis
natural, `socorro`, `desatento`, `alivio`, `mercado` e `mobilidade` concluiu
com conservação, `save_load_equivalent` e auditoria limpa (`ok=true` no gate
curto). O horizonte de dez anos ainda precisa ser repetido; a pressão
econômica observada continua uma lacuna, não um motivo para inventar
distribuição automática.

### Fila prioritária consolidada

1. Corrigir o bloqueio de aplicação de tecnologia e provar rollback/ausência de
   mutação parcial.
2. Fechar a prova operacional do provider real (decisão, `NO_ACTION`, erro,
   orçamento e affordance stale); sem credencial, registrar bloqueio explícito.
3. Tornar a economia resiliente: renda/emprego, alternativas de abastecimento,
   rota interrompida, saúde, unrest e migração precisam produzir trajetórias
   materiais diferentes sem distribuição automática.
4. Completar agência institucional e social: memória estratégica utilizável,
   compromissos sociais, acusação/evidência, persuasão ampla e reparação além
   de pagamento.
5. Fechar campanha persistente e solução política pós-ocupação, incluindo
   manutenção fora do cerco, cessar-fogo e cumprimento bilateral.
6. Generalizar magia/ecologia/criaturas para mais habitats e leis authored,
   mantendo exposição, resistência, custo, recuperação e ausência de spawn
   obrigatório como invariantes.
7. Completar observabilidade e UI PT-BR: dossier multi-salto, mapa de rotas,
   forças, controle, ameaças e planos, navegando até decisão/owner/evidência.
8. Executar o gate final: regressões focadas, três seeds naturais por dez anos,
   fixtures pressionadas, auditoria causal/conservação/rollback/save-load e
   custo de IA.

## Leitura correta do estado

Desde o último recorte, o fallback offline/test de workforce pode aceitar uma
transição ocupacional enumerada sob pressão observada e falta de mão de obra.
O owner recompõe e valida os termos; não há conversão automática de estoque em
consumo. O gate de 120 dias da seed 73 com perfis `desatento`, `alivio`,
`mercado` e `mobilidade` passou com conservação, save/load equivalente e
auditoria causal limpa, mas a resiliência de longo prazo permanece aberta.

### Correção de prioridade de mobilidade — 19/09/2026

O fallback offline de workforce agora compara corretamente a ocupação alvo da
affordance com a prioridade derivada da pressão observada. Quando há falta de
comida, uma oferta enumerada de retorno à agricultura vence ofertas de outras
ocupações; fora desse caso, a ordenação anterior para trabalho artesanal ou
mercantil é preservada. Antes, a comparação usava uma tupla aninhada e nunca
reconhecia `farmer` como prioridade, permitindo uma escolha materialmente
inadequada sem inventar nenhuma affordance. A regressão focada de workforce e
emprego passou em 38 testes; o gate curto de 120 dias preservou conservação de
dinheiro/recursos e save/load. Isso corrige uma decisão de mobilidade, mas não
fecha a resiliência econômica de longo prazo nem o gate de dez anos.

O mesmo critério foi aplicado ao fallback de emprego permanente: dentro da
mesma pressão observada, uma affordance de ocupação `farmer` é preferida a
outra ocupação. A escolha continua limitada às ofertas atuais e o owner ainda
revalida autoridade, site, coorte e saldo; a regressão conjunta de emprego,
workforce e smoke passou em 45 testes. Isso melhora a recuperação possível sem
transformar emprego em renda automática.

Já existem fatias causais para contratos e memória institucional, decisões
cívicas, alfândega, pesquisa, expansão, emprego/workforce, provisionamento,
migração, recuperação de frete/compra, cerco, guarnição, controle territorial,
apprenticeship, roubo/venda de tecnologia, ritos de restauração/proteção, duas
criaturas do Rio Lume, protesto/greve/tumulto e observabilidade inicial.
Regressões focadas, `compileall` e `git diff --check` foram usados nesses
recortes.

Isso ainda não prova provider remoto, economia resiliente, campanha completa,
magia geral, ecologia geral, intriga/religião completa nem o gate de dez anos.

Na fronteira do menu institucional, abastecimento e compra de mercado agora
compartilham um fragmento de situação público e datado: relatórios próprios de
assentamento, identidade pública de recurso, rotas conhecidas e cotações
públicas datadas. Os rótulos e o contexto não expõem objetivo, estoque, conta,
folha ou quantidade; o owner continua recompondo esses termos antes da execução. Isso melhora a
decisão econômica sem transformar alternativas enumeradas em prova de
resiliência.
Quando há várias ofertas, o fragmento também identifica o índice da escolha,
a origem pública e a cotação datada; o montante executável continua privado e
é recalculado pelo owner.

Nota operacional: uma tentativa de 3.600 dias com a seed 73 foi interrompida
no mês 6 após aproximadamente 69 segundos de execução. O trecho não reportou
crash nem causa quebrada; o horizonte de dez anos permanece pendente por custo
de execução, não por aprovação ou reprovação do sistema.

O clone transacional agora compartilha o prefixo de eventos append-only,
isola o runtime mutável do mapa (rotas, sites, interdições e fila de updates) e
mantém registries/agenda/RNG isolados. O perfil de 18 passos melhorou de 14,5 s
para 11,4 s; após o clone do mapa, três passos caíram para 3,1 s no perfil
curto. Uma execução natural de 120 dias com seed 73 terminou com
`ok=true`, `broken_cause_ids=[]`, `story_material_events=[]`, conservação de
dinheiro/recursos e `save_load_equivalent=true`. O gate de três seeds por dez
anos continua pendente.

IDs internos que atravessavam o menu composto também foram corrigidos na
fronteira de provider: handles com estoque, tesouro, conta, folha ou pantry
agora chegam como tokens opacos, enquanto o owner remapeia e revalida o ID
canônico. A capacidade estratégica no dossier usa status/contagens, sem IDs de
registros privados. Regressão focada de IA/recourse/dossier/estratégia/diplomacia:
32 testes.

Procurement agora mantém cada rota fiscal conhecida como affordance distinta:
o fallback mensal ainda ordena e escolhe deterministicamente, mas a decisão
institucional pode selecionar uma alternativa de caminho. O owner recompõe a
rota para a quantidade atual e revalida todos os termos antes de abrir a carga.
Os rótulos mostram a rota pública, mas o provider continua respondendo apenas
com o ID da affordance. Procurement, roteamento, escassez, ajuda e recuperação
passaram em 56 testes focados.

## Princípios

- O estado canônico gera fatos e affordances; o ator escolhe uma affordance ou
  `NO_ACTION`; o owner revalida e executa.
- LLM, Story e prosa não criam quantidade, custo, alvo, recurso ou mutação.
- Não criar planner, catálogo, estado persistido ou sistema de validação
  paralelo.
- Uma vertical só é considerada entregue quando houver executor material,
  causalidade navegável, save/load e regressão focada.

## Ordem de execução

### 1. Provider remoto e prova operacional

- Executar uma sondagem pequena com provider real para: decisão válida,
  `NO_ACTION`, orçamento excedido, indisponibilidade e affordance stale.
- Registrar custo, latência, erro e comportamento fail-closed; nenhum erro pode
  deixar mutação parcial.
- Verificar rollback, save/load, agenda e RNG em uma execução abortada.

Aceite: cada falha deixa receipt auditável e nenhum estado inválido; sem
provider configurado, o harness falha explicitamente e não usa fallback como
prova de autonomia geral.

### 2. Agência institucional e memória social

- Completar objetivos/planos persistentes dentro da consulta mensal existente,
  sem segundo planner.
- Expandir compromissos sociais: persuasão, violação deliberada, acusação,
  descoberta por evidência e reparação sem apagar o breach histórico.
- Fazer memória estratégica entrar em decisões futuras somente quando o ator
  possui conhecimento e fatos canônicos correspondentes.

Aceite: duas instituições tomam decisões independentes, e cada mudança de
obrigação/relação aponta para decisão, owner e fatos-fonte.

### 3. Economia, subsistência e mobilidade resilientes

- Fechar renda/emprego recorrente das coortes e seus limites de autoridade,
  estoque, folha e capacidade.
- Demonstrar escassez afetando saúde, descontentamento e migração sem resolver
  a condição automaticamente; o fallback offline de emprego já existe, mas
  não é prova de resiliência econômica.
- Completar pedágio, trânsito, bloqueio, contrabando, detecção, apreensão e
  retorno por affordances explícitas.
- Adicionar alternativas de abastecimento/recuperação apenas como opções
  materiais enumeradas; nenhuma distribuição automática.

Aceite: rota interrompida, rota alternativa e recuperação produzem estoques,
população, saúde e pressão social diferentes, todos auditáveis.

### 4. Tecnologia e produção

- Ampliar a árvore além das técnicas militares já existentes.
- Implementar pelo menos uma cadeia completa: descoberta → produção →
  treinamento → instalação/operação → manutenção.
- Ligar o resultado a comércio, defesa ou campanha, sempre com autoridade,
  suprimento e operador válidos.

Aceite: conhecimento isolado não muda o mundo; a instalação material muda uma
leitura canônica e produz efeito limitado e reversível quando aplicável.

### 5. Campanha e solução política

- Generalizar manutenção, rotação/queda de guarnição, combate, cerco,
  ocupação e controle territorial para campanhas persistentes.
- A retirada voluntária de um cerco agora é uma affordance da própria campanha:
  o owner encerra as interdições e suprimento pendente da sua coluna e inicia
  uma marcha física, sem transferir ocupação ou administração.
- Cessar-fogo bilateral de cerco agora reutiliza o `DiplomaticProposal` e cria
  uma obrigação `campaign_withdrawal` por coluna; cada owner aceita/recusa e
  cumpre a própria retirada material.
- Completar administração pós-ocupação, manutenção ampla e campanhas
  prolongadas com termos executáveis, aceitação independente e cumprimento
  material, reutilizando commitments e owners existentes.

Aceite: ocupação sem guarnição/abastecimento não vira controle duradouro; uma
solução política só muda estado após aceitação e execução material.

### 6. Magia, ecologia e criaturas

- Generalizar hazards/ritos para escolas engine-owned com custo, alcance,
  duração, resistência e contramedida.
- Adicionar mais de uma criatura/território com habitat, necessidades,
  memória, negociação e ataque material.
- Evitar spawn ou catástrofe obrigatórios; cada impacto exige exposição e
  definição canônica.

Aceite: efeitos têm alvo, resistência, recuperação e evidência física
revalidáveis; nenhuma criatura altera o mundo por narrativa.

### 7. Intriga, religião e observabilidade do jogador

- Completar perseguição religiosa, conspiração e persuasão ampla somente com
  pressão, organização, liderança, conhecimento e ação material.
- Completar dossier multi-salto, mapa de controle/rotas/forças/ameaças/planos e
  perspectivas privadas na UI PT-BR.
- Manter o Dao onisciente, mas filtrar cada ator pelo próprio conhecimento.

Aceite: o jogador navega do resultado ao evento, decisão, owner e evidências;
nenhuma acusação ou plano privado aparece como causa material sem fato-fonte.

### 8. Gate final de release

- Rodar regressões focadas por onda.
- Rodar três seeds naturais por dez anos: estabilidade é resultado válido.
- Rodar fixtures pressionadas para exigir cadeia multietapas institucional,
  econômica e de campanha.
- Auditar causalidade, conservação de dinheiro/recursos, rollback,
  agenda/RNG, save/load, materialidade de Story e custo de IA.

Aceite: zero causas quebradas, zero deltas originados em Story/LLM, nenhuma
mutação parcial e equivalência de save/load. A cadeia multietapas é obrigatória
somente nas fixtures pressionadas.

## Dependências

1. A onda 1 é pré-requisito operacional para todas as demais.
2. A onda 2 precede a expansão social, intriga e solução política.
3. As ondas 3 e 4 podem avançar em paralelo após a onda 2.
4. As ondas 5 e 6 dependem dos owners materiais das ondas 2–4.
5. A onda 7 depende dos contratos e projeções estabilizados.
6. A onda 8 é sempre a última.

## Próximo passo recomendado

Depois das regressões locais já concluídas para workforce e migração, avançar
na onda 3: escolher uma cadeia de oferta alternativa e fazê-la atravessar
owner, estoque, saúde e pressão social. Se um provider remoto estiver
disponível, executar a onda 1 antes de usar qualquer resultado de IA como
evidência.

## Fora do escopo desta fila

Não criar compatibilidade com contratos antigos, migração automática de saves,
DSL mecânica nova, tesouro imperial separado, logística profunda ou eventos
narrativos aleatórios que alterem a realidade. Não declarar o roadmap inteiro
concluído a partir de uma regressão focada ou de um smoke curto.

## Evidência mais recente da onda 3

O menu civil composto agora registra `relief_adapters()` junto das demais
famílias. Quando o estoque pertence à instituição, o relatório de escassez é
atual e existe autoridade de `supply`, `relief-distribute:*` aparece como uma
affordance real no mesmo turno que pedido, cumprimento de ajuda e
abastecimento; a distribuição continua uma decisão explícita, sem fallback.
Os testes focados de menu/relief passaram (44 testes), e o smoke de 120 dias
com seed 73 confirmou conservação de recursos e save/load equivalentes. Na
fixture `socorro`, `relief_given_total` permaneceu zero porque o decisor de
teste prioriza pedidos/cumprimentos de ajuda em toda fronteira mensal; isso é
limitação da política de medição, não ausência da affordance. A economia
resiliente ainda não está fechada: a comparação pressionada precisa continuar
medindo alternativas de oferta, escassez, saúde e pressão social.
Essa comparação agora existe no harness como perfil `alivio`, que prioriza
somente IDs `relief-distribute:*` já enumerados; a regressão passou e a execução
`seed=73`, 120 dias, registrou 9 distribuições materiais. O resultado também
mostra por que a onda continua aberta: distribuir reduz o déficit daquele
relatório, mas consome o estoque público e, nesta fixture, terminou com
`missing_food=6216`, saúde média `879,62` e unrest médio `120,38`, contra
`6128`, `880,50` e `119,50` sem essa política. Isso é evidência de trade-off
material, não uma vitória automática de resiliência; ainda faltam alternativas
de oferta e uma política que as compare.
O release gate opcional `--economic` registra essa comparação em
`/tmp/cws-gate-economic/report.json`, com `relief_selected=true`,
`different_material_outcome=true` e `ok=true`.

O gate econômico agora compara quatro políticas explícitas na mesma seed:
`desatento`, `alivio`, `mercado` e `mobilidade`. Em 120 dias com seed 73, as
quatro execuções conservaram dinheiro/recursos e save/load; alívio registrou
distribuição, mercado registrou compras bilaterais e mobilidade registrou
empregos/transições. O relatório terminou com
`relief_selected=true`, `market_selected=true`, `mobility_selected=true`,
`different_material_outcome=true` e `ok=true`. Isso prova que alternativas
enumeradas produzem trajetórias diferentes; não prova ainda recuperação
econômica de longo prazo nem o gate de dez anos.

Após o isolamento do runtime do mapa e a normalização da igualdade de eventos,
a matriz de 120 dias com `--pressured --economic` também passou novamente:
`ok=true`, `natural_ok=true`, `pressured_ok=true`, conservação de recursos,
`relief_selected=true` e `different_material_outcome=true`. Isso continua
sendo um gate curto; não fecha a resiliência econômica nem o horizonte de dez
anos.
O gate agora também envia logs de progresso para `stderr`, deixando `stdout`
como um relatório JSON parseável; a execução curta de seed 73 foi validada
carregando o arquivo diretamente com `json.load`.

### Atualização operacional seguinte

Ofertas de mercado bilaterais passaram a compor o turno institucional como
`market-purchase:*`, concorrendo com `supply-objective:*` para o mesmo objetivo.
O executor existente continua responsável por revalidar cotação, rota, tarifa,
saldo, autoridade e resposta do vendedor antes de criar frete. A decisão só
persiste o ID da affordance; os causal links usam o evento do relatório de
oferta e as observações de rota, nunca o ID transitório do relatório. A
regressão civil focada passou em 18 testes. Isso fecha a entrada da alternativa
de oferta no menu, mas não fecha a resiliência econômica nem o gate prolongado.

O harness ganhou ainda o perfil determinístico `mercado`, que escolhe somente
IDs `market-purchase:*` enumerados. A execução `seed=73`, 120 dias, terminou
com 9 compras/vendas bilaterais, 9 ordens físicas, conservação de dinheiro e
recursos e `save_load_equivalent=true`; o resultado material permaneceu
auditável (`missing_food=6128`, saúde média `880,5`, unrest médio `119,5`).
Isso prova que a alternativa foi usada, não que ela resolve a escassez: o
cenário ainda termina pressionado e precisa de uma política de oferta mais
abrangente.

### Provisão domiciliar bilateral

O fluxo de household provisioning agora participa do turno institucional em
provider mode. A coorte seleciona uma oferta pública local enumerada; o
proprietário recebe uma opção independente de aceitar ou recusar em turno
posterior. O owner só executa a transferência depois do aceite, revalidando
oferta, estoque, reserva, preço, saldo, capacidade da despensa e autoridade.
O teste focado passou em 11 casos e a regressão de agenda/engine/migração em 24.
O fallback determinístico não foi alterado para o modo offline. A política
econômica de longo prazo e o gate de dez anos seguem abertos.

### Dossier estratégico compartilhado

O dossier comum entregue ao provider agora inclui `known_institutional_views`
derivadas de fatos conhecidos e `strategic_capacity` derivada de objetivos,
planos e registros dos owners. A memória não é copiada como verdade global nem
cria score/planner persistente; apenas torna o contexto social já conhecido
disponível para todas as affordances do turno composto. A regressão focada
passou em 29 testes.

### Campanha pós-brecha no turno único

O menu composto de campanha agora inclui também ocupação material após brecha
e estabelecimento/retirada explícita de controle territorial. Os executors
continuam separados e revalidam campanha, relatório, guarnição e autoridade;
nenhuma administração é transferida por seleção de menu. A concessão bilateral
agora também é uma opção de oferta, resposta e cumprimento nesse mesmo menu.
A regressão focada passou em 38 testes.

### Ecologia ligada à capacidade da rota

O ciclo engine-owned de criaturas passou a considerar degradação parcial da
capacidade operacional da rota (qualidade ou dependência física), preservando
o mesmo pipeline de evidência e decisão posterior. O payload distingue rotas
fechadas de rotas apenas prejudicadas; nenhuma catástrofe ou demanda nasce do
tick. O teste de criatura/magia passou em 8 casos.

### Observabilidade do habitat

O observatório/Atlas agora torna navegável o estresse ecológico derivado de
rotas parcialmente degradadas, sem duplicar estado de ameaça: a projeção lê o
payload do tick e aponta para o evento-fonte. A regressão backend passou em 19
testes e a suíte medieval frontend em 65.
