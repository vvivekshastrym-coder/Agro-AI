import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import {
  Sliders,
  RefreshCw,
  Power,
  AlertOctagon,
  Wrench,
  Clock,
  Search,
  CheckCircle2,
  ShieldAlert,
} from 'lucide-react';

interface GlobalFeature {
  key: string;
  name: string;
  description: string;
  category: string;
  api_prefixes: string[];
  depends_on: string[];
  dependents: string[];
  status: 'ENABLED' | 'DISABLED' | 'MAINTENANCE' | 'EMERGENCY_SHUTDOWN' | 'SCHEDULED';
  maintenance_message: string | null;
  estimated_restore_at: string | null;
  scheduled_shutdown_at: string | null;
  scheduled_restore_at: string | null;
  revision: number;
  changed_by: string | null;
  changed_at: string | null;
  reason: string | null;
}

const CATEGORIES = ['all', 'ai', 'market', 'advisory', 'operations', 'commerce', 'finance', 'analytics', 'billing'];

export const FeatureControlCentre: React.FC = () => {
  const { isSuperAdmin } = useAdminAuth();
  const [features, setFeatures] = useState<GlobalFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [scheduleKey, setScheduleKey] = useState<string | null>(null);
  const [schedForm, setSchedForm] = useState({ shutdownAt: '', restoreAt: '', targetState: 'MAINTENANCE', reason: '' });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/features');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setFeatures(d.features || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load global feature controls');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const changeStatus = async (feat: GlobalFeature, status: 'ENABLED' | 'DISABLED' | 'MAINTENANCE' | 'EMERGENCY_SHUTDOWN') => {
    if (!isSuperAdmin) return;
    const depWarn = feat.dependents.length > 0 && status !== 'ENABLED'
      ? `\n\nDependent services that rely on ${feat.name}: ${feat.dependents.join(', ')}.`
      : '';
    const defaultReason =
      status === 'EMERGENCY_SHUTDOWN' ? `Emergency shutdown of ${feat.name}` :
      status === 'MAINTENANCE' ? `Scheduled maintenance on ${feat.name}` :
      status === 'DISABLED' ? `Disabled ${feat.name} by Super Admin` :
      `Restored ${feat.name} to normal operation`;
    const reason = window.prompt(`Enter audit reason for setting ${feat.name} -> ${status}:${depWarn}`, defaultReason);
    if (!reason || reason.trim().length < 5) return;

    let maintenance_message: string | undefined;
    if (status === 'MAINTENANCE' || status === 'EMERGENCY_SHUTDOWN') {
      const msg = window.prompt(
        `Optional farmer-facing message for ${feat.name} (leave blank for default):`,
        feat.maintenance_message || `${feat.name} is temporarily under maintenance. Your data is safe.`
      );
      if (msg !== null) maintenance_message = msg;
    }

    setBusyKey(feat.key);
    setError(null);
    try {
      const res = await adminFetch(`/api/admin/features/${feat.key}/status`, {
        method: 'POST',
        body: JSON.stringify({ status, reason: reason.trim(), maintenance_message }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.error?.message || `HTTP ${res.status}`);
      }
      await load();
    } catch (e: any) {
      setError(e.message || 'Feature update failed');
    } finally {
      setBusyKey(null);
    }
  };

  const submitSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleKey || !isSuperAdmin) return;
    setBusyKey(scheduleKey);
    setError(null);
    try {
      const res = await adminFetch(`/api/admin/features/${scheduleKey}/schedule`, {
        method: 'POST',
        body: JSON.stringify({
          scheduled_shutdown_at: schedForm.shutdownAt ? new Date(schedForm.shutdownAt).toISOString() : null,
          scheduled_restore_at: schedForm.restoreAt ? new Date(schedForm.restoreAt).toISOString() : null,
          scheduled_target_state: schedForm.targetState,
          reason: schedForm.reason.trim() || 'Scheduled maintenance window',
          cancel: false,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setScheduleKey(null);
      setSchedForm({ shutdownAt: '', restoreAt: '', targetState: 'MAINTENANCE', reason: '' });
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not schedule feature window');
    } finally {
      setBusyKey(null);
    }
  };

  const cancelSchedule = async (key: string) => {
    if (!isSuperAdmin) return;
    setBusyKey(key);
    try {
      const res = await adminFetch(`/api/admin/features/${key}/schedule`, {
        method: 'POST',
        body: JSON.stringify({ cancel: true, reason: 'Cancelled scheduled maintenance window' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (err: any) {
      setError(err.message || 'Cancel failed');
    } finally {
      setBusyKey(null);
    }
  };

  const statusBadge = (st: string) => {
    switch (st) {
      case 'ENABLED': return 'bg-[#D1FAE5] text-[#065F46] border-[#A7F3D0]';
      case 'MAINTENANCE': return 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
      case 'SCHEDULED': return 'bg-[#DBEAFE] text-[#1E40AF] border-[#BFDBFE]';
      case 'EMERGENCY_SHUTDOWN': return 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]';
      default: return 'bg-[#F3F4F6] text-[#374151] border-[#E5E7EB]';
    }
  };

  const filtered = features.filter((f) => {
    const matchCat = category === 'all' || f.category === category;
    const q = search.trim().toLowerCase();
    const matchQ = !q || f.name.toLowerCase().includes(q) || f.key.toLowerCase().includes(q) || f.description.toLowerCase().includes(q);
    return matchCat && matchQ;
  });

  const enabledCount = features.filter((f) => f.status === 'ENABLED').length;
  const haltedCount = features.filter((f) => ['DISABLED', 'MAINTENANCE', 'EMERGENCY_SHUTDOWN'].includes(f.status)).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <Sliders size={22} className="text-[#2D6A4F]" /> Global Feature Control Centre
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Server-enforced feature switches · Super Admin exclusive write control · Auth, RBAC & Audit Logs are protected and cannot be disabled
          </p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] transition cursor-pointer"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Sync Live State
        </button>
      </div>

      {/* Summary Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Total Controlled Modules</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">{features.length}</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Enabled & Operational</div>
          <div className="text-2xl font-bold text-[#065F46] mt-1">{enabledCount}</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Disabled / Maintenance / Emergency</div>
          <div className={`text-2xl font-bold mt-1 ${haltedCount > 0 ? 'text-red-700' : 'text-[#081C15]'}`}>{haltedCount}</div>
        </div>
      </div>

      {!isSuperAdmin && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-center gap-2">
          <ShieldAlert size={15} /> Read-only view: Only the Founder / Super Admin can enable, disable, or trigger emergency shutdowns.
        </div>
      )}

      {error && (
        <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>
      )}

      {/* Search & Category Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={14} className="absolute left-3 top-2.5 text-[#9CA3AF]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search features (Mandi, AgroGPT, Weather, Drone...)"
            className="w-full pl-9 pr-3 py-2 text-xs bg-white border border-[#D1D5DB] rounded-xl"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`px-3 py-1.5 rounded-full text-[11px] font-semibold capitalize cursor-pointer border ${
                category === c ? 'bg-[#1B4332] text-white border-[#1B4332]' : 'bg-white text-[#4B5563] border-[#E5E7EB] hover:bg-gray-50'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Schedule Drawer */}
      {scheduleKey && (
        <form onSubmit={submitSchedule} className="bg-white border border-[#2D6A4F] rounded-2xl p-5 space-y-3 shadow-sm">
          <h3 className="text-sm font-bold text-[#081C15]">Schedule Backend Shutdown / Auto-Restore for <span className="font-mono text-[#2D6A4F]">{scheduleKey}</span></h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <label className="block">
              <span className="text-[#4B5563] font-medium">Shutdown Time (Local)</span>
              <input type="datetime-local" value={schedForm.shutdownAt} onChange={(e) => setSchedForm({ ...schedForm, shutdownAt: e.target.value })} className="mt-1 w-full px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            </label>
            <label className="block">
              <span className="text-[#4B5563] font-medium">Auto-Restore Time (Local)</span>
              <input type="datetime-local" value={schedForm.restoreAt} onChange={(e) => setSchedForm({ ...schedForm, restoreAt: e.target.value })} className="mt-1 w-full px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            </label>
            <label className="block">
              <span className="text-[#4B5563] font-medium">Target State</span>
              <select value={schedForm.targetState} onChange={(e) => setSchedForm({ ...schedForm, targetState: e.target.value })} className="mt-1 w-full px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white">
                <option value="MAINTENANCE">MAINTENANCE</option>
                <option value="DISABLED">DISABLED</option>
              </select>
            </label>
          </div>
          <input required minLength={5} placeholder="Audit reason (min 5 chars)" value={schedForm.reason} onChange={(e) => setSchedForm({ ...schedForm, reason: e.target.value })} className="w-full px-3 py-2 text-xs border border-[#D1D5DB] rounded-lg" />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setScheduleKey(null)} className="px-3 py-1.5 text-xs rounded-lg border border-[#D1D5DB] cursor-pointer">Cancel</button>
            <button type="submit" className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-[#1B4332] text-white cursor-pointer">Save Schedule</button>
          </div>
        </form>
      )}

      {/* Feature Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((f) => {
          const isBusy = busyKey === f.key;
          const isHalted = f.status !== 'ENABLED';
          return (
            <div key={f.key} className={`bg-white rounded-2xl p-5 border ${f.status === 'EMERGENCY_SHUTDOWN' ? 'border-red-300 bg-red-50/30' : 'border-[#E5E7EB]'}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-[#081C15]">{f.name}</h3>
                    <span className="text-[10px] font-mono text-[#6B7280] bg-[#FAF8F5] px-1.5 py-0.5 rounded border border-[#E5E7EB]">{f.key}</span>
                  </div>
                  <p className="text-xs text-[#6B7280] mt-1">{f.description}</p>
                </div>
                <span className={`text-[10px] font-bold uppercase px-2.5 py-1 rounded-full border whitespace-nowrap ${statusBadge(f.status)}`}>
                  {f.status.replace('_', ' ')}
                </span>
              </div>

              <div className="mt-3 pt-3 border-t border-[#F3F4F6] text-[11px] text-[#6B7280] space-y-1">
                <div>API: <span className="font-mono text-[#374151]">{f.api_prefixes.join(', ')}</span> · Rev v{f.revision}</div>
                {f.dependents.length > 0 && (
                  <div className="text-amber-700">Dependent modules: <span className="font-semibold">{f.dependents.join(', ')}</span></div>
                )}
                {f.reason && <div>Last reason: <span className="text-[#374151]">{f.reason}</span></div>}
                {(f.scheduled_shutdown_at || f.scheduled_restore_at) && (
                  <div className="text-blue-700 flex items-center justify-between">
                    <span>Schedule: {f.scheduled_shutdown_at ? `Off ${f.scheduled_shutdown_at.slice(0, 16)}` : ''} {f.scheduled_restore_at ? `→ On ${f.scheduled_restore_at.slice(0, 16)}` : ''}</span>
                    {isSuperAdmin && (
                      <button onClick={() => cancelSchedule(f.key)} className="underline text-xs cursor-pointer">Cancel</button>
                    )}
                  </div>
                )}
              </div>

              {isSuperAdmin && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {isHalted ? (
                    <button
                      disabled={isBusy}
                      onClick={() => changeStatus(f, 'ENABLED')}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer"
                    >
                      <CheckCircle2 size={13} /> Restore / Enable
                    </button>
                  ) : (
                    <button
                      disabled={isBusy}
                      onClick={() => changeStatus(f, 'DISABLED')}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-[#D1D5DB] bg-white text-[#374151] text-xs font-semibold hover:bg-gray-50 cursor-pointer"
                    >
                      <Power size={13} /> Disable
                    </button>
                  )}
                  <button
                    disabled={isBusy}
                    onClick={() => changeStatus(f, 'MAINTENANCE')}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-amber-100 text-amber-900 text-xs font-semibold hover:bg-amber-200 cursor-pointer"
                  >
                    <Wrench size={13} /> Maintenance
                  </button>
                  <button
                    disabled={isBusy}
                    onClick={() => setScheduleKey(f.key)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-50 text-blue-800 text-xs font-semibold hover:bg-blue-100 cursor-pointer"
                  >
                    <Clock size={13} /> Schedule
                  </button>
                  <button
                    disabled={isBusy}
                    onClick={() => changeStatus(f, 'EMERGENCY_SHUTDOWN')}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-red-700 text-white text-xs font-semibold hover:bg-red-800 cursor-pointer ml-auto"
                  >
                    <AlertOctagon size={13} /> Emergency Off
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
