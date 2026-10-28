# Usar o Media Saver no Windows

Para instalar do zero, use o [passo a passo para outro PC, sem Telegram](instalar-no-windows.md).

## Primeira configuração em cada computador

1. Instale Python compatível com as dependências, Node.js 24 e FFmpeg (incluindo ffprobe).
2. Na raiz, execute `python -m venv .venv` e
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
3. Copie `.env.example` para `.env` (sem substituir um arquivo já configurado).
   Para usar sem Telegram, deixe TELEGRAM_BOT_TOKEN vazio e ajuste FFMPEG_LOCATION
   se necessário. Abra `configurar-acesso.cmd` e defina uma senha de 10 a 128 caracteres.
   Quando pedir ID, pressione Enter para criar a biblioteca local. Para acessar sua
   biblioteca existente do bot, informe seu próprio ID do Telegram.
   O cadastro e a troca de senha só podem ser feitos nesse terminal local; não há
   cadastro público. Existe um acesso por senha por instalação. A senha é armazenada
   com salt aleatório e scrypt no banco, nunca em texto puro ou no .env.
   Se quiser usar também o bot, configure TELEGRAM_BOT_TOKEN e ALLOWED_USER_IDS.
4. Dê dois cliques em `preparar-painel.cmd`. Essa etapa precisa de internet e
   gera frontend/dist. Repita após atualizar o código da interface.

## Uso diário

Feche as execuções antigas do bot e da API antes de usar o iniciador.
Dê dois cliques em `iniciar.cmd`, ou execute `./iniciar.cmd` no terminal.
O programa valida as configurações, reserva a porta 8000, inicia Telegram e API,
e abre http://127.0.0.1:8000. Entre com a senha configurada. A sessão dura duas horas.
Telegram só inicia se houver token configurado; nesse caso o código /login continua disponível.
Sem token, o iniciador não se conecta ao Telegram.

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

## Adicionar arquivos sem Telegram

Abra **Adicionar à biblioteca** no painel. Em **Baixar por link**, cole um link
individual do YouTube, Instagram ou TikTok, escolha MP3 ou MP4 e um nome opcional.
Em **Enviar do computador**, selecione um arquivo e, se quiser, dê outro nome.
A extensão original é mantida. O limite é de menos de 50 MB por arquivo final.
A cópia enviada fica em data/; o original no computador não é alterado.

A API permite uma importação por vez por processo. Mantenha a página aberta até
concluir: ainda não há fila persistente, retomada ou porcentagem de progresso.
Os links usam yt-dlp/FFmpeg, podem exigir atualizações e baixar intermediários maiores
que o limite final. No acesso remoto, o túnel/proxy pode interromper requisições longas;
esta primeira versão foi preparada para uso local.

Para trocar ou recuperar a senha, execute configurar-acesso.cmd novamente no PC.
Informe o mesmo ID (ou Enter para a biblioteca local); a troca encerra as sessões
anteriores desse acesso. Não é necessário editar o banco nem criar outro bot.

## Entregar para outra pessoa

Sem Telegram, configure apenas a senha local. Se optar pelo Telegram, use um bot separado ou pare a execução do mesmo bot no outro computador. Não rode
duas instâncias de polling do mesmo token. Cada PC usa seu próprio armazenamento.
Não copie a pasta .venv de um PC para outro: faça a configuração inicial acima.
Os arquivos e sessões ficam em data/. Não publique essa pasta, .env ou .runtime/.
O instalador completo e o atalho de área de trabalho ainda serão uma etapa posterior.
