import React, { useEffect, useState, useRef } from 'react';
import {
  CreditCard, Search, RefreshCw, AlertTriangle, CheckCircle, Clock, XCircle,
  ShieldCheck, Radio, Phone, Mail, HelpCircle, UserCheck, MessageSquare, AlertOctagon, RotateCcw
} from 'lucide-react';
import { adminFetch } from '../lib/api';

interface PaymentOrderRecord {
  id: string;
  user_id: string;
  user_email?: string;
  user_name?: string;
  user_phone?: string;
  plan_version_id: string;
  plan_name?: string;
  amount_minor: number;
  amount_formatted: string;
  currency: string;
  provider: string;
  provider_order_id?: string;
  status: string;
  notes?: any;
  has_open_issue?: boolean;
  created_at?: string;
}

interface PaymentTransactionRecord {
  id: string;
  order_id: string;
  provider: string;
  provider_payment_id?: string;
  amount_minor: number;
  amount_formatted: string;
  currency: string;
  status: string;
  payment_method?: string;
  verified_at?: string;
  created_at?: string;
}

export const PaymentOrders: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'all_orders' | 'issues' | 'transactions'>('all_orders');
  const [orders, setOrders] = useState<PaymentOrderRecord[]>([]);
  const [transactions, setTransactions] = useState<PaymentTransactionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const pollTimerRef = useRef<any>(null);

  // Assistance Modal State
  const [assistOrder, setAssistOrder] = useState<PaymentOrderRecord | null>(null);
  const [staffNote, setStaffNote] = useState('');
  const [paymentRef, setPaymentRef] = useState('');
  const [assistActionLoading, setAssistActionLoading] = useState(false);
  const [assistSuccess, setAssistSuccess] = useState<string | null>(null);
  const [assistTab, setAssistTab] = useState<'activate' | 'note' | 'refund'>('activate');
  const [refundReason, setRefundReason] = useState('');

  const fetchData = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const [ordRes, txRes] = await Promise.all([
        adminFetch('/api/admin/payments/orders'),
        adminFetch('/api/admin/payments/transactions')
      ]);

      if (!ordRes.ok || !txRes.ok) {
        throw new Error('Failed to fetch payment records');
      }

      const ordData = await ordRes.json();
      const txData = await txRes.json();

      setOrders(ordData);
      setTransactions(txData);
      setSecondsAgo(0);

      // If assistance modal is open, refresh its data
      if (assistOrder) {
        const updated = ordData.find((o: PaymentOrderRecord) => o.id === assistOrder.id);
        if (updated) setAssistOrder(updated);
      }
    } catch (err: any) {
      if (!isBackground) {
        setError(err.message || 'Error loading payments data');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData(false);

    // Auto-poll every 12 seconds for live orders and issues
    pollTimerRef.current = setInterval(() => {
      fetchData(true);
    }, 12000);

    const handleFocus = () => {
      fetchData(true);
    };
    window.addEventListener('focus', handleFocus);

    const secondTimer = setInterval(() => {
      setSecondsAgo(prev => prev + 1);
    }, 1000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      clearInterval(secondTimer);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  const handleManualActivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assistOrder) return;
    if (!staffNote || staffNote.length < 5) {
      setError('Please provide staff justification notes (at least 5 characters).');
      return;
    }

    setAssistActionLoading(true);
    setAssistSuccess(null);
    try {
      const res = await adminFetch(`/api/admin/payments/orders/${assistOrder.id}/assist-activate`, {
        method: 'POST',
        body: JSON.stringify({
          staff_notes: staffNote.trim(),
          payment_reference: paymentRef.trim() || undefined
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to activate subscription');
      }

      setAssistSuccess('Farmer subscription activated successfully! Ledger updated.');
      setStaffNote('');
      setPaymentRef('');
      await fetchData(true);
    } catch (err: any) {
      setError(err.message || 'Failed to activate plan');
    } finally {
      setAssistActionLoading(false);
    }
  };

  const handleAddSupportNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assistOrder || !staffNote) return;

    setAssistActionLoading(true);
    setAssistSuccess(null);
    try {
      const res = await adminFetch(`/api/admin/payments/orders/${assistOrder.id}/add-notes`, {
        method: 'POST',
        body: JSON.stringify({ note: staffNote.trim() })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to add note');
      }

      setAssistSuccess('Internal support note saved to order history.');
      setStaffNote('');
      await fetchData(true);
    } catch (err: any) {
      setError(err.message || 'Failed to save note');
    } finally {
      setAssistActionLoading(false);
    }
  };

  const handleMarkRefunded = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assistOrder || !refundReason) return;

    setAssistActionLoading(true);
    setAssistSuccess(null);
    try {
      const res = await adminFetch(`/api/admin/payments/orders/${assistOrder.id}/mark-refunded`, {
        method: 'POST',
        body: JSON.stringify({ reason: refundReason.trim() })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to mark refunded');
      }

      setAssistSuccess('Order marked as refunded and subscription canceled.');
      setRefundReason('');
      await fetchData(true);
    } catch (err: any) {
      setError(err.message || 'Failed to record refund');
    } finally {
      setAssistActionLoading(false);
    }
  };

  const getStatusBadge = (status: string, hasIssue?: boolean) => {
    if (hasIssue || status === 'issue_reported') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 animate-pulse">
          <AlertOctagon size={12} /> ISSUE REPORTED
        </span>
      );
    }
    switch (status.toLowerCase()) {
      case 'paid':
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle size={12} /> PAID
          </span>
        );
      case 'pending':
      case 'created':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock size={12} /> PENDING
          </span>
        );
      case 'refunded':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <RotateCcw size={12} /> REFUNDED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
            <XCircle size={12} /> FAILED
          </span>
        );
    }
  };

  const issuesList = orders.filter(o => o.has_open_issue || o.status === 'issue_reported' || o.status === 'failed');

  const displayedOrders = orders.filter(o => {
    if (activeSubTab === 'issues') {
      return o.has_open_issue || o.status === 'issue_reported' || o.status === 'failed';
    }
    return true;
  }).filter(o => {
    const s = search.toLowerCase();
    return (
      o.user_email?.toLowerCase().includes(s) ||
      o.user_name?.toLowerCase().includes(s) ||
      o.user_phone?.toLowerCase().includes(s) ||
      o.provider_order_id?.toLowerCase().includes(s) ||
      o.plan_name?.toLowerCase().includes(s) ||
      o.id.toLowerCase().includes(s)
    );
  });

  const filteredTransactions = transactions.filter(t => {
    const s = search.toLowerCase();
    return (
      t.provider_payment_id?.toLowerCase().includes(s) ||
      t.order_id?.toLowerCase().includes(s) ||
      t.payment_method?.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Header with Live Indicator */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#E5DFD3]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-display font-bold text-[#1B4332]">Payment Orders & Staff Assistance</h1>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Ledger Stream
            </div>
          </div>
          <p className="text-sm text-[#4B5563] mt-1">
            Real customer transactions, live UPI webhooks, and farmer payment dispute resolution tools. Synced {secondsAgo}s ago.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => fetchData(false)}
            disabled={loading || refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-xs cursor-pointer"
          >
            <RefreshCw size={14} className={loading || refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-800 text-xs font-bold">Dismiss</button>
        </div>
      )}

      {/* Sub Tabs / Filters */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#E5DFD3] pb-2">
        <button
          onClick={() => setActiveSubTab('all_orders')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer ${
            activeSubTab === 'all_orders'
              ? 'bg-[#2D6A4F] text-white shadow-xs'
              : 'text-[#4B5563] hover:bg-[#F3EFE6]'
          }`}
        >
          All Payment Orders ({orders.length})
        </button>

        <button
          onClick={() => setActiveSubTab('issues')}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer ${
            activeSubTab === 'issues'
              ? 'bg-rose-700 text-white shadow-xs'
              : 'text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200'
          }`}
        >
          <AlertOctagon size={14} />
          Needs Staff Help ({issuesList.length})
        </button>

        <button
          onClick={() => setActiveSubTab('transactions')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold transition cursor-pointer ${
            activeSubTab === 'transactions'
              ? 'bg-[#2D6A4F] text-white shadow-xs'
              : 'text-[#4B5563] hover:bg-[#F3EFE6]'
          }`}
        >
          Settled Transactions ({transactions.length})
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={
            activeSubTab === 'transactions'
              ? 'Filter transactions by payment ID, order ID, payment method...'
              : 'Filter orders by farmer name, phone number, email, order ID...'
          }
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#E5DFD3] bg-white text-sm text-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20 focus:border-[#2D6A4F]"
        />
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          {activeSubTab !== 'transactions' ? (
            <table className="w-full text-left text-sm text-[#374151]">
              <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
                <tr>
                  <th className="px-6 py-4">Farmer Details</th>
                  <th className="px-6 py-4">Plan & Amount</th>
                  <th className="px-6 py-4">Status & Issues</th>
                  <th className="px-6 py-4">Order ID</th>
                  <th className="px-6 py-4">Created</th>
                  <th className="px-6 py-4 text-right">Staff Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5DFD3]">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                      Loading real payment orders...
                    </td>
                  </tr>
                ) : displayedOrders.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-16 text-center">
                      <div className="max-w-md mx-auto space-y-3">
                        <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-[#2D6A4F] flex items-center justify-center mx-auto border border-emerald-100">
                          {activeSubTab === 'issues' ? <CheckCircle size={24} /> : <Radio size={24} className="animate-pulse" />}
                        </div>
                        <h3 className="font-display text-base font-bold text-[#1B4332]">
                          {activeSubTab === 'issues' ? 'No Open Payment Issues' : 'No Live Payment Orders Yet'}
                        </h3>
                        <p className="text-xs text-[#6B7280] leading-relaxed">
                          {activeSubTab === 'issues'
                            ? 'All farmer payments are in good standing. No farmers have reported unresolved payment issues.'
                            : 'All simulated test orders have been purged. When a farmer initiates a plan upgrade via Razorpay or UPI, the order streams here live.'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  displayedOrders.map(order => (
                    <tr key={order.id} className="hover:bg-[#FAF8F5]/60 transition">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-[#1B4332]">{order.user_name || 'Farmer'}</div>
                        <div className="text-xs text-[#6B7280] flex items-center gap-2 mt-0.5">
                          {order.user_phone ? (
                            <a href={`tel:${order.user_phone}`} className="inline-flex items-center gap-1 text-[#2D6A4F] hover:underline">
                              <Phone size={10} /> {order.user_phone}
                            </a>
                          ) : null}
                          {order.user_email ? (
                            <a href={`mailto:${order.user_email}`} className="inline-flex items-center gap-1 text-[#6B7280] hover:text-[#1B4332]">
                              <Mail size={10} /> {order.user_email}
                            </a>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-semibold text-[#111827]">{order.amount_formatted}</div>
                        <div className="text-xs text-[#4B5563]">{order.plan_name || 'Subscription Plan'}</div>
                      </td>
                      <td className="px-6 py-4">
                        {getStatusBadge(order.status, order.has_open_issue)}
                        {order.notes?.staff_assistance && (
                          <div className="text-[10px] text-[#2D6A4F] font-semibold mt-1 flex items-center gap-1">
                            <ShieldCheck size={10} /> Staff Assisted
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-[#6B7280]">
                        <span title={order.id}>{order.provider_order_id || order.id.slice(0, 12)}</span>
                      </td>
                      <td className="px-6 py-4 text-xs text-[#6B7280]">
                        {order.created_at ? new Date(order.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => {
                            setAssistOrder(order);
                            setAssistSuccess(null);
                            setError(null);
                            setStaffNote('');
                            setPaymentRef('');
                          }}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-[#2D6A4F] text-xs font-semibold text-[#2D6A4F] hover:bg-[#2D6A4F] hover:text-white transition shadow-xs cursor-pointer"
                        >
                          <HelpCircle size={13} />
                          Help Farmer
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-left text-sm text-[#374151]">
              <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
                <tr>
                  <th className="px-6 py-4">Transaction ID</th>
                  <th className="px-6 py-4">Order ID</th>
                  <th className="px-6 py-4">Provider</th>
                  <th className="px-6 py-4">Method</th>
                  <th className="px-6 py-4">Amount</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Settled At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5DFD3]">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                      Loading settled transaction records...
                    </td>
                  </tr>
                ) : filteredTransactions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-16 text-center">
                      <div className="max-w-md mx-auto space-y-3">
                        <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-[#2D6A4F] flex items-center justify-center mx-auto border border-emerald-100">
                          <ShieldCheck size={24} />
                        </div>
                        <h3 className="font-display text-base font-bold text-[#1B4332]">Zero Fabricated Transactions</h3>
                        <p className="text-xs text-[#6B7280] leading-relaxed">
                          No mock settlements are generated. Only cryptographic signature-verified webhooks from Razorpay / UPI are recorded in this ledger.
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredTransactions.map(tx => (
                    <tr key={tx.id} className="hover:bg-[#FAF8F5]/60 transition">
                      <td className="px-6 py-4">
                        <span className="font-mono text-xs text-[#1B4332] font-semibold">
                          {tx.provider_payment_id || tx.id.slice(0, 12)}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-xs text-[#6B7280]">
                        {tx.order_id.slice(0, 8)}...
                      </td>
                      <td className="px-6 py-4 text-xs font-semibold text-[#1B4332] uppercase">
                        {tx.provider}
                      </td>
                      <td className="px-6 py-4 text-xs text-[#4B5563]">
                        {tx.payment_method || 'UPI / NetBanking'}
                      </td>
                      <td className="px-6 py-4 font-semibold text-[#047857]">
                        {tx.amount_formatted}
                      </td>
                      <td className="px-6 py-4">
                        {getStatusBadge(tx.status)}
                      </td>
                      <td className="px-6 py-4 text-right text-xs text-[#6B7280]">
                        {tx.verified_at ? new Date(tx.verified_at).toLocaleString() : (tx.created_at ? new Date(tx.created_at).toLocaleString() : '—')}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Staff Payment Assistance Modal */}
      {assistOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-3 border-b border-[#E5DFD3]">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xl font-display font-bold text-[#1B4332]">Staff Payment Assistance</h3>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Farmer Resolution Suite
                  </span>
                </div>
                <p className="text-xs text-[#6B7280] mt-0.5">
                  Resolve payment difficulties, verify bank debits, and assist farmers directly.
                </p>
              </div>
              <button
                onClick={() => setAssistOrder(null)}
                className="text-[#9CA3AF] hover:text-[#1F2937] text-lg font-bold p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {assistSuccess && (
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 font-medium">
                <CheckCircle size={16} className="shrink-0" />
                <span>{assistSuccess}</span>
              </div>
            )}

            {/* Farmer Overview Card */}
            <div className="p-4 rounded-xl bg-[#FAF8F5] border border-[#E5DFD3] space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="text-xs text-[#6B7280] uppercase tracking-wider font-semibold">Farmer Name</span>
                  <div className="text-base font-bold text-[#1B4332]">{assistOrder.user_name || 'Farmer'}</div>
                </div>
                <div className="flex items-center gap-2">
                  {assistOrder.user_phone && (
                    <a
                      href={`tel:${assistOrder.user_phone}`}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 transition"
                    >
                      <Phone size={12} /> Call Farmer ({assistOrder.user_phone})
                    </a>
                  )}
                  {assistOrder.user_email && (
                    <a
                      href={`mailto:${assistOrder.user_email}`}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-[#E5DFD3] text-[#1B4332] text-xs font-semibold hover:bg-[#F3EFE6] transition"
                    >
                      <Mail size={12} /> Email
                    </a>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-[#E5DFD3]/60 text-xs">
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Selected Plan</span>
                  <span className="font-semibold text-[#111827]">{assistOrder.plan_name || 'Plan'}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Order Amount</span>
                  <span className="font-semibold text-[#047857]">{assistOrder.amount_formatted}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Current Status</span>
                  <span className="font-semibold text-[#111827] uppercase">{assistOrder.status}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Order Reference</span>
                  <span className="font-mono text-[10px] text-[#6B7280] truncate block" title={assistOrder.id}>{assistOrder.id.slice(0, 10)}...</span>
                </div>
              </div>
            </div>

            {/* Farmer Reported Issue Alert (If Any) */}
            {assistOrder.notes?.reported_issues && assistOrder.notes.reported_issues.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-2">
                <div className="font-bold flex items-center gap-1.5 text-amber-800">
                  <AlertOctagon size={14} /> Reported Farmer Complaint
                </div>
                {assistOrder.notes.reported_issues.map((iss: any, idx: number) => (
                  <div key={idx} className="bg-white/80 p-2.5 rounded-lg border border-amber-200/60 space-y-1">
                    <div className="flex justify-between text-[11px] text-amber-700">
                      <span><strong>Type:</strong> {iss.issue_type}</span>
                      <span>{new Date(iss.reported_at).toLocaleString()}</span>
                    </div>
                    <div><strong>Description:</strong> {iss.description}</div>
                    {iss.upi_ref_or_utr && (
                      <div className="font-mono text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded text-[11px] inline-block">
                        <strong>Farmer Submitted UTR:</strong> {iss.upi_ref_or_utr}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Staff Action Tabs */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 border-b border-[#E5DFD3] pb-2 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setAssistTab('activate')}
                  className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${
                    assistTab === 'activate' ? 'bg-[#2D6A4F] text-white' : 'text-[#4B5563] hover:bg-[#F3EFE6]'
                  }`}
                >
                  ✓ Verify & Activate Subscription
                </button>
                <button
                  type="button"
                  onClick={() => setAssistTab('note')}
                  className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${
                    assistTab === 'note' ? 'bg-[#2D6A4F] text-white' : 'text-[#4B5563] hover:bg-[#F3EFE6]'
                  }`}
                >
                  + Add Support Note
                </button>
                <button
                  type="button"
                  onClick={() => setAssistTab('refund')}
                  className={`px-3 py-1.5 rounded-lg transition cursor-pointer ${
                    assistTab === 'refund' ? 'bg-purple-800 text-white' : 'text-[#4B5563] hover:bg-[#F3EFE6]'
                  }`}
                >
                  ↺ Record Refund
                </button>
              </div>

              {/* Form 1: Manual Activation */}
              {assistTab === 'activate' && (
                <form onSubmit={handleManualActivate} className="space-y-3">
                  <div className="p-3 bg-emerald-50/70 border border-emerald-100 rounded-xl text-xs text-emerald-900 leading-relaxed">
                    <strong>Use this if:</strong> The farmer paid via UPI / NetBanking and money was deducted from their bank, but network or gateway webhook delay prevented automatic activation.
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#1F2937] mb-1">
                      Bank Reference / UPI UTR Number (Optional)
                    </label>
                    <input
                      type="text"
                      value={paymentRef}
                      onChange={e => setPaymentRef(e.target.value)}
                      placeholder="e.g. 409823149812 or pay_..."
                      className="w-full px-3 py-2 rounded-xl border border-[#E5DFD3] text-xs font-mono text-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#1F2937] mb-1">
                      Staff Justification / Resolution Notes (Required)
                    </label>
                    <textarea
                      rows={2}
                      value={staffNote}
                      onChange={e => setStaffNote(e.target.value)}
                      placeholder="e.g. Verified UPI statement screenshot with farmer over call. Activated Kisan Plus."
                      className="w-full px-3 py-2 rounded-xl border border-[#E5DFD3] text-xs text-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20"
                      required
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setAssistOrder(null)}
                      className="px-4 py-2 rounded-xl border border-[#E5DFD3] text-xs font-medium text-[#4B5563] hover:bg-[#F3EFE6] cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={assistActionLoading}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#2D6A4F] text-white text-xs font-semibold hover:bg-[#1B4332] transition cursor-pointer shadow-xs disabled:opacity-50"
                    >
                      <UserCheck size={14} />
                      {assistActionLoading ? 'Activating...' : 'Confirm & Activate Membership'}
                    </button>
                  </div>
                </form>
              )}

              {/* Form 2: Add Note */}
              {assistTab === 'note' && (
                <form onSubmit={handleAddSupportNote} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#1F2937] mb-1">
                      Internal Support Log / Farmer Communication Note
                    </label>
                    <textarea
                      rows={3}
                      value={staffNote}
                      onChange={e => setStaffNote(e.target.value)}
                      placeholder="e.g. Spoke with farmer Suresh. Advised him that bank takes 24 hours to clear UPI charge."
                      className="w-full px-3 py-2 rounded-xl border border-[#E5DFD3] text-xs text-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20"
                      required
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setAssistOrder(null)}
                      className="px-4 py-2 rounded-xl border border-[#E5DFD3] text-xs font-medium text-[#4B5563] hover:bg-[#F3EFE6] cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={assistActionLoading}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] transition cursor-pointer shadow-xs disabled:opacity-50"
                    >
                      <MessageSquare size={14} />
                      {assistActionLoading ? 'Saving...' : 'Save Support Note'}
                    </button>
                  </div>
                </form>
              )}

              {/* Form 3: Refund */}
              {assistTab === 'refund' && (
                <form onSubmit={handleMarkRefunded} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#1F2937] mb-1">
                      Refund Reason / Gateway Refund ID
                    </label>
                    <textarea
                      rows={2}
                      value={refundReason}
                      onChange={e => setRefundReason(e.target.value)}
                      placeholder="e.g. Farmer requested cancellation within 24h. Refunded to original bank account."
                      className="w-full px-3 py-2 rounded-xl border border-[#E5DFD3] text-xs text-[#1F2937] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20"
                      required
                    />
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setAssistOrder(null)}
                      className="px-4 py-2 rounded-xl border border-[#E5DFD3] text-xs font-medium text-[#4B5563] hover:bg-[#F3EFE6] cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={assistActionLoading}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-700 text-white text-xs font-semibold hover:bg-purple-800 transition cursor-pointer shadow-xs disabled:opacity-50"
                    >
                      <RotateCcw size={14} />
                      {assistActionLoading ? 'Recording...' : 'Record Refund'}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Support Log History */}
            {assistOrder.notes?.staff_log && assistOrder.notes.staff_log.length > 0 && (
              <div className="pt-3 border-t border-[#E5DFD3] space-y-2">
                <span className="text-xs font-bold text-[#1F2937] block">Staff Communication History</span>
                <div className="space-y-1.5 max-h-36 overflow-y-auto">
                  {assistOrder.notes.staff_log.map((log: any, idx: number) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#FAF8F5] border border-[#E5DFD3] text-[11px] text-[#4B5563] flex justify-between">
                      <span>"{log.note}"</span>
                      <span className="text-[#9CA3AF] shrink-0 ml-2">{new Date(log.timestamp).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
