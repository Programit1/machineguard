import React from 'react';

export default function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend = null,
  colorScheme = 'blue',
  onClick = null,
}) {
  const colorMap = {
    blue: {
      border: 'border-slate-200 hover:border-blue-400',
      iconBg: 'bg-blue-50 text-blue-700 border border-blue-100',
    },
    emerald: {
      border: 'border-slate-200 hover:border-emerald-400',
      iconBg: 'bg-emerald-50 text-emerald-700 border border-emerald-100',
    },
    amber: {
      border: 'border-slate-200 hover:border-amber-400',
      iconBg: 'bg-amber-50 text-amber-700 border border-amber-100',
    },
    rose: {
      border: 'border-slate-200 hover:border-rose-400',
      iconBg: 'bg-rose-50 text-rose-700 border border-rose-100',
    },
    purple: {
      border: 'border-slate-200 hover:border-purple-400',
      iconBg: 'bg-purple-50 text-purple-700 border border-purple-100',
    },
    slate: {
      border: 'border-slate-200 hover:border-slate-400',
      iconBg: 'bg-slate-100 text-slate-700 border border-slate-200',
    },
  };

  const scheme = colorMap[colorScheme] || colorMap.slate;

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border bg-white p-4 shadow-xs transition-all duration-150 ${
        scheme.border
      } ${onClick ? 'cursor-pointer hover:shadow-sm' : ''}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{title}</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono tracking-tight text-slate-900">{value}</span>
            {trend && <span className="text-xs font-medium text-slate-500">{trend}</span>}
          </div>
          {subtitle && <p className="mt-1 text-[11px] text-slate-500">{subtitle}</p>}
        </div>

        {Icon && (
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${scheme.iconBg}`}>
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </div>
  );
}
