# Painel Media Saver

Interface React + TypeScript + Vite conectada à biblioteca SQLite do bot.
Tema escuro inspirado na Steam, capas por nome, busca, filtros, ordenação e download.
Favoritos são temporários e duram até sair ou recarregar a página.

## Entrar pelo Telegram

Envie `/login` ao bot em conversa privada. Cole no painel o código recebido.
O código vale 5 minutos, só funciona uma vez e um novo pedido invalida o anterior.
A sessão vale 2 horas; Sair a revoga no servidor. A sessão fica salva neste navegador e é restaurada ao recarregar ou reabrir o painel,
sem renovar o prazo. Use Sair em computadores compartilhados. Não há chave manual nem ID digitado.

Bot e API precisam usar a mesma pasta `data/`. O arquivo `auth.sqlite3` contém
apenas hashes dos códigos e das sessões, com proprietário e prazo de validade.
O limite inicial é global: 30 tentativas de entrada por minuto. Não depende de
cabeçalhos de IP enviados pelo navegador. Esse limite pode bloquear temporariamente
todos os logins em caso de abuso; proteção por usuário/rede é uma evolução futura.

`PANEL_OWNER_ID` e `PANEL_ACCESS_KEY` não são mais usados e podem ser removidos do `.env`.
`ALLOWED_USER_IDS` continua restringindo quem pode pedir códigos pelo bot.

## Executar

Na raiz, com o ambiente virtual ativo:

```powershell
python -m uvicorn media_bot.api:app --host 127.0.0.1 --port 8000
```

Em outro terminal, também a partir da raiz:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abra o endereço informado pelo Vite e entre com o código do Telegram.
O Vite encaminha `/api` para a API local na porta 8000. O bot precisa estar ligado para emitir novos códigos; após entrar, consultas usam a API. Use Atualizar após salvar algo novo.
Uma biblioteca vazia é exibida vazia, sem exemplos ou fallback fictício.
O download retorna o arquivo original com seu nome salvo.

## Verificar

`npm run build` verifica TypeScript e gera `dist/`. O build sozinho não inclui a API
nem o proxy do servidor de desenvolvimento.

A integração atual permite listar, baixar e renomear arquivos. Abra os detalhes,
clique em Renomear arquivo e salve o novo nome, incluindo a extensão. A alteração
também aparece no bot porque ambos usam a mesma biblioteca. Excluir continua pelo bot. As capas são representações dos nomes, não miniaturas extraídas da mídia.

## Publicação

Veja [o guia da Cloudflare Pages](../docs/cloudflare.md). O desenvolvimento local
continua usando o proxy do Vite; publicações usam `VITE_API_BASE_URL` com HTTPS.
