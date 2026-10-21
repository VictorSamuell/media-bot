# Downloader de Mídia — Telegram Bot

**Nova etapa: biblioteca de documentos.** Envie um documento menor que 20 MB
na conversa privada e use `/arquivos` para listar os últimos dez documentos.
Eles ficam persistidos em `data/`; os downloads de links continuam temporários.
Veja [PRIMEIRA-ETAPA.md](PRIMEIRA-ETAPA.md) para testar e implementar sua primeira tarefa.

**Para ligar o bot já configurado neste PC, siga o [passo a passo LEIA-ME.md](LEIA-ME.md).**

Bot Python com polling, async/await, yt-dlp via módulo e FFmpeg. Recebe links do YouTube, Instagram e TikTok e devolve MP4 ou MP3 como documento.

## Executar no Windows

Requisitos: Python 3.10+ e FFmpeg (incluindo ffprobe) no PATH. Para melhor suporte ao YouTube, instale também um runtime JavaScript suportado pelo yt-dlp, como Deno. FFmpeg é um programa separado.

Abra o PowerShell nesta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Se `.venv` ou `.env` já existirem, reutilize-os. Não sobrescreva um `.env` configurado.

No Telegram, abra [@BotFather](https://t.me/BotFather), envie `/newbot` e siga as instruções. Salve o token em `TELEGRAM_BOT_TOKEN` no `.env` local. Não é necessário enviar o token pelo chat.

```powershell
.\.venv\Scripts\python.exe -m media_bot
```

Deixe o terminal aberto. Para parar, pressione Ctrl+C. Esta versão usa polling e não precisa de webhook. Execute apenas uma instância por token.

## Comandos

- `/start` ou `/help`: instruções e seu ID do Telegram.
- Um link: baixa MP4.
- `/audio LINK`: baixa MP3.
- `/audio` e depois um link: baixa apenas o próximo link válido em MP3.
- `/video`: desativa o modo de áudio pendente; também aceita `/video LINK`.

O modo pendente é separado por usuário e chat e é perdido ao reiniciar. Um link inválido não consome o modo; uma tentativa válida de download consome, mesmo se falhar.

## Configuração

Veja `.env.example`. `ALLOWED_USER_IDS` restringe o bot aos IDs separados por vírgulas. Vazio permite qualquer usuário. `FFMPEG_LOCATION` aceita a pasta contendo ffmpeg e ffprobe quando não estão no PATH.

## Comportamento e limites

- Seleciona a melhor qualidade disponível, sem redução automática para caber no limite.
- Recusa arquivo final maior ou igual a 50.000.000 bytes. O [limite documentado de envio é 50 MB](https://core.telegram.org/bots/api#senddocument).
- Usa uma pasta temporária por solicitação dentro de `work/` no projeto, evitando restrições da pasta temporária do Windows, e remove arquivos após sucesso ou falha de download, conversão e envio.
- Downloads rodam em uma thread. Solicitações são processadas uma de cada vez; novas mensagens aguardam durante o download.
- Cancelamento normal aguarda o worker antes de limpar. Encerramento forçado ou queda de energia pode deixar arquivos temporários.
- Links privados, lives, playlists e conteúdo que exige login não são suportados. Sites podem mudar e exigir atualização do yt-dlp.
- O limite de envio é verificado após a conversão. Reserve espaço para originais e intermediários maiores que 50 MB.
- A validação limita domínios iniciais às três plataformas; hospedagem pública requer também controles de rede e recursos no servidor.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes simulam download e envio para verificar limpeza, erros, limite de tamanho, comandos e cancelamento, sem token. O teste real exige configurar o token e enviar um link ao bot.

## Estrutura

- `media_bot/config.py`: configuração e verificação do FFmpeg.
- `media_bot/downloader.py`: validação, download e conversão.
- `media_bot/bot.py`: comandos, envio e limpeza.
- `media_bot/__main__.py`: inicialização.
- `requirements.txt`: dependências.

Referências: [python-telegram-bot](https://docs.python-telegram-bot.org/en/stable/telegram.ext.application.html) e [yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp).
