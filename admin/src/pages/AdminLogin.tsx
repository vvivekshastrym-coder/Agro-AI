import React, { useState } from 'react';
import { useAdminAuth } from '../context/AdminAuthContext';
import { Shield, Lock, ArrowRight, AlertCircle, CheckCircle2, UserCheck, KeyRound, Sparkles } from 'lucide-react';

export const AdminLogin: React.FC = () => {
  const { login, verifyMfa, mfaRequired, error: authError, loading } = useAdminAuth();
  
  const [tab, setTab] = useState<'signin' | 'request'>('signin');
  
  // Sign in state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  // Request access state
  const [reqFullName, setReqFullName] = useState('');
  const [reqEmail, setReqEmail] = useState('');
  const [reqPassword, setReqPassword] = useState('');
  const [reqRole, setReqRole] = useState('plan_manager');
  const [reqNotes, setReqNotes] = useState('');
  const [reqLoading, setReqLoading] = useState(false);
  const [reqSuccess, setReqSuccess] = useState<string | null>(null);
  const [reqError, setReqError] = useState<string | null>(null);

  const fillSuperAdmin = () => {
    setEmail('vvivekshastrym@gmail.com');
    setPassword('Vivek@123');
    setLocalError(null);
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (mfaRequired) {
      if (!totpCode || totpCode.length !== 6) {
        setLocalError('Please enter a valid 6-digit TOTP code from your authenticator app.');
        return;
      }
      const success = await verifyMfa(totpCode);
      if (!success) {
        setLocalError('Invalid or expired authentication code.');
      }
      return;
    }

    if (!email) {
      setLocalError('Please enter your administrator email address.');
      return;
    }

    try {
      await login(email, password || undefined);
    } catch (err: any) {
      setLocalError(err.message || 'Authentication failed. Please verify credentials.');
    }
  };

  const handleRequestAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    setReqLoading(true);
    setReqError(null);
    setReqSuccess(null);

    try {
      const res = await fetch('/api/admin/request-access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: reqFullName.trim(),
          email: reqEmail.trim(),
          password: reqPassword,
          requested_role: reqRole,
          notes: reqNotes.trim() || undefined
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Failed to submit access request.');
      }

      setReqSuccess(data.message || 'Access request submitted! Awaiting approval from Head Super Admin.');
      setReqFullName('');
      setReqEmail('');
      setReqPassword('');
      setReqNotes('');
    } catch (err: any) {
      setReqError(err.message || 'Error submitting access request.');
    } finally {
      setReqLoading(false);
    }
  };

  const errDisplay = localError || authError;
  const isPendingApproval = errDisplay && (errDisplay.includes('awaiting approval') || errDisplay.includes('not been approved') || errDisplay.includes('Head Super Admin'));

  return (
    <div className="min-h-screen bg-[#FAF8F5] flex flex-col justify-center items-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Header and Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-br from-[#2D6A4F] to-[#081C15] items-center justify-center text-3xl shadow-lg mb-3">
            🌾
          </div>
          <h1 className="font-display text-2xl font-bold text-[#1B4332]">Agro AI Admin Console</h1>
          <p className="text-sm text-[#4B5563] mt-1">Enterprise Management & Access Hierarchy</p>
        </div>

        {/* Tab Switcher */}
        <div className="flex bg-[#EFECE6] p-1 rounded-xl mb-4 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setTab('signin')}
            className={`flex-1 py-2 rounded-lg transition ${
              tab === 'signin'
                ? 'bg-white text-[#1B4332] shadow-sm'
                : 'text-[#6B7280] hover:text-[#1F2937]'
            }`}
          >
            Admin Sign In
          </button>
          <button
            type="button"
            onClick={() => setTab('request')}
            className={`flex-1 py-2 rounded-lg transition ${
              tab === 'request'
                ? 'bg-white text-[#1B4332] shadow-sm'
                : 'text-[#6B7280] hover:text-[#1F2937]'
            }`}
          >
            Request Staff Access
          </button>
        </div>

        {/* Super Admin Quick Notice */}
        <div className="bg-[#E8F5E9] border border-[#C8E6C9] rounded-xl p-3 mb-4 flex items-center justify-between text-xs text-[#1B4332]">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-[#2D6A4F] shrink-0" />
            <div>
              <span className="font-semibold">Head Super Admin:</span> vvivekshastrym@gmail.com
            </div>
          </div>
          {tab === 'signin' && (
            <button
              type="button"
              onClick={fillSuperAdmin}
              className="text-[11px] font-medium text-[#2D6A4F] hover:text-[#1B4332] bg-white px-2 py-1 rounded-md border border-[#A5D6A7] shadow-xs cursor-pointer"
            >
              Autofill
            </button>
          )}
        </div>

        {/* Main Card */}
        <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-md p-6 sm:p-8">
          {tab === 'signin' ? (
            <div>
              {/* Approval Error Notice */}
              {isPendingApproval ? (
                <div className="mb-5 p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-2.5">
                  <Lock size={16} className="shrink-0 text-amber-600 mt-0.5" />
                  <div>
                    <p className="font-bold">Access Pending Super Admin Approval</p>
                    <p className="mt-0.5">{errDisplay}</p>
                    <p className="mt-1 text-[11px] text-amber-700">Please contact Head Super Admin Vivek Shastry to authorize your account.</p>
                  </div>
                </div>
              ) : errDisplay ? (
                <div className="mb-5 p-3.5 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3 text-red-700 text-xs">
                  <AlertCircle size={16} className="shrink-0 mt-0.5 text-red-600" />
                  <div>
                    <p className="font-semibold">Sign In Failed</p>
                    <p className="mt-0.5">{errDisplay}</p>
                  </div>
                </div>
              ) : null}

              {!mfaRequired ? (
                <form onSubmit={handleSignIn} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-[#374151] uppercase tracking-wider mb-1.5">
                      Admin Email
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="admin@agroai.internal"
                      className="w-full px-4 py-2.5 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] focus:border-transparent transition bg-[#FBFBFB]"
                      required
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-semibold text-[#374151] uppercase tracking-wider">
                        Password
                      </label>
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full px-4 py-2.5 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] focus:border-transparent transition bg-[#FBFBFB]"
                      required
                    />
                  </div>

                  <div className="pt-2">
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full py-3 px-4 rounded-xl bg-[#1B4332] hover:bg-[#2D6A4F] text-white font-medium text-sm flex items-center justify-center gap-2 shadow-sm transition disabled:opacity-60 cursor-pointer"
                    >
                      {loading ? 'Authenticating…' : 'Sign In to Console'}
                      <ArrowRight size={16} />
                    </button>
                  </div>

                  <div className="mt-4 pt-4 border-t border-[#F3EFE6] text-center">
                    <p className="text-xs text-[#6B7280]">
                      Protected by server-side approval gate and PBKDF2 cryptography.
                    </p>
                  </div>
                </form>
              ) : (
                <form onSubmit={handleSignIn} className="space-y-5">
                  <div className="text-center pb-2">
                    <div className="w-10 h-10 rounded-full bg-[#E8F5E9] text-[#2D6A4F] mx-auto flex items-center justify-center mb-2">
                      <Shield size={20} />
                    </div>
                    <h3 className="font-semibold text-base text-[#1F2937]">Two-Factor Authentication</h3>
                    <p className="text-xs text-[#6B7280] mt-1">Enter the 6-digit code from your authenticator app</p>
                  </div>

                  <div>
                    <input
                      type="text"
                      maxLength={6}
                      value={totpCode}
                      onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="000000"
                      className="w-full py-3 text-center tracking-widest text-2xl font-mono rounded-xl border border-[#D1D5DB] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]"
                      autoFocus
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading || totpCode.length !== 6}
                    className="w-full py-3 px-4 rounded-xl bg-[#1B4332] hover:bg-[#2D6A4F] text-white font-medium text-sm flex items-center justify-center gap-2 transition disabled:opacity-50 cursor-pointer"
                  >
                    {loading ? 'Verifying…' : 'Verify & Continue'}
                    <CheckCircle2 size={16} />
                  </button>
                </form>
              )}
            </div>
          ) : (
            <div>
              {/* Access Request Form */}
              <div className="mb-4">
                <h2 className="font-semibold text-[#1B4332] text-sm">Staff Access Request</h2>
                <p className="text-xs text-[#6B7280] mt-0.5">
                  All company worker accounts must be explicitly approved by Head Super Admin (Vivek Shastry) before access is activated.
                </p>
              </div>

              {reqSuccess && (
                <div className="mb-4 p-3.5 rounded-xl bg-green-50 border border-green-200 text-green-800 text-xs flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">Request Submitted</p>
                    <p className="mt-0.5">{reqSuccess}</p>
                  </div>
                </div>
              )}

              {reqError && (
                <div className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5">
                  <AlertCircle size={16} className="text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">Submission Failed</p>
                    <p className="mt-0.5">{reqError}</p>
                  </div>
                </div>
              )}

              <form onSubmit={handleRequestAccess} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={reqFullName}
                    onChange={(e) => setReqFullName(e.target.value)}
                    placeholder="e.g. Ramesh Kumar"
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">
                    Company Email
                  </label>
                  <input
                    type="email"
                    value={reqEmail}
                    onChange={(e) => setReqEmail(e.target.value)}
                    placeholder="e.g. ramesh@agroai.internal"
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">
                    Password (for login once approved)
                  </label>
                  <input
                    type="password"
                    value={reqPassword}
                    onChange={(e) => setReqPassword(e.target.value)}
                    placeholder="Minimum 6 characters"
                    minLength={6}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">
                    Desired Department / Role
                  </label>
                  <select
                    value={reqRole}
                    onChange={(e) => setReqRole(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-sm focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                  >
                    <option value="plan_manager">Plan Operations (Drafting & Limits)</option>
                    <option value="payment_manager">Finance & Payment Settlements</option>
                    <option value="support_agent">Farmer Support & Privacy Queue</option>
                    <option value="analyst">Data Analytics & Audit Inspector</option>
                    <option value="content_manager">Crop Advisory Content</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#374151] mb-1">
                    Purpose / Notes for Super Admin (Optional)
                  </label>
                  <textarea
                    value={reqNotes}
                    onChange={(e) => setReqNotes(e.target.value)}
                    rows={2}
                    placeholder="Reason or department assignment..."
                    className="w-full px-3.5 py-2 rounded-xl border border-[#D1D5DB] text-xs focus:outline-none focus:ring-2 focus:ring-[#2D6A4F] bg-[#FBFBFB]"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={reqLoading}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#2D6A4F] hover:bg-[#1B4332] text-white font-medium text-xs flex items-center justify-center gap-2 shadow-sm transition disabled:opacity-60 cursor-pointer"
                  >
                    <UserCheck size={15} />
                    {reqLoading ? 'Submitting…' : 'Submit Request to Super Admin'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
