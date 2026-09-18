# Plano: fome com consequência política

Plano completo e final desta frente. Substitui a versão anterior (que pedia
diagnóstico da Frente C — já executado, resultados incorporados abaixo).

## O problema, em uma frase

O motor sabe passar fome, mas não sabe reagir à fome. As consequências materiais
funcionam — comida acaba, saúde cai, gente morre. As políticas — ajudar,
revoltar, pedir socorro — ou são automáticas demais, ou estão trancadas atrás de
condições que a fome sozinha não abre.

## Restrição de arquitetura (do usuário, literal)

> "a ajuda tem q ser uma consequencia... eles podem ignorar tambvem, dai isso
> gerar ate mesmo uma revolta na populacao. Porem tudo isso é uma cadeia de
> acontecimentos, A IA decide oq vai acontecer, e oq acontece é persistido com
> as ferramentas q oferecemos."

Ajuda não é configuração, não é default, não é rotina determinística. É um ato
escolhido por quem governa, com causa datada e consequência persistida.

## O que já foi medido (não repetir)

- 12 meses, seed 73, três perfis. OMISSO termina com saúde 0, revolta 1000, 482
  mortes por privação. Logs em `.tmp-relief-measurements/behavior-*-73.log`.
- **Protestos abertos: 0 nos três cenários**, mesmo com 32 opções de protesto
  disponíveis no mês 3. Abrir exige provider; o smoke roda sem IA.
- O menu real de um governante faminto só oferece `relief-rate:...:0` e
  `relief-rate:...:500`. Não existe opção de ajudar.
- Migração **não está quebrada**: com fome assimétrica, 28 destinos passam em
  todos os portões e travam só em comida própria zero (`migration_policy.py:117`).
  Com rações nas despensas: 28 opções, 4 migrações, 396 pessoas. **Fora do
  escopo deste plano** — é decisão de produto pendente do usuário.
- Socorro entre cidades: `aid_request_options` **nunca voltou vazia**. A rotina
  não a consulta. Em 36 avaliações polity/mês, `_pressured_settlements` devolveu
  vazio porque os planos alimentares estavam `satisfied`/`await_delivery`.

---

## Passo 1 — Socorro deixa de depender de plano bloqueado

**Causa provada.** `institutional_aid_policy.py:186` exige `plan.stage ==
"blocked"`. Reserva atendida não significa população alimentada, então a cidade
passa fome com o plano verde e nunca pede socorro.

Remover a exigência de `plan.stage == "blocked"` de `_pressured_settlements`. A
causa suficiente passa a ser o que já está nas linhas seguintes: relatório
datado **próprio**, observado hoje, com `missing_food > 0`. Manter o resto como
está (objetivo do próprio ator, recurso `food`, `_own_open_chain`).

Um objetivo alimentar continua necessário para saber de qual assentamento se
fala — não inventar pedido para assentamento sem objetivo.

## Passo 2 — Ignorar vira fato de decisão

**Buraco medido.** `NO_ACTION` grava apenas `ai_decision_declined` como
`OCCURRENCE`. A Crônica não mostra "o governo decidiu não agir", e nada a
jusante consegue se ligar causalmente à omissão — o que impede a revolta de ser
consequência rastreável de ignorar.

Em `institutional_decision_turn.py`, quando o ator é consultado e responde
`NO_ACTION`, gravar também um `FactKind.DECISION` (sem deltas, como todo fato de
decisão), com as mesmas causas datadas que compuseram o menu e o conjunto de
affordances recusadas. Manter o `ai_decision_declined` como está — é o recibo da
consulta, não a decisão.

Distinguir com rigor, porque já erramos isso antes: **recusa deliberada** (foi
perguntado e disse não) grava decisão; **falha técnica** (sem provider, sem
orçamento, teto mensal) não grava decisão nenhuma e não reivindica nada, para
não matar de fome as passagens determinísticas. `ai_decider.consultable()` já
faz essa distinção — usar, não reimplementar.

O mapeamento do front em `web/src/medieval/mappers.ts` já separa
`technical_failure`, `explicit_refusal` e `consultation_completed`; conferir que
a decisão nova aparece como escolha do ator e não como recusa.

## Passo 3 — Governo roteirizado no arnês de medição

**Por que existe.** O smoke reporta `"policy": "routine-rules"` como se fosse um
perfil de governo, mas é ausência de ator. Medir um mundo sem governo e concluir
coisas sobre governos é inválido — aconteceu duas vezes nesta frente.

Em `tools/medieval_autonomy_smoke.py`, um decisor determinístico **explícito**
instalado no lugar do provider, selecionável por flag:

- `desatento`: sempre `NO_ACTION`
- `reativo`: escolhe ajuda quando a fome observada passa de um limiar
- `preventivo`: escolhe ajuda ao primeiro sinal no relatório próprio

**Vive em `tools/`, nunca em `src/sim/`.** Não é fallback do motor: é um ator de
teste. O motor continua sem rotina de ajuda, e o protesto cívico continua sem
fallback determinístico — criar um transformaria revolta em script, repetindo o
erro que o Passo 4 desfaz.

## Passo 4 — Ajuda vira ato, não taxa

**O defeito.** A ajuda nasce em 1000, e o menu só mostra o que difere do valor
atual. Logo a IA nunca pode decidir ajudar, só parar de ajudar. Pior:
`authority.py:54` exige evento de origem para qualquer taxa diferente de 1000 —
a generosidade é axioma, a crueldade é que precisa de causa. É o inverso do
pretendido.

### Remover (sem camada de compatibilidade — regra do repo)

- `ReliefPolicy` em `src/classes/governance/models.py`, seu registro e a
  validação de proveniência em `authority.py:44-55`
- `src/sim/medieval/relief.py` inteiro (RELIEF_RATES, `relief_allowance`,
  `ReliefRateOption`, `relief_options`, `set_relief_rate`, `review_relief_rates`)
- a chamada `review_relief_rates` em `engine.py:161` e seu import
- o bootstrap da política em `src/run/medieval_governance.py`
- `tests/test_medieval_relief_policy.py`

Bump de `SCHEMA` em `persistence.py` (atual: 52). Saves antigos são rejeitados,
nunca migrados.

### Em `consume_monthly` (`economy.py`)

A demanda pública não paga vira `missing` diretamente. Não existe mais ajuda
automática. A prosa do recibo `subsistence_resolved` não pode continuar
afirmando "ajuda pública" — o repo trata prosa desalinhada do material como bug.

### O ato novo

`relief.py` (mesmo nome, conteúdo outro) e `relief_policy.py` (adapter):

- `ReliefDistributionOption`: ator é o **dono do estoque** (`stock.owner_ref`,
  se `kind == "polity"`), não o administrador — quem abre mão da receita é o
  dono da comida. Quantidade derivada do relatório datado próprio do ator sobre
  aquele assentamento, limitada pelo estoque físico real.
- Mais de uma quantidade por assentamento no menu (cobrir a fome observada
  inteira, ou metade): a IA escolhe **quanto**, não só **se**.
- `distribute_relief(world, option_id, decision_event_id)`: exige autoridade
  `supply`, revalida a opção (rejeita velha, inventada ou replay), move a comida
  do celeiro e grava `STATE_TRANSITION` com deltas de estoque e de
  `SettlementNeeds`.
- `relief_adapters(on_executed=None)` com `family="relief"`,
  `claim_fn=("relief", polity_id)` e `situation_fn` expondo só relatórios
  datados do próprio ator. Registrar em `institutional_agenda.monthly_adapters`.

### Latência, deliberada

`consume_monthly` roda antes do turno institucional, então o ato deste mês
afeta o consumo do mês seguinte. **Isso é correto e não deve ser "consertado"**:
o governo reage ao relatório do mês passado, que é o que governo faz. Reordenar
o bloco mensal quebraria a premissa dos relatórios datados.

---

## Verificação — enxuta, mas real

Sem matriz exaustiva de testes. O que tem que existir:

1. **Suíte medieval focada verde** nos arquivos tocados. Vão quebrar os testes
   que assumem ajuda infinita (`test_medieval_consumption.py`,
   `test_medieval_economy.py`, `test_medieval_logistics.py`, as fixtures
   `fed_world` de demografia/mortalidade, `test_medieval_markets.py`). **Isso é
   o objetivo, não regressão** — migrar as fixtures com um helper único.
2. **Não pode quebrar sem ser tocado:** conservação de dinheiro, revalidação
   bilateral de `buy_rations`, `ration_shares` estável, `test_medieval_tariffs.py`.
3. **Um teste por passo**, não mais: socorro pede com plano verde e fome real;
   `NO_ACTION` grava decisão e falha técnica não grava; ato de ajuda tira comida
   do celeiro de verdade e replay não tem efeito (`world_snapshot` idêntico).
4. **Uma medição final só**, 12 meses seed 73, os três perfis do Passo 3, com o
   ato de ajuda do Passo 4. Pergunta a responder: **com um governo omisso mas
   presente, a revolta abre?**

## Restrições

- Não commitar, não fazer push, stash, reset ou checkout destrutivo.
- A árvore tem WIP de outras frentes (52 arquivos). Não tocar em
  `src/classes/governance/diplomacy.py` nem `tests/test_medieval_customs.py`.
- Migração está **fora de escopo**. Não alterar `migration_policy.py`.
- Campanhas, magia e criaturas estão fora de escopo por instrução explícita.
- Medição com `python -u` e redirecionamento direto para arquivo, sem pipe e sem
  `timeout` — já perdemos medições por buffer perdido no SIGTERM.
- Ao mudar o significado de uma constante, grepar também o literal em string:
  três testes já quebraram por usarem a string crua em vez do nome.
