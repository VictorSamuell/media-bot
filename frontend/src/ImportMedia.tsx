import {useRef, useState} from "react";
import {request} from "./library";

export default function ImportMedia({accessKey, onImported}: {accessKey:string; onImported:()=>void}) {
  const [tab, setTab] = useState<'link'|'file'>('link');
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState('audio');
  const [name, setName] = useState('');
  const [file, setFile] = useState<File|null>(null);
  const [busy, setBusy] = useState(false);
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
        response = await request('/api/import/file?' + new URLSearchParams({name:chosen}), accessKey, {method:'POST', headers:{'Content-Type':'application/octet-stream'}, body:file});
      }
      const saved = await response.json();
      setMessage(`${saved.name} salvo na biblioteca.`);
      setUrl(''); setName(''); setFile(null);
      if(input.current) input.current.value = '';
      onImported();
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível importar.');}
    finally {pending.current = false; setBusy(false);}
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
      {busy && <p role="status">Aguarde o processamento. Mantenha esta página aberta até terminar.</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </form>
  </details>;
}
