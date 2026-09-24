import { useState, useEffect, useRef } from 'react';
import { getStudio, salvaStudio, caricaLogo, eliminaLogo, logoUrl } from '../utils/api';
import { useNotify } from '../App';

const CAMPI = [['nome', 'Nome dello studio'], ['indirizzo', 'Indirizzo'], ['piva', 'P.IVA'],
  ['telefono', 'Telefono'], ['email', 'Email'], ['pec', 'PEC']];

/** "Il tuo studio": intestazione del PSC (uno per account). */
export default function StudioCard() {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [s, setS] = useState(null);
  const [v, setV] = useState(Date.now());

  useEffect(() => {
    getStudio().then(r => setS(r.data)).catch(e => notifyRef.current(e.message, 'error'));
  }, []);

  const salva = async () => {
    try { const r = await salvaStudio(s); setS(r.data); notify('Dati dello studio salvati ✓', 'success'); }
    catch (e) { notify(e.message, 'error'); }
  };
  const logo = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('file', file);
    try { const r = await caricaLogo(fd); setS(x => ({ ...x, ha_logo: r.data.ha_logo })); setV(Date.now()); notify('Logo caricato ✓', 'success'); }
    catch (e) { notify(e.message, 'error'); }
  };
  const togli = async () => {
    try { const r = await eliminaLogo(); setS(x => ({ ...x, ha_logo: r.data.ha_logo })); } catch (e) { notify(e.message, 'error'); }
  };

  if (!s) return null;
  return (
    <div className="card" style={{ marginBottom: 20 }} data-testid="studio">
      <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 4 }}>🏢 Il tuo studio</div>
      <div style={{ fontSize: '0.78rem', color: '#8A9BB0', marginBottom: 12 }}>
        Intestazione dei PSC: logo e dati in copertina, logo e nome dello studio in cima a ogni pagina.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px', gap: 16, alignItems: 'start' }}>
        <div className="form-grid">
          {CAMPI.map(([k, label]) => (
            <div className="form-group" key={k}>
              <label htmlFor={`studio-${k}`}>{label}</label>
              <input id={`studio-${k}`} className="form-control" value={s[k] || ''} onChange={e => setS(x => ({ ...x, [k]: e.target.value }))} />
            </div>
          ))}
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ border: '1px dashed #DCE3ED', borderRadius: 8, height: 90, display: 'flex', alignItems: 'center',
            justifyContent: 'center', marginBottom: 6, background: '#FAFBFC' }}>
            {s.ha_logo ? <img src={logoUrl(v)} alt="Logo dello studio" style={{ maxWidth: 160, maxHeight: 80 }} />
              : <span style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>Nessun logo</span>}
          </div>
          <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer' }}>
            {s.ha_logo ? 'Cambia logo' : 'Carica logo'}
            <input type="file" accept=".png,.jpg,.jpeg" style={{ display: 'none' }} data-testid="file-logo"
              onChange={e => { logo(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
          {s.ha_logo && <button className="btn btn-ghost btn-sm" onClick={togli} style={{ marginLeft: 4 }}>✕</button>}
        </div>
      </div>
      <div style={{ textAlign: 'right', marginTop: 8 }}>
        <button className="btn btn-primary" onClick={salva}>💾 Salva dati dello studio</button>
      </div>
    </div>
  );
}
