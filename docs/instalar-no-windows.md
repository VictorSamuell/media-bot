# Instalar o Media Saver em outro PC (sem Telegram)

Este guia é para quem quer usar o painel no próprio Windows. Não precisa de
Telegram, conta na Cloudflare ou túnel. A biblioteca fica salva nesse computador.

## 1. Baixar o projeto

Abra [o repositório no GitHub](https://github.com/VictorSamuell/media-bot), clique
em **Code → Download ZIP** e extraia o conteúdo em uma pasta fixa, por exemplo
`C:\MediaSaver`. Não execute os arquivos de dentro do ZIP.

A pasta correta contém `requirements.txt`, `iniciar.cmd` e `frontend`.

## 2. Instalar os programas necessários

- **Python 3.12**: marque **Add Python to PATH** durante a instalação.
- **Node.js 24**: necessário para preparar o painel.
- **FFmpeg**: a pasta de programas deve conter `ffmpeg.exe` e `ffprobe.exe`.

Depois de instalar, abra um terminal novo. Confira Python e Node:

```powershell
python --version
node --version
npm --version
```

## 3. Preparar o Python e as configurações

No Explorador de Arquivos, abra a pasta do projeto, clique na barra de endereço,
digite `powershell` e pressione Enter. Execute os comandos, um de cada vez:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

O comando de cópia é para a primeira instalação. Se `.env` já existir, mantenha o
arquivo e abra-o diretamente; não substitua as configurações existentes.

No Bloco de Notas, deixe `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_IDS` e
`PANEL_ALLOWED_ORIGINS` vazios. Se o FFmpeg não estiver no PATH, preencha
`FFMPEG_LOCATION` com a pasta que contém os dois executáveis. Exemplo:

```dotenv
TELEGRAM_BOT_TOKEN=
ALLOWED_USER_IDS=
FFMPEG_LOCATION=C:/ffmpeg/bin
PANEL_ALLOWED_ORIGINS=
```

Troque `C:/ffmpeg/bin` pela pasta real do seu PC. Salve o arquivo como `.env`,
sem acrescentar `.txt`. Não coloque a senha do painel nesse arquivo.

## 4. Criar sua senha

Dê dois cliques em **configurar-acesso.cmd**:

1. Quando pedir ID do Telegram, pressione **Enter**, sem digitar nada.
2. Digite uma senha de **10 a 128 caracteres**.
3. Repita a senha para confirmar.

A senha não aparece enquanto você digita — isso é normal. Aguarde a mensagem
**Senha salva**. Esse procedimento cria um acesso para a biblioteca local.
Quem já usa o bot nesse mesmo PC pode informar seu próprio ID para acessar a
biblioteca existente, em vez de pressionar Enter.

## 5. Preparar e abrir o painel

1. Dê dois cliques em **preparar-painel.cmd**. Precisa de internet; aguarde a
   mensagem de conclusão. Se aparecer erro, resolva antes de continuar.
2. Dê dois cliques em **iniciar.cmd**.
3. O navegador abre em `http://127.0.0.1:8000`.
4. Escolha **Entrar com senha** e use a senha criada.

A sessão dura duas horas. Depois, basta entrar com a mesma senha novamente.

## Usar no dia a dia

- **Ligar:** abra `iniciar.cmd` e mantenha a janela aberta.
- **Baixar música ou vídeo:** abra **Adicionar à biblioteca → Baixar por link**,
  cole o link do YouTube, Instagram ou TikTok, escolha MP3 ou MP4 e um nome opcional.
- **Guardar um arquivo do PC:** escolha **Enviar do computador**.
- **Encerrar:** abra `parar.cmd` e aguarde o encerramento.

O limite atual é de menos de **50 MB por arquivo final**. Mantenha a página aberta
até a importação terminar. Baixar por link exige internet; consultar arquivos já
salvos não depende do Telegram. Fechar só o navegador não encerra o programa.

Você pode criar atalhos de `iniciar.cmd` e `parar.cmd` na área de trabalho pelo
menu de contexto do Windows. Mantenha a pasta do projeto no mesmo lugar para
os atalhos continuarem funcionando.

## Se algo der errado

- **Python ou npm não reconhecido:** confira a instalação e abra um terminal novo.
- **FFmpeg não encontrado:** ajuste `FFMPEG_LOCATION` para a pasta com os dois executáveis.
- **Porta 8000 ocupada:** pare a execução anterior. Se iniciou uma API manualmente,
  encerre-a no terminal correspondente antes de abrir `iniciar.cmd`.
- **Esqueceu a senha:** abra `configurar-acesso.cmd` novamente e use a mesma opção
  de biblioteca (Enter para a local). A troca encerra as sessões anteriores.
- **Interface não preparada:** execute `preparar-painel.cmd` e confira se terminou sem erro.

## Seus arquivos e atualizações

Os arquivos ficam na pasta `data`. Cada PC tem sua própria biblioteca; não há
sincronização automática entre computadores. Para backup, pare o Media Saver e
copie toda a pasta `data` para um local seguro.

Ao atualizar o código, preserve `data` e `.env`, reinstale as dependências com
`.venv\Scripts\python.exe -m pip install -r requirements.txt` e execute
`preparar-painel.cmd` novamente. Não copie a `.venv` de outro computador.

Detalhes adicionais: [guia de uso local](uso-local.md).
