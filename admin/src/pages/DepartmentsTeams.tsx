import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import { Building2, RefreshCw, Plus, CheckCircle2, XCircle, Send } from 'lucide-react';

interface DepartmentRow {
  slug: string;
  name: string;
  description: string | null;
  is_active: boolean;
  member_count: number;
  team_count: number;
}

interface FeatureReqRow {
  id: string;
  feature_key: string;
  requested_status: string;
  reason: string;
  department_slug: string | null;
  requested_by: string | null;
  status: string;
  review_notes: string | null;
  created_at: string | null;
}

export const DepartmentsTeams: React.FC = () => {
  const { isSuperAdmin, isAdminOrAbove, profile } = useAdminAuth();
  const [depts, setDepts] = useState<DepartmentRow[]>([]);
  const [requests, setRequests] = useState<FeatureReqRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddDept, setShowAddDept] = useState(false);
  const [deptForm, setDeptForm] = useState({ slug: '', name: '', description: '' });
  const [reqForm, setReqForm] = useState({ feature_key: 'mandi', requested_status: 'MAINTENANCE', reason: '' });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dRes, rRes] = await Promise.all([
        adminFetch('/api/admin/departments'),
        isAdminOrAbove ? adminFetch('/api/admin/features/requests') : Promise.resolve(null),
      ]);
      if (!dRes.ok) throw new Error(`HTTP ${dRes.status}`);
      const dData = await dRes.json();
      setDepts(dData.departments || []);
      if (rRes && rRes.ok) {
        const rData = await rRes.json();
        setRequests(rData.requests || []);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load departments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const createDept = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await adminFetch('/api/admin/departments', {
        method: 'POST',
        body: JSON.stringify({ ...deptForm, is_active: true }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setShowAddDept(false);
      setDeptForm({ slug: '', name: '', description: '' });
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save department');
    }
  };

  const submitFeatureRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await adminFetch('/api/admin/features/requests', {
        method: 'POST',
        body: JSON.stringify({ ...reqForm, department_slug: profile?.departments?.[0] || null }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReqForm({ ...reqForm, reason: '' });
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not submit request');
    }
  };

  const decideRequest = async (id: string, decision: 'approved' | 'rejected') => {
    try {
      const res = await adminFetch(`/api/admin/features/requests/${id}/decide`, {
        method: 'POST',
        body: JSON.stringify({ decision, review_notes: `Reviewed by Super Admin (${decision})` }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (err: any) {
      setError(err.message || 'Decision failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <Building2 size={22} className="text-[#2D6A4F]" /> 4-Level Hierarchy · Departments & Teams
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            L1 Super Admin (Global) → L2 Dept Admin (Assigned Depts) → L3 Supervisor (Assigned Team) → L4 Staff (Assigned Tasks)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[#D1D5DB] bg-white text-xs font-semibold cursor-pointer">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          {isSuperAdmin && (
            <button onClick={() => setShowAddDept((v) => !v)} className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer">
              <Plus size={14} /> New Department
            </button>
          )}
        </div>
      </div>

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>}

      {showAddDept && isSuperAdmin && (
        <form onSubmit={createDept} className="bg-white border border-[#E5E7EB] rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-[#081C15]">Create / Update Department</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <input required pattern="[a-z0-9_-]+" placeholder="Slug (e.g. mandi)" value={deptForm.slug} onChange={(e) => setDeptForm({ ...deptForm, slug: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input required placeholder="Department Name" value={deptForm.name} onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input placeholder="Description" value={deptForm.description} onChange={(e) => setDeptForm({ ...deptForm, description: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowAddDept(false)} className="px-3 py-1.5 text-xs rounded-lg border border-[#D1D5DB] cursor-pointer">Cancel</button>
            <button type="submit" className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-[#1B4332] text-white cursor-pointer">Save Department</button>
          </div>
        </form>
      )}

      {/* Departments Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {depts.map((d) => (
          <div key={d.slug} className="bg-white border border-[#E5E7EB] rounded-2xl p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-[#081C15]">{d.name}</h3>
              <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${d.is_active ? 'bg-[#D1FAE5] text-[#065F46]' : 'bg-gray-100 text-gray-600'}`}>
                {d.is_active ? 'Active' : 'Suspended'}
              </span>
            </div>
            <p className="text-xs text-[#6B7280] mt-1">{d.description || 'Operational department'}</p>
            <div className="mt-3 pt-2.5 border-t border-[#F3F4F6] text-[11px] text-[#4B5563] flex items-center justify-between">
              <span className="font-mono text-[#2D6A4F]">{d.slug}</span>
              <span>{d.member_count} members · {d.team_count} teams</span>
            </div>
          </div>
        ))}
      </div>

      {/* Feature Change Requests Queue (Admins Request -> Super Admin Approves) */}
      {isAdminOrAbove && (
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 space-y-4">
          <h3 className="text-sm font-bold text-[#081C15]">Feature Shutdown & Maintenance Requests (Dept Admin → Super Admin Approval)</h3>
          <form onSubmit={submitFeatureRequest} className="grid grid-cols-1 md:grid-cols-4 gap-2.5 text-xs">
            <select value={reqForm.feature_key} onChange={(e) => setReqForm({ ...reqForm, feature_key: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white">
              <option value="mandi">Mandi</option>
              <option value="agrogpt">AgroGPT</option>
              <option value="weather">Weather</option>
              <option value="diagnosis">Crop Diagnosis</option>
              <option value="marketplace">Marketplace</option>
              <option value="logistics">Logistics</option>
              <option value="drone">Drone</option>
            </select>
            <select value={reqForm.requested_status} onChange={(e) => setReqForm({ ...reqForm, requested_status: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white">
              <option value="MAINTENANCE">MAINTENANCE</option>
              <option value="DISABLED">DISABLED</option>
              <option value="EMERGENCY_SHUTDOWN">EMERGENCY_SHUTDOWN</option>
              <option value="ENABLED">ENABLED (Restore)</option>
            </select>
            <input required minLength={5} placeholder="Reason for Super Admin review" value={reqForm.reason} onChange={(e) => setReqForm({ ...reqForm, reason: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <button type="submit" className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#1B4332] text-white font-semibold hover:bg-[#2D6A4F] cursor-pointer">
              <Send size={13} /> Submit Request
            </button>
          </form>

          {requests.length === 0 ? (
            <p className="text-xs text-[#6B7280]">No pending or historical feature change requests.</p>
          ) : (
            <div className="space-y-2">
              {requests.map((r) => (
                <div key={r.id} className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E7EB] flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div>
                    <span className="font-bold text-[#081C15]">{r.feature_key}</span> → <span className="font-mono font-semibold text-amber-800">{r.requested_status}</span>
                    <span className="ml-2 text-[#6B7280]">({r.reason})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${r.status === 'approved' ? 'bg-[#D1FAE5] text-[#065F46]' : r.status === 'rejected' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'}`}>
                      {r.status}
                    </span>
                    {isSuperAdmin && r.status === 'pending' && (
                      <>
                        <button onClick={() => decideRequest(r.id, 'approved')} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#D1FAE5] text-[#065F46] font-semibold cursor-pointer">
                          <CheckCircle2 size={12} /> Approve & Apply
                        </button>
                        <button onClick={() => decideRequest(r.id, 'rejected')} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-100 text-red-700 font-semibold cursor-pointer">
                          <XCircle size={12} /> Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
