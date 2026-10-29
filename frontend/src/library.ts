export type Kind = "Vídeos" | "Documentos" | "Áudios" | "Imagens" | "Outros";
export type MediaFile = {
  id: string;
  name: string;
  size: number;
  date: string;
  kind: Kind;
  note: string;
};
export const kinds: Kind[] = [
  "Vídeos",
  "Documentos",
  "Áudios",
  "Imagens",
  "Outros",
];
export const icons: Record<Kind, string> = {
  Vídeos: "▷",
  Documentos: "▤",
  Áudios: "♫",
  Imagens: "▧",
  Outros: "▣",
};
export function category(name: string): Kind {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["mp4", "mkv", "webm", "mov", "avi"].includes(ext)) return "Vídeos";
  if (["mp3", "wav", "ogg", "m4a", "flac"].includes(ext)) return "Áudios";
  if (["jpg", "jpeg", "png", "webp", "gif", "svg"].includes(ext))
    return "Imagens";
  if (["pdf", "txt", "doc", "docx", "xlsx", "csv", "pptx", "md"].includes(ext))
    return "Documentos";
  return "Outros";
}
export function apiUrl(path: string) {
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(window.location.hostname);
  const base = local ? '' : (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
  if (base && new URL(base).protocol !== 'https:') {
    throw new Error('O endereço remoto da API deve usar HTTPS.');
  }
  if (!base && import.meta.env.PROD && !local) {
    throw new Error('A conexão com a API ainda não foi configurada nesta publicação.');
  }
  return base + path;
}

export async function request(path: string, key: string, options: RequestInit = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${key}` },
    cache: "no-store",
  });
  if (response.status === 401 && key) {
    window.dispatchEvent(new Event('session-expired'));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error((typeof body?.detail === "string" ? body.detail : "") || `Falha na API (${response.status}).`);
  }
  return response;
}
