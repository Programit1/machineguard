import { supabase, isSupabaseConfigured } from './supabaseClient';

const defaultLocalUrl = 'http://localhost:8000/api';
const rawBase = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app') ? defaultLocalUrl : '/api')
).replace(/\/$/, '');
export const API_BASE = rawBase.startsWith('http') && !rawBase.endsWith('/api') ? `${rawBase}/api` : rawBase;

// -----------------------------------------------------------------------------
// DASHBOARD & FLEET SUMMARY
// -----------------------------------------------------------------------------

export async function fetchDashboardSummary() {
  if (isSupabaseConfigured && supabase) {
    try {
      // 1. Fetch machines
      const { data: machines, error: mErr } = await supabase
        .from('machines')
        .select('*')
        .order('created_at', { ascending: false });
      if (mErr) throw mErr;

      // 2. Fetch recent readings
      const { data: recentTelemetry, error: rErr } = await supabase
        .from('sensor_readings')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(15);
      if (rErr) throw rErr;

      // 3. Fetch recent alerts
      const { data: recentAlerts, error: aErr } = await supabase
        .from('alerts')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(10);
      if (aErr) throw aErr;

      // 4. Fetch active incidents
      const { data: recentIncidents } = await supabase
        .from('incidents')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(10);

      // Compute aggregates
      const now = Date.now();
      let online_machines = 0;
      let healthy_machines = 0;
      let attention_machines = 0;
      let high_risk_machines = 0;
      let critical_risk_machines = 0;
      const risk_distribution = { Low: 0, Medium: 0, High: 0, Critical: 0 };

      // Map latest readings per machine
      const latestReadingMap = {};
      for (const r of recentTelemetry || []) {
        if (!latestReadingMap[r.machine_id]) {
          latestReadingMap[r.machine_id] = r;
        }
      }

      for (const m of machines || []) {
        const latestR = latestReadingMap[m.machine_id];
        const isOnline = latestR && (now - new Date(latestR.timestamp).getTime() <= 45000);
        if (isOnline) online_machines++;

        // Query prediction for machine
        const { data: pData } = await supabase
          .from('predictions')
          .select('*')
          .eq('machine_id', m.machine_id)
          .order('timestamp', { ascending: false })
          .limit(1);

        const pred = pData && pData[0];
        if (pred) {
          const cat = pred.risk_category || 'Low';
          if (risk_distribution[cat] !== undefined) risk_distribution[cat]++;
          if (cat === 'Critical') critical_risk_machines++;
          else if (cat === 'High') high_risk_machines++;
          else if (cat === 'Medium') attention_machines++;
          else healthy_machines++;
        } else {
          healthy_machines++;
          risk_distribution.Low++;
        }
      }

      const activeAlertsCount = (recentAlerts || []).filter(
        (a) => (a.status || '').toUpperCase() === 'ACTIVE'
      ).length;

      return {
        total_machines: (machines || []).length,
        online_machines,
        healthy_machines,
        attention_machines,
        high_risk_machines,
        critical_risk_machines,
        active_alerts_count: activeAlertsCount,
        risk_distribution,
        recent_alerts: recentAlerts || [],
        recent_telemetry: recentTelemetry || [],
        recent_incidents: recentIncidents || [],
      };
    } catch (err) {
      console.warn('Supabase fetchDashboardSummary fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/dashboard/summary`);
  if (!res.ok) throw new Error(`Failed to load dashboard summary: ${res.statusText}`);
  return res.json();
}

// -----------------------------------------------------------------------------
// MACHINES
// -----------------------------------------------------------------------------

export async function fetchMachines() {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data: machines, error } = await supabase
        .from('machines')
        .select('*')
        .order('created_at', { ascending: false });
      if (error) throw error;

      const now = Date.now();
      const cardSummaries = [];

      for (const m of machines || []) {
        // Fetch latest reading
        const { data: rData } = await supabase
          .from('sensor_readings')
          .select('*')
          .eq('machine_id', m.machine_id)
          .order('timestamp', { ascending: false })
          .limit(1);

        const latestReading = rData && rData[0];
        const isOnline = latestReading && (now - new Date(latestReading.timestamp).getTime() <= 45000);

        // Fetch latest prediction
        const { data: pData } = await supabase
          .from('predictions')
          .select('*')
          .eq('machine_id', m.machine_id)
          .order('timestamp', { ascending: false })
          .limit(1);

        const latestPred = pData && pData[0];

        // Active alerts
        const { count: activeAlertsCount } = await supabase
          .from('alerts')
          .select('*', { count: 'exact', head: true })
          .eq('machine_id', m.machine_id)
          .ilike('status', 'active');

        let health_status = 'Healthy';
        if (!latestPred) {
          health_status = 'No Data';
        } else if (latestPred.risk_category === 'Critical') {
          health_status = 'Critical Risk';
        } else if (latestPred.risk_category === 'High') {
          health_status = 'High Risk';
        } else if (latestPred.risk_category === 'Medium') {
          health_status = 'Attention Required';
        }

        cardSummaries.push({
          id: m.machine_id,
          machine_id: m.machine_id,
          name: m.name,
          machine_type: m.machine_type,
          location: m.location,
          description: m.description || '',
          type_variant: m.type_variant || 'M',
          is_online: Boolean(isOnline),
          status: isOnline ? 'ONLINE' : 'OFFLINE',
          last_telemetry_time: latestReading ? latestReading.timestamp : null,
          latest_reading: latestReading,
          latest_prediction: latestPred,
          health_status,
          active_alerts_count: activeAlertsCount || 0,
        });
      }

      return cardSummaries;
    } catch (err) {
      console.warn('Supabase fetchMachines fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/machines`);
  if (!res.ok) throw new Error(`Failed to load machines: ${res.statusText}`);
  return res.json();
}

export async function fetchMachineDetail(machineId) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('machines')
        .select('*')
        .eq('machine_id', machineId)
        .single();
      if (error) throw error;
      return data;
    } catch (err) {
      console.warn('Supabase fetchMachineDetail fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}`);
  if (!res.ok) throw new Error(`Failed to load machine: ${res.statusText}`);
  return res.json();
}

export async function createMachine(data) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data: created, error } = await supabase
        .from('machines')
        .insert([data])
        .select()
        .single();
      if (error) throw error;
      return created;
    } catch (err) {
      console.warn('Supabase createMachine fallback to API:', err);
    }
  }

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
  if (isSupabaseConfigured && supabase) {
    try {
      const { data: updated, error } = await supabase
        .from('machines')
        .update(data)
        .eq('machine_id', machineId)
        .select()
        .single();
      if (error) throw error;
      return updated;
    } catch (err) {
      console.warn('Supabase updateMachine fallback to API:', err);
    }
  }

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
  if (isSupabaseConfigured && supabase) {
    try {
      const { error } = await supabase
        .from('machines')
        .delete()
        .eq('machine_id', machineId);
      if (error) throw error;
      return { status: 'deleted', machine_id: machineId };
    } catch (err) {
      console.warn('Supabase deleteMachine fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete machine: ${res.statusText}`);
  return res.json();
}

// -----------------------------------------------------------------------------
// TELEMETRY & PREDICTIONS
// -----------------------------------------------------------------------------

export async function fetchMachineTelemetry(machineId, limit = 60) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('sensor_readings')
        .select('*')
        .eq('machine_id', machineId)
        .order('timestamp', { ascending: false })
        .limit(limit);
      if (error) throw error;
      return (data || []).reverse(); // chronological for charts
    } catch (err) {
      console.warn('Supabase fetchMachineTelemetry fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}/telemetry?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load telemetry: ${res.statusText}`);
  return res.json();
}

export async function fetchMachinePredictions(machineId, limit = 30) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('predictions')
        .select('*')
        .eq('machine_id', machineId)
        .order('timestamp', { ascending: false })
        .limit(limit);
      if (error) throw error;
      return data || [];
    } catch (err) {
      console.warn('Supabase fetchMachinePredictions fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/machines/${encodeURIComponent(machineId)}/predictions?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load predictions: ${res.statusText}`);
  return res.json();
}

// -----------------------------------------------------------------------------
// ALERTS & NOTIFICATIONS
// -----------------------------------------------------------------------------

export async function fetchAlerts(status = null, machineId = null) {
  if (isSupabaseConfigured && supabase) {
    try {
      let query = supabase.from('alerts').select('*').order('timestamp', { ascending: false });
      if (status && status !== 'all') {
        query = query.ilike('status', status);
      }
      if (machineId) {
        query = query.eq('machine_id', machineId);
      }
      const { data, error } = await query;
      if (error) throw error;
      return data || [];
    } catch (err) {
      console.warn('Supabase fetchAlerts fallback to API:', err);
    }
  }

  const params = new URLSearchParams();
  if (status && status !== 'all') params.append('status', status);
  if (machineId) params.append('machine_id', machineId);
  const res = await fetch(`${API_BASE}/alerts?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load alerts: ${res.statusText}`);
  return res.json();
}

export async function updateAlertStatus(alertId, newStatus) {
  if (isSupabaseConfigured && supabase) {
    try {
      const updateData = { status: newStatus.toUpperCase() };
      if (newStatus.toUpperCase() === 'ACKNOWLEDGED') {
        updateData.acknowledged_at = new Date().toISOString();
      } else if (newStatus.toUpperCase() === 'RESOLVED') {
        updateData.resolved_at = new Date().toISOString();
      }
      const { data, error } = await supabase
        .from('alerts')
        .update(updateData)
        .eq('id', alertId)
        .select()
        .single();
      if (error) throw error;
      return data;
    } catch (err) {
      console.warn('Supabase updateAlertStatus fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/alerts/${alertId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  });
  if (!res.ok) throw new Error(`Failed to update alert: ${res.statusText}`);
  return res.json();
}

// -----------------------------------------------------------------------------
// INCIDENTS & AUTOMATED VERIFICATION
// -----------------------------------------------------------------------------

export async function fetchIncidents(status = null, machineId = null) {
  if (isSupabaseConfigured && supabase) {
    try {
      let query = supabase.from('incidents').select('*').order('created_at', { ascending: false });
      if (status && status !== 'all') {
        query = query.ilike('status', status);
      }
      if (machineId) {
        query = query.eq('machine_id', machineId);
      }
      const { data, error } = await query;
      if (error) throw error;
      return data || [];
    } catch (err) {
      console.warn('Supabase fetchIncidents fallback to API:', err);
    }
  }

  const params = new URLSearchParams();
  if (status && status !== 'all') params.append('status', status);
  if (machineId) params.append('machine_id', machineId);
  const res = await fetch(`${API_BASE}/incidents?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load incidents: ${res.statusText}`);
  return res.json();
}

export async function getIncidentDetail(incidentId) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('incidents')
        .select('*')
        .eq('incident_id', incidentId)
        .single();
      if (error) throw error;
      return data;
    } catch (err) {
      console.warn('Supabase getIncidentDetail fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}`);
  if (!res.ok) throw new Error(`Failed to load incident: ${res.statusText}`);
  return res.json();
}

export async function updateIncidentStatus(incidentId, newStatus, operatorName = 'Operator') {
  if (isSupabaseConfigured && supabase) {
    try {
      const updateData = {
        status: newStatus,
        updated_at: new Date().toISOString(),
      };
      if (newStatus.toLowerCase() === 'acknowledged') {
        updateData.acknowledged_at = new Date().toISOString();
        updateData.acknowledged_by = operatorName;
      } else if (newStatus.toLowerCase() === 'resolved') {
        updateData.resolved_at = new Date().toISOString();
      }
      const { data, error } = await supabase
        .from('incidents')
        .update(updateData)
        .eq('incident_id', incidentId)
        .select()
        .single();
      if (error) throw error;
      return data;
    } catch (err) {
      console.warn('Supabase updateIncidentStatus fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: newStatus, operator_name: operatorName }),
  });
  if (!res.ok) throw new Error(`Failed to update incident: ${res.statusText}`);
  return res.json();
}

export async function recordMaintenance(data) {
  if (isSupabaseConfigured && supabase) {
    try {
      const nowIso = new Date().toISOString();
      const insertData = {
        machine_id: data.machine_id,
        incident_id: data.incident_id || null,
        action: data.action,
        technician: data.technician || 'System Operator',
        notes: data.notes || '',
        timestamp: nowIso,
        completed_at: nowIso,
      };

      const { data: createdLog, error } = await supabase
        .from('maintenance_logs')
        .insert([insertData])
        .select()
        .single();
      if (error) throw error;

      // If linked to an incident, advance incident status to "Verification Pending"
      if (data.incident_id) {
        await supabase
          .from('incidents')
          .update({
            status: 'Verification Pending',
            updated_at: nowIso,
          })
          .eq('incident_id', data.incident_id);

        // Create initial verification session record
        await supabase
          .from('incident_verifications')
          .insert([{
            incident_id: data.incident_id,
            machine_id: data.machine_id,
            maintenance_log_id: createdLog.id,
            status: 'IN_PROGRESS',
            consecutive_healthy_count: 0,
            required_healthy_count: 3,
            verification_timestamp: nowIso,
            evidence: `Maintenance logged by ${insertData.technician}: '${insertData.action}'. Awaiting 3 consecutive healthy cycles.`,
            supporting_telemetry_ids: '[]',
            evaluated_predictions: '{}',
            notes: insertData.notes,
          }]);
      }

      return createdLog;
    } catch (err) {
      console.warn('Supabase recordMaintenance fallback to API:', err);
    }
  }

  const url = data.incident_id
    ? `${API_BASE}/incidents/${encodeURIComponent(data.incident_id)}/maintenance`
    : `${API_BASE}/maintenance`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to record maintenance: ${res.statusText}`);
  return res.json();
}

export async function fetchMaintenanceLogs(machineId = null) {
  if (isSupabaseConfigured && supabase) {
    try {
      let query = supabase.from('maintenance_logs').select('*').order('timestamp', { ascending: false });
      if (machineId) {
        query = query.eq('machine_id', machineId);
      }
      const { data, error } = await query;
      if (error) throw error;
      return data || [];
    } catch (err) {
      console.warn('Supabase fetchMaintenanceLogs fallback to API:', err);
    }
  }

  const params = machineId ? `?machine_id=${encodeURIComponent(machineId)}` : '';
  const res = await fetch(`${API_BASE}/maintenance${params}`);
  if (!res.ok) throw new Error(`Failed to load maintenance logs: ${res.statusText}`);
  return res.json();
}

export async function fetchVerifications(incidentId) {
  if (isSupabaseConfigured && supabase) {
    try {
      const { data, error } = await supabase
        .from('incident_verifications')
        .select('*')
        .eq('incident_id', incidentId)
        .order('verification_timestamp', { ascending: false });
      if (error) throw error;
      return data || [];
    } catch (err) {
      console.warn('Supabase fetchVerifications fallback to API:', err);
    }
  }

  const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/verifications`);
  if (!res.ok) throw new Error(`Failed to load verifications: ${res.statusText}`);
  return res.json();
}

// -----------------------------------------------------------------------------
// SYSTEM STATUS & MODEL HEALTH
// -----------------------------------------------------------------------------

export async function checkBackendHealth() {
  let localBackend = { status: 'down' };
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    const res = await fetch(`${API_BASE}/health`, { signal: controller.signal });
    clearTimeout(timer);
    const contentType = res.headers.get('content-type') || '';
    if (res.ok && contentType.includes('application/json')) {
      localBackend = await res.json();
    }
  } catch {
    localBackend = { status: 'down' };
  }

  // Ping Supabase Cloud directly from browser
  let supabaseConnected = false;
  let supabasePingMs = null;
  let supabaseRowCount = 0;
  if (isSupabaseConfigured && supabase) {
    try {
      const t0 = performance.now();
      const { count, error } = await supabase
        .from('machines')
        .select('*', { count: 'exact', head: true });
      if (!error) {
        supabaseConnected = true;
        supabasePingMs = Math.max(1, Math.round(performance.now() - t0));
        supabaseRowCount = count || 0;
      }
    } catch (err) {
      console.warn('Supabase ping check error:', err);
    }
  }

  const isHealthy = localBackend.status === 'healthy' || supabaseConnected;

  return {
    ...localBackend,
    backendOnline: localBackend.status === 'healthy',
    supabaseConnected,
    supabasePingMs,
    supabaseRowCount,
    database_type: supabaseConnected ? 'PostgreSQL' : (localBackend.database_type || 'Unknown'),
    database: supabaseConnected ? 'postgresql_connected' : (localBackend.database || 'offline'),
    status: isHealthy ? 'healthy' : 'down',
  };
}

export async function fetchModelStatus() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    const res = await fetch(`${API_BASE}/ml/models/status`, { signal: controller.signal });
    clearTimeout(timer);
    const contentType = res.headers.get('content-type') || '';
    if (res.ok && contentType.includes('application/json')) {
      return await res.json();
    }
    return { loaded: false };
  } catch {
    return { loaded: false };
  }
}

export async function fetchMLModelsStatus() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    const res = await fetch(`${API_BASE}/ml/models/status`, { signal: controller.signal });
    clearTimeout(timer);
    const contentType = res.headers.get('content-type') || '';
    if (res.ok && contentType.includes('application/json')) {
      return await res.json();
    }
    return { error: 'Local backend paused' };
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
