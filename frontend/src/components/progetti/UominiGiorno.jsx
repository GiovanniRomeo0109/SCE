import { useState, useEffect, useCallback, useRef } from 'react';
import { getUominiGiorno, salvaUominiGiorno, exportUrl } from '../../utils/api';
import { useNotify } from '../../App';

const num = (v, dec = 1) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('it-IT', { maximumFractionDigits: dec, minimumFractionDigits: 0 }));
const euro = (v) => (v === null || v === undefined ? '—' : `€ ${Number(v).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
// Numeri all'italiana: "1.234,56" → 1234.56 · "21,71" → 21.71 · "21.71" → 21.71 · "250.000" → 250000
const perNumero = (s) => {
  let t = String(s ?? '').trim().replace(/[€\s]/g, '');
  if (t === '') return null;
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');   // solo separatori delle migliaia
  const n = Number(t);
  return Number.isFinite(n) ? n : NaN;
};
// Valore mostrato nei campi: virgola decimale, senza separatore delle migliaia
const inCampo = (v) => (v === null || v === undefined || v === '' ? '' : Number(v).toLocaleString('it-IT', { useGrouping: false, maximumFractionDigits: 4 }));

/** Campo numerico che salva all'uscita (blur) o con Invio. */
function CampoNumero({ id, valore, onSalva, placeholder, suffisso, larghezza = 140 }) {
  const [testo, setTesto] = useState(inCampo(valore));
  useEffect(() => { setTesto(inCampo(valore)); }, [valore]);
  const salva = () => {
    const n = perNumero(testo);
    if (Number.isNaN(n)) { setTesto(inCampo(valore)); return; }
    if ((n ?? null) !== (valore ?? null)) onSalva(n);
  };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <input id={id} className="form-control" style={{ width: larghezza }} value={testo} placeholder={placeholder}
        onChange={e => setTesto(e.target.value)} onBlur={salva} onKeyDown={e => e.key === 'Enter' && e.target.blur()} />
      {suffisso}
    </span>
  );
}

export default function UominiGiorno({ progettoId, versione }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [u, setU] = useState(null);

  const carica = useCallback(async () => {
    try { const r = await getUominiGiorno(progettoId); setU(r.data); }
    catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { carica(); }, [carica, versione]);

  const salva = async (campo, valore) => {
    try { const r = await salvaUominiGiorno(progettoId, { [campo]: valore }, [campo]); setU(r.data); }
    catch (e) { notify(e.message, 'error'); carica(); }
  };

  if (!u) return null;
  const a = u.cronoprogramma, b = u.incidenza;
  const box = (attivo) => ({
    flex: 1, minWidth: 280, border: `1.5px solid ${attivo ? '#27AE60' : '#DCE3ED'}`, borderRadius: 10,
    padding: 14, background: attivo ? '#F4FBF6' : 'white',
  });

  return (
    <div data-testid="uomini-giorno" style={{ borderTop: '2px solid #EEF1F5', marginTop: 8, paddingTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 10, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontWeight: 700, color: '#1A3A5C' }}>👷 Uomini-giorno</div>
          <div style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
            Due metodi a confronto: scegli quale usare nel PSC (predefinito il maggiore).
          </div>
        </div>
        <a className="btn btn-gold btn-sm" href={exportUrl(progettoId, 'cronoprogramma')} download>
          ⬇ Cronoprogramma Excel
        </a>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {/* Metodo A */}
        <div style={box(u.scelta === 'cronoprogramma')}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 700, color: '#1A3A5C', cursor: 'pointer' }}>
            <input type="radio" name="metodo-ug" checked={u.scelta === 'cronoprogramma'} disabled={!a.uomini_giorno}
              onChange={() => salva('ug_scelta', 'cronoprogramma')} />
            A · Dal cronoprogramma
          </label>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#1A3A5C', margin: '6px 0' }} data-testid="ug-a">
            {num(a.uomini_giorno)} <span style={{ fontSize: '0.8rem', fontWeight: 400 }}>uomini-giorno</span>
          </div>
          <div style={{ fontSize: '0.76rem', color: '#5A6B7D' }}>
            Σ durata (settimane) × {u.giorni_per_settimana} giorni × addetti medi, dalla tabella del cronoprogramma qui sopra.
          </div>
          {a.senza_addetti.length > 0 && (
            <div style={{ fontSize: '0.74rem', color: '#8A6D00', marginTop: 6 }}>
              ⚠️ Fasi senza addetti medi (non conteggiate): {a.senza_addetti.join(', ')}
            </div>
          )}
        </div>

        {/* Metodo B */}
        <div style={box(u.scelta === 'incidenza')}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 700, color: '#1A3A5C', cursor: 'pointer' }}>
            <input type="radio" name="metodo-ug" checked={u.scelta === 'incidenza'} disabled={!b.uomini_giorno}
              onChange={() => salva('ug_scelta', 'incidenza')} />
            B · Dall'incidenza della manodopera
          </label>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#1A3A5C', margin: '6px 0' }} data-testid="ug-b">
            {num(b.uomini_giorno)} <span style={{ fontSize: '0.8rem', fontWeight: 400 }}>uomini-giorno</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 10px', alignItems: 'center', fontSize: '0.8rem' }}>
            <label htmlFor="ug-importo">Importo lavori</label>
            <CampoNumero id="ug-importo" valore={b.importo_lavori} placeholder="es. 250000" suffisso="€"
              onSalva={v => salva('importo_lavori', v)} />
            <label htmlFor="ug-incidenza">Incidenza manodopera</label>
            <span>
              <CampoNumero id="ug-incidenza" valore={b.incidenza_csp} placeholder="%" suffisso="%" larghezza={90}
                onSalva={v => salva('incidenza_manodopera', v)} />
              {b.origine_manodopera?.startsWith('computo') && (
                <div style={{ fontSize: '0.72rem', color: '#27AE60' }}>Dal {b.origine_manodopera}: prevale sulla percentuale</div>
              )}
            </span>
            <label htmlFor="ug-costo">Costo giornaliero</label>
            <span>
              <CampoNumero id="ug-costo" valore={b.costo_giornaliero_csp ?? b.costo_giornaliero} placeholder="€/giorno" suffisso="€/giorno"
                onSalva={v => salva('costo_giornaliero', v)} />
              {b.proposta && (
                <div style={{ fontSize: '0.72rem', color: '#5A6B7D' }}>
                  Proposto {euro(b.proposta.valore)}: media di {b.proposta.qualifiche.length} qualifiche edili
                  ({euro(b.proposta.media_oraria)}/h) × 8 h — elenco "{b.proposta.elenco}".
                  {b.costo_giornaliero_csp !== null && b.costo_giornaliero_csp !== b.proposta.valore && (
                    <button className="btn btn-ghost btn-sm" style={{ marginLeft: 6, padding: '0 6px' }}
                      onClick={() => salva('costo_giornaliero', null)}>usa il proposto</button>
                  )}
                </div>
              )}
              {!b.proposta && !b.costo_giornaliero && (
                <div style={{ fontSize: '0.72rem', color: '#8A6D00' }}>
                  Nessun capitolo manodopera negli elenchi: inserisci il costo giornaliero.
                </div>
              )}
            </span>
          </div>
          {!b.uomini_giorno && !b.origine_manodopera && (
            <div style={{ fontSize: '0.76rem', color: '#8A6D00', marginTop: 8 }} data-testid="ug-b-mancante">
              Inserisci la percentuale di incidenza della manodopera per calcolare questo metodo
            </div>
          )}
          {b.importo_manodopera && (
            <div style={{ fontSize: '0.74rem', color: '#5A6B7D', marginTop: 6 }}>
              Manodopera {euro(b.importo_manodopera)} ÷ {euro(b.costo_giornaliero)}/giorno
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 10, fontSize: '0.85rem' }} data-testid="ug-valore">
        <strong>Valore per il PSC: {num(u.valore)} uomini-giorno</strong>
        {u.scelta && ` (metodo ${u.scelta === 'cronoprogramma' ? 'A' : 'B'}${u.scelta === u.maggiore ? ', il maggiore' : ''})`}
        {u.valore >= 200 && <span style={{ color: '#8A6D00' }}> · pari o superiore a 200 uomini-giorno (art. 99 D.Lgs. 81/2008)</span>}
      </div>
    </div>
  );
}
