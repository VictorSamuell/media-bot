"""Entrada de mídia pelo painel, sem dependência do Telegram."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, StrictStr
from yt_dlp.utils import DownloadError

from .downloader import download_async, validate_url, MAX_UPLOAD_BYTES
from .library import Library


async def disk_work(function, *args):
    worker = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        try:
            await worker
        except Exception:
            pass
        raise


def media_name(name, original):
    name = name.strip() or original
    suffix = Path(original).suffix
    if suffix and not name.lower().endswith(suffix.lower()):
        name += suffix
    if not name or len(name) > 200 or name in ('.', '..') or any(
        not c.isprintable() or c in '/\\:*?"<>|' for c in name
    ):
        raise ValueError('Use um nome de até 200 caracteres, sem barras ou caracteres especiais de caminho.')
    return name


class LinkDownload(BaseModel):
    url: StrictStr = Field(min_length=1, max_length=2048)
    mode: Literal['audio', 'video'] = 'video'
    name: StrictStr = Field(default='', max_length=200)


def router_for(owner, library):
    router = APIRouter()
    # Uma importação por vez por processo evita downloads simultâneos sem limite.
    busy = asyncio.Lock()

    @router.post('/api/import/link', status_code=201)
    async def import_link(body: LinkDownload, owner_id: int = Depends(owner), store: Library = Depends(library)):
        try:
            url = validate_url(body.url)
            name = media_name(body.name, 'media.mp3' if body.mode == 'audio' else 'media.mp4')
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if busy.locked():
            raise HTTPException(409, 'Outra importação está em andamento. Aguarde terminar.')
        async with busy:
            from .config import Settings
            try:
                settings = Settings.load(require_token=False)
                with TemporaryDirectory(prefix='media-saver-') as folder:
                    path = await download_async(url, body.mode, Path(folder), settings.ffmpeg_location)
                    if path.stat().st_size >= MAX_UPLOAD_BYTES:
                        raise HTTPException(413, 'O arquivo precisa ter menos de 50 MB.')
                    destination = path.with_name(name)
                    if destination != path:
                        path.rename(destination)
                    file_id = await disk_work(store.save_local, destination, owner_id)
                return {'id': file_id, 'name': name}
            except (DownloadError, ValueError):
                raise HTTPException(400, 'Não foi possível baixar. Verifique o link e a instalação do FFmpeg; o conteúdo pode estar privado ou indisponível.') from None
            except OSError:
                raise HTTPException(503, 'Não foi possível salvar o arquivo no computador.') from None

    @router.post('/api/import/file', status_code=201)
    async def import_file(request: Request, name: str = Query(..., min_length=1, max_length=200),
                          owner_id: int = Depends(owner), store: Library = Depends(library)):
        try:
            name = media_name(name, '')
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if busy.locked():
            raise HTTPException(409, 'Outra importação está em andamento. Aguarde terminar.')
        async with busy:
            try:
                with TemporaryDirectory(prefix='media-saver-') as folder:
                    path = Path(folder) / name
                    size = 0
                    with path.open('wb') as output:
                        async for chunk in request.stream():
                            size += len(chunk)
                            if size >= MAX_UPLOAD_BYTES:
                                raise HTTPException(413, 'O arquivo precisa ter menos de 50 MB.')
                            await disk_work(output.write, chunk)
                    if not size:
                        raise HTTPException(400, 'O arquivo está vazio.')
                    file_id = await disk_work(store.save_local, path, owner_id)
                return {'id': file_id, 'name': name}
            except OSError:
                raise HTTPException(503, 'Não foi possível salvar o arquivo no computador.') from None

    return router
