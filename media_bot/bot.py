import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from yt_dlp.utils import DownloadError

from .config import Settings
from .library import Library
from .downloader import MAX_UPLOAD_BYTES, download_async, validate_url

logger = logging.getLogger(__name__)


class MediaBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.audio_pending: set[tuple[int, int]] = set()
        self.library = Library(Path(__file__).resolve().parents[1] / 'data')

    async def authorized(self, update):
        if not update.message or not update.effective_user:
            return False
        if self.settings.allowed_users and update.effective_user.id not in self.settings.allowed_users:
            await update.message.reply_text('Este bot é de uso restrito.')
            return False
        return True

    def key(self, update):
        return update.effective_chat.id, update.effective_user.id

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self.authorized(update):
            await update.message.reply_text(
                'Envie um link do YouTube, Instagram ou TikTok para receber MP4.\n'
                'Use /audio LINK para MP3 ou envie /audio e depois o link.\n'
                'Use /video para voltar ao vídeo. Um arquivo por vez, abaixo de 50 MB.\n'
                'Envie um documento em conversa privada para guardar na biblioteca.\n'
                'Use /arquivos para listar seus últimos documentos.\n'
                f'Seu ID: {update.effective_user.id}')

    async def document(self, update, context):
        if not await self.authorized(update):
            return
        if update.effective_chat.type != 'private':
            await update.message.reply_text('Envie o documento na conversa privada com o bot.')
            return
        attachment = update.message.document
        # Limite conservador para baixar anexos pela API hospedada do Telegram.
        if attachment.file_size is None or attachment.file_size >= 20_000_000:
            await update.message.reply_text('Nesta primeira versão, envie documentos menores que 20 MB.')
            return
        try:
            await self.library.save(attachment, update.effective_user.id)
        except Exception as exc:
            logger.error('Falha ao salvar documento: %s', type(exc).__name__)
            await update.message.reply_text('Não consegui guardar o documento. Tente novamente.')
            return
        await update.message.reply_text('Documento salvo na biblioteca! Use /arquivos para consultar.')

    async def files(self, update, context):
        if not await self.authorized(update):
            return
        if update.effective_chat.type != 'private':
            await update.message.reply_text('Consulte sua biblioteca na conversa privada com o bot.')
            return
        rows = self.library.recent(update.effective_user.id)
        text = '\n'.join(f'{row["name"]} ({row["size"]:,} bytes)' for row in rows)
        await update.message.reply_text('Seus últimos documentos:\n' + text if rows else 'Sua biblioteca ainda está vazia.')

    async def audio(self, update, context):
        if not await self.authorized(update):
            return
        self.audio_pending.add(self.key(update))
        if context.args:
            await self.process(update, ' '.join(context.args))
        else:
            await update.message.reply_text('Envie o próximo link para baixar em MP3.')

    async def video(self, update, context):
        if not await self.authorized(update):
            return
        self.audio_pending.discard(self.key(update))
        if context.args:
            await self.process(update, ' '.join(context.args))
        else:
            await update.message.reply_text('Envie o próximo link para baixar em MP4.')

    async def text(self, update, context):
        if await self.authorized(update):
            await self.process(update, update.message.text)

    async def process(self, update, text):
        message = update.message
        try:
            url = validate_url(text)
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        key = self.key(update)
        mode = 'audio' if key in self.audio_pending else 'video'
        self.audio_pending.discard(key)
        status = await message.reply_text('Baixando e processando...')
        try:
            temp_root = Path(__file__).resolve().parents[1] / 'work'
            temp_root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix='telegram-media-', dir=temp_root) as folder:
                path = await download_async(url, mode, Path(folder), self.settings.ffmpeg_location)
                if path.stat().st_size >= MAX_UPLOAD_BYTES:
                    await status.edit_text('O arquivo ficou com 50 MB ou mais e não pode ser enviado. Tente um vídeo menor ou /audio.')
                    return
                with path.open('rb') as media:
                    await message.reply_document(document=media, filename=path.name,
                                                 read_timeout=120, write_timeout=120,
                                                 connect_timeout=30)
            await status.edit_text('Pronto! Arquivo enviado.')
        except (DownloadError, ValueError):
            await status.edit_text('Não consegui baixar este vídeo. Ele pode estar privado, indisponível ou exigir login. Tente outro link.')
        except TelegramError:
            await self.report(status, 'O envio falhou. Verifique sua conexão e tente novamente.')
        except Exception as exc:
            logger.error('Falha no processamento: %s', type(exc).__name__)
            await self.report(status, 'Ocorreu um erro ao processar o arquivo. Tente novamente.')

    @staticmethod
    async def report(status, text):
        try:
            await status.edit_text(text)
        except TelegramError:
            logger.warning('Não foi possível enviar a mensagem de erro.')


async def on_error(update, context):
    logger.error('Erro no bot: %s', type(context.error).__name__)


def build_application(settings):
    handlers = MediaBot(settings)
    # Processamento sequencial limita uso de disco/CPU e preserva /audio -> link.
    app = Application.builder().token(settings.token).concurrent_updates(False).build()
    app.add_handler(CommandHandler(['start', 'help'], handlers.start))
    app.add_handler(CommandHandler('audio', handlers.audio))
    app.add_handler(CommandHandler('video', handlers.video))
    app.add_handler(CommandHandler('arquivos', handlers.files))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text))
    app.add_error_handler(on_error)
    return app
