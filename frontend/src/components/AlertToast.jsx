import React from 'react';
import { AlertOctagon, AlertTriangle, X, ArrowRight } from 'lucide-react';

export default function AlertToast({ notification, onDismiss, onViewMachine }) {
  if (!notification) return null;

  const isCritical = notification.severity === 'CRITICAL' || notification.risk_level === 'Critical';
  const Icon = isCritical ? AlertOctagon : AlertTriangle;
  const borderColor = isCritical ? 'border-rose-400' : 'border-orange-400';
  const bgColor = isCritical ? 'bg-white' : 'bg-white';
  const iconBg = isCritical ? 'bg-rose-100 text-rose-700' : 'bg-orange-100 text-orange-700';

  return (
    <div
      role="alert"
      className={`fixed bottom-5 right-5 z-50 max-w-md w-full rounded-lg border-2 ${borderColor} ${bgColor} p-4 shadow-xl transition-all duration-300 animate-slide-up`}
    >
      <div className="flex items-start gap-3">
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider font-mono ${
                isCritical ? 'bg-rose-100 text-rose-800' : 'bg-orange-100 text-orange-800'
              }`}
            >
              {notification.severity || 'HIGH'} ALERT
            </span>
            <button
              onClick={() => onDismiss(notification.id)}
              className="text-slate-400 hover:text-slate-600 rounded p-0.5 transition-colors"
              title="Dismiss notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <h4 className="mt-1 text-sm font-bold text-slate-900 leading-snug">
            {notification.title || `${notification.machine_name} Alert`}
          </h4>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Machine: <span className="font-semibold text-slate-800">{notification.machine_name} ({notification.machine_id})</span>
          </p>
          <p className="mt-1 text-xs text-slate-600 line-clamp-2 leading-relaxed">
            {notification.reason}
          </p>

          <div className="mt-3 flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              onClick={() => onDismiss(notification.id)}
              className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-slate-800 rounded transition-colors"
            >
              Dismiss
            </button>
            <button
              onClick={() => onViewMachine(notification.machine_id)}
              className="inline-flex items-center gap-1.5 rounded bg-slate-900 px-3 py-1 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
            >
              <span>View Machine</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
