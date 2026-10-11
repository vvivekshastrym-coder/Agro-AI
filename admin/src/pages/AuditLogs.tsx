import React, { useEffect, useState } from 'react';
import { ShieldCheck, Search, RefreshCw, AlertTriangle, Terminal } from 'lucide-react';
import { adminFetch } from '../lib/api';

interface AuditLogRecord {
  id: string;
  actor_id?: string;
  actor_role: string;
  action: string;
  target_entity: string;
  target_id?: string;
  details: Record<string, any>;
  ip_address?: string;
  created_at?: string;
}

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedDetails, setSelectedDetails] = useState<Record<string, any> | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/audit-logs');
      if (!res.ok) {
        throw new Error('Failed to retrieve security audit logs');
      }
      const data = await res.json();
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Error fetching audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter(l => {
    const s = search.toLowerCase();
    return (
      l.action.toLowerCase().includes(s) ||
      l.target_entity.toLowerCase().includes(s) ||
      l.actor_role.toLowerCase().includes(s) ||
      l.target_id?.toLowerCase().includes(s) ||
      l.actor_id?.toLowerCase().includes(s) ||
      l.ip_address?.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Security Audit Logs</h1>
          <p className="text-sm text-[#4B5563]">
            Tamper-evident, server-recorded log of all administrative operations and privileged state changes.
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-sm"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-3">
          <AlertTriangle size={18} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Filter audit logs by action, target entity, role, IP..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#E5DFD3] bg-white text-sm text-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20 focus:border-[#2D6A4F]"
        />
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-[#374151]">
            <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
              <tr>
                <th className="px-6 py-4">Timestamp</th>
                <th className="px-6 py-4">Action</th>
                <th className="px-6 py-4">Actor</th>
                <th className="px-6 py-4">Target Entity</th>
                <th className="px-6 py-4">IP Address</th>
                <th className="px-6 py-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5DFD3] font-mono text-xs">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm font-sans text-[#6B7280]">
                    Loading audit trail from database...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm font-sans text-[#6B7280]">
                    No audit records found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => (
                  <tr key={log.id} className="hover:bg-[#FAF8F5]/60 transition">
                    <td className="px-6 py-4 text-[#4B5563] whitespace-nowrap">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-semibold text-[#1B4332] bg-[#E8F5E9] text-[#2D6A4F] px-2 py-0.5 rounded border border-[#C8E6C9]">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-[#1B4332]">{log.actor_role}</div>
                      <div className="text-[10px] text-[#9CA3AF] truncate max-w-[120px]">{log.actor_id || 'System'}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-[#374151]">{log.target_entity}</div>
                      <div className="text-[10px] text-[#9CA3AF] truncate max-w-[140px]">{log.target_id || '—'}</div>
                    </td>
                    <td className="px-6 py-4 text-[#6B7280]">
                      {log.ip_address || '—'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => setSelectedDetails(log.details)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#FAF8F5] text-[#2D6A4F] font-sans font-medium text-xs hover:bg-[#E8F5E9] border border-[#E5DFD3] transition"
                      >
                        <Terminal size={12} /> View Payload
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* JSON Modal */}
      {selectedDetails && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-[#E5DFD3] space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-base text-[#1B4332]">Audit Event Payload</h3>
              <button
                onClick={() => setSelectedDetails(null)}
                className="text-[#9CA3AF] hover:text-[#1B4332] text-sm font-semibold"
              >
                ✕ Close
              </button>
            </div>
            <pre className="p-4 rounded-xl bg-[#081C15] text-[#A7F3D0] text-xs font-mono overflow-auto max-h-96">
              {JSON.stringify(selectedDetails, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
