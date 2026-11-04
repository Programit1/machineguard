import React from 'react';
import { CloudCheck, Radio } from 'lucide-react';

export default function Navbar({
  title,
  subtitle,
  lastUpdated,
  backendOnline = true,
  cloudOnline = true,
  onNavigateToStatus,
}) {
  const isFullyOnline = cloudOnline && backendOnline;
  const isCloudOnly = cloudOnline && !backendOnline;

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-6 backdrop-blur-md shadow-xs">
      <div>
        <h1 className="text-base font-bold text-slate-900 tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {isFullyOnline ? (
          <button
            onClick={onNavigateToStatus}
            className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 hover:bg-slate-100 px-2.5 py-1 text-xs text-slate-600 shadow-2xs transition-colors cursor-pointer"
            title="Click to view detailed system infrastructure & ML models status"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-semibold text-emerald-800 text-[11px]">Cloud & Local ML Synced</span>
            <span className="text-slate-400 text-[10px]">•</span>
            <span className="font-mono text-[10px] text-slate-700">
              {lastUpdated
                ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : 'Live'}
            </span>
          </button>
        ) : isCloudOnly ? (
          <button
            onClick={onNavigateToStatus}
            className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50/70 hover:bg-emerald-100/70 px-3 py-1 text-xs text-emerald-800 shadow-2xs transition-colors cursor-pointer"
            title="Click to view detailed system infrastructure & ML models status"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-semibold text-[11px]">Supabase Cloud Live</span>
            <span className="text-slate-400 text-[10px]">•</span>
            <span className="font-mono text-[10px] text-slate-600">
              {lastUpdated
                ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : 'Synced'}
            </span>
          </button>
        ) : (
          <button
            onClick={onNavigateToStatus}
            className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 hover:bg-slate-100 px-3 py-1 text-xs text-slate-600 shadow-2xs transition-colors cursor-pointer"
            title="Click to view detailed system infrastructure & ML models status"
          >
            <span className="h-2 w-2 rounded-full bg-amber-500"></span>
            <span className="font-medium text-[11px] text-slate-700">Connecting to Cloud...</span>
          </button>
        )}
      </div>
    </header>
  );
}
