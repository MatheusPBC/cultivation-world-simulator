# Runtime medieval em construção

## Entrada pública

`python -m src.server.main` inicia a API medieval local; `/docs` apresenta os
contratos de criação, consulta, avanço, pausa, velocidade e save/load.
Veja [medieval-public-api.md](medieval-public-api.md). O observatório visual está
conectado: execute npm run build em web e abra a raiz. Sem build medieval marcado,
a raiz retorna `FRONTEND_PENDING`, sem servir o bundle antigo.

## Executar a prova da fundação

Na raiz do fork, com o ambiente virtual instalado:

```powershell
$env:CWS_DATA_DIR = Join-Path (Get-Location) '.test-data'
.\.venv\Scripts\python.exe tools/medieval_smoke.py --seed 73 --output .test-data/runtime-foundation-smoke/world.mws
```

O cenário preparado inicia uma viagem e estudo para os outros personagens,
avança 360 dias, salva cada salto e confere a retomada. Ele não representa uma
simulação natural de política/economia nem chama IA. Por padrão são 12
personagens incluídos nos grupos de 10.900 habitantes.

Para testar comércio, bloqueio e recuperação com condições preparadas:

```powershell
.\.venv\Scripts\python.exe tools/medieval_trade_smoke.py --seed 73 --output .test-data/runtime-trade-smoke/world.mws
```

Esse cenário compra 2.400 rações para Portovelho, mantém a passagem fechada até o
dia30, retoma um save em trânsito e reabre a passagem. No dia60 verifica entrega,
recuperação de saúde e conservação estoque+carga+consumo e dinheiro. As decisões
e a reabertura são preparadas, não escolhas autônomas de IA.

## Estado e execução

`MedievalSimulator` resolve situações na data agendada e processa os domínios
mensais nas viradas de mês. A resolução datada precede o processamento mensal
quando ambos coincidem. Atividades desconhecidas são erros explícitos: não são
descartadas da agenda. Treino/estudo acumulam dias efetivos e produzem um ponto
por 30 dias, até o limite da habilidade; uma prática iniciada no dia 29 não
recebe um mês inteiro no dia 30.

Viagens usam uma rota explícita e seus endpoints, qualidade e capacidade
operacional. Nesta fundação, a escala é 10 km por célula, 20 km/dia em estrada
ou 40 km/dia por rio, antes do ajuste por qualidade. É deslocamento entre
regiões, não geometria precisa da estrada. O personagem conserva a residência
populacional enquanto viaja. Uma rota indisponível na resolução adia a chegada
e reagenda a situação; a escolha estratégica de desvio ainda será integrada.

Para portos e passagens de montanha, o Map separa dano físico de serviço. O
proprietário atual, com mandato de abastecimento, presença local e `SiteReport`
recente, pode suspender ou retomar o próprio serviço. Serviço suspenso zera a
capacidade derivada da rota e preserva a carga em espera; não repara, não reativa
`enabled=false`, não confisca bens e não modela bloqueio militar ou alfândega.

O desgaste segue a mesma fronteira de ownership: é uma mutação física do Map
derivada somente de uso material comprovado por recibos de produção ou carga.
Sua lei é determinística e limitada a 1% por janela de 30 dias; não usa clima,
RNG ou eventos narrativos. O relatório do ciclo registra a integridade resultante
antes de o mantenedor decidir um reparo, e nenhum sistema repara ou reativa o
site automaticamente.

O runner prepara uma cópia isolada do mundo, incluindo RNG, atividades e
histórico. Só publica o candidato no objeto raiz depois de validar e, quando
configurado um caminho, salvar. Falhas deixam o objeto publicado e o save
anterior intactos. Consumers devem consultar o estado pelo mundo atual após
cada passo; referências a subobjetos de snapshots anteriores não são atualizadas.
O runtime público mantém um único simulador e serializa consultas, comandos e
passos pela mesma trava. A trava interna do simulador também protege seus passos;
não é autorização para mutações concorrentes por outras instâncias.

## Histórico causal

Produção e consumo agora executam mensalmente, respeitando trabalhadores, insumos,
integridade e armazenamento. A falta de rações afeta saúde e descontentamento;
instalações sem produção deixam evidência dos fatores limitantes, ligada ao
abastecimento. Estoques privados não são consumidos pelo povoado. Regras e unidades
estão em [medieval-economy.md](medieval-economy.md). Compras bilaterais à vista,
preços locais e cargas por múltiplas rotas agora são executáveis; contratos de
transporte estão em [medieval-logistics.md](medieval-logistics.md). Compras e remessas
autônomas agora seguem relatórios, objetivos e consentimento dos governos:
[medieval-autonomy.md](medieval-autonomy.md). A economia não está calibrada.

`WorldEvent` reutiliza `FactKind`, `CausalOrigin`, `StateDelta` e `CausalLink`
do fork, com dia absoluto e sequência monotônica determinística. A decisão
contém a intenção e não aceita deltas; a mudança posterior do owner registra
os deltas e aponta para a decisão. Causas inexistentes e sequências/datas
inconsistentes são rejeitadas. Os executores são responsáveis por demonstrar
que seus deltas correspondem ao efeito material; narrativa não aplica patches.

A cópia transacional de eventos reconstrói valores pela forma serializada validada,
sem compartilhar os dicionários, deltas ou parâmetros de vínculos com o mundo
publicado. A serialização intermediária preserva números não finitos até a rejeição
JSON estrita, evitando convertê-los silenciosamente para `null`. A validação integral
do histórico e a escrita atômica continuam ocorrendo nas fronteiras existentes.

Durante um lote de cargas, a proveniência das rotas utilizadas é derivada numa
única passagem pelo histórico. O lote não altera rotas nem instalações; seus
eventos de carga não invalidam essa consulta. O resultado é descartado ao fim
do lote e refeito na próxima resolução, inclusive após save/load. Não há cache
persistido ou segunda fonte de verdade para bloqueios ou danos.

Medição histórica schema5 seed73/dia180: o smoke natural caiu de 29,98s (medição anterior)
para 21,06s; snapshots e todos os 3.831 eventos salvos foram comparados e iguais.
No perfil isolado do salto180→181, a cópia recursiva original levou 1,099s no
total e a cópia validada 0,393s, ambas com a consulta de rotas já otimizada.
São medições locais, não garantias de latência. Cópia, validação e reescrita ainda
crescem com o histórico; isso não prova a meta de três mundos de dez anos.

## Save próprio

Um `.mws` é um arquivo SQLite com tabelas `metadata`, `world` e `events`, e
índice por dia/sequência. O snapshot JSON interno carrega sociedade, mapa físico,
rotas, instalações, relógio, agenda, atividades, economia, autoridade, conhecimento,
estratégia, pesquisa, configuração e RNG.
A identidade de produto é `medieval-world-simulator`, com schema 19 e versão de catálogo explícitos; Society está no schema 2 e Economy no schema 10.
Nenhum loader consulta o catálogo atual para reconstruir o mundo salvo.
Saves experimentais schema 1–18 são rejeitados e preservados; use um novo arquivo
para o smoke atualizado, sem sobrescrever a prova histórica anterior. O snapshot
atual inclui migrações, provisões de viagem, observações de povoado e a economia schema 10 com `repair_blueprints`,
`repairs`, postos civis de alfândega e manifestos; nenhum loader migra schemas antigos. O catálogo de custos é propriedade
do engine e os DTOs apenas o projetam.

Relatórios fiscais de rota são conhecimento datado e persistem como recibos:
observação do operador do checkpoint e boletins físicos publicados por decisão.
Rotas legais sem posto permanecem opções distintas. A abertura de uma nova carga
revalida a opção enumerada pelo engine; ordens existentes não são redirecionadas,
e esta vertical não cria força, confisco, bloqueio ou rota secreta.

A escrita valida o candidato, prepara um arquivo temporário na mesma pasta,
fecha conexões e substitui atomicamente o destino. Um arquivo existente de
outro produto não é sobrescrito. A leitura é somente leitura, rejeita saves
xianxia/estrangeiros e ausência de histórico declarada pelo snapshot. Não há
credenciais, sessões, locks ou configurações secretas no arquivo.

## Pendências de integração

Etapa 1 (fundação/informação/abastecimento) está **PARCIAL**: o núcleo de dano e
reparo material de instalações existe, mas ainda faltam hazards naturais, clima e
desgaste, mobilidade/treinamento de força de trabalho (as vilas são todas farmer,
portanto o trabalho artesanal pode bloquear),
pedágio/trânsito/bloqueios/contrabando e decisões de IA real. Diplomacia com barganha
determinística já está integrada (ver medieval-diplomacy.md), mas sem IA real.
Migração temporal já é projetada, inclusive recuperação/retorno validada na rodada
E45, sem genealogia profunda ou difusão de conhecimento por migração.
Também faltam crédito/investimentos mais amplos, demografia profunda,
sucessão/disputa de autoridade, planos multissetoriais, pesquisa avançada/difusão,
campanhas, magia, criaturas e observatório completo. Evidência de execução
(contagens de teste, smokes e status da suíte) está centralizada em
docs/handoff/medieval-current-state.md; não repetir aqui.
O servidor principal e o observatório conectado já usam este runner.
Produção remunera trabalho real e recolhe imposto de renda conforme mandato,
com folhas e poupança visíveis no painel Finanças; ver medieval-economy.md.
Construção mensal precede produção, compartilha trabalhadores e só aumenta
capacidade após materiais e trabalho pagos. Revisão de investimento ocorre após
consumo e antes dos mercados/relatórios/compras; projetos recém-abertos só trabalham
no mês seguinte. Escassez bloqueia a obra, falha técnica aborta o salto.
A prova de fundação não encerra A1–A9, mesmo avançando um ano e salvando corretamente.
