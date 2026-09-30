# Execução na VPS

Mantenha o Compose ligado ao loopback (`CWS_BIND_IP=127.0.0.1`). O backend fica
na porta 8002 e o frontend na 8123 por padrão; ajuste apenas
`CWS_BACKEND_PORT`/`CWS_FRONTEND_PORT` quando necessário. Não amplie TrustedHost
ou CORS para o endereço da VPS.

Use um túnel SSH na estação do operador:

```bash
ssh -N -L 8123:127.0.0.1:8123 -L 8002:127.0.0.1:8002 user@vps
```

Na VPS:

```bash
test -f .env || cp .env.example .env
docker compose build
docker compose up -d
curl -fsS http://127.0.0.1:8123/api/health
curl -fsS http://127.0.0.1:8002/api/v2/query/status
```

`./docker-data` é montado como `/data` (`CWS_DATA_DIR=/data`); configurações,
segredos e saves ficam fora da imagem e do Git. Faça backup antes de alterar
saves e valide uma cópia antes de qualquer rollback. O fluxo Medieval
usa `/api/v2/command/*` para criar, avançar, pausar/retomar, salvar e carregar,
e `/api/v2/query/*` para consulta. Os caminhos antigos `/api/v1` e
`/api/settings` não são contratos de deploy. Saves xianxia e schemas anteriores
ao schema 84 são rejeitados e preservados, sem sobrescrita nem migração.

O Compose monta Node (`/usr/bin/node`) e o módulo Codex
(`/usr/lib/node_modules/@openai/codex`) como volumes somente de leitura, além
do diretório OAuth dedicado
(`/home/codex-agent/.codex` em `/codex-home`) gravável para refresh da sessão
quando o provider estiver configurado. O diretório OAuth deve permanecer privado
e fora do Git. Esses caminhos podem ser ajustados para outra VPS. Nunca copie
`auth.json` ou outro material OAuth para o repositório ou para a imagem.
