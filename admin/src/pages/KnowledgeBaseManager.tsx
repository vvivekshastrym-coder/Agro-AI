import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import { BookOpen, Plus, CheckCircle2, XCircle, RefreshCw, ExternalLink } from 'lucide-react';

interface KnowledgeSource {
  id: string;
  title: string;
  publisher: string;
  source_url: string | null;
  crop: string;
  region: string;
  language: string;
  publication_date: string | null;
  last_verified_date: string | null;
  license_status: string;
  review_status: 'draft' | 'under_review' | 'approved' | 'rejected';
  summary: string | null;
  version: number;
}

export const KnowledgeBaseManager: React.FC = () => {
  const { isAdminOrAbove } = useAdminAuth();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    title: '',
    publisher: 'UAS Bengaluru / KVK Mandya',
    source_url: '',
    crop: 'Ragi',
    region: 'Mandya, Karnataka',
    language: 'en',
    publication_date: '',
    license_status: 'link_and_summary_only',
    summary: '',
  });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/knowledge/sources');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setSources(d.sources || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load knowledge sources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await adminFetch('/api/admin/knowledge/sources', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.error?.message || `HTTP ${res.status}`);
      }
      setShowAdd(false);
      setForm({ ...form, title: '', source_url: '', summary: '' });
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not add source');
    }
  };

  const handleReview = async (id: string, status: 'approved' | 'rejected') => {
    try {
      const res = await adminFetch(`/api/admin/knowledge/sources/${id}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ review_status: status }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (err: any) {
      setError(err.message || 'Review update failed');
    }
  };

  const statusBadge = (s: string) => {
    if (s === 'approved') return 'bg-[#D1FAE5] text-[#065F46]';
    if (s === 'rejected') return 'bg-[#FEE2E2] text-[#991B1B]';
    return 'bg-[#FEF3C7] text-[#92400E]';
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-[#081C15] flex items-center gap-2">
            <BookOpen size={22} className="text-[#2D6A4F]" /> Agricultural Knowledge Library
          </h2>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Verified ICAR, KVK & State Agricultural University sources · Unreviewed drafts are never used for AgroGPT dosage guidance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[#D1D5DB] bg-white text-xs font-semibold text-[#1F2937] hover:bg-gray-50 cursor-pointer"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button
            onClick={() => setShowAdd((v) => !v)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] cursor-pointer"
          >
            <Plus size={14} /> Add Source Draft
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">{error}</div>
      )}

      {showAdd && (
        <form onSubmit={handleCreate} className="bg-white border border-[#E5E7EB] rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-[#081C15]">Register New Knowledge Source (Saved as Draft)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <input required placeholder="Document Title (e.g. Package of Practices — Ragi)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input required placeholder="Publisher (ICAR / KVK / SAU)" value={form.publisher} onChange={(e) => setForm({ ...form, publisher: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input placeholder="Official Source URL" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input required placeholder="Crop (e.g. Ragi, Paddy, Tomato)" value={form.crop} onChange={(e) => setForm({ ...form, crop: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <input required placeholder="Region (e.g. Mandya, Karnataka)" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg" />
            <select value={form.license_status} onChange={(e) => setForm({ ...form, license_status: e.target.value })} className="px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white">
              <option value="link_and_summary_only">Link + Own Summary Only</option>
              <option value="public_domain_govt">Public Domain / Open Govt License</option>
              <option value="publisher_permission_granted">Publisher Permission Granted</option>
            </select>
          </div>
          <textarea rows={2} placeholder="Agronomist-written summary (do not paste copyrighted full text without permission)" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} className="w-full px-3 py-2 text-xs border border-[#D1D5DB] rounded-lg" />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-xs rounded-lg border border-[#D1D5DB] cursor-pointer">Cancel</button>
            <button type="submit" className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-[#1B4332] text-white cursor-pointer">Save Draft</button>
          </div>
        </form>
      )}

      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-5 overflow-x-auto">
        {sources.length === 0 ? (
          <p className="text-xs text-[#6B7280]">No agricultural knowledge sources registered yet. Add an ICAR, KVK, or SAU draft above for agronomist review.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E5E7EB] text-[#6B7280] uppercase">
                <th className="py-2 pr-3">Title & Publisher</th>
                <th className="py-2 pr-3">Crop / Region</th>
                <th className="py-2 pr-3">License</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Verified</th>
                {isAdminOrAbove && <th className="py-2">Review Action</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F4F6]">
              {sources.map((s) => (
                <tr key={s.id}>
                  <td className="py-2.5 pr-3">
                    <div className="font-semibold text-[#081C15] flex items-center gap-1.5">
                      {s.title}
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noreferrer" className="text-[#2D6A4F]">
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                    <div className="text-[11px] text-[#6B7280]">{s.publisher} · v{s.version}</div>
                  </td>
                  <td className="py-2.5 pr-3">{s.crop} · {s.region} ({s.language})</td>
                  <td className="py-2.5 pr-3 text-[11px] text-[#4B5563]">{s.license_status.replace(/_/g, ' ')}</td>
                  <td className="py-2.5 pr-3">
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${statusBadge(s.review_status)}`}>
                      {s.review_status}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-[#6B7280]">{s.last_verified_date || 'Pending'}</td>
                  {isAdminOrAbove && (
                    <td className="py-2.5">
                      <div className="flex items-center gap-1.5">
                        <button onClick={() => handleReview(s.id, 'approved')} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#D1FAE5] text-[#065F46] font-semibold hover:bg-[#A7F3D0] cursor-pointer">
                          <CheckCircle2 size={12} /> Approve
                        </button>
                        <button onClick={() => handleReview(s.id, 'rejected')} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#FEE2E2] text-[#991B1B] font-semibold hover:bg-[#FECACA] cursor-pointer">
                          <XCircle size={12} /> Reject
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
