import { useState, useEffect } from 'react';
import { getBudget } from '../utils/api';

/**
 * Banner permanente mostrato quando il budget demo è esaurito.
 * Compare all'apertura dell'app (se il budget è già finito) oppure
 * appena il server risponde 402 a un'operazione.
 * L'utente continua a vedere e usare tutto ciò che non ha costi.
 */
export default function DemoBanner() {
  const [messaggio, setMessaggio] = useState(null);

  useEffect(() => {
    getBudget()
      .then(r => {
        if (r.data?.demo_terminata) {
          setMessaggio('La demo è terminata: hai utilizzato tutto il budget disponibile.');
        }
      })
      .catch(() => {});

    const onTerminata = (e) => setMessaggio(e.detail || 'La demo è terminata.');
    window.addEventListener('sce-demo-terminata', onTerminata);
    return () => window.removeEventListener('sce-demo-terminata', onTerminata);
  }, []);

  if (!messaggio) return null;

  return (
    <div style={{
      background: '#FFF4D6', border: '1px solid #E0A800', borderRadius: 8,
      padding: '12px 16px', marginBottom: 20, color: '#5A4300', fontSize: '0.88rem',
      display: 'flex', gap: 10, alignItems: 'flex-start',
    }}>
      <span style={{ fontSize: '1.2rem' }}>⏳</span>
      <div>
        <strong>{messaggio}</strong>
        <div style={{ marginTop: 4 }}>
          Puoi continuare a consultare, modificare ed esportare tutti i risultati già prodotti.
          Le funzioni che usano l'intelligenza artificiale non sono più disponibili.
        </div>
      </div>
    </div>
  );
}
