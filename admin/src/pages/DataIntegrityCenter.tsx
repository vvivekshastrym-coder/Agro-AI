import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import { Database, RefreshCw, AlertTriangle, CheckCircle2, XCircle, Play, Power } from 'lucide-react';

interface DataSourceRow {
  key: string;
  provider_name: string;
  provider_type: string;
  department_slug: string;
  endpoint_reference: string | null;
  supported_modules: string[];
  priority: number;
  freshness_threshold_hours: number;
  is_enabled: boolean;
  auth_configured: boolean;
  last_retrieved_at: string | null;
  last_source_reporting_date: string | null;
  freshness_status: string;
  last_status: string;
  last_error: string | null;
}

interface OverviewPayload {
  checked_at: string;
  total_sources: number;
  configured_sources: number;
  outlier_count: number;
  sources: DataSourceRow[];
  outliers: Array<{ id: string; commodity: string; market: string; min_price: number; modal_price: number; max_price: number; reasons: string[] }>;
  recent_sync_logs: Array<{ id: string; source_key: string; status: string; records_fetched: number; source_reporting_date: string | null; error_message: string | null; created_at: string | null }>;
}

export const DataIntegrityCenter: React.FC = () => {
  const { isAdminOrAbove } = useAdminAuth();
  const [data, setData] = useState<OverviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/data-integrity/overview');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message || 'Failed to load data integrity overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const triggerSync = async (key: string) => {
    setBusyKey(key);
    setError(null);
    try {
      const res = await adminFetch(`/api/admin/data-integrity/sources/${key}/sync`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e: any) {
      setError(e.message || 'Sync failed');
    } finally {
      setBusyKey(null);
    }
  };

  const toggleSource = async (s: DataSourceRow) => {
    const reason = window.prompt(`Reason for ${s.is_enabled ? 'disabling' : 'enabling'} ${s.provider_name}:`, `${s.is_enabled ? 'Paused' : 'Re-enabled'} provider`);
    if (!reason || reason.trim().length < 5) return;
    setBusyKey(s.key);
    try {
      const res = await adminFetch(`/api/admin/data-integrity/sources/${s.key}/toggle`, {
        method: 'POST',
        body: JSON.stringify({ is_enabled: !s.is_enabled, reason: reason.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e: any) {
      setError(e.message || 'Toggle failed');
    } finally {
      setBusyKey(null);
    }
  };

  const freshnessBadge = (st: string) => {
    if (st === 'FRESH') return 'bg-[#D1FAE5] text-[#065F46]';
    if (st === 'DELAYED') return 'bg-[#FEF3C7] text-[#92400E]';
    if (st === 'STALE') return 'bg-[#FEE2E2] text-[#991B1B]';
    return 'bg-[#F3F4F6] text-[#4B5563]';
  };

  if (loading && !data) return <div className="p-8 text-sm text-[#4B5563]">Loading Data Integrity Center...</div>;
  if (error && !data) return <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <Database size={22} className="text-[#2D6A4F]" /> Data Integrity & Source Monitoring
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Real Data Only Policy · Separate source reporting date vs. retrieval timestamp · Zero fabricated sync status
          </p>
        </div>
        <button onClick={load} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>}

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Registered Data Providers</div>
          <div className="text-2xl font-bold text-[#081C15] mt-1">{data.total_sources}</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Credentials Configured</div>
          <div className="text-2xl font-bold text-[#065F46] mt-1">{data.configured_sources} / {data.total_sources}</div>
        </div>
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
          <div className="text-xs text-[#6B7280]">Flagged Price Anomalies</div>
          <div className={`text-2xl font-bold mt-1 ${data.outlier_count > 0 ? 'text-red-700' : 'text-[#081C15]'}`}>{data.outlier_count}</div>
        </div>
      </div>

      {/* Providers List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.sources.map((s) => (
          <div key={s.key} className="bg-white border border-[#E5E7EB] rounded-2xl p-4 space-y-2.5">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-bold text-[#081C15]">{s.provider_name}</div>
                <div className="text-[11px] text-[#6B7280]">
                  Dept: <span className="font-mono text-[#1B4332]">{s.department_slug}</span> · Priority #{s.priority} · Modules: {s.supported_modules.join(', ')}
                </div>
              </div>
              <span className={`text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full ${freshnessBadge(s.freshness_status)}`}>
                {s.freshness_status}
              </span>
            </div>
            <div className="text-[11px] text-[#4B5563] space-y-0.5 pt-2 border-t border-[#F3F4F6]">
              <div>
                Auth: {s.auth_configured ? <span className="text-[#065F46] font-semibold"><CheckCircle2 size={11} className="inline mr-1" />Configured</span> : <span className="text-amber-700 font-semibold"><XCircle size={11} className="inline mr-1" />Not configured</span>}
                {' · '}Provider: <span className="font-semibold">{s.is_enabled ? 'Enabled' : 'Disabled'}</span>
              </div>
              <div>Source Reporting Date: <span className="font-mono">{s.last_source_reporting_date || 'None retrieved yet'}</span></div>
              <div>Last Retrieval (UTC): <span className="font-mono">{s.last_retrieved_at ? s.last_retrieved_at.slice(0, 19).replace('T', ' ') : 'Never'}</span></div>
              {s.last_error && <div className="text-red-700 flex items-center gap-1"><AlertTriangle size={11} /> {s.last_error}</div>}
            </div>
            {isAdminOrAbove && (
              <div className="flex items-center gap-2 pt-1">
                <button disabled={busyKey === s.key} onClick={() => triggerSync(s.key)} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer">
                  <Play size={12} /> Sync Now
                </button>
                <button disabled={busyKey === s.key} onClick={() => toggleSource(s)} className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-[#D1D5DB] bg-white text-[#374151] text-xs font-semibold hover:bg-gray-50 cursor-pointer">
                  <Power size={12} /> {s.is_enabled ? 'Disable' : 'Enable'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Recent Sync History */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 overflow-x-auto">
        <h3 className="text-sm font-bold text-[#081C15] mb-3">Recent Synchronization History</h3>
        {data.recent_sync_logs.length === 0 ? (
          <p className="text-xs text-[#6B7280]">No synchronization runs recorded yet. Click "Sync Now" on any provider above.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E5E7EB] text-[#6B7280] uppercase">
                <th className="py-2 pr-3">Provider</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Records</th>
                <th className="py-2 pr-3">Source Date</th>
                <th className="py-2">Detail / Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {data.recent_sync_logs.map((l) => (
                <tr key={l.id}>
                  <td className="py-2 pr-3 font-mono text-[11px]">{l.source_key}</td>
                  <td className="py-2 pr-3 font-semibold">{l.status}</td>
                  <td className="py-2 pr-3">{l.records_fetched}</td>
                  <td className="py-2 pr-3">{l.source_reporting_date || '—'}</td>
                  <td className="py-2 text-[#6B7280]">{l.error_message || 'OK'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
