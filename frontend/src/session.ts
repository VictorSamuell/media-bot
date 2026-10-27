export const SESSION_STORAGE_KEY = 'media-saver-session';
type Session = { token: string; expiresAt: number };
export function removeSession() {
  try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch { /* Navegação com armazenamento bloqueado. */ }
}
export function readSession(): Session | null {
  try {
    const value = JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || 'null');
    if (value && typeof value.token === 'string' && value.token.length > 0 &&
        typeof value.expiresAt === 'number' && Number.isFinite(value.expiresAt) && value.expiresAt > Date.now()) return value;
  } catch { /* Sessões inválidas nunca são restauradas. */ }
  removeSession();
  return null;
}
export function saveSession(session: Session) {
  try { localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session)); }
  catch { /* Sem armazenamento, o acesso ainda funciona até fechar a página. */ }
}
