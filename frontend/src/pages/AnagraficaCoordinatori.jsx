import { useState, useEffect } from 'react';
import { getCoordinatori, createCoordinatore, updateCoordinatore, deleteCoordinatore } from '../utils/api';
import { useNotify } from '../App';
import Field from '../components/Field';

const EMPTY = { nome: '', cognome: '', codice_fiscale: '', ordine_professionale: '', numero_ordine: '', provincia_ordine: '', titolo_studio: '', anni_esperienza: '', attestato_corso: '', data_corso: '', data_aggiornamento: '', telefono: '', email: '', pec: '' };

export default function AnagraficaCoordinatori() {
  const [list, setList]       = useState([]);
  const [form, setForm]       = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [showForm, setShow]   = useState(false);
  const notify = useNotify();

  const carica = () => getCoordinatori().then(r => setList(r.data)).catch(() => {});
  useEffect(carica, []);

  const set  = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const F    = (props) => <Field {...props} form={form} set={set} />;

  const apri = (item = null) => { setEditing(item); setForm(item ? { ...item } : EMPTY); setShow(true); };

  const salva = async (e) => {
    e.preventDefault();
    if (!form.nome || !form.cognome) { notify('Nome e cognome sono obbligatori', 'error'); return; }
    try {
      if (editing) await updateCoordinatore(editing.id, form);
      else         await createCoordinatore(form);
      notify(editing ? 'Coordinatore aggiornato ✓' : 'Coordinatore aggiunto ✓', 'success');
      setShow(false); carica();
    } catch { notify('Errore durante il salvataggio', 'error'); }
  };

  const elimina = async (id) => {
    if (!window.confirm('Eliminare questo coordinatore?')) return;
    try { await deleteCoordinatore(id); notify('Eliminato', 'success'); carica(); }
    catch { notify('Errore', 'error'); }
  };

  return (
    <div>
      <div className="page-header"><h1>📐 Coordinatori CSP / CSE</h1><p>Anagrafica coordinatori persistente</p></div>
      <div className="toolbar">
        <span style={{ color: '#8A9BB0', fontSize: '0.85rem' }}>{list.length} coordinatori</span>
        <button className="btn btn-primary" onClick={() => apri()}>+ Nuovo Coordinatore</button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 20, borderColor: '#BFDBFE', borderWidth: 2 }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1A3A5C', marginBottom: 20 }}>
            {editing ? '✏️ Modifica' : '➕ Nuovo'} Coordinatore
          </div>
          <form onSubmit={salva}>
            <div className="form-grid">
              <F label="Nome *"    field="nome" />
              <F label="Cognome *" field="cognome" />
              <F label="Codice Fiscale" field="codice_fiscale" />
              <div className="form-group">
                <label className="form-label">Ordine Professionale</label>
                <select className="form-control" value={form.ordine_professionale || ''}
                  onChange={e => set('ordine_professionale', e.target.value)}>
                  <option value="">Seleziona...</option>
                  <option>Ordine degli Ingegneri</option>
                  <option>Ordine degli Architetti</option>
                  <option>Ordine dei Geometri</option>
                  <option>Ordine dei Periti Industriali</option>
                </select>
              </div>
              <F label="N. Iscrizione Albo"              field="numero_ordine" />
              <F label="Provincia Albo"                  field="provincia_ordine" />
              <F label="Titolo di Studio"                field="titolo_studio" />
              <F label="Anni di Esperienza"              field="anni_esperienza" type="number" />
              <F label="Attestato Corso 120h"            field="attestato_corso" />
              <F label="Data Corso"                      field="data_corso"        type="date" />
              <F label="Data Ultimo Aggiornamento (40h)" field="data_aggiornamento" type="date" />
              <F label="Telefono"                        field="telefono" />
              <F label="Email"                           field="email"  type="email" />
              <F label="PEC"                             field="pec"    type="email" />
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
          <div className="empty-state"><div className="empty-icon">📐</div><p>Nessun coordinatore registrato</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Nome Cognome</th><th>Ordine</th><th>N. Iscrizione</th><th>Aggiornamento</th><th>Contatti</th><th>Azioni</th></tr></thead>
              <tbody>
                {list.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.nome} {c.cognome}</strong></td>
                    <td style={{ fontSize: '0.82rem' }}>{c.ordine_professionale || '—'}</td>
                    <td style={{ fontSize: '0.82rem' }}>{c.numero_ordine || '—'}{c.provincia_ordine ? ` (${c.provincia_ordine})` : ''}</td>
                    <td style={{ fontSize: '0.82rem', color: c.data_aggiornamento ? '#27AE60' : '#C0392B' }}>
                      {c.data_aggiornamento ? new Date(c.data_aggiornamento).toLocaleDateString('it-IT') : 'Non indicata'}
                    </td>
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