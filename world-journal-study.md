# Estudo: Diário do Mundo e leitura de histórias massivas

## Objetivo

Permitir que o jogador entenda rapidamente:

- o que mudou no mundo;
- quem está fazendo algo importante;
- o que cada personagem acompanhado quer e pensa;
- quais histórias estão em andamento;
- onde encontrar o registro completo, sem perder a linha do tempo atual.

A proposta preserva a linha do tempo existente e a transforma em um dos modos de um mesmo **Diário do Mundo**.

## Diagnóstico do produto atual

A base técnica já é boa:

- eventos têm data, participantes, seitas relacionadas e marcadores `is_major` e `is_story`;
- a API já oferece paginação e filtros por personagem, seita e importância;
- personagens já possuem ação atual, pensamento, objetivos curto/longo e relações;
- desktop e celular reutilizam a mesma lista de eventos.

O problema é a hierarquia da informação. Eventos rotineiros, fatos decisivos e histórias longas disputam a mesma atenção. O jogador consegue descobrir tudo, mas precisa ler quase tudo.

No save auditado havia 605 eventos em 87 meses:

- 54 eventos maiores, aproximadamente 9%;
- 33 histórias, aproximadamente 5%;
- 538 eventos sem `event_type`, aproximadamente 89%;
- 598 eventos sem `render_key`, aproximadamente 99%.

Isso também mostra que classificar eventos antigos lendo frases no frontend seria frágil. Eventos antigos devem continuar acessíveis na linha do tempo; eventos novos precisam nascer com metadados estruturados.

## O que as referências ensinam

### Dwarf Fortress e Legends Viewer

O modo Legends organiza uma massa enorme de história por entidades — personagens, locais, civilizações e artefatos — e permite navegar pelos vínculos entre elas. O Legends Viewer acrescenta busca, filtros, ordenação, paginação, mapas e telas de visão geral.

Aplicação aqui: nomes, seitas, regiões e objetivos devem ser pontos de navegação. O jogador deve poder partir de um fato, abrir o personagem e seguir a história relacionada, em vez de depender apenas de uma lista cronológica.

Fontes: [Dwarf Fortress Wiki: Legends](https://dwarffortresswiki.org/index.php/Legend), [LegendsViewer](https://github.com/Kromtec/LegendsViewer), [LegendsViewer-Next](https://github.com/Kromtec/LegendsViewer-Next).

### RimWorld

O histórico combina gráficos, marcadores com natureza positiva/negativa/hostil, intervalos de tempo e um arquivo de mensagens. Nem tudo vira alerta; alguns fatos podem ser fixados pelo jogador.

Aplicação aqui: período selecionável, poucos sinais visuais consistentes e personagens acompanhados são mais úteis que contadores de “não lidos” em cada evento.

Fonte: [RimWorld Wiki: History](https://rimworldwiki.com/wiki/History).

### Football Manager

A UI recente usa a regra “visão geral primeiro, detalhe ao aprofundar”: blocos pequenos mostram o estado atual e abrem telas mais completas. O portal reúne acontecimentos, notícias e tarefas, mas permite filtrar o fluxo.

Aplicação aqui: o Diário deve começar com respostas curtas e acionáveis e usar os painéis detalhados já existentes quando o jogador tocar em um personagem, seita ou região.

Fonte: [Football Manager 26: Reimagined User Interface](https://www.footballmanager.com/fm26/features/fm26s-reimagined-user-interface).

### Stellaris

O outliner organiza listas por categorias recolhíveis e personalizáveis. Alertas usam urgência e persistência; objetivos em andamento ficam separados do ruído cotidiano.

Aplicação aqui: “precisa da sua atenção” e “história em andamento” não devem ser tratados como simples eventos cronológicos.

Fonte: [Stellaris Wiki: Main interface](https://stellaris.fandom.com/wiki/Main_interface).

### Visualização de grandes sequências

A literatura de visualização converge para **visão geral primeiro, filtro/zoom depois e detalhes sob demanda**. Visões coordenadas em níveis funcionam melhor que uma única lista tentando cumprir todos os papéis.

Fontes: [Sequen-C: Multilevel Overview of Temporal Event Sequences](https://arxiv.org/abs/2108.03043), [A Survey on Temporal Event Sequence Visualization](https://arxiv.org/abs/2006.14291), [Shneiderman: The Eyes Have It](https://www.cs.ubc.ca/~tmm/courses/547-14/slides/Sep22-Shneiderman-4x4.pdf).

## Proposta: um Diário, quatro modos

O mesmo painel terá um seletor:

`Agora | Em foco | Histórias | Linha do tempo`

### 1. Agora — resposta rápida

É a tela padrão. Resume um período escolhido: `Este mês | 3 meses | 1 ano`.

Ordem sugerida:

1. **Mudanças importantes** — no máximo três a cinco fatos, com causa e consequência curtas.
2. **Em andamento** — conflitos, missões, objetivos e oportunidades ainda abertos.
3. **Quem mudou** — personagens que trocaram de objetivo, avançaram, morreram ou alteraram uma relação relevante.
4. **Atividade do mundo** — números agregados para dar escala sem listar cada repetição.

Exemplo de cartão:

> **Qi Hanzhou julgou um roubo na seita**
>
> Descobriu que um mercador comprava segredos usando uma dívida antiga.
>
> **Resultado:** o talismã voltou e o mercador foi eliminado.
> `Qi Hanzhou` `Seita do Som Ceifador` `Ver história`

O resumo deve ser determinístico, construído dos eventos e estados reais. Não deve usar LLM por padrão.

### 2. Em foco — pessoas que o jogador acompanha

O jogador fixa de três a cinco personagens. Cada cartão mostra:

- ação atual;
- pensamento atual;
- objetivo de curto prazo;
- objetivo de longo prazo;
- última mudança relevante;
- botão para abrir o painel completo.

Isso responde “o que cada um está fazendo e querendo” sem exigir procurar o personagem em toda visita.

### 3. Histórias — narrativa sem perder o fato

Mostra somente eventos narrativos. Cada história aparece recolhida com:

- título factual;
- participantes e lugar;
- resultado conhecido;
- trecho inicial;
- botão `Ler história completa`;
- ligação explícita com o evento factual que originou a narrativa.

O texto literário continua existindo, mas nunca é a única forma de saber o que ocorreu.

### 4. Linha do tempo — registro completo preservado

Mantém a lista atual e sua paginação. Evoluções posteriores:

- agrupamento visual por mês;
- busca textual;
- filtro por categoria;
- filtro de intervalo;
- opção de mostrar/ocultar atividades rotineiras;
- links para personagem, seita, região e história relacionada.

## Wireframes

### Desktop

```text
┌──────────────── Diário do Mundo ────────────────┐
│ [Agora] [Em foco] [Histórias] [Linha do tempo] │
│ Período: [Este mês v]                          │
├─────────────────────────────────────────────────┤
│ 3 mudanças importantes                         │
│ ┌ Qi Hanzhou julgou um roubo ────────────────┐ │
│ │ causa curta · resultado curto · abrir       │ │
│ └─────────────────────────────────────────────┘ │
│ Em andamento                                    │
│ • missão de Sima Lei ...                        │
│ Quem mudou                                      │
│ • Bai Ziyan redefiniu seu objetivo ...          │
└─────────────────────────────────────────────────┘
```

O Diário ocupa a barra lateral atual. Clicar numa entidade usa os painéis de detalhe existentes e, quando aplicável, centraliza o mapa.

### Celular

```text
┌────────────── Diário ──────────────┐
│ Agora | Em foco | Histórias | Linha│  <- fixo
│ [Este mês v]                       │
│                                    │
│ Mudanças importantes               │
│ ┌────────────────────────────────┐ │
│ │ fato                            │ │
│ │ causa                           │ │
│ │ resultado                 [>]   │ │
│ └────────────────────────────────┘ │
│                                    │
│ conteúdo rolável                   │
├────────────────────────────────────┤
│ Mundo       Avatares       Roleplay│  <- menu atual
└────────────────────────────────────┘
```

Os quatro modos ficam dentro da aba atual do Diário/Mundo; não viram novos itens no menu inferior. A área rolável deve respeitar o menu e a safe area do aparelho.

## Regras de produto

- A UI não inventa participantes, causas ou resultados.
- Um resumo sempre aponta para os fatos que o sustentam.
- Cor comunica categoria ou urgência, nunca decoração aleatória.
- Atividades repetitivas são agregadas; mortes, avanços, conflitos, mudanças de objetivo e relações relevantes ganham destaque.
- Não criar badge de “não lido” para cada evento. Isso transforma a simulação em caixa de entrada.
- O período explícito vem antes de “desde a última visita”. Sincronizar leitura entre desktop e celular exigiria um cursor persistido no servidor; `localStorage` não resolve o uso multiplataforma.
- LLM pode existir depois como botão opcional `Narrar este período`, usando eventos fixos como fonte e resposta cacheada. Não participa da classificação nem decide o que aconteceu.

## Dados e arquitetura necessários

### Taxonomia de eventos

Todo evento novo deve ter um `event_type` estável. Um registro central mapeia esse tipo para:

- categoria: cultivo, relação, conflito, exploração, recurso, seita, objetivo, vida/morte ou mundo;
- importância padrão;
- ícone;
- fase, quando houver: início, progresso ou resultado;
- templates i18n de título e resumo.

Exceções podem elevar a importância de uma ocorrência, mas a regra comum vive no registro. Não classificar eventos interpretando o texto renderizado.

### Ligação entre fato e história

Eventos `is_story` precisam de `source_event_id` apontando para o fato que expandem. Isso permite mostrar resumo, resultado e narrativa como níveis da mesma ocorrência.

### Consulta do Diário

Criar uma consulta de leitura, por exemplo `GET /api/v1/query/world/journal`, que recebe período e devolve:

- destaques ordenados deterministicamente;
- assuntos em andamento;
- mudanças de personagens;
- agregados de atividade;
- cartões dos personagens fixados;
- IDs dos eventos-fonte.

O serviço de consulta compõe eventos e estado atual. O frontend apenas apresenta o resultado. Isso evita várias requisições por personagem e mantém celular e desktop coerentes.

### Relevância determinística

A ordem considera:

1. importância definida pelo evento;
2. marcadores `is_major` e `is_story`;
3. impacto verificável: morte, avanço, guerra, descoberta, mudança de objetivo ou relação;
4. recência;
5. redução de repetição por tipo e participante.

Não usar LLM ou modelo opaco para calcular relevância.

## Plano de implementação

1. **Formalizar a taxonomia de eventos.** Criar o registro central e exigir `event_type` em todo evento novo. Verificar com testes que nenhuma fábrica/emissão nova persiste tipo vazio.
2. **Ligar narrativa ao fato.** Adicionar `source_event_id` aos eventos de história e aos DTOs. Verificar que uma história sempre abre seu fato-base e seus participantes reais.
3. **Criar a consulta do Diário.** Implementar serviço e endpoint para períodos fechados, com destaques, assuntos, mudanças e agregados determinísticos. Verificar ordenação e ausência de entidades inventadas em fixtures.
4. **Criar o shell compartilhado.** Implementar `WorldJournalPanel` com os quatro modos e incorporar a timeline atual como filho, sem reescrevê-la. Verificar desktop e celular com o mesmo estado selecionado.
5. **Entregar o modo Agora.** Implementar seletor de período, cartões de mudanças, andamento e atividade. Verificar o resultado contra um save real e eventos conhecidos.
6. **Entregar o modo Em foco.** Permitir fixar até cinco personagens e mostrar ação, pensamento, objetivos e última mudança. Persistir a preferência no backend para funcionar em celular e desktop.
7. **Entregar Histórias e evoluir a timeline.** Agrupar fato e narrativa; adicionar agrupamento mensal, categoria, período e busca ao registro completo. Verificar combinações de filtros com paginação.
8. **Validar compreensão e escala.** Rodar testes backend/frontend, build, telas de 360/390 px e desktop, fixture com ao menos 10 mil eventos e um teste com jogador: identificar três mudanças importantes e o objetivo de um personagem em menos de um minuto.

## Recorte recomendado para a primeira entrega

A primeira versão jogável deve terminar no passo 5. Ela já resolve a maior dor: entender rapidamente o mundo sem perder a linha do tempo. `Em foco`, `Histórias` e filtros avançados entram sobre uma base funcionando, sem segurar o valor inicial por uma implementação grande.

## Critério de sucesso

Ao abrir o jogo depois de vários meses simulados, o jogador deve conseguir, sem ler a timeline inteira:

- dizer as três principais mudanças do período;
- apontar o que está em andamento;
- abrir as evidências de qualquer resumo;
- entender o estado e o objetivo dos personagens acompanhados;
- acessar todo o histórico original quando quiser investigar.
