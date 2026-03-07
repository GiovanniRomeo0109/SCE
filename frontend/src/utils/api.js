import axios from 'axios';

// Il proxy in package.json manda tutto a http://localhost:8000
const api = axios.create({ baseURL: '/api' });

// ── ANAGRAFICA ──────────────────────────────────────────────
export const getCommittenti    = () => api.get('/anagrafica/committenti');
export const createCommittente = (d) => api.post('/anagrafica/committenti', d);
export const updateCommittente = (id, d) => api.put(`/anagrafica/committenti/${id}`, d);
export const deleteCommittente = (id) => api.delete(`/anagrafica/committenti/${id}`);

export const getImprese    = () => api.get('/anagrafica/imprese');
export const createImpresa = (d) => api.post('/anagrafica/imprese', d);
export const updateImpresa = (id, d) => api.put(`/anagrafica/imprese/${id}`, d);
export const deleteImpresa = (id) => api.delete(`/anagrafica/imprese/${id}`);

export const getCoordinatori    = () => api.get('/anagrafica/coordinatori');
export const createCoordinatore = (d) => api.post('/anagrafica/coordinatori', d);
export const updateCoordinatore = (id, d) => api.put(`/anagrafica/coordinatori/${id}`, d);
export const deleteCoordinatore = (id) => api.delete(`/anagrafica/coordinatori/${id}`);

// ── AGENTE AI ───────────────────────────────────────────────
export const checkObbligatorieta = (d) => api.post('/agent/check-obbligatorieta', d);
export const generaContenutoAI   = (d) => api.post('/agent/genera-contenuto', d);

// ── DOCUMENTI ───────────────────────────────────────────────
export const generaDocumento = (d) => api.post('/documents/genera', d);
export const getStorico      = () => api.get('/documents/storico');
export const deleteDocumento = (id) => api.delete(`/documents/storico/${id}`);
export const getDownloadUrl  = (id) => `/documents/download/${id}`;
// ── ESTRAZIONE AI ─────────────────────────────────────────
export const estraiDati = (formData) =>
  api.post('/estrazione/analizza', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minuti — analisi può essere lenta
  });
  // Aggiungi questa riga alla fine
export const analisiRischi = (payload) => api.post('/agent/analisi-rischi', payload);
export default api;