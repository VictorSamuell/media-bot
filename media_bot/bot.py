import logging

"""O asyncio é uma biblioteca padrão do Python usada para escrever código concorrente utilizando a sintaxe async/await. 
Ele é ideal para tarefas estruturadas de alto nível e operações vinculadas a E/S (I/O-bound), como requisições web, 
consultas a bancos de dados e leitura/escrita de arquivos, permitindo que o programa execute outras tarefas 
enquanto aguarda a resposta dessas operações de rede ou disco."""

import asyncio
import re
import secrets
from time import monotonic

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
        self.delete_pending = {}
        self.name_pending = {}

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
                'Use /buscar palavra para pesquisar e /baixar ID para receber um arquivo salvo.\n'
                '/renomear ID novo nome: altera o nome do arquivo.\n'
                '/excluir ID: pede confirmação para apagar. /cancelar: cancela a operação pendente.\n'
                'Ao enviar arquivo ou link, escolha um nome ou use /original.\n'
                '/espaco: mostra a quantidade e o tamanho dos seus arquivos.\n'
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
        await self.ask_name(update, 'document', attachment, None)

    async def ask_name(self, update, kind, payload, mode):
        now = monotonic()
        self.name_pending = {key: value for key, value in self.name_pending.items() if value[3] > now}
        if self.key(update) in self.name_pending:
            await update.message.reply_text('Já estou esperando um nome. Responda ou use /cancelar antes de enviar outro arquivo.')
            return
        self.name_pending[self.key(update)] = (kind, payload, mode, now + 300)
        await update.message.reply_text(
            'Qual nome você quer para o arquivo? Envie o nome em até 5 minutos. '
            'Vou manter a extensão original. Use /original para manter o nome ou /cancelar para desistir.')

    async def prepare_link(self, update, text):
        try:
            url = validate_url(text)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        mode = 'audio' if self.key(update) in self.audio_pending else 'video'
        await self.ask_name(update, 'link', url, mode)
        self.audio_pending.discard(self.key(update))

    @staticmethod
    def chosen_name(name, original):
        name = name.strip()
        if not name or name in ('.', '..'):
            raise ValueError('Envie um nome válido ou use /original.')
        suffix = Path(original).suffix
        if suffix and not name.lower().endswith(suffix.lower()):
            name += suffix
        if not name or len(name) > 200 or name in ('.', '..') or any(
            not c.isprintable() or c in '/\\:*?"<>|' for c in name
        ):
            raise ValueError('Use um nome de até 200 caracteres, sem barras ou caracteres especiais de caminho.')
        return name

    async def finish_name(self, update, name):
        pending = self.name_pending.get(self.key(update))
        if pending is None or pending[3] <= monotonic():
            self.name_pending.pop(self.key(update), None)
            await update.message.reply_text('Não há arquivo aguardando nome ou o prazo expirou. Envie o arquivo ou link novamente.')
            return
        kind, payload, mode, _ = pending
        original = (payload.file_name or 'documento') if kind == 'document' else ('media.mp3' if mode == 'audio' else 'media.mp4')
        try:
            chosen = self.chosen_name(name, original) if name is not None else None
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        self.name_pending.pop(self.key(update))
        if kind == 'link':
            await self.process(update, payload, chosen, mode)
            return
        try:
            await self.library.save(payload, update.effective_user.id, name=chosen)
        except Exception as exc:
            logger.error('Falha ao salvar documento: %s', type(exc).__name__)
            await update.message.reply_text('Não consegui guardar o documento. Envie novamente para tentar.')
            return
        await update.message.reply_text('Documento salvo na biblioteca! Use /arquivos para consultar.')

    async def original_name(self, update, context):
        if await self.authorized(update):
            await self.finish_name(update, None)

    async def files(self, update, context):
        if not await self.authorized(update):
            return
        if update.effective_chat.type != 'private':
            await update.message.reply_text('Consulte sua biblioteca na conversa privada com o bot.')
            return
        rows = self.library.recent(update.effective_user.id)
        text = self.format_files(rows)
        await update.message.reply_text('Seus últimos documentos:\n' + text if rows else 'Sua biblioteca ainda está vazia.')

    async def search(self, update, context):
        if not await self.authorized(update):
            return

        if update.effective_chat.type != 'private':
            await update.message.reply_text(
                'Pesquise na conversa privada com o bot.'
            )
            return

        term = ' '.join(context.args).strip()

        if not term:
            await update.message.reply_text(
                'Use /buscar seguido de um nome. Exemplo: /buscar final'
            )
            return

        rows = await asyncio.to_thread(
            self.library.search,
            update.effective_user.id,
            term,
        )

        if not rows:
            await update.message.reply_text('Nenhum arquivo encontrado.')
            return

        text = self.format_files(rows)
        await update.message.reply_text('Arquivos encontrados:\n' + text)

    @staticmethod
    def format_files(rows):
        return '\n\n'.join(
            f'{row["name"]} ({row["size"]:,} bytes)\n/baixar {row["id"]}'
            for row in rows
        )

    async def retrieve(self, update, context):
        if not await self.authorized(update):
            return
        message = update.message
        if update.effective_chat.type != 'private':
            await message.reply_text('Baixe seus arquivos na conversa privada com o bot.')
            return
        if len(context.args) != 1 or not re.fullmatch(r'[0-9a-fA-F]{32}', context.args[0]):
            await message.reply_text('Use /baixar ID. Copie o comando mostrado em /arquivos ou /buscar.')
            return
        file_id = context.args[0].lower()
        row = await asyncio.to_thread(self.library.get, update.effective_user.id, file_id)
        if row is None:
            await message.reply_text('Arquivo não encontrado na sua biblioteca.')
            return
        path = self.library.root / file_id
        try:
            if path.stat().st_size >= MAX_UPLOAD_BYTES:
                await message.reply_text('Este arquivo ultrapassa o limite de envio do bot.')
                return
            with path.open('rb') as media:
                await message.reply_document(
                    document=media, filename=row['name'],
                    read_timeout=120, write_timeout=120, connect_timeout=30,
                )
        except FileNotFoundError:
            await message.reply_text('O registro existe, mas o arquivo não está mais no armazenamento.')
        except OSError:
            await message.reply_text('Não consegui ler o arquivo salvo. Tente novamente.')
        except TelegramError:
            await message.reply_text('O envio falhou. O arquivo continua salvo; tente novamente.')

    async def private_library(self, update):
        if not await self.authorized(update):
            return False
        if update.effective_chat.type != 'private':
            await update.message.reply_text('Use este comando na conversa privada com o bot.')
            return False
        return True

    async def rename(self, update, context):
        if not await self.private_library(update):
            return
        if len(context.args) < 2 or not re.fullmatch(r'[0-9a-fA-F]{32}', context.args[0]):
            await update.message.reply_text('Use /renomear ID novo nome. Exemplo: /renomear ID aula Python.mp4')
            return
        name = ' '.join(context.args[1:]).strip()
        try:
            changed = await asyncio.to_thread(self.library.rename, update.effective_user.id,
                                             context.args[0].lower(), name)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        await update.message.reply_text(f'Arquivo renomeado para: {name}' if changed
                                        else 'Arquivo não encontrado na sua biblioteca.')

    async def space(self, update, context):
        if not await self.private_library(update):
            return
        usage = await asyncio.to_thread(self.library.usage, update.effective_user.id)
        await update.message.reply_text(
            f'Sua biblioteca: {usage["count"]} arquivo(s).\n'
            f'Tamanho registrado: {usage["bytes"]:,} bytes ({usage["bytes"] / 1_000_000:.2f} MB).'
        )

    async def delete(self, update, context):
        if not await self.private_library(update):
            return
        if len(context.args) != 1 or not re.fullmatch(r'[0-9a-fA-F]{32}', context.args[0]):
            await update.message.reply_text('Use /excluir ID. Encontre o ID em /arquivos ou /buscar.')
            return
        file_id = context.args[0].lower()
        row = await asyncio.to_thread(self.library.get, update.effective_user.id, file_id)
        if row is None:
            await update.message.reply_text('Arquivo não encontrado na sua biblioteca.')
            return
        now = monotonic()
        self.delete_pending = {key: value for key, value in self.delete_pending.items() if value[2] > now}
        code = secrets.token_hex(4)
        self.delete_pending[self.key(update)] = (file_id, code, now + 120)
        await update.message.reply_text(
            f'Excluir definitivamente da biblioteca: {row["name"]}?\n'
            f'Confirme em até 2 minutos: /confirmar {code}\n'
            'Ou use /cancelar. Isso não apaga mensagens já enviadas ao Telegram.'
        )

    async def confirm_delete(self, update, context):
        if not await self.private_library(update):
            return
        key = self.key(update)
        pending = self.delete_pending.get(key)
        if pending is None or pending[2] <= monotonic():
            self.delete_pending.pop(key, None)
            await update.message.reply_text('Não há exclusão pendente ou a confirmação expirou. Use /excluir ID novamente.')
            return
        if context.args != [pending[1]]:
            await update.message.reply_text('Código incorreto. Copie o comando de confirmação ou use /cancelar.')
            return
        self.delete_pending.pop(key)
        try:
            deleted = await asyncio.to_thread(self.library.delete, update.effective_user.id, pending[0])
        except OSError:
            await update.message.reply_text('Não consegui remover o arquivo. Tente novamente com /excluir ID.')
            return
        await update.message.reply_text('Arquivo excluído da biblioteca.' if deleted
                                        else 'Arquivo não encontrado na sua biblioteca.')

    async def cancel_delete(self, update, context):
        if not await self.authorized(update):
            return
        naming = self.name_pending.pop(self.key(update), None)
        if naming:
            await update.message.reply_text('Envio cancelado. Nenhum arquivo foi salvo.')
            return
        pending = self.delete_pending.pop(self.key(update), None)
        await update.message.reply_text('Exclusão cancelada.' if pending else 'Não há exclusão pendente.')

    async def audio(self, update, context):
        if not await self.authorized(update):
            return
        self.audio_pending.add(self.key(update))
        if context.args:
            await self.prepare_link(update, ' '.join(context.args))
        else:
            await update.message.reply_text('Envie o próximo link para baixar em MP3.')

    async def video(self, update, context):
        if not await self.authorized(update):
            return
        self.audio_pending.discard(self.key(update))
        if context.args:
            await self.prepare_link(update, ' '.join(context.args))
        else:
            await update.message.reply_text('Envie o próximo link para baixar em MP4.')

    async def text(self, update, context):
        if await self.authorized(update):
            if self.key(update) in self.name_pending:
                await self.finish_name(update, update.message.text)
            else:
                await self.prepare_link(update, update.message.text)

    async def process(self, update, text, chosen=None, selected_mode=None):
        message = update.message
        try:
            url = validate_url(text)
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        key = self.key(update)
        mode = selected_mode or ('audio' if key in self.audio_pending else 'video')
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
                if chosen is not None:
                    destination = path.with_name(self.chosen_name(chosen, path.name))
                    if destination != path:
                        path.rename(destination)
                        path = destination
                await asyncio.to_thread(
                    self.library.save_local,
                    path,
                    update.effective_user.id,
                )
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
    # Tipos ajudam a diagnosticar sem registrar URLs com token ou dados do usuário.
    error = context.error
    causes = []
    seen = set()
    while error is not None and id(error) not in seen and len(causes) < 8:
        seen.add(id(error))
        causes.append(type(error).__name__)
        error = error.__cause__ or error.__context__
    logger.error('Erro no bot: %s', ' -> '.join(causes))


def build_application(settings):
    handlers = MediaBot(settings)
    # Processamento sequencial limita uso de disco/CPU e preserva /audio -> link.
    app = Application.builder().token(settings.token).concurrent_updates(False).build()
    app.add_handler(CommandHandler(['start', 'help'], handlers.start))
    app.add_handler(CommandHandler('audio', handlers.audio))
    app.add_handler(CommandHandler('video', handlers.video))
    app.add_handler(CommandHandler('arquivos', handlers.files))
    app.add_handler(CommandHandler('buscar', handlers.search))
    app.add_handler(CommandHandler('baixar', handlers.retrieve))
    app.add_handler(CommandHandler('original', handlers.original_name))
    app.add_handler(CommandHandler('renomear', handlers.rename))
    app.add_handler(CommandHandler('espaco', handlers.space))
    app.add_handler(CommandHandler('excluir', handlers.delete))
    app.add_handler(CommandHandler('confirmar', handlers.confirm_delete))
    app.add_handler(CommandHandler('cancelar', handlers.cancel_delete))
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text))
    app.add_error_handler(on_error)
    return app
