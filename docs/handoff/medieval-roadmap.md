# Roadmap do fork medieval

Atualizado em 13/09/2026. Este é o plano de produto que substitui o roteiro
herdado de xianxia para o fork medieval. Este roadmap e
`docs/handoff/medieval-current-state.md`, ambos versionados, são a fonte
canônica do plano e do estado atual. `.agent/tasks/medieval-world-simulator/`
é apenas registro local de orquestração/retomada, não versionado e não
substitui nem complementa a autoridade destes dois documentos.

## Regras que permanecem inegociáveis

```text
estado canônico -> possibilidades enumeradas -> decisão do ator
-> revalidação pelo owner -> execução material -> fatos/deltas
-> conhecimento e memória -> novas possibilidades
```

- Nenhum evento é obrigatório por roteiro. Paz, trabalho e cooperação são tão
  válidos quanto crise, guerra ou desastre.
- IA, quando integrada, só escolhe entre affordances calculadas pela engine. Ela
  não inventa alvos, quantidades, poderes, fatos, autoridade, custos ou resultados.
- Decisão não transfere bens nem cria efeitos por si só. O owner revalida recursos,
  autoridade, tempo, rota, conhecimento e capacidade na execução.
- Atores só usam o que sabem por canais válidos; observatório pode ser onisciente,
  mas relato, crença e verdade canônica não são a mesma coisa.
- Salto mensal é o padrão quando o mundo está estável. Processamento diário só é
  escalado por situação material ativa: prazos, viagem, carga, campanha, cerco,
  ritual, investigação, ataque, crise de abastecimento ou projeto crítico.
- Save/load e rollback devem preservar estado, agenda, RNG, fatos e causalidade.
  Affordances transitórias não são persistidas.

## Ordem de execução

### 0. Estabilizar a fundação atual

Corrigir as duas falhas da suíte de diplomacia sem mascarar a política causal;
executar novamente testes focados, API, persistência, frontend e build. Registrar
o comando, a revisão, a seed e qualquer limite observado.

**Aceite:** a política não produz uma quebra artificial; fixtures respeitam a
imutabilidade; falha técnica nunca aparece como escolha estratégica.

### 1. Fechar economia e informação material

Completar preços e demanda locais, contratos de mercado, tarifas, bloqueios,
contrabando/detecção, efeitos de escassez sobre saúde/migração/descontentamento e
propriedade de patrimônio. Expor apenas relatórios autorizados aos atores.

**Aceite:** uma rota interrompida altera estoque, entrega e população; uma rota ou
acordo alternativo pode recuperar a situação sem uma batalha roteirizada.

### 2. Estratégia e diplomacia emergentes

Evoluir objetivos e planos verificáveis para proteção, recursos, influência e
território; integrar barganha autônoma, recusas, contrapartes, compromissos,
persuasão, informação imperfeita, espionagem, suborno e sabotagem. Traição requer
obrigação/confiança concreta e descoberta por canal causal.

**Aceite:** uma concessão pode surgir sem batalha; uma quebra deliberada é
rastreável, tem repercussão futura e não depende de uma cena obrigatória.

### 3. Conhecimento, produção e poder

Ampliar pesquisa para conservação, aço, pólvora, artilharia, vapor, logística,
barreiras e doutrina; implementar difusão por ensino, venda, roubo e migração.
Conhecimento não substitui instalação, operador, equipamento, manutenção ou
suprimento.

**Aceite:** uma descoberta + produção + treinamento muda uma negociação, defesa ou
campanha por fatores materiais observáveis.

### 4. Campanhas e controle territorial

Criar forças agregadas, recrutamento, manutenção, comando, reconhecimento,
posições, suprimento, táticas, retirada, cerco, interdição, ocupação e solução
política. QG e comando são capacidades de instituições, não bônus narrativos.

**Aceite:** força menor pode vencer por preparo verificável; mudar terreno,
informação, moral, fadiga, suprimento ou comando muda a explicação causal do
resultado. Ocupação sem guarnição e solução política não é controle duradouro.

### 5. Magia, criaturas e ação individual

Implementar escolas mágicas com custo, alcance, duração, recuperação e
contramedidas; rituais detectáveis/interrompíveis; criaturas com território,
necessidades, memória e decisões próprias. O dragão pode negociar, exigir,
recuar ou atacar conforme condições, sem ser uma catástrofe programada.

**Aceite:** ameaça ritual e defesa de vila admitem investigação/intervenção real;
um ataque de criatura afeta pessoas, instalações e decisões posteriores.

### 6. IA real, observabilidade e calibração

Adicionar provedores reais somente depois de as affordances, validações, limites de
orçamento e fallback determinístico estarem cobertos. Expandir o observatório para
mapa de controle/ocupação, rotas, forças, ameaças, disputas, planos, crenças e
cronologia investigável.

**Aceite:** rodar três seeds naturais por dez anos e cenários preparados para cada
vertical, com artefatos, auditoria causal e custo de IA registrados. Erros do
provider são visíveis e não deixam mutação parcial.

## Critério de conclusão

O projeto só se aproxima de concluído quando for possível criar, observar, salvar e
retomar mundos onde resultados diversos possam emergir de meios diversos — comércio,
conversa, estratégia, pesquisa, magia, criaturas ou conflito — e o observador possa
explicar materialmente por que aconteceram. Quantidade de eventos, commits, guerras
ou texto gerado não é métrica de mundo vivo.
