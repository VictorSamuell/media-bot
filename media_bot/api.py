"""API do painel local; a chave identifica um único proprietário configurado."""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictStr, StrictBool, Field

from media_bot.library import Library, normalize_search
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
                               allow_methods=['GET', 'PATCH', 'POST', 'DELETE'],
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
        raise HTTPException(401, 'Sessão inválida ou expirada. Entre novamente no painel.')
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
    return JSONResponse({'token': token, 'expires_in':7200}, headers={'Cache-Control':'no-store'})


class PasswordLogin(BaseModel):
    password: StrictStr = Field(min_length=1, max_length=128)


@app.post('/api/auth/password')
def password_login(body: PasswordLogin, auth: AuthStore = Depends(auth_store)):
    token, error = auth.exchange_password(body.password)
    if error == 'limited':
        raise HTTPException(429, 'Muitas tentativas. Aguarde um minuto.', headers={'Retry-After': '60'})
    if error:
        raise HTTPException(401, 'Senha inválida ou acesso por senha ainda não configurado neste PC.')
    from fastapi.responses import JSONResponse
    return JSONResponse({'token': token, 'expires_in': 7200}, headers={'Cache-Control': 'no-store'})


@app.post('/api/auth/logout')
def logout(authorization: str = Header(default=''), auth: AuthStore = Depends(auth_store)):
    auth.revoke(authorization.removeprefix('Bearer '))
    return {'ok': True}


@app.get('/health')
async def health():
    return {'status': 'ok'}


def file_kind(name):
    extension = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    for kind, extensions in {
        'Vídeos': ('mp4','mkv','webm','mov','avi'),
        'Áudios': ('mp3','wav','ogg','m4a','flac'),
        'Imagens': ('jpg','jpeg','png','webp','gif','svg'),
        'Documentos': ('pdf','txt','doc','docx','xlsx','csv','pptx','md'),
    }.items():
        if extension in extensions:
            return kind
    return 'Outros'


@app.get('/api/files')
def files(page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
          q: str = Query('', max_length=200), kind: str = Query('Todos', pattern='^(Todos|Vídeos|Áudios|Imagens|Documentos|Outros)$'),
          sort: str = Query('recent', pattern='^(recent|name|size)$'),
          extension: str = Query('', max_length=200),
          favorites_only: bool = False,
          ids: str | None = Query(None, max_length=17000),
          owner_id: int = Depends(owner), store: Library = Depends(library)):
    db = store.connect()
    try:
        db.create_function('normalized', 1, normalize_search, deterministic=True)
        db.create_function('file_kind', 1, file_kind, deterministic=True)
        db.create_function('extension', 1, lambda name: Path(name).suffix.lower().lstrip('.'), deterministic=True)
        where = 'owner_id = ?'
        params = [owner_id]
        if q.strip():
            where += ' AND instr(normalized(name), ?) > 0'
            params.append(normalize_search(q.strip()))
        if kind != 'Todos':
            where += ' AND file_kind(name) = ?'
            params.append(kind)
        if extension:
            where += ' AND extension(name) = ?'
            params.append(extension.strip().lower().lstrip('.'))
        if favorites_only:
            where += ' AND id IN (SELECT file_id FROM favorites)'
        if ids is not None:
            identifiers = ids.split(',') if ids else []
            if len(identifiers) > 500 or any(not re.fullmatch(r'[0-9a-f]{32}', value) for value in identifiers):
                raise HTTPException(422, 'Lista de favoritos inválida (máximo 500).')
            where += ' AND id IN (' + ','.join('?' for _ in identifiers) + ')'
            params.extend(identifiers)
        db.execute('BEGIN')
        usage = dict(db.execute('SELECT COUNT(*) AS count, COALESCE(SUM(size),0) AS bytes FROM files WHERE owner_id = ?', (owner_id,)).fetchone())
        extensions = [row[0] for row in db.execute(
            "SELECT DISTINCT extension(name) AS ext FROM files WHERE owner_id = ? AND extension(name) != '' ORDER BY ext", (owner_id,))]
        favorites = [row[0] for row in db.execute('SELECT file_id FROM favorites JOIN files ON files.id = favorites.file_id WHERE owner_id = ?', (owner_id,))]
        total = db.execute('SELECT COUNT(*) FROM files WHERE ' + where, params).fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, pages)
        order = {'recent':'created_at DESC, rowid DESC', 'name':'normalized(name), id', 'size':'size DESC, id'}[sort]
        rows = db.execute('SELECT id, name, size, created_at FROM files WHERE ' + where +
                          ' ORDER BY ' + order + ' LIMIT ? OFFSET ?',
                          [*params, page_size, (page - 1) * page_size]).fetchall()
        return {'files':[dict(row) for row in rows], 'owner_id':str(owner_id),
                'page':page, 'pages':pages, 'total':total, 'usage':usage, 'favorites':favorites, 'extensions':extensions}
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


class FavoriteFile(BaseModel):
    enabled: StrictBool


@app.patch('/api/files/{file_id}/favorite')
def favorite_file(file_id: str, body: FavoriteFile, owner_id: int = Depends(owner),
                  store: Library = Depends(library)):
    if not store.set_favorite(owner_id, file_id, body.enabled):
        raise HTTPException(404, 'Arquivo não encontrado.')
    return {'id': file_id, 'favorite': body.enabled}


class DeleteFile(BaseModel):
    confirmed: StrictBool = False


@app.delete('/api/files/{file_id}')
def delete_file(file_id: str, body: DeleteFile, owner_id: int = Depends(owner),
                store: Library = Depends(library)):
    if not body.confirmed:
        raise HTTPException(400, 'Confirme a exclusão antes de continuar.')
    try:
        deleted = store.delete(owner_id, file_id)
    except OSError:
        raise HTTPException(503, 'Não foi possível apagar o arquivo. Tente novamente.') from None
    if not deleted:
        raise HTTPException(404, 'Arquivo não encontrado.')
    return {'deleted': file_id}


from .ingest import router_for
app.include_router(router_for(owner, library))

# Montado depois das rotas da API: caminhos /api desconhecidos continuam 404.
from fastapi.staticfiles import StaticFiles


def mount_frontend(application, directory):
    @application.api_route('/api/{path:path}', methods=['GET', 'POST', 'PATCH', 'DELETE'])
    def unknown_api(path: str):
        raise HTTPException(404, 'Endpoint não encontrado.')

    if directory.is_dir():
        application.mount('/', StaticFiles(directory=directory, html=True), name='frontend')


mount_frontend(app, ROOT / 'frontend' / 'dist')
