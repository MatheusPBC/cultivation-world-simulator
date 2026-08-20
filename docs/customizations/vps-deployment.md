# Execucao na VPS

## Topologia

O Compose executa dois servicos:

- `backend`, na porta 8002;
- `frontend`, na porta 8123, com proxy `/api` para o backend.

O bind e controlado por `CWS_BIND_IP`. Copie `.env.example` para `.env` e use um endereco
privado da VPS, como o IP Tailscale. O `.env` real nao deve ser commitado.

```bash
cp .env.example .env
```

## Persistencia

`./docker-data` e montado como `/data` no backend. Configuracoes, segredos e saves de producao
permanecem fora da imagem e fora do Git. Antes de alterar um save, crie backup e valide uma
copia.

## Preparar OAuth do Codex

O host precisa ter Node e Codex CLI instalados e uma sessao OAuth valida em um diretorio
dedicado. O Compose monta:

- `/usr/bin/node` como somente leitura;
- `/usr/lib/node_modules/@openai/codex` como somente leitura;
- `/home/codex-agent/.codex` em `/codex-home`.

Esses caminhos podem ser ajustados para outra VPS, mas nunca copie `auth.json` ou outro
material OAuth para o repositorio ou para a imagem.

## Build e atualizacao

Para atualizar toda a aplicacao:

```bash
docker compose build
docker compose up -d
```

Para uma mudanca exclusivamente visual:

```bash
docker compose build frontend
docker compose up -d --no-deps frontend
```

A segunda forma nao reinicia o backend nem altera o estado do mundo.

## Verificacao

```bash
docker compose ps
curl -fsS "http://${CWS_BIND_IP}:8123/api/v1/query/runtime/status"
```

Confirme:

- frontend e backend `healthy`;
- `status` igual a `ready`;
- `is_paused` no estado esperado antes de abandonar a sessao;
- `llm_check_failed` falso quando o provider Codex estiver configurado.

O jogo nao deve depender de um navegador conectado para manter o container vivo. Pausa e
retomada sao comandos explicitos do runtime e devem ser verificadas pela API.
