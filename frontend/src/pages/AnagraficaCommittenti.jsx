import { useState, useEffect } from 'react';
import { getCommittenti, createCommittente, updateCommittente, deleteCommittente } from '../utils/api';
import { useNotify } from '../App';

const EMPTY = { tipo: 'persona_fisica', nome: '', cognome: '', ragione_sociale: '', codice_fiscale: '', piva: '', indirizzo: '', citta: '', provincia: '', telefono: '', email: '' };

export default function AnagraficaCommittenti() {
  const [list, setList]       = useState([]);
  const [form, setForm]       = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [showForm, setShow]   = useState(false);
  const notify = useNotify();

  const carica = () => getCommittenti().then(r => setList(r.data)).catch(() => {});
  useEffect(carica, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const apri = (item = null) => {
    setEditing(item);
    setForm(item ? { ...item } : EMPTY);
    setShow(true);
  };

  const salva = async (e) => {
    e.preventDefault();
    if (!form.nome && !form.ragione_sociale) { notify('Inserire nome o ragione sociale', 'error'); return; }
    try {
      if (editing) await updateCommittente(editing.id, form);
      else         await createCommittente(form);
      notify(editing ? 'Committente aggiornato ✓' : 'Committente aggiunto ✓', 'success');
      setShow(false); carica();
    } catch { notify('Errore durante il salvataggio', 'error'); }
  };

  const elimina = async (id) => {
    if (!window.confirm('Eliminare questo committente?')) return;
    try { await deleteCommittente(id); notify('Eliminato', 'success'); carica(); }
    catch { notify('Errore', 'error'); }
  };

  const F = ({ label, field, type = 'text', req }) => (
    <div className="form-group">
      <label className="form-label">{label}{req && <span className="required">*</span>}</label>
      <input type={type} className="form-control" value={form[field] || ''} onChange={e => set(field, e.target.value)} />
    </div>
  );

  return (
    <div>
      <div className="page-header"><h1>👤 Committenti</h1><p>Anagrafica committenti persistente</p></div>
      <div className="toolbar">
        <span style={{ color: '#8A9BB0', fontSize: '0.85rem' }}>{list.length} committenti</span>
        <button className="btn btn-primary" onClick={() => apri()}>+ Nuovo Committente</button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 20, borderColor: '#BFDBFE', borderWidth: 2 }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1A3A5C', marginBottom: 20 }}>
            {editing ? '✏️ Modifica' : '➕ Nuovo'} Committente
          </div>
          <form onSubmit={salva}>
            <div className="form-group">
              <label className="form-label">Tipo</label>
              <select className="form-control" value={form.tipo} onChange={e => set('tipo', e.target.value)}>
                <option value="persona_fisica">Persona Fisica</option>
                <option value="persona_giuridica">Persona Giuridica</option>
              </select>
            </div>
            <div className="form-grid">
              <F label="Nome" field="nome" req />
              <F label="Cognome" field="cognome" />
              {form.tipo === 'persona_giuridica' && <F label="Ragione Sociale" field="ragione_sociale" />}
              <F label="Codice Fiscale" field="codice_fiscale" />
              {form.tipo === 'persona_giuridica' && <F label="P.IVA" field="piva" />}
              <F label="Indirizzo" field="indirizzo" />
              <F label="Città" field="citta" />
              <F label="Provincia" field="provincia" />
              <F label="Telefono" field="telefono" />
              <F label="Email / PEC" field="email" type="email" />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button type="button" className="btn btn-ghost" onClick={() => setShow(false)}>Annulla</button>
              <button type="submit" className="btn btn-primary">💾 Salva</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {list.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">👤</div><p>Nessun committente. Aggiungine uno!</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Nome / Ragione Sociale</th><th>CF / P.IVA</th><th>Città</th><th>Contatti</th><th>Azioni</th></tr></thead>
              <tbody>
                {list.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.tipo === 'persona_giuridica' ? c.ragione_sociale : `${c.nome || ''} ${c.cognome || ''}`}</strong></td>
                    <td style={{ fontSize: '0.82rem' }}>{c.codice_fiscale || c.piva || '—'}</td>
                    <td style={{ fontSize: '0.82rem' }}>{c.citta || '—'}</td>
                    <td style={{ fontSize: '0.82rem' }}>{c.email || c.telefono || '—'}</td>
                    <td style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => apri(c)}>✏️</button>
                      <button className="btn btn-danger btn-sm" onClick={() => elimina(c.id)}>🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}