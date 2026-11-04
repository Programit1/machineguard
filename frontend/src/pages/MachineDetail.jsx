import React, { useState, useEffect, useCallback, useRef, Component } from 'react';
import {
  ArrowLeft,
  Clock,
  Cpu,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  TrendingUp,
  Activity,
  Layers,
  Thermometer,
  RotateCw,
  Gauge,
  Shield,
  Sliders,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

import RiskBadge from '../components/RiskBadge';
import StatusBadge from '../components/StatusBadge';
import {
  fetchMachineDetail,
  fetchMachineTelemetry,
  fetchMachinePredictions,
  fetchAlerts,
  updateAlertStatus,
} from '../api';

function formatLocalTime(ts) {
  if (!ts) return 'Awaiting telemetry';
  try {
    const str = String(ts);
    const iso = !str.endsWith('Z') && !str.includes('+') ? `${str}Z` : str;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    return String(ts);
  }
}

function formatChartTime(ts) {
  if (!ts) return '';
  try {
    const str = String(ts);
    const iso = !str.endsWith('Z') && !str.includes('+') ? `${str}Z` : str;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    return '';
  }
}

const DEFAULT_FLEET_METADATA = {
  'CNC-001': { name: 'Simulated CNC Milling Machine', machine_type: 'CNC Mill', type_variant: 'M', location: 'Bay 1 - Precision Milling Cell', description: '3-axis precision milling machine instrumented with AI4I physical telemetry sensors.' },
  'CNC-101': { name: 'Vertical CNC Milling Center 1', machine_type: 'CNC Mill', type_variant: 'M', location: 'Bay A - Precision Machining Cell', description: '5-axis vertical machining center for titanium aerostructure components.' },
  'PUMP-201': { name: 'High-Pressure Centrifugal Pump A', machine_type: 'Centrifugal Pump', type_variant: 'L', location: 'Utility Plant - Cooling Loop 2', description: 'Variable-speed cooling fluid circulation pump rated for 350 GPM.' },
  'PRESS-301': { name: 'Hydraulic Stamping Press 300T', machine_type: 'Hydraulic Press', type_variant: 'H', location: 'Stamping Line 3', description: 'Heavy duty 300-ton hydraulic sheet metal forming press.' },
  'COMP-401': { name: 'Rotary Screw Air Compressor B', machine_type: 'Air Compressor', type_variant: 'M', location: 'Compressor House 1', description: 'Primary pneumatic supply rotary compressor operating at 7.5 bar nominal.' },
  'ROBOT-501': { name: '6-Axis Articulated Welding Robot', machine_type: 'Robotic Arm', type_variant: 'L', location: 'Assembly Cell 4', description: 'High-precision robotic welding arm equipped with load torque feedback.' }
};

function getFallbackMachine(mid) {
  if (!mid) return null;
  const meta = DEFAULT_FLEET_METADATA[mid.toUpperCase()] || {
    name: `Industrial Equipment ${mid}`,
    machine_type: 'Industrial Machine',
    type_variant: 'M',
    location: 'Production Floor'
  };
  return {
    id: mid,
    machine_id: mid,
    name: meta.name,
    machine_type: meta.machine_type,
    location: meta.location,
    description: meta.description || '',
    type_variant: meta.type_variant,
    status: 'ONLINE',
    is_online: true,
    latest_reading: null,
    latest_prediction: null,
    health_status: 'Healthy',
    active_alerts_count: 0
  };
}

class MachineErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('MachineDetail rendering error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-xl mx-auto my-12">
          <div className="rounded-xl border border-rose-200 bg-white p-6 shadow-sm text-center space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Machine Telemetry Display Notice</h3>
              <p className="mt-1 text-xs text-slate-600">
                A rendering issue occurred while parsing machine diagnostics ({this.props.machineId || 'Unknown'}).
              </p>
              <p className="mt-2 text-[11px] font-mono bg-slate-50 p-2 rounded border border-slate-200 text-rose-700 text-left overflow-x-auto">
                {this.state.error?.message || 'Unknown error'}
              </p>
            </div>
            <div className="flex justify-center gap-3 pt-2">
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
              >
                Retry
              </button>
              <button
                onClick={this.props.onBack}
                className="rounded-md bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
              >
                Return to Fleet
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function MachineDetailContent({ machineId, initialMachine, onBack }) {
  const [machine, setMachine] = useState(() => initialMachine || getFallbackMachine(machineId));
  const [telemetry, setTelemetry] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeChartTab, setActiveChartTab] = useState('mechanical'); // mechanical, thermal, condition
  const isFetchingRef = useRef(false);

  // Sync initialMachine or fallback when machineId changes
  useEffect(() => {
    if (initialMachine) {
      setMachine(initialMachine);
    } else if (machineId) {
      setMachine((prev) => (prev?.machine_id === machineId ? prev : getFallbackMachine(machineId)));
    }
  }, [initialMachine, machineId]);

  const loadData = useCallback(async () => {
    if (!machineId || isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      const [mRes, tRes, pRes, aRes] = await Promise.allSettled([
        fetchMachineDetail(machineId),
        fetchMachineTelemetry(machineId, 50),
        fetchMachinePredictions(machineId, 30),
        fetchAlerts(null, machineId),
      ]);

      if (mRes.status === 'fulfilled' && mRes.value) {
        setMachine((prev) => ({
          ...prev,
          ...mRes.value,
          latest_reading: mRes.value.latest_reading || prev?.latest_reading || null,
          latest_prediction: mRes.value.latest_prediction || prev?.latest_prediction || null,
        }));
      }

      if (tRes.status === 'fulfilled' && Array.isArray(tRes.value)) {
        setTelemetry(tRes.value);
        if (tRes.value.length > 0) {
          const newestTelemetry = tRes.value[tRes.value.length - 1];
          setMachine((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              latest_reading: prev.latest_reading || newestTelemetry,
              last_telemetry_time: prev.last_telemetry_time || newestTelemetry.timestamp,
            };
          });
        }
      }

      if (pRes.status === 'fulfilled' && Array.isArray(pRes.value)) {
        setPredictions(pRes.value);
        if (pRes.value.length > 0) {
          const newestPred = pRes.value[0];
          setMachine((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              latest_prediction: prev.latest_prediction || newestPred,
            };
          });
        }
      }

      if (aRes.status === 'fulfilled' && Array.isArray(aRes.value)) {
        setAlerts(aRes.value);
      }
    } catch (err) {
      console.error('Failed to load machine detail:', err);
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, [machineId]);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // 2-second live telemetry refresh with in-flight guard
  useEffect(() => {
    const timer = setInterval(loadData, 2000);
    return () => clearInterval(timer);
  }, [loadData]);

  const handleResolveAlert = async (alertId) => {
    try {
      await updateAlertStatus(alertId, 'RESOLVED');
      await loadData();
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  if (loading && !machine) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-500">
        <Activity className="h-6 w-6 animate-spin text-slate-700" />
        <span className="text-xs font-medium">Connecting to machine telemetry channel ({machineId})...</span>
      </div>
    );
  }

  if (!machine) {
    return (
      <div className="p-8 text-center text-slate-500 max-w-lg mx-auto">
        <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-xs">
          <p className="font-semibold text-slate-800">Machine '{machineId}' not found.</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button
              onClick={() => {
                setLoading(true);
                loadData();
              }}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
            >
              Retry Connection
            </button>
            <button
              onClick={onBack}
              className="rounded-md bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition-colors"
            >
              Return to Fleet
            </button>
          </div>
        </div>
      </div>
    );
  }

  const latestReading = machine?.latest_reading || (telemetry.length > 0 ? telemetry[telemetry.length - 1] : null);
  const latestPred = machine?.latest_prediction || (predictions.length > 0 ? predictions[0] : null);

  // Probability formatting: backend decimal in [0.0, 1.0] -> % for display
  const rawProb =
    latestPred?.failure_probability !== null && latestPred?.failure_probability !== undefined
      ? latestPred.failure_probability
      : null;
  const failurePct =
    typeof rawProb === 'number' && !isNaN(rawProb)
      ? rawProb <= 1.0
        ? rawProb * 100.0
        : rawProb
      : 0.0;
  const riskCat = latestPred?.risk_category || 'Low';

  // Anomaly status
  const isAnomaly = Boolean(latestPred?.anomaly || latestPred?.anomaly_detected);
  const anomScore = latestPred?.anomaly_score;
  const anomLabel = latestPred?.anomaly_label || (isAnomaly ? 'Anomaly' : 'Normal');

  // RUL status
  const rulCycles = latestPred?.estimated_remaining_cuts;
  const rulUnit = latestPred?.rul_unit || 'cycles';
  const rulAvailable = Boolean(latestPred?.rul_available);

  // Health status
  const healthStatus = latestPred?.machine_health_status || machine?.health_status || 'Healthy';
  const hasDisagreement = Boolean(latestPred?.model_disagreement);
  const disagreementReason = latestPred?.disagreement_reason;

  // Active alerts for this machine
  const activeAlerts = alerts.filter((a) => a && a.status && a.status.toUpperCase() === 'ACTIVE');

  // Format telemetry chart records safely
  const chartData = telemetry.map((t) => {
    const airK = typeof t?.air_temperature === 'number' ? t.air_temperature : null;
    const procK = typeof t?.process_temperature === 'number' ? t.process_temperature : null;
    const directTemp = typeof t?.temperature === 'number' ? t.temperature : null;

    const airC = airK !== null ? parseFloat((airK - 273.15).toFixed(1)) : null;
    const procC = directTemp !== null ? directTemp : procK !== null ? parseFloat((procK - 273.15).toFixed(1)) : null;

    return {
      time: formatChartTime(t?.timestamp),
      speed: typeof t?.rotational_speed === 'number' ? t.rotational_speed : null,
      torque: typeof t?.torque === 'number' ? t.torque : null,
      wear: typeof t?.tool_wear === 'number' ? t.tool_wear : null,
      air_temp_c: airC,
      proc_temp_c: procC,
      vibration: typeof t?.vibration === 'number' ? t.vibration : null,
      pressure: typeof t?.pressure === 'number' ? t.pressure : null,
    };
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* 1. Header: Back Navigation & Primary Machine Details */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors shadow-xs"
            title="Return to fleet view"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold bg-slate-900 text-white px-2 py-0.5 rounded">
                {machine.machine_id}
              </span>
              <StatusBadge isOnline={Boolean(machine.is_online)} health={healthStatus} />
              <span className="text-xs font-medium text-slate-500">
                {machine.type_variant ? `Variant ${machine.type_variant}` : 'Standard Variant'}
              </span>
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">{machine.name}</h1>
            <p className="text-xs text-slate-500 font-medium">
              {machine.machine_type} • Location: <span className="text-slate-700">{machine.location}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
              Last Telemetry Packet
            </div>
            <div className="flex items-center justify-end gap-1 font-mono text-xs font-semibold text-slate-900 mt-0.5">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span>{formatLocalTime(machine.last_telemetry_time)}</span>
            </div>
          </div>

          <div className="pl-4 border-l border-slate-200">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
              Overall Health
            </div>
            <div className="mt-0.5">
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-bold ${
                  healthStatus === 'Critical Risk' || healthStatus === 'Critical'
                    ? 'bg-rose-100 text-rose-800 border border-rose-200'
                    : healthStatus === 'Attention Required' ||
                      healthStatus === 'Warning' ||
                      healthStatus.includes('Warning')
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                }`}
              >
                {healthStatus}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Model Disagreement Diagnostic Alert Banner if active */}
      {hasDisagreement && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-amber-900">Model Consensus Notice</h4>
              <p className="mt-0.5 text-xs text-amber-800 leading-relaxed">
                {disagreementReason ||
                  'Failure Classifier and Isolation Forest diverge on current operational dynamics. Machine flagged for review.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Sensor Readings Grid */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Live Telemetry Sensor Readings
          </h2>
          <span className="text-[11px] font-mono text-slate-400">1.0s Ingestion Frequency</span>
        </div>

        {latestReading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {/* Air Temperature */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Air Temp</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.air_temperature === 'number'
                  ? `${(latestReading.air_temperature - 273.15).toFixed(1)}°C`
                  : typeof latestReading?.temperature === 'number'
                  ? `${latestReading.temperature.toFixed(1)}°C`
                  : '—'}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                {typeof latestReading?.air_temperature === 'number'
                  ? `${latestReading.air_temperature.toFixed(1)} K`
                  : 'Ambient'}
              </div>
            </div>

            {/* Process Temperature */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Process Temp</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.process_temperature === 'number'
                  ? `${(latestReading.process_temperature - 273.15).toFixed(1)}°C`
                  : typeof latestReading?.temperature === 'number'
                  ? `${latestReading.temperature.toFixed(1)}°C`
                  : '—'}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                {typeof latestReading?.process_temperature === 'number'
                  ? `${latestReading.process_temperature.toFixed(1)} K`
                  : 'Internal'}
              </div>
            </div>

            {/* Rotational Speed */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Spindle Speed</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.rotational_speed === 'number'
                  ? `${Math.round(latestReading.rotational_speed)}`
                  : '—'}
              </div>
              <div className="text-[10px] text-slate-400">rpm (1300–1800)</div>
            </div>

            {/* Torque */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Drive Torque</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.torque === 'number' ? `${latestReading.torque.toFixed(1)}` : '—'}
              </div>
              <div className="text-[10px] text-slate-400">Nm (Nominal 25–55)</div>
            </div>

            {/* Tool Wear */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Tool Wear</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.tool_wear === 'number' ? `${Math.round(latestReading.tool_wear)}` : '—'}
              </div>
              <div className="text-[10px] text-slate-400">min (Limit: 240)</div>
            </div>

            {/* Vibration */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Vibration</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.vibration === 'number' ? `${latestReading.vibration.toFixed(2)}` : '—'}
              </div>
              <div className="text-[10px] text-slate-400">mm/s (&lt; 5.0)</div>
            </div>

            {/* Pressure */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
              <div className="text-[11px] text-slate-500 font-medium">Line Pressure</div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-900">
                {typeof latestReading?.pressure === 'number' ? `${latestReading.pressure.toFixed(1)}` : '—'}
              </div>
              <div className="text-[10px] text-slate-400">bar</div>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center text-xs text-slate-400">
            Awaiting telemetry packets from data generator.
          </div>
        )}
      </div>

      {/* 3. Three Separate ML Prediction Sections */}
      <div>
        <h2 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          Predictive Maintenance AI Diagnoses
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Section A: Failure Prediction (Random Forest) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-xs font-bold text-slate-900 uppercase">
                  A. Failure Risk Analysis
                </span>
                <span className="text-[10px] font-mono text-slate-500 font-semibold">Random Forest</span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-slate-900">
                    {failurePct > 0 && failurePct < 0.1 ? `${failurePct.toFixed(2)}%` : `${failurePct.toFixed(1)}%`}
                  </div>
                  <div className="text-[11px] text-slate-500">Calculated Failure Risk</div>
                </div>
                <RiskBadge category={riskCat} size="md" />
              </div>

              {/* Plain-Language Explanation */}
              <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1.5">
                <div className="text-[11px] font-bold text-slate-800">
                  {riskCat === 'Critical'
                    ? 'Critical Failure Probability'
                    : riskCat === 'High'
                    ? 'Elevated Failure Risk'
                    : riskCat === 'Medium'
                    ? 'Moderate Parameter Drift'
                    : 'Nominal Operational Dynamics'}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {latestPred?.contributing_factors && latestPred.contributing_factors.length > 0
                    ? latestPred.contributing_factors.join(' ')
                    : 'All physical sensor parameters (speed, torque, wear, temperature) remain within nominal baseline tolerances.'}
                </p>
                <div className="pt-1 text-[11px] text-slate-700 font-medium">
                  <span className="font-semibold text-slate-900">Recommended action:</span>{' '}
                  {latestPred?.recommendation || 'Continue standard operational schedule and preventative monitoring.'}
                </div>
              </div>
            </div>

            {/* Expandable Technical Details Section */}
            <details className="mt-3 pt-2 border-t border-slate-100 group">
              <summary className="cursor-pointer text-[11px] font-semibold text-blue-700 hover:text-blue-900 flex items-center justify-between">
                <span>Technical Model Details</span>
                <span className="text-slate-400 group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="mt-2 space-y-1 text-[11px] font-mono text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-100">
                <div className="flex justify-between">
                  <span>Model:</span>
                  <span className="font-bold text-slate-800">AI4I RandomForestClassifier</span>
                </div>
                <div className="flex justify-between">
                  <span>Raw Decimal Probability:</span>
                  <span className="font-bold text-slate-800">
                    {typeof rawProb === 'number' && !isNaN(rawProb) ? rawProb.toFixed(5) : '0.00000'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Classification Threshold:</span>
                  <span>&ge; 0.6000 (60.0%)</span>
                </div>
                <div className="flex justify-between">
                  <span>Binary Flag:</span>
                  <span>{latestPred?.failure_prediction === 1 ? '1 (Failure)' : '0 (Normal)'}</span>
                </div>
              </div>
            </details>
          </div>

          {/* Section B: Operational Anomaly Detection (Isolation Forest) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-xs font-bold text-slate-900 uppercase">
                  B. Anomaly Detection
                </span>
                <span className="text-[10px] font-mono text-slate-500 font-semibold">Isolation Forest</span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-xl font-bold font-mono text-slate-900">
                    {isAnomaly ? 'Unusual Condition' : 'Normal Operating'}
                  </div>
                  <div className="text-[11px] text-slate-500">Operational Dynamics</div>
                </div>

                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-bold ${
                    isAnomaly
                      ? 'bg-rose-100 text-rose-800 border border-rose-200'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  }`}
                >
                  {isAnomaly ? 'Unusual' : 'Normal'}
                </span>
              </div>

              {/* Plain-Language Explanation */}
              <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1.5">
                <div className="text-[11px] font-bold text-slate-800">
                  {isAnomaly ? 'Unusual Operating Condition' : 'Normal Operating Behaviour'}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {isAnomaly ? (
                    typeof latestReading?.vibration === 'number' && latestReading.vibration > 5.0 ? (
                      <>
                        Vibration is{' '}
                        <span className="font-mono font-bold text-rose-700">
                          {latestReading.vibration.toFixed(2)} mm/s
                        </span>
                        , exceeding configured ISO limit of 5.0 mm/s (normal range: 0.5–5.0 mm/s).
                      </>
                    ) : typeof latestReading?.torque === 'number' && latestReading.torque > 60.0 ? (
                      <>
                        Drive torque is{' '}
                        <span className="font-mono font-bold text-amber-700">
                          {latestReading.torque.toFixed(1)} Nm
                        </span>
                        , exceeding normal rated torque of 55 Nm (normal range: 25–55 Nm).
                      </>
                    ) : (
                      <>Atypical operational parameter correlation detected outside standard multidimensional cluster dynamics.</>
                    )
                  ) : (
                    "Sensor readings are within the model's expected multidimensional operating pattern."
                  )}
                </p>
                <div className="pt-1 text-[11px] text-slate-700 font-medium">
                  <span className="font-semibold text-slate-900">Recommended action:</span>{' '}
                  {isAnomaly ? (
                    typeof latestReading?.vibration === 'number' && latestReading.vibration > 5.0
                      ? 'Inspect spindle bearings, mechanical balance, and mounting bolts.'
                      : typeof latestReading?.torque === 'number' && latestReading.torque > 60.0
                      ? 'Inspect workpiece feed rate and spindle drive motor.'
                      : 'Inspect operating load and verify sensor calibration.'
                  ) : (
                    'Continue standard preventative inspection schedule.'
                  )}
                </div>

                {/* Educational Notice */}
                <div className="mt-1 pt-1.5 border-t border-slate-200/70 text-[10px] text-slate-500 leading-tight">
                  <span className="font-semibold text-slate-700">Notice:</span> Anomaly detection identifies unusual multi-parameter sensor behaviour and statistical outliers; it is distinct from mechanical failure probability.
                </div>
              </div>
            </div>

            {/* Expandable Technical Details Section */}
            <details className="mt-3 pt-2 border-t border-slate-100 group">
              <summary className="cursor-pointer text-[11px] font-semibold text-blue-700 hover:text-blue-900 flex items-center justify-between">
                <span>Technical Model Details</span>
                <span className="text-slate-400 group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="mt-2 space-y-1 text-[11px] font-mono text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-100">
                <div className="flex justify-between">
                  <span>Model:</span>
                  <span className="font-bold text-slate-800">AI4I Isolation Forest Outlier Analysis</span>
                </div>
                <div className="flex justify-between">
                  <span>Raw Decision Score:</span>
                  <span className="font-bold text-slate-800">
                    {typeof anomScore === 'number' && !isNaN(anomScore)
                      ? anomScore > 0
                        ? `+${anomScore.toFixed(4)}`
                        : anomScore.toFixed(4)
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Decision Boundary:</span>
                  <span>0.0000 (Score &lt; 0 indicates anomaly)</span>
                </div>
                <div className="flex justify-between">
                  <span>Cluster Status:</span>
                  <span>{isAnomaly ? 'Sparse Statistical Outlier' : 'In-Distribution Cluster'}</span>
                </div>
              </div>
            </details>
          </div>

          {/* Section C: Remaining Useful Life (RUL Regressor) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-xs font-bold text-slate-900 uppercase">
                  C. Remaining Useful Life (RUL)
                </span>
                <span className="text-[10px] font-mono text-slate-500 font-semibold">RUL Regressor</span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-slate-900">
                    {typeof rulCycles === 'number' && !isNaN(rulCycles)
                      ? `${Math.round(rulCycles)}`
                      : 'Unavailable'}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {typeof rulCycles === 'number' && !isNaN(rulCycles)
                      ? `Remaining ${rulUnit}`
                      : 'RUL Estimation'}
                  </div>
                </div>

                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-bold ${
                    rulAvailable
                      ? 'bg-blue-100 text-blue-800 border border-blue-200'
                      : 'bg-slate-100 text-slate-600 border border-slate-200'
                  }`}
                >
                  {rulAvailable ? 'Model Active' : 'Unavailable'}
                </span>
              </div>

              {/* Plain-Language Explanation */}
              <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1.5">
                <div className="text-[11px] font-bold text-slate-800">
                  {typeof rulCycles === 'number' && !isNaN(rulCycles)
                    ? 'Tooling Life Cycle Estimation'
                    : 'Model Not Applicable'}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {typeof rulCycles === 'number' && !isNaN(rulCycles) ? (
                    <>
                      Estimated{' '}
                      <span className="font-mono font-bold text-slate-900">{Math.round(rulCycles)}</span>{' '}
                      production cycles remaining before cutting tool degradation reaches the critical 240-minute replacement limit.
                    </>
                  ) : (
                    'Unavailable: Tooling telemetry channels are not instrumented for this equipment type or tool wear sensor channel is inactive.'
                  )}
                </p>
                <div className="pt-1 text-[11px] text-slate-700 font-medium">
                  <span className="font-semibold text-slate-900">Recommended action:</span>{' '}
                  {typeof rulCycles === 'number' && rulCycles < 50
                    ? 'Schedule immediate cutting insert changeout before next production batch.'
                    : 'Continue standard operations; re-evaluate tool wear on shift transition.'}
                </div>
              </div>
            </div>

            {/* Expandable Technical Details Section */}
            <details className="mt-3 pt-2 border-t border-slate-100 group">
              <summary className="cursor-pointer text-[11px] font-semibold text-blue-700 hover:text-blue-900 flex items-center justify-between">
                <span>Technical Model Details</span>
                <span className="text-slate-400 group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="mt-2 space-y-1 text-[11px] font-mono text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-100">
                <div className="flex justify-between">
                  <span>Model:</span>
                  <span className="font-bold text-slate-800">PHM 2010 Tool Wear Regressor</span>
                </div>
                <div className="flex justify-between">
                  <span>Training Dataset:</span>
                  <span>PHM 2010 CNC High-Speed Milling</span>
                </div>
                <div className="flex justify-between">
                  <span>End-of-Life Boundary:</span>
                  <span>240 min Flank Wear</span>
                </div>
                <div className="flex justify-between">
                  <span>Model Availability:</span>
                  <span>{rulAvailable ? 'Ready (Inputs Validated)' : 'Incompatible Sensor Array'}</span>
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>

      {/* 4. Prescriptive Maintenance Recommendations */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <h2 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          Maintenance Recommendations & Rule Verification
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[11px] font-semibold text-slate-500 uppercase">Concern Status</div>
            <div className="mt-1 text-sm font-bold text-slate-900">
              {activeAlerts.length > 0 ? `${activeAlerts.length} Active Concern(s)` : 'Nominal Operational State'}
            </div>
            <p className="mt-0.5 text-xs text-slate-600">
              {activeAlerts.length > 0 ? activeAlerts[0].title : 'No active threshold violations.'}
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[11px] font-semibold text-slate-500 uppercase">Triggering Values</div>
            <div className="mt-1 font-mono text-xs text-slate-800 overflow-x-auto">
              {activeAlerts.length > 0 && activeAlerts[0].triggering_values
                ? JSON.stringify(activeAlerts[0].triggering_values)
                : 'All parameters within rated limits'}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[11px] font-semibold text-slate-500 uppercase">Recommended Inspection</div>
            <p className="mt-1 text-xs text-slate-700 font-medium">
              {latestPred?.recommendation || 'Standard preventative inspection cycle.'}
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[11px] font-semibold text-slate-500 uppercase">Maintenance Priority</div>
            <div className="mt-1">
              <span
                className={`inline-flex px-2 py-0.5 rounded text-xs font-bold ${
                  riskCat === 'Critical'
                    ? 'bg-rose-100 text-rose-800'
                    : riskCat === 'High'
                    ? 'bg-orange-100 text-orange-800'
                    : riskCat === 'Medium'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-emerald-100 text-emerald-800'
                }`}
              >
                {riskCat === 'Critical'
                  ? 'Immediate Shutdown'
                  : riskCat === 'High'
                  ? 'Inspect Within 24h'
                  : riskCat === 'Medium'
                  ? 'Monitor Next Shift'
                  : 'Routine'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Interactive Time-Series Sensor History Charts */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-tight">
              Telemetry Time-Series Trends
            </h2>
            <p className="text-xs text-slate-500">Real-time multi-channel sensor telemetry history</p>
          </div>

          {/* Chart View Switcher */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
            <button
              onClick={() => setActiveChartTab('mechanical')}
              className={`px-3 py-1 font-semibold rounded-md transition-colors ${
                activeChartTab === 'mechanical'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Speed & Torque
            </button>
            <button
              onClick={() => setActiveChartTab('thermal')}
              className={`px-3 py-1 font-semibold rounded-md transition-colors ${
                activeChartTab === 'thermal'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Thermal Gradient
            </button>
            <button
              onClick={() => setActiveChartTab('condition')}
              className={`px-3 py-1 font-semibold rounded-md transition-colors ${
                activeChartTab === 'condition'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Wear & Vibration
            </button>
          </div>
        </div>

        <div className="h-64 w-full">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#cbd5e1',
                    borderRadius: '8px',
                    fontSize: '11px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />

                {activeChartTab === 'mechanical' && (
                  <>
                    <Line
                      type="monotone"
                      dataKey="speed"
                      name="Rotational Speed (rpm)"
                      stroke="#2563eb"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="torque"
                      name="Torque (Nm)"
                      stroke="#d97706"
                      strokeWidth={2}
                      dot={false}
                    />
                  </>
                )}

                {activeChartTab === 'thermal' && (
                  <>
                    <Line
                      type="monotone"
                      dataKey="proc_temp_c"
                      name="Process Temp (°C)"
                      stroke="#dc2626"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="air_temp_c"
                      name="Air Temp (°C)"
                      stroke="#059669"
                      strokeWidth={2}
                      dot={false}
                    />
                  </>
                )}

                {activeChartTab === 'condition' && (
                  <>
                    <Line
                      type="monotone"
                      dataKey="wear"
                      name="Tool Wear (min)"
                      stroke="#7c3aed"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="vibration"
                      name="Vibration (mm/s)"
                      stroke="#ea580c"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="pressure"
                      name="Pressure (bar)"
                      stroke="#0284c7"
                      strokeWidth={2}
                      dot={false}
                    />
                  </>
                )}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-400">
              Gathering time-series data points...
            </div>
          )}
        </div>
      </div>

      {/* 6. Synchronized Prediction History Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <h2 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
          Synchronized ML Evaluation History
        </h2>
        <p className="text-xs text-slate-500 mb-3">
          Every record links the evaluated telemetry packet directly with model outputs
        </p>

        <div className="overflow-x-auto max-h-72 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-y border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="py-2 px-3">Timestamp</th>
                <th className="py-2 px-3">Failure Prob</th>
                <th className="py-2 px-3">ML Risk</th>
                <th className="py-2 px-3">Anomaly</th>
                <th className="py-2 px-3">Anomaly Score</th>
                <th className="py-2 px-3">RUL Cycles</th>
                <th className="py-2 px-3">Overall Health</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {predictions.map((p, idx) => {
                const pProb =
                  typeof p?.failure_probability === 'number'
                    ? p.failure_probability <= 1.0
                      ? p.failure_probability * 100.0
                      : p.failure_probability
                    : null;
                const pAnomaly = Boolean(p?.anomaly_detected || p?.anomaly);
                const pHealth = p?.machine_health_status || 'Healthy';

                return (
                  <tr key={p?.id || p?.prediction_id || idx} className="hover:bg-slate-50/80">
                    <td className="py-2 px-3 text-slate-500">{formatLocalTime(p?.timestamp)}</td>
                    <td className="py-2 px-3 font-bold text-slate-900">
                      {pProb !== null ? `${pProb.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className="py-2 px-3 font-sans">
                      <RiskBadge category={p?.risk_category || 'Low'} size="sm" />
                    </td>
                    <td className="py-2 px-3 font-sans">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          pAnomaly ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {p?.anomaly_label || (pAnomaly ? 'Anomaly' : 'Normal')}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-600">
                      {typeof p?.anomaly_score === 'number'
                        ? p.anomaly_score > 0
                          ? `+${p.anomaly_score.toFixed(3)}`
                          : p.anomaly_score.toFixed(3)
                        : '—'}
                    </td>
                    <td className="py-2 px-3 text-slate-900 font-bold">
                      {typeof p?.estimated_remaining_cuts === 'number'
                        ? Math.round(p.estimated_remaining_cuts)
                        : '—'}
                    </td>
                    <td className="py-2 px-3 font-sans">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          pHealth === 'Critical Risk' || pHealth === 'Critical'
                            ? 'bg-rose-100 text-rose-800'
                            : pHealth.includes('Warning') || pHealth === 'Attention Required'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {pHealth}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function MachineDetail(props) {
  return (
    <MachineErrorBoundary machineId={props.machineId} onBack={props.onBack}>
      <MachineDetailContent {...props} />
    </MachineErrorBoundary>
  );
}
