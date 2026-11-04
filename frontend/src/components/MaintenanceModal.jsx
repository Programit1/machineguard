import React, { useState } from 'react';
import { Wrench, X, CheckCircle, AlertTriangle } from 'lucide-react';
import { recordMaintenance } from '../api';

export default function MaintenanceModal({ isOpen, onClose, incident, machineId, onSuccess }) {
  const [action, setAction] = useState('');
  const [technician, setTechnician] = useState('Operator Sarah');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const targetMachineId = machineId || (incident && incident.machine_id) || 'CNC-001';
  const targetIncidentId = incident ? incident.incident_id : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!action.trim()) {
      setError('Please provide a description of the maintenance action performed.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await recordMaintenance({
        machine_id: targetMachineId,
        incident_id: targetIncidentId,
        action: action.trim(),
        technician: technician.trim() || 'System Operator',
        notes: notes.trim(),
      });
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to submit maintenance log');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
              <Wrench className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900">Record Maintenance Action</h3>
              <p className="text-[11px] text-slate-500">
                Machine: <span className="font-mono font-semibold text-slate-700">{targetMachineId}</span>
                {targetIncidentId && (
                  <span> &bull; Incident: <span className="font-mono text-blue-700 font-semibold">{targetIncidentId}</span></span>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {incident && (
            <div className="p-3 rounded-lg bg-amber-50/80 border border-amber-200/80 text-xs text-amber-900 space-y-1">
              <div className="font-semibold text-amber-950 flex items-center gap-1.5">
                <span>Problem Detected:</span>
                <span className="font-mono bg-amber-200/70 px-1.5 py-0.2 rounded text-[10px]">
                  {incident.condition_type}
                </span>
              </div>
              <p className="text-amber-800 text-[11px] leading-relaxed">
                {incident.description || incident.title}
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Maintenance Action Performed *
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Replaced worn cutter insert and reset spindle torque"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Technician / Operator Label
              </label>
              <input
                type="text"
                value={technician}
                onChange={(e) => setTechnician(e.target.value)}
                placeholder="Operator Sarah"
                className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Post-Maintenance State
              </label>
              <div className="w-full text-xs px-3 py-2 bg-indigo-50 border border-indigo-200 rounded-lg text-indigo-800 font-semibold flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-ping" />
                <span>Verification Pending</span>
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Maintenance Notes (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Details on spare part numbers, torque recalibration, or lubrication applied..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-600">
            <span className="font-semibold text-slate-800">Automated Recovery Verification:</span> Upon submission, the system will collect fresh telemetry and require <span className="font-semibold text-slate-800">3 consecutive nominal cycles</span> before declaring the incident verified and resolved.
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-xs disabled:opacity-50 flex items-center gap-1.5"
            >
              {isSubmitting ? 'Recording...' : 'Submit Maintenance & Initiate Verification'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
