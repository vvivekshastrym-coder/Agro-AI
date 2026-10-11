import React, { useState } from 'react';
import { AdminAuthProvider, useAdminAuth } from './context/AdminAuthContext';
import { AdminLogin } from './pages/AdminLogin';
import { AdminLayout } from './components/AdminLayout';
import { DashboardOverview } from './pages/DashboardOverview';
import { PlanManager } from './pages/PlanManager';
import { UserDirectory } from './pages/UserDirectory';
import { PaymentOrders } from './pages/PaymentOrders';
import { DataRequestsQueue } from './pages/DataRequestsQueue';
import { AuditLogs } from './pages/AuditLogs';
import { BroadcastManager } from './pages/BroadcastManager';
import { FarmerDataExport } from './pages/FarmerDataExport';

const AdminAppShell: React.FC = () => {
  const { user, profile, mfaRequired, loading } = useAdminAuth();
  const [currentTab, setCurrentTab] = useState<string>('overview');

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-4 border-[#2D6A4F] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm font-medium text-[#1B4332]">Verifying administrator credentials...</p>
      </div>
    );
  }

  if (!user || !profile || mfaRequired) {
    return <AdminLogin />;
  }

  const renderTabContent = () => {
    switch (currentTab) {
      case 'overview':
        return <DashboardOverview />;
      case 'broadcasts':
        return <BroadcastManager />;
      case 'farmer_exports':
        return <FarmerDataExport />;
      case 'plans':
        return <PlanManager />;
      case 'users':
        return <UserDirectory />;
      case 'payments':
        return <PaymentOrders />;
      case 'data_requests':
        return <DataRequestsQueue />;
      case 'audit_logs':
        return <AuditLogs />;
      default:
        return <DashboardOverview />;
    }
  };

  return (
    <AdminLayout currentTab={currentTab} onTabChange={setCurrentTab}>
      {renderTabContent()}
    </AdminLayout>
  );
};

export default function App() {
  return (
    <AdminAuthProvider>
      <AdminAppShell />
    </AdminAuthProvider>
  );
}
