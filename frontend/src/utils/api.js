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
  if (res.status === 429) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Limite giornaliero raggiunto');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Errore ${res.status}`);
  return { data, status: res.status };
}

// ── Autenticazione ────────────────────────────────────────────────────────────
export const getCurrentUser = () => apiFetch('/api/auth/me');
export const getUsageStats  = () => apiFetch('/api/auth/usage');

// ── Storico ───────────────────────────────────────────────────────────────────
export const getStorico       = ()   => apiFetch('/api/documents/storico');
export const deleteDocumento  = (id) => apiFetch(`/api/documents/${id}`, { method: 'DELETE' });

// ── Anagrafica ────────────────────────────────────────────────────────────────
export const getCommittenti   = ()         => apiFetch('/api/anagrafica/committenti');
export const getImprese       = ()         => apiFetch('/api/anagrafica/imprese');
export const getCoordinatori  = ()         => apiFetch('/api/anagrafica/coordinatori');

// CREATE
export const saveCommittente  = (data)     => apiFetch('/api/anagrafica/committenti',       { method: 'POST',   body: JSON.stringify(data) });
export const saveImpresa      = (data)     => apiFetch('/api/anagrafica/imprese',           { method: 'POST',   body: JSON.stringify(data) });
export const saveCoordinatore = (data)     => apiFetch('/api/anagrafica/coordinatori',      { method: 'POST',   body: JSON.stringify(data) });
// Alias create* → save* (usati da alcuni componenti)
export const createCommittente  = (data)   => apiFetch('/api/anagrafica/committenti',       { method: 'POST',   body: JSON.stringify(data) });
export const createImpresa      = (data)   => apiFetch('/api/anagrafica/imprese',           { method: 'POST',   body: JSON.stringify(data) });
export const createCoordinatore = (data)   => apiFetch('/api/anagrafica/coordinatori',      { method: 'POST',   body: JSON.stringify(data) });

// UPDATE
export const updateCommittente  = (id, data) => apiFetch(`/api/anagrafica/committenti/${id}`,  { method: 'PUT',    body: JSON.stringify(data) });
export const updateImpresa      = (id, data) => apiFetch(`/api/anagrafica/imprese/${id}`,      { method: 'PUT',    body: JSON.stringify(data) });
export const updateCoordinatore = (id, data) => apiFetch(`/api/anagrafica/coordinatori/${id}`, { method: 'PUT',    body: JSON.stringify(data) });

// DELETE
export const deleteCommittente  = (id)     => apiFetch(`/api/anagrafica/committenti/${id}`,    { method: 'DELETE' });
export const deleteImpresa      = (id)     => apiFetch(`/api/anagrafica/imprese/${id}`,        { method: 'DELETE' });
export const deleteCoordinatore = (id)     => apiFetch(`/api/anagrafica/coordinatori/${id}`,   { method: 'DELETE' });

// ── Agent ─────────────────────────────────────────────────────────────────────
export const checkObbligatorieta = (data) =>
  apiFetch('/api/agent/check-obbligatorieta', { method: 'POST', body: JSON.stringify(data) });
export const generaContenuto = (data) =>
  apiFetch('/api/agent/genera-contenuto', { method: 'POST', body: JSON.stringify(data) });
export const analisiRischi = (data) =>
  apiFetch('/agent/analisi-rischi', { method: 'POST', body: JSON.stringify(data) });
export const generaDocumento = (data) =>
  apiFetch('/api/agent/genera-documento', { method: 'POST', body: JSON.stringify(data) });
// Alias usato da WizardPSC e WizardPOS
export const generaContenutoAI = (data) =>
  apiFetch('/api/agent/genera-contenuto', { method: 'POST', body: JSON.stringify(data) });

// ── Estrazione ────────────────────────────────────────────────────────────────
export const estraiDocumento = (formData) =>
  apiFetch('/api/estrazione/estrai', { method: 'POST', body: formData });
// Alias usato da alcuni componenti
export const estraiDati = (formData) =>
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
