import { useState } from 'react';
import { request, type MediaFile } from './library';

export default function RenameForm({file, accessKey, onRenamed}: {
  file: MediaFile; accessKey: string; onRenamed: (id:string, name:string)=>void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(file.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function save() {
    setSaving(true); setError(''); setSuccess('');
    try {
      const response = await request(`/api/files/${file.id}`, accessKey, {
        method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name})
      });
      const updated = await response.json();
      onRenamed(file.id, updated.name);
      setEditing(false); setSuccess('Nome atualizado na biblioteca.');
    } catch (e) {setError(e instanceof Error ? e.message : 'Não foi possível renomear.');}
    finally {setSaving(false);}
  }
  return <div className="rename-panel">
    {editing ? <form onSubmit={event=>{event.preventDefault(); void save();}}>
      <label htmlFor="file-name">Novo nome</label>
      <input id="file-name" autoFocus required maxLength={200} value={name} disabled={saving}
        onChange={event=>setName(event.target.value)} aria-describedby="rename-help" />
      <p id="rename-help">Inclua a extensão, como .mp4 ou .pdf. Renomear não converte o arquivo.</p>
      <div className="rename-actions">
        <button className="primary" disabled={saving || !name.trim()}>{saving?'Salvando…':'Salvar nome'}</button>
        <button type="button" disabled={saving} onClick={()=>{setEditing(false);setError('');}}>Cancelar</button>
      </div>
    </form> : <button onClick={()=>{setName(file.name);setError('');setSuccess('');setEditing(true);}}>Renomear arquivo</button>}
    {error && <p role="alert">{error}</p>}
    {success && <p role="status">{success}</p>}
  </div>;
}
