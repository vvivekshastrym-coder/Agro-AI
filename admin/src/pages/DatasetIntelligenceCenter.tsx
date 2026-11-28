import React, { useEffect, useState } from 'react';
import { adminFetch } from '../lib/api';
import { useAdminAuth } from '../context/AdminAuthContext';
import {
  Upload,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Eye,
  Database,
  ShieldCheck,
  PauseCircle,
  Cpu,
} from 'lucide-react';

interface DatasetRow {
  id: string;
  name: string;
  slug: string;
  version: number;
  parent_dataset_id: string | null;
  file_format: string;
  subject: string;
  crop: string | null;
  region: string;
  language: string;
  source_name: string | null;
  publisher: string | null;
  original_publication_date: string | null;
  trust_level: string;
  approval_status: string;
  ingestion_status: string;
  total_records: number;
  valid_records: number;
  duplicate_records: number;
  invalid_records: number;
  conflict_records: number;
  stale_records: number;
  review_notes: string | null;
  created_at: string | null;
  preview_rows?: Record<string, any>[];
  validation_errors?: Array<{ row: number; field: string; error: string }>;
  conflicts_detected?: Array<{ row: number; crop?: string; topic?: string; conflict_type?: string; dataset_claim?: string; official_source?: string; official_rule?: string }>;
}

export const DatasetIntelligenceCenter: React.FC = () => {
  const { profile, isAdminOrAbove } = useAdminAuth();
  const isSuperAdmin = profile?.role === 'super_admin' || profile?.hierarchy_level === 'SUPER_ADMIN_HEAD';

  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [inspectDs, setInspectDs] = useState<DatasetRow | null>(null);

  // Upload form state
  const [file, setFile] = useState<File | null>(null);
  const [dsName, setDsName] = useState('');
  const [subject, setSubject] = useState('');
  const [crop, setCrop] = useState('');
  const [region, setRegion] = useState('Karnataka');
  const [language, setLanguage] = useState('en');
  const [sourceName, setSourceName] = useState('');
  const [publisher, setPublisher] = useState('');
  const [pubDate, setPubDate] = useState('');
  const [replaceId, setReplaceId] = useState('');
  const [uploading, setUploading] = useState(false);

  // Hybrid RAG Test state
  const [testQuery, setTestQuery] = useState('');
  const [testCrop, setTestCrop] = useState('');
  const [ragResult, setRagResult] = useState<any>(null);
  const [testingRag, setTestingRag] = useState(false);

  const loadOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/intelligence/overview');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setOverview(await res.json());
    } catch (e: any) {
      setError(e.message || 'Failed to load Dataset & API Intelligence overview.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOverview();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Select a CSV, XLSX, JSON, PDF, or TXT dataset file first.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      if (dsName.trim()) fd.append('name', dsName.trim());
      if (subject) fd.append('subject', subject);
      if (crop.trim()) fd.append('crop', crop.trim());
      if (region.trim()) fd.append('region', region.trim());
      if (language) fd.append('language', language);
      if (sourceName.trim()) fd.append('source_name', sourceName.trim());
      if (publisher.trim()) fd.append('publisher', publisher.trim());
      if (pubDate.trim()) fd.append('original_publication_date', pubDate.trim());
      if (replaceId) fd.append('replace_dataset_id', replaceId);

      const res = await adminFetch('/api/admin/datasets/upload', { method: 'POST', body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.detail?.error?.message || `Upload failed (HTTP ${res.status})`);
      setInspectDs(body);
      setFile(null);
      setDsName('');
      await loadOverview();
    } catch (err: any) {
      setError(err.message || 'Dataset upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const openDetails = async (id: string) => {
    setBusyId(id);
    try {
      const res = await adminFetch(`/api/admin/datasets/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setInspectDs(await res.json());
    } catch (err: any) {
      setError(err.message || 'Could not load dataset preview.');
    } finally {
      setBusyId(null);
    }
  };

  const decideDataset = async (id: string, action: 'approve' | 'reject' | 'deactivate' | 'reprocess', trustLevel = 'community_curated') => {
    const notes = window.prompt(`Review notes for ${action.toUpperCase()}:`, `${action} after admin inspection`) || '';
    setBusyId(id);
    setError(null);
    try {
      const res = await adminFetch(`/api/admin/datasets/${id}/decide`, {
        method: 'POST',
        body: JSON.stringify({ action, trust_level: trustLevel, review_notes: notes }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.detail?.error?.message || `Action failed (HTTP ${res.status})`);
      setInspectDs(body);
      await loadOverview();
    } catch (err: any) {
      setError(err.message || 'Dataset action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const runRagTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testQuery.trim()) return;
    setTestingRag(true);
    setError(null);
    try {
      const res = await adminFetch('/api/admin/intelligence/search-test', {
        method: 'POST',
        body: JSON.stringify({ query: testQuery.trim(), crop: testCrop.trim() || null, state: 'Karnataka', language: 'en' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRagResult(await res.json());
    } catch (err: any) {
      setError(err.message || 'RAG search test failed.');
    } finally {
      setTestingRag(false);
    }
  };

  const statusBadge = (st: string) => {
    if (st === 'approved') return 'bg-[#D1FAE5] text-[#065F46]';
    if (st === 'pending_review') return 'bg-[#FEF3C7] text-[#92400E]';
    if (st === 'rejected' || st === 'deactivated') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-700';
  };

  const evalRep = overview?.models_and_diagnosis?.diagnosis_eval_report;
  const evalMetrics = evalRep?.summary_metrics;

  return (
    <div className="space-y-6 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-[#081C15]">Dataset, Hybrid RAG & API Intelligence</h2>
          <p className="text-xs sm:text-sm text-[#4B5563]">
            Ingest, validate, deduplicate, preview, and verify agricultural datasets alongside live APIs and calibrated AI models.
          </p>
        </div>
        <button
          onClick={loadOverview}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold hover:bg-[#2D6A4F] transition cursor-pointer self-start"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh Telemetry
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-2">
          <AlertTriangle size={16} /> <span>{error}</span>
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-white border border-[#E5E0D8] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280] uppercase">Datasets Registered</div>
          <div className="mt-1 text-2xl font-bold text-[#081C15]">{overview?.dataset_totals?.count ?? 0}</div>
          <div className="mt-1 text-xs text-[#2D6A4F]">
            {overview?.dataset_totals?.approved ?? 0} approved · {overview?.dataset_totals?.pending_review ?? 0} pending review
          </div>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-[#E5E0D8] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280] uppercase">Hybrid RAG Chunks</div>
          <div className="mt-1 text-2xl font-bold text-[#081C15]">{overview?.knowledge_index?.active_chunks ?? 0}</div>
          <div className="mt-1 text-xs text-[#4B5563]">
            {overview?.knowledge_index?.official_kb_chunks ?? 0} official KB · {overview?.knowledge_index?.approved_dataset_chunks ?? 0} dataset
          </div>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-[#E5E0D8] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280] uppercase">Hygiene Gatekeeper</div>
          <div className="mt-1 text-2xl font-bold text-[#081C15]">{overview?.dataset_totals?.total_duplicates_blocked ?? 0}</div>
          <div className="mt-1 text-xs text-amber-700">
            duplicates stripped · {overview?.dataset_totals?.total_conflicts_flagged ?? 0} conflicts flagged
          </div>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-[#E5E0D8] shadow-xs">
          <div className="text-xs font-semibold text-[#6B7280] uppercase">Evidence Verifications</div>
          <div className="mt-1 text-2xl font-bold text-[#081C15]">{overview?.evidence_verification?.total_evaluated ?? 0}</div>
          <div className="mt-1 text-xs text-[#4B5563]">
            avg {overview?.evidence_verification?.avg_chunks_retrieved ?? 0} chunks / query
          </div>
        </div>
      </div>

      {/* Multi-Format Dataset Uploader */}
      <div className="p-5 rounded-2xl bg-white border border-[#E5E0D8] space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-base font-bold text-[#081C15] flex items-center gap-2">
            <Upload size={18} className="text-[#2D6A4F]" /> Import & Validate Agricultural Dataset
          </h3>
          <span className="text-[11px] px-2.5 py-1 rounded-full bg-[#FFF8EC] border border-[#F59E0B]/40 text-[#92400E] font-medium">
            Zero Auto-Trust: Staged as pending_review until previewed & approved
          </span>
        </div>

        <form onSubmit={handleUpload} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold text-[#374151] mb-1">Dataset File (CSV, XLSX, JSON, PDF, TXT)</label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.json,.pdf,.txt"
              onChange={e => setFile(e.target.files?.[0] || null)}
              className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2 bg-[#FAF8F5]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Dataset Title</label>
            <input
              type="text"
              value={dsName}
              onChange={e => setDsName(e.target.value)}
              placeholder="e.g. UAS Bengaluru Ragi Advisory"
              className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Subject</label>
            <select value={subject} onChange={e => setSubject(e.target.value)} className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2 bg-white">
              <option value="">Auto-detect subject</option>
              <option value="crop_disease">Crop & Disease Info</option>
              <option value="treatments">Organic & Chemical Treatments</option>
              <option value="soil_fertilizer">Soil & Fertilizer Data</option>
              <option value="weather_rainfall">Weather & Rainfall Data</option>
              <option value="mandi_prices">Mandi Prices & Market Data</option>
              <option value="plant_images">Plant Disease Image Manifest</option>
              <option value="general_agronomy">General Agronomy</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Primary Crop (optional)</label>
            <input type="text" value={crop} onChange={e => setCrop(e.target.value)} placeholder="Auto-detect or e.g. Ragi" className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Region / State</label>
            <input type="text" value={region} onChange={e => setRegion(e.target.value)} className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Publisher / Institution</label>
            <input type="text" value={publisher} onChange={e => setPublisher(e.target.value)} placeholder="e.g. ICAR / KVK Mandya" className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Publication Date</label>
            <input type="text" value={pubDate} onChange={e => setPubDate(e.target.value)} placeholder="YYYY-MM-DD or YYYY" className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Language</label>
            <select value={language} onChange={e => setLanguage(e.target.value)} className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2 bg-white">
              <option value="en">English (en)</option>
              <option value="kn">Kannada (kn)</option>
              <option value="hi">Hindi (hi)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Source Name / Citation</label>
            <input type="text" value={sourceName} onChange={e => setSourceName(e.target.value)} placeholder="Source document title" className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#374151] mb-1">Replace Existing Dataset (Version++)</label>
            <select value={replaceId} onChange={e => setReplaceId(e.target.value)} className="w-full text-xs border border-[#D1D5DB] rounded-xl px-3 py-2 bg-white">
              <option value="">New standalone dataset</option>
              {(overview?.datasets || []).map((d: DatasetRow) => (
                <option key={d.id} value={d.id}>{d.name} (v{d.version})</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={uploading}
              className="w-full py-2 px-4 rounded-xl bg-[#2D6A4F] text-white text-xs font-semibold hover:bg-[#1B4332] transition cursor-pointer"
            >
              {uploading ? 'Validating & Staging...' : 'Upload & Run Hygiene Check'}
            </button>
          </div>
        </form>
      </div>

      {/* Dataset Preview & Conflict Inspector Modal/Drawer */}
      {inspectDs && (
        <div className="p-5 rounded-2xl bg-[#FFF8EC] border border-[#D97706]/40 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h4 className="text-sm font-bold text-[#081C15]">
                Preview & Hygiene Audit: {inspectDs.name} (v{inspectDs.version} · {inspectDs.file_format.toUpperCase()})
              </h4>
              <p className="text-xs text-[#4B5563]">
                Valid: <b>{inspectDs.valid_records}</b> · Duplicates Removed: <b>{inspectDs.duplicate_records}</b> · Validation Failures: <b>{inspectDs.invalid_records}</b> · Conflicts: <b>{inspectDs.conflict_records}</b>
              </p>
            </div>
            <button onClick={() => setInspectDs(null)} className="text-xs font-semibold text-[#92400E] underline cursor-pointer">Close Preview</button>
          </div>

          {(inspectDs.conflicts_detected || []).length > 0 && (
            <div className="p-3 rounded-xl bg-amber-100/80 border border-amber-300 text-xs space-y-1">
              <div className="font-bold text-amber-900">Conflicts / Safety Flags Detected ({inspectDs.conflicts_detected?.length}):</div>
              {inspectDs.conflicts_detected?.slice(0, 5).map((c, idx) => (
                <div key={idx} className="text-amber-950">
                  • Row {c.row} ({c.crop || 'general'} — {c.conflict_type}): {c.official_source || c.official_rule}
                </div>
              ))}
            </div>
          )}

          {(inspectDs.validation_errors || []).length > 0 && (
            <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs space-y-1">
              <div className="font-bold text-red-900">Validation Notes / Rejected Rows ({inspectDs.validation_errors?.length}):</div>
              {inspectDs.validation_errors?.slice(0, 5).map((v, idx) => (
                <div key={idx} className="text-red-800">• Row {v.row} [{v.field}]: {v.error}</div>
              ))}
            </div>
          )}

          <div className="overflow-x-auto bg-white rounded-xl border border-[#E5E0D8] p-3">
            <div className="text-xs font-semibold text-[#374151] mb-2">Sample Staged Records (Preview Before Activation)</div>
            <pre className="text-[11px] text-[#1F2937] whitespace-pre-wrap break-words max-h-52 overflow-y-auto">
              {JSON.stringify((inspectDs.preview_rows || []).slice(0, 5), null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Imported Datasets Registry Table */}
      <div className="p-5 rounded-2xl bg-white border border-[#E5E0D8] space-y-3">
        <h3 className="text-base font-bold text-[#081C15] flex items-center gap-2">
          <Database size={18} className="text-[#2D6A4F]" /> Dataset Version & Approval Registry
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs min-w-[780px]">
            <thead>
              <tr className="border-b border-[#E5E0D8] text-[#6B7280] uppercase text-[11px]">
                <th className="py-2.5 pr-3">Dataset & Version</th>
                <th className="py-2.5 px-3">Subject / Crop</th>
                <th className="py-2.5 px-3">Publisher & Date</th>
                <th className="py-2.5 px-3">Records / Hygiene</th>
                <th className="py-2.5 px-3">Status & Trust</th>
                <th className="py-2.5 pl-3">Authorized Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F0EA]">
              {(overview?.datasets || []).map((d: DatasetRow) => (
                <tr key={d.id} className="hover:bg-[#FAF8F5]">
                  <td className="py-3 pr-3">
                    <div className="font-semibold text-[#081C15]">{d.name}</div>
                    <div className="text-[11px] text-[#6B7280]">v{d.version} · {d.file_format.toUpperCase()} · {d.language.toUpperCase()}</div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-medium text-[#1F2937]">{d.subject.replace(/_/g, ' ')}</div>
                    <div className="text-[11px] text-[#6B7280]">{d.crop || 'Multi-crop'} · {d.region}</div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="text-[#1F2937] truncate max-w-[180px]">{d.publisher || 'Unspecified'}</div>
                    <div className="text-[11px] text-[#6B7280]">Pub: {d.original_publication_date || 'Undated'}</div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-[#065F46]">{d.valid_records.toLocaleString()} clean</div>
                    <div className="text-[11px] text-[#6B7280]">
                      {d.duplicate_records} dup · {d.invalid_records} err · {d.conflict_records} conflict
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${statusBadge(d.approval_status)}`}>
                      {d.approval_status.replace('_', ' ')}
                    </span>
                    <div className="text-[10px] text-[#6B7280] mt-1">{d.trust_level.replace('_', ' ')}</div>
                  </td>
                  <td className="py-3 pl-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        onClick={() => openDetails(d.id)}
                        disabled={busyId === d.id}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-[#D1D5DB] text-[#1F2937] hover:bg-gray-50 cursor-pointer"
                      >
                        <Eye size={12} /> Preview
                      </button>
                      {isAdminOrAbove && d.approval_status !== 'approved' && (
                        <button
                          onClick={() => decideDataset(d.id, 'approve', 'community_curated')}
                          disabled={busyId === d.id}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#2D6A4F] text-white hover:bg-[#1B4332] cursor-pointer"
                        >
                          <CheckCircle2 size={12} /> Approve
                        </button>
                      )}
                      {isSuperAdmin && d.approval_status !== 'approved' && (
                        <button
                          onClick={() => decideDataset(d.id, 'approve', 'official_verified')}
                          disabled={busyId === d.id}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#081C15] text-[#A7F3D0] cursor-pointer"
                        >
                          <ShieldCheck size={12} /> Approve Official
                        </button>
                      )}
                      {isAdminOrAbove && d.approval_status === 'approved' && (
                        <>
                          <button
                            onClick={() => decideDataset(d.id, 'reprocess')}
                            disabled={busyId === d.id}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-[#2D6A4F] text-[#2D6A4F] cursor-pointer"
                          >
                            <RefreshCw size={12} /> Reprocess
                          </button>
                          <button
                            onClick={() => decideDataset(d.id, 'deactivate')}
                            disabled={busyId === d.id}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-amber-400 text-amber-800 cursor-pointer"
                          >
                            <PauseCircle size={12} /> Deactivate
                          </button>
                        </>
                      )}
                      {isAdminOrAbove && d.approval_status === 'pending_review' && (
                        <button
                          onClick={() => decideDataset(d.id, 'reject')}
                          disabled={busyId === d.id}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-red-300 text-red-700 cursor-pointer"
                        >
                          <XCircle size={12} /> Reject
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Measured Leaf Diagnosis Evaluation & Calibration Metrics */}
      <div className="p-5 rounded-2xl bg-white border border-[#E5E0D8] space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-base font-bold text-[#081C15] flex items-center gap-2">
            <Cpu size={18} className="text-[#2D6A4F]" /> Measured Two-Stage Vision Evaluation (Held-Out Test Split)
          </h3>
          <span className="text-[11px] text-[#6B7280]">
            {evalRep ? `Model: ${evalRep.model_id} · Test n=${evalMetrics?.test_samples}` : 'Evaluation training run in progress or not yet generated'}
          </span>
        </div>

        {evalMetrics ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">Stage A Crop Acc</div>
                <div className="text-lg font-bold text-[#081C15]">{(evalMetrics.stage_a_plant_id_accuracy * 100).toFixed(1)}%</div>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">End-to-End Acc</div>
                <div className="text-lg font-bold text-[#081C15]">{(evalMetrics.stage_b_end_to_end_accuracy * 100).toFixed(1)}%</div>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">40-Class Macro F1</div>
                <div className="text-lg font-bold text-[#081C15]">{(evalMetrics.stage_b_macro_f1 * 100).toFixed(1)}%</div>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">False HIGH Rate</div>
                <div className="text-lg font-bold text-[#065F46]">{(evalMetrics.false_high_confidence_rate * 100).toFixed(1)}%</div>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">Calibrated ECE</div>
                <div className="text-lg font-bold text-[#081C15]">{evalMetrics.ece_problem_after_temp_scaling}</div>
              </div>
              <div className="p-3 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                <div className="text-[10px] text-[#6B7280] uppercase font-semibold">Non-Plant Reject</div>
                <div className="text-lg font-bold text-[#081C15]">{(evalMetrics.ood_non_plant_rejection_rate * 100).toFixed(1)}%</div>
              </div>
            </div>
            <div className="text-xs text-[#4B5563] space-y-1 bg-[#FAF8F5] p-3 rounded-xl border border-[#E5E0D8]">
              <div className="font-semibold text-[#081C15]">Scope & Disclosed Limitations:</div>
              {(evalRep.known_limitations || []).map((lim: string, i: number) => (
                <div key={i}>• {lim}</div>
              ))}
            </div>
          </>
        ) : (
          <div className="text-xs text-[#6B7280] p-3 rounded-xl bg-[#FAF8F5]">
            No held-out evaluation report found on disk yet. Run <code>python backend/evals/diagnosis/train_two_stage_classifier.py</code> to generate real metrics.
          </div>
        )}
      </div>

      {/* Interactive Hybrid RAG & Evidence Verification Sandbox + Evidence Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl bg-white border border-[#E5E0D8] space-y-3">
          <h3 className="text-base font-bold text-[#081C15] flex items-center gap-2">
            <Search size={18} className="text-[#2D6A4F]" /> Test Hybrid RAG & Answer Verification
          </h3>
          <form onSubmit={runRagTest} className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={testQuery}
              onChange={e => setTestQuery(e.target.value)}
              placeholder="Ask e.g. Ragi leaf blast management in Mandya..."
              className="flex-1 text-xs border border-[#D1D5DB] rounded-xl px-3 py-2"
            />
            <input
              type="text"
              value={testCrop}
              onChange={e => setTestCrop(e.target.value)}
              placeholder="Crop filter"
              className="sm:w-28 text-xs border border-[#D1D5DB] rounded-xl px-3 py-2"
            />
            <button type="submit" disabled={testingRag} className="px-4 py-2 rounded-xl bg-[#1B4332] text-white text-xs font-semibold cursor-pointer">
              {testingRag ? 'Testing...' : 'Verify'}
            </button>
          </form>

          {ragResult && (
            <div className="space-y-2 text-xs pt-2">
              <div className="font-semibold text-[#081C15]">
                Evidence Status: <span className="px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">{ragResult.verification?.evidence_status}</span>
              </div>
              {(ragResult.retrieved_chunks || []).length === 0 ? (
                <div className="text-[#6B7280]">0 chunks passed relevance & crop-isolation thresholds (no unrelated filler returned).</div>
              ) : (
                ragResult.retrieved_chunks.map((c: any) => (
                  <div key={c.chunk_id} className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8]">
                    <div className="font-semibold text-[#081C15]">{c.title} ({c.is_official ? 'Official KB' : 'Approved Dataset'})</div>
                    <div className="text-[11px] text-[#6B7280]">Publisher: {c.publisher} · Score: {c.relevance_score}</div>
                    <div className="text-[#374151] mt-1">{c.content.slice(0, 220)}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="p-5 rounded-2xl bg-white border border-[#E5E0D8] space-y-3">
          <h3 className="text-base font-bold text-[#081C15]">Evidence Status & API Validation Breakdown</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {['Verified', 'Partially verified', 'Conflicting information', 'Outdated', 'Unverified', 'Insufficient information'].map(st => (
              <div key={st} className="p-2.5 rounded-xl bg-[#FAF8F5] border border-[#E5E0D8] flex items-center justify-between">
                <span className="text-[#374151] font-medium">{st}</span>
                <span className="font-bold text-[#081C15]">{overview?.evidence_verification?.by_status?.[st] ?? 0}</span>
              </div>
            ))}
          </div>
          <div className="text-xs text-[#4B5563] pt-2 border-t border-[#F3F0EA]">
            API Schema Validation Pass Rate:{' '}
            <b>
              {overview?.api_intelligence?.schema_valid_rate != null
                ? `${(overview.api_intelligence.schema_valid_rate * 100).toFixed(1)}%`
                : 'No recent live API calls'}
            </b>{' '}
            · Avg Latency: <b>{overview?.api_intelligence?.avg_latency_ms != null ? `${overview.api_intelligence.avg_latency_ms} ms` : '—'}</b>
          </div>
        </div>
      </div>
    </div>
  );
};
