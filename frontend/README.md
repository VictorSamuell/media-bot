# Painel Media Saver

Interface React + TypeScript + Vite conectada à biblioteca SQLite do bot.
Tema escuro inspirado na Steam, capas por nome, busca, filtros, ordenação e download.
Favoritos são temporários e duram até sair ou recarregar a página.

## Configurar o acesso local

No `.env` da raiz do projeto, acrescente:

```dotenv
PANEL_OWNER_ID=seu_id_numerico_do_telegram
PANEL_ACCESS_KEY=sua_chave_aleatoria_com_pelo_menos_32_caracteres
```

O `/start` do bot informa seu ID. Gere uma chave separada do token do Telegram:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copie o resultado para `PANEL_ACCESS_KEY` e use essa chave na tela de entrada.
Ela fica apenas na memória da página e é enviada no cabeçalho Authorization.
O proprietário é definido no servidor; a página não pode escolher outro ID.
Nunca publique o `.env` ou a chave. Essa configuração é para uso local de um dono;
acesso remoto e contas múltiplas exigem uma etapa própria de autenticação e HTTPS.

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

Abra o endereço informado pelo Vite e entre com sua chave.
O Vite encaminha `/api` para a API local na porta 8000. O bot não precisa estar
ligado para consultar arquivos já salvos. Use Atualizar após salvar algo novo.
Uma biblioteca vazia é exibida vazia, sem exemplos ou fallback fictício.
O download retorna o arquivo original com seu nome salvo.

## Verificar

`npm run build` verifica TypeScript e gera `dist/`. O build sozinho não inclui a API
nem o proxy do servidor de desenvolvimento.

A integração atual permite listar e baixar arquivos. Renomear e excluir continuam
pelo bot. As capas são representações dos nomes, não miniaturas extraídas da mídia.
