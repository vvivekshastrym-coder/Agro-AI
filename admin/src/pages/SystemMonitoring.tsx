import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import { Activity, RefreshCw, ShieldAlert, Lock, Unlock, CheckCircle2, AlertTriangle, Server } from 'lucide-react';

interface HealthData {
  checked_at: string;
  environment: string;
  mfa_enforced_global: boolean;
  emergency_lockdown: boolean;
  services: Array<{ name: string; status: string; detail: string; checked_at: string }>;
  modules: Array<{ key: string; name: string; status: string; detail: string }>;
}

export const SystemMonitoring: React.FC = () => {
  const { isSuperAdmin } = useAdminAuth();
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lockReason, setLockReason] = useState('');
  const [lockBusy, setLockBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/system/health');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message || 'Failed to load system health');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleLockdown = async (enable: boolean) => {
    const reason = lockReason.trim() || (enable ? 'Emergency security lockdown triggered by Super Admin' : 'Lockdown lifted after security review');
    if (reason.length < 5) return;
    if (!window.confirm(enable
      ? 'Confirm EMERGENCY LOCKDOWN? All non-Super-Admin sessions will be revoked immediately.'
      : 'Confirm lifting Emergency Lockdown?')) {
      return;
    }
    setLockBusy(true);
    try {
      const res = await adminFetch('/api/admin/security/lockdown', {
        method: 'POST',
        body: JSON.stringify({ enabled: enable, reason }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setLockReason('');
      await load();
    } catch (e: any) {
      setError(e.message || 'Lockdown action failed');
    } finally {
      setLockBusy(false);
    }
  };

  if (loading && !data) return <div className="p-8 text-sm text-[#4B5563]">Checking live service health...</div>;
  if (error && !data) return <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">{error}</div>;
  if (!data) return null;

  const badge = (st: string) => {
    if (st === 'healthy' || st === 'active') return 'bg-[#D1FAE5] text-[#065F46]';
    if (st === 'partial' || st === 'preview' || st === 'configured_client_only') return 'bg-[#FEF3C7] text-[#92400E]';
    if (st === 'not_configured') return 'bg-[#F3F4F6] text-[#4B5563]';
    return 'bg-[#FEE2E2] text-[#991B1B]';
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <Activity size={22} className="text-[#2D6A4F]" /> System Monitoring & Feature Health
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Real-time backend probes · Environment: <span className="font-semibold">{data.environment}</span> · Checked: {data.checked_at.slice(0, 19).replace('T', ' ')} UTC
          </p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] transition cursor-pointer"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Re-check Now
        </button>
      </div>

      {/* Emergency Lockdown Panel (Super Admin Only) */}
      <div className={`rounded-2xl p-5 border ${data.emergency_lockdown ? 'bg-red-50 border-red-300' : 'bg-white border-[#E5E7EB]'}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-[#081C15] flex items-center gap-2">
              <ShieldAlert size={16} className={data.emergency_lockdown ? 'text-red-600' : 'text-[#2D6A4F]'} />
              Zero-Trust Security Posture & Emergency Lockdown
            </h3>
            <p className="text-xs text-[#4B5563] mt-1">
              MFA Enforcement: <span className="font-semibold">{data.mfa_enforced_global ? 'Mandatory (aal2)' : 'Configurable (Dev Mode)'}</span> ·
              Lockdown Status: <span className={`font-bold ${data.emergency_lockdown ? 'text-red-700' : 'text-[#1B4332]'}`}>
                {data.emergency_lockdown ? 'LOCKDOWN ACTIVE' : 'Normal Operations'}
              </span>
            </p>
          </div>
          {isSuperAdmin && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={lockReason}
                onChange={(e) => setLockReason(e.target.value)}
                placeholder="Reason for audit log (min 5 chars)"
                className="px-3 py-1.5 text-xs border border-[#D1D5DB] rounded-lg bg-white w-64"
              />
              {data.emergency_lockdown ? (
                <button
                  disabled={lockBusy}
                  onClick={() => toggleLockdown(false)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer"
                >
                  <Unlock size={13} /> Lift Lockdown
                </button>
              ) : (
                <button
                  disabled={lockBusy}
                  onClick={() => toggleLockdown(true)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-red-700 text-white text-xs font-semibold hover:bg-red-800 cursor-pointer"
                >
                  <Lock size={13} /> Activate Lockdown
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Infrastructure Services */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5">
        <h3 className="text-sm font-bold text-[#081C15] mb-3 flex items-center gap-2">
          <Server size={16} className="text-[#2D6A4F]" /> Live Backend & External Service Probes
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.services.map((s) => (
            <div key={s.name} className="p-3.5 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB] flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#081C15]">{s.name}</div>
                <div className="text-xs text-[#6B7280] mt-0.5">{s.detail}</div>
              </div>
              <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full whitespace-nowrap ${badge(s.status)}`}>
                {s.status === 'healthy' ? <CheckCircle2 size={11} className="inline mr-1" /> : <AlertTriangle size={11} className="inline mr-1" />}
                {s.status.replace(/_/g, ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Feature / Module Availability */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5">
        <h3 className="text-sm font-bold text-[#081C15] mb-3">Platform Feature Availability</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.modules.map((m) => (
            <div key={m.key} className="p-3.5 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-[#081C15]">{m.name}</span>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${badge(m.status)}`}>
                  {m.status}
                </span>
              </div>
              <p className="text-xs text-[#6B7280] mt-1">{m.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
