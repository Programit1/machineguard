import React, { useState, useEffect } from 'react';
import {
  Bell,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  Clock,
  Wrench,
  Cpu,
  Check,
  ArrowRight,
  Filter,
} from 'lucide-react';
import { fetchAlerts, updateAlertStatus, fetchMachines } from '../api';

function formatLocalTime(ts) {
  if (!ts) return '—';
  const str = String(ts);
  const iso = (!str.endsWith('Z') && !str.includes('+')) ? `${str}Z` : str;
  return new Date(iso).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function Alerts({ onSelectMachine }) {
  const [alerts, setAlerts] = useState([]);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all'); // all, active, resolved
  const [severityFilter, setSeverityFilter] = useState('all');
  const [machineFilter, setMachineFilter] = useState('all');

  const loadAlerts = async () => {
    try {
      const [alertData, machineData] = await Promise.all([
        fetchAlerts(statusFilter === 'all' ? null : statusFilter),
        fetchMachines().catch(() => []),
      ]);
      setAlerts(alertData);
      setMachines(machineData);
    } catch (err) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 2000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  const handleResolve = async (alertId) => {
    try {
      await updateAlertStatus(alertId, 'RESOLVED');
      await loadAlerts();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    // Severity Filter
    if (severityFilter !== 'all') {
      const sev = (a.severity || a.risk_level || '').toUpperCase();
      if (sev !== severityFilter.toUpperCase()) return false;
    }
    // Machine Filter
    if (machineFilter !== 'all' && a.machine_id !== machineFilter) {
      return false;
    }
    // Status Filter (client-side backup for robust consistency)
    if (statusFilter !== 'all') {
      const isResolved = a.status?.toUpperCase() === 'RESOLVED';
      if (statusFilter === 'active' && isResolved) return false;
      if (statusFilter === 'resolved' && !isResolved) return false;
    }
    return true;
  });

  const activeCount = alerts.filter((a) => a.status?.toUpperCase() === 'ACTIVE').length;
  const resolvedCount = alerts.filter((a) => a.status?.toUpperCase() === 'RESOLVED').length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header & Filter Controls Bar */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 tracking-tight">
            Incident Alerts & Alarm Center
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational rule violations, ML failure alerts, and anomaly records
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-slate-900 shadow-xs"
          >
            <option value="all">All Alerts ({alerts.length})</option>
            <option value="active">Active Only ({activeCount})</option>
            <option value="resolved">Resolved History ({resolvedCount})</option>
          </select>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-slate-900 shadow-xs"
          >
            <option value="all">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="WARNING">Warning / Medium</option>
            <option value="LOW">Low</option>
          </select>

          {/* Machine Filter */}
          <select
            value={machineFilter}
            onChange={(e) => setMachineFilter(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-slate-900 shadow-xs"
          >
            <option value="all">All Machines</option>
            {machines.map((m) => (
              <option key={m.machine_id} value={m.machine_id}>
                {m.machine_id} - {m.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Alerts Structured Feed */}
      {filteredAlerts.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500 shadow-xs">
          <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
          <h3 className="text-sm font-bold text-slate-800">No matching alerts</h3>
          <p className="text-xs text-slate-500 mt-1">
            {statusFilter === 'active'
              ? 'All machinery operating within safe thresholds. No active unresolved alarms.'
              : 'No alert entries match the selected filter criteria.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {filteredAlerts.map((alert) => {
            const isResolved = alert.status?.toUpperCase() === 'RESOLVED';
            const sev = (alert.severity || alert.risk_level || 'HIGH').toUpperCase();
            const isCritical = sev === 'CRITICAL';
            const isHigh = sev === 'HIGH';
            const isMedium = sev === 'WARNING' || sev === 'MEDIUM';

            // Severity Badge Styling as specified:
            // Red: Critical, Orange: High, Amber: Medium, Neutral: Low, Green: Resolved
            let badgeBg = 'bg-slate-100 text-slate-700 border-slate-200';
            let Icon = AlertTriangle;

            if (isResolved) {
              badgeBg = 'bg-emerald-50 text-emerald-800 border-emerald-200';
              Icon = CheckCircle;
            } else if (isCritical) {
              badgeBg = 'bg-rose-50 text-rose-800 border-rose-200';
              Icon = AlertOctagon;
            } else if (isHigh) {
              badgeBg = 'bg-orange-50 text-orange-800 border-orange-200';
              Icon = AlertTriangle;
            } else if (isMedium) {
              badgeBg = 'bg-amber-50 text-amber-800 border-amber-200';
              Icon = AlertTriangle;
            }

            // Triggering values object or JSON
            let trigVals = alert.triggering_values;
            if (typeof trigVals === 'string') {
              try {
                trigVals = JSON.parse(trigVals);
              } catch {
                trigVals = null;
              }
            }

            return (
              <div
                key={alert.id}
                className={`rounded-xl border bg-white p-4 shadow-xs transition-colors ${
                  isResolved
                    ? 'border-slate-200 opacity-80'
                    : isCritical
                    ? 'border-rose-300 ring-1 ring-rose-200'
                    : isHigh
                    ? 'border-orange-300'
                    : 'border-slate-200'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  {/* Left Column: Severity, Machine, Title, Description */}
                  <div className="flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Severity Label & Icon */}
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold uppercase border ${badgeBg}`}>
                        <Icon className="h-3.5 w-3.5" />
                        <span>{isResolved ? 'Resolved' : sev}</span>
                      </span>

                      {/* Machine ID & Name (Clickable) */}
                      <button
                        onClick={() => onSelectMachine(alert.machine_id)}
                        className="inline-flex items-center gap-1 font-mono text-xs font-bold text-blue-700 hover:text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-200"
                        title="Open machine monitoring page"
                      >
                        <Cpu className="h-3 w-3" />
                        <span>{alert.machine_id}</span>
                      </button>

                      <span className="text-xs font-semibold text-slate-800">
                        {alert.machine_name}
                      </span>

                      {/* Alert Source */}
                      {alert.alert_source && (
                        <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.2 rounded border border-slate-200 uppercase">
                          Src: {alert.alert_source}
                        </span>
                      )}

                      {/* Timestamp */}
                      <div className="flex items-center gap-1 text-[11px] font-mono text-slate-500 ml-auto">
                        <Clock className="h-3 w-3 text-slate-400" />
                        <span>{formatLocalTime(alert.timestamp)}</span>
                      </div>
                    </div>

                    {/* Alert Title & Reason */}
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">
                        {alert.title || alert.reason}
                      </h3>
                      <p className="mt-0.5 text-xs text-slate-600 leading-relaxed">
                        {alert.reason}
                      </p>
                    </div>

                    {/* Triggering Sensor Values & Configured Rule */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                      {/* Configured Threshold or Rule */}
                      {alert.threshold_or_rule && (
                        <div className="text-[11px] text-slate-600 rounded bg-slate-50 border border-slate-200 p-2">
                          <span className="font-semibold text-slate-700">Configured Rule / Limit: </span>
                          <span className="font-mono text-slate-800">{alert.threshold_or_rule}</span>
                        </div>
                      )}

                      {/* Actual Triggering Values */}
                      {trigVals && Object.keys(trigVals).length > 0 && (
                        <div className="text-[11px] text-slate-600 rounded bg-slate-50 border border-slate-200 p-2">
                          <span className="font-semibold text-slate-700">Triggering Values: </span>
                          <span className="font-mono text-slate-800">
                            {Object.entries(trigVals).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Recommended Action */}
                    {alert.recommendation && (
                      <div className="text-xs text-slate-600 flex items-start gap-1.5 pt-0.5">
                        <Wrench className="h-3.5 w-3.5 text-slate-500 shrink-0 mt-0.5" />
                        <span>
                          <strong className="text-slate-700">Recommended Action:</strong> {alert.recommendation}
                        </span>
                      </div>
                    )}

                    {/* Resolution Note if resolved */}
                    {isResolved && alert.resolution_note && (
                      <div className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded p-2">
                        <strong className="font-semibold">Audit Resolution Note:</strong> {alert.resolution_note}
                        {alert.resolved_at && (
                          <span className="block mt-0.5 font-mono text-[10px] text-emerald-700">
                            Resolved At: {formatLocalTime(alert.resolved_at)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Right Column: Action Buttons */}
                  <div className="flex lg:flex-col items-center gap-2 shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100">
                    <button
                      onClick={() => onSelectMachine(alert.machine_id)}
                      className="inline-flex items-center justify-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors w-full sm:w-auto"
                    >
                      <span>View Machine</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>

                    {!isResolved && (
                      <button
                        onClick={() => handleResolve(alert.id)}
                        className="inline-flex items-center justify-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors w-full sm:w-auto"
                      >
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                        <span>Resolve Alert</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
