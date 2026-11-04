import React, { useState } from 'react';
import {
  Cpu,
  Search,
  Plus,
  Trash2,
  Edit,
  ArrowRight,
  MapPin,
  Clock,
  AlertTriangle,
  RotateCcw,
  Zap,
} from 'lucide-react';
import RiskBadge from '../components/RiskBadge';
import StatusBadge from '../components/StatusBadge';

export default function Machines({
  machines = [],
  onSelectMachine,
  onOpenAddModal,
  onOpenEditModal,
  onDeleteMachine,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Distinct machine types
  const machineTypes = ['ALL', ...new Set(machines.map((m) => m.machine_type))];

  // Filtering
  const filteredMachines = machines.filter((m) => {
    const matchesSearch =
      m.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.machine_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.location.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesType = typeFilter === 'ALL' || m.machine_type === typeFilter;

    let matchesStatus = true;
    if (statusFilter === 'ONLINE') matchesStatus = m.is_online;
    if (statusFilter === 'OFFLINE') matchesStatus = !m.is_online;
    if (statusFilter === 'HIGH_RISK') {
      const cat = m.latest_prediction?.risk_category;
      matchesStatus = cat === 'High' || cat === 'Critical';
    }

    return matchesSearch && matchesType && matchesStatus;
  });

  return (
    <div className="space-y-6 p-6">
      {/* Top Controls: Search, Filters, Add Button */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex flex-1 flex-wrap items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by ID, machine name, or cell location..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-4 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {machineTypes.map((t) => (
              <option key={t} value={t}>
                {t === 'ALL' ? 'All Machine Types' : t}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="ONLINE">Online Streaming</option>
            <option value="OFFLINE">Offline</option>
            <option value="HIGH_RISK">High / Critical Risk</option>
          </select>
        </div>

        <button
          onClick={onOpenAddModal}
          className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-all shrink-0"
        >
          <Plus className="h-4 w-4" />
          <span>Register New Machine</span>
        </button>
      </div>

      {/* Equipment Fleet Grid */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        {filteredMachines.map((m) => {
          const reading = m.latest_reading;
          const pred = m.latest_prediction;
          const riskCat = pred ? pred.risk_category : 'Low';
          const prob = pred ? pred.failure_probability : 0.0;
          const hasAI4I = reading && reading.rotational_speed !== null && reading.rotational_speed !== undefined;

          return (
            <div
              key={m.machine_id}
              className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-slate-300 hover:shadow-md transition-all"
            >
              <div>
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-300">
                        {m.machine_id}
                      </span>
                      <StatusBadge
                        isOnline={m.is_online}
                        health={!m.is_online ? 'Offline' : (riskCat === 'Critical' ? 'Critical' : (riskCat === 'High' || riskCat === 'Medium' ? 'Warning' : m.health_status))}
                      />
                      {m.type_variant && (
                        <span className="font-mono text-[10px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                          Variant {m.type_variant}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-2 text-base font-bold text-slate-800 leading-tight">{m.name}</h3>
                    <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                      <MapPin className="h-3 w-3 shrink-0 text-slate-400" />
                      <span>{m.location}</span>
                    </p>
                  </div>

                  <RiskBadge category={riskCat} score={prob} size="sm" />
                </div>

                {/* Machine Type & Description */}
                <div className="mt-3 text-xs text-slate-600 line-clamp-2">
                  <span className="font-semibold text-slate-700">{m.machine_type}</span>
                  {m.description && <span> — {m.description}</span>}
                </div>

                {/* Latest Sensor Readings Capsule */}
                {reading ? (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                    <div className="flex items-center justify-between text-[11px] text-slate-500 mb-2">
                      <span className="font-semibold uppercase tracking-wider text-[10px]">Latest Ingestion</span>
                      <span className="font-mono">
                        {new Date(reading.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </div>

                    {hasAI4I ? (
                      /* AI4I Machine Telemetry */
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="flex justify-between border-b border-slate-200 pb-1">
                          <span className="text-slate-500">Speed</span>
                          <span className="font-mono font-semibold text-slate-800">
                            {Math.round(reading.rotational_speed)} rpm
                          </span>
                        </div>
                        <div className="flex justify-between border-b border-slate-200 pb-1">
                          <span className="text-slate-500">Torque</span>
                          <span className={`font-mono font-semibold ${reading.torque > 55 ? 'text-amber-700' : 'text-slate-800'}`}>
                            {reading.torque.toFixed(1)} Nm
                          </span>
                        </div>
                        <div className="flex justify-between pt-1">
                          <span className="text-slate-500">Tool Wear</span>
                          <span className={`font-mono font-semibold ${reading.tool_wear > 200 ? 'text-rose-700' : 'text-slate-800'}`}>
                            {Math.round(reading.tool_wear)} min
                          </span>
                        </div>
                        <div className="flex justify-between pt-1">
                          <span className="text-slate-500">Process Temp</span>
                          <span className="font-mono font-semibold text-slate-800">
                            {(reading.process_temperature - 273.15).toFixed(1)} °C
                          </span>
                        </div>
                      </div>
                    ) : (
                      /* Plant Condition Telemetry */
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="flex justify-between border-b border-slate-200 pb-1">
                          <span className="text-slate-500">Temperature</span>
                          <span className={`font-mono font-semibold ${reading.temperature > 75 ? 'text-rose-700' : 'text-slate-800'}`}>
                            {reading.temperature.toFixed(1)} °C
                          </span>
                        </div>
                        <div className="flex justify-between border-b border-slate-200 pb-1">
                          <span className="text-slate-500">Vibration</span>
                          <span className={`font-mono font-semibold ${reading.vibration > 4.5 ? 'text-rose-700' : 'text-slate-800'}`}>
                            {reading.vibration.toFixed(2)} mm/s
                          </span>
                        </div>
                        <div className="flex justify-between pt-1">
                          <span className="text-slate-500">Pressure</span>
                          <span className={`font-mono font-semibold ${reading.pressure < 2.5 || reading.pressure > 7.0 ? 'text-amber-700' : 'text-slate-800'}`}>
                            {reading.pressure.toFixed(2)} bar
                          </span>
                        </div>
                        <div className="flex justify-between pt-1">
                          <span className="text-slate-500">Power</span>
                          <span className="font-mono font-semibold text-slate-800">
                            {reading.power_consumption.toFixed(1)} kW
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-3 text-center text-xs text-slate-400">
                    No sensor readings received yet.
                  </div>
                )}

                {/* Active Alerts warning indicator */}
                {m.active_alerts_count > 0 && (
                  <div className="mt-3 flex items-center gap-2 rounded-lg bg-rose-50 border border-rose-200 px-2.5 py-1.5 text-xs text-rose-700">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-600" />
                    <span>{m.active_alerts_count} active failure alert(s)</span>
                  </div>
                )}
              </div>

              {/* Bottom Actions */}
              <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3 text-xs">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => onOpenEditModal(m)}
                    className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-all"
                    title="Edit machine details"
                  >
                    <Edit className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => onDeleteMachine(m.machine_id)}
                    className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                    title="Delete machine"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <button
                  onClick={() => onSelectMachine(m.machine_id)}
                  className="flex items-center gap-1.5 rounded-lg bg-blue-50 border border-blue-200 px-3 py-1.5 font-semibold text-blue-700 hover:bg-blue-100 transition-all"
                >
                  <span>Open Monitoring</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {filteredMachines.length === 0 && (
        <div className="flex flex-col items-center justify-center p-12 text-center text-slate-500 border border-dashed border-slate-200 rounded-2xl bg-white shadow-sm">
          <Cpu className="h-10 w-10 text-slate-400 mb-3" />
          <h4 className="text-base font-bold text-slate-800">No Machinery Found</h4>
          <p className="text-xs text-slate-500 max-w-sm mt-1">
            No equipment matches your search or filter parameters. Register a new machine or clear active filters.
          </p>
        </div>
      )}
    </div>
  );
}
