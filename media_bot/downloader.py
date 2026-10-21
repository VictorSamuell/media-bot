import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL

MAX_UPLOAD_BYTES = 50_000_000
DOMAINS = ('youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com')


def validate_url(text: str) -> str:
    url = text.strip()
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        valid = (parsed.scheme in ('http', 'https') and not parsed.username
                 and not parsed.password and parsed.port in (None, 80, 443)
                 and not any(c.isspace() for c in url)
                 and any(host == d or host.endswith('.' + d) for d in DOMAINS))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Envie um único link válido do YouTube, Instagram ou TikTok.')
    return url


class QuietLogger:
    # Não registrar links, cookies ou detalhes retornados pelos sites.
    def debug(self, message):
        pass

    info = warning = error = debug


def download(url: str, mode: str, directory: Path, ffmpeg_location=None) -> Path:
    audio = mode == 'audio'
    options = {
        'format': 'bestaudio/best' if audio else 'bestvideo+bestaudio/best',
        'outtmpl': str(directory / 'media.%(ext)s'),
        'noplaylist': True,
        'playlistend': 1,
        'cachedir': False,
        'quiet': True,
        'logger': QuietLogger(),
        'socket_timeout': 30,
        'retries': 2,
        'fragment_retries': 2,
        'match_filter': lambda info, **kwargs: 'Transmissões ao vivo não são suportadas.' if info.get('is_live') else None,
        'postprocessors': ([{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                           if audio else [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]),
    }
    if not audio:
        options['merge_output_format'] = 'mp4'
    if ffmpeg_location:
        options['ffmpeg_location'] = ffmpeg_location
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
    if not info or info.get('_type') in ('playlist', 'multi_video'):
        raise ValueError('Envie o link de um vídeo individual.')
    result = directory / ('media.mp3' if audio else 'media.mp4')
    if not result.is_file() or result.stat().st_size == 0:
        raise ValueError('Não foi possível produzir o arquivo final.')
    return result


async def download_async(*args) -> Path:
    # O worker deve terminar antes de o chamador remover a pasta temporária.
    worker = asyncio.create_task(asyncio.to_thread(download, *args))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        try:
            await worker
        except Exception:
            pass
        raise
