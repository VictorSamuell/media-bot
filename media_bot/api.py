"""API local do Media Saver, independente do processo do bot."""
from fastapi import FastAPI


app = FastAPI(title='Media Saver API')


@app.get('/health')
async def health():
    """Confirma que a API responde; não verifica Telegram ou armazenamento."""
    return {'status': 'ok'}
