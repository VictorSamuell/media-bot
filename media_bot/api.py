"""API do painel local; a chave identifica um único proprietário configurado."""
import os
import re
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from media_bot.library import Library

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='Media Saver API')


def library():
    return Library(ROOT / 'data')


def owner(authorization: str = Header(default='')):
    load_dotenv(ROOT / '.env')
    key = os.getenv('PANEL_ACCESS_KEY', '').strip()
    owner_id = os.getenv('PANEL_OWNER_ID', '').strip()
    if len(key) < 32 or not owner_id.isdecimal() or int(owner_id) <= 0:
        raise HTTPException(503, 'Configure PANEL_OWNER_ID e PANEL_ACCESS_KEY no .env.')
    if not secrets.compare_digest(authorization.encode(), ('Bearer ' + key).encode()):
        raise HTTPException(401, 'Chave de acesso inválida.')
    return int(owner_id)


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/files')
def files(owner_id: int = Depends(owner), store: Library = Depends(library)):
    db = store.connect()
    try:
        rows = db.execute('SELECT id, name, size, created_at FROM files WHERE owner_id = ? '
                          'ORDER BY created_at DESC, rowid DESC', (owner_id,)).fetchall()
        return {'files': [dict(row) for row in rows], 'owner_id': str(owner_id)}
    finally:
        db.close()


@app.get('/api/files/{file_id}/download')
def download(file_id: str, owner_id: int = Depends(owner), store: Library = Depends(library)):
    if not re.fullmatch(r'[0-9a-f]{32}', file_id):
        raise HTTPException(404, 'Arquivo não encontrado.')
    row = store.get(owner_id, file_id)
    if row is None or not (store.root / file_id).is_file():
        raise HTTPException(404, 'Arquivo não encontrado.')
    return FileResponse(store.root / file_id, filename=row['name'],
                        media_type='application/octet-stream',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
