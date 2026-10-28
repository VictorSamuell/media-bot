"""Configuração de senha somente no terminal do proprietário do PC."""
from getpass import getpass
from pathlib import Path
from .auth import AuthStore


def main():
    print('Configure o acesso por senha. A senha não aparece enquanto você digita.')
    owner_text = input('ID do Telegram para usar uma biblioteca existente (Enter = biblioteca local nova): ').strip()
    owner = int(owner_text) if owner_text else -1
    if owner_text and owner <= 0:
        raise ValueError('O ID do Telegram deve ser positivo.')
    password = getpass('Senha (10 a 128 caracteres): ')
    if password != getpass('Repita a senha: '):
        raise ValueError('As senhas não coincidem.')
    AuthStore(Path(__file__).resolve().parents[1] / 'data').configure_password(password, owner)
    print('Senha salva. Abra iniciar.cmd e escolha Entrar com senha.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyboardInterrupt) as exc:
        print(str(exc) or 'Configuração cancelada.')
        raise SystemExit(1)
