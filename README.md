# Downloader de Mídia — Telegram Bot

Bot Python com polling, async/await, yt-dlp via módulo e FFmpeg. Recebe links do YouTube, Instagram e TikTok, guarda os downloads abaixo do limite de envio na biblioteca local e devolve MP4 ou MP3 como documento.

Também guarda documentos menores que 20 MB enviados na conversa privada.
Use `/arquivos` para listar seus dez arquivos mais recentes. A biblioteca fica
em `data/` e permanece salva após reiniciar o bot.

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

## Painel local

A interface em `frontend/` usa React, TypeScript e Vite. Ela permite explorar
arquivos reais com busca sem acentos, filtros, ordenação, download e favoritos temporários.
Configure PANEL_OWNER_ID e PANEL_ACCESS_KEY no .env e inicie a API na porta 8000.
O passo a passo está em [frontend/README.md](frontend/README.md).

Com Node.js 24 instalado:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abra o endereço local mostrado no terminal. Use Ctrl+C para parar.
Veja [frontend/README.md](frontend/README.md) para estrutura e limitações.
O build pode ser validado com `npm run build` dentro de `frontend/`.

## API local

Com as dependências instaladas, execute em outro terminal na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn media_bot.api:app --reload --host 127.0.0.1 --port 8000
```

Abra <http://127.0.0.1:8000/health> para receber `{"status":"ok"}`.
A documentação interativa fica em <http://127.0.0.1:8000/docs>.
Essa rota confirma apenas que a API responde; não verifica Telegram ou banco.
A API roda separadamente do bot, sem precisar do token, e nesta etapa não
disponibiliza arquivos da biblioteca. Use `--reload` apenas no desenvolvimento.
Para encerrar o servidor, pressione Ctrl+C.

## Comandos

- `/start` ou `/help`: instruções e seu ID do Telegram.
- Um link: baixa MP4.
- `/audio LINK`: baixa MP3.
- `/audio` e depois um link: baixa apenas o próximo link válido em MP3.
- `/video`: desativa o modo de áudio pendente; também aceita `/video LINK`.
- `/arquivos`: lista seus dez arquivos mais recentes, somente na conversa privada.
- `/buscar palavra`: procura pelo nome nos seus arquivos e retorna até dez resultados, somente na conversa privada.
  A busca ignora maiúsculas, minúsculas e acentos: `relatorio` encontra `Relatório.pdf` e `acao` encontra `AÇÃO.mp4`. O nome original é preservado; não é necessário reenviar arquivos antigos.
- `/baixar ID`: reenvia um arquivo seu já salvo, somente na conversa privada. Copie o comando completo exibido em `/arquivos` ou `/buscar`.
- `/renomear ID novo nome`: altera o nome usado na busca, listagem e reenvio. Inclua a extensão desejada, como `aula Python.mp4`; isso não converte o formato do arquivo.
- `/espaco`: mostra a quantidade de arquivos e a soma dos tamanhos registrados do usuário, em bytes e MB decimais. Não mede espaço livre no disco, banco de dados ou arquivos temporários.
- `/excluir ID`: mostra o nome do arquivo e solicita confirmação antes de remover a cópia da biblioteca.
- `/confirmar CODIGO`: confirma a exclusão solicitada, com código válido por dois minutos e somente para o mesmo usuário e conversa.
- `/cancelar`: cancela o pedido de exclusão pendente. Todos os comandos de gerenciamento funcionam somente em conversa privada.
- Documento anexado: salva na biblioteca, somente na conversa privada e abaixo de 20.000.000 bytes.

O modo pendente é separado por usuário e chat e é perdido ao reiniciar. Um link inválido não consome o modo; uma tentativa válida de download consome, mesmo se falhar.

## Biblioteca local

- Downloads de links com menos de 50.000.000 bytes são copiados para a biblioteca antes do envio ao Telegram. Se o envio falhar, a cópia já salva permanece.
- Downloads que atingem ou ultrapassam esse limite não são guardados na biblioteca nem enviados.
- Os downloads aparecem como `media.mp4` ou `media.mp3`. Cada cópia recebe um identificador único no disco, evitando sobrescrever arquivos com o mesmo nome.
- Fotos, vídeos e áudios anexados precisam ser enviados como **arquivo/documento** nesta versão. Anexos enviados como mídia ou mensagem de voz ainda não são tratados.
- O banco SQLite `data/library.sqlite3` registra nome, tamanho, proprietário e data. `/arquivos` lista apenas os registros do usuário que executou o comando.
- O reenvio mantém a cópia na biblioteca e usa o nome registrado. IDs inexistentes ou de outros usuários não retornam arquivos. Se a cópia no disco estiver ausente, o bot informa que o registro existe, mas o conteúdo não está disponível.
- Renomear aceita até 200 caracteres imprimíveis e rejeita separadores de caminho. O conteúdo e o identificador permanecem iguais.
- Excluir remove o arquivo local e seu registro, sem apagar mensagens ou cópias já enviadas ao Telegram. Não há lixeira. Um novo pedido substitui a confirmação anterior; reiniciar o bot cancela confirmações pendentes.
- Se o arquivo estiver ausente, confirmar a exclusão remove o registro restante. Se o sistema negar a remoção, o registro é mantido para nova tentativa. Disco e SQLite não compartilham uma transação atômica: uma interrupção entre remoção e confirmação no banco pode deixar um registro sem arquivo.
- O painel local permite consulta e download; ainda não há limite total de armazenamento. Downloads repetidos ocupam espaço novamente.
- Para fazer backup, pare o bot e copie toda a pasta `data/`, incluindo o banco e os arquivos. Não publique `data/` nem `.env` no GitHub.

## Configuração

Veja `.env.example`. `ALLOWED_USER_IDS` restringe o bot aos IDs separados por vírgulas. Vazio permite qualquer usuário. `FFMPEG_LOCATION` aceita a pasta contendo ffmpeg e ffprobe quando não estão no PATH.

## Comportamento e limites

- Seleciona a melhor qualidade disponível, sem redução automática para caber no limite.
- O bot limita o arquivo final a menos de 50.000.000 bytes para envio. Consulte também a [documentação do Telegram](https://core.telegram.org/bots/api#senddocument).
- Usa uma pasta temporária por solicitação dentro de `work/` no projeto, evitando restrições da pasta temporária do Windows. Ao sair desse processamento, remove os temporários; a cópia já salva em `data/` permanece.
- Downloads rodam em uma thread. Solicitações são processadas uma de cada vez; novas mensagens aguardam durante o download.
- O download aguarda seu worker em caso de cancelamento antes da limpeza. A cópia para a biblioteca ainda não tem a mesma proteção contra cancelamento; evite interromper o bot durante essa etapa. Encerramento forçado ou queda de energia pode deixar arquivos incompletos ou sem registro.
- Links privados, lives, playlists e conteúdo que exige login não são suportados. Sites podem mudar e exigir atualização do yt-dlp.
- O limite de envio é verificado após a conversão. Reserve espaço para originais e intermediários maiores que 50 MB.
- A validação limita domínios iniciais às três plataformas; hospedagem pública requer também controles de rede e recursos no servidor.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes simulam download e envio para verificar limpeza, erros, limite de tamanho, comandos e cancelamento, sem token. O teste real exige configurar o token e enviar um link ao bot.

Os testes da biblioteca usam arquivos e SQLite em pastas temporárias para verificar persistência, isolamento entre usuários, cópia local e limpeza após falhas. Os testes do fluxo do bot simulam o armazenamento para não alterar sua biblioteca real.

## Estrutura

- `media_bot/config.py`: configuração e verificação do FFmpeg.
- `media_bot/downloader.py`: validação, download e conversão.
- `media_bot/bot.py`: comandos, envio e limpeza.
- `media_bot/library.py`: armazenamento de arquivos e metadados em SQLite.
- `media_bot/__main__.py`: inicialização.
- `requirements.txt`: dependências.

Referências: [python-telegram-bot](https://docs.python-telegram-bot.org/en/stable/telegram.ext.application.html) e [yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp).

### Escolher o nome antes de salvar

Ao receber um documento privado ou um link (inclusive `/audio LINK` e `/video LINK`),
o bot pergunta o nome. Responda em até cinco minutos; a extensão original é mantida.
Use `/original` para manter o nome e `/cancelar` para desistir antes do processamento.
Enquanto aguarda um nome, outro envio não substitui o pedido pendente.
Pedidos ficam na memória: se reiniciar o bot, envie o documento ou link novamente.
O comando `/baixar ID` continua reenviando o arquivo com o nome já salvo na biblioteca.
