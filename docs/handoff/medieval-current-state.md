# Estado atual — Medieval World Simulator

Atualizado em 13/09/2026. Este documento descreve o WIP local que será publicado
na branch de trabalho; não é uma declaração de produto concluído.

## Visão que orienta o fork

O projeto deixa de ser um simulador xianxia e passa a ser um mundo medieval de
alta fantasia observado de cima. Personagens, instituições, grupos populacionais,
mercados, pesquisas, magia e criaturas devem agir a partir de capacidades,
necessidades, conhecimento, relações e recursos reais. Conflitos são uma
possibilidade importante de teste, mas não uma obrigação narrativa: cooperação,
comércio, crescimento pacífico e períodos estáveis também são resultados válidos.

Não existe diretor de história. Um dragão, uma torre mágica, uma guilda, uma casa
nobre ou uma vila só altera o mundo por ações implementadas e validadas. A prosa
explica fatos; nunca cria recursos, vitórias, mortes, obrigações ou consequências.

## O que já existe no WIP local

- Runtime medieval separado, configuração persistente e save schema 11; dados de
  execução usam namespace próprio e saves experimentais antigos são rejeitados.
- Calendário híbrido de 12 meses de 30 dias. Rotinas agregadas usam o salto mensal;
  agendas, prazos, viagem, carga e situações ativas podem exigir processamento por
  dia. Cada salto é transacional e preserva relógio, agenda, eventos e RNG.
- Cenário inicial `Vale das Três Coroas`, com 12 personagens relevantes e população
  em coortes (10.900 pessoas), três cidades e suas instalações/rotas. Isso é uma
  fundação, não o mapa final de todo o escopo proposto.
- Estados com owners separados para sociedade/população, economia, autoridade,
  conhecimento, estratégia, pesquisa e relações. Registros causais distinguem
  decisão, execução material e interpretação.
- Produção, estoques, contas, salários, imposto sobre renda, consumo doméstico,
  ajuda pública, trabalho, transporte de cargas, pedidos de abastecimento,
  compras/remessas e construção financiada.
- Pesquisa inicial, conhecimento institucional, ensino consentido, obras de
  aplicação e linhas produtivas preparadas para carvão, aço, motores e bombeamento.
- Núcleo de diplomacia: propostas, contrapropostas, aceitação sem transferência,
  obrigações de pagamento/ensino, prazos, expiração, quebra, dispensa e avisos
  privados. Cumprimento material ainda exige uma decisão nova e autorização atual.
- API `/api/v2`, observatório PT-BR e frontend Vue para mapa, cronologia, economia,
  pesquisa, obras, abastecimento, saves e inspeção causal.

## Evidência disponível e limites

Há ampla cobertura focada herdada do WIP para economia, agenda, pesquisa,
observatório e persistência. A última execução conhecida da suíte específica de
diplomacia retornou **21 aprovados e 2 falhas**. Portanto, não declarar a suíte
global verde nem publicar uma versão como validada.

As duas falhas conhecidas são de fronteira da política diplomática: um cenário de
quebra esperava o dia 101, mas a rotina material cumpriu a obrigação antes disso e
agendou o passo seguinte no dia 96; e uma fixture tenta alterar diretamente um
campo imutável (`capability_ids`). Elas precisam ser corrigidas por uma prova que
represente quebra genuína e por substituição imutável do estado, sem enfraquecer os
contratos do domínio.

## Lacunas explícitas

- Ainda não há provedor de IA real integrado às decisões do mundo. A política atual
  de abastecimento/barganha usa regras determinísticas; isso é deliberado para
  testes, não equivale a autonomia inteligente.
- Objetivos e planos estratégicos gerais, informação secreta, espionagem, suborno,
  sabotagem, persuasão e traição descobrível ainda não compõem uma vertical completa.
- Não há campanha territorial completa: contingentes, reconhecimento, comando,
  suprimento militar, posições, táticas, cerco, ocupação e acordo político posterior
  continuam pendentes.
- Magia é apenas uma direção arquitetural do produto; rituais, custos, detecção,
  proteção e contramedidas ainda não foram implementados como sistemas completos.
- Criaturas autônomas, ameaças dinâmicas e o dragão não existem no runtime atual.
- Demografia profunda, migração patrimonial, preços locais, tarifas, bloqueios,
  contrabando e calibração econômica de longo prazo continuam abertos.
- O observatório ainda não mostra campanha, criatura, estratégia geral ou todas as
  cadeias de informação. Testes de backend não substituem inspeção visual e mundos
  naturais de longa duração.

## Handoff Git

Este WIP está sendo preparado a partir da branch local `codex/medieval-foundation`.
O destino autorizado é uma branch remota exclusiva, `codex/medieval-remote`, no
repositório de origem. Nenhuma alteração deve ser enviada à `main`, mesclada ou
publicada como release por este handoff. Arquivos de cache, `web/dist-medieval` e
`.test-data` não pertencem ao commit.
