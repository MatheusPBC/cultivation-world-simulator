# Pesquisa e aplicação de técnicas

Implementação parcial da etapa tecnológica, não encerramento da árvore ou da meta.
O catálogo contém irrigação, rotação, metalurgia, aço, vapor, treino de campo,
cerco, fortificação, logística e barreiras defensivas. Os recortes abaixo preservam provas históricas;
o estado atual e suas limitações estão em `docs/handoff/medieval-current-state.md`.

## Fronteiras e execução

ResearchState possui catálogo versionado e projetos; KnowledgeState possui o
conhecimento por instituição. Economia continua dona de estoques, salários, contas,
receitas e obras. O mapa possui as instalações. O save medieval atual usa schema 67
(Economy 15, Research 3), rejeita schemas anteriores e preserva os arquivos
antigos sem migração ou sobrescrita.

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
Venda V1 é uma transferência bilateral paga: o comprador precisa de uma
instalação própria capaz, pré-requisitos e saldo; o detentor recompõe e aceita a
mesma affordance, e o pagamento econômico precede o recibo de conhecimento.
O vendedor mantém seu conhecimento e a aplicação posterior ainda exige obra e
materiais próprios.
Roubo V1 é um caminho separado e material: a instituição precisa de um agente
nomeado por ofício atual, presença física no assentamento, sighting vigente da
técnica, relatório atual da instalação e produção recente de uma linha cuja
receita operacional exige a técnica do detentor. Conhecimento ou obra parada
não abre a affordance. O resultado engine-owned é `success`,
`failure` ou `discovered`; somente `success` cria conhecimento `stolen` a partir
do recibo canônico do detentor. Finding, observação e decisão ficam privados e
persistidos; nenhum resultado inventa técnica, receita, capacidade ou efeito.
Se ensinar torna conhecido um experimento ativo, ele é encerrado sem trabalho fictício.

`field_drill` é uma aplicação defensiva datada: conhecimento adquirido torna
disponível a opção de treinar uma coluna própria, mas não altera sua força.
A decisão consome ferramentas locais; a coluna precisa completar três dias
estacionários e abastecidos. Só então `field_strength` aplica o bônus limitado
àquela coluna. `siegecraft` exige treino próprio posterior; `field_logistics`
exige treino próprio para ampliar bagagem física e limite de provisões, sem
criar alimentos. Combate e bagagem citam os fatos de aplicação, não prosa.

Quando um experimento autorizado tem líder, materiais, caixa e instalação
válidos, mas nenhum assistente disponível, seu recibo emite `labor_shortfall`
tipado. A administração recebe uma demanda datada; um grupo elegível recebe
oferta privada com ocupação, quantidade e bolsa calculadas pela engine. Só uma
decisão atual desse grupo paga a bolsa e reserva os participantes por 30 dias;
Society conclui a mudança de ocupação, sem criar habitantes. Pesquisa precisa
de novo fechamento, recursos e salário para avançar. Na prova militar, os
soldados locais saíram por mobilização paga; um grupo civil aceitou virar
`soldier` e a pesquisa avançou apenas depois da conversão. Esta é reposição de
assistentes de pesquisa, não recrutamento geral de campanha nem treinamento de
campo da coluna.

`defensive_barriers` depende de `fortification`. Conhecimento apenas habilita
uma obra no próprio assentamento; a paliçada só existe após madeira, pedra,
ferramentas, trabalhadores e salários efetivos. Um cerco lê a paliçada Map-owned
do defensor apenas se estiver íntegra e operante; sua resistência limita o
desgaste diário da guarnição em uma unidade, sem cancelar a fome ou criar
soldados. O fato do cerco cita o último fato material do site. Dano abaixo de
0,50 remove esse efeito; um maintainer autorizado pode restaurá-lo por obra
de reparo com insumos e pagamento reais. A prova atual usa conhecimento e dano
como premissas explícitas de fixture, não descoberta natural ou hazard autônomo.

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

Conservação, pólvora e artilharia continuam no plano integral;
logística de coluna já tem aplicação material. Difusão por migração possui uma
fatia de apprenticeship pago e datado; ensino institucional geral ainda é
imediato e não possui curso/custo. Segredo e vínculos estratégicos amplos com
diplomacia/campanhas continuam parciais. O catálogo é finito
por versão e expansível por conteúdo, sem inventar regras durante execução.
Demografia, mobilidade de especialistas, recrutamento militar fora da falta de
assistentes de pesquisa e calibração financeira seguem abertas. O mundo inicial inclui pequenas coortes
com ocupação militar como premissa populacional, sem criar destacamento, salário ou
ordem de marcha automática; elas preservam o total de habitantes do catálogo.
