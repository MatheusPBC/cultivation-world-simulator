# Medieval World Simulator

Fork local de alta fantasia do [cultivation-world-simulator de MatheusPBC](https://github.com/MatheusPBC/cultivation-world-simulator), baseado no projeto de 4thfever. O objetivo é observar um mundo em que comércio, diplomacia, pesquisa, campanhas, magia e decisões individuais gerem consequências materiais e histórias causais.

## Estado atual

Em desenvolvimento: o servidor principal já executa exclusivamente o mundo medieval.
A API permite criar, consultar, avançar, pausar, acelerar, salvar e retomar.
O observatório PT-BR já está conectado: mapa Pixi com camadas, inspeção de
povoados/personagens/organizações, estoques, rotas, instalações e crônica causal.
A raiz HTTP serve somente o novo build; sem build, retorna `FRONTEND_PENDING`.

O cenário inicial contém 3 governos, 3 cidades, 5 vilas, 12 personagens relevantes
e 10.900 habitantes (os personagens estão incluídos nessa população). O tempo
salta meses em estabilidade e resolve datas específicas quando há situações agendadas.
Já existem produção, consumo, saúde/descontentamento, estoques, preços, cargas,
compra bilateral, treino/estudo, viagens, eventos causais e save SQLite próprio.
Produção paga salários aos grupos populacionais e recolhe imposto sobre essa renda,
com contas reais, limites de caixa e comprovantes no painel Finanças.
Famílias usam seus saldos para comprar rações locais; o restante do atendimento
continua como ajuda pública. Compras mostram decisões, pagamento e consumo na
crônica causal, e a receita pode financiar a produção do mês seguinte.

Governos já revisam reservas mensalmente e decidem remessas/compras bilaterais
autônomas, com cargos, relatórios próprios e ofertas públicas. Oficinas e governos
também repõem madeira e ferro para suas instalações, com reserva produtiva do
fornecedor, pagamento e entrega física. Projetos de expansão consomem materiais,
pagam artesãos e aumentam capacidade somente na conclusão. Finanças mostra obras,
progresso e impedimentos, além das folhas. O painel
Abastecimento mostra planos, impedimentos, cargas e causas. A economia ainda
tem gargalos de transporte e esgotamento de caixa; não está calibrada a longo prazo.
Pesquisa de irrigação, metalurgia, aço e engenharia a vapor exige especialistas,
materiais e salários. Linhas adicionais produzem carvão, aço e motores sem apagar a
produção anterior. Bombas mecanizadas consomem motores na obra e carvão ao operar.
Conhecimento pertence à instituição; ensino exige consentimento bilateral e a
aplicação depende de obras pagas. O painel Pesquisa mostra progresso e causas.
Veja [Pesquisa e aplicação](docs/specs/medieval-research.md) para os limites atuais.
Não há decisões por LLM nesta versão; diplomacia, pesquisa avançada, campanhas, magia,
criaturas e demografia autônoma continuam em implementação. Não é o jogo completo.

Exportações entre administrações diferentes podem carregar uma tarifa de origem
datada na oferta pública. A cotação mostra ao comprador apenas a taxa, o fato de
política e o coletor da jurisdição de origem; na abertura bilateral da ordem, o
comprador paga base mais tarifa uma única vez, o vendedor recebe a base e o tesouro
de origem recebe a tarifa. Não há tarifa em frete próprio/doméstico, pedágio,
trânsito ou bloqueio nesta vertical.

## Executar localmente

Na raiz deste fork, com Python e Node.js:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location web
npm ci
npm run build
Set-Location ..
$env:CWS_DATA_DIR = Join-Path (Get-Location) '.test-data'
.\.venv\Scripts\python.exe -m src.server.main
```

Abra o endereço raiz exibido pelo servidor para criar ou carregar o mundo.
O botão Avançar salto executa um mês estável ou a próxima situação datada;
Continuar/Pausar controla o loop. Arquivos do mundo permite salvar e retomar.
No atlas, selecione um povoado; Ver causa abre o fato e seus vínculos.

Para clientes da API, abra `/docs`. Use `/api/v2/command/create`
com corpo `{"seed":73,"character_count":12}`, seguido de `command/step`
com `{}` para um salto. Consultas ficam em `/api/v2/query/*`.
O servidor é local e não possui autenticação para exposição pública.
A variável `SERVER_PORT` permite escolher a porta.

Sem override, dados usam a pasta de aplicativo `MedievalWorldSimulator(-dev)`,
separada da origem. Saves estão em `saves/medieval/*.mws`, schema 67 (Society 21,
economia 15). Saves xianxia e schemas anteriores ao 67 são rejeitados e
preservados, sem sobrescrita nem migração.
O histórico causal é mantido integralmente em blocos compactados, com índice
de IDs, sequência e dia. Salvar substitui o arquivo de forma atômica; em caso
de falha, o save anterior permanece intacto.

Overflow regional é uma lei física sazonal engine-owned: usa água declarada e
elevação, exige duas avaliações altas consecutivas e danifica no máximo um site
aquático vulnerável por ocorrência. O Map é o owner e reports expõem o dano no
mesmo ciclo; o Dao vê a ocorrência, mas atores não recebem clima canônico. Não há
clima legado/xianxia, seca/população/colheita, quota de desastre, reparo ou decisão
automática, nem UI/API pública para essa vertical.

Migrações são jornadas temporais canônicas: residentes permanecem na coorte de
origem enquanto `present_population` diminui. A provisão usa `MoneyAccount` e
pantry próprio, com transferência bilateral entre donos, não consumo genérico.

Ajuda alimentar institucional está preparada como executor direto: a instituição
solicitante usa seu próprio `SettlementReport` causal atual com `missing_food` e
escolhe uma opção transitória enumerada pelo engine. O aviso persistido contém
somente `requested_food` engine-owned derivado desse relatório; não é um relatório
vivo e não revela oferta, estoque ou rota do provedor. O provider avalia o aviso
contra seu próprio stock e relatórios fiscais datados. Aceitar não move recursos;
fulfillment posterior revalida opções atuais, abre o frete e cumpre no dispatch.
O fallback `routine-rules` não é IA: no máximo uma ação por polity/revisão, na
ordem `respond`, `fulfill`, `remediate`, `request`. Request usa apenas plano
alimentar bloqueado, shortfall atual e uma cadeia/settlement aberto; as demais ações
usam opções atuais válidas. A agenda permite request em N, reply em N+1 e
fulfillment em N+2. Breach persiste e remediação não o apaga.

Memória institucional é uma camada de relevância, não uma segunda fonte de
conhecimento: `KnowledgeState` guarda os `DiplomaticNotice` que dão conhecimento
do fato, enquanto `RelationsState` persiste somente a memória ativa e seus cinco
campos (`id`, instituição, evento canônico, dia registrado e último reforço).
Criação e reforço exigem o fato de transição canônico e o delta do receipt
correspondente. Saliência e leitura são derivadas sem mutação e decaem numa
janela linear de 360 dias. Na V1, somente ajuda alimentar produz leitura
direcional: o credor lê breach como -4 e remediação como +2; não existe score
social genérico armazenado, fator de LLM, UI/API, IA real ou estratégia geral.

Quando uma instalação artesanal demonstra uma limitação real de mão de obra,
o engine pode publicar uma demanda datada e uma oferta privada para grupos locais
de agricultores. O grupo precisa aceitar por uma decisão exata; a oferta não
reserva pessoas nem dinheiro. A aceitação paga um estipêndio, torna o contingente
indisponível por 30 dias e só então Society revalida e converte a fração selecionada
em artesãos. É uma vertical agregada de transição local, não educação genérica,
aceitação autônoma ou IA real.

Instalações têm integridade e operabilidade no Map. Reparos são obrigações
econômicas explícitas, com projetos e lotes decididos, materiais e salários
pagos a partir da força de trabalho mensal compartilhada. O catálogo conhece
somente farm, mine, port, workshop, forest e mountainpass; a recuperação é
gradual (até 0,10 por lote) e não reativa automaticamente uma instalação com
`enabled=false`.

Um workshop já comissionado pode mudar de controle por conveyance bilateral:
o proprietário propõe e uma contraparte aceita uma opção enumerada pelo engine.
O executor revalida o site físico, owner/maintainer, autoridade e vínculos locais
de estoque/folha; só esses vínculos mudam. Estoque, saldos e projetos não são
movidos. Esta V1 não é um sistema de `PropertyTitle`, arrendamento, herança,
captura ou guerra e não expõe controle no observatório.

Uma carga interna presa numa passagem sem capacidade pode ser recuperada: o
dono escolhe entre aguardar ou abrir uma remessa sucessora por outra rota
fiscal válida, ambas opções transitórias enumeradas pelo engine a cada
consulta. A ordem original nunca é reescrita, reroteada ou reexecutada; só uma
transferência interna não paga e ainda não entregue é recuperável hoje, e uma
compra bloqueada agora possui uma vertical bilateral V1: somente compra já paga,
sem tarifa, sem entrega parcial e com frete integralmente bloqueado. O comprador
solicita uma rota alternativa por opção transitória e o vendedor aceita ou
recusa em decisão independente. A ordem, pagamento e carga originais são
imutáveis; a aceitação devolve explicitamente a carga original ao estoque do
vendedor e abre sucessora com estoque novo, sem novo pagamento ou refund. Não
há tarifa, automaticidade, despachante de affordances, UI ou API pública nesta
vertical.

Rotas fiscais são conhecimento datado: o operador de um posto civil publica um
recibo por decisão, distribuído pela rede física alcançável. Ao criar uma nova
carga, o ator escolhe entre opções de rota enumeradas pelo engine, incluindo
caminhos legais sem posto; a cotação e o relatório precisam continuar atuais na
revalidação. Cargas já contratadas não mudam de rota. Esta camada não modela
força, confisco, bloqueio ou rota secreta.

## Desenvolvimento e documentação

- [Contrato da API medieval](docs/specs/medieval-public-api.md)
- [Runtime, calendário e persistência](docs/specs/medieval-runtime.md)
- [Economia material](docs/specs/medieval-economy.md)
- [Logística e mercados](docs/specs/medieval-logistics.md)
- [Autoridade e abastecimento autônomo](docs/specs/medieval-autonomy.md)
- [Fronteiras arquiteturais](docs/adr/0010-medieval-world-foundation.md)
- [Interface e verificações](docs/specs/medieval-observatory.md)

Testes focados: `.\.venv\Scripts\python.exe -m pytest tests/test_medieval_api.py -q`,
com `CWS_DATA_DIR` definido como acima. Em `web`, `npm test` executa a suíte
medieval, `npm run type-check` verifica também templates Vue e `npm run build`
gera `dist-medieval`. `npm run dev` usa proxy para localhost:8002, configurável
por `VITE_API_TARGET`. A suíte xianxia está disponível como `npm run test:legacy`;
ela e a documentação herdada precisam de triagem e não representam o contrato novo.

O [README herdado](docs/upstream/README.md) fica preservado como histórico
(seus links relativos conservam a base da antiga raiz).
Consulte [LICENSE](LICENSE) e [CONTRIBUTORS.md](CONTRIBUTORS.md) para os termos
e créditos herdados. Este fork local não é uma versão publicada pelos projetos de origem.
