import React, { useState, useEffect } from 'react';
import {
  Wrench,
  CheckCircle,
  AlertTriangle,
  Clock,
  Cpu,
  Search,
  Filter,
  RefreshCw,
  FileText,
} from 'lucide-react';
import { fetchMaintenanceLogs, fetchMachines, fetchVerifications, fetchIncidents } from '../api';

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

export default function MaintenanceHistory({ onSelectMachine }) {
  const [logs, setLogs] = useState([]);
  const [machines, setMachines] = useState([]);
  const [incidentsMap, setIncidentsMap] = useState({});
  const [verificationsMap, setVerificationsMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedMachine, setSelectedMachine] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadHistory = async () => {
    try {
      setLoading(true);
      const [mLogs, mList, allIncidents] = await Promise.all([
        fetchMaintenanceLogs(selectedMachine === 'all' ? null : selectedMachine),
        fetchMachines().catch(() => []),
        fetchIncidents().catch(() => []),
      ]);

      setLogs(mLogs || []);
      setMachines(mList || []);

      // Build incident lookup
      const incMap = {};
      for (const inc of allIncidents || []) {
        incMap[inc.incident_id] = inc;
      }
      setIncidentsMap(incMap);

      // Fetch verifications for any incidents linked to maintenance logs
      const vMap = {};
      const uniqueIncidentIds = [...new Set((mLogs || []).map((l) => l.incident_id).filter(Boolean))];
      await Promise.all(
        uniqueIncidentIds.map(async (incId) => {
          try {
            const vList = await fetchVerifications(incId);
            if (vList && vList.length > 0) {
              vMap[incId] = vList[0];
            }
          } catch {
            // ignore
          }
        })
      );
      setVerificationsMap(vMap);
    } catch (err) {
      console.error('Failed to load maintenance history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [selectedMachine]);

  const filteredLogs = logs.filter((l) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchMachine = l.machine_id?.toLowerCase().includes(q);
      const matchAction = l.action?.toLowerCase().includes(q);
      const matchTech = l.technician?.toLowerCase().includes(q);
      const matchInc = l.incident_id?.toLowerCase().includes(q);
      if (!matchMachine && !matchAction && !matchTech && !matchInc) return false;
    }
    return true;
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Wrench className="h-5 w-5 text-blue-600" />
            <span>Equipment Maintenance History & Verification Ledger</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit-grade record of physical interventions, operator actions, and automated telemetry verification outcomes.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter actions or IDs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-48"
            />
          </div>

          <select
            value={selectedMachine}
            onChange={(e) => setSelectedMachine(e.target.value)}
            className="text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white font-medium text-slate-700"
          >
            <option value="all">All Machinery Units</option>
            {machines.map((m) => (
              <option key={m.machine_id} value={m.machine_id}>
                {m.machine_id} - {m.name}
              </option>
            ))}
          </select>

          <button
            onClick={loadHistory}
            className="p-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 text-slate-600 transition-colors"
            title="Refresh history"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Ledger Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        {loading && logs.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400 animate-pulse">
            Loading verified maintenance history from database...
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <FileText className="h-8 w-8 text-slate-300 mx-auto" />
            <div className="text-xs font-semibold text-slate-700">No maintenance records found</div>
            <p className="text-[11px] text-slate-400">
              When maintenance interventions are performed on critical incidents, records and automated recovery evidence will appear here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredLogs.map((log) => {
              const inc = log.incident_id ? incidentsMap[log.incident_id] : null;
              const verif = log.incident_id ? verificationsMap[log.incident_id] : null;
              const isResolved = verif?.status === 'RESOLVED' || inc?.status === 'Resolved';
              const isFailed = verif?.status === 'NOT FIXED' || inc?.status === 'Not Fixed';
              const isPending = !isResolved && !isFailed;

              return (
                <div key={log.id} className="p-4 hover:bg-slate-50/60 transition-colors space-y-3">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => onSelectMachine && onSelectMachine(log.machine_id)}
                          className="font-mono text-xs font-bold text-blue-700 hover:underline bg-blue-50 px-2 py-0.5 rounded border border-blue-200"
                        >
                          {log.machine_id}
                        </button>

                        {log.incident_id && (
                          <span className="font-mono text-[11px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                            {log.incident_id}
                          </span>
                        )}

                        {/* Verification Outcome Badge */}
                        {isResolved ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                            <CheckCircle className="h-3 w-3" />
                            <span>VERIFIED RECOVERED</span>
                          </span>
                        ) : isFailed ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                            <AlertTriangle className="h-3 w-3" />
                            <span>NOT FIXED / RE-TRIGGERED</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                            <Clock className="h-3 w-3 animate-spin" />
                            <span>VERIFICATION PENDING</span>
                          </span>
                        )}
                      </div>

                      <div className="text-xs font-semibold text-slate-900 mt-1">
                        {log.action}
                      </div>

                      {log.notes && (
                        <p className="text-[11px] text-slate-600 italic">
                          "{log.notes}"
                        </p>
                      )}
                    </div>

                    <div className="text-right text-[11px] text-slate-500 space-y-0.5 shrink-0">
                      <div className="font-medium text-slate-700">
                        Technician: <span className="font-semibold text-slate-900">{log.technician || 'System Operator'}</span>
                      </div>
                      <div className="flex items-center gap-1 justify-end text-slate-400">
                        <Clock className="h-3 w-3" />
                        <span>Completed: {formatLocalTime(log.completed_at || log.timestamp)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Incident Problem & Verification Evidence Box */}
                  {(inc || verif) && (
                    <div className="rounded-lg bg-slate-50 border border-slate-200/90 p-3 text-xs space-y-1.5">
                      {inc && (
                        <div className="flex items-baseline gap-2">
                          <span className="font-semibold text-slate-700 text-[11px]">Problem Detected:</span>
                          <span className="text-[11px] text-slate-600">
                            <strong className="text-slate-800 font-mono">[{inc.condition_type}]</strong> {inc.description || inc.title}
                          </span>
                        </div>
                      )}

                      {verif && (
                        <div className="flex items-baseline gap-2 pt-1 border-t border-slate-200/60">
                          <span className="font-semibold text-slate-700 text-[11px]">Verification Evidence:</span>
                          <span className="text-[11px] text-slate-700 font-mono leading-relaxed">
                            {verif.evidence}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
