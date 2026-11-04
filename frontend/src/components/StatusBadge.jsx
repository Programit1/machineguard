import React from 'react';

export default function StatusBadge({ status = 'ONLINE', isOnline = true, health = null }) {
  // If health is provided (e.g. Critical, Warning), show health status color
  let label = isOnline ? 'Running' : 'Offline';
  let dotColor = isOnline ? 'bg-emerald-500' : 'bg-slate-400';
  let textColor = isOnline ? 'text-emerald-700' : 'text-slate-500';
  let bgColor = isOnline ? 'bg-emerald-50/60 border-emerald-200' : 'bg-slate-50 border-slate-200';

  if (health === 'Critical' || health === 'Critical Risk') {
    label = 'Critical';
    dotColor = 'bg-rose-500';
    textColor = 'text-rose-700';
    bgColor = 'bg-rose-50 border-rose-200';
  } else if (health === 'Warning' || health === 'Attention Required' || health === 'Warning (Model Disagreement)') {
    label = 'Warning';
    dotColor = 'bg-amber-500';
    textColor = 'text-amber-800';
    bgColor = 'bg-amber-50 border-amber-200';
  } else if (!isOnline) {
    label = 'Offline';
    dotColor = 'bg-slate-400';
    textColor = 'text-slate-500';
    bgColor = 'bg-slate-100 border-slate-200';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] font-medium ${bgColor}`}>
      <span className="relative flex h-2 w-2">
        {isOnline && dotColor === 'bg-emerald-500' && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`}></span>
      </span>
      <span className={`font-semibold text-[10px] tracking-wide uppercase ${textColor}`}>
        {label}
      </span>
    </span>
  );
}
