import React, { useState } from 'react';
import { useAdminAuth, AdminRole } from '../context/AdminAuthContext';
import {
  LayoutDashboard,
  Layers,
  Users,
  CreditCard,
  ShieldCheck,
  FileText,
  LogOut,
  ChevronRight,
  Menu,
  X,
  Megaphone,
  FileSpreadsheet,
  ShoppingBag,
  Bot,
  BookOpen,
  Activity,
  Sliders,
  Building2,
  Database
} from 'lucide-react';

interface NavItem {
  id: string;
  moduleKey: string;
  label: string;
  icon: React.ReactNode;
  roles: AdminRole[];
}

interface AdminLayoutProps {
  currentTab: string;
  onTabChange: (tabId: string) => void;
  children: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', moduleKey: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} />, roles: ['super_admin', 'admin', 'staff', 'plan_manager', 'payment_manager', 'payment_staff', 'support_agent', 'content_manager', 'listing_reviewer', 'seller_reviewer', 'analyst'] },
  { id: 'feature_control', moduleKey: 'overview', label: 'Feature Controls', icon: <Sliders size={18} />, roles: ['super_admin', 'admin', 'analyst'] },
  { id: 'departments', moduleKey: 'overview', label: 'Departments & Teams', icon: <Building2 size={18} />, roles: ['super_admin', 'admin', 'supervisor', 'staff'] },
  { id: 'agrogpt', moduleKey: 'overview', label: 'AgroGPT Control', icon: <Bot size={18} />, roles: ['super_admin', 'admin', 'analyst'] },
  { id: 'knowledge', moduleKey: 'overview', label: 'Knowledge Library', icon: <BookOpen size={18} />, roles: ['super_admin', 'admin', 'content_manager', 'analyst'] },
  { id: 'data_integrity', moduleKey: 'overview', label: 'Data Integrity', icon: <Database size={18} />, roles: ['super_admin', 'admin', 'analyst'] },
  { id: 'system_health', moduleKey: 'overview', label: 'System & Security', icon: <Activity size={18} />, roles: ['super_admin', 'admin', 'analyst'] },
  { id: 'mart', moduleKey: 'mart', label: 'Agro AI Mart', icon: <ShoppingBag size={18} />, roles: ['super_admin', 'admin', 'staff', 'plan_manager', 'payment_manager', 'support_agent', 'content_manager', 'listing_reviewer', 'seller_reviewer', 'analyst'] },
  { id: 'broadcasts', moduleKey: 'posts_offers', label: 'Posts & Offers', icon: <Megaphone size={18} />, roles: ['super_admin', 'admin', 'staff', 'content_manager', 'plan_manager', 'support_agent', 'analyst'] },
  { id: 'farmer_exports', moduleKey: 'excel_registry', label: 'Excel Data Registry', icon: <FileSpreadsheet size={18} />, roles: ['super_admin', 'admin', 'staff', 'support_agent', 'content_manager', 'analyst', 'plan_manager'] },
  { id: 'plans', moduleKey: 'subscription_plans', label: 'Subscription Plans', icon: <Layers size={18} />, roles: ['super_admin', 'admin', 'plan_manager', 'analyst'] },
  { id: 'users', moduleKey: 'users_roles', label: 'Users & Roles', icon: <Users size={18} />, roles: ['super_admin', 'admin', 'support_agent', 'analyst'] },
  { id: 'payments', moduleKey: 'payment_orders', label: 'Payment Orders', icon: <CreditCard size={18} />, roles: ['super_admin', 'admin', 'staff', 'payment_manager', 'payment_staff', 'support_agent', 'analyst'] },
  { id: 'data_requests', moduleKey: 'data_requests', label: 'Data Requests', icon: <FileText size={18} />, roles: ['super_admin', 'admin', 'staff', 'support_agent', 'analyst'] },
  { id: 'audit_logs', moduleKey: 'audit_logs', label: 'Security Audit Logs', icon: <ShieldCheck size={18} />, roles: ['super_admin', 'admin', 'analyst'] },
];

export const AdminLayout: React.FC<AdminLayoutProps> = ({ currentTab, onTabChange, children }) => {
  const { profile, logout, logoutAllDevices } = useAdminAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const role = profile?.role || 'staff';
  const hierarchyLevel = profile?.hierarchy_level || (role === 'super_admin' ? 'SUPER_ADMIN_HEAD' : role === 'admin' ? 'ADMIN' : 'STAFF');

  const tierLabelMap: Record<string, string> = {
    SUPER_ADMIN_HEAD: 'Level 1 · Super Admin',
    ADMIN: 'Level 2 · Dept Admin',
    SUPERVISOR: 'Level 3 · Supervisor',
    STAFF: 'Level 4 · Staff',
  };

  const roleBadgeColors: Record<string, string> = {
    super_admin: 'bg-[#B91C1C]/20 text-[#FCA5A5] border-[#B91C1C]/40',
    admin: 'bg-[#2D6A4F]/25 text-[#A7F3D0] border-[#40916C]/50',
    supervisor: 'bg-[#D97706]/20 text-[#FDE68A] border-[#F59E0B]/40',
    staff: 'bg-[#1D4ED8]/20 text-[#93C5FD] border-[#3B82F6]/40',
    plan_manager: 'bg-[#2D6A4F]/20 text-[#A7F3D0] border-[#2D6A4F]/40',
    payment_manager: 'bg-[#B26E28]/20 text-[#FCD34D] border-[#B26E28]/40',
    support_agent: 'bg-[#1D4ED8]/20 text-[#93C5FD] border-[#1D4ED8]/40',
    content_manager: 'bg-[#7C3AED]/20 text-[#C4B5FD] border-[#7C3AED]/40',
    analyst: 'bg-[#4B5563]/20 text-[#D1D5DB] border-[#4B5563]/40',
  };

  const allowedNav = NAV_ITEMS.filter(item => {
    if (role === 'super_admin' || hierarchyLevel === 'SUPER_ADMIN_HEAD') return true;
    if (profile?.authorized_modules && profile.authorized_modules.length > 0) {
      return profile.authorized_modules.includes(item.moduleKey);
    }
    return item.roles.includes(role);
  });

  const mobileQuickTabs = allowedNav.slice(0, 4);

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-[#FAF8F5]">
      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] md:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── SIDEBAR ─────────────────────────────────── */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] md:w-64 bg-[#081C15] text-[#E5E7EB] transform transition-transform duration-200 ease-in-out md:relative md:translate-x-0 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="flex flex-col h-full border-r border-[#1B4332]">
          {/* Logo & Platform Name */}
          <div className="p-5 border-b border-[#1B4332]/60 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#40916C] to-[#1B4332] flex items-center justify-center text-white shadow-md font-bold text-lg">
                🌾
              </div>
              <div>
                <h1 className="font-display font-bold text-base text-white tracking-wide">Agro AI</h1>
                <p className="text-[11px] text-[#A7F3D0] uppercase tracking-wider font-semibold">Admin Console</p>
              </div>
            </div>
            <button className="md:hidden text-[#9CA3AF] hover:text-white" onClick={() => setMobileMenuOpen(false)}>
              <X size={20} />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
            <div className="px-3 pb-2 text-[11px] font-semibold text-[#6EE7B7] uppercase tracking-wider">
              Authorized Modules ({allowedNav.length})
            </div>
            {allowedNav.map(item => {
              const active = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onTabChange(item.id);
                    setMobileMenuOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                    active
                      ? 'bg-[#2D6A4F] text-white shadow-sm font-semibold'
                      : 'text-[#9CA3AF] hover:bg-[#1B4332]/60 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={active ? 'text-[#A7F3D0]' : 'text-[#6EE7B7]'}>{item.icon}</span>
                    <span>{item.label}</span>
                  </div>
                  {active && <ChevronRight size={14} className="text-[#A7F3D0]" />}
                </button>
              );
            })}
          </nav>

          {/* User & Role Card */}
          <div className="p-4 border-t border-[#1B4332]/60 bg-[#061610]">
            <div className="flex items-center justify-between mb-2">
              <div className="truncate mr-2">
                <p className="text-xs font-semibold text-white truncate">{profile?.full_name}</p>
                <p className="text-[11px] text-[#9CA3AF] truncate">{profile?.email}</p>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="p-1.5 rounded-lg text-[#9CA3AF] hover:text-red-400 hover:bg-red-950/40 transition cursor-pointer"
              >
                <LogOut size={16} />
              </button>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="text-[10px] font-bold text-[#6EE7B7] uppercase tracking-wider">
                {tierLabelMap[hierarchyLevel] || 'Level 3 · Staff'}
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wider ${roleBadgeColors[role] || 'bg-gray-800 text-gray-300'}`}>
                  {role.replace('_', ' ')}
                </span>
                <span className="flex items-center gap-1 text-[10px] text-[#A7F3D0]">
                  <ShieldCheck size={12} /> RBAC Enforced
                </span>
              </div>
              <button
                onClick={logoutAllDevices}
                className="mt-1 text-left text-[10px] text-[#9CA3AF] hover:text-red-300 underline cursor-pointer"
              >
                Revoke all admin sessions
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 md:h-16 bg-white border-b border-[#E5DFD3] flex items-center justify-between px-4 md:px-6 z-10 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="md:hidden p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl text-[#374151] hover:bg-[#F3EFE6]"
            >
              <Menu size={20} />
            </button>
            <h2 className="font-display text-base md:text-lg font-semibold text-[#1B4332] capitalize truncate">
              {allowedNav.find(n => n.id === currentTab)?.label || currentTab.replace('_', ' ')}
            </h2>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-[#E8F5E9] text-[#2D6A4F] text-xs font-semibold border border-[#C8E6C9]">
              <span className="w-2 h-2 rounded-full bg-[#2D6A4F] animate-pulse"></span>
              {tierLabelMap[hierarchyLevel]}
            </div>
            <a
              href="/"
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-[#2D6A4F] hover:text-[#1B4332] underline whitespace-nowrap"
            >
              ↗ Farmer App
            </a>
          </div>
        </header>

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 pb-24 md:p-8 md:pb-8">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>

        {/* Mobile Bottom Navigation Bar (<768px) — Role-Scoped */}
        <nav
          aria-label="Mobile admin navigation"
          className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-[#081C15] border-t border-[#1B4332] px-1 pt-1 pb-[max(0.35rem,env(safe-area-inset-bottom))] flex items-center justify-around"
        >
          {mobileQuickTabs.map((item) => {
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`flex-1 flex flex-col items-center justify-center min-h-[48px] px-1 py-1 rounded-lg text-[10px] font-semibold transition ${
                  active ? 'text-[#A7F3D0] bg-[#1B4332]/70' : 'text-[#9CA3AF]'
                }`}
              >
                <span>{item.icon}</span>
                <span className="mt-0.5 truncate max-w-[68px]">{item.label.split(' ')[0]}</span>
              </button>
            );
          })}
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="flex-1 flex flex-col items-center justify-center min-h-[48px] px-1 py-1 rounded-lg text-[10px] font-semibold text-[#9CA3AF]"
          >
            <Menu size={18} />
            <span className="mt-0.5">More</span>
          </button>
        </nav>
      </div>
    </div>
  );
};
