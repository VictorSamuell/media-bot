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
export async function request(path: string, key: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${key}` },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error((typeof body?.detail === "string" ? body.detail : "") || `Falha na API (${response.status}).`);
  }
  return response;
}
