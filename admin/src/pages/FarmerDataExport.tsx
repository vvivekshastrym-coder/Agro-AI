import React, { useEffect, useState } from 'react';
import { adminFetch, getAdminToken } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import {
  FileSpreadsheet,
  Download,
  HardDrive,
  RefreshCw,
  Users,
  CheckCircle2,
  Calendar,
  Layers,
  Upload,
  AlertTriangle,
  XCircle,
  Eye,
  RotateCcw,
  Send
} from 'lucide-react';

interface ExportSummary {
  total_farmers: number;
  file_persisted_on_disk: boolean;
  excel_file_path: string;
  csv_file_path: string;
  file_size_kb: number;
  last_updated?: string | null;
}

interface ExcelJob {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  target_dataset: string;
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  duplicate_rows_count: number;
  status: string;
  uploaded_by?: string;
  uploaded_by_role?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  published_by?: string;
  published_at?: string;
  review_notes?: string;
  created_at?: string;
}

const SAMPLE_CSV_TEMPLATES: Record<string, string> = {
  mandi_prices: `commodity,variety,market_name,state,district,min_price,modal_price,max_price,unit
Tomato,Hybrid,Mandya APMC,Karnataka,Mandya,1800,2200,2600,quintal
Ragi (Finger Millet),Local,Mysore APMC,Karnataka,Mysore,3200,3500,3800,quintal
Onion,Red,Yeshwanthpur APMC,Karnataka,Bangalore Urban,2100,2500,2900,quintal`,
  mandi_markets: `market_name,district,state,market_type
Channapatna APMC,Ramanagara,Karnataka,Principal Yard
Srirangapatna Sub-Market,Mandya,Karnataka,Sub-Market Yard`,
  camp_registrations: `farmer_name,phone,village,district,state
Kempegowda M,9448012345,Maddur,Mandya,Karnataka
Shanthamma R,9448054321,Malavalli,Mandya,Karnataka`,
  advisories: `title,content,language
Rabi Pulse Sowing Advisory,Apply Rhizobium bio-fertilizer seed treatment before sowing Bengal Gram in black cotton soils.,en
ರಾಗಿ ಬೆಳೆ ನಿರ್ವಹಣೆ,ತೆನೆ ಕಟ್ಟುವ ಹಂತದಲ್ಲಿ ತೇವಾಂಶ ಕೊರತೆಯಾಗದಂತೆ ಎಚ್ಚರವಹಿಸಿ.,kn`
};

export const FarmerDataExport: React.FC = () => {
  const { isAdminOrAbove, hasPermission } = useAdminAuth();
  const [activeSubTab, setActiveSubTab] = useState<'import' | 'export'>('import');

  // Export state
  const [summary, setSummary] = useState<ExportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<'excel' | 'csv' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Import state
  const [jobs, setJobs] = useState<ExcelJob[]>([]);
  const [targetDataset, setTargetDataset] = useState<string>('mandi_prices');
  const [filename, setFilename] = useState<string>('mandi_daily_rates.csv');
  const [csvContent, setCsvContent] = useState<string>(SAMPLE_CSV_TEMPLATES.mandi_prices);
  const [uploading, setUploading] = useState(false);
  const [selectedJobDetail, setSelectedJobDetail] = useState<any | null>(null);
  const [processingJobId, setProcessingJobId] = useState<string | null>(null);

  const canApprove = isAdminOrAbove || hasPermission('excel_registry', 'approve');
  const canPublish = isAdminOrAbove || hasPermission('excel_registry', 'publish');

  const fetchSummaryAndJobs = async () => {
    setLoading(true);
    try {
      const [sumRes, jobsRes] = await Promise.all([
        adminFetch('/api/admin/export/summary'),
        adminFetch('/api/admin/excel-registry/jobs')
      ]);
      if (sumRes.ok) setSummary(await sumRes.json());
      if (jobsRes.ok) setJobs(await jobsRes.json());
    } catch (err: any) {
      setError(err.message || 'Error loading Excel Data Registry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummaryAndJobs();
  }, []);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    const text = await file.text();
    setCsvContent(text);
  };

  const handleUploadAndValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await adminFetch('/api/admin/excel-registry/upload', {
        method: 'POST',
        body: JSON.stringify({
          filename: filename.trim() || 'upload.csv',
          target_dataset: targetDataset,
          csv_content: csvContent
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || 'Upload validation failed');
      }
      setSuccessMsg(
        `Validated "${data.filename}": ${data.valid_rows_count} valid rows, ${data.invalid_rows_count} invalid rows, ${data.duplicate_rows_count} duplicates. Status: PENDING_REVIEW.`
      );
      setSelectedJobDetail(data);
      await fetchSummaryAndJobs();
    } catch (err: any) {
      setError(err.message || 'Failed to validate spreadsheet');
    } finally {
      setUploading(false);
    }
  };

  const handleViewJob = async (jobId: string) => {
    try {
      const res = await adminFetch(`/api/admin/excel-registry/jobs/${jobId}`);
      if (res.ok) {
        setSelectedJobDetail(await res.json());
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleJobAction = async (jobId: string, action: 'approve' | 'publish' | 'reject' | 'rollback') => {
    setProcessingJobId(jobId);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await adminFetch(`/api/admin/excel-registry/jobs/${jobId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ review_notes: `Action ${action} executed from Admin Console` })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || `Failed to ${action} job`);
      }
      setSuccessMsg(`Import job ${jobId.slice(0, 8)} successfully updated to ${data.status}!`);
      await fetchSummaryAndJobs();
      if (selectedJobDetail?.id === jobId) {
        await handleViewJob(jobId);
      }
    } catch (err: any) {
      setError(err.message || `Action ${action} failed`);
    } finally {
      setProcessingJobId(null);
    }
  };

  const downloadErrorReport = async (jobId: string) => {
    const token = await getAdminToken();
    const res = await fetch(`/api/admin/excel-registry/jobs/${jobId}/errors-csv`, {
      headers: { Authorization: token ? `Bearer ${token}` : '' }
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `import_errors_${jobId.slice(0, 8)}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

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
          <h1 className="text-2xl font-display font-bold text-[#1B4332]">Excel Data Registry</h1>
          <p className="text-sm text-[#4B5563]">
            Import, validate, preview, approve, and publish operational spreadsheets — plus download live Farmer Registry workbooks.
          </p>
        </div>
        <button
          onClick={fetchSummaryAndJobs}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#E5DFD3] text-sm font-semibold text-[#1B4332] hover:bg-[#F3EFE6] transition shadow-xs cursor-pointer"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh Registry
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex border-b border-[#E5DFD3] gap-6 text-sm font-semibold">
        <button
          onClick={() => setActiveSubTab('import')}
          className={`pb-3 transition flex items-center gap-2 cursor-pointer ${
            activeSubTab === 'import'
              ? 'text-[#1B4332] border-b-2 border-[#1B4332]'
              : 'text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <Upload size={16} />
          <span>Import, Validate & Publish Spreadsheets</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-[#E8F5E9] text-[#2D6A4F]">
            {jobs.length}
          </span>
        </button>
        <button
          onClick={() => setActiveSubTab('export')}
          className={`pb-3 transition flex items-center gap-2 cursor-pointer ${
            activeSubTab === 'export'
              ? 'text-[#1B4332] border-b-2 border-[#1B4332]'
              : 'text-[#6B7280] hover:text-[#1F2937]'
          }`}
        >
          <Download size={16} />
          <span>Export Farmer Registry (.XLSX / .CSV)</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold">Dismiss</button>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-bold">Dismiss</button>
        </div>
      )}

      {activeSubTab === 'import' ? (
        <div className="space-y-6">
          {/* Upload & Validation Form */}
          <form onSubmit={handleUploadAndValidate} className="bg-white rounded-2xl border border-[#E5DFD3] p-6 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="font-bold text-base text-[#1B4332]">1. Upload & Validate Operational Spreadsheet</h2>
                <p className="text-xs text-[#6B7280]">
                  Staff can upload CSV/XLSX data for validation (`PENDING_REVIEW`). Admin or Super Admin Head approves and publishes validated rows.
                </p>
              </div>
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-[#FAF8F5] border border-[#E5DFD3] text-[#374151]">
                Max size: 10 MB · Formats: .CSV, .XLSX
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#374151] mb-1">Target Operational Dataset</label>
                <select
                  value={targetDataset}
                  onChange={(e) => {
                    const ds = e.target.value;
                    setTargetDataset(ds);
                    setFilename(`${ds}_import.csv`);
                    if (SAMPLE_CSV_TEMPLATES[ds]) setCsvContent(SAMPLE_CSV_TEMPLATES[ds]);
                  }}
                  className="w-full px-3 py-2 rounded-xl border border-[#D1D5DB] text-sm text-[#1B4332] bg-white"
                >
                  <option value="mandi_prices">Mandi Commodity Prices (mandi_prices)</option>
                  <option value="mandi_markets">APMC Market Directory (mandi_markets)</option>
                  <option value="camp_registrations">Farmer Camp Registrations (camp_registrations)</option>
                  <option value="advisories">Multilingual Crop Advisories (advisories)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#374151] mb-1">Spreadsheet Filename</label>
                <input
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-[#D1D5DB] text-sm text-[#1B4332]"
                  placeholder="e.g. karnataka_mandi_rates.csv"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#374151] mb-1">Select Local .CSV File (Optional)</label>
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileSelect}
                  className="w-full text-xs text-[#4B5563] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#E8F5E9] file:text-[#1B4332]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#374151] mb-1">
                Spreadsheet Rows (CSV Content Preview / Editor)
              </label>
              <textarea
                rows={5}
                value={csvContent}
                onChange={(e) => setCsvContent(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#D1D5DB] font-mono text-xs text-[#111827] bg-[#FAF8F5]"
              />
            </div>

            <div className="flex items-center justify-end">
              <button
                type="submit"
                disabled={uploading}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#1B4332] hover:bg-[#2D6A4F] text-white text-sm font-semibold shadow-xs transition cursor-pointer disabled:opacity-50"
              >
                <Upload size={16} />
                {uploading ? 'Validating Rows & Checking Duplicates...' : 'Validate & Submit for Review'}
              </button>
            </div>
          </form>

          {/* Selected Job Preview & Row-Level Validation Report */}
          {selectedJobDetail && (
            <div className="bg-white rounded-2xl border border-[#2D6A4F]/40 p-6 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E5DFD3] pb-3">
                <div>
                  <h3 className="font-bold text-base text-[#1B4332]">
                    Validation Preview: {selectedJobDetail.filename} ({selectedJobDetail.target_dataset})
                  </h3>
                  <p className="text-xs text-[#6B7280]">
                    Total Rows: {selectedJobDetail.total_rows} · Valid: {selectedJobDetail.valid_rows_count} · Invalid: {selectedJobDetail.invalid_rows_count} · Duplicates: {selectedJobDetail.duplicate_rows_count}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {selectedJobDetail.invalid_rows_count > 0 && (
                    <button
                      onClick={() => downloadErrorReport(selectedJobDetail.id)}
                      className="px-3 py-1.5 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs font-semibold hover:bg-red-100 cursor-pointer"
                    >
                      Download Invalid Rows (.CSV)
                    </button>
                  )}
                  <button
                    onClick={() => setSelectedJobDetail(null)}
                    className="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs font-semibold cursor-pointer"
                  >
                    Close Preview
                  </button>
                </div>
              </div>

              {selectedJobDetail.error_rows && selectedJobDetail.error_rows.length > 0 && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 space-y-1.5">
                  <div className="text-xs font-bold text-red-800">Row-Level Validation Errors ({selectedJobDetail.error_rows.length}):</div>
                  {selectedJobDetail.error_rows.slice(0, 10).map((err: any, i: number) => (
                    <div key={i} className="text-xs text-red-700 font-mono">
                      • Row {err.row} [{err.field}]: {err.error}
                    </div>
                  ))}
                </div>
              )}

              {selectedJobDetail.preview_rows && selectedJobDetail.preview_rows.length > 0 && (
                <div>
                  <div className="text-xs font-bold text-[#1B4332] mb-2">
                    Validated Rows Ready for Publication ({selectedJobDetail.preview_rows.length}):
                  </div>
                  <pre className="p-3 rounded-xl bg-[#081C15] text-[#A7F3D0] text-xs font-mono overflow-x-auto max-h-52">
                    {JSON.stringify(selectedJobDetail.preview_rows.slice(0, 10), null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Import Jobs Approval & Publication Queue */}
          <div className="bg-white rounded-2xl border border-[#E5DFD3] shadow-xs overflow-hidden">
            <div className="p-5 border-b border-[#E5DFD3] bg-[#FAF8F5]">
              <h2 className="font-bold text-sm text-[#1B4332]">2. Excel Import Jobs Queue (PENDING_REVIEW → APPROVED → PUBLISHED)</h2>
              <p className="text-xs text-[#6B7280] mt-0.5">
                Every spreadsheet import is validated, audited, and supports one-click rollback if needed.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-[#374151]">
                <thead className="bg-[#FAF8F5] text-xs uppercase font-semibold text-[#6B7280] border-b border-[#E5DFD3]">
                  <tr>
                    <th className="px-5 py-3.5">Filename & Dataset</th>
                    <th className="px-5 py-3.5">Validation Summary</th>
                    <th className="px-5 py-3.5">Status</th>
                    <th className="px-5 py-3.5">Uploaded By</th>
                    <th className="px-5 py-3.5 text-right">Workflow Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5DFD3]">
                  {jobs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-10 text-center text-sm text-[#6B7280]">
                        No spreadsheet import jobs yet. Upload a CSV or XLSX above to validate and preview.
                      </td>
                    </tr>
                  ) : (
                    jobs.map((j) => (
                      <tr key={j.id} className="hover:bg-[#FAF8F5]/60">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-[#1B4332]">{j.filename}</div>
                          <div className="text-xs text-[#6B7280] font-mono">{j.target_dataset}</div>
                        </td>
                        <td className="px-5 py-4 text-xs">
                          <span className="text-emerald-700 font-semibold">{j.valid_rows_count} valid</span>
                          <span className="mx-1.5 text-gray-300">|</span>
                          <span className={j.invalid_rows_count > 0 ? 'text-red-600 font-semibold' : 'text-gray-500'}>
                            {j.invalid_rows_count} invalid
                          </span>
                          <span className="mx-1.5 text-gray-300">|</span>
                          <span className="text-amber-700">{j.duplicate_rows_count} dup</span>
                        </td>
                        <td className="px-5 py-4">
                          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                            j.status === 'PUBLISHED'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : j.status === 'APPROVED'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : j.status === 'REJECTED' || j.status === 'ROLLED_BACK'
                              ? 'bg-red-50 text-red-700 border-red-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}>
                            {j.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-xs text-[#6B7280]">
                          <div>{j.uploaded_by_role || 'staff'}</div>
                          <div className="text-[10px]">{j.created_at ? new Date(j.created_at).toLocaleString() : ''}</div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleViewJob(j.id)}
                              className="px-2.5 py-1 rounded-lg bg-[#FAF8F5] border border-[#E5DFD3] text-xs font-medium text-[#1B4332] hover:bg-[#E8F5E9] cursor-pointer"
                            >
                              <Eye size={13} className="inline mr-1" /> Preview
                            </button>
                            {canApprove && j.status === 'PENDING_REVIEW' && j.valid_rows_count > 0 && (
                              <button
                                disabled={processingJobId === j.id}
                                onClick={() => handleJobAction(j.id, 'approve')}
                                className="px-2.5 py-1 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 cursor-pointer disabled:opacity-50"
                              >
                                Approve
                              </button>
                            )}
                            {canPublish && (j.status === 'APPROVED' || j.status === 'PENDING_REVIEW') && j.valid_rows_count > 0 && (
                              <button
                                disabled={processingJobId === j.id}
                                onClick={() => handleJobAction(j.id, 'publish')}
                                className="px-2.5 py-1 rounded-lg bg-[#2D6A4F] text-white text-xs font-semibold hover:bg-[#1B4332] cursor-pointer disabled:opacity-50"
                              >
                                <Send size={12} className="inline mr-1" /> Publish
                              </button>
                            )}
                            {canApprove && j.status === 'PENDING_REVIEW' && (
                              <button
                                disabled={processingJobId === j.id}
                                onClick={() => handleJobAction(j.id, 'reject')}
                                className="px-2.5 py-1 rounded-lg bg-red-100 text-red-700 text-xs font-semibold hover:bg-red-200 cursor-pointer disabled:opacity-50"
                              >
                                <XCircle size={12} className="inline mr-1" /> Reject
                              </button>
                            )}
                            {canPublish && j.status === 'PUBLISHED' && (
                              <button
                                disabled={processingJobId === j.id}
                                onClick={() => handleJobAction(j.id, 'rollback')}
                                className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-800 text-xs font-semibold hover:bg-amber-200 cursor-pointer disabled:opacity-50"
                              >
                                <RotateCcw size={12} className="inline mr-1" /> Rollback
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
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
        </div>
      )}
    </div>
  );
};
