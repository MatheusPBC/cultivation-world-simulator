# Plano: traição como escolha, com repercussão futura

Fatia mínima do item 2 do roadmap ("Estratégia e diplomacia emergentes"), cujo
critério de aceite é: *"uma concessão pode surgir sem batalha; uma quebra
deliberada é rastreável, tem repercussão futura e não depende de uma cena
obrigatória."*

## As duas lacunas, verificadas no código

**1. Quebrar não é decisão de ninguém.** `src/sim/medieval/commitments.py:105`:

```python
status = 'excused' if any(d.status != 'fulfilled' for d in dependencies) else 'breached'
```

O prazo vence e o status vira `breached` sozinho. Não existe afordância "eu
escolho não honrar isto". A traição acontece por decurso de prazo, não por
vontade. É exatamente o erro que a frente da ajuda desfez: lá, ajudar era
automático e só cortar era escolha; aqui, trair é automático e não é escolha de
ninguém.

**2. Não há repercussão futura no julgamento.** `diplomacy_policy.py` não expõe
quebras passadas na situação apresentada ao ator. Um parceiro que já descumpriu
três promessas é avaliado exatamente como um que nunca descumpriu. A memória
existe no estado (`obligation.status == 'breached'`, `breach_event_id`) e é
usada em `authority_claims.py:77-89` para reivindicação de autoridade, mas nunca
chega a quem vai decidir se fecha o próximo acordo.

## Passo 1 — Repudiar vira ato

Enquanto a obrigação está `active` e antes do prazo, o devedor pode decidir
repudiá-la. Vira `FactKind.DECISION` (sem deltas) seguido de um
`STATE_TRANSITION` separado que conclui a obrigação como quebrada — com a mesma
disciplina de todo ato do kernel.

- Opção nova na família `diplomacy`, com autoridade e revalidação iguais às das
  afordâncias existentes (`OFFER_ACTION`/`PAY_ACTION` servem de molde — copie o
  padrão, não invente formato).
- A opção some sozinha quando a obrigação deixa de estar `active` (mesmo truque
  de basis no id já usado pelas outras).
- O repúdio **não** substitui o lapso por prazo: quem simplesmente não age
  continua caindo em `breached` pelo caminho atual. O que passa a existir é a
  diferença entre *não conseguir* e *não querer* — e essa diferença fica no
  grafo causal, legível.
- Reusar o caminho existente: `conclude_obligation(...)` e `note_breach(...)`
  já disparam o turno do credor lesado (`recourse_policy`). O repúdio entra
  nesse mesmo caminho, não cria um paralelo.

## Passo 2 — A quebra conhecida pesa no próximo acordo

O `situation_fn` da família `diplomacy` passa a expor, sobre cada contraparte,
as quebras que **este ator específico tem direito de conhecer**.

**Descoberta por canal causal, não onisciência.** O ator só vê a quebra se foi
notificado dela. O mecanismo já existe e deve ser reusado, não reimplementado:
`authority_claims.py:87` já filtra por `notice.recipient_ref == actor and
notice.event_id == obligation.breach_event_id`. Quem não foi lesado e não
recebeu notícia não sabe de nada — e isso é o ponto, não uma limitação.

Distinga no fragmento de situação, porque a diferença é o coração da fatia:
- **repudiada** — a contraparte escolheu não honrar
- **quebrada por prazo** — venceu sem cumprimento
- **escusada** — a dependência dela não foi cumprida primeiro, então a falha
  não é dela

Nada de score numérico de confiança. O ator recebe os fatos datados e decide.
Um placar seria script; a decisão é da IA.

## Fora de escopo, explicitamente

Persuasão, espionagem, suborno e sabotagem. São o resto do item 2 e cada um
merece a sua própria fatia. Esta entrega só fecha "quebra deliberada rastreável
com repercussão futura".

## Verificação — enxuta

1. Repudiar grava decisão sem deltas e transição material separada; a obrigação
   fica quebrada e o credor lesado ganha o turno de recurso que já existia.
2. Repúdio de obrigação já concluída, ou replay do mesmo `option_id`, não tem
   efeito (`world_snapshot` idêntico).
3. Um ator que foi notificado de uma quebra vê a quebra na situação; um que não
   foi notificado **não vê**. Este é o teste que impede a onisciência.
4. Suíte focada verde nos arquivos tocados. A suíte de diplomacia tinha 2
   falhas conhecidas e pré-existentes antes desta frente — confira o estado
   antes de começar e não conte elas como regressão sua.

## Restrições

- Não commitar, não fazer push, stash, reset ou checkout.
- A árvore tem WIP grande de várias frentes. `src/classes/governance/diplomacy.py`
  já tem alteração de outra frente (um invariante de recibo de frete): preserve
  o que está lá.
- Não tocar em `migration_policy.py`, `procurement.py`, `test_medieval_customs.py`.
- Bump de `SCHEMA` em `persistence.py` se acrescentar campo persistido. Saves
  antigos são rejeitados, nunca migrados.
