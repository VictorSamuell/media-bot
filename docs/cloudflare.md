# Publicar o frontend na Cloudflare Pages

O frontend está preparado, mas a publicação funcional depende de uma URL HTTPS
para a API. Nenhum túnel é iniciado automaticamente e nenhuma porta é aberta.
Bot, API e arquivos continuam no computador; desligá-lo interrompe essas funções.

## Pages com GitHub

Conecte o repositório no Cloudflare Pages e configure:

- Diretório raiz: `frontend`
- Comando de build: `npm run build`
- Diretório de saída: `dist`
- Versão do Node (`NODE_VERSION`): `24`
- Variável pública de build `VITE_API_BASE_URL`: URL HTTPS da API, sem `/api` final.

Não coloque `PANEL_ACCESS_KEY` nem `TELEGRAM_BOT_TOKEN` na Cloudflare ou em qualquer
variável `VITE_*`: essas variáveis entram no JavaScript público.
Sem a URL da API, o painel exibe uma mensagem de configuração ao tentar entrar.
Alterar a URL exige um novo build/deploy.

## Permitir o painel na API

No `.env` da raiz, configure a origem exata retornada pelo Pages:

```dotenv
PANEL_ALLOWED_ORIGINS=https://seu-painel.pages.dev
```

Reinicie a API. A chave do painel permanece obrigatória. CORS só controla quais
origens o navegador aceita; não substitui autenticação. URLs de previews não são
liberadas automaticamente.

## Conectar o PC

Um Cloudflare Tunnel pode encaminhar uma URL HTTPS à API em `127.0.0.1:8000`.
Um Quick Tunnel fornece endereço temporário e serve para testes; não é uma solução
permanente. Escolha a configuração do túnel antes de publicar o painel funcional.
Não compartilhe a chave do painel e não utilize uma chave que já foi exposta.

Depois de conectar: testar entrada, lista, download e renomeação; uma origem
não autorizada deve falhar no preflight. O bot continua iniciado separadamente.

Referências:
- https://developers.cloudflare.com/pages/configuration/build-configuration/
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
