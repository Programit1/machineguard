const rawBase = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
export const API_BASE = rawBase.startsWith('http') && !rawBase.endsWith('/api') ? `${rawBase}/api` : rawBase;

export async function fetchDashboardSummary() {
  const res = await fetch(`${API_BASE}/dashboard/summary`);
  if (!res.ok) throw new Error(`Failed to load dashboard summary: ${res.statusText}`);
  return res.json();
}

export async function fetchMachines() {
  const res = await fetch(`${API_BASE}/machines`);
  if (!res.ok) throw new Error(`Failed to load machines: ${res.statusText}`);
  return res.json();
}

export async function fetchMachineDetail(machineId) {
  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}`);
  if (!res.ok) throw new Error(`Failed to load machine: ${res.statusText}`);
  return res.json();
}

export async function createMachine(data) {
  const res = await fetch(`${API_BASE}/machines`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create machine: ${res.statusText}`);
  }
  return res.json();
}

export async function updateMachine(machineId, data) {
  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update machine: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteMachine(machineId) {
  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete machine: ${res.statusText}`);
  return res.json();
}

export async function fetchMachineTelemetry(machineId, limit = 60) {
  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}/telemetry?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load telemetry: ${res.statusText}`);
  return res.json();
}

export async function fetchMachinePredictions(machineId, limit = 30) {
  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}/predictions?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load predictions: ${res.statusText}`);
  return res.json();
}

export async function fetchAlerts(status = null, machineId = null) {
  const params = new URLSearchParams();
  if (status && status !== 'all') params.append('status', status);
  if (machineId) params.append('machine_id', machineId);
  const res = await fetch(`${API_BASE}/alerts?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load alerts: ${res.statusText}`);
  return res.json();
}

export async function updateAlertStatus(alertId, newStatus) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  });
  if (!res.ok) throw new Error(`Failed to update alert: ${res.statusText}`);
  return res.json();
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) return await res.json();
    return { status: 'down' };
  } catch {
    return { status: 'down' };
  }
}

export async function fetchModelStatus() {
  try {
    const res = await fetch(`${API_BASE}/ml/models/status`);
    if (res.ok) return await res.json();
    return { loaded: false };
  } catch {
    return { loaded: false };
  }
}

export async function fetchMLModelsStatus() {
  try {
    const res = await fetch(`${API_BASE}/ml/models/status`);
    if (res.ok) return await res.json();
    return { error: 'Failed to fetch status' };
  } catch (err) {
    return { error: err.message };
  }
}

export async function fetchMLMetadata() {
  const res = await fetch(`${API_BASE}/ml/models/metadata`);
  if (!res.ok) throw new Error(`Failed to load ML metadata: ${res.statusText}`);
  return res.json();
}

export async function fetchMLEvaluations() {
  const res = await fetch(`${API_BASE}/ml/models/evaluations`);
  if (!res.ok) throw new Error(`Failed to load ML evaluations: ${res.statusText}`);
  return res.json();
}

export async function predictFailure(payload) {
  const res = await fetch(`${API_BASE}/ml/failure/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failure prediction failed: ${res.statusText}`);
  }
  return res.json();
}

export async function detectAnomaly(payload) {
  const res = await fetch(`${API_BASE}/ml/anomaly/detect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Anomaly detection failed: ${res.statusText}`);
  }
  return res.json();
}

export async function predictRUL(payload) {
  const res = await fetch(`${API_BASE}/ml/rul/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `RUL prediction unavailable: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNotifications(status = null) {
  const url = status ? `${API_BASE}/notifications?status=${status}` : `${API_BASE}/notifications`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load notifications: ${res.statusText}`);
  return res.json();
}

export async function acknowledgeNotification(id) {
  const res = await fetch(`${API_BASE}/notifications/${id}/acknowledge`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to acknowledge notification: ${res.statusText}`);
  return res.json();
}

export async function resolveNotification(id) {
  const res = await fetch(`${API_BASE}/notifications/${id}/resolve`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to resolve notification: ${res.statusText}`);
  return res.json();
}

