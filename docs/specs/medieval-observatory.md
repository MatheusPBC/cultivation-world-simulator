# Observatório medieval conectado

## Contrato atual

Frontend Vue/TypeScript/Pinia/Pixi em web/src/medieval. main.ts/App.vue montam
exclusivamente esse produto, com textos PT-BR em i18n.ts. A tela inicial oferece
seed e contagem (12 por padrão); população nomeada está incluída no total.
O observador cria/carrega/salva, pausa/continua, avança um salto e muda velocidade.
Não edita recursos, decisões, personagens nem resultados materiais.

Fluxo: tipos em types/medieval-api.ts (projeção do OpenAPI, defaults de resposta
sempre serializados), transporte api.ts, mappers.ts, Pinia/composables e componentes.
O índice types/api.ts reexporta o namespace, sem aliases entre contratos.
query/observatory reúne status/world/society/economy/map/governance/research/diplomacy
sob uma única revisão. Histórico e efeitos causais são paginados em consultas separadas.

O cliente não avança o relógio nem interpreta deltas como patches. Falha mantém a
última leitura com mensagem explícita; número de requisição impede publicação
atrasada. Comandos invalidam leituras anteriores. Trocar run_id limpa seleção e
foco causal. Loop de consulta não se sobrepõe, ignora aba oculta e é removido no
unmount; pausado consulta a cada4s, em execução a cada1s. Um timeout de30s limita
requisições, mas não implica que o servidor tenha cancelado um comando já recebido.

## Atlas e inspeção

Terreno vem de geography; território vem de region_rows. Não há segunda rede:
rotas ligam os endpoints canônicos e exibem a capacidade operacional da API.
Linhas são topológicas, não traçado exato. Sites usam células declaradas.
O preset ainda é esquemático/retangular, não geografia visual definitiva.

useAtlas mantém Pixi fora de proxies, usa useElementSize e destrói recursos no
unmount. Há camadas terreno/governos/abastecimento, visibilidade de rotas/sites,
zoom e enquadramento. Seleção por região também está disponível na lista HTML.
Falha de WebGL mostra alternativa textual; canvas não é a única interação.

Inspeção distingue administrador, ocupante e reivindicações. Exibe população,
saúde/descontentamento, estoques privados/públicos com donos, preços, grupos,
instalações/produção, rotas, personagens/habilidades/motivações, governos,
organizações, contas e cargas. Fontes materiais abrem a crônica com foco e rolagem.
Abastecimento contém SupplyPlans/useSupplyPlans: objetivo de reserva, estoque,
trânsito, etapa, bloqueio e relatórios comerciais do governo, datados e separados
da verdade atual. Novos tipos são derivados do OpenAPI; seletores são computed.
Histórico mostra25fatos por página, classificação, intenção, deltas brutos e
links para causas/efeitos. Deltas brutos preservam as unidades de seus owners
(por exemplo saúde/descontentamento em milésimos, versus porcentagem no resumo).

Save exige basename seguro; substituição de arquivo e carregamento têm confirmação
explícita. Carregar exige pausa e preserva autosave anterior. IDs de sessão e estado
do observatório não fazem parte do save canônico.

## Build e verificação

Em web: npm ci; npm test; npm run type-check; npm run build.
Typecheck inclui templates via vue-tsc; dist-medieval é o único output servido.
Servidor confere marcador medieval no index e confina assets a web_static;
arquivo/API desconhecido continua404. Sem build, raiz503 orienta a geração.
Nenhum asset/áudio/UI xianxia herdado é copiado pelo novo build.

Vitest medieval tem configuração própria; a suíte herdada continua em test:legacy,
sem alegação de compatibilidade ou aprovação. Testes atuais cobrem criação12,
avanço, seleção, save/load, erros, resposta atrasada, projeção espacial e causa
sem mutação, incluindo foco por teclado. Backend cobre snapshot coerente e
serviço de arquivos além da regressão de domínio.

Smoke histórico anterior à autonomia (schema4), em2026-09-13: seed73, 12personagens, dia360,
252eventos,10900habitantes; salvar, avançar390, carregar360; causa de escassez
e antes/depois visíveis. Continuar/pausar e foco causal também inspecionados.
Layout desktop e viewport estreito390 (375px úteis) sem overflow horizontal.
Console sem warnings/erros no percurso. Build possui aviso de chunk Pixi
772,8KB minificado/221,4KB gzip, carregado por import dinâmico, não na tela inicial.

## Limites e próxima unidade

Isto não encerra o observatório completo de disputas/campanhas/sucessão nem o jogo.
Abastecimento autônomo, cargos e planos já estão conectados; teste visual schema5
criou12 e avançou60dias, mostrando Portovelho com2000rações em estoque e2000 em
trânsito para reserva desejada4000; causa114 abre plano109/aceite111/carga112.
Painel/boletins inspecionados em desktop e390px sem overflow horizontal; console
semwarn/error. Restam diplomacia, conhecimento secreto/crenças, pesquisa, campanhas,
magia/criaturas, demografia, sucessão e IA real. Economia expõe gargalos/custo real,
sem garantir estabilidade artificial das cidades.
Não foi feita calibração de10anos. Áudio e triagem/remoção dos módulos/testes/
documentação legados também estão pendentes; build focado não prova fullsuite.

Painel Finanças (schema6): useIncome projeta poupança por povoado a partir das
contas dos grupos, sem somar personagens de novo. Folhas mostram última data,
trabalhadores, bruto, imposto, líquido e causa. Taxa configurada não é promessa
de arrecadação; texto explicita exigência de autoridade/administração. Na prova
UI seed73/dia30, poupança2520 e folhaSalgueiro800bruto/80imposto/720líquido;
causa3 abre salário2 e deltas das contas. Testes14passados e build/vue-tsc aprovados.
Inspeção desktop/390px encontrou e corrigiu overflow das cinco abas, agora com
quebra de linha; documento375px/scroll375, abas341px/scroll341. Artefatos em
income-desktop-final.png/income-narrow-final.png no workspace pai. Primeira navegação
registrou favicon404 não funcional; no build final consolewarning/error vazio.

No schema7, SupplyPlans usa o estoque/recurso do objetivo e o alvo derivado pelo
backend; não calcula insumos por população. Mostra finalidade, unidade, disponível,
em trânsito e data, filtrando boletins pelo recurso. Fonte mantém computed e keys
estáveis conforme orientação ui-ux-pro-max, sem novo estilo ou navegação.
TesteDOM distinguiu120ferro de3600rações; mapper recusa objetivo sem estoque/recurso
válidos ou alvo inteiro. Browser seed73/day30 mostrou oficina0ferro/120emtrânsito,
no31 passou120/0 e reserva atendida. Capturas inputs-workshop-before.png,
inputs-workshop-after.png e inputs-workshop-narrow.png no workspacepai, inspecionadas.
Em390px, documento375==scroll375, cartão295px. Build/vue-tsc e18testes aprovados;
permaneceaviso do bundlePixi772.8KB. Console registrou apenasfavicon404. Provas
anteriores de esquema/renda semconsumo são históricas, não saldo esperado atual.

Schema8: Finanças inclui ExpansionPanel, projetando instalação, estágio, trabalho,
capacidade atual, ganho previsto/aplicado e impedimento em português. progress tem
rótulo acessível; causa abre o evento material. Folhas de obra são distinguidas
das folhas de produção. No browser, mina10/10/capacidade70/conclusão90 e oficina5/10
sem saldo foram inspecionadas. Causa1055 mostrou ferramentas15→10, madeira130→120,
trabalho5→10 e capacidade60→70; consequências incluem salários1056 e produção1065.
Capturas expansion-desktop.png/expansion-narrow.png no workspacepai foram vistas.
Documento em390px:375==scroll375. Captura da seção inteira no viewport estreito
é cortada pelo contêiner rolável; não prova visibilidade simultânea de toda lista.
20testes frontend e build/vue-tsc aprovados, avisoPixi mantido, console sófavicon404.

Schema9: ResearchPanel/useResearch consulta o mesmo snapshot do mundo. Mostra
patrocinador, especialista, técnica, progresso, impedimentos e conhecimento por
instituição. Finanças identifica folhas de pesquisa e adaptação da receita sem
confundi-la com aumento de capacidade. Browser criou12/avançou30, carregou o
natural360 e inspecionou causa6107(pesquisa6105/salário6106/obra6154). Obras paradas
continuam mostrando rendimento pendente. Screenshots research-start-desktop.png,
research-adaptation-narrow.png e research-complete-narrow.png no workspacepai,
vistos;390pxdocumento375==scroll375/tabs341==341/cards295==295. Frontend23testes
e build/vue-tsc741módulos aprovados. Apenasfavicon404 no console, warningPixi
772.8KB permanece. Ver medieval-research.md para limites funcionais.

DiplomacyPanel/useDiplomacy consultam o mesmo DiplomacyView do snapshot (listas
planas de proposals/obligations/notices; a API não agrupa). O composable agrupa
obrigações por proposta+índice de cláusula, resolve nomes por entityName e abre
a crônica causal a partir de decision_event_id/last_event_id/material_event_id.
Notices exibidos ficam restritos ao evento focado, sem promover registro privado
a conhecimento público. Barganha determinística já está integrada ao motor; IA
real de negociação não. Ver medieval-diplomacy.md para os limites completos da
frente e docs/handoff/medieval-current-state.md para evidência de execução
(contagens de testes, prova manual e status da suíte ampla). Isto não encerra o
observatório de diplomacia, muito menos o roadmap ou a etapa0 do plano medieval.
