import React, { useEffect, useState } from 'react';
import { FileText, Search, RefreshCw, AlertTriangle, CheckCircle, Clock, XCircle, ShieldAlert } from 'lucide-react';
import { adminFetch } from '../lib/api';

interface DataRequestRecord {
  id: string;
  user_id: string;
  user_email?: string;
  user_name?: string;
  request_type: string; // 'export' | 'delete'
  status: string; // 'pending' | 'processing' | 'completed' | 'rejected'
  details?: Record<string, any>;
  admin_notes?: string;
  created_at?: string;
  processed_at?: string;
}

export const DataRequestsQueue: React.FC = () => {
  const [requests, setRequests] = useState<DataRequestRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [adminNotes, setAdminNotes] = useState<Record<string, string>>({});
  const [search, setSearch] = useState('');

  const fetchRequests = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/data-requests');
      if (!res.ok) {
        throw new Error('Failed to fetch data requests');
      }
      const data = await res.json();
      setRequests(data);
    } catch (err: any) {
      setError(err.message || 'Error loading data privacy requests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const handleProcess = async (requestId: string, status: 'completed' | 'rejected') => {
    setProcessingId(requestId);
    setError(null);
    setActionSuccess(null);
    try {
      const res = await adminFetch(`/api/admin/data-requests/${requestId}/process`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          admin_notes: adminNotes[requestId] || `Marked ${status} by administrator.`
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || 'Failed to update request status');
      }

      setActionSuccess(`Request successfully marked as ${status}.`);
      await fetchRequests();
    } catch (err: any) {
      setError(err.message || 'Error processing request');
    } finally {
      setProcessingId(null);
    }
  };

  const filteredRequests = requests.filter(r => {
    const s = search.toLowerCase();
    return (
      r.user_email?.toLowerCase().includes(s) ||
      r.user_name?.toLowerCase().includes(s) ||
      r.request_type?.toLowerCase().includes(s) ||
      r.id.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Data Privacy & GDPR Queue</h1>
          <p className="text-sm text-[#4B5563]">
            Review and fulfill farmer requests for personal data export and account erasure.
          </p>
        </div>
        <button
          onClick={fetchRequests}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-sm"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {actionSuccess && (
        <div className="p-4 rounded-xl bg-[#E8F5E9] border border-[#A7F3D0] text-[#1B4332] text-sm flex items-center gap-3">
          <CheckCircle size={18} className="text-[#2D6A4F] shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-3">
          <AlertTriangle size={18} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Input */}
      <div className="relative">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Filter requests by email, requester name, or ID..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#E5DFD3] bg-white text-sm text-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20 focus:border-[#2D6A4F]"
        />
      </div>

      {/* Requests List */}
      <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-[#374151]">
            <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
              <tr>
                <th className="px-6 py-4">Requester</th>
                <th className="px-6 py-4">Request Type</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Date Submitted</th>
                <th className="px-6 py-4">Admin Notes & Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5DFD3]">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                    Loading privacy requests from database...
                  </td>
                </tr>
              ) : filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                    No pending or processed data privacy requests found.
                  </td>
                </tr>
              ) : (
                filteredRequests.map(req => (
                  <tr key={req.id} className="hover:bg-[#FAF8F5]/60 transition">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-[#1B4332]">{req.user_name || 'Farmer Account'}</div>
                      <div className="text-xs text-[#6B7280]">{req.user_email || req.user_id}</div>
                      <div className="text-[10px] text-[#9CA3AF] font-mono mt-0.5">{req.id}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold uppercase ${
                        req.request_type === 'delete'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {req.request_type === 'delete' ? <ShieldAlert size={12} /> : <FileText size={12} />}
                        {req.request_type}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        req.status === 'completed'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : req.status === 'rejected'
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {req.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-[#6B7280]">
                      {req.created_at ? new Date(req.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      {req.status === 'pending' || req.status === 'processing' ? (
                        <div className="space-y-2">
                          <input
                            type="text"
                            placeholder="Add compliance notes..."
                            value={adminNotes[req.id] || ''}
                            onChange={e => setAdminNotes({ ...adminNotes, [req.id]: e.target.value })}
                            className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-[#E5DFD3] focus:outline-none focus:ring-1 focus:ring-[#2D6A4F]"
                          />
                          <div className="flex items-center gap-2">
                            <button
                              disabled={processingId === req.id}
                              onClick={() => handleProcess(req.id, 'completed')}
                              className="px-2.5 py-1 rounded-lg bg-[#2D6A4F] text-white text-xs font-semibold hover:bg-[#1B4332] disabled:opacity-50"
                            >
                              Fulfill & Complete
                            </button>
                            <button
                              disabled={processingId === req.id}
                              onClick={() => handleProcess(req.id, 'rejected')}
                              className="px-2.5 py-1 rounded-lg bg-red-100 text-red-700 text-xs font-semibold hover:bg-red-200 disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="text-xs text-[#6B7280]">
                          <p className="italic">{req.admin_notes || 'Processed'}</p>
                          <p className="text-[10px] text-[#9CA3AF] mt-0.5">
                            {req.processed_at ? new Date(req.processed_at).toLocaleString() : ''}
                          </p>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
