# Usar o Media Saver no Windows

## Primeira configuração em cada computador

1. Instale Python compatível com as dependências, Node.js 24 e FFmpeg (incluindo ffprobe).
2. Na raiz, execute `python -m venv .venv` e
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
3. Copie `.env.example` para `.env` e configure TELEGRAM_BOT_TOKEN,
   ALLOWED_USER_IDS e, se necessário, FFMPEG_LOCATION. Não compartilhe o token.
4. Dê dois cliques em `preparar-painel.cmd`. Essa etapa precisa de internet e
   gera frontend/dist. Repita após atualizar o código da interface.

## Uso diário

Feche as execuções antigas do bot e da API antes de usar o iniciador.
Dê dois cliques em `iniciar.cmd`, ou execute `./iniciar.cmd` no terminal.
O programa valida as configurações, reserva a porta 8000, inicia Telegram e API,
e abre http://127.0.0.1:8000. Envie /login ao bot e cole o código no painel.

Mantenha a janela do iniciador aberta. Fechar só a aba do navegador não para os
serviços. Para parar, use `parar.cmd` ou Ctrl+C na janela do iniciador. O encerramento
pode esperar trabalhos em andamento; evite fechar à força durante downloads.
O botão Sair do painel encerra apenas sua sessão, não o programa.

Não são necessários Vite, Cloudflare, ngrok ou cloudflared no uso local. O build
local ignora a URL remota e usa a API do mesmo computador. Telegram e downloads
continuam exigindo internet. Desligar o computador interrompe o aplicativo.

O comando parar só sinaliza a execução criada pelo iniciador nesta pasta; não mata
processos pela porta e não encerra uma API ou bot iniciados manualmente.
Se a porta estiver ocupada, encerre a execução antiga no terminal correspondente.

## Entregar para outra pessoa

Use um bot separado ou pare a execução do mesmo bot no outro computador. Não rode
duas instâncias de polling do mesmo token. Cada PC usa seu próprio armazenamento.
Não copie a pasta .venv de um PC para outro: faça a configuração inicial acima.
Os arquivos e sessões ficam em data/. Não publique essa pasta, .env ou .runtime/.
O instalador completo e o atalho de área de trabalho ainda serão uma etapa posterior.
