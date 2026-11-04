import React from 'react';
import { AlertCircle, CloudCheck, Radio } from 'lucide-react';

export default function Navbar({
  title,
  subtitle,
  lastUpdated,
  backendOnline = true,
  cloudOnline = true,
}) {
  const isFullyOnline = cloudOnline && backendOnline;
  const isCloudOnly = cloudOnline && !backendOnline;
  const isCompletelyOffline = !cloudOnline && !backendOnline;

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-6 backdrop-blur-md shadow-xs">
      <div>
        <h1 className="text-base font-bold text-slate-900 tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {isCompletelyOffline ? (
          <div className="flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 shadow-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
            </span>
            <AlertCircle className="h-3.5 w-3.5 text-rose-600" />
            <span>Connection Offline — Retrying...</span>
          </div>
        ) : isCloudOnly ? (
          <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50/70 px-3 py-1 text-xs text-emerald-800 shadow-2xs">
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
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 shadow-2xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-semibold text-emerald-800 text-[11px]">Cloud & Local ML Synced</span>
            <span className="text-slate-400 text-[10px]">•</span>
            <span className="font-mono text-[10px] text-slate-700">
              {lastUpdated
                ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : 'Live (1s)'}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
