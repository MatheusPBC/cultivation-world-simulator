# Handoff do goal medieval — 18–19/09/2026

Este documento registra o trabalho acumulado no checkout desde a definição do
goal `implemente o plan medieval-roadmap-completion-plan.md`. Ele é um relato
de estado e evidência, não uma declaração de que o roadmap inteiro esteja
concluído. A referência de intenção continua em
[`docs/handoff/medieval-roadmap.md`](medieval-roadmap.md); a fila restante está
em [`medieval-roadmap-general-remaining-plan.md`](../../medieval-roadmap-general-remaining-plan.md)
e os checkpoints detalhados em
[`medieval-roadmap-completion-plan.md`](../../medieval-roadmap-completion-plan.md).

## Regra arquitetural preservada

O trabalho manteve uma única cadeia causal:

```text
estado canônico → condição/relatório → affordance transitória
→ decisão por ID ou NO_ACTION → owner revalida → execução material
→ evento + StateDelta + links causais → memória/read model
```

Affordances não são persistidas. Decisões persistem apenas a seleção e suas
fontes. A interpretação da IA, a prosa e Story não registram leis físicas nem
mutam o mundo. Authority, Knowledge, Strategy, Society, Economy, Map e
Research continuam owners separados. Obrigações representam compromissos e
não executam sozinhas quando chegam ao prazo.

## O que foi implementado ou consolidado

### Núcleo causal, transação e persistência

- Revalidação de affordance stale e receipts determinísticos para ausência de
  opção ou decisão obsoleta, sem delta parcial.
- Commit transacional incremental dos eventos novos, rollback de estado,
  agenda e RNG, e equivalência de save/load sem compartilhar estado mutável.
- Validação de `STATE_TRANSITION`, separação de eventos interpretativos e
  auditoria read-only em `tools/medieval_causal_audit.py`.
- Payload causal persistente e navegação do Why/API com fatos, owners, receipts,
  deltas e elos de causa conhecidos.
- IDs privados de estoque, conta, folha e plano são opacos no contexto do
  provider; o owner recompõe os parâmetros reais antes de executar.

### Economia, abastecimento e mobilidade

- Produção, emprego permanente, folha, mercado com oferta/demanda observadas,
  compras, pagamentos, tarifas, alfândega e rotas fiscais com conhecimento
  datado e revalidação no dia corrente.
- Desgaste de infraestrutura por uso material, reparo gradual explícito,
  reativação somente quando autorizada, conveyance produtiva e projetos com
  materiais/folha reais.
- Provisionamento domiciliar, relief institucional, transferência alimentar
  direta e interurbana, remediação de breach e recuperação de frete/compra
  bloqueados; ordens originais permanecem imutáveis.
- Migração com jornada, provisão de viagem, retorno, reroute por falta de
  moradia e deltas de pressão na origem/destino somente na chegada factual.
- Workforce `farmer → artisan/merchant`, ofertas privadas, reservas temporárias,
  demanda de trabalho agrícola escalada por escassez e fallback conservador que
  escolhe apenas IDs engine-owned.
- O menu institucional composto passou a consultar ajuda, mercado, workforce,
  diplomacia, estratégia, campanha e outras verticais sob o mesmo orçamento;
  ausência de affordance não chama provider.
- As affordances de socorro agora expõem cobertura integral e parcial do
  shortfall, ordenadas de modo estável pela maior quantidade; isso não cria
  estoque, dinheiro ou ajuda automática.

### Instituições, relações e agência

- Dossier institucional com capacidade estratégica derivada, objetivos/planos,
  evidências e memória direcional filtrada por conhecimento/notices do ator.
- Diplomacia com propostas, counteroffers, persuasão, respostas independentes,
  pagamentos, ensino, transferências, deadlines, breach, remediação e
  renegociação sem apagar fatos históricos.
- Memória institucional aponta para fatos canônicos e receipts de criação ou
  reforço; saliência é read model derivado, não um score social inventado pela
  LLM.
- Acusação derivada de investigação, findings privados de espionagem/roubo e
  suborno/sabotagem com presença, autoridade, ferramentas e evidência reais.
- Protesto, recusa cívica, tumulto, greve, movimento, rebelião, revolução,
  negociação, supressão e anistia têm escada material; nenhum estágio concede
  autoridade, território ou vitória automaticamente.

### Tecnologia, pesquisa e produção

- Catálogo de pesquisa com descoberta, pré-requisitos, conhecimento
  institucional e aplicação como construção paga.
- Apprenticeship exige especialista que migrou de fato, residência, patrocínio,
  trabalhadores locais, pagamento e agenda de conclusão.
- Venda e roubo tecnológico têm consentimento/decisão independente,
  autoridade, instalação, conhecimento, agente/ofício e receipts próprios.
- Cadeia agrícola authored de conhecimento → ensino/apprenticeship → instalação
  → operação/manutenção, além de `field_drill`/`siegecraft` com efeito limitado
  e engine-owned na força de campo.

### Campanhas, força e controle

- Levantamento de coortes, salário, rações, marcha, comando, reconhecimento,
  força de campo, fadiga/moral/terreno e resolução de engajamento.
- Cerco persistente com suprimento, progresso, endurance, brecha/colapso,
  retirada, rotação e guarnição; a brecha não concede ocupação sozinha.
- Ocupação, controle territorial, administração, retirada e concessão são
  estados distintos. Cessar-fogo, solução política e remediação exigem
  decisões e cumprimento material posteriores.
- Projeções de campanha e Atlas expõem estados, propostas e controles ao Dao
  sem criar mutação na UI.

### Magia, hazards, ecologia e criaturas

- Definições engine-owned de hazard por espécie, resistência, magnitude limitada,
  wards, flood-control, contramedidas e evidência de exposição.
- Overflow regional baseado em água/elevação e duas avaliações altas; sem quota
  narrativa, clima fornecido aos atores ou reparo automático.
- Rio Lume com `river_drake` e `river_serpent`, demandas de tributo, parcelas,
  passagem, recuo e ataque limitado a coortes anônimas reais quando a exigência
  vencida é ignorada.
- Tick ecológico deriva estresse da capacidade operacional e dependências da
  rota; habitat/espécie e decisões de criatura permanecem separados.
- Ritos restaurativos exigem oficiante, site, reagentes, assistentes e
  testemunhas; não criam população, recurso, controle ou lei mágica.

### API, UI, documentação e ferramentas

- Contratos `/api/v2`, observatório, dossier privado, diplomacia, campanhas,
  tecnologia, hazards, pesquisa, renda, supply e leituras locais de mercado.
- UI PT-BR com Atlas, Chronicle, Inspector, Diplomacy, Research, Supply,
  Income e Strategic Capacity; o frontend mantém snapshot atômico sob lock e
  não autoriza edição de estado canônico.
- Atualização de `CONTEXT.md`, specs, handoffs e planos; inclusão do plano geral
  restante e deste documento como continuidade explícita.
- Ferramentas de smoke, auditoria causal, release gate e probe de provider real.
  O probe falha explicitamente quando o provider não está configurado, sem
  fallback silencioso.

## Evidência executada neste checkpoint

Os comandos abaixo foram executados no checkout antes do commit:

```text
93 testes materiais (ondas 3–5): PASS
31 testes de provider/turno: PASS
36 testes de relief/turno/smoke: PASS
python -m compileall -q src tests tools: PASS
git diff --check: PASS
smoke socorro de 60 dias: conservação de comida/dinheiro/recursos,
save_load_equivalent=true, real_ai_calls=0
```

O probe operacional real também foi exercitado:

```text
CWS_DATA_DIR=/tmp/cws-tests .venv/bin/python tools/medieval_provider_probe.py \\
  --seed 73 --ai-calls-per-step 1
→ RuntimeError: real provider is not configured or is disabled in this runtime
```

Esse erro é o comportamento fail-closed esperado; não é prova de provider
remoto funcionando. Os recortes acima também não são a suíte global.

## O que permanece aberto

1. **Provider real:** configurar e validar uma consulta real, `NO_ACTION`, ID
   stale/inexistente, orçamento, latência, custo, rollback e continuação após
   save/load.
2. **Agência institucional completa:** generalizar compromissos, memória,
   negociação, acusação, traição deliberada e reparação fora das verticais V1.
3. **Economia resiliente:** o mundo ainda pode permanecer com déficit alimentar
   em horizonte longo; não foi adicionada distribuição automática para mascarar
   a pressão.
4. **Tecnologia ampla:** cadeia industrial, difusão geral e operação além dos
   recortes authored ainda precisam de prova material extensa.
5. **Campanha persistente:** manutenção/rotação/queda em horizonte prolongado e
   solução política pós-ocupação ainda não formam uma campanha geral.
6. **Magia/ecologia geral:** mais escolas, habitats, necessidades persistentes,
   contramedidas e negociação de criaturas ainda faltam.
7. **Intriga e produto do Dao:** dossier multi-salto e superfícies PT-BR para
   navegar resultado → fato → decisão → owner → evidência ainda precisam ser
   completados.
8. **Gate de release:** três seeds naturais por dez anos, fixtures pressionadas
   por vertical, auditoria final, type-check/build web e custo/latência do
   provider ainda não formam um aceite final. O smoke natural de dez anos foi
   interrompido por custo operacional, não aceito.

## Estado de publicação

Este handoff e o WIP técnico foram incluídos no commit desta sessão. O commit e
o push devem ser conferidos pelo hash e pelo branch remoto informados na entrega;
nenhum deploy da VPS faz parte deste checkpoint.
