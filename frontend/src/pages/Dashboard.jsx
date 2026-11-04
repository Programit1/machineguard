import React from 'react';
import {
  Cpu,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Bell,
  ArrowRight,
  Clock,
  ServerOff,
  RefreshCw,
  Gauge,
  Thermometer,
  RotateCw,
  Activity,
  Layers,
  Radio,
  CheckCircle2,
} from 'lucide-react';

import RiskBadge from '../components/RiskBadge';
import StatusBadge from '../components/StatusBadge';
import { API_BASE } from '../api';

function formatLocalTime(ts) {
  if (!ts) return 'Awaiting telemetry';
  const str = String(ts);
  const iso = (!str.endsWith('Z') && !str.includes('+')) ? `${str}Z` : str;
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatRelativeTime(ts) {
  if (!ts) return '';
  const str = String(ts);
  const iso = (!str.endsWith('Z') && !str.includes('+')) ? `${str}Z` : str;
  const deltaSec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (deltaSec < 2) return 'Just now';
  if (deltaSec < 60) return `${deltaSec}s ago`;
  const mins = Math.floor(deltaSec / 60);
  return `${mins}m ago`;
}

export default function Dashboard({
  summary,
  machines = [],
  backendOnline = true,
  onRetry,
  onSelectMachine,
  onNavigateToMachines,
  onNavigateToAlerts,
}) {
  // Loading State
  if (!summary) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-500">
        <Activity className="h-6 w-6 animate-spin text-blue-600" />
        <span className="text-xs font-medium">Connecting to machine telemetry channel...</span>
      </div>
    );
  }

  // Fleet stats
  const totalMachines = summary.total_machines || machines.length;
  const runningMachines = summary.online_machines || machines.filter(m => m.is_online).length;
  const warningMachines = summary.attention_machines || 0;
  const criticalMachines = summary.critical_risk_machines || 0;
  const totalActiveAlerts = summary.active_alerts_count || 0;

  // Primary two monitored machine cards as specified
  const primaryMachines = machines.slice(0, 2);

  // Overall Fleet Health status (only elevate to warning/critical if there are active unresolved alerts)
  const fleetHealth = (totalActiveAlerts > 0 && criticalMachines > 0)
    ? { title: 'Critical Attention Required', color: 'bg-rose-50 border-rose-200 text-rose-800', desc: `${criticalMachines} machinery unit(s) report active safety alarms.` }
    : (totalActiveAlerts > 0 && warningMachines > 0)
    ? { title: 'Advisory / Maintenance Review', color: 'bg-amber-50 border-amber-200 text-amber-800', desc: `${warningMachines} unit(s) exhibit elevated risk or statistical operational anomalies.` }
    : { title: 'Nominal Fleet Condition', color: 'bg-emerald-50 border-emerald-200 text-emerald-800', desc: 'All monitored assets are operating within standard mechanical and thermal tolerances.' };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">

      {/* Critical Incident Banner (only displayed when an ACTIVE unresolved alert is open) */}
      {totalActiveAlerts > 0 && criticalMachines > 0 && (
        <div className="rounded-xl border border-rose-300 bg-rose-50 p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-rose-900">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-100 text-rose-700 border border-rose-300 shrink-0">
              <AlertOctagon className="h-5 w-5 text-rose-600 animate-pulse" />
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-rose-800">
                Critical Incident Notification ({criticalMachines} Machine{criticalMachines > 1 ? 's' : ''} in Fault State)
              </div>
              <p className="text-xs text-rose-700 mt-0.5">
                Active fault condition detected. Review incident log and execute corrective actions.
              </p>
            </div>
          </div>
          {onNavigateToAlerts && (
            <button
              onClick={onNavigateToAlerts}
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-xs transition-colors shrink-0"
            >
              <span>Manage Incidents</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      {/* 1. Overall Fleet Health Overview Banner */}
      <div className={`rounded-xl border p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${fleetHealth.color}`}>
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white shadow-xs border border-inherit shrink-0">
            {criticalMachines > 0 ? (
              <AlertOctagon className="h-5 w-5 text-rose-600" />
            ) : warningMachines > 0 ? (
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
            )}
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider">Fleet Health Overview: {fleetHealth.title}</div>
            <p className="text-xs opacity-90 mt-0.5">{fleetHealth.desc}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded bg-white border border-inherit">
            {runningMachines} / {totalMachines} Online
          </span>
        </div>
      </div>

      {/* 2. Fleet Condition Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Total Machines */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Total Machinery</span>
            <Cpu className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-900">{totalMachines}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">Registered assets</div>
        </div>

        {/* Running Machines */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Running Machinery</span>
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-emerald-700">{runningMachines}</div>
          <div className="mt-0.5 text-[11px] text-emerald-600 font-medium">Active telemetry stream</div>
        </div>

        {/* Machines with Warnings */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Attention Required</span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-amber-700">{warningMachines}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">Elevated risk or anomaly</div>
        </div>

        {/* Critical Alerts */}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Critical Alarms</span>
            <AlertOctagon className="h-4 w-4 text-rose-600" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-rose-700">{criticalMachines}</div>
          <div className="mt-0.5 text-[11px] text-rose-600 font-medium">Immediate intervention</div>
        </div>

        {/* Total Active Alerts */}
        <div
          onClick={onNavigateToAlerts}
          className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs cursor-pointer hover:border-blue-300 transition-colors"
        >
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Active Incidents</span>
            <Bell className="h-4 w-4 text-slate-500" />
          </div>
          <div className={`mt-2 text-2xl font-bold font-mono ${totalActiveAlerts > 0 ? 'text-rose-700' : 'text-slate-800'}`}>
            {totalActiveAlerts}
          </div>
          <div className="mt-0.5 text-[11px] text-blue-600 flex items-center gap-1 font-medium">
            <span>Audit alerts</span>
            <ArrowRight className="h-3 w-3" />
          </div>
        </div>
      </div>

      {/* 3. Featured Monitored Machinery (Live Cards) */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 tracking-tight uppercase">
              Monitored Machinery (Real-Time Ingestion)
            </h2>
            <p className="text-xs text-slate-500">
              Live sensor telemetry feeds, machine learning condition inference, and mechanical state
            </p>
          </div>
          {machines.length > 2 && onNavigateToMachines && (
            <button
              onClick={onNavigateToMachines}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-900"
            >
              <span>View all {machines.length} units in fleet</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {primaryMachines.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
            <Cpu className="h-8 w-8 text-slate-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-slate-700">No machinery registered in database.</p>
            <p className="text-xs text-slate-500 mt-1">Enroll equipment on the Machines page to begin real-time monitoring.</p>
            <button
              onClick={onNavigateToMachines}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors shadow-xs"
            >
              <span>Go to Machines</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {primaryMachines.map((m) => {
              const reading = m.latest_reading;
              const pred = m.latest_prediction;
              const riskCat = pred ? pred.risk_category : 'Low';
              const rawProb = pred?.failure_probability !== null && pred?.failure_probability !== undefined
                ? pred.failure_probability
                : 0.0;
              const probPct = rawProb <= 1.0 ? rawProb * 100.0 : rawProb;

              const isAnomaly = Boolean(pred?.anomaly || pred?.anomaly_detected);
              const anomScore = pred?.anomaly_score;
              const anomLabel = pred?.anomaly_label || (isAnomaly ? 'Anomaly' : 'Normal');

              const rulCycles = pred?.estimated_remaining_cuts;
              const rulUnit = pred?.rul_unit || 'cycles';

              const ts = reading?.timestamp || pred?.timestamp;
              const iso = ts ? ((!String(ts).endsWith('Z') && !String(ts).includes('+')) ? `${ts}Z` : ts) : null;
              const deltaSec = iso ? Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000)) : 999;
              const isStale = deltaSec > 45;
              const isActuallyOnline = m.is_online && !isStale;

              return (
                <div
                  key={m.machine_id}
                  className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden flex flex-col justify-between"
                >
                  {/* Card Header */}
                  <div className="p-4 border-b border-slate-100 bg-slate-50/60">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold bg-slate-100 text-slate-900 border border-slate-300 px-2 py-0.5 rounded">
                            {m.machine_id}
                          </span>
                          <StatusBadge
                            isOnline={isActuallyOnline}
                            health={!isActuallyOnline ? 'Offline' : m.health_status}
                          />
                          <span className="text-[11px] font-medium text-slate-500">
                            {m.type_variant ? `Variant ${m.type_variant}` : 'Standard Variant'}
                          </span>
                        </div>
                        <h3 className="mt-1.5 text-base font-bold text-slate-900">
                          {m.name}
                        </h3>
                        <p className="text-xs text-slate-500">
                          {m.machine_type} • {m.location}
                        </p>
                      </div>

                      <div className="text-right">
                        <div className="flex items-center gap-1 text-[11px] text-slate-500 font-mono justify-end">
                          <Clock className="h-3 w-3" />
                          <span>{formatLocalTime(ts)}</span>
                        </div>
                        <span className={`text-[10px] font-mono font-medium ${isStale ? 'text-amber-700' : 'text-slate-400'}`}>
                          {isStale ? `Stale (${deltaSec}s ago)` : formatRelativeTime(ts)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* ML Diagnoses Bar (Unmerged) */}
                  <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100 p-3 bg-white text-center">
                    {/* Failure Probability */}
                    <div className="px-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                        Failure Probability
                      </div>
                      <div className="flex items-center justify-center gap-1.5">
                        <span className="text-lg font-bold font-mono text-slate-900">
                          {probPct.toFixed(1)}%
                        </span>
                        <RiskBadge category={riskCat} size="sm" />
                      </div>
                    </div>

                    {/* Operational Anomaly Detection */}
                    <div className="px-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                        Anomaly Status
                      </div>
                      <div className="flex items-center justify-center gap-1.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${
                            isAnomaly
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          }`}
                        >
                          {isAnomaly ? 'Unusual' : 'Normal'}
                        </span>
                      </div>
                    </div>

                    {/* Remaining Useful Life */}
                    <div className="px-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                        Remaining Life (RUL)
                      </div>
                      <div className="text-lg font-bold font-mono text-slate-900">
                        {rulCycles !== null && rulCycles !== undefined
                          ? `${Math.round(rulCycles)} ${rulUnit}`
                          : pred?.rul_available ? 'Active' : 'Unavailable'}
                      </div>
                    </div>
                  </div>

                  {/* Sensor Snapshot */}
                  <div className="p-4 bg-white">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
                      Sensor Measurements
                    </div>
                    {reading ? (
                      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Speed</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.rotational_speed !== null ? `${Math.round(reading.rotational_speed)}` : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">rpm</div>
                        </div>

                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Torque</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.torque !== null ? `${reading.torque.toFixed(1)}` : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">Nm</div>
                        </div>

                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Tool Wear</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.tool_wear !== null ? `${Math.round(reading.tool_wear)}` : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">min</div>
                        </div>

                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Process Temp</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.temperature !== null
                              ? `${reading.temperature.toFixed(1)}°`
                              : reading.process_temperature
                                ? `${(reading.process_temperature - 273.15).toFixed(1)}°`
                                : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">°C</div>
                        </div>

                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Vibration</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.vibration !== null ? `${reading.vibration.toFixed(2)}` : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">mm/s</div>
                        </div>

                        <div className="rounded-md border border-slate-100 bg-slate-50/70 p-2 text-center">
                          <div className="text-[10px] text-slate-500">Pressure</div>
                          <div className="mt-0.5 font-mono text-xs font-bold text-slate-900">
                            {reading.pressure !== null ? `${reading.pressure.toFixed(1)}` : '—'}
                          </div>
                          <div className="text-[9px] text-slate-400">bar</div>
                        </div>
                      </div>
                    ) : (
                      <div className="py-4 text-center text-xs text-slate-400">
                        No telemetry packets received for this machine yet.
                      </div>
                    )}
                  </div>

                  {/* Card Footer */}
                  <div className="p-3 border-t border-slate-100 bg-slate-50/60 flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-600">
                      Overall Health:{' '}
                      <span className={`font-semibold ${
                        m.health_status === 'Critical Risk' ? 'text-rose-700' :
                        m.health_status === 'Attention Required' ? 'text-amber-700' : 'text-emerald-700'
                      }`}>
                        {m.health_status || 'Healthy'}
                      </span>
                    </span>

                    <button
                      onClick={() => onSelectMachine(m.machine_id)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
                    >
                      <span>Open Monitoring</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Split Section: Recent Telemetry Updates & Recent Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent Telemetry Feed */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-blue-600" />
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-tight">
                Recent Telemetry Stream
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">5.0s Cycle</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-y border-slate-100">
                <tr>
                  <th className="py-2 px-2.5">Time</th>
                  <th className="py-2 px-2.5">Machine</th>
                  <th className="py-2 px-2.5">Speed / Torque</th>
                  <th className="py-2 px-2.5">Vibration</th>
                  <th className="py-2 px-2.5">Wear</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {(summary.recent_telemetry || []).slice(0, 5).map((t, idx) => (
                  <tr key={t.id || idx} className="hover:bg-slate-50/70">
                    <td className="py-2 px-2.5 text-slate-500">{formatLocalTime(t.timestamp)}</td>
                    <td className="py-2 px-2.5 font-bold text-slate-900">
                      <button
                        onClick={() => onSelectMachine(t.machine_id)}
                        className="text-blue-700 hover:underline"
                      >
                        {t.machine_id}
                      </button>
                    </td>
                    <td className="py-2 px-2.5 text-slate-700">
                      {t.rotational_speed ? `${Math.round(t.rotational_speed)} rpm` : '—'} / {t.torque ? `${t.torque.toFixed(1)} Nm` : '—'}
                    </td>
                    <td className="py-2 px-2.5 text-slate-700">
                      {t.vibration ? `${t.vibration.toFixed(2)} mm/s` : '—'}
                    </td>
                    <td className="py-2 px-2.5 text-slate-700">
                      {t.tool_wear ? `${Math.round(t.tool_wear)} min` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Alerts Feed */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-rose-600" />
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-tight">
                Recent Incident Alerts
              </h3>
            </div>
            {onNavigateToAlerts && (
              <button
                onClick={onNavigateToAlerts}
                className="text-xs font-semibold text-blue-700 hover:text-blue-900 flex items-center gap-1"
              >
                <span>View all</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-y border-slate-100">
                <tr>
                  <th className="py-2 px-2.5">Machine</th>
                  <th className="py-2 px-2.5">Severity</th>
                  <th className="py-2 px-2.5">Alert</th>
                  <th className="py-2 px-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {(summary.recent_alerts || []).slice(0, 5).map((a) => {
                  const isResolved = a.status?.toUpperCase() === 'RESOLVED';
                  return (
                    <tr key={a.id} className="hover:bg-slate-50/70">
                      <td className="py-2 px-2.5 font-bold text-slate-900">
                        <button
                          onClick={() => onSelectMachine(a.machine_id)}
                          className="text-blue-700 hover:underline"
                        >
                          {a.machine_id}
                        </button>
                      </td>
                      <td className="py-2 px-2.5 font-sans">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            a.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                            a.severity === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                            'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {a.severity}
                        </span>
                      </td>
                      <td className="py-2 px-2.5 font-sans text-slate-700 max-w-xs truncate">
                        {a.title || a.reason}
                      </td>
                      <td className="py-2 px-2.5 font-sans">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            isResolved ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800 animate-pulse'
                          }`}
                        >
                          {a.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
