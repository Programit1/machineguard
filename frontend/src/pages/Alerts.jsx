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
  ShieldAlert,
  Flame,
  Activity,
  Zap,
} from 'lucide-react';
import {
  fetchAlerts,
  updateAlertStatus,
  fetchMachines,
  fetchIncidents,
  updateIncidentStatus,
  fetchVerifications,
} from '../api';
import MaintenanceModal from '../components/MaintenanceModal';

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
  const [viewMode, setViewMode] = useState('incidents'); // 'incidents' | 'alerts'
  const [alerts, setAlerts] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [verificationsMap, setVerificationsMap] = useState({});
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [incidentStatusFilter, setIncidentStatusFilter] = useState('all');
  const [alertStatusFilter, setAlertStatusFilter] = useState('all');
  const [selectedMachineFilter, setSelectedMachineFilter] = useState('all');

  // Maintenance Modal
  const [isMaintenanceModalOpen, setIsMaintenanceModalOpen] = useState(false);
  const [activeIncidentForMaintenance, setActiveIncidentForMaintenance] = useState(null);

  const loadData = async () => {
    try {
      const [alertData, incidentData, machineData] = await Promise.all([
        fetchAlerts(alertStatusFilter === 'all' ? null : alertStatusFilter),
        fetchIncidents(incidentStatusFilter === 'all' ? null : incidentStatusFilter),
        fetchMachines().catch(() => []),
      ]);

      setAlerts(alertData || []);
      setIncidents(incidentData || []);
      setMachines(machineData || []);

      // Fetch verification states for incidents
      const vMap = {};
      await Promise.all(
        (incidentData || []).map(async (inc) => {
          try {
            const vList = await fetchVerifications(inc.incident_id);
            if (vList && vList.length > 0) {
              vMap[inc.incident_id] = vList[0];
            }
          } catch {
            // ignore
          }
        })
      );
      setVerificationsMap(vMap);
    } catch (err) {
      console.error('Failed to load alerts & incidents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [incidentStatusFilter, alertStatusFilter]);

  const handleAlertResolve = async (alertId) => {
    try {
      await updateAlertStatus(alertId, 'RESOLVED');
      await loadData();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  const handleIncidentStatus = async (incidentId, newStatus) => {
    try {
      await updateIncidentStatus(incidentId, newStatus, 'Operator Sarah');
      await loadData();
    } catch (err) {
      console.error('Failed to update incident status:', err);
    }
  };

  const openMaintenanceForIncident = (inc) => {
    setActiveIncidentForMaintenance(inc);
    setIsMaintenanceModalOpen(true);
  };

  // Filter incidents
  const filteredIncidents = incidents.filter((inc) => {
    if (selectedMachineFilter !== 'all' && inc.machine_id !== selectedMachineFilter) {
      return false;
    }
    if (incidentStatusFilter !== 'all') {
      if (inc.status.toLowerCase() !== incidentStatusFilter.toLowerCase()) return false;
    }
    return true;
  });

  // Filter alerts
  const filteredAlerts = alerts.filter((a) => {
    if (selectedMachineFilter !== 'all' && a.machine_id !== selectedMachineFilter) {
      return false;
    }
    if (alertStatusFilter !== 'all') {
      const isResolved = a.status?.toUpperCase() === 'RESOLVED';
      if (alertStatusFilter === 'active' && isResolved) return false;
      if (alertStatusFilter === 'resolved' && !isResolved) return false;
    }
    return true;
  });

  const activeIncidentsCount = incidents.filter(
    (i) => !['resolved'].includes((i.status || '').toLowerCase())
  ).length;

  const activeAlertsCount = alerts.filter(
    (a) => (a.status || '').toUpperCase() === 'ACTIVE'
  ).length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Banner & Mode Toggle */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-rose-600" />
            <span>Alerts & Critical Incident Operations Center</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational rule violations, ML failure forecasts, active incident management, and automated maintenance verification.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg border border-slate-200/80">
          <button
            onClick={() => setViewMode('incidents')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5 ${
              viewMode === 'incidents'
                ? 'bg-white text-slate-900 shadow-xs border border-slate-200/60'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Flame className="h-3.5 w-3.5 text-rose-600" />
            <span>Critical Incidents</span>
            {activeIncidentsCount > 0 && (
              <span className="bg-rose-100 text-rose-700 text-[10px] font-bold px-1.5 py-0.2 rounded-full font-mono">
                {activeIncidentsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setViewMode('alerts')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5 ${
              viewMode === 'alerts'
                ? 'bg-white text-slate-900 shadow-xs border border-slate-200/60'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bell className="h-3.5 w-3.5 text-amber-600" />
            <span>Telemetry Alerts</span>
            {activeAlertsCount > 0 && (
              <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-1.5 py-0.2 rounded-full font-mono">
                {activeAlertsCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* VIEW 1: CRITICAL INCIDENTS & RECOVERY VERIFICATION */}
      {viewMode === 'incidents' && (
        <div className="space-y-4">
          {/* Incidents Filter Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5" /> Filter Status:
              </span>
              {[
                { id: 'all', label: 'All Incidents' },
                { id: 'open', label: 'Open' },
                { id: 'acknowledged', label: 'Acknowledged' },
                { id: 'under maintenance', label: 'Under Maintenance' },
                { id: 'verification pending', label: 'Verification Pending' },
                { id: 'resolved', label: 'Resolved' },
                { id: 'not fixed', label: 'Not Fixed' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setIncidentStatusFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    incidentStatusFilter === tab.id
                      ? 'bg-blue-600 text-white font-semibold'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <select
              value={selectedMachineFilter}
              onChange={(e) => setSelectedMachineFilter(e.target.value)}
              className="text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium text-slate-700"
            >
              <option value="all">All Machinery Units</option>
              {machines.map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.machine_id} - {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Incidents List */}
          <div className="space-y-3">
            {filteredIncidents.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-12 text-center space-y-2">
                <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto" />
                <div className="text-xs font-semibold text-slate-700">No Critical Incidents Found</div>
                <p className="text-[11px] text-slate-400">
                  All equipment is operating within nominal safety boundaries.
                </p>
              </div>
            ) : (
              filteredIncidents.map((inc) => {
                const verif = verificationsMap[inc.incident_id];
                const statusLower = inc.status.toLowerCase();
                const isResolved = statusLower === 'resolved';
                const isPending = statusLower === 'verification pending';
                const isNotFixed = statusLower === 'not fixed';

                // Status Badge Color
                let statusBadgeClass = 'bg-rose-100 text-rose-800 border-rose-200';
                if (statusLower === 'acknowledged') statusBadgeClass = 'bg-amber-100 text-amber-800 border-amber-200';
                else if (statusLower === 'under maintenance') statusBadgeClass = 'bg-blue-100 text-blue-800 border-blue-200';
                else if (isPending) statusBadgeClass = 'bg-indigo-100 text-indigo-800 border-indigo-200 animate-pulse';
                else if (isResolved) statusBadgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';

                // Parse triggering values
                let trigValues = {};
                try {
                  trigValues = JSON.parse(inc.triggering_values || '{}');
                } catch {
                  trigValues = {};
                }

                return (
                  <div
                    key={inc.id}
                    className={`rounded-xl border bg-white p-5 shadow-xs transition-all space-y-3.5 ${
                      isResolved
                        ? 'border-emerald-200 bg-emerald-50/20'
                        : isNotFixed
                        ? 'border-rose-300 bg-rose-50/20'
                        : 'border-slate-200'
                    }`}
                  >
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                            {inc.incident_id}
                          </span>

                          <button
                            onClick={() => onSelectMachine && onSelectMachine(inc.machine_id)}
                            className="font-mono text-xs font-bold text-blue-700 hover:underline bg-blue-50 px-2 py-0.5 rounded border border-blue-200 flex items-center gap-1"
                          >
                            <Cpu className="h-3 w-3" />
                            <span>{inc.machine_id}</span>
                          </button>

                          <span className="font-semibold text-xs text-slate-700">
                            {inc.machine_name}
                          </span>

                          <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">
                            {inc.condition_type}
                          </span>

                          <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${statusBadgeClass}`}>
                            {inc.status.toUpperCase()}
                          </span>
                        </div>

                        <h3 className="font-bold text-sm text-slate-900 pt-1">
                          {inc.title}
                        </h3>

                        <p className="text-xs text-slate-600 leading-relaxed">
                          {inc.description}
                        </p>
                      </div>

                      {/* Right metadata & Action Buttons */}
                      <div className="text-right space-y-2 shrink-0">
                        <div className="text-[11px] text-slate-400 flex items-center gap-1 justify-end">
                          <Clock className="h-3 w-3" />
                          <span>Detected: {formatLocalTime(inc.created_at)}</span>
                        </div>

                        <div className="flex flex-wrap items-center gap-1.5 justify-end">
                          {statusLower === 'open' && (
                            <button
                              onClick={() => handleIncidentStatus(inc.incident_id, 'Acknowledged')}
                              className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100"
                            >
                              Acknowledge
                            </button>
                          )}

                          {['open', 'acknowledged'].includes(statusLower) && (
                            <button
                              onClick={() => handleIncidentStatus(inc.incident_id, 'Under Maintenance')}
                              className="px-2.5 py-1 text-xs font-semibold rounded bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100"
                            >
                              Under Maintenance
                            </button>
                          )}

                          {/* Record Maintenance Action */}
                          {!isResolved && (
                            <button
                              onClick={() => openMaintenanceForIncident(inc)}
                              className="px-3 py-1 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 shadow-xs flex items-center gap-1.5"
                            >
                              <Wrench className="h-3.5 w-3.5" />
                              <span>Record Maintenance</span>
                            </button>
                          )}

                          <button
                            onClick={() => onSelectMachine && onSelectMachine(inc.machine_id)}
                            className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-800 bg-slate-50 border border-slate-200 rounded flex items-center gap-1"
                          >
                            <span>Open Machine</span>
                            <ArrowRight className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Triggering Sensor Values Snapshot */}
                    {Object.keys(trigValues).length > 0 && (
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs flex flex-wrap items-center gap-x-4 gap-y-1">
                        <span className="font-semibold text-slate-700 text-[11px]">Triggering Values:</span>
                        {Object.entries(trigValues).map(([k, v]) => (
                          <div key={k} className="text-[11px] text-slate-600 font-mono">
                            <span className="text-slate-400">{k}:</span>{' '}
                            <span className="font-bold text-slate-800">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Verification Status & Evidence Box */}
                    {verif && (
                      <div className={`rounded-lg p-3 text-xs border ${
                        verif.status === 'RESOLVED'
                          ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                          : verif.status === 'NOT FIXED'
                          ? 'bg-rose-50/70 border-rose-200 text-rose-900'
                          : 'bg-indigo-50/70 border-indigo-200 text-indigo-900'
                      }`}>
                        <div className="flex items-center justify-between font-semibold text-[11px] mb-1">
                          <span className="flex items-center gap-1.5">
                            {verif.status === 'RESOLVED' ? (
                              <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
                            ) : verif.status === 'NOT FIXED' ? (
                              <AlertOctagon className="h-3.5 w-3.5 text-rose-600" />
                            ) : (
                              <Clock className="h-3.5 w-3.5 text-indigo-600 animate-spin" />
                            )}
                            <span>Automated Recovery Verification ({verif.status}):</span>
                          </span>
                          <span className="font-mono text-[10px] text-slate-500">
                            {formatLocalTime(verif.verification_timestamp)}
                          </span>
                        </div>
                        <p className="text-[11px] font-mono leading-relaxed">
                          {verif.evidence}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* VIEW 2: REAL-TIME TELEMETRY ALERTS */}
      {viewMode === 'alerts' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5" /> Status:
              </span>
              {[
                { id: 'all', label: 'All Alerts' },
                { id: 'active', label: 'Active Alarms' },
                { id: 'resolved', label: 'Resolved History' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setAlertStatusFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    alertStatusFilter === tab.id
                      ? 'bg-blue-600 text-white font-semibold'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <select
              value={selectedMachineFilter}
              onChange={(e) => setSelectedMachineFilter(e.target.value)}
              className="text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium text-slate-700"
            >
              <option value="all">All Machinery Units</option>
              {machines.map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.machine_id} - {m.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-3">
            {filteredAlerts.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-12 text-center space-y-2">
                <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto" />
                <div className="text-xs font-semibold text-slate-700">No Telemetry Alerts</div>
                <p className="text-[11px] text-slate-400">
                  Physical sensors and ML models are reporting safe operation.
                </p>
              </div>
            ) : (
              filteredAlerts.map((a) => {
                const isCrit = (a.severity || '').toUpperCase() === 'CRITICAL';
                const isResolved = a.status?.toUpperCase() === 'RESOLVED';

                return (
                  <div
                    key={a.id}
                    className={`rounded-xl border bg-white p-4 shadow-xs transition-colors space-y-2.5 ${
                      isResolved
                        ? 'border-slate-200 opacity-75'
                        : isCrit
                        ? 'border-rose-300 bg-rose-50/20'
                        : 'border-amber-200 bg-amber-50/20'
                    }`}
                  >
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => onSelectMachine && onSelectMachine(a.machine_id)}
                            className="font-mono text-xs font-bold text-blue-700 hover:underline bg-blue-50 px-2 py-0.5 rounded border border-blue-200"
                          >
                            {a.machine_id}
                          </button>
                          <span className="font-semibold text-xs text-slate-800">
                            {a.machine_name}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              isCrit
                                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                : 'bg-amber-100 text-amber-800 border border-amber-200'
                            }`}
                          >
                            {a.severity || a.risk_level}
                          </span>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                            {a.status}
                          </span>
                        </div>

                        <div className="text-xs font-bold text-slate-900 pt-0.5">
                          {a.title || a.reason}
                        </div>

                        <p className="text-xs text-slate-600">
                          {a.reason}
                        </p>
                      </div>

                      <div className="text-right space-y-1.5 shrink-0">
                        <div className="text-[11px] text-slate-400">
                          {formatLocalTime(a.timestamp)}
                        </div>
                        {!isResolved && (
                          <button
                            onClick={() => handleAlertResolve(a.id)}
                            className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
                          >
                            Mark Resolved
                          </button>
                        )}
                      </div>
                    </div>

                    {a.resolution_note && (
                      <div className="text-[11px] font-mono text-emerald-800 bg-emerald-50 border border-emerald-200 p-2 rounded">
                        {a.resolution_note}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Maintenance Action Modal */}
      <MaintenanceModal
        isOpen={isMaintenanceModalOpen}
        onClose={() => setIsMaintenanceModalOpen(false)}
        incident={activeIncidentForMaintenance}
        onSuccess={loadData}
      />
    </div>
  );
}
