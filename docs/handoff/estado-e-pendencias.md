# Estado, pendências e sequência de retomada

Base inspecionada em 12/09/2026: `896c0359`, `main`, sem WIP anterior a este pacote documental. Não houve nova execução de testes ou inspeção da VPS para escrever este handoff. Evidências de execução abaixo são históricas, não validação nova.

## Veredito

**O plano inteiro não está concluído.** A infraestrutura causal/institucional e a vertical de ajuda existem; várias composições sociais têm somente recortes funcionais. Não usar quantidade de commits ou testes como porcentagem de conclusão.

| Área | Cobertura registrada | Limite atual |
| --- | --- | --- |
| Ondas 1–5 | Contratos, estados separados, autoridade, ajuda e seleção/revalidação de affordances implementados. Administração anual das seitas já seleciona um ID por rodada. | Não é auditoria exaustiva de toda mutação possível no jogo. |
| Onda 6 | Termos, entrega, breach, reparação, memória/decay e impactos qualitativos implementados em caminhos concretos. | Ledger mantém cobertura parcial; influência/anchors não têm cobertura universal. |
| Onda 7 | Cadeia institucional em região, seita e dinastia, API e Why. | Testes de UI/build não substituem inspeção visual real ou aceite de usabilidade. |
| Onda 8 | Até três meses de pré-história em fases canônicas filtradas; ampliada para pressão urbana e resposta das seitas. | Não representa uma vida passada completa nem toda a variedade de episódios planejada. |
| Onda 9 | Correção hidrológica, drenagem, observações e proveniência; dano material separado. | Calibração e cobertura não provam todos os mapas equilibrados. |
| Comércio | Troca recíproca entre cidades sob escassez, dois termos independentes, rota/estoque reais. | Não é comércio geral, mercado de preços ou cadeia logística profunda. |
| Guerra | Agressão auditada, resposta independente, declaração institucional e negociação de paz; fase autônoma de batalhas removida. | Não é um sistema completo de campanhas ou guerra territorial. |
| Religião | Ritos e patrocínio causal, audiência e reação de testemunhas têm caminhos verificados. | Não entrega genericamente perseguições, inquisições ou todo conflito religioso desejado. |
| Desordem civil | Petição, paralisação de um ciclo, tumulto, endosso de residente e resposta independente do governo. | Greve geral, violência coletiva distinta, movimento organizado, rebelião e revolução ainda ausentes. |
| Onda 11 | Condicionada à evidência das simulações. | Intriga, conspiração e ameaças míticas não iniciadas. |

## Problemas observados no último mundo — não corrigidos neste pacote

Inspeção histórica de 09/09/2026: ano 101, mês 10, 13 Avatares, mundo pausado. Oito estavam respirando qi. Nos últimos 12 meses consultados: 61 eventos, 56 rotineiros, quatro importantes e uma Story. A amostra não é prova de inatividade de todos os sistemas.

### P0 — Falha de interpretação apresentada como estratégia

A decisão anual da seita 12 registrou `maintain` porque o provider estava indisponível; resumo e crônica apresentaram consolidação como preferência estratégica. O motivo técnico exato ainda não foi determinado: o fallback pode cobrir erro de provider ou parsing.

- Decisão: `af11cf64-0de9-4993-962b-91e5b4a0b4fb`.
- Resumo: `c8dc023c-f532-4cf4-8ed8-7719f62103bc`.
- Inspecionar `domain_decision_interpreter.py`, `sect_decider.py`, projeções e templates.
- Aceite proposto: distinguir escolha consciente, ausência de affordance e falha técnica, sem inventar motivação; preservar ausência de mutação em falhas.
- O endpoint causal mostrou `decision: null` enquanto outra projeção tinha motivo: investigar contrato, não assumir perda no storage.

### P0 — Crônica confunde mês absoluto e ano

O mundo estava em 101, mas o texto usava “Em 1213”, “Em 1218” e “No ano de 1200”. Esses valores coincidem com month stamps internos.

- Inspecionar `chronicle_service.py`, calendário, payload e templates.
- Aceite proposto: ano/mês corretos em geração e apresentação, inclusive virada de ano; timestamp interno nunca tratado como ano.

### P1 — Acontecimento sem efeito ganha importância e sugere trama inexistente

Huyan Ya perdeu **0** pontos de cultivo, mas o fato era importante. A Story vinculada descrevia mecanismo/ameaça sem consequência material registrada na cadeia consultada.

- Fato: `b00fed87-aa8c-419b-83c0-3ad42ee9bcd9`.
- Story: `4963a673-3af3-4566-aa55-fc5314e6a7a4`.
- A Story não tinha deltas e seu link vinha do fato: não foi observada mutação causada por prosa.
- Inspecionar `fortune.py`, `story_event_service.py`, classificação e templates.
- Aceite proposto: zero efeito não virar grande consequência sem outro fundamento; narrativa não prometer ameaça persistente inexistente.

Esses IDs pertencem àquele mundo e podem não existir em outros saves. Sua presença não autoriza editar o histórico real para “corrigi-lo”.

## Ordem recomendada para continuar

1. Confirmar revisão, WIP e reproduzir os três problemas acima em dados isolados. Corrigir transparência técnica, calendário e classificação/narrativa com testes focados.
2. Auditar em mundo natural por que as instituições recebem ou não oportunidades: leituras, autoridade, estoque, conhecimento, cadence e orçamento. Não aumentar urgência ou forçar pedidos só para obter drama.
3. Fechar lacunas da vertical existente: persistência, memória influenciando contexto futuro, UI/Why e falhas reais de provider. Medir cobertura, não reabrir arquitetura.
4. Completar recortes restantes das ondas 8/10, um caminho material por vez. Antes de rebelião, demonstrar pessoas, organização, liderança e capacidade; não criar estado político fictício para satisfazer uma meta narrativa.
5. Reexecutar smokes natural e pressionado, registrar seed/revisão/artefatos e analisar histórias concretas. Só então decidir se a onda 11 se justifica.

Essa ordem é recomendação de retomada; não amplia o plano nem autoriza implementação/deploy automaticamente.

## Evidências históricas e limites

Último checkpoint anual registrado: **105 testes em 16 arquivos**, 13,30 s, Ruff/diff limpos e build frontend com typecheck. Não foi suíte inteira.

Smokes institucionais focados de 120 meses:

| Cenário | Eventos | Profundidade causal | Transferências |
| --- | ---: | ---: | ---: |
| Natural | 3.233 | 18 | 0 |
| Pressionado | 3.671 | 9 | 20 |

Ambos registraram auditoria limpa, sem causas quebradas/fora de janela, mutações de Story ou chamadas ao provider. Pressionado registrou cadeia de sete fatos e memória; ausência de entrega no natural é válida. Não provam toda a experiência com LLM real.

Os artefatos originais estavam em `/tmp/cws-annual-aff-natural120.json` e `/tmp/cws-annual-aff-pressured120.json`. **Não fazem parte do repositório e podem ter desaparecido**; rerodar em outro ambiente. Os 27 registros de condições eram oito condições positivas/operacionais e 19 déficits de acesso a cura, não 27 enchentes.

Deploy histórico: `896c0359` publicado e saudável em 09/09/2026; novo mundo criado depois. O pedido posterior de pausa encontrou o mundo já pausado. Revalidar tudo antes de qualquer afirmação sobre produção atual.

Alertas históricos adicionais: build frontend com chunk grande; auditoria npm do build apontou 21 vulnerabilidades (4 moderadas, 15 altas, 2 críticas), sem análise de explorabilidade. Não confundir dependências de build com vulnerabilidade comprovadamente explorável em produção; investigar separadamente, sem atualização massiva automática.
