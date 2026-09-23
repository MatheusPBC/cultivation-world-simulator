# Plano de correções e finalização — Medieval World Simulator

> Status em 21/09/2026: a fundação causal e várias verticais estreitas estão
> implementadas no WIP local; o roadmap amplo ainda não está finalizado. Este
> documento separa evidência existente de trabalho pendente.

## Objetivo

Concluir o fork medieval mantendo uma única cadeia causal:

```text
estado canônico → affordances → decisão do ator → owner revalida
→ execução material → fatos/deltas/links → conhecimento e memória
```

A IA interpreta o contexto e escolhe uma opção enumerada; ela não inventa
alvos, quantidades, autoridade, custos, efeitos ou causas.

## Leitura rápida do estado

| Área | Estado | Limite da evidência atual |
|---|---|---|
| Autoria causal e `Why` | Parcial forte | Guards e auditoria existem; falta varrer todos os owners. |
| Provider fail-closed | Parcial forte | Institucional e abastecimento de campanha cobertos; falta auditar toda decisão opcional/individual e provider remoto. |
| Economia | Parcial | Mercado, ajuda, emprego, workforce, rotas e reparação existem; a recuperação ainda deixa déficit material. |
| Diplomacia/commitments | Parcial forte | Propostas, multi-termo, breach, renegociação e reparação têm slices; intriga ampla falta. |
| Campanhas | Parcial | Forças, suprimento, cerco, cessar-fogo e controle revogável existem; campanha persistente e solução geral faltam. |
| Tecnologia | Parcial forte | Pesquisa, apprenticeship/difusão e uma cadeia industrial aplicada têm owners e regressão; difusão/defesa geral ainda faltam. |
| Magia/ecologia/criaturas | Parcial | Rito, hazard e drake têm owners; falta generalização. |
| Intriga/religião/Dao | Parcial | Movimento cívico e observabilidade existem; falta composição ampla de conhecimento e conflito. |
| Gates finais | Aberto | Provider real e três seeds naturais por dez anos ainda não foram validados. |

Uma fixture pressionada prova que uma cadeia pode ocorrer; não prova resiliência
geral. Testes focados verdes cobrem seus contratos, não uma onda inteira.
Estabilidade e `NO_ACTION` são resultados válidos no smoke natural.

## O que já foi corrigido neste checkpoint

- Autoria material central: transições `ACTOR_DECISION` exigem decisão-fonte;
  Story e interpretação não podem carregar deltas.
- Provider fail-closed: indisponibilidade, orçamento, ID inválido ou decisão
  stale pausam o mundo com rollback; não há fallback silencioso em modo IA.
- Revisões individuais: viagem de personagem, oferta/patrocínio de rito e
  consequência de vitória agora também pausam em modo IA quando uma affordance
  já agendada perde o provider; offline continua sem ação automática.
- Menu institucional composto: ajuda, mercado, emprego, workforce, migração,
  manutenção, diplomacia e reparação usam affordances revalidadas pelo owner.
- Movimento cívico: adesão independente, repressão com destacamento e provisão
  reais, anistia e receipts causais.
- Hazards e infraestrutura: overflow usa definição engine-owned, resistência e
  restauração material; a causa é navegável.
- Commitments: propostas, respostas, breach, renegociação e reparação de ajuda,
  pagamentos e transferências negociadas têm receipts e links causais.
- Leituras econômicas: a demanda pública de mercado agora é congelada depois de
  todos os custos engine-owned usados pela cotação, incluindo obras, pesquisa e
  reparos.
- Subsistência: o recibo publica `unaffordable_by_group`, tornando visível a
  diferença entre estoque público e poder de compra doméstico sem criar
  recursos ou subsídios.
- Emprego permanente: quando uma linha alimentar publica `labor_shortfall`, a
  engine não oferece um contrato que reserve agricultores para outro vínculo;
  a affordance de workforce continua sendo o caminho explícito para recompor a
  mão de obra.
- Relief material: a distribuição escolhida pelo owner agora sai do estoque
  público e entra em `household-stock:<group_id>` em cotas determinísticas por
  pessoas. O mesmo receipt registra deltas de estoque, `missing_food`, saúde,
  unrest e o payload de alocação; não existe redução de métrica sem destino
  físico.
- Dossier econômico: o contexto dos atores projeta, de forma agregada, a falta
  de poder de compra e o receipt que a mediu; saldos e IDs domésticos continuam
  fora do provider, e a métrica não executa nenhuma ação.
- Migração: o tick datado não chama mais a política determinística em modo IA;
  migração e recuperação passam pelo turno do próprio grupo, deixando o
  fallback apenas para offline/teste explícito.
- Campanha/observabilidade: cessar-fogo bilateral e cláusulas de retirada são
  projetados no observatório e na UI sem executar durante a leitura.
- Smoke econômico pressionado de 120 dias, auditoria causal e regressões focadas
  estão verdes. Isso é evidência de slices, não conclusão do roadmap.
- O smoke pressionado de 180 dias mostra recuperação parcial via workforce,
  mas mantém déficit material em três assentamentos; esse problema continua
  aberto para a Onda 1.

## Correções ainda necessárias antes do gate final

- [ ] Completar a auditoria de autoria em todos os owners restantes: cada delta
  deve ter decisão atual, `causal_payload`, owner, fontes e `Why` navegável.
- [ ] Remover qualquer caminho de fallback determinístico que ainda possa
  substituir uma consulta coberta em modo IA; fallback só pode ser política
  explícita de offline/teste.
- [ ] Garantir que commitments nunca executem sozinhos: prazo cria obrigação,
  mas estoque, rota, autoridade e decisão atual continuam necessários.
- [ ] Separar, nas projeções, fato histórico, estado atual reparado e memória
  institucional; nenhum resumo ou lembrança pode virar causa material.
- [ ] Fechar o contrato de save/load/rollback para agenda, RNG, decisões,
  commitments, memória, relações e auditoria sem persistir affordances.

### Correções operacionais detalhadas

1. **Auditoria de autoria:** cada delta precisa de decisão canônica atual,
   `actor_ref`, affordance/ação, parâmetros revalidados, owner, fontes e
   `causal_payload`; falhar antes do commit se qualquer vínculo faltar.
2. **Fail-closed uniforme:** em `ai_enabled=true`, indisponibilidade,
   orçamento excedido, resposta inválida ou affordance stale pausa e faz
   rollback. Escolha automática só existe em política explícita de
   `offline/test`.
3. **Obrigações passivas:** vencimento cria obrigação/affordance, nunca uma
   transferência automática. Cumprimento exige estoque, rota, autoridade,
   capacidade e decisão atual; reparação muda o estado atual sem apagar o
   breach histórico.
4. **Projeções separadas:** fato histórico, estado reparado, conhecimento e
   memória devem continuar distinguíveis; resumo ou prosa não pode virar causa.
5. **Save/load:** agenda, RNG, decisões, receipts, commitments, relações,
   memória, conhecimento e auditoria precisam sobreviver a save/load e rollback;
   affordances continuam transitórias e são recompostas.

**Evidência de encerramento desta seção:** auditoria final com
`broken_cause_ids=[]`, zero `ACTOR_DECISION` sem fonte e zero Story/LLM com
efeito material, além de teste de falha do provider sem mutação parcial.

## Ondas restantes do roadmap geral

### 1. Economia resiliente

Completar o ciclo preço/demanda/produção/estoque/renda/emprego, escassez com
efeitos materiais em saúde, unrest e migração, rotas alternativas, pedágio,
bloqueio, contrabando/detecção e recuperação de abastecimento. Toda solução
deve ser uma decisão atual e uma execução física; não criar comida nem distribuir
recursos automaticamente.

**Aceite:** uma rota interrompida reduz entrega e altera população; uma rota,
compra, contrato ou transferência alternativa pode recuperar o assentamento sem
evento roteirizado. Testar com fixture pressionada e seeds naturais.

**Próximo recorte:** explicar e reduzir o déficit alimentar dos assentamentos
limitados por mão de obra usando apenas affordances de produção, mercado,
workforce, rota e transferência existentes. Não criar comida, aumentar output
por script ou subsidiar automaticamente.

**Evidência atual:** no smoke pressionado de 180 dias, o déficit caiu de 4266
no dia 120 para 1195 no dia 180 após decisões de relief próprio, ofertas aceitas
de retorno à agricultura, workforce e uma expansão engine-owned concluída; as
fazendas passaram a recuperar trabalhadores, mas Ferroalto ainda encerra o
período com falta material. O estoque público não
é a mesma coisa que alimento acessível: famílias sem saldo não conseguem
comprar suas rações, e uma remessa/ajuda só existe quando uma instituição a
escolhe e a rota/estoque do owner permitem. A próxima implementação deve
instrumentar e testar esse gargalo, não escondê-lo com produção automática.

O horizonte de 360 dias confirmou a limitação: na seed 73, mesmo com as
decisões de relief e workforce existentes, o estado terminou com 3249 de
déficit agregado, zero mortes por privação, saúde média 633.38 e unrest médio
366.62. Isso é evidência para resolver renda, capacidade produtiva e rotas; não
é motivo para criar subsídio automático.

Uma correção adicional do owner de produção foi aplicada depois desse smoke:
quando vários grupos equivalentes podem preencher a mesma folha de pagamento,
a ordem de alocação agora é rotacionada de forma determinística por linha e
mês. Isso impede que a ordenação permanente por ID concentre todo o salário em
uma única coorte. A mudança não cria trabalhadores, dinheiro ou comida e foi
validada por 48 testes focados de economia, renda e emprego; o smoke de 360
dias ainda precisa ser repetido com essa versão antes de medir o efeito
agregado.

Também foi adicionada a affordance `granary-extension`: quando uma linha é
limitada por armazenamento, a instituição pode financiar uma expansão
engine-owned do estoque. O projeto consome madeira, pedra, ferramentas e
trabalho da ocupação declarada pelo blueprint ao longo de vários meses;
somente a conclusão aumenta a capacidade do estoque e publica o delta causal.
Para o celeiro, agricultores existentes podem construir a instalação, evitando
uma dependência circular de artesãos que não existem no assentamento. A opção
funciona em teste focado; a política de recuperação continua priorizando
socorro imediato e só considera a expansão depois de ajuda/mercado, sem
transformá-la em ação obrigatória.

Os recortes corretivos seguintes já foram aplicados: uma distribuição de
relief também recupera saúde e reduz unrest em proporção à comida realmente
entregue, limitada a 20 por ciclo, e uma demanda de workforce preserva seus
termos enquanto o mesmo receipt de produção/shortfall continuar vigente,
mesmo que outro owner altere a subsistência. Protestos fechados preservam sua
contagem histórica sem bloquear a posterior mudança de coorte. O smoke de 360
dias concluiu com saúde média 633.38, unrest 366.62 e déficit 3249, sem
mutação narrativa; isso fecha consequências e invariantes, mas não a
resiliência da produção, renda ou logística.

O recorte seguinte materializou o destino da ajuda: a mesma quantidade agora é
armazenada nas despensas domésticas canônicas e consumida na próxima resolução
mensal antes de qualquer compra. A regressão focada de economia/relief/consumo
(42 testes), a regressão institucional/persistência (37 testes), smoke de 180
dias e auditoria causal passaram. Isso corrige conservação e semântica da
ajuda, mas ainda não torna renda, produção e rotas sustentáveis em dez anos.

No smoke de 360 dias após essa mudança, a falta agregada caiu para `2208`, com
conservação, save/load e auditoria causal verdes. A melhora é evidência do
destino material correto da ajuda, não de equilíbrio econômico: ainda existem
  assentamentos com estoque público e famílias sem poder de compra, além de

Uma guarda adicional foi aplicada à própria oferta de transferência: o
`missing_food` atual do assentamento de origem agora é reservado junto das
reservas de subsistência, ordens e produção. Isso impede que uma decisão de
socorro elimine a falta do destino às custas de uma falta já conhecida na
origem. O recorte passou em 25 testes e em smoke/auditoria causal de 180 dias;
ele protege a validade local da ação, mas não resolve sozinho rotas, produção,
renda ou equilíbrio econômico de longo prazo.

Como parte da primeira correção de autoria, foi acrescentada uma regressão de
ledger para a fraude mais curta: uma transição `ACTOR_DECISION` com payload
apontando para uma decisão inexistente, mas ligada a uma ocorrência comum. A
validação rejeita o histórico antes do commit. Isso prova o guardrail do
ledger, não a auditoria completa de todos os owners.
linhas limitadas por folha, capacidade ou rotas.

Uma regressão adicional prova o fechamento do ciclo: no mês seguinte, as
rações em `household-stock:<group_id>` são consumidas antes de qualquer compra,
e o déficit residual coincide com a parte não distribuída. Isso reforça a
conservação material sem transformar relief em subsídio recorrente.

O release gate curto também permaneceu verde (`natural_ok`, `pressured_ok` e
`economic.ok` verdadeiros). As políticas de alívio, desatenção, mercado e
mobilidade produziram déficits distintos (`312`, `18830`, `18600` e `15410`),
confirmando que decisões de affordance mudam o resultado material sem uma cota
de drama ou fallback narrativo.

O recorte seguinte fechou uma falha de capacidade financeira das affordances de
emprego permanente: antes de enumerar outro vínculo recorrente, o owner soma as
folhas mensais dos contratos já aceitos pelo mesmo empregador e exige que o
primeiro payroll do candidato caiba no saldo atual. Isso evita que uma decisão
nova consuma o caixa que uma linha produtiva já precisa, sem transformar
contratos em crédito, cancelar obrigações existentes ou inventar receita. A
regressão focada teve 49 testes e o smoke de 360 dias permaneceu causalmente
limpo (`ok=true`), mas o déficit final continuou 2208; portanto o recorte é uma
guarda de sobrecompromisso, não a conclusão da resiliência econômica.

Depois, a ordem de execução das linhas produtivas que compartilham uma conta de
payroll passou a girar de forma determinística por mês. Antes, a ordenação por
ID fazia a primeira linha consumir o caixa compartilhado repetidamente, mesmo
quando outra linha tinha estoque, trabalhadores e demanda válidos. O recorte
mantém os owners e limites de cada produção, mas distribui a oportunidade de
folha entre linhas equivalentes. A regressão teve 50 testes e o smoke de 360
dias reduziu a falta agregada de `2208` para `2174`, com conservação/save-load e
auditoria causal verdes. Isso é uma melhora material pequena; não encerra a
resiliência de renda, produção ou logística.

### 2. Agência institucional e diplomacia

Completar objetivos/planos verificáveis, barganha bilateral, recusas, influência,
espionagem, suborno, sabotagem, acusação, traição e commitments multi-termo.
Integrar conhecimento privado, autoridade concorrente e memória com saliência;
nenhuma culpa, guerra ou retaliação pode surgir apenas da prosa.

**Aceite:** uma concessão ou quebra deliberada nasce de decisões independentes,
tem execução/recibo e altera decisões futuras; reparação resolve o estado atual
sem apagar o breach histórico.

**Dependência:** recursos, capacidade, conhecimento e rotas da Onda 1 precisam
estar disponíveis para que barganha e traição não sejam apenas texto.

### 3. Tecnologia aplicada

Completar pelo menos uma cadeia de ponta a ponta:
`descoberta → conhecimento → ensino/venda/roubo/migração → instalação
→ operador → manutenção → produção/defesa/campanha`.

**Aceite:** a técnica muda um resultado material observável; conhecimento sem
instalação, operador, equipamento ou manutenção não produz efeito.

**Recorte mínimo:** instalar uma técnica já existente, designar operador,
consumir materiais, produzir um output observável e perder esse output quando
manutenção ou suprimento falhar.

**Evidência atual:** a cadeia industrial de Ferroalto já cobre conhecimento,
construção de linha, consumo de madeira/ferramentas/máquinas, produção de
carvão/aço/motores, manutenção de insumos e save/load; 40 testes focados
passaram. Isso fecha apenas a primeira cadeia aplicada: venda/roubo/migração de
técnica, defesa e difusão ampla continuam pendentes.

### 4. Campanhas e controle territorial

Generalizar força agregada, recrutamento, comando, reconhecimento, doutrina,
suprimento, posições, combate, retirada, cerco, interdição, ocupação revogável,
guarnição persistente e solução política. Controle exige capacidade e logística
atuais; cessar-fogo ou concessão aceita não executa automaticamente.

**Aceite:** mudar terreno, informação, moral, fadiga, comando ou suprimento muda
o resultado e a explicação causal; ocupação sem guarnição não é controle
duradouro.

**Recorte mínimo:** persistir uma campanha por vários turnos com suprimento,
posição e objetivo; retirada, cessar-fogo ou solução política não podem resolver
o conflito por texto.

### 5. Magia, ecologia e criaturas

Registrar escolas, rituais, custos, alcance, duração, recuperação, resistências e
contramedidas em definições engine-owned. Criaturas devem possuir habitat,
necessidades, memória e affordances próprias; ataques, tributos e recuos exigem
condições e decisões, não spawn ou catástrofe obrigatórios.

**Aceite:** uma ameaça ritual ou criatura altera instalação, pessoas ou decisões
posteriores por uma cadeia material investigável.

**Recorte mínimo:** registrar mais de um tipo de hazard/rito/criatura com custo,
resistência, habitat e owner de resposta, sem spawn ou catástrofe obrigatórios.

### 6. Intriga, religião e observabilidade do Dao

Completar perseguição, organização, liderança, protesto/revolta, religião e
conflitos institucionais como composições de pressão, conhecimento, autoridade,
recursos e decisões. Finalizar dossier multi-salto e UI PT-BR para navegar
`resultado → evento → decisão → owner → evidências`; o Dao vê a verdade completa,
atores veem apenas conhecimento recebido.

**Aceite:** cada fixture mostra causas e perspectivas corretas sem transformar
prosa em mutação; uma desordem espontânea não vira rebelião sem organização e
liderança.

**Recorte mínimo:** uma investigação produz evidência privada; uma instituição
pode acusar, perseguir, negociar ou recuar; protesto, tumulto e rebelião seguem
estados distintos e exigem seus pré-requisitos materiais.

## Ordem operacional por checkpoint

1. Fechar as cinco correções de autoria, fail-closed, obligations, projeções e
   persistência.
2. Resolver uma causa concreta do déficit econômico e repetir a fixture sem
   criar recursos.
3. Completar uma negociação multi-termo com resposta independente e reparação.
4. Entregar uma cadeia tecnológica aplicada ponta a ponta.
5. Persistir campanha e solução política em vários turnos.
6. Generalizar uma vertical de magia/ecologia/criatura.
7. Fechar intriga/religião e dossier multi-salto do Dao.
8. Executar gates longos, provider real, frontend e handoff final.

Cada checkpoint registra arquivos, ownership, testes, limitações e auditoria.
Não abrir a próxima onda apenas porque uma fixture isolada passou.

Ao concluir cada checkpoint, o andamento deve ser comunicado em quatro linhas:

1. **Concluído:** mudanças efetivamente implementadas, com arquivos e owners.
2. **Evidência:** testes, auditorias e smoke executados, incluindo falhas ou
   verificações ainda não feitas.
3. **Limites:** o que a evidência não prova e quais caminhos continuam sem
   cobertura.
4. **Próximo passo:** a menor tarefa causal que fecha a próxima pendência.

Um checkpoint não significa que o roadmap geral terminou. Só as ondas com
aceite e evidência publicados podem ser marcadas como concluídas; as demais
continuam explicitamente abertas.

## Gate de conclusão

O recorte de 120 dias para a seed 73 já passou como checkpoint operacional
(natural/pressured/economic). Ele valida conservação, save/load, auditoria e
seleção de affordances nas fixtures existentes, mas não substitui os horizontes
de dez anos nem a resiliência econômica exigida abaixo.

- [ ] Regressões focadas de cada onda, `compileall`, `git diff --check`, type-check
  e testes web medievais.
- [ ] Fixtures pressionadas para economia, diplomacia, campanha, intriga,
  tecnologia e ecologia, cada uma com cadeia multietapas material.
- [ ] Três seeds naturais por dez anos: estabilidade é válida; comparar
  save/load, agenda, RNG, conservação, rollback, latência e custo de IA.
- [ ] Provider real validado separadamente; erro não pode publicar mutação parcial.
- [ ] Auditoria final com `broken_cause_ids=[]`, zero transições de decisão sem
  fonte e zero Story/LLM com efeito material.
- [ ] Só então marcar as ondas como concluídas e atualizar handoff/roadmap.

O gate tem dois cenários diferentes:

- **Natural smoke:** três seeds por dez anos; estabilidade é válida e nenhuma
  cadeia dramática é obrigatória. Comparar save/load, agenda, RNG, conservação,
  rollback, latência e custo de IA.
- **Pressured smoke:** fixtures deliberadamente tensionadas para economia,
  diplomacia, campanha, intriga, tecnologia e ecologia; cada uma deve produzir
  ao menos uma cadeia material multietapas.

Um mundo natural sem crise não é falha. Uma fixture pressionada sem cadeia é
falha de cobertura ou de causalidade.

## Dependências e fora do escopo

Ordem: correções de autoria → economia/agência → tecnologia → campanhas →
magia/ecologia → intriga/observabilidade → gates finais. Não criar planner
paralelo, DSL mecânica nova, compatibilidade para saves antigos, tesouro
imperial separado ou eventos narrativos aleatórios que alterem a realidade.

O owner de folha também foi corrigido: o imposto de renda agora é calculado
sobre o bruto agregado antes do arredondamento e o resto é distribuído de forma
determinística entre as contas domésticas. O caso de salários pequenos em
coortes diferentes deixou de perder imposto por truncamento independente. A
mudança mantém conservação e não cria dinheiro, mas é somente uma correção de
contabilidade; a renda estrutural e a resiliência econômica continuam abertas.

No review provider de ajuda, a ausência de affordance foi separada de uma
consulta que termina em `NO_ACTION`. Isso impede que o mesmo ator seja
consultado novamente por fulfillment, remediação ou request no mesmo turno e
mantém a decisão única sobre as opções concorrentes. O contrato foi validado
com provider falso; a sondagem de provider real continua pendente.

O gate de fixture pressionada também foi exercitado em `seed=73`, perfil
`recuperacao`, por 120 dias. O teste exige uma cadeia material multietapas
(mercado, emprego, workforce e relief), conservação, save/load e auditoria
causal limpa, mas aceita que a pressão permaneça (`missing_food=148`). Ele
serve para provar que a vertical usa owners e affordances existentes; não
substitui os smokes naturais de dez anos, provider real ou as fixtures de
outros domínios.

No limite transacional do engine, um receipt
`institutional_decision_stale_affordance` produzido durante uma consulta de IA
agora aborta o candidato quando a IA está habilitada. A chamada unitária ainda
permite observar o receipt sem mutação, mas a simulação não publica decisões,
calendário ou deltas de famílias posteriores de um mês parcialmente
processado. O teste de rollback passou junto com 26 regressões de
engine/provider/AI; falhas de owners diários e provider real continuam sendo
itens separados do gate fail-closed.

As fixtures do recourse diário foram alinhadas a esse contrato: a preparação
configura um provider falso, e os casos de indisponibilidade agora esperam a
pausa `ProviderDecisionRequired` sem publicar receipt de falha ou escolha
determinística. A regressão composta de engine, AI, menu mensal e turno diário
passou em 34 testes. Isso corrige a prova do contrato; provider remoto e todos
os owners diários ainda precisam de sondagem própria.

O abastecimento de campanha foi alinhado ao mesmo limite: se a opção escolhida
fica stale ou o owner rejeita os termos atuais, o review propaga
`ProviderDecisionRequired` em modo IA. Não há frete aberto pelo caminho direto;
no engine, a transação isolada descarta o candidato. A regressão específica
passou em 5 testes, mas contato armado, aftermath e resposta estratégica ainda
contêm recortes separados a auditar.
