import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    allowed_users: frozenset[int] = frozenset()
    ffmpeg_location: str | None = None

    @classmethod
    def load(cls):
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
        token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        if not token:
            raise ValueError('Preencha TELEGRAM_BOT_TOKEN no arquivo .env.')
        try:
            users = frozenset(int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip())
        except ValueError:
            raise ValueError('ALLOWED_USER_IDS deve conter IDs numéricos separados por vírgula.') from None
        location = os.getenv('FFMPEG_LOCATION', '').strip() or None
        for executable in ('ffmpeg', 'ffprobe'):
            if not shutil.which(executable, path=location):
                raise ValueError(f'{executable} não encontrado. Instale FFmpeg ou configure FFMPEG_LOCATION.')
        return cls(token, users, location)
