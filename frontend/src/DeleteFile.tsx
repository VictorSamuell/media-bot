import { useRef, useState } from 'react';
import { request, type MediaFile } from './library';

export default function DeleteFile({file, accessKey, onDeleted}: {
  file: MediaFile; accessKey: string; onDeleted: (id:string)=>void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function remove() {
    if (pending.current) return;
    pending.current=true; setBusy(true); setError('');
    try {
      await request(`/api/files/${file.id}`, accessKey, {
        method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmed:true})
      });
      dialog.current?.close();
      onDeleted(file.id);
    } catch(e) {setError(e instanceof Error ? e.message : 'Não foi possível excluir.');}
    finally {pending.current=false;setBusy(false);}
  }
  return <div className="delete-panel">
    <button className="danger" onClick={()=>{setError('');dialog.current?.showModal();}}>Excluir arquivo</button>
    <dialog ref={dialog} aria-labelledby="delete-title" aria-describedby="delete-description"
      onCancel={event=>{if (pending.current) event.preventDefault();}}>
      <h2 id="delete-title">Excluir este arquivo?</h2>
      <p className="delete-name">{file.name}</p>
      <p id="delete-description">O arquivo será apagado do computador e da biblioteca. Não é possível desfazer. Cópias já enviadas no Telegram não serão apagadas.</p>
      {error && <p role="alert">{error}</p>}
      <div className="rename-actions">
        <button className="primary" autoFocus disabled={busy} onClick={()=>dialog.current?.close()}>Cancelar</button>
        <button className="danger" disabled={busy} onClick={()=>void remove()}>{busy?'Excluindo…':'Sim, excluir definitivamente'}</button>
      </div>
    </dialog>
  </div>;
}
