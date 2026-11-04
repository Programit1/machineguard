import React, { useState, useEffect } from 'react';
import {
  X,
  Cpu,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';

export default function MachineFormModal({
  isOpen,
  onClose,
  onSubmit,
  initialData = null,
  isEdit = false,
}) {
  const [formData, setFormData] = useState({
    machine_id: '',
    name: '',
    machine_type: 'CNC Mill',
    location: '',
    description: '',
    type_variant: 'M',
  });

  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFormData({
        machine_id: initialData.machine_id || '',
        name: initialData.name || '',
        machine_type: initialData.machine_type || 'CNC Mill',
        location: initialData.location || '',
        description: initialData.description || '',
        type_variant: initialData.type_variant || 'M',
      });
    } else {
      setFormData({
        machine_id: '',
        name: '',
        machine_type: 'CNC Mill',
        location: '',
        description: '',
        type_variant: 'M',
      });
    }
    setError('');
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const machineTypes = [
    'CNC Mill',
    'Centrifugal Pump',
    'Hydraulic Press',
    'Air Compressor',
    'Industrial Turbofan',
    'Robotic Arm',
    'Conveyor Drive',
    'CNC Lathe',
    'Injection Molder',
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.name.trim()) {
      setError('Machine Name is required');
      return;
    }
    if (!isEdit && !formData.machine_id.trim()) {
      setError('Unique Machine ID is required');
      return;
    }
    if (!formData.location.trim()) {
      setError('Plant Location / Work Cell is required');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSubmit(formData);
      onClose();
    } catch (err) {
      setError(err.message || 'Operation failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="relative w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700 border border-blue-100">
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {isEdit ? `Edit Machinery (${formData.machine_id})` : 'Register Industrial Machinery'}
              </h3>
              <p className="text-xs text-slate-500">
                {isEdit ? 'Update machine location and specifications' : 'Enroll asset into the local monitoring fleet'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-3.5">
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
              Machine ID {!isEdit && <span className="text-rose-600">*</span>}
            </label>
            <input
              type="text"
              disabled={isEdit}
              placeholder="e.g. CNC-102, PUMP-202, PRESS-302"
              value={formData.machine_id}
              onChange={(e) => setFormData({ ...formData, machine_id: e.target.value.toUpperCase() })}
              className={`w-full rounded-md border px-3 py-2 text-xs font-mono text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600 ${
                isEdit ? 'border-slate-200 bg-slate-100 opacity-70 cursor-not-allowed' : 'border-slate-300 bg-white'
              }`}
            />
            <p className="mt-1 text-[11px] text-slate-500">
              {isEdit ? 'Machine ID is unique and immutable.' : 'Routing identifier auto-discovered by telemetry generator.'}
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
              Machine Name <span className="text-rose-600">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. 5-Axis Vertical CNC Milling Center"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Machine Type
              </label>
              <select
                value={formData.machine_type}
                onChange={(e) => setFormData({ ...formData, machine_type: e.target.value })}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-600"
              >
                {machineTypes.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Quality / Duty Variant
              </label>
              <select
                value={formData.type_variant}
                onChange={(e) => setFormData({ ...formData, type_variant: e.target.value })}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-600"
              >
                <option value="L">L (Low - Standard Duty)</option>
                <option value="M">M (Medium - Heavy Duty)</option>
                <option value="H">H (High - Severe Duty)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
              Shop Floor Location / Work Cell <span className="text-rose-600">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Bay A - Precision Machining Cell 2"
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-700 mb-1">
              Description / Duty Specifications
            </label>
            <textarea
              rows={2}
              placeholder="Rated continuous torque, cooling loop specifications, duty cycle notes..."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors disabled:opacity-50 shadow-xs"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              <span>{isSubmitting ? 'Registering...' : isEdit ? 'Save Changes' : 'Register Machine'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
