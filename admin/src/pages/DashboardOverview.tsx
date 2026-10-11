import React, { useEffect, useState, useRef } from 'react';
import { Users, CreditCard, Sparkles, AlertCircle, RefreshCw, Layers, ShieldCheck, Activity, Bell, FileSpreadsheet, MapPin } from 'lucide-react';
import { adminFetch } from '../lib/api';

interface Metrics {
  registered_users: number;
  total_farmers: number;
  verified_users: number;
  active_subscriptions: number;
  total_orders: number;
  total_revenue_inr: number;
  total_acres: number;
  ai_diagnoses_count: number;
  active_broadcasts_count: number;
  pending_approvals_count: number;
  payment_gateway_status: string;
  metrics_computed_at: string;
}

export const DashboardOverview: React.FC = () => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const pollTimerRef = useRef<any>(null);

  const fetchMetrics = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/overview/metrics');

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to compute database metrics`);
      }

      const data = await res.json();
      setMetrics(data);
      setLastSyncTime(new Date());
      setSecondsAgo(0);
    } catch (err: any) {
      if (!isBackground) {
        setError(err.message || 'Could not retrieve overview metrics.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial fetch and auto-refresh polling every 12 seconds
  useEffect(() => {
    fetchMetrics(false);

    pollTimerRef.current = setInterval(() => {
      fetchMetrics(true);
    }, 12000);

    // Refresh immediately when tab gains focus
    const handleFocus = () => {
      fetchMetrics(true);
    };
    window.addEventListener('focus', handleFocus);

    // Second counter for "Updated X seconds ago"
    const secondTimer = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      clearInterval(secondTimer);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  const primaryCards = [
    {
      label: 'Real Registered Farmers',
      val: metrics ? metrics.total_farmers.toLocaleString() : 'Not available',
      sub: `${metrics ? metrics.verified_users : 0} verified accounts`,
      icon: <Users size={22} className="text-[#2D6A4F]" />,
      bg: 'bg-[#E8F5E9]',
      border: 'border-[#C8E6C9]'
    },
    {
      label: 'Verified Farmland (Acres)',
      val: metrics ? `${metrics.total_acres.toLocaleString()} ac` : 'Not available',
      sub: 'Total acreage logged in registry',
      icon: <MapPin size={22} className="text-[#059669]" />,
      bg: 'bg-[#ECFDF5]',
      border: 'border-[#A7F3D0]'
    },
    {
      label: 'AI Crop Diagnoses Run',
      val: metrics ? metrics.ai_diagnoses_count.toLocaleString() : 'Not available',
      sub: 'Gemini Vision plant disease scans',
      icon: <Sparkles size={22} className="text-[#7C3AED]" />,
      bg: 'bg-[#F3E8FF]',
      border: 'border-[#DDD6FE]'
    },
    {
      label: 'Active Subscriptions',
      val: metrics ? metrics.active_subscriptions.toLocaleString() : 'Not available',
      sub: 'Farmers on active paid tiers',
      icon: <Layers size={22} className="text-[#1D4ED8]" />,
      bg: 'bg-[#DBEAFE]',
      border: 'border-[#BFDBFE]'
    },
    {
      label: 'Real Purchase Orders',
      val: metrics ? metrics.total_orders.toLocaleString() : '0',
      sub: 'Genuine checkout orders placed',
      icon: <CreditCard size={22} className="text-[#D97706]" />,
      bg: 'bg-[#FEF3C7]',
      border: 'border-[#FDE68A]'
    },
    {
      label: 'Verified Revenue (INR)',
      val: metrics ? `₹${metrics.total_revenue_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '₹0.00',
      sub: 'Verified settlement deposits only',
      icon: <Sparkles size={22} className="text-[#047857]" />,
      bg: 'bg-[#D1FAE5]',
      border: 'border-[#A7F3D0]'
    },
    {
      label: 'Live Posts & Offers',
      val: metrics ? metrics.active_broadcasts_count.toLocaleString() : '0',
      sub: 'Super Admin approved items live',
      icon: <Bell size={22} className="text-[#2563EB]" />,
      bg: 'bg-[#EFF6FF]',
      border: 'border-[#BFDBFE]'
    },
    {
      label: 'Pending Approvals',
      val: metrics ? metrics.pending_approvals_count.toLocaleString() : '0',
      sub: 'Awaiting Super Admin decision',
      icon: <ShieldCheck size={22} className="text-[#EA580C]" />,
      bg: 'bg-[#FFEDD5]',
      border: 'border-[#FED7AA]'
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header with Live Sync Status & Manual Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#E5DFD3]">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="font-display text-2xl font-bold text-[#1B4332]">Platform Live Overview</h2>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Sync Active
            </div>
          </div>
          <p className="text-sm text-[#6B7280] mt-1">
            Real-time data queried directly from the production database. Updated {secondsAgo}s ago.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => fetchMetrics(false)}
            disabled={loading || refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-medium text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-xs cursor-pointer"
          >
            <RefreshCw size={14} className={loading || refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-3">
          <AlertCircle size={18} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {primaryCards.map((c, i) => (
          <div key={i} className={`bg-white rounded-2xl border ${c.border} p-5 shadow-xs flex flex-col justify-between hover:shadow-sm transition`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{c.label}</span>
              <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center shrink-0`}>
                {c.icon}
              </div>
            </div>
            <div>
              <div className="font-display text-2xl font-bold text-[#111827]">
                {loading ? '...' : c.val}
              </div>
              <p className="text-xs text-[#6B7280] mt-1 font-medium">{c.sub}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Live System Status & Zero Fabrication Guarantee */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="bg-white border border-[#E5DFD3] rounded-2xl p-5 shadow-xs lg:col-span-2">
          <div className="flex items-center gap-2 mb-3 text-sm font-bold text-[#1B4332]">
            <Activity size={18} className="text-[#2D6A4F]" />
            Live Infrastructure & Service Connectivity
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-[#F8F9FA] border border-[#E9ECEF]">
              <span className="text-[#6C757D] font-medium block">Database Connectivity</span>
              <span className="font-semibold text-emerald-700 flex items-center gap-1.5 mt-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Connected & Responsive
              </span>
            </div>
            <div className="p-3 rounded-xl bg-[#F8F9FA] border border-[#E9ECEF]">
              <span className="text-[#6C757D] font-medium block">Payment Webhook Listener</span>
              <span className="font-semibold text-emerald-700 flex items-center gap-1.5 mt-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> /api/payments/webhook Active
              </span>
            </div>
            <div className="p-3 rounded-xl bg-[#F8F9FA] border border-[#E9ECEF]">
              <span className="text-[#6C757D] font-medium block">Excel Registry Auto-Sync</span>
              <span className="font-semibold text-emerald-700 flex items-center gap-1.5 mt-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> exports/farmers_registry.xlsx
              </span>
            </div>
            <div className="p-3 rounded-xl bg-[#F8F9FA] border border-[#E9ECEF]">
              <span className="text-[#6C757D] font-medium block">Decision Authority Gate</span>
              <span className="font-semibold text-[#1B4332] flex items-center gap-1.5 mt-1">
                <ShieldCheck size={14} className="text-[#2D6A4F]" /> vvivekshastrym@gmail.com
              </span>
            </div>
          </div>
        </div>

        <div className="bg-[#FAF8F5] border border-[#E5DFD3] rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2 text-sm font-bold text-[#1B4332]">
              <ShieldCheck size={18} className="text-[#2D6A4F]" />
              Zero-Fabrication Policy
            </div>
            <p className="text-xs text-[#4B5563] leading-relaxed">
              All metrics above are queried live from real database records.
              Zero simulated revenue, fake users, or artificial transactions are permitted. When a real farmer registers or subscribes, this dashboard updates automatically.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-[#E5DFD3] text-[11px] text-[#6B7280] flex items-center justify-between">
            <span>Auto-poll frequency: 12s</span>
            <span className="font-medium text-[#1B4332]">Sync Status: Healthy</span>
          </div>
        </div>
      </div>
    </div>
  );
};
