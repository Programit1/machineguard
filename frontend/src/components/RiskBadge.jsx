import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, Info, HelpCircle } from 'lucide-react';

export default function RiskBadge({ category = 'Low', score = null, size = 'md' }) {
  const cat = (category || 'Low').toLowerCase();

  const configs = {
    low: {
      bg: 'bg-emerald-50 border-emerald-200 text-emerald-700',
      icon: ShieldCheck,
      label: 'Low Risk',
    },
    medium: {
      bg: 'bg-amber-50 border-amber-200 text-amber-700',
      icon: Info,
      label: 'Medium Risk',
    },
    high: {
      bg: 'bg-orange-50 border-orange-200 text-orange-700',
      icon: AlertTriangle,
      label: 'High Risk',
    },
    critical: {
      bg: 'bg-rose-50 border-rose-300 text-rose-700 font-semibold',
      icon: AlertOctagon,
      label: 'Critical Risk',
    },
    unavailable: {
      bg: 'bg-slate-100 border-slate-200 text-slate-600',
      icon: HelpCircle,
      label: 'Pending Data',
    },
  };

  const current = configs[cat] || configs.low;
  const Icon = current.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[11px]',
    md: 'px-2.5 py-1 text-xs font-medium',
    lg: 'px-3 py-1.5 text-xs font-semibold',
  }[size] || 'px-2.5 py-1 text-xs';

  const displayPct =
    score !== null && score !== undefined && score >= 0
      ? (score <= 1.0 ? score * 100.0 : score).toFixed(1)
      : null;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border ${current.bg} ${sizeClasses}`}>
      <Icon className={size === 'sm' ? 'w-3 h-3' : size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />
      <span>{current.label}</span>
      {displayPct !== null && (
        <span className="font-mono pl-1 border-l border-current/20 font-semibold">
          {displayPct}%
        </span>
      )}
    </span>
  );
}
