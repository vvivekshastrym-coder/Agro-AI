import React, { useEffect, useState } from 'react';
import {
  ShoppingBag,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Search,
  Filter,
  MapPin,
  Phone,
  FileCheck,
  CheckSquare,
  TrendingUp,
  PackageCheck
} from 'lucide-react';
import { adminFetch } from '../lib/api';

interface SellerApp {
  id: string;
  user_id: string;
  farm_name: string;
  contact_phone: string;
  state: string;
  district: string;
  village: string;
  service_pincodes: string[];
  fulfilment_modes: string[];
  status: string;
  proof_type: string;
  phone_verified: boolean;
  staff_call_completed: boolean;
  declaration_cultivates_produce: boolean;
  created_at?: string;
}

interface ListingQueueItem {
  id: string;
  title: string;
  description?: string;
  price_formatted: string;
  unit: string;
  stock_quantity: number;
  harvest_date: string;
  status: string;
  is_organic_claim: boolean;
  photos: string[];
  farm_name: string;
  village: string;
  district: string;
  created_at?: string;
}

interface MasterOrder {
  id: string;
  order_number: string;
  status: string;
  fulfilment_type: string;
  farm_name: string;
  customer_name: string;
  delivery_pincode: string;
  total_formatted: string;
  payment_status: string;
  created_at?: string;
}

interface WaitlistGroup {
  pincode: string;
  district: string;
  state: string;
  requests_count: number;
}

export const MartConsole: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'applications' | 'listings' | 'orders' | 'waitlist'>('applications');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [applications, setApplications] = useState<SellerApp[]>([]);
  const [appFilter, setAppFilter] = useState<string>('SUBMITTED');
  const [listings, setListings] = useState<ListingQueueItem[]>([]);
  const [orders, setOrders] = useState<MasterOrder[]>([]);
  const [waitlist, setWaitlist] = useState<WaitlistGroup[]>([]);

  // Action states
  const [staffCallMap, setStaffCallMap] = useState<Record<string, boolean>>({});
  const [reviewNotesMap, setReviewNotesMap] = useState<Record<string, string>>({});
  const [rejectReasonMap, setRejectReasonMap] = useState<Record<string, string>>({});
  const [processingId, setProcessingId] = useState<string | null>(null);

  const fetchApplications = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = appFilter === 'ALL' 
        ? '/api/admin/mart/applications' 
        : `/api/admin/mart/applications?status_filter=${encodeURIComponent(appFilter)}`;
      const res = await adminFetch(url);
      if (!res.ok) throw new Error('Failed to load seller applications queue');
      const data = await res.json();
      setApplications(data);
    } catch (e: any) {
      setError(e.message || 'Error fetching applications');
    } finally {
      setLoading(false);
    }
  };

  const fetchListingsQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/mart/listings/review-queue');
      if (!res.ok) throw new Error('Failed to load listings queue');
      const data = await res.json();
      setListings(data);
    } catch (e: any) {
      setError(e.message || 'Error fetching listings review queue');
    } finally {
      setLoading(false);
    }
  };

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/mart/orders');
      if (!res.ok) throw new Error('Failed to load orders ledger');
      const data = await res.json();
      setOrders(data);
    } catch (e: any) {
      setError(e.message || 'Error fetching orders ledger');
    } finally {
      setLoading(false);
    }
  };

  const fetchWaitlist = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/mart/waitlist');
      if (!res.ok) throw new Error('Failed to load waitlist summary');
      const data = await res.json();
      setWaitlist(data);
    } catch (e: any) {
      setError(e.message || 'Error fetching waitlist');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'applications') fetchApplications();
    else if (activeTab === 'listings') fetchListingsQueue();
    else if (activeTab === 'orders') fetchOrders();
    else if (activeTab === 'waitlist') fetchWaitlist();
  }, [activeTab, appFilter]);

  const handleReviewSeller = async (appId: string, decision: 'APPROVED' | 'REJECTED' | 'INFO_REQUIRED') => {
    setProcessingId(appId);
    setError(null);
    try {
      const notes = reviewNotesMap[appId] || '';
      const staffCall = staffCallMap[appId] !== false; // default true if not unchecked

      const res = await adminFetch(`/api/admin/mart/applications/${appId}/review`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          staff_call_completed: staffCall,
          review_notes: notes || `Staff decision: ${decision}`
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || 'Review action failed');
      }

      setSuccessMsg(`Seller application marked as ${decision}!`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchApplications();
    } catch (e: any) {
      setError(e.message || 'Action failed');
    } finally {
      setProcessingId(null);
    }
  };

  const handleReviewListing = async (listingId: string, decision: 'APPROVED' | 'REJECTED') => {
    setProcessingId(listingId);
    setError(null);
    try {
      const reason = rejectReasonMap[listingId] || '';
      if (decision === 'REJECTED' && !reason.trim()) {
        throw new Error('Please provide a rejection reason for the farmer.');
      }

      const res = await adminFetch(`/api/admin/mart/listings/${listingId}/review`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          rejection_reason: reason || null,
          confirm_organic_evidence: true
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || 'Listing review failed');
      }

      setSuccessMsg(`Listing ${decision === 'APPROVED' ? 'approved and made live!' : 'rejected.'}`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchListingsQueue();
    } catch (e: any) {
      setError(e.message || 'Action failed');
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* ── HEADER ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-[#2D6A4F]/10 text-[#2D6A4F]">
              <ShoppingBag size={22} />
            </span>
            <h1 className="text-2xl font-bold font-display text-[#1B4332]">Agro AI Mart</h1>
          </div>
          <p className="text-sm text-[#40916C] mt-1">
            Farm-to-Consumer Produce Marketplace · Direct Farmer Settlement · Zero Middlemen
          </p>
        </div>

        <button
          onClick={() => {
            if (activeTab === 'applications') fetchApplications();
            else if (activeTab === 'listings') fetchListingsQueue();
            else if (activeTab === 'orders') fetchOrders();
            else if (activeTab === 'waitlist') fetchWaitlist();
          }}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-[#D8D2C2] rounded-xl text-sm font-semibold text-[#1B4332] hover:bg-[#FAF8F5] transition shadow-xs"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* ── FEEDBACK ALERTS ── */}
      {error && (
        <div className="p-4 bg-[#B91C1C]/10 border border-[#B91C1C]/30 rounded-xl text-sm text-[#B91C1C] flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-[#2D6A4F]/10 border border-[#2D6A4F]/30 rounded-xl text-sm text-[#2D6A4F] flex items-center gap-2 font-medium">
          <CheckCircle size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* ── SUBTABS NAVIGATION ── */}
      <div className="flex border-b border-[#D8D2C2] gap-1 sm:gap-4 overflow-x-auto">
        <button
          onClick={() => setActiveTab('applications')}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'applications'
              ? 'border-[#2D6A4F] text-[#2D6A4F]'
              : 'border-transparent text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <FileCheck size={16} />
          Seller Applications
        </button>

        <button
          onClick={() => setActiveTab('listings')}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'listings'
              ? 'border-[#2D6A4F] text-[#2D6A4F]'
              : 'border-transparent text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <PackageCheck size={16} />
          Listings Queue
        </button>

        <button
          onClick={() => setActiveTab('orders')}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'orders'
              ? 'border-[#2D6A4F] text-[#2D6A4F]'
              : 'border-transparent text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <Clock size={16} />
          Live Orders Ledger
        </button>

        <button
          onClick={() => setActiveTab('waitlist')}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'waitlist'
              ? 'border-[#2D6A4F] text-[#2D6A4F]'
              : 'border-transparent text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <TrendingUp size={16} />
          Demand Waitlist Heatmap
        </button>
      </div>

      {/* ── TAB 1: SELLER APPLICATIONS QUEUE ── */}
      {activeTab === 'applications' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-[#4B5563]">
              Review land ownership and verify cultivation before farmers can sell to customers.
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#6B7280]">Status:</span>
              <select
                value={appFilter}
                onChange={e => setAppFilter(e.target.value)}
                className="text-xs font-semibold bg-white border border-[#D8D2C2] rounded-lg px-2.5 py-1.5 text-[#1F2937] outline-none"
              >
                <option value="SUBMITTED">Submitted (Pending Review)</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
                <option value="ALL">All Statuses</option>
              </select>
            </div>
          </div>

          {!applications.length && !loading ? (
            <div className="bg-white border border-[#D8D2C2] rounded-2xl p-10 text-center">
              <CheckCircle className="mx-auto text-[#2D6A4F] mb-3" size={32} />
              <h3 className="font-bold text-[#1F2937]">Application Queue Clean</h3>
              <p className="text-sm text-[#6B7280] mt-1">
                No farmer seller applications match status filter &ldquo;{appFilter}&rdquo;.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {applications.map(app => (
                <div key={app.id} className="bg-white border border-[#D8D2C2] rounded-2xl p-5 shadow-xs space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 border-b border-[#F3F4F6] pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-[#1F2937]">{app.farm_name}</h3>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                          app.status === 'APPROVED' ? 'bg-[#2D6A4F]/15 text-[#2D6A4F]' :
                          app.status === 'REJECTED' ? 'bg-[#B91C1C]/15 text-[#B91C1C]' :
                          'bg-[#B26E28]/15 text-[#B26E28]'
                        }`}>
                          {app.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-[#6B7280] mt-1">
                        <span className="flex items-center gap-1">
                          <MapPin size={13} />
                          {app.village}, {app.district}, {app.state}
                        </span>
                        <span className="flex items-center gap-1">
                          <Phone size={13} />
                          {app.contact_phone}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs text-[#9CA3AF]">
                      Submitted: {app.created_at ? new Date(app.created_at).toLocaleDateString('en-IN') : 'Recent'}
                    </div>
                  </div>

                  {/* Verification Criteria */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs bg-[#F9FAFB] p-3 rounded-xl border border-[#E5E7EB]">
                    <div>
                      <span className="text-[#6B7280] block font-medium">Service PIN Codes:</span>
                      <span className="font-semibold text-[#1F2937]">
                        {app.service_pincodes?.length ? app.service_pincodes.join(', ') : 'None specified'}
                      </span>
                    </div>
                    <div>
                      <span className="text-[#6B7280] block font-medium">Land Document Type:</span>
                      <span className="font-semibold text-[#1F2937]">{app.proof_type || 'Self-declaration'}</span>
                    </div>
                    <div>
                      <span className="text-[#6B7280] block font-medium">Cultivation Declaration:</span>
                      <span className="font-semibold text-[#2D6A4F]">
                        {app.declaration_cultivates_produce ? '✓ Signed & Declared' : '✗ Unsigned'}
                      </span>
                    </div>
                  </div>

                  {/* Review Actions if Pending */}
                  {app.status === 'SUBMITTED' && (
                    <div className="space-y-3 pt-2">
                      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                        <label className="flex items-center gap-2 text-xs font-semibold text-[#1F2937] cursor-pointer">
                          <input
                            type="checkbox"
                            checked={staffCallMap[app.id] ?? true}
                            onChange={e => setStaffCallMap({ ...staffCallMap, [app.id]: e.target.checked })}
                            className="rounded text-[#2D6A4F]"
                          />
                          <span>Confirm agronomist phone call conducted with farmer</span>
                        </label>

                        <input
                          type="text"
                          placeholder="Review notes / verification remarks..."
                          value={reviewNotesMap[app.id] || ''}
                          onChange={e => setReviewNotesMap({ ...reviewNotesMap, [app.id]: e.target.value })}
                          className="flex-1 text-xs px-3 py-1.5 border border-[#D8D2C2] rounded-lg outline-none"
                        />
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleReviewSeller(app.id, 'APPROVED')}
                          disabled={processingId === app.id}
                          className="px-4 py-2 bg-[#2D6A4F] text-white rounded-xl text-xs font-bold hover:bg-[#1B4332] transition"
                        >
                          ✓ Approve Seller
                        </button>
                        <button
                          onClick={() => handleReviewSeller(app.id, 'REJECTED')}
                          disabled={processingId === app.id}
                          className="px-4 py-2 bg-white border border-[#B91C1C] text-[#B91C1C] rounded-xl text-xs font-bold hover:bg-[#B91C1C]/10 transition"
                        >
                          ✕ Reject
                        </button>
                        <button
                          onClick={() => handleReviewSeller(app.id, 'INFO_REQUIRED')}
                          disabled={processingId === app.id}
                          className="px-4 py-2 bg-white border border-[#D8D2C2] text-[#4B5563] rounded-xl text-xs font-medium hover:bg-gray-50 transition"
                        >
                          Request More Proof
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: PRODUCE LISTINGS QUEUE ── */}
      {activeTab === 'listings' && (
        <div className="space-y-4">
          <div className="text-sm font-medium text-[#4B5563]">
            Verify produce quality, harvest date, and organic claims before items appear in the customer marketplace.
          </div>

          {!listings.length && !loading ? (
            <div className="bg-white border border-[#D8D2C2] rounded-2xl p-10 text-center">
              <CheckCircle className="mx-auto text-[#2D6A4F] mb-3" size={32} />
              <h3 className="font-bold text-[#1F2937]">Listings Queue Empty</h3>
              <p className="text-sm text-[#6B7280] mt-1">All farmer produce listings have been reviewed and approved.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {listings.map(l => (
                <div key={l.id} className="bg-white border border-[#D8D2C2] rounded-2xl p-4 shadow-xs space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-bold text-sm text-[#1F2937]">{l.title}</h4>
                      <div className="text-xs text-[#6B7280]">
                        🏡 {l.farm_name} ({l.village}, {l.district})
                      </div>
                    </div>
                    <span className="text-sm font-black text-[#2D6A4F]">
                      {l.price_formatted} <span className="text-xs font-normal text-[#6B7280]">/ {l.unit}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-[#4B5563] bg-[#F9FAFB] p-2.5 rounded-xl border border-[#E5E7EB]">
                    <div>Stock: <strong>{l.stock_quantity} {l.unit}</strong></div>
                    <div>•</div>
                    <div>Harvest Date: <strong>{l.harvest_date}</strong></div>
                    {l.is_organic_claim && (
                      <>
                        <div>•</div>
                        <span className="text-[#2D6A4F] font-bold">🌿 Organic Claim</span>
                      </>
                    )}
                  </div>

                  <div className="space-y-2 pt-1">
                    <input
                      type="text"
                      placeholder="Rejection reason (required if rejecting)..."
                      value={rejectReasonMap[l.id] || ''}
                      onChange={e => setRejectReasonMap({ ...rejectReasonMap, [l.id]: e.target.value })}
                      className="w-full text-xs px-3 py-1.5 border border-[#D8D2C2] rounded-lg outline-none"
                    />

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReviewListing(l.id, 'APPROVED')}
                        disabled={processingId === l.id}
                        className="flex-1 py-1.5 bg-[#2D6A4F] text-white rounded-xl text-xs font-bold hover:bg-[#1B4332] transition"
                      >
                        ✓ Approve Produce
                      </button>
                      <button
                        onClick={() => handleReviewListing(l.id, 'REJECTED')}
                        disabled={processingId === l.id}
                        className="py-1.5 px-3 bg-white border border-[#B91C1C] text-[#B91C1C] rounded-xl text-xs font-bold hover:bg-[#B91C1C]/10 transition"
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: LIVE ORDERS LEDGER ── */}
      {activeTab === 'orders' && (
        <div className="space-y-4">
          <div className="text-sm font-medium text-[#4B5563]">
            Master order log across all farms. Direct farmer settlement (Pay on Delivery).
          </div>

          {!orders.length && !loading ? (
            <div className="bg-white border border-[#D8D2C2] rounded-2xl p-10 text-center">
              <ShoppingBag className="mx-auto text-[#6B7280] mb-3" size={32} />
              <h3 className="font-bold text-[#1F2937]">No Orders Recorded</h3>
              <p className="text-sm text-[#6B7280] mt-1">Orders placed by customers will be visible here in real time.</p>
            </div>
          ) : (
            <div className="bg-white border border-[#D8D2C2] rounded-2xl overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAF8F5] border-b border-[#D8D2C2] text-[#6B7280] font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="p-3">Order #</th>
                    <th className="p-3">Farm</th>
                    <th className="p-3">Customer</th>
                    <th className="p-3">PIN</th>
                    <th className="p-3">Mode</th>
                    <th className="p-3">Total</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F3F4F6]">
                  {orders.map(o => (
                    <tr key={o.id} className="hover:bg-gray-50/60 transition">
                      <td className="p-3 font-bold text-[#1F2937]">#{o.order_number}</td>
                      <td className="p-3 font-medium text-[#1F2937]">{o.farm_name}</td>
                      <td className="p-3 text-[#4B5563]">{o.customer_name}</td>
                      <td className="p-3 font-mono text-[#6B7280]">{o.delivery_pincode}</td>
                      <td className="p-3 text-[#4B5563]">{o.fulfilment_type}</td>
                      <td className="p-3 font-bold text-[#2D6A4F]">{o.total_formatted}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                          o.status === 'COMPLETED' ? 'bg-[#2D6A4F]/15 text-[#2D6A4F]' :
                          o.status === 'CANCELLED' ? 'bg-[#B91C1C]/15 text-[#B91C1C]' :
                          'bg-[#B26E28]/15 text-[#B26E28]'
                        }`}>
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 4: DEMAND WAITLIST HEATMAP ── */}
      {activeTab === 'waitlist' && (
        <div className="space-y-4">
          <div className="text-sm font-medium text-[#4B5563]">
            Truthful demand collection from customers searching in unserved PIN codes. Guides targeted farmer onboarding.
          </div>

          {!waitlist.length && !loading ? (
            <div className="bg-white border border-[#D8D2C2] rounded-2xl p-10 text-center">
              <TrendingUp className="mx-auto text-[#6B7280] mb-3" size={32} />
              <h3 className="font-bold text-[#1F2937]">Waitlist Empty</h3>
              <p className="text-sm text-[#6B7280] mt-1">Customer &ldquo;Notify Me&rdquo; signups will be aggregated here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {waitlist.map(w => (
                <div key={w.pincode} className="bg-white border border-[#D8D2C2] rounded-2xl p-4 shadow-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono font-black text-lg text-[#1F2937]">{w.pincode}</span>
                    <span className="px-2.5 py-1 rounded-full bg-[#2D6A4F]/15 text-[#2D6A4F] font-black text-xs">
                      {w.requests_count} customer{w.requests_count > 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="text-xs text-[#6B7280]">
                    {w.district}, {w.state}
                  </div>
                  <div className="mt-3 pt-2 border-t border-[#F3F4F6] text-[11px] text-[#40916C] font-semibold">
                    Target priority: {w.requests_count >= 5 ? '🔥 High Demand' : 'Normal'}
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
