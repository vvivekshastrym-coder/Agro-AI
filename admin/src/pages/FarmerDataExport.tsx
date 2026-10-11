import React, { useEffect, useState } from 'react';
import { adminFetch, getAdminToken } from '../lib/api';
import {
  FileSpreadsheet,
  Download,
  HardDrive,
  RefreshCw,
  Users,
  CheckCircle2,
  Calendar,
  Layers,
  MapPin,
  Sparkles,
  ShieldCheck
} from 'lucide-react';

interface ExportSummary {
  total_farmers: number;
  file_persisted_on_disk: boolean;
  excel_file_path: string;
  csv_file_path: string;
  file_size_kb: number;
  last_updated?: string | null;
}

export const FarmerDataExport: React.FC = () => {
  const [summary, setSummary] = useState<ExportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<'excel' | 'csv' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/export/summary');
      if (!res.ok) throw new Error('Failed to load export summary');
      const data = await res.json();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Error loading export metadata');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();

    const timer = setInterval(() => {
      fetchSummary();
    }, 12000);

    const handleFocus = () => {
      fetchSummary();
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  const downloadFile = async (type: 'excel' | 'csv') => {
    setDownloading(type);
    try {
      const endpoint = type === 'excel' ? '/api/admin/export/farmers-excel' : '/api/admin/export/farmers-csv';
      const token = await getAdminToken();
      const res = await fetch(endpoint, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
        },
      });

      if (!res.ok) throw new Error(`Download failed with status ${res.status}`);

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = type === 'excel' ? 'Agro_AI_Farmers_Registry.xlsx' : 'Agro_AI_Farmers_Registry.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(err.message || 'Failed to download file');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Farmer Data Registry & Excel Sheets</h1>
          <p className="text-sm text-[#4B5563]">
            Automatic multi-sheet Microsoft Excel (.xlsx) and CSV exports with local disk persistence.
          </p>
        </div>
        <button
          onClick={fetchSummary}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-xs cursor-pointer"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh Registry Data
        </button>
      </div>

      {/* Main Download Card */}
      <div className="bg-gradient-to-br from-[#1B4332] to-[#081C15] text-white rounded-3xl p-6 sm:p-8 shadow-md">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-[#A7F3D0] text-xs font-semibold mb-4 backdrop-blur-xs">
            <FileSpreadsheet size={14} />
            <span>Official Microsoft Excel (.xlsx) & RFC 4180 CSV</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-display font-bold mb-2">
            Download Registered Farmers Data
          </h2>
          <p className="text-sm text-[#D1FAE5] leading-relaxed mb-6">
            Includes all registered farmers, contact info, farm locations (State/District/Pincode), total & leased acreage, cultivated crop records, active plan subscriptions, and leaf diagnosis counts.
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <button
              onClick={() => downloadFile('excel')}
              disabled={downloading !== null}
              className="px-5 py-3 rounded-xl bg-white text-[#1B4332] hover:bg-[#F0FDF4] font-semibold text-sm flex items-center gap-2.5 shadow-sm transition disabled:opacity-50 cursor-pointer"
            >
              <Download size={18} className="text-[#2D6A4F]" />
              {downloading === 'excel' ? 'Preparing Excel (.xlsx)...' : 'Download Excel Registry (.XLSX)'}
            </button>

            <button
              onClick={() => downloadFile('csv')}
              disabled={downloading !== null}
              className="px-5 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-sm flex items-center gap-2.5 border border-white/20 transition disabled:opacity-50 cursor-pointer"
            >
              <Download size={18} />
              {downloading === 'csv' ? 'Preparing CSV...' : 'Download CSV (.CSV)'}
            </button>
          </div>
        </div>
      </div>

      {/* Local Disk Storage & Verification Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-[#E8F5E9] text-[#2D6A4F] flex items-center justify-center">
              <Users size={18} />
            </div>
            <div>
              <div className="text-xs text-[#6B7280]">Registered Farmers</div>
              <div className="text-xl font-bold font-display text-[#1B4332]">
                {summary ? summary.total_farmers : '—'}
              </div>
            </div>
          </div>
          <p className="text-[11px] text-[#6B7280]">All farmer accounts currently registered in database.</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-[#DBEAFE] text-[#1D4ED8] flex items-center justify-center">
              <HardDrive size={18} />
            </div>
            <div>
              <div className="text-xs text-[#6B7280]">Server Disk Backup</div>
              <div className="text-xl font-bold font-display text-[#1D4ED8]">
                {summary?.file_persisted_on_disk ? 'Saved on Disk' : 'Generating'}
              </div>
            </div>
          </div>
          <div className="text-[11px] text-[#6B7280] truncate font-mono" title={summary?.excel_file_path}>
            {summary?.file_size_kb ? `${summary.file_size_kb} KB stored` : 'Persistent export'}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E5DFD3] shadow-xs">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-[#FEF3C7] text-[#D97706] flex items-center justify-center">
              <Calendar size={18} />
            </div>
            <div>
              <div className="text-xs text-[#6B7280]">Last Export Sync</div>
              <div className="text-sm font-bold text-[#92400E]">
                {summary?.last_updated ? new Date(summary.last_updated).toLocaleTimeString() : 'Current Live'}
              </div>
            </div>
          </div>
          <p className="text-[11px] text-[#6B7280]">Auto-refreshed upon every registry export request.</p>
        </div>
      </div>

      {/* Spreadsheet Columns Reference Table */}
      <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-xs p-6">
        <h3 className="font-bold text-sm text-[#1B4332] mb-1">Exported Excel Data Fields</h3>
        <p className="text-xs text-[#6B7280] mb-4">
          The generated Excel spreadsheet includes two organized worksheets:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-[#FAF8F5] border border-[#E5DFD3]">
            <div className="font-bold text-[#1B4332] flex items-center gap-2 mb-2">
              <FileSpreadsheet size={15} />
              Sheet 1: Executive Summary
            </div>
            <ul className="space-y-1 text-[#4B5563]">
              <li>• Total Registered Farmers Count</li>
              <li>• Active vs Suspended Accounts Ratio</li>
              <li>• Verified Contact Statuses</li>
              <li>• Total Farmland Acreage Across States</li>
              <li>• Active Premium Plan Subscriptions</li>
              <li>• AI Leaf Disease Scans Executed</li>
            </ul>
          </div>

          <div className="p-4 rounded-xl bg-[#FAF8F5] border border-[#E5DFD3]">
            <div className="font-bold text-[#1B4332] flex items-center gap-2 mb-2">
              <Layers size={15} />
              Sheet 2: Farmers Registry
            </div>
            <ul className="space-y-1 text-[#4B5563]">
              <li>• Full Name, Phone, Email & Preferred Language</li>
              <li>• State, District, Pincode</li>
              <li>• Total Acres, Owned Acres, Leased Acres</li>
              <li>• Soil Type, Irrigation Method & Water Source</li>
              <li>• Cultivated Crops (Sugarcane, Cotton, Wheat, Rice)</li>
              <li>• Subscription Plan Name, Status & Valid Date</li>
            </ul>
          </div>
        </div>

        {summary?.excel_file_path && (
          <div className="mt-4 pt-4 border-t border-[#F3EFE6] flex items-center justify-between text-xs text-[#6B7280]">
            <div>
              <span className="font-semibold">Local Storage Path:</span>{' '}
              <code className="bg-[#FAF8F5] px-2 py-0.5 rounded text-[#1B4332] border border-[#E5DFD3]">
                {summary.excel_file_path}
              </code>
            </div>
            <span className="text-emerald-700 font-semibold flex items-center gap-1">
              <CheckCircle2 size={13} /> Stored on Disk
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
