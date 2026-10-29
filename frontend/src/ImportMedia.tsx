import {useRef, useState} from "react";
import {apiUrl, request} from "./library";

export default function ImportMedia({accessKey, onImported}: {accessKey:string; onImported:()=>void}) {
  const [tab, setTab] = useState<'link'|'file'>('link');
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState('audio');
  const [name, setName] = useState('');
  const [file, setFile] = useState<File|null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const pending = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  async function submit() {
    if (pending.current) return;
    setError(''); setMessage('');
    if (tab === 'file' && (!file || file.size === 0 || file.size >= 50_000_000)) {
      setError('Escolha um arquivo não vazio com menos de 50 MB.'); return;
    }
    pending.current = true; setBusy(true);
    try {
      let response:Response;
      if (tab === 'link') {
        response = await request('/api/import/link', accessKey, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, mode, name})});
      } else {
        const original = file!.name;
        const suffix = original.includes('.') ? original.slice(original.lastIndexOf('.')) : '';
        let chosen = name.trim() || original;
        if (suffix && !chosen.toLowerCase().endsWith(suffix.toLowerCase())) chosen += suffix;
        setProgress(0);
        response = await new Promise<Response>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', apiUrl('/api/import/file?' + new URLSearchParams({name:chosen})));
          xhr.setRequestHeader('Authorization', `Bearer ${accessKey}`);
          xhr.setRequestHeader('Content-Type', 'application/octet-stream');
          xhr.responseType = 'json';
          xhr.upload.onprogress = event => {
            if (event.lengthComputable) setProgress(Math.min(99, Math.round(event.loaded / event.total * 100)));
          };
          xhr.onload = () => {
            if (xhr.status === 401) window.dispatchEvent(new Event('session-expired'));
            if (xhr.status >= 200 && xhr.status < 300) resolve(new Response(JSON.stringify(xhr.response), {status:xhr.status, headers:{'Content-Type':'application/json'}}));
            else reject(new Error(xhr.response?.detail || `Falha na API (${xhr.status}).`));
          };
          xhr.onerror = () => reject(new Error('Falha de conexão durante o envio.'));
          xhr.onabort = () => reject(new Error('Envio cancelado.'));
          xhr.send(file);
        });
        setProgress(100);
      }
      const saved = await response.json();
      setMessage(`${saved.name} salvo na biblioteca.`);
      setUrl(''); setName(''); setFile(null);
      if(input.current) input.current.value = '';
      onImported();
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível importar.');}
    finally {pending.current = false; setBusy(false); setProgress(null);}
  }
  return <details className="import-media">
    <summary>＋ Adicionar à biblioteca</summary>
    <form onSubmit={e => {e.preventDefault(); void submit();}}>
      <fieldset disabled={busy}>
        <legend>Como deseja adicionar?</legend>
        <div className="login-options">
          <button type="button" aria-pressed={tab === 'link'} onClick={()=>{setTab('link');setError('');setMessage('');}}>Baixar por link</button>
          <button type="button" aria-pressed={tab === 'file'} onClick={()=>{setTab('file');setError('');setMessage('');}}>Enviar do computador</button>
        </div>
        {tab === 'link' ? <>
          <label>Link do YouTube, Instagram ou TikTok<input type="url" required maxLength={2048} value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://…" /></label>
          <label>Formato<select value={mode} onChange={e=>setMode(e.target.value)}><option value="audio">Música / áudio (MP3)</option><option value="video">Vídeo (MP4)</option></select></label>
        </> : <label>Arquivo do computador<input ref={input} type="file" required onChange={e=>setFile(e.target.files?.[0] || null)} /></label>}
        <label>Nome (opcional)<input maxLength={190} value={name} onChange={e=>setName(e.target.value)} placeholder="Ex.: Minha música" /></label>
        <p>Arquivos menores que 50 MB. A extensão será mantida.</p>
        <button className="primary" type="submit">{busy ? 'Processando…' : 'Salvar na biblioteca'}</button>
      </fieldset>
      {busy && (tab === 'file' && progress !== null ? <div className="upload-progress" role="status" aria-live="polite">
        <div><span>Enviando arquivo</span><strong>{progress}%</strong></div>
        <progress max="100" value={progress} aria-label="Progresso do envio do arquivo" />
        <small>{file?.name} · {(file!.size * progress / 100 / 1_000_000).toLocaleString('pt-BR', {maximumFractionDigits:1})} de {(file!.size / 1_000_000).toLocaleString('pt-BR', {maximumFractionDigits:1})} MB enviados</small>
      </div> : <p role="status">Processando o link. Mantenha esta página aberta até terminar.</p>)}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </form>
  </details>;
}
