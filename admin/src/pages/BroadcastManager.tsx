import React, { useEffect, useState } from 'react';
import { useAdminAuth } from '../context/AdminAuthContext';
import { adminFetch } from '../lib/api';
import {
  Megaphone,
  Tag,
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Lock,
  Sparkles,
  Calendar,
  Percent,
  Search,
  Trash2,
  Send,
  Eye
} from 'lucide-react';

interface BroadcastRecord {
  id: string;
  item_type: 'post' | 'offer' | 'advisory';
  title: string;
  content: string;
  discount_percent?: number | null;
  discount_code?: string | null;
  target_plan_slug?: string | null;
  banner_url?: string | null;
  tags: string[];
  status: 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'archived';
  created_by?: string;
  author_name?: string;
  author_email?: string;
  submitted_at?: string;
  approved_by?: string;
  approver_name?: string;
  approved_at?: string;
  super_admin_notes?: string;
  valid_from?: string;
  valid_until?: string;
  created_at?: string;
}

export const BroadcastManager: React.FC = () => {
  const { profile, isSuperAdmin } = useAdminAuth();

  const [items, setItems] = useState<BroadcastRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<'all' | 'pending' | 'approved' | 'offer' | 'post'>('all');
  const [search, setSearch] = useState('');

  // Create Modal State
  const [showModal, setShowModal] = useState(false);
  const [itemType, setItemType] = useState<'post' | 'offer' | 'advisory'>('offer');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [discountPercent, setDiscountPercent] = useState<number | ''>(20);
  const [discountCode, setDiscountCode] = useState('');
  const [tags, setTags] = useState('fertilizer, discount, sowing');
  const [validUntil, setValidUntil] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Reject Modal State
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');

  const fetchBroadcasts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/broadcasts');
      if (!res.ok) throw new Error('Failed to load broadcasts and offers');
      const data = await res.json();
      setItems(data);
    } catch (err: any) {
      setError(err.message || 'Error fetching data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBroadcasts();

    const timer = setInterval(() => {
      fetchBroadcasts();
    }, 12000);

    const handleFocus = () => {
      fetchBroadcasts();
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  const handleCreate = async (submitForApproval: boolean) => {
    if (!title || !content) {
      setError('Please provide both title and content.');
      return;
    }
    setSubmitting(true);
    setError(null);

    const tagsList = tags.split(',').map(t => t.trim()).filter(Boolean);

    try {
      const res = await adminFetch('/api/admin/broadcasts', {
        method: 'POST',
        body: JSON.stringify({
          item_type: itemType,
          title: title.trim(),
          content: content.trim(),
          discount_percent: itemType === 'offer' && discountPercent !== '' ? Number(discountPercent) : null,
          discount_code: itemType === 'offer' && discountCode.trim() ? discountCode.trim().toUpperCase() : null,
          tags: tagsList,
          valid_until: validUntil ? new Date(validUntil).toISOString() : null,
          submit_for_approval: submitForApproval
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to create broadcast item');
      }

      setSuccessMsg(data.message || 'Item created successfully!');
      setShowModal(false);
      setTitle('');
      setContent('');
      setDiscountCode('');
      await fetchBroadcasts();
    } catch (err: any) {
      setError(err.message || 'Failed to create post');
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (id: string, itemTitle: string) => {
    if (!isSuperAdmin) {
      setError('Executive Decision: Only Head Super Admin (vvivekshastrym@gmail.com) can approve posts and offers.');
      return;
    }
    try {
      const res = await adminFetch(`/api/admin/broadcasts/${id}/approve`, {
        method: 'POST'
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Approval failed');
      }
      setSuccessMsg(`Approved "${itemTitle}"! It is now live in the Farmer App.`);
      await fetchBroadcasts();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRejectConfirm = async () => {
    if (!rejectingId || !rejectNotes.trim()) return;
    try {
      const res = await adminFetch(`/api/admin/broadcasts/${rejectingId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ rejection_notes: rejectNotes.trim() })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Rejection failed');
      }
      setSuccessMsg('Post rejected and returned to author with guidance notes.');
      setRejectingId(null);
      setRejectNotes('');
      await fetchBroadcasts();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSubmitDraft = async (id: string, itemTitle: string) => {
    try {
      const res = await adminFetch(`/api/admin/broadcasts/${id}/submit`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Submission failed');
      setSuccessMsg(`"${itemTitle}" submitted for Head Super Admin approval!`);
      await fetchBroadcasts();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this broadcast post?')) return;
    try {
      const res = await adminFetch(`/api/admin/broadcasts/${id}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Deletion failed');
      setSuccessMsg('Post deleted successfully.');
      await fetchBroadcasts();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const pendingCount = items.filter(i => i.status === 'pending_approval').length;
  const approvedCount = items.filter(i => i.status === 'approved').length;

  const filteredItems = items.filter(it => {
    const matchesFilter =
      activeFilter === 'all' ? true :
      activeFilter === 'pending' ? it.status === 'pending_approval' :
      activeFilter === 'approved' ? it.status === 'approved' :
      activeFilter === 'offer' ? it.item_type === 'offer' :
      activeFilter === 'post' ? it.item_type !== 'offer' : true;

    const s = search.toLowerCase();
    const matchesSearch =
      it.title.toLowerCase().includes(s) ||
      it.content.toLowerCase().includes(s) ||
      (it.discount_code && it.discount_code.toLowerCase().includes(s)) ||
      (it.author_name && it.author_name.toLowerCase().includes(s));

    return matchesFilter && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Posts & Promotional Offers</h1>
          <p className="text-sm text-[#4B5563]">
            Workers draft updates & discount offers. Head Super Admin approves them before publishing to farmers.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchBroadcasts}
            className="p-2.5 rounded-xl bg-white border border-[#E5DFD3] text-[#374151] hover:bg-[#F9F7F1] cursor-pointer"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#1B4332] hover:bg-[#2D6A4F] text-white text-sm font-semibold shadow-xs transition cursor-pointer"
          >
            <Plus size={16} />
            Create Post or Offer
          </button>
        </div>
      </div>

      {/* Authority Banner */}
      <div className="p-4 rounded-xl bg-[#E8F5E9] border border-[#C8E6C9] flex items-center justify-between gap-3 text-xs text-[#1B4332]">
        <div className="flex items-center gap-2.5">
          <Sparkles size={18} className="text-[#2D6A4F] shrink-0" />
          <div>
            <span className="font-bold">Super Admin Review Gate:</span> Normal workers can draft and submit offers. Only Head Super Admin (Vivek Shastry) can approve and make them live for farmers.
          </div>
        </div>
        <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#2D6A4F] text-white">
          {isSuperAdmin ? 'Executive Approver Mode' : 'Worker Drafting Mode'}
        </span>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-bold text-emerald-900 cursor-pointer">Dismiss</button>
        </div>
      )}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold text-red-900 cursor-pointer">Dismiss</button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280]">Total Items</div>
          <div className="text-2xl font-bold font-display text-[#1B4332] mt-1">{items.length}</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="text-xs font-semibold text-emerald-700">Live (Approved)</div>
          <div className="text-2xl font-bold font-display text-emerald-700 mt-1">{approvedCount}</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="text-xs font-semibold text-amber-700">Awaiting Approval</div>
          <div className="text-2xl font-bold font-display text-amber-700 mt-1">{pendingCount}</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280]">Promotional Offers</div>
          <div className="text-2xl font-bold font-display text-[#2D6A4F] mt-1">
            {items.filter(i => i.item_type === 'offer').length}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex bg-[#EFECE6] p-1 rounded-xl text-xs font-semibold">
          {[
            { id: 'all', label: 'All Items' },
            { id: 'pending', label: `Pending Approval (${pendingCount})` },
            { id: 'approved', label: `Live / Approved (${approvedCount})` },
            { id: 'offer', label: 'Promotional Offers' },
            { id: 'post', label: 'General Posts' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setActiveFilter(f.id as any)}
              className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${
                activeFilter === f.id ? 'bg-white text-[#1B4332] shadow-xs' : 'text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by title, coupon, author..."
            className="pl-9 pr-4 py-2 rounded-xl border border-[#E5DFD3] bg-white text-xs text-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] w-full sm:w-64"
          />
        </div>
      </div>

      {/* Broadcast Cards Grid */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-[#E5DFD3] p-12 text-center text-sm text-[#6B7280]">
          Loading posts and offers...
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="bg-white rounded-2xl border border-[#E5DFD3] p-12 text-center">
          <Megaphone size={40} className="mx-auto text-[#9CA3AF] mb-3" />
          <h3 className="font-display text-base font-bold text-[#1B4332]">No Broadcasts Found</h3>
          <p className="text-xs text-[#6B7280] mt-1 max-w-sm mx-auto">
            Create an announcement, pest advisory, or promotional discount coupon for registered farmers.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredItems.map(item => {
            const isOffer = item.item_type === 'offer';
            return (
              <div
                key={item.id}
                className={`bg-white rounded-2xl border p-5 shadow-xs relative transition flex flex-col justify-between ${
                  item.status === 'approved' ? 'border-emerald-300 ring-1 ring-emerald-50' :
                  item.status === 'pending_approval' ? 'border-amber-300 bg-amber-50/20' :
                  item.status === 'rejected' ? 'border-red-200' : 'border-[#E5DFD3]'
                }`}
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                        isOffer ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                      }`}>
                        {item.item_type}
                      </span>
                      {isOffer && item.discount_percent && (
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          {item.discount_percent}% OFF
                        </span>
                      )}
                    </div>

                    {/* Status Badge */}
                    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      item.status === 'approved' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                      item.status === 'pending_approval' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                      item.status === 'rejected' ? 'bg-red-50 text-red-700 border border-red-200' :
                      'bg-gray-100 text-gray-700 border border-gray-200'
                    }`}>
                      {item.status === 'approved' && <CheckCircle2 size={12} />}
                      {item.status === 'pending_approval' && <Clock size={12} />}
                      {item.status === 'rejected' && <XCircle size={12} />}
                      <span className="capitalize">{item.status.replace('_', ' ')}</span>
                    </span>
                  </div>

                  {/* Title & Content */}
                  <h3 className="font-bold text-base text-[#111827] mb-1">{item.title}</h3>
                  <p className="text-xs text-[#4B5563] leading-relaxed mb-3 line-clamp-3">{item.content}</p>

                  {/* Coupon Code Banner for Offers */}
                  {isOffer && item.discount_code && (
                    <div className="mb-3 py-1.5 px-3 rounded-lg bg-[#FAF8F5] border border-dashed border-[#2D6A4F]/40 flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-[#2D6A4F]">PROMO CODE:</span>
                      <span className="font-mono font-bold text-xs text-[#1B4332] tracking-wider">{item.discount_code}</span>
                    </div>
                  )}

                  {/* Tags */}
                  {item.tags && item.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {item.tags.map((t, idx) => (
                        <span key={idx} className="text-[10px] px-2 py-0.5 rounded bg-gray-100 text-[#4B5563]">
                          #{t}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Rejection Notes if any */}
                  {item.status === 'rejected' && item.super_admin_notes && (
                    <div className="mb-3 p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-800 text-xs">
                      <div className="font-bold flex items-center gap-1 mb-0.5">
                        <AlertTriangle size={12} />
                        Super Admin Feedback:
                      </div>
                      <p className="text-[11px]">{item.super_admin_notes}</p>
                    </div>
                  )}
                </div>

                {/* Footer and Actions */}
                <div className="pt-3 border-t border-[#F3EFE6] mt-2">
                  <div className="flex items-center justify-between text-[11px] text-[#6B7280] mb-3">
                    <div>Author: <span className="font-medium text-[#111827]">{item.author_name || 'Worker'}</span></div>
                    {item.valid_until && (
                      <div className="flex items-center gap-1">
                        <Calendar size={11} />
                        Expires: {new Date(item.valid_until).toLocaleDateString()}
                      </div>
                    )}
                  </div>

                  {/* Super Admin / Worker Action Buttons */}
                  <div className="flex items-center justify-between gap-2">
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 transition cursor-pointer"
                      title="Delete post"
                    >
                      <Trash2 size={15} />
                    </button>

                    {item.status === 'pending_approval' && (
                      isSuperAdmin ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              setRejectingId(item.id);
                              setRejectNotes('');
                            }}
                            className="px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 text-xs font-semibold border border-red-200 transition cursor-pointer"
                          >
                            Reject
                          </button>
                          <button
                            onClick={() => handleApprove(item.id, item.title)}
                            className="px-3 py-1.5 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-xs font-semibold flex items-center gap-1 shadow-xs transition cursor-pointer"
                          >
                            <CheckCircle2 size={14} />
                            Approve & Go Live
                          </button>
                        </div>
                      ) : (
                        <div className="text-[11px] font-semibold text-amber-700 flex items-center gap-1">
                          <Clock size={12} />
                          Awaiting Super Admin Approval
                        </div>
                      )
                    )}

                    {item.status === 'draft' && (
                      <button
                        onClick={() => handleSubmitDraft(item.id, item.title)}
                        className="px-3 py-1.5 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-xs font-semibold flex items-center gap-1 shadow-xs transition cursor-pointer"
                      >
                        <Send size={13} />
                        Submit for Super Admin Approval
                      </button>
                    )}

                    {item.status === 'approved' && (
                      <span className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                        <Eye size={12} /> Live in Farmer App
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── CREATE POST / OFFER MODAL ───────────────────────── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-[#E5DFD3] max-h-[90vh] overflow-y-auto">
            <h3 className="font-display text-lg font-bold text-[#1B4332] mb-1">Create Broadcast or Offer</h3>
            <p className="text-xs text-[#6B7280] mb-4">
              Compose promotional offers, pest advisories, or general announcements for farmers.
            </p>

            {/* Type selector */}
            <div className="flex bg-[#EFECE6] p-1 rounded-xl mb-4 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setItemType('offer')}
                className={`flex-1 py-2 rounded-lg transition cursor-pointer ${
                  itemType === 'offer' ? 'bg-white text-[#1B4332] shadow-xs' : 'text-[#6B7280]'
                }`}
              >
                🏷️ Promotional Offer / Discount
              </button>
              <button
                type="button"
                onClick={() => setItemType('post')}
                className={`flex-1 py-2 rounded-lg transition cursor-pointer ${
                  itemType === 'post' ? 'bg-white text-[#1B4332] shadow-xs' : 'text-[#6B7280]'
                }`}
              >
                📢 Announcement / Post
              </button>
            </div>

            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-[#374151] mb-1">Headline / Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder={itemType === 'offer' ? 'e.g. Monsoon Fertilizer 25% Off Deal' : 'e.g. Locust Pest Warning for Karnataka'}
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#374151] mb-1">Detailed Description / Instructions</label>
                <textarea
                  value={content}
                  onChange={e => setContent(e.target.value)}
                  rows={4}
                  placeholder="Explain terms, benefits, treatment recommendations, or coupon redemption details..."
                  className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                  required
                />
              </div>

              {itemType === 'offer' && (
                <div className="grid grid-cols-2 gap-3 bg-[#FAF8F5] p-3 rounded-xl border border-[#E5DFD3]">
                  <div>
                    <label className="block text-xs font-semibold text-[#374151] mb-1">Discount %</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={discountPercent}
                      onChange={e => setDiscountPercent(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder="25"
                      className="w-full px-3 py-1.5 rounded-lg border border-[#D1D5DB] text-xs bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#374151] mb-1">Coupon Code</label>
                    <input
                      type="text"
                      value={discountCode}
                      onChange={e => setDiscountCode(e.target.value.toUpperCase())}
                      placeholder="MONSOON25"
                      className="w-full px-3 py-1.5 rounded-lg border border-[#D1D5DB] text-xs font-mono bg-white uppercase"
                    />
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">Tags (comma separated)</label>
                  <input
                    type="text"
                    value={tags}
                    onChange={e => setTags(e.target.value)}
                    placeholder="fertilizer, seeds, subsidy"
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs bg-[#FBFBFB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">Valid Until (Optional)</label>
                  <input
                    type="date"
                    value={validUntil}
                    onChange={e => setValidUntil(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs bg-[#FBFBFB]"
                  />
                </div>
              </div>

              {/* Approval Notice */}
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
                <Lock size={14} className="shrink-0 text-amber-600" />
                <span>
                  {isSuperAdmin
                    ? 'As Head Super Admin, you can publish this directly or save as draft.'
                    : 'Submitting will send this item to Head Super Admin (Vivek Shastry) for approval.'}
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#F3EFE6]">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-xl border border-[#D1D5DB] text-xs font-semibold text-[#374151] hover:bg-gray-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleCreate(false)}
                  className="px-4 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-xs font-semibold text-[#374151] cursor-pointer"
                >
                  Save as Draft
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => handleCreate(true)}
                  className="px-4 py-2 rounded-xl bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <Send size={13} />
                  {isSuperAdmin ? 'Publish Live Immediately' : 'Submit for Super Admin Approval'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── REJECT MODAL ────────────────────────────────────── */}
      {rejectingId && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-[#E5DFD3]">
            <h3 className="font-display text-base font-bold text-red-700 mb-1">Reject Post / Offer</h3>
            <p className="text-xs text-[#6B7280] mb-4">
              Explain why this item is rejected so the author can modify and re-submit.
            </p>
            <textarea
              rows={3}
              value={rejectNotes}
              onChange={e => setRejectNotes(e.target.value)}
              placeholder="e.g. Please verify fertilizer safety dosage guidelines before submitting..."
              className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs focus:ring-2 focus:ring-red-500 mb-4"
              required
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setRejectingId(null)}
                className="px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs font-semibold text-[#374151] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectConfirm}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-semibold cursor-pointer"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
