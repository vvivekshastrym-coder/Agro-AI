import React, { useEffect, useState } from 'react';
import { useAdminAuth, AdminRole } from '../context/AdminAuthContext';
import { Users, Shield, Search, CheckCircle, AlertTriangle, RefreshCw, UserCheck, XCircle, Clock, Lock } from 'lucide-react';
import { adminFetch } from '../lib/api';

interface UserRecord {
  id: string;
  email: string;
  full_name?: string;
  role?: string;
  admin_role?: AdminRole | null;
  is_active: boolean;
  created_at?: string;
}

interface AccessRequestRecord {
  id: string;
  user_id?: string;
  email: string;
  full_name: string;
  requested_role: string;
  notes?: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string;
  reviewed_at?: string;
  created_at?: string;
}

const ALL_ROLES: { role: AdminRole; label: string }[] = [
  { role: 'plan_manager', label: 'Plan Operations (Drafting & Limits)' },
  { role: 'payment_manager', label: 'Finance & Payment Settlements' },
  { role: 'support_agent', label: 'Farmer Support & Privacy Queue' },
  { role: 'analyst', label: 'Data Analytics & Audit Inspector' },
  { role: 'content_manager', label: 'Crop Advisory Content' },
  { role: 'super_admin', label: 'Super Admin (Executive Authority)' }
];

export const UserDirectory: React.FC = () => {
  const { profile, isSuperAdmin } = useAdminAuth();
  
  const [activeTab, setActiveTab] = useState<'users' | 'requests'>('requests');
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [accessRequests, setAccessRequests] = useState<AccessRequestRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Selected roles map for approving access requests
  const [selectedApproveRoles, setSelectedApproveRoles] = useState<Record<string, AdminRole>>({});

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/users');
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error?.message || `Failed to fetch users: HTTP ${res.status}`);
      }
      const data = await res.json();
      setUsers(data);
    } catch (err: any) {
      setError(err.message || 'Error loading users');
    } finally {
      setLoading(false);
    }
  };

  const fetchAccessRequests = async () => {
    if (!isSuperAdmin) return;
    setRequestsLoading(true);
    try {
      const res = await adminFetch('/api/admin/access-requests');
      if (res.ok) {
        const data = await res.json();
        setAccessRequests(data);
        // Pre-fill selected approve roles
        const initialMap: Record<string, AdminRole> = {};
        data.forEach((r: AccessRequestRecord) => {
          initialMap[r.id] = (r.requested_role as AdminRole) || 'support_agent';
        });
        setSelectedApproveRoles(initialMap);
      }
    } catch (err: any) {
      console.error('Error loading access requests:', err);
    } finally {
      setRequestsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    if (isSuperAdmin) {
      fetchAccessRequests();
    } else {
      setActiveTab('users');
    }

    const timer = setInterval(() => {
      fetchUsers();
      if (isSuperAdmin) fetchAccessRequests();
    }, 12000);

    const handleFocus = () => {
      fetchUsers();
      if (isSuperAdmin) fetchAccessRequests();
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', handleFocus);
    };
  }, [isSuperAdmin]);

  const handleApproveRequest = async (requestId: string) => {
    setActionLoading(requestId);
    setActionSuccess(null);
    setError(null);
    try {
      const roleToAssign = selectedApproveRoles[requestId] || 'support_agent';
      const res = await adminFetch(`/api/admin/access-requests/${requestId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ role: roleToAssign })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail?.error?.message || errData?.detail || 'Failed to approve request');
      }
      const data = await res.json();
      setActionSuccess(data.message || 'Staff request approved successfully!');
      await fetchAccessRequests();
      await fetchUsers();
    } catch (err: any) {
      setError(err.message || 'Error approving request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectRequest = async (requestId: string) => {
    setActionLoading(requestId);
    setActionSuccess(null);
    setError(null);
    try {
      const res = await adminFetch(`/api/admin/access-requests/${requestId}/reject`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail?.error?.message || errData?.detail || 'Failed to reject request');
      }
      setActionSuccess('Staff request has been rejected.');
      await fetchAccessRequests();
      await fetchUsers();
    } catch (err: any) {
      setError(err.message || 'Error rejecting request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleAssignRole = async (userId: string, newRole: AdminRole) => {
    setActionLoading(userId);
    setActionSuccess(null);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/users/assign-role', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, role: newRole, is_active: true })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail?.error?.message || errData?.detail || 'Failed to update administrative role');
      }
      setActionSuccess(`Successfully assigned ${newRole.replace('_', ' ')} role.`);
      await fetchUsers();
    } catch (err: any) {
      setError(err.message || 'Error assigning role');
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    setActionLoading(userId);
    setActionSuccess(null);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/users/assign-role', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, is_active: !currentActive })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail?.error?.message || errData?.detail || 'Failed to toggle access status');
      }
      setActionSuccess(`Account access ${!currentActive ? 'reactivated' : 'revoked'}.`);
      await fetchUsers();
    } catch (err: any) {
      setError(err.message || 'Error updating account status');
    } finally {
      setActionLoading(null);
    }
  };

  const pendingRequests = accessRequests.filter(r => r.status === 'pending');

  const filteredUsers = users.filter(u => {
    const s = search.toLowerCase();
    return (
      u.email?.toLowerCase().includes(s) ||
      u.full_name?.toLowerCase().includes(s) ||
      u.id?.toLowerCase().includes(s) ||
      u.admin_role?.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Staff & Platform Permissions</h1>
          <p className="text-sm text-[#4B5563]">
            Access Approval Architecture: Only Head Super Admin can authorize company workers and assign permissions.
          </p>
        </div>
        <button
          onClick={() => {
            fetchUsers();
            if (isSuperAdmin) fetchAccessRequests();
          }}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-xs cursor-pointer"
        >
          <RefreshCw size={16} className={loading || requestsLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Hierarchy Info Banner */}
      <div className="p-4 rounded-xl bg-[#E8F5E9] border border-[#C8E6C9] flex items-start sm:items-center justify-between gap-3 text-xs text-[#1B4332]">
        <div className="flex items-center gap-2.5">
          <Shield size={18} className="text-[#2D6A4F] shrink-0" />
          <div>
            <span className="font-bold">Head of Agro AI (Super Admin):</span> vvivekshastrym@gmail.com
            <span className="mx-2 text-[#81C784]">|</span>
            <span className="text-[#2E7D32]">All major plan publishing and staff access decisions require Super Admin approval.</span>
          </div>
        </div>
        <span className="hidden sm:inline-block px-2 py-0.5 rounded-full bg-[#2D6A4F] text-white font-semibold text-[11px]">
          {isSuperAdmin ? 'Logged in as Super Admin' : 'Worker (Read/Manage Mode)'}
        </span>
      </div>

      {/* Notifications */}
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

      {/* Tabs */}
      {isSuperAdmin && (
        <div className="flex border-b border-[#E5DFD3] gap-6 text-sm font-semibold">
          <button
            onClick={() => setActiveTab('requests')}
            className={`pb-3 relative transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'requests'
                ? 'text-[#1B4332] border-b-2 border-[#1B4332]'
                : 'text-[#6B7280] hover:text-[#1F2937]'
            }`}
          >
            <span>Pending Staff Access Requests</span>
            {pendingRequests.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500 text-white font-bold">
                {pendingRequests.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`pb-3 relative transition flex items-center gap-2 cursor-pointer ${
              activeTab === 'users'
                ? 'text-[#1B4332] border-b-2 border-[#1B4332]'
                : 'text-[#6B7280] hover:text-[#1F2937]'
            }`}
          >
            <span>All Registered Users & Staff</span>
            <span className="px-2 py-0.5 rounded-full text-xs bg-[#E5DFD3] text-[#374151]">
              {users.length}
            </span>
          </button>
        </div>
      )}

      {/* TAB 1: PENDING STAFF ACCESS REQUESTS */}
      {isSuperAdmin && activeTab === 'requests' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-xs overflow-hidden">
            <div className="p-5 border-b border-[#E5DFD3] bg-[#FAF8F5]">
              <h2 className="font-semibold text-sm text-[#1B4332]">Staff Access Requests Awaiting Approval</h2>
              <p className="text-xs text-[#6B7280] mt-0.5">
                Review and approve company workers before they can sign in to the Agro AI admin panel.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-[#374151]">
                <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
                  <tr>
                    <th className="px-6 py-3.5">Applicant</th>
                    <th className="px-6 py-3.5">Requested Role & Purpose</th>
                    <th className="px-6 py-3.5">Date Submitted</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5 text-right">Approval Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5DFD3]">
                  {requestsLoading ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-sm text-[#6B7280]">
                        Checking pending access queue...
                      </td>
                    </tr>
                  ) : accessRequests.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-sm text-[#6B7280]">
                        No pending staff access requests at this time.
                      </td>
                    </tr>
                  ) : (
                    accessRequests.map(req => (
                      <tr key={req.id} className="hover:bg-[#FAF8F5]/60 transition">
                        <td className="px-6 py-4">
                          <div className="font-semibold text-[#1B4332]">{req.full_name}</div>
                          <div className="text-xs text-[#4B5563]">{req.email}</div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-xs font-semibold text-[#2D6A4F] capitalize">
                            Requested: {req.requested_role.replace('_', ' ')}
                          </div>
                          {req.notes && (
                            <div className="text-xs text-[#6B7280] italic mt-0.5">"{req.notes}"</div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-xs text-[#6B7280]">
                          {req.created_at ? new Date(req.created_at).toLocaleDateString('en-IN', {
                            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                          }) : '—'}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                            req.status === 'approved'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : req.status === 'rejected'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {req.status === 'pending' && <Clock size={12} />}
                            {req.status === 'approved' && <CheckCircle size={12} />}
                            {req.status === 'rejected' && <XCircle size={12} />}
                            <span className="capitalize">{req.status}</span>
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          {req.status === 'pending' ? (
                            <div className="flex items-center justify-end gap-2">
                              <select
                                value={selectedApproveRoles[req.id] || 'support_agent'}
                                onChange={e => setSelectedApproveRoles(prev => ({ ...prev, [req.id]: e.target.value as AdminRole }))}
                                className="text-xs px-2.5 py-1.5 rounded-lg border border-[#D1D5DB] bg-white text-[#1B4332] font-medium"
                              >
                                {ALL_ROLES.map(r => (
                                  <option key={r.role} value={r.role}>
                                    {r.label}
                                  </option>
                                ))}
                              </select>
                              <button
                                onClick={() => handleApproveRequest(req.id)}
                                disabled={actionLoading === req.id}
                                className="px-3 py-1.5 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4332] text-white text-xs font-semibold flex items-center gap-1 transition shadow-xs disabled:opacity-50 cursor-pointer"
                              >
                                <CheckCircle size={13} />
                                Approve
                              </button>
                              <button
                                onClick={() => handleRejectRequest(req.id)}
                                disabled={actionLoading === req.id}
                                className="px-2.5 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-xs font-semibold transition disabled:opacity-50 cursor-pointer"
                              >
                                Reject
                              </button>
                            </div>
                          ) : (
                            <span className="text-xs text-[#9CA3AF] capitalize font-medium">Processed</span>
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
      )}

      {/* TAB 2: ACTIVE USERS & PERMISSIONS TABLE */}
      {(!isSuperAdmin || activeTab === 'users') && (
        <div className="space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by name, email, user ID, or role..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-[#E5DFD3] bg-white text-sm text-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#2D6A4F]/20 focus:border-[#2D6A4F]"
            />
          </div>

          {/* Users Table */}
          <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-[#374151]">
                <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
                  <tr>
                    <th className="px-6 py-4">User</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Farmer Role</th>
                    <th className="px-6 py-4">Admin Privileges</th>
                    <th className="px-6 py-4 text-right">Super Admin Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5DFD3]">
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                        Loading user records from database...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-sm text-[#6B7280]">
                        No user accounts match your search query.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map(user => {
                      const isHeadSuperAdmin = user.email?.toLowerCase() === 'vvivekshastrym@gmail.com';
                      return (
                        <tr key={user.id} className={`hover:bg-[#FAF8F5]/60 transition ${isHeadSuperAdmin ? 'bg-emerald-50/40' : ''}`}>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-[#1B4332]">{user.full_name || 'Unnamed User'}</span>
                              {isHeadSuperAdmin && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#1B4332] text-white">
                                  HEAD SUPER ADMIN
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-[#6B7280]">{user.email}</div>
                            <div className="text-[10px] text-[#9CA3AF] font-mono mt-0.5">{user.id}</div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                              user.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${user.is_active ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                              {user.is_active ? 'Active' : 'Suspended'}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="capitalize text-xs font-medium text-[#4B5563]">
                              {user.role || 'farmer'}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            {user.admin_role ? (
                              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold ${
                                user.admin_role === 'super_admin'
                                  ? 'bg-[#1B4332] text-white'
                                  : 'bg-[#2D6A4F]/10 text-[#2D6A4F] border border-[#2D6A4F]/20'
                              } uppercase tracking-wide`}>
                                <Shield size={12} />
                                {user.admin_role.replace('_', ' ')}
                              </span>
                            ) : (
                              <span className="text-xs text-[#9CA3AF]">None</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-right">
                            {isSuperAdmin ? (
                              <div className="inline-flex items-center gap-2">
                                {!isHeadSuperAdmin ? (
                                  <>
                                    <select
                                      disabled={actionLoading === user.id}
                                      value={user.admin_role || ''}
                                      onChange={e => {
                                        if (e.target.value) {
                                          handleAssignRole(user.id, e.target.value as AdminRole);
                                        }
                                      }}
                                      className="text-xs px-2.5 py-1.5 rounded-lg border border-[#E5DFD3] bg-white text-[#1B4332] font-medium focus:ring-1 focus:ring-[#2D6A4F] disabled:opacity-50"
                                    >
                                      <option value="" disabled>Change role...</option>
                                      {ALL_ROLES.map(r => (
                                        <option key={r.role} value={r.role}>
                                          {r.role.replace('_', ' ').toUpperCase()}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      onClick={() => handleToggleActive(user.id, user.is_active)}
                                      disabled={actionLoading === user.id}
                                      className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
                                        user.is_active
                                          ? 'border-red-200 text-red-600 hover:bg-red-50'
                                          : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'
                                      }`}
                                    >
                                      {user.is_active ? 'Revoke' : 'Activate'}
                                    </button>
                                  </>
                                ) : (
                                  <span className="text-xs font-semibold text-[#2D6A4F]">Permanent Head</span>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-[#9CA3AF] italic">View only</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
