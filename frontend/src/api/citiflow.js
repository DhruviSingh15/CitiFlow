import axios from 'axios';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001/api/v1';

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Payment ───────────────────────────────────────────────────
export const processPayment = (body) => api.post('/payment/process', body);
export const getTransaction  = (ref)  => api.get(`/payment/${ref}`);

// ── Risk ──────────────────────────────────────────────────────
export const analyzeRisk = (body) => api.post('/risk/analyze', body);

// ── FX ────────────────────────────────────────────────────────
export const calculateFx = (body) => api.post('/fx/calculate', body);

// ── Routes ────────────────────────────────────────────────────
export const getAvailableRoutes = (params) =>
  api.get('/routes/available', { params });

// ── Control Tower ─────────────────────────────────────────────
export const getStats        = ()       => api.get('/control-tower/stats');
export const getTransactions = (params) => api.get('/control-tower/transactions', { params });
export const getLiquidity    = ()       => api.get('/control-tower/liquidity');
export const getRails        = ()       => api.get('/control-tower/rails');

// ── Admin ─────────────────────────────────────────────────────
export const updateLiquidity = (railId, body) =>
  api.patch(`/rails/${railId}/liquidity`, body);

export default api;
