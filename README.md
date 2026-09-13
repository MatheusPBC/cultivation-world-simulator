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
separada da origem. Saves estão em `saves/medieval/*.mws`, schema 19. Saves
xianxia e schemas experimentais anteriores (18 e abaixo) são rejeitados e
preservados, sem sobrescrita nem migração.

Migrações são jornadas temporais canônicas: residentes permanecem na coorte de
origem enquanto `present_population` diminui. A provisão usa `MoneyAccount` e
pantry próprio, com transferência bilateral entre donos, não consumo genérico.

Instalações têm integridade e operabilidade no Map. Reparos são obrigações
econômicas explícitas, com projetos e lotes decididos, materiais e salários
pagos a partir da força de trabalho mensal compartilhada. O catálogo conhece
somente farm, mine, port, workshop, forest e mountainpass; a recuperação é
gradual (até 0,10 por lote) e não reativa automaticamente uma instalação com
`enabled=false`.

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
