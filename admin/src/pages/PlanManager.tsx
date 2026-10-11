import React, { useEffect, useState } from 'react';
import { useAdminAuth } from '../context/AdminAuthContext';
import { adminFetch } from '../lib/api';
import {
  Plus,
  Layers,
  CheckCircle2,
  AlertCircle,
  PauseCircle,
  Archive,
  RefreshCw,
  Lock,
  Tag,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Shield
} from 'lucide-react';

interface Entitlement {
  enabled: boolean;
  usage_limit: number | null;
  limit_period: string;
}

interface PlanVersion {
  id: string;
  version: number;
  name: string;
  description?: string;
  price_minor: number;
  price_formatted: string;
  currency: string;
  billing_interval: string;
  trial_days: number;
  benefits: string[];
  is_published: boolean;
  available_from?: string;
  created_at: string;
  entitlements: Record<string, Entitlement>;
}

interface Plan {
  id: string;
  slug: string;
  status: 'draft' | 'published' | 'paused' | 'archived';
  created_at: string;
  versions: PlanVersion[];
}

export const PlanManager: React.FC = () => {
  const { isSuperAdmin } = useAdminAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals state
  const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
  const [newPlanSlug, setNewPlanSlug] = useState('');

  const [showCreateVersionModal, setShowCreateVersionModal] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  
  // Version form fields
  const [verName, setVerName] = useState('');
  const [verDesc, setVerDesc] = useState('');
  const [verPriceInr, setVerPriceInr] = useState(199);
  const [verInterval, setVerInterval] = useState('monthly');
  const [verTrialDays, setVerTrialDays] = useState(0);
  const [verBenefits, setVerBenefits] = useState('Unlimited Kisan GPT Crop Consultation\nInstant Leaf Disease Diagnosis with treatments\nLive Mandi APMC Price Trends');
  
  // Feature Entitlements
  const [entKisanChatLimit, setEntKisanChatLimit] = useState<number | ''>(''); // blank = unlimited
  const [entDiagnoseLimit, setEntDiagnoseLimit] = useState<number | ''>(50);
  const [entMandiLimit, setEntMandiLimit] = useState<number | ''>('');

  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);

  const fetchPlans = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/plans');
      if (!res.ok) throw new Error('Failed to load subscription plans');
      const data = await res.json();
      setPlans(data);
      if (data.length > 0 && !expandedPlanId) {
        setExpandedPlanId(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Error fetching plans');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPlanSlug) return;
    try {
      const res = await adminFetch('/api/admin/plans', {
        method: 'POST',
        body: JSON.stringify({ slug: newPlanSlug.toLowerCase().trim() }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Could not create plan container');
      }
      setSuccessMsg(`Plan "${newPlanSlug}" created in draft status.`);
      setNewPlanSlug('');
      setShowCreatePlanModal(false);
      await fetchPlans();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlanId || !verName) return;

    const benefitsList = verBenefits.split('\n').map(s => s.trim()).filter(Boolean);
    const entitlementsPayload: Record<string, any> = {
      kisan_chat: {
        enabled: true,
        usage_limit: entKisanChatLimit === '' ? null : Number(entKisanChatLimit),
        limit_period: 'monthly'
      },
      diagnose_leaf: {
        enabled: true,
        usage_limit: entDiagnoseLimit === '' ? null : Number(entDiagnoseLimit),
        limit_period: 'monthly'
      },
      mandi_price: {
        enabled: true,
        usage_limit: entMandiLimit === '' ? null : Number(entMandiLimit),
        limit_period: 'monthly'
      }
    };

    try {
      const res = await adminFetch(`/api/admin/plans/${selectedPlanId}/versions`, {
        method: 'POST',
        body: JSON.stringify({
          name: verName,
          description: verDesc,
          price_minor: Math.round(verPriceInr * 100),
          currency: 'INR',
          billing_interval: verInterval,
          trial_days: Number(verTrialDays),
          benefits: benefitsList,
          entitlements: entitlementsPayload
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Could not create plan version');
      }

      setSuccessMsg(`Version "${verName}" created as draft. Review and submit for Super Admin approval.`);
      setShowCreateVersionModal(false);
      await fetchPlans();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handlePublishVersion = async (planId: string, versionId: string, versionName: string) => {
    if (!isSuperAdmin) {
      setError('Executive Authority Required: Only Head Super Admin (vvivekshastrym@gmail.com) can publish pricing versions to production.');
      return;
    }
    if (!confirm(`Publish "${versionName}"?\n\nOnce published, this pricing version is permanently IMMUTABLE under audit policies. Existing subscribers keep their agreed version.`)) {
      return;
    }
    try {
      const res = await adminFetch(`/api/admin/plans/${planId}/versions/${versionId}/publish`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Failed to publish version');
      }
      setSuccessMsg(`Version published successfully! It is now live in the Farmer App.`);
      await fetchPlans();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUpdateStatus = async (planId: string, newStatus: string) => {
    if (!isSuperAdmin) {
      setError('Executive Authority Required: Only Head Super Admin (vvivekshastrym@gmail.com) can change plan lifecycle status.');
      return;
    }
    try {
      const res = await adminFetch(`/api/admin/plans/${planId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.error?.message || err.detail || 'Status update failed');
      }
      setSuccessMsg(`Plan status changed to ${newStatus}.`);
      await fetchPlans();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const statusBadge = (st: string) => {
    const map: Record<string, string> = {
      published: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      draft: 'bg-amber-50 text-amber-700 border-amber-200',
      paused: 'bg-orange-50 text-orange-700 border-orange-200',
      archived: 'bg-gray-100 text-gray-700 border-gray-200',
    };
    return (
      <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border uppercase tracking-wider ${map[st] || 'bg-gray-50'}`}>
        {st}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div>
          <h2 className="font-display text-2xl font-bold text-[#1B4332]">Subscription Plan Manager</h2>
          <p className="text-sm text-[#6B7280]">Configure immutable pricing versions, entitlement gates, and intervals</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchPlans}
            disabled={loading}
            className="p-2 rounded-xl bg-white border border-[#E5DFD3] text-[#374151] hover:bg-[#F9F7F1]"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowCreatePlanModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#1B4332] hover:bg-[#2D6A4F] text-white text-sm font-semibold shadow-xs transition cursor-pointer"
          >
            <Plus size={16} />
            Create Plan
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold text-red-800">Dismiss</button>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-bold text-emerald-900">Dismiss</button>
        </div>
      )}

      {/* Plans List */}
      {plans.length === 0 && !loading ? (
        <div className="bg-white rounded-2xl border border-[#E5DFD3] p-12 text-center">
          <Layers size={40} className="mx-auto text-[#9CA3AF] mb-3" />
          <h3 className="font-display text-lg font-bold text-[#1B4332]">No Subscription Plans Yet</h3>
          <p className="text-sm text-[#6B7280] max-w-md mx-auto mt-1 mb-6">
            Create your first plan container (e.g. "kisan-pro") and add versioned pricing terms.
          </p>
          <button
            onClick={() => setShowCreatePlanModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1B4332] text-white text-sm font-semibold"
          >
            <Plus size={16} /> Create Plan
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {plans.map((plan) => {
            const isExpanded = expandedPlanId === plan.id;
            return (
              <div key={plan.id} className="bg-white rounded-2xl border border-[#E5DFD3] overflow-hidden shadow-xs">
                {/* Plan Header Row */}
                <div className="p-5 flex items-center justify-between hover:bg-[#FAF8F5] transition">
                  <div
                    className="flex-1 flex items-center gap-4 cursor-pointer"
                    onClick={() => setExpandedPlanId(isExpanded ? null : plan.id)}
                  >
                    <div className="w-10 h-10 rounded-xl bg-[#E8F5E9] text-[#2D6A4F] flex items-center justify-center font-bold">
                      <Tag size={18} />
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-bold text-[#111827]">{plan.slug}</span>
                        {statusBadge(plan.status)}
                      </div>
                      <p className="text-xs text-[#6B7280] mt-0.5">
                        {plan.versions.length} version{plan.versions.length === 1 ? '' : 's'} recorded
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        setSelectedPlanId(plan.id);
                        setShowCreateVersionModal(true);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-[#FAF8F5] hover:bg-[#F3EFE6] border border-[#E5DFD3] text-xs font-semibold text-[#1B4332] flex items-center gap-1.5"
                    >
                      <Plus size={14} /> New Version
                    </button>

                    {plan.status === 'published' ? (
                      <button
                        onClick={() => handleUpdateStatus(plan.id, 'paused')}
                        title="Pause Plan"
                        className="p-1.5 rounded-lg text-amber-700 hover:bg-amber-50"
                      >
                        <PauseCircle size={18} />
                      </button>
                    ) : plan.status === 'paused' ? (
                      <button
                        onClick={() => handleUpdateStatus(plan.id, 'published')}
                        title="Resume Plan"
                        className="p-1.5 rounded-lg text-emerald-700 hover:bg-emerald-50"
                      >
                        <CheckCircle2 size={18} />
                      </button>
                    ) : null}

                    {plan.status !== 'archived' && (
                      <button
                        onClick={() => handleUpdateStatus(plan.id, 'archived')}
                        title="Archive Plan"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700"
                      >
                        <Archive size={18} />
                      </button>
                    )}

                    <button
                      onClick={() => setExpandedPlanId(isExpanded ? null : plan.id)}
                      className="text-gray-400 hover:text-gray-700"
                    >
                      {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </button>
                  </div>
                </div>

                {/* Versions Accordion Body */}
                {isExpanded && (
                  <div className="border-t border-[#F3EFE6] bg-[#FAF8F5] p-5 space-y-4">
                    <div className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">
                      Pricing Versions & Entitlements
                    </div>

                    {plan.versions.length === 0 ? (
                      <div className="text-center py-6 text-sm text-[#9CA3AF]">
                        No versions created for this plan yet. Click "New Version" above to define pricing.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {plan.versions.map((v) => (
                          <div
                            key={v.id}
                            className={`rounded-xl border p-4 bg-white relative ${
                              v.is_published ? 'border-emerald-300 ring-1 ring-emerald-100' : 'border-amber-200'
                            }`}
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div>
                                <div className="flex items-center gap-2">
                                  <h4 className="font-bold text-sm text-[#111827]">{v.name}</h4>
                                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-gray-100 font-semibold text-gray-700">
                                    v{v.version}
                                  </span>
                                </div>
                                <p className="text-xs text-[#6B7280] mt-0.5">{v.description || 'No description'}</p>
                              </div>

                              <div>
                                {v.is_published ? (
                                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                    <Lock size={10} /> Published
                                  </span>
                                ) : (
                                  <span className="text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                                    Draft
                                  </span>
                                )}
                              </div>
                            </div>

                            {/* Pricing & Terms */}
                            <div className="my-3 py-2 px-3 rounded-lg bg-[#FAF8F5] flex items-center justify-between">
                              <span className="font-display text-xl font-bold text-[#1B4332]">
                                {v.price_formatted}
                              </span>
                              <span className="text-xs text-[#4B5563] capitalize font-medium">
                                billed {v.billing_interval} {v.trial_days > 0 ? `· ${v.trial_days}d trial` : ''}
                              </span>
                            </div>

                            {/* Feature Entitlements Breakdown */}
                            <div className="space-y-1 mb-3 text-xs text-[#374151]">
                              <div className="font-semibold text-[11px] text-[#6B7280] uppercase tracking-wider">
                                Active Feature Gates
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span>🌾 Kisan GPT Chat</span>
                                <span className="font-mono font-semibold">
                                  {v.entitlements.kisan_chat?.usage_limit ? `${v.entitlements.kisan_chat.usage_limit}/mo` : 'Unlimited'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span>🔬 Leaf Crop Diagnosis</span>
                                <span className="font-mono font-semibold">
                                  {v.entitlements.diagnose_leaf?.usage_limit ? `${v.entitlements.diagnose_leaf.usage_limit}/mo` : 'Unlimited'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span>📈 Mandi APMC Prices</span>
                                <span className="font-mono font-semibold">
                                  {v.entitlements.mandi_price?.usage_limit ? `${v.entitlements.mandi_price.usage_limit}/mo` : 'Unlimited'}
                                </span>
                              </div>
                            </div>

                            {/* Benefits Bullet Points */}
                            {v.benefits && v.benefits.length > 0 && (
                              <div className="border-t border-[#F3EFE6] pt-2 mb-3">
                                <ul className="text-xs text-[#4B5563] space-y-1">
                                  {v.benefits.map((b, idx) => (
                                    <li key={idx} className="flex items-center gap-1.5 truncate">
                                      <span className="text-emerald-600 font-bold">✓</span> {b}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Action to publish if draft */}
                            {!v.is_published && (
                              isSuperAdmin ? (
                                <button
                                  onClick={() => handlePublishVersion(plan.id, v.id, v.name)}
                                  className="w-full mt-2 py-2 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer"
                                >
                                  <Sparkles size={14} /> Publish this Version
                                </button>
                              ) : (
                                <div className="w-full mt-2 py-2 px-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-semibold flex items-center justify-center gap-1.5 text-center">
                                  <Lock size={12} className="shrink-0" />
                                  <span>Publishing Requires Head Super Admin Approval</span>
                                </div>
                              )
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── CREATE PLAN MODAL ───────────────────────── */}
      {showCreatePlanModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-[#E5DFD3]">
            <h3 className="font-display text-lg font-bold text-[#1B4332] mb-1">Create Subscription Plan</h3>
            <p className="text-xs text-[#6B7280] mb-4">Enter a clean URL slug (e.g. "farmer-pro" or "kisan-growth").</p>

            <form onSubmit={handleCreatePlan} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Plan Slug</label>
                <input
                  type="text"
                  value={newPlanSlug}
                  onChange={(e) => setNewPlanSlug(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                  placeholder="farmer-pro"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-gray-300 text-sm font-mono focus:ring-2 focus:ring-[#2D6A4F]"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreatePlanModal(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-[#1B4332] text-white text-sm font-semibold hover:bg-[#2D6A4F]"
                >
                  Create Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── CREATE VERSION MODAL ────────────────────── */}
      {showCreateVersionModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl border border-[#E5DFD3] my-8">
            <h3 className="font-display text-lg font-bold text-[#1B4332] mb-1">Add Pricing Version</h3>
            <p className="text-xs text-[#6B7280] mb-4">Creates a draft terms version. Does not affect existing subscribers.</p>

            <form onSubmit={handleCreateVersion} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Version Title</label>
                  <input
                    type="text"
                    value={verName}
                    onChange={(e) => setVerName(e.target.value)}
                    placeholder="Kisan Pro Annual"
                    className="w-full px-3 py-2 rounded-xl border border-gray-300 text-sm focus:ring-2 focus:ring-[#2D6A4F]"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Price (₹ INR)</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={verPriceInr}
                    onChange={(e) => setVerPriceInr(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl border border-gray-300 text-sm focus:ring-2 focus:ring-[#2D6A4F]"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Billing Interval</label>
                  <select
                    value={verInterval}
                    onChange={(e) => setVerInterval(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-300 text-sm focus:ring-2 focus:ring-[#2D6A4F]"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="yearly">Yearly</option>
                    <option value="lifetime">Lifetime</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Trial Period (Days)</label>
                  <input
                    type="number"
                    min="0"
                    value={verTrialDays}
                    onChange={(e) => setVerTrialDays(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl border border-gray-300 text-sm focus:ring-2 focus:ring-[#2D6A4F]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Description</label>
                <input
                  type="text"
                  value={verDesc}
                  onChange={(e) => setVerDesc(e.target.value)}
                  placeholder="Full access to Kisan AI crop doctor & market intelligence"
                  className="w-full px-3 py-2 rounded-xl border border-gray-300 text-sm"
                />
              </div>

              {/* Entitlement Limits */}
              <div className="p-3.5 bg-[#FAF8F5] rounded-xl border border-[#E5DFD3] space-y-3">
                <div className="text-xs font-bold text-[#1B4332] uppercase">Feature Usage Limits (leave blank for unlimited)</div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-gray-600 mb-0.5">Kisan GPT / mo</label>
                    <input
                      type="number"
                      min="0"
                      value={entKisanChatLimit}
                      onChange={(e) => setEntKisanChatLimit(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder="Unlimited"
                      className="w-full px-2 py-1.5 rounded-lg border border-gray-300 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-gray-600 mb-0.5">Diagnose Leaf / mo</label>
                    <input
                      type="number"
                      min="0"
                      value={entDiagnoseLimit}
                      onChange={(e) => setEntDiagnoseLimit(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder="Unlimited"
                      className="w-full px-2 py-1.5 rounded-lg border border-gray-300 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-gray-600 mb-0.5">Mandi Price / mo</label>
                    <input
                      type="number"
                      min="0"
                      value={entMandiLimit}
                      onChange={(e) => setEntMandiLimit(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder="Unlimited"
                      className="w-full px-2 py-1.5 rounded-lg border border-gray-300 text-xs"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#374151] uppercase mb-1">Benefits Bullet Points (One per line)</label>
                <textarea
                  rows={3}
                  value={verBenefits}
                  onChange={(e) => setVerBenefits(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-sans"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateVersionModal(false)}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-[#1B4332] text-white text-sm font-semibold hover:bg-[#2D6A4F] cursor-pointer"
                >
                  Save Draft Version
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
