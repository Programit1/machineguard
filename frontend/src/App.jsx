import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import AlertToast from './components/AlertToast';
import MachineFormModal from './components/MachineFormModal';

import Dashboard from './pages/Dashboard';
import Machines from './pages/Machines';
import MachineDetail from './pages/MachineDetail';
import Alerts from './pages/Alerts';
import MaintenanceHistory from './pages/MaintenanceHistory';
import SystemStatus from './pages/SystemStatus';
import { supabase } from './supabaseClient';

import {
  fetchDashboardSummary,
  fetchMachines,
  fetchAlerts,
  createMachine,
  updateMachine,
  deleteMachine,
  updateAlertStatus,
  checkBackendHealth,
} from './api';

export default function App() {
  // Navigation: 'dashboard' | 'machines' | 'alerts' | 'system-status' | 'machine-detail'
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedMachineId, setSelectedMachineId] = useState(null);

  // Core Data State
  const [summary, setSummary] = useState(null);
  const [machines, setMachines] = useState([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Modal states for adding/editing machinery
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [machineToEdit, setMachineToEdit] = useState(null);

  // Global High/Critical Alert Toast & Notification Deduplication
  const [activeAlertNotification, setActiveAlertNotification] = useState(null);
  const dismissedAlertIdsRef = useRef(new Set());

  // Transient Action Feedback Toast
  const [feedbackToast, setFeedbackToast] = useState(null);

  const showFeedback = (message, type = 'info') => {
    setFeedbackToast({ message, type });
    setTimeout(() => setFeedbackToast(null), 3500);
  };

  const loadData = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const [sumRes, mList, healthRes, alertsRes] = await Promise.all([
        fetchDashboardSummary(),
        fetchMachines(),
        checkBackendHealth(),
        fetchAlerts('active').catch(() => []),
      ]);

      setSummary(sumRes);
      setMachines(mList);
      setBackendOnline(healthRes.status === 'healthy');
      setLastUpdated(new Date());

      // Check for undismissed CRITICAL or HIGH severity alerts
      const highAlerts = (alertsRes || []).filter((a) => {
        const sev = (a.severity || a.risk_level || '').toUpperCase();
        return (sev === 'CRITICAL' || sev === 'HIGH') && !dismissedAlertIdsRef.current.has(a.id);
      });

      if (highAlerts.length > 0) {
        // Show the most recent critical/high alert
        const newest = highAlerts[0];
        setActiveAlertNotification(newest);
      } else {
        setActiveAlertNotification(null);
      }
    } catch (err) {
      console.warn('Backend polling warning:', err);
      setBackendOnline(false);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Live Auto-Polling: 2.0s when on overview pages (pauses during dedicated machine-detail view to free WAN bandwidth)
  useEffect(() => {
    if (activeTab === 'machine-detail') return;
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [loadData, activeTab]);

  // Supabase Realtime live subscription for instant updates on all tables
  useEffect(() => {
    if (!supabase) return;

    const channel = supabase
      .channel('machineguard-realtime-all')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sensor_readings' }, () => {
        loadData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'predictions' }, () => {
        loadData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'alerts' }, () => {
        loadData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'incidents' }, () => {
        loadData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'maintenance_logs' }, () => {
        loadData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'incident_verifications' }, () => {
        loadData();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [loadData]);

  // Navigation handlers
  const handleSelectMachine = (machineId) => {
    setSelectedMachineId(machineId);
    setActiveTab('machine-detail');
  };

  const handleBackToMachines = () => {
    setSelectedMachineId(null);
    setActiveTab('machines');
  };

  const handleDismissAlert = (alertId) => {
    dismissedAlertIdsRef.current.add(alertId);
    setActiveAlertNotification(null);
  };

  // Machine CRUD handlers
  const handleCreateMachine = async (formData) => {
    try {
      const res = await createMachine(formData);
      showFeedback(`Machine ${formData.machine_id} registered successfully.`, 'success');
      await loadData();
      return res;
    } catch (err) {
      showFeedback(err.message, 'error');
      throw err;
    }
  };

  const handleEditMachine = async (formData) => {
    try {
      await updateMachine(formData.machine_id, formData);
      showFeedback(`Machine ${formData.machine_id} updated successfully.`, 'success');
      await loadData();
    } catch (err) {
      showFeedback(err.message, 'error');
      throw err;
    }
  };

  const handleDeleteMachine = async (machineId) => {
    if (!window.confirm(`Are you sure you want to delete machine '${machineId}' and all its historical telemetry?`)) {
      return;
    }
    try {
      await deleteMachine(machineId);
      showFeedback(`Machine ${machineId} deleted.`, 'info');
      await loadData();
      if (selectedMachineId === machineId) {
        setSelectedMachineId(null);
        setActiveTab('machines');
      }
    } catch (err) {
      showFeedback(err.message, 'error');
    }
  };

  const handleUpdateAlertStatus = async (alertId, newStatus) => {
    try {
      await updateAlertStatus(alertId, newStatus);
      showFeedback(`Alert #${alertId} marked as ${newStatus}.`, 'success');
      await loadData();
    } catch (err) {
      showFeedback(err.message, 'error');
    }
  };

  const getPageTitle = () => {
    switch (activeTab) {
      case 'dashboard':
        return {
          title: 'Fleet Health & Operational Overview',
          subtitle: 'Live industrial telemetry, machine learning risk inference, and critical alarms',
        };
      case 'machines':
        return {
          title: 'Industrial Machinery Fleet',
          subtitle: 'Register, inspect, and configure monitored manufacturing assets',
        };
      case 'machine-detail':
        return {
          title: `Telemetry & Diagnostics: ${selectedMachineId || ''}`,
          subtitle: 'Multi-channel sensor feeds, machine learning models, and prescriptive maintenance actions',
        };
      case 'alerts':
        return {
          title: 'Incident Alerts & Alarm Center',
          subtitle: 'Operational rule violations, ML failure alerts, and anomaly records',
        };
      case 'maintenance-history':
        return {
          title: 'Maintenance History & Recovery Verification',
          subtitle: 'Audit trail of corrective interventions, engineer actions, and automated recovery tests',
        };
      case 'system-status':
        return {
          title: 'System Infrastructure & Service Status',
          subtitle: 'Real-time health audits, service latency, database telemetry, and model readiness',
        };
      default:
        return { title: 'MachineGuard', subtitle: 'Industrial Monitoring' };
    }
  };

  const pageInfo = getPageTitle();

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-800 font-sans">
      {/* Transient Action Feedback Toast */}
      {feedbackToast && (
        <div
          className={`fixed top-4 right-4 z-50 flex items-center gap-2 rounded-lg border px-4 py-2.5 text-xs font-semibold shadow-lg backdrop-blur-md transition-all ${
            feedbackToast.type === 'error'
              ? 'border-rose-300 bg-rose-50 text-rose-800'
              : feedbackToast.type === 'success'
              ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
              : 'border-blue-300 bg-blue-50 text-blue-800'
          }`}
        >
          <span>{feedbackToast.message}</span>
        </div>
      )}

      {/* Global High/Critical Alert Toast Notification */}
      <AlertToast
        notification={activeAlertNotification}
        onDismiss={handleDismissAlert}
        onViewMachine={(machineId) => {
          if (activeAlertNotification) {
            handleDismissAlert(activeAlertNotification.id);
          }
          handleSelectMachine(machineId);
        }}
      />

      {/* Primary Sidebar Navigation (5 Primary Tabs) */}
      <Sidebar
        activeTab={activeTab === 'machine-detail' ? 'machines' : activeTab}
        setActiveTab={(tab) => {
          setSelectedMachineId(null);
          setActiveTab(tab);
        }}
        activeAlertsCount={summary?.active_alerts_count || 0}
        activeIncidentsCount={(summary?.recent_incidents || []).filter(i => i.status !== 'RESOLVED').length}
        backendOnline={backendOnline}
      />

      {/* Main Content Viewport */}
      <div className="flex flex-1 flex-col overflow-y-auto">
        <Navbar
          title={pageInfo.title}
          subtitle={pageInfo.subtitle}
          lastUpdated={lastUpdated}
          backendOnline={backendOnline}
        />

        <main className="flex-1 pb-12">
          {activeTab === 'dashboard' && (
            <Dashboard
              summary={summary}
              machines={machines}
              backendOnline={backendOnline}
              onRetry={loadData}
              onSelectMachine={handleSelectMachine}
              onNavigateToMachines={() => setActiveTab('machines')}
              onNavigateToAlerts={() => setActiveTab('alerts')}
            />
          )}

          {activeTab === 'machines' && (
            <Machines
              machines={machines}
              onSelectMachine={handleSelectMachine}
              onOpenAddModal={() => setIsAddModalOpen(true)}
              onOpenEditModal={(m) => {
                setMachineToEdit(m);
                setIsEditModalOpen(true);
              }}
              onDeleteMachine={handleDeleteMachine}
            />
          )}

          {activeTab === 'machine-detail' && (
            <MachineDetail
              machineId={selectedMachineId}
              initialMachine={machines.find((m) => m.machine_id === selectedMachineId || m.id === selectedMachineId)}
              onBack={handleBackToMachines}
            />
          )}

          {activeTab === 'alerts' && (
            <Alerts
              onSelectMachine={handleSelectMachine}
            />
          )}

          {activeTab === 'maintenance-history' && (
            <MaintenanceHistory />
          )}

          {activeTab === 'system-status' && (
            <SystemStatus />
          )}
        </main>
      </div>

      {/* Add Machine Modal */}
      <MachineFormModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleCreateMachine}
        isEdit={false}
      />

      {/* Edit Machine Modal */}
      <MachineFormModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setMachineToEdit(null);
        }}
        onSubmit={handleEditMachine}
        initialData={machineToEdit}
        isEdit={true}
      />
    </div>
  );
}
