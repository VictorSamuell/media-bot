"""Iniciador local: um processo supervisiona API e Telegram, sem túnel."""
import asyncio
import json
import logging
import secrets
import socket
from socket import socket as create_socket
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
STATUS = RUNTIME / 'instance.json'
STOP = RUNTIME / 'stop'


def request_stop():
    if not STATUS.exists():
        print('Nenhuma execução do iniciador foi encontrada.')
        return
    instance = json.loads(STATUS.read_text(encoding='utf-8'))['instance']
    STOP.write_text(instance, encoding='utf-8')
    print('Encerramento solicitado. Aguarde a janela do Media Saver terminar.')


async def run():
    import uvicorn
    from .config import Settings
    from .bot import build_application

    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        raise RuntimeError('Interface não preparada. Execute preparar-painel.cmd uma vez.')
    settings = Settings.load(require_token=False)
    from .auth import AuthStore
    if not settings.token and not AuthStore(ROOT / "data").password_ready():
        raise RuntimeError("Configure uma senha primeiro: abra configurar-acesso.cmd.")
    # Reserva antes de iniciar o bot: evita uma segunda execução local.
    listener = create_socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(('127.0.0.1', 8000))
        listener.listen(128)
        listener.setblocking(False)
    except OSError:
        listener.close()
        raise RuntimeError('A porta 8000 está ocupada. Pare a API antiga antes de iniciar novamente.') from None

    application = build_application(settings) if settings.token else None
    server = uvicorn.Server(uvicorn.Config('media_bot.api:app', host='127.0.0.1', port=8000,
                                           log_level='warning', access_log=False))
    instance = secrets.token_hex(16)
    api_task = None
    initialized = False
    RUNTIME.mkdir(exist_ok=True)
    try:
        if application:
            print('Conectando ao Telegram...', flush=True)
            await asyncio.wait_for(application.initialize(), timeout=45)
            initialized = True
            await application.start()
            await application.updater.start_polling(allowed_updates=['message'], bootstrap_retries=0)
        api_task = asyncio.create_task(server.serve(sockets=[listener]))
        for _ in range(100):
            if api_task.done():
                await api_task
                raise RuntimeError('A API encerrou durante a inicialização.')
            if server.started:
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError('A API não ficou pronta no prazo esperado.')
        STATUS.write_text(json.dumps({'instance': instance}), encoding='utf-8')
        print('Media Saver pronto: http://127.0.0.1:8000\n'
              'Entre com sua senha ou com /login do Telegram, se configurado.\n'
              'Para encerrar, use parar.cmd ou Ctrl+C nesta janela.', flush=True)
        webbrowser.open('http://127.0.0.1:8000')
        while not api_task.done() and not server.should_exit:
            if STOP.exists() and STOP.read_text(encoding='utf-8') == instance:
                break
            await asyncio.sleep(.5)
    finally:
        print('Encerrando Media Saver...', flush=True)
        server.should_exit = True
        if application and application.updater.running:
            await application.updater.stop()
        if application and application.running:
            await application.stop()
        if initialized:
            await application.shutdown()
        if api_task:
            await api_task
        listener.close()
        if STATUS.exists() and json.loads(STATUS.read_text(encoding='utf-8'))['instance'] == instance:
            STATUS.unlink()
        if STOP.exists() and STOP.read_text(encoding='utf-8') == instance:
            STOP.unlink()


def main():
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        if '--stop' in sys.argv:
            request_stop()
        else:
            asyncio.run(run())
    except KeyboardInterrupt:
        print('Media Saver encerrado.')
    except Exception as exc:
        # Não registrar mensagens de rede que possam conter o token do bot.
        print(str(exc) if isinstance(exc, (ValueError, RuntimeError)) else
              f'Falha ao iniciar ({type(exc).__name__}). Confira internet, .env e dependências.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
