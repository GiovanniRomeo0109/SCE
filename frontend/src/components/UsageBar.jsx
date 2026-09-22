import { useState, useEffect, useCallback } from 'react';
import { getBudget } from '../utils/api';

/**
 * Barra del budget demo nella sidebar.
 * Si aggiorna all'avvio, dopo ogni operazione (evento 'sce-budget-refresh')
 * e quando il server segnala la fine della demo.
 */
export default function UsageBar() {
  const [b, setB] = useState(null);

  const carica = useCallback(() => {
    getBudget().then(r => setB(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    carica();
    window.addEventListener('sce-budget-refresh', carica);
    window.addEventListener('sce-demo-terminata', carica);
    return () => {
      window.removeEventListener('sce-budget-refresh', carica);
      window.removeEventListener('sce-demo-terminata', carica);
    };
  }, [carica]);

  if (!b) return null;

  const box = { padding: '10px 12px', fontSize: '0.78rem', color: '#C9D3DE' };

  if (b.is_admin) {
    return (
      <div style={box}>
        <div style={{ fontWeight: 700, color: '#F5C842' }}>👑 Amministratore</div>
        <div>Nessun limite · spesi € {b.speso_eur.toFixed(2)}</div>
      </div>
    );
  }

  const perc = Math.min(100, (b.speso_eur / b.limite_eur) * 100);
  const colore = b.demo_terminata ? '#E74C3C' : perc > 75 ? '#F39C12' : '#27AE60';

  return (
    <div style={box}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontWeight: 700 }}>Budget demo</span>
        <span>€ {b.residuo_eur.toFixed(2)} / € {b.limite_eur.toFixed(2)}</span>
      </div>
      <div style={{ height: 6, background: 'rgba(255,255,255,0.12)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${perc}%`, height: '100%', background: colore, transition: 'width .3s' }} />
      </div>
      <div style={{ marginTop: 6, color: b.demo_terminata ? '#FF8A80' : '#8A9BB0' }}>
        {b.demo_terminata ? 'Demo terminata' : `Chiamate oggi: ${b.chiamate_oggi} / ${b.max_chiamate_giorno}`}
      </div>
    </div>
  );
}
