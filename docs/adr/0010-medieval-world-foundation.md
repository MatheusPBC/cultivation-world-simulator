# Fundação do fork medieval

Status: em implementação. A entrada pública do aplicativo ainda precisa migrar.

## Decisão

O produto-alvo usa `MedievalWorld`: relógio absoluto, agenda, gerador aleatório
por mundo, sociedade e mapa físico. Não há opção planejada para alternar regras
xianxia/medievais. O executor e o frontend herdados serão substituídos durante
a migração; os testes de caracterização existentes continuam úteis até lá.

`SocietyState` possui identidades de personagens, governos, organizações,
assentamentos e grupos populacionais. Cada personagem vivo referencia um grupo
e já está incluído na sua contagem. Recrutar transfere pessoas de uma atividade
para `soldier`; migração altera residência sem criar pessoas; morte remove a
pessoa do grupo e preserva o personagem arquivado. Nenhuma dessas operações
autoriza a si mesma: os futuros executores revalidam decisão, recursos e
autoridade e registram seus eventos/deltas antes do commit do salto.

Identidade de governo ou organização não é prova de autoridade. Títulos,
habilidades ou filiação também não a concedem. A integração das instituições,
cargos, conhecimento e memória ainda está pendente, mantendo owners distintos.

Administração territorial, ocupação física e reivindicação são campos distintos.
A operação de ocupação não troca administração nem remove reivindicações.
Não existe cópia de população em `SettlementRegion`: suas consultas leem a
sociedade. A presença temporária de um personagem pode diferir de sua residência.

O padrão escolhido pelo usuário em 2026-09-13 é **12 personagens relevantes**,
substituindo os 60 originais. A população restante continua em grupos. O número
é configurável sem alterar a população total; limites de chamadas/tokens de IA
serão uma configuração independente. Criar personagens não chama um provider.

## Espaço e conteúdo

`Map`, `GeographyLayer`, `Route` e `InfrastructureSite` são reaproveitados.
O preset schema v6 `vale-das-tres-coroas` está no mesmo catálogo físico.
O loader medieval associa suas regiões à sociedade, sem carregar metadados de
seitas, cavernas de cultivo ou dinastia. O catálogo em PT-BR contém três
governos, três cidades, cinco vilas, oito organizações e 10.900 pessoas.
Nove rotas terrestres/fluviais e oito instalações têm referências verificadas.
A geografia inicial é esquemática e ainda exige refinamento visual.

## Limites atuais e próximas entregas

- `create_medieval_world()` já compõe sociedade e mapa; ainda não é a entrada
  usada pelo servidor/frontend. O catálogo geral já lista o novo preset, mas
  selecioná-lo pelo fluxo xianxia herdado ainda não constitui uma criação válida.
- A serialização de sociedade é estrita e testada em JSON. Ainda faltam o save
  medieval completo com produto/schema próprios, RNG e SQLite associado.
- O calendário herdado recebeu proteção contra perda de prazos e rollback
  testado. Seus callbacks não podem confirmar IO externo, e o checkpoint ainda
  precisa suportar explicitamente o RNG por mundo do novo `MedievalWorld`.
- Faltam commit causal por salto, fases mensais medievais e situações de domínio.
- A fundação não satisfaz A1 nem as demais provas do plano. Suíte completa,
  interface, simulações de dez anos e execução limitada de IA continuam pendentes.
