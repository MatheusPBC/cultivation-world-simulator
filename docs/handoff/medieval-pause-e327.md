# Pausa solicitada — E327 (2026-09-29)

Atualização: o usuário retomou o goal e revogou a pausa. E327 foi verificado
e fechado no diário/matriz; E328 é a próxima tarefa. Este arquivo conserva
o checkpoint histórico, não constitui pedido vigente de pausa.

Implementação interrompida a pedido do usuário. Preservar o worktree; não tratar
esta pausa como conclusão de M5 ou do contrato Medieval.

## Checkpoint

- E326: rito elemental de reparo, com evidência registrada nos documentos atuais.
- E327: anteparo evocado temporário implementado em WIP, com entidade própria,
  custo material, duração de 12 dias, interceptação de um impacto de criatura,
  dissolução, observações locais, persistência e exposição na interface.
- A execução que estava pendente terminou: `tests/test_medieval_evocation.py`
  apresentou **5 passed in 2.78s**. Resultado recuperado na pausa; não é um gate
  agregado nem prova de emergência natural/provider real.
- Regressão anterior deste recorte: elemental + rite reach, 18 passed in 5.73s.
- Type-check anterior passou, mas houve alterações posteriores no mapper e na
  fixture do frontend; repetir a verificação antes de declarar o recorte fechado.
- Não foi encontrado processo pytest de E327 ainda em execução.
- Não houve commit, push, merge ou deploy nesta pausa. WIP permanece local.

## Retomada, em ordem

1. Revisar o diff E327 e confirmar os cinco casos executados.
2. Verificar decisões independentes datadas e interrupção do rito, incluindo
   interrupção no mesmo dia da conclusão; não assumir que estão cobertas.
3. Verificar UI e regressão focada de conhecimento, ritos, criaturas e save/load.
4. Sincronizar AGENTS.md (ainda declara schemas anteriores), contrato, matriz e
   estado atual somente com evidência verificada. Schema em código: save 83,
   Research 5 e Knowledge 11.
5. Fechar o checkbox E327 apenas após estes aceites; M5–M8 continuam abertos.

Não iniciar outra vertical nem smoke longo enquanto este recorte estiver aberto.
