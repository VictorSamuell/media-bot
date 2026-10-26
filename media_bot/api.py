"""API do painel local; a chave identifica um único proprietário configurado."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictStr

from media_bot.library import Library
from media_bot.auth import AuthStore

ROOT = Path(__file__).resolve().parents[1]
def create_app():
    load_dotenv(ROOT / '.env')
    application = FastAPI(title='Media Saver API')
    origins = [origin.strip().rstrip('/') for origin in
               os.getenv('PANEL_ALLOWED_ORIGINS', '').split(',') if origin.strip()]
    if any(not origin.startswith('https://') or '*' in origin for origin in origins):
        raise ValueError('PANEL_ALLOWED_ORIGINS deve conter origens HTTPS explícitas, sem curingas.')
    application.add_middleware(CORSMiddleware, allow_origins=origins,
                               allow_methods=['GET', 'PATCH', 'POST'],
                               allow_headers=['Authorization', 'Content-Type'])
    return application


app = create_app()


def library():
    return Library(ROOT / 'data')


def auth_store():
    return AuthStore(ROOT / 'data')


def owner(authorization: str = Header(default=''), auth: AuthStore = Depends(auth_store)):
    token = authorization.removeprefix('Bearer ')
    owner_id = auth.owner(token) if authorization.startswith('Bearer ') else None
    if owner_id is None:
        raise HTTPException(401, 'Sessão inválida ou expirada. Gere outro código com /login no bot.')
    return owner_id


class LoginCode(BaseModel):
    code: StrictStr


@app.post('/api/auth/login')
def login(body: LoginCode, auth: AuthStore = Depends(auth_store)):
    token, error = auth.exchange(body.code[:200])
    if error == 'limited':
        raise HTTPException(429, 'Muitas tentativas. Aguarde um minuto.', headers={'Retry-After':'60'})
    if error:
        raise HTTPException(401, 'Código inválido, usado ou expirado. Envie /login ao bot.')
    from fastapi.responses import JSONResponse
    return JSONResponse({'token': token, 'expires_in':43200}, headers={'Cache-Control':'no-store'})


@app.post('/api/auth/logout')
def logout(authorization: str = Header(default=''), auth: AuthStore = Depends(auth_store)):
    auth.revoke(authorization.removeprefix('Bearer '))
    return {'ok': True}


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


class RenameFile(BaseModel):
    name: StrictStr


@app.patch('/api/files/{file_id}')
def rename_file(file_id: str, body: RenameFile, owner_id: int = Depends(owner),
                store: Library = Depends(library)):
    if not re.fullmatch(r'[0-9a-f]{32}', file_id) or store.get(owner_id, file_id) is None:
        raise HTTPException(404, 'Arquivo não encontrado.')
    try:
        changed = store.rename(owner_id, file_id, body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if not changed:
        raise HTTPException(404, 'Arquivo não encontrado.')
    return {'id': file_id, 'name': body.name.strip()}


# Montado depois das rotas da API: caminhos /api desconhecidos continuam 404.
from fastapi.staticfiles import StaticFiles


def mount_frontend(application, directory):
    @application.api_route('/api/{path:path}', methods=['GET', 'POST', 'PATCH', 'DELETE'])
    def unknown_api(path: str):
        raise HTTPException(404, 'Endpoint não encontrado.')

    if directory.is_dir():
        application.mount('/', StaticFiles(directory=directory, html=True), name='frontend')


mount_frontend(app, ROOT / 'frontend' / 'dist')
