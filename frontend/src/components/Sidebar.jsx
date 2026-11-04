import React from 'react';
import {
  LayoutDashboard,
  Cpu,
  Bell,
  Activity,
  Shield,
  Radio,
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, activeAlertsCount = 0, backendOnline = true }) {
  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
    },
    {
      id: 'machines',
      label: 'Machines',
      icon: Cpu,
    },
    {
      id: 'alerts',
      label: 'Alerts',
      icon: Bell,
      badge: activeAlertsCount > 0 ? activeAlertsCount : null,
    },
    {
      id: 'system-status',
      label: 'System Status',
      icon: Activity,
    },
  ];

  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="p-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700 border border-blue-200 shadow-xs">
              <Shield className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <div className="font-bold text-base tracking-tight text-slate-900">
                MachineGuard
              </div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Industrial Monitoring
              </p>
            </div>
          </div>
        </div>

        {/* Primary Navigation */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50/80 text-blue-800 font-semibold border border-blue-200/90 shadow-xs'
                    : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`h-4 w-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                  <span className={isActive ? 'font-semibold text-blue-900' : ''}>{item.label}</span>
                </div>

                {item.badge !== null && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold font-mono ${
                      isActive
                        ? 'bg-rose-100 text-rose-800 border border-rose-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* System Status Footer */}
      <div className="p-3 border-t border-slate-200 bg-slate-50/80">
        <div className="flex items-center justify-between px-2 py-1 text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span className="font-medium text-slate-700">
              {backendOnline ? 'System Online' : 'System Offline'}
            </span>
          </div>
          <span className="font-mono text-[10px] text-slate-500">1.0s Feed</span>
        </div>
      </div>
    </aside>
  );
}
