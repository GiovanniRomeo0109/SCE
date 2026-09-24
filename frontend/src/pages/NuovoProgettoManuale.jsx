import { useNavigate } from 'react-router-dom';
import ProgettiPSC from '../components/progetti/ProgettiPSC';

/**
 * Nuovo Progetto Manuale (PSC): nessun documento da caricare e nessuna generazione AI delle tappe.
 * Le 12 tappe nascono vuote e il CSP le compila a mano. Resta disponibile l'abbinamento
 * automatico dei prezzi alle misure della tappa 11.
 */
export default function NuovoProgettoManuale() {
  const nav = useNavigate();
  return (
    <div>
      <div className="page-header">
        <h1>✍️ Nuovo Progetto Manuale</h1>
        <p>Piano di Sicurezza e Coordinamento compilato a mano, tappa per tappa, senza caricare documenti</p>
      </div>
      <ProgettiPSC modalita="manuale" onIndietro={() => nav('/nuovo')} />
    </div>
  );
}
