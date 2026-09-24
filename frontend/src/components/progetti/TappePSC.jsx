import { useState, useEffect, useCallback, useRef } from 'react';
import { getTappe, avviaBozza, interrompiTappe, stimaTappe, tappeManuali } from '../../utils/api';
import { useNotify } from '../../App';
import TappaEditor from './TappaEditor';

const euro = (n) => `€ ${Number(n || 0).toFixed(2).replace('.', ',')}`;

function statoTappa(t) {
  if (t.stato === 'in_generazione') return { testo: 'In generazione', colore: '#1A3A5C', icona: '⏳' };
  if (t.stato === 'in_coda') return { testo: 'In coda', colore: '#8A9BB0', icona: '⋯' };
  if (t.stato === 'errore') return { testo: 'Errore', colore: '#C0392B', icona: '❌' };
  if (t.da_ricontrollare) return { testo: 'Da ricontrollare', colore: '#C88B2A', icona: '⚠️' };
  if (t.da_aggiornare) return { testo: 'Da aggiornare', colore: '#C88B2A', icona: '⚠️' };
  if (t.contenuto && t.modificata_a_mano) return { testo: 'Modificata da te', colore: '#27AE60', icona: '✔' };
  if (t.contenuto) return { testo: 'Generata', colore: '#27AE60', icona: '✓' };
  return { testo: 'Da generare', colore: '#8A9BB0', icona: '○' };
}

export default function TappePSC({ progettoId, onApriSchema, solaLettura }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [dati, setDati] = useState(null);
  const [selezionata, setSelezionata] = useState(1);
  const [avvio, setAvvio] = useState(false);
  const modifiche = useRef(false);

  const carica = useCallback(async () => {
    try { const r = await getTappe(progettoId); setDati(r.data); }
    catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);

  useEffect(() => { carica(); }, [carica]);
  useEffect(() => {
    if (!dati?.in_corso) return;
    const t = setInterval(carica, 2500);
    return () => clearInterval(t);
  }, [dati?.in_corso, carica]);

  const onModificata = useCallback((v) => { modifiche.current = v; }, []);

  const scegli = (n) => {
    if (n === selezionata) return;
    if (modifiche.current && !window.confirm('Hai modifiche non salvate in questa tappa. Cambiare tappa e perderle?')) return;
    modifiche.current = false;
    setSelezionata(n);
  };

  const bozza = async () => {
    const tappe = dati.tappe;
    const daGenerare = tappe.filter(t => !(t.modificata_a_mano && t.contenuto)).map(t => t.numero);
    const escluse = tappe.filter(t => t.modificata_a_mano && t.contenuto).map(t => t.numero);
    let stima = '';
    try { const r = await stimaTappe(progettoId, daGenerare); stima = `\n\nCosto stimato: ${euro(r.data.stima_eur)}.`; } catch { /* stima non essenziale */ }
    const giaFatte = tappe.some(t => t.contenuto && !t.modificata_a_mano);
    const testo = `Generare la bozza completa del PSC (${daGenerare.length} tappe in sequenza)?`
      + (giaFatte ? '\nLe tappe già generate verranno sostituite.' : '')
      + (escluse.length ? `\nLe tappe ${escluse.join(', ')}, modificate a mano, non verranno toccate e saranno segnate "da ricontrollare".` : '')
      + '\nPuoi chiudere la pagina: la generazione continua in background.' + stima;
    if (!window.confirm(testo)) return;
    setAvvio(true);
    try {
      await avviaBozza(progettoId);
      notify('Bozza completa avviata', 'success');
      carica();
    } catch (e) { notify(e.message, 'error'); }
    finally { setAvvio(false); }
  };

  const compilaAMano = async () => {
    if (!window.confirm('Creare le tappe vuote da compilare a mano, senza AI? Le potrai riempire sezione per sezione.')) return;
    try { const r = await tappeManuali(progettoId); notify(`${r.data.create.length} tappe pronte da compilare`, 'success'); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const interrompi = async () => {
    if (!window.confirm('Interrompere la generazione? Le tappe già completate restano.')) return;
    try { await interrompiTappe(progettoId); carica(); } catch (e) { notify(e.message, 'error'); }
  };

  if (!dati) return <div style={{ padding: 30, color: '#8A9BB0' }}>Caricamento tappe…</div>;

  const { tappe, documenti, bozza: statoBozza, in_corso: inCorso } = dati;
  const generate = tappe.filter(t => t.contenuto).length;
  const tappa = tappe.find(t => t.numero === selezionata) || tappe[0];
  const docPronti = documenti.completati > 0 && !documenti.in_lavorazione;
  const inGenerazione = tappe.find(t => t.stato === 'in_generazione');
  const attenzione = tappe.filter(t => t.da_ricontrollare || t.da_aggiornare).length;

  return (
    <div>
      {/* Barra superiore */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ fontWeight: 700, color: '#1A3A5C' }}>Tappe del PSC: {generate} di 12 generate</div>
          <div style={{ height: 6, background: '#EEF1F5', borderRadius: 3, overflow: 'hidden', margin: '6px 0' }}>
            <div style={{ width: `${(generate / 12) * 100}%`, height: '100%', background: '#27AE60', transition: 'width .4s' }} />
          </div>
          <div style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
            {inCorso ? (inGenerazione ? `In generazione: tappa ${inGenerazione.numero} — ${inGenerazione.titolo}` : 'In coda…')
              : !docPronti ? (documenti.in_lavorazione ? 'Attendi la fine dell\'elaborazione dei documenti' : 'Carica almeno un documento nella scheda Documenti')
              : attenzione ? `${attenzione} tappe da ricontrollare o aggiornare` : 'Puoi generare le tappe una alla volta o tutte insieme'}
          </div>
        </div>
        {!inCorso && !solaLettura && !documenti.completati && !documenti.in_lavorazione && generate < 12 && (
          <button className="btn btn-ghost" onClick={compilaAMano} data-testid="compila-senza-documenti">✍️ Compila senza documenti</button>
        )}
        {solaLettura ? null : inCorso ? (
          <button className="btn btn-ghost" onClick={interrompi}>⏹ Interrompi</button>
        ) : (
          <button className="btn btn-gold" onClick={bozza} disabled={!docPronti || avvio}>
            {avvio ? 'Avvio…' : '🚀 Genera bozza completa'}
          </button>
        )}
      </div>

      {statoBozza?.stato === 'interrotta' && statoBozza.messaggio && !inCorso && (
        <div className="warn-box" style={{ marginBottom: 16, fontSize: '0.84rem' }}>⏳ {statoBozza.messaggio}</div>
      )}
      {statoBozza?.stato === 'completata' && !inCorso && (
        <div className="info-box" style={{ marginBottom: 16, fontSize: '0.84rem' }}>
          ✅ Bozza completa generata. Rivedi le tappe, correggi dove serve e compila il questionario del sopralluogo.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, alignItems: 'start' }}>
        {/* Elenco tappe */}
        <div className="card" style={{ padding: 8 }}>
          {tappe.map(t => {
            const st = statoTappa(t);
            const attiva = t.numero === selezionata;
            return (
              <div key={t.numero} onClick={() => scegli(t.numero)} data-testid={`voce-tappa-${t.numero}`}
                style={{ padding: '8px 10px', borderRadius: 6, cursor: 'pointer', marginBottom: 2,
                  background: attiva ? '#EEF4FA' : 'transparent', borderLeft: `3px solid ${attiva ? '#1A3A5C' : 'transparent'}` }}>
                <div style={{ fontSize: '0.82rem', fontWeight: attiva ? 700 : 500, color: '#1A3A5C' }}>
                  {t.numero}. {t.titolo}
                </div>
                <div style={{ fontSize: '0.7rem', color: st.colore }}>
                  {st.icona} {st.testo}{t.n_da_verificare ? ` · ${t.n_da_verificare} da verificare` : ''}
                </div>
              </div>
            );
          })}
        </div>

        {/* Editor */}
        <TappaEditor progettoId={progettoId} tappa={tappa} tappe={tappe}
          dataInizio={dati.data_inizio_lavori} occupato={!!solaLettura}
          onAggiorna={carica} onModificata={onModificata} onApriSchema={onApriSchema} />
      </div>
    </div>
  );
}
