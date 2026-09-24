# Plano para terminar o roadmap medieval

Atualizado em 24/09/2026, iniciado sobre `codex/medieval-remote` no checkpoint
local `ed13e80a`. Este plano define o trabalho que falta; não declara o roadmap
concluído. Fatos e resultados detalhados ficam em
`docs/handoff/medieval-current-state.md`; o produto desejado, em
`docs/handoff/medieval-roadmap.md`; checkpoints históricos, em
`medieval-roadmap-completion-plan.md`.

## Direção

Não abrir novas verticais enquanto as existentes não formarem um mundo
observável e sustentável. A regra continua:

```text
estado e evidência canônicos → affordances válidas → decisão independente
→ owner revalida/executa → fatos e deltas → conhecimento/memória → próximas decisões
```

Sem quotas de drama: estabilidade, `NO_ACTION`, crise ou guerra podem ser
resultados válidos. Pressões de teste podem ser construídas em fixtures, mas
eventos narrativos não podem forçar a trajetória natural.

## Estado comprovado no checkpoint

- O kernel causal e fatias materiais de economia, auxílio, mobilidade,
  diplomacia, pesquisa, forças/campanhas, criaturas, ecologia e observação já
  existem; vários continuam V1/parciais.
- Houve escolhas reais curtas de Luna em um menu econômico natural (alívio, não
  oficina) e para um comandante em contato (`hold`). Isso valida chamadas
  delimitadas, não autonomia contínua nem escolha da melhor política econômica.
- O smoke natural schema 70 da seed 73 chegou ao dia 1440 sem provider: auditoria
  causal e conservação passaram, mas houve 452 mortes por privação, saúde média
  321,62/1000 e unrest 449,75/1000. Não é sucesso econômico nem gate final.
  Schema 71 agora permite suspender um vínculo sob pressão atual de folha por
  decisão do empregador; ainda não foi observado em mundo natural/provider.
- A interferência campanha–criatura–comércio foi provada em fixture pressionada;
  a cadeia política rei → QG → comandante e sua formação natural ainda não foram
  provadas. O limite de staffing já mostra custos/saldo do empregador à IA, mas
  sua escolha espontânea ainda não foi medida.
- Os gates de três seeds por dez anos, provider real em horizonte representativo,
  integração ampla e escala/save/load no checkout final continuam abertos.

## Trabalho restante, em ordem

1. **Fechar o diagnóstico econômico antes de balancear.** Usar snapshots e
   receipts atuais para localizar, por assentamento, se a pressão é falta física,
   falta de renda, folha concorrente, rota ou distribuição. Selecionar uma causa
   dominante e uma affordance/owner existente para tratá-la; não criar dinheiro,
   comida, emprego ou resgate automático. A opção recém-adicionada de suspender
   um vínculo sob limite real de folha é candidata a liberar força de trabalho
   e orçamento, mas não deve ser declarada solução antes de ser escolhida e
   medida.
   **Aceite:** contrafactual controlado muda a causa e, por ela, a consequência;
   custo, trabalho, estoque, saúde e população continuam conservados e navegáveis.

2. **Validar decisões reais nos menus atuais.** Já existem escolhas reais curtas
   de Luna (alívio entre opções econômicas) e de comandante (`hold`). Falta
   cobrir `NO_ACTION`, erro/timeout, orçamento esgotado e ID stale com provider
   configurado; owner sempre recompõe opções. Interpretação não tem delta; falha
   não deixa mutação parcial nem avança agenda/RNG. Não equiparar provider e
   fallback.
   **Aceite:** receipts/auditoria provam cada caminho e uma execução curta no
   schema atual mede escolhas com affordances concorrentes. Consulta externa só
   com autorização vigente e payload sintético/minimizado.

3. **Fechar uma economia natural utilizável.** Depois da correção causal escolhida
   no item 1, fazer preflight reproduzível no schema atual e acompanhar renda,
   produção, compras, estoques, saúde, falta, migração e mortalidade; usar o
   provider separadamente quando habilitado. Nenhuma política recebe prioridade
   porque o teste exige recuperação.
   **Aceite:** recuperação é possível por decisões e owners materiais, sem
   apagar crises legítimas; toda deterioração continua explicável. Se não houver
   estabilidade em toda seed, registrar diferenças e causas — não mascarar.

4. **Completar a cadeia de comando institucional.** Compor líder político,
   titular de policy, QG/operations e comandante como atores/autoridades
   distintos: objetivo, plano/ordem válida, transmissão ou relatório datado,
   decisão tática e resposta ao resultado. Implementar apenas os elos ausentes;
   não simular mensagens instantâneas, obediência, discordância ou sucesso por
   prosa.
   **Aceite:** cada decisão tem ator, conhecimento, autoridade e receipt
   próprios; atraso/relatório velho e `NO_ACTION` podem alterar o curso por owners
   reais; save/load preserva ordens e pendências.

5. **Provar composição de campanha sem roteiro.** Integrar uma campanha já ativa
   com ao menos uma interferência material existente (rota/clima/criatura),
   abastecimento, resposta do comandante/QG e consequência econômica ou social.
   Começar por fixture pressionada causal; depois observar runs naturais sem
   exigir que o evento ocorra.
   **Aceite:** mudar rota, carga, relatório ou decisão muda o resultado material;
   nenhuma fixture injeta o resultado, e uma seed tranquila continua válida.

6. **Fechar campanha e saída política.** Auditar gaps restantes de mobilização,
   rotação/manutenção, suprimento, combate/cerco prolongado, controle revogável,
   cessar-fogo, retirada, concessão e breach/remediação. Implementar só gaps
   demonstrados na auditoria; propostas e compromissos nunca executam sozinhos.
   **Aceite:** força sem suprimento/guarnição perde capacidade material;
   aceite político só altera realidade após cumprimento independente e válido.

7. **Concluir verticais restantes do roadmap, sem novos minigames.** Completar a
   cadeia tecnologia → conhecimento → instalação/operação/manutenção; generalizar
   leis engine-owned de magia/ecologia/criaturas; finalizar intriga, religião e
   investigação com evidência/conhecimento/ação material. Reusar affordances,
   autoridade, commitments, memória e owners atuais.
   **Aceite:** cada vertical tem uma cadeia ponta a ponta causal, save/load e
   regressão focada; efeitos especiais não são inventados por LLM nem disparados
   por quota narrativa.

8. **Tornar a causalidade legível e passar os gates finais.** Completar os
   dossiers PT-BR para navegar decisão → evento → owner → evidência em economia,
   campanha, comando, relações e ameaças; medir custo de simulação, RSS e saves.
   Ao estabilizar o schema/regras, rodar três seeds naturais por 3.600 dias com
   checkpoints, conservação, save/load/continuação e auditoria causal; rodar
   fixtures pressionadas separadas para exigir cadeias multietapas. Executar por
   fim regressões focadas, type-check/build e gates de API/frontend.
   **Aceite:** zero causa quebrada, delta originado em Story/interpretação ou
   mutação parcial; runs tranquilos são válidos; custo/memória/saves ficam
   reportados e dentro do limite operacional acordado.

## Dependências e controle de escopo

```text
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
```

Uma etapa só fecha com evidência do owner e estado atuais. Teste focal prova
contrato local; fixture prova mecanismo sob pressão; smoke natural mede a
trajetória daquela política/seed; provider stub ou fallback não prova IA real.
Não começar Industrial Warfare, nem abrir torneios ou novas features laterais
antes do item 8.
