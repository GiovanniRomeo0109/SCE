/**
 * api.js aggiornato per Railway
 * - URL relativo (funziona sia in locale che in produzione)
 * - Aggiunge Bearer token a tutte le chiamate
 * - Gestisce 401 (redirect al login) e 429 (limite raggiunto)
 */

// In produzione (Railway) le API sono sullo stesso dominio → URL relativo
// In sviluppo locale → punta a localhost:8000
const BASE_URL = process.env.NODE_ENV === 'production'
  ? ''
  : 'http://localhost:8000';

function getToken() {
  return localStorage.getItem('sce_token');
}

export function logout() {
  localStorage.removeItem('sce_token');
  localStorage.removeItem('sce_user');
  window.location.href = '/';
}

export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  // Non impostare Content-Type per FormData (lo fa il browser)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error('Sessione scaduta — effettua di nuovo il login');
  }
  if (res.status === 402) {
    // Budget demo esaurito: avvisa l'app (banner) e interrompe l'operazione
    const data = await res.json().catch(() => ({}));
    const msg = data?.detail?.message || 'La demo è terminata.';
    window.dispatchEvent(new CustomEvent('sce-demo-terminata', { detail: msg }));
    throw new Error(msg);
  }
  if (res.status === 429) {
    const data = await res.json().catch(() => ({}));
    throw new Error(dettaglioErrore(data.detail) || 'Limite giornaliero raggiunto');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(dettaglioErrore(data.detail) || `Errore ${res.status}`);
  // Dopo ogni chiamata riuscita la barra del budget si aggiorna
  // (escluse le rotte /api/auth, altrimenti la barra richiamerebbe sé stessa in loop)
  if (!path.startsWith('/api/auth/')) window.dispatchEvent(new Event('sce-budget-refresh'));
  return { data, status: res.status };
}

// Converte il campo detail di FastAPI (stringa, oggetto o lista di errori) in testo
function dettaglioErrore(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(e => e.msg || JSON.stringify(e)).join(', ');
  return detail.message || JSON.stringify(detail);
}

// Link di download dei DOCX (il token viaggia come parametro, così funziona con <a href>)
export function downloadUrl(docId) {
  return `${BASE_URL}/api/documents/download/${docId}?token=${encodeURIComponent(getToken() || '')}`;
}

// ── Autenticazione ────────────────────────────────────────────────────────────
export const getCurrentUser = () => apiFetch('/api/auth/me');
export const getUsageStats  = () => apiFetch('/api/auth/usage');
export const getBudget      = () => apiFetch('/api/auth/budget');

// ── Storico ───────────────────────────────────────────────────────────────────
export const getStorico       = ()   => apiFetch('/api/documents/storico');
export const deleteDocumento  = (id) => apiFetch(`/api/documents/${id}`, { method: 'DELETE' });

// ── Anagrafica ────────────────────────────────────────────────────────────────
export const getCommittenti  = ()     => apiFetch('/api/anagrafica/committenti');
export const getImprese      = ()     => apiFetch('/api/anagrafica/imprese');
export const getCoordinatori = ()     => apiFetch('/api/anagrafica/coordinatori');
export const saveCommittente = (data) => apiFetch('/api/anagrafica/committenti', { method: 'POST', body: JSON.stringify(data) });
export const saveImpresa     = (data) => apiFetch('/api/anagrafica/imprese',     { method: 'POST', body: JSON.stringify(data) });
export const saveCoordinatore= (data) => apiFetch('/api/anagrafica/coordinatori',{ method: 'POST', body: JSON.stringify(data) });

// ── Agent ─────────────────────────────────────────────────────────────────────
export const checkObbligatorieta = (data) =>
  apiFetch('/api/agent/check-obbligatorieta', { method: 'POST', body: JSON.stringify(data) });
export const generaContenuto = (data) =>
  apiFetch('/api/agent/genera-contenuto', { method: 'POST', body: JSON.stringify(data) });
export const analisiRischi = (data) =>
  apiFetch('/agent/analisi-rischi', { method: 'POST', body: JSON.stringify(data) });

// ── Estrazione ────────────────────────────────────────────────────────────────
export const estraiDocumento = (formData) =>
  apiFetch('/api/estrazione/estrai', { method: 'POST', body: formData });

// ── Verifica ──────────────────────────────────────────────────────────────────
export const verificaPsc = (formData) =>
  apiFetch('/api/verifica/verifica-psc', { method: 'POST', body: formData });
export const verificaPos = (formData) =>
  apiFetch('/api/verifica/verifica-pos', { method: 'POST', body: formData });
export const verificaCongruita = (formData) =>
  apiFetch('/api/verifica/verifica-congruita', { method: 'POST', body: formData });
export const generaVerbale = (data) =>
  apiFetch('/api/verifica/genera-verbale', { method: 'POST', body: JSON.stringify(data) });

// ── Registrazione (no token richiesto) ────────────────────────────────────────
const _BASE = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000';
export async function register(body) {
  const res = await fetch(`${_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Errore registrazione');
  return json;
}

// ── Anagrafica CRUD completo ──────────────────────────────────────────────────
export const createCommittente  = (data)     => apiFetch('/api/anagrafica/committenti',          { method: 'POST',   body: JSON.stringify(data) });
export const createImpresa      = (data)     => apiFetch('/api/anagrafica/imprese',              { method: 'POST',   body: JSON.stringify(data) });
export const createCoordinatore = (data)     => apiFetch('/api/anagrafica/coordinatori',         { method: 'POST',   body: JSON.stringify(data) });
export const updateCommittente  = (id, data) => apiFetch(`/api/anagrafica/committenti/${id}`,   { method: 'PUT',    body: JSON.stringify(data) });
export const updateImpresa      = (id, data) => apiFetch(`/api/anagrafica/imprese/${id}`,       { method: 'PUT',    body: JSON.stringify(data) });
export const updateCoordinatore = (id, data) => apiFetch(`/api/anagrafica/coordinatori/${id}`,  { method: 'PUT',    body: JSON.stringify(data) });
export const deleteCommittente  = (id)       => apiFetch(`/api/anagrafica/committenti/${id}`,   { method: 'DELETE' });
export const deleteImpresa      = (id)       => apiFetch(`/api/anagrafica/imprese/${id}`,       { method: 'DELETE' });
export const deleteCoordinatore = (id)       => apiFetch(`/api/anagrafica/coordinatori/${id}`,  { method: 'DELETE' });

// ── Agent completo ────────────────────────────────────────────────────────────
export const generaDocumento    = (data) => apiFetch('/api/agent/genera-documento',  { method: 'POST', body: JSON.stringify(data) });
export const generaContenutoAI  = (data) => apiFetch('/api/agent/genera-contenuto',  { method: 'POST', body: JSON.stringify(data) });
export const estraiDati         = (formData) => apiFetch('/api/estrazione/estrai',   { method: 'POST', body: formData });

// ── Progetti PSC (blocco 2) ───────────────────────────────────────────────────
export const getProgetti        = ()               => apiFetch('/api/progetti');
export const creaProgetto       = (nome)           => apiFetch('/api/progetti', { method: 'POST', body: JSON.stringify({ nome }) });
export const getProgetto        = (id)             => apiFetch(`/api/progetti/${id}`);
export const rinominaProgetto   = (id, nome)       => apiFetch(`/api/progetti/${id}`, { method: 'PATCH', body: JSON.stringify({ nome }) });
export const eliminaProgetto    = (id)             => apiFetch(`/api/progetti/${id}`, { method: 'DELETE' });
export const caricaDocumentiProgetto = (id, formData) => apiFetch(`/api/progetti/${id}/documenti`, { method: 'POST', body: formData });
export const correggiTipoDocumento   = (id, docId, tipo) => apiFetch(`/api/progetti/${id}/documenti/${docId}`, { method: 'PATCH', body: JSON.stringify({ tipo }) });
export const rielaboraDocumento      = (id, docId) => apiFetch(`/api/progetti/${id}/documenti/${docId}/rielabora`, { method: 'POST' });
export const eliminaDocumentoProgetto = (id, docId) => apiFetch(`/api/progetti/${id}/documenti/${docId}`, { method: 'DELETE' });
export const getDatiDocumento        = (id, docId) => apiFetch(`/api/progetti/${id}/documenti/${docId}/dati`);
export const mappaturaDocumento      = (id, docId, m) => apiFetch(`/api/progetti/${id}/documenti/${docId}/mappatura`, { method: 'POST', body: JSON.stringify(m) });

// ── Elenchi prezzi (blocco 2) ─────────────────────────────────────────────────
export const getElenchi         = ()               => apiFetch('/api/elenchi');
export const caricaElenco       = (formData)       => apiFetch('/api/elenchi', { method: 'POST', body: formData });
export const rinominaElenco     = (id, nome)       => apiFetch(`/api/elenchi/${id}`, { method: 'PATCH', body: JSON.stringify({ nome }) });
export const eliminaElenco      = (id)             => apiFetch(`/api/elenchi/${id}`, { method: 'DELETE' });
export const mappaturaElenco    = (id, m)          => apiFetch(`/api/elenchi/${id}/mappatura`, { method: 'POST', body: JSON.stringify(m) });
export const cercaVociElenco    = (id, q)          => apiFetch(`/api/elenchi/${id}/voci?q=${encodeURIComponent(q || '')}`);

// ── Tappe PSC e questionario (blocco 3) ───────────────────────────────────────
export const getTappe          = (id)              => apiFetch(`/api/progetti/${id}/tappe`);
export const stimaTappe        = (id, numeri)      => apiFetch(`/api/progetti/${id}/tappe/stima?numeri=${numeri.join(',')}`);
export const avviaBozza        = (id)              => apiFetch(`/api/progetti/${id}/tappe/bozza`, { method: 'POST' });
export const interrompiTappe   = (id)              => apiFetch(`/api/progetti/${id}/tappe/interrompi`, { method: 'POST' });
export const generaTappa       = (id, n, nota)     => apiFetch(`/api/progetti/${id}/tappe/${n}/genera`, { method: 'POST', body: JSON.stringify({ nota: nota || null }) });
export const salvaTappa        = (id, n, sezioni)  => apiFetch(`/api/progetti/${id}/tappe/${n}`, { method: 'PUT', body: JSON.stringify({ sezioni }) });
export const tappaVerificata   = (id, n)           => apiFetch(`/api/progetti/${id}/tappe/${n}/verificata`, { method: 'POST' });
export const salvaDatiCSP      = (id, dati)        => apiFetch(`/api/progetti/${id}/dati-csp`, { method: 'PATCH', body: JSON.stringify(dati) });
export const getQuestionario   = (id)              => apiFetch(`/api/progetti/${id}/questionario`);
export const rispondiDomanda   = (id, domandaId, risposta) => apiFetch(`/api/progetti/${id}/questionario/${domandaId}`, { method: 'PATCH', body: JSON.stringify({ risposta }) });
export const applicaRisposte   = (id)              => apiFetch(`/api/progetti/${id}/questionario/applica`, { method: 'POST' });

// ── Default export ────────────────────────────────────────────────────────────
const api = {
  apiFetch, logout, getCurrentUser, getUsageStats, getBudget, downloadUrl, register,
  getStorico, deleteDocumento,
  getCommittenti, getImprese, getCoordinatori,
  saveCommittente, saveImpresa, saveCoordinatore,
  createCommittente, createImpresa, createCoordinatore,
  updateCommittente, updateImpresa, updateCoordinatore,
  deleteCommittente, deleteImpresa, deleteCoordinatore,
  checkObbligatorieta, generaContenuto, analisiRischi,
  generaDocumento, generaContenutoAI,
  estraiDocumento, estraiDati,
  verificaPsc, verificaPos, verificaCongruita, generaVerbale,
  getProgetti, creaProgetto, getProgetto, rinominaProgetto, eliminaProgetto,
  caricaDocumentiProgetto, correggiTipoDocumento, rielaboraDocumento,
  eliminaDocumentoProgetto, getDatiDocumento, mappaturaDocumento,
  getElenchi, caricaElenco, rinominaElenco, eliminaElenco, mappaturaElenco, cercaVociElenco,
  getTappe, stimaTappe, avviaBozza, interrompiTappe, generaTappa, salvaTappa, tappaVerificata,
  salvaDatiCSP, getQuestionario, rispondiDomanda, applicaRisposte,
};
export default api;
