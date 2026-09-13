# Pesquisa e aplicação de técnicas

Implementação parcial da etapa 4, não encerramento da árvore tecnológica ou da meta.
O catálogo contém irrigação, metalurgia, aço e engenharia a vapor; projetos mensais podem surgir
pela política determinística das instituições. Não há chamadas de IA nessa política.

## Fronteiras e execução

ResearchState possui catálogo versionado e projetos; KnowledgeState possui o
conhecimento por instituição. Economia continua dona de estoques, salários, contas,
receitas e obras. O mapa possui as instalações. Save schema11/economy6 persiste esses
contratos, rejeita schemas experimentais1–10 e preserva os arquivos antigos.

O patrocinador e o especialista registram consentimentos independentes, exatos e
atuais. Pesquisa exige autoridade research/trade/supply, instalação capaz e íntegra,
estoque/conta próprios, especialista vivo/local/qualificado e pré-requisitos conhecidos.
Há um projeto ativo por instituição e por especialista. Viagem/treino/estudo
concorrente impede pesquisa. Revalidação ocorre em cada fechamento mensal.

As técnicas atuais exigem seis unidades; habilidade limita o ritmo, até duas por
mês. Os insumos são próprios de cada técnica (madeira/ferramentas nas raízes,
ferro/carvão/ferramentas no aço, aço/carvão/ferramentas no vapor). Cada unidade
ocupa dois assistentes; um líder
nomeado adicional participa do período, incluído no grupo populacional, não contado
duas vezes. Salários saem da conta patrocinadora. Pesquisa, construção e produção
dividem a disponibilidade de trabalhadores; nenhum ponto é ganho sem insumos e caixa.
Materiais restantes entram uma única vez nas metas de abastecimento e reservas.

Descobrir cria conhecimento apenas para o patrocinador. Ensino exige dois novos
consentimentos atuais, conhecimento do professor, pré-requisitos do aluno e mandatos
de pesquisa; não cria instalações nem equipamentos. Atualmente é uma transferência
institucional imediata, sem curso, deslocamento, preço ou política autônoma de ensino.
Se ensinar torna conhecido um experimento ativo, ele é encerrado sem trabalho fictício.

Aplicação exige uma obra própria: canais (alimento100→120 por lote) ou fornos
(ferro5→7). Cada adaptação custa20madeiras,10ferramentas e40salários em duas etapas
mensais se houver recursos/artesãos. Só a conclusão troca a receita; não aumenta a
capacidade nominal. Conhecimento roubado ou recebido nunca substitui esse trabalho.

## Linhas industriais e vapor (schema10/economy6)

Além das adaptações, uma obra pode criar uma linha produtiva adicional no mesmo
site. Ela tem ID/capacidade/receita próprios, mas compartilha estoque, conta patronal,
armazenamento e trabalhadores. A mina original não é substituída por uma carvoaria.
Não há produção antes da conclusão. O executor impede duas âncoras de construir a
mesma linha no mesmo site; o save exige a linha e seu recibo de comissionamento.

Metalurgia habilita fornos de carvão; aço exige metalurgia, e engenharia a vapor
exige aço. Cada nova linha custa 12 madeiras, 6 ferramentas e 24 salários brutos,
com seis unidades de obra e no máximo três por fechamento mensal. Capacidade
inicial: dez lotes, sujeitos aos recursos e trabalhadores realmente disponíveis.

| Linha | Insumos por lote | Produto por lote | Trabalhadores |
| --- | --- | --- | --- |
| Fornos de carvão | 2 madeiras | 1 carvão | 2 |
| Aciaria | 3 ferros, 1 carvão | 2 aços | 4 |
| Oficina de motores | 2 aços, 2 ferros, 1 carvão, 1 ferramenta | 1 motor a vapor | 6 |

As receitas exigem conhecimento do proprietário também durante a operação.
Novas linhas entram nas metas de insumos, sem criar estoques ou pessoas extras.
Bombeamento mecanizado adapta a mina de alto rendimento: consome seis motores,
12 madeiras, seis ferramentas e 24 salários durante a obra. Depois, cada lote
consome uma madeira e um carvão, emprega oito trabalhadores e produz 12 ferros.
Sem combustível a produção para. Operadores especializados, desgaste/manutenção
de equipamento e aplicações militares ainda não estão implementados.

Prova preparada em `test_medieval_industry.py`: estoques iniciais ampliados e
especialista Ofícios40, um complexo isolado; pesquisa e construção não são
resultados naturais do preset. Carvão entra no150, aço no300, motores no450 e
bombeamento no570. O teste reduz a capacidade de outras linhas explicitamente,
esgota carvão por produção real, comprova parada e retoma com carvão no870.
Essa escolha operacional é uma preparação de teste, não um comando público.
Moeda total76000, balanço de todos os recursos e save/load equivalente são auditados.

Smoke natural schema10, seed73/360dias: irrigação/metalurgia concluídas, aço
impedido por carvão; os fornos de carvão ficam em3/6 sem caixa. Nenhuma nova linha
foi concluída nesse mundo. São310saltos,72pedidos e11084eventos salvos; continuação361
equivalente com11096eventos. Conservação não prova equilíbrio: saúde596–1000 e
tesouros de Valedouro/Escárlia zerados permanecem limitações conhecidas.

## Observação e evidência

GET `/api/v2/query/research` e o snapshot único do observatório expõem catálogo,
projetos e conhecimento. O painel Pesquisa mostra instituição, especialista,
instalação, progresso, bloqueio, data e causa. Finanças distingue salários de
pesquisa/obras/produção e mostra rendimento prometido separado de capacidade atual.
Linhas adicionais mostram capacidade própria, inicialmente zero, e capacidade
prevista até a conclusão; folhas produtivas nomeiam os produtos da linha atual.

Testes preparados em test_medieval_research.py cobrem descoberta, ensino, aplicação
produtiva, ausência de requisitos, mão de obra, demanda, save/load e rollback.
Proveniência exige recibo do próprio projeto/conhecimento, técnica e dono coerentes.

Smoke histórico schema9, seed73,360dias: irrigação e metalurgia concluídas no210; irrigação
impedida por falta de artesãos e fornos em5/10 sem caixa no360. Não houve melhoria
produtiva automática.76000moedas e todos os recursos contabilizados; retomada361
equivalente. Cenário preparado com especialista mais hábil conclui pesquisa90 e
adaptação150, depois produz420ferro (60lotes×7).

## Trabalho ainda necessário

Conservação, pólvora, artilharia, barreiras e logística continuam no
plano integral. Também faltam segredo, venda/roubo, difusão por migração, ensino com
tempo/custos e vínculos estratégicos com diplomacia/campanhas. O catálogo é finito
por versão e expansível por conteúdo, sem inventar regras durante execução.
Demografia, mobilidade de especialistas e calibração financeira seguem abertas.
