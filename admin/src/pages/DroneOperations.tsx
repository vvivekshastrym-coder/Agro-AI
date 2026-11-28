import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, ChevronRight, Clock3, FileCheck2, Plane, RefreshCw, ShieldCheck, Users } from 'lucide-react';
import { adminFetch } from '../lib/api';

type Tab = 'overview' | 'applications' | 'providers' | 'bookings' | 'roles';
type Application = {
  id: string; type: 'individual' | 'company' | 'copilot'; status: string;
  data: Record<string, any>; applicant?: { user_id: string; name?: string; email?: string; phone?: string };
  submitted_at?: string; reviewed_at?: string; review_notes?: string;
  required_documents_present: boolean;
  documents: Array<{ id: string; document_type: string; filename: string; content_type: string; size_bytes: number; verification_status: string }>;
  history: Array<{ action: string; previous_status?: string; new_status: string; reason?: string; notes?: string; created_at?: string }>;
};
type Overview = Record<string, number>;

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'overview', label: 'Overview' }, { id: 'applications', label: 'Applications & approvals' },
  { id: 'providers', label: 'Pilot directory' }, { id: 'bookings', label: 'Bookings' }, { id: 'roles', label: 'Role approvals' },
];
const SERVICES = ['crop_spraying', 'surveying', 'mapping', 'crop_monitoring', 'other'];

async function readResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail?.message || body.detail || 'Request failed. Try again.');
  return body as T;
}

function StatCard({ label, value, icon: Icon, tone = 'green' }: { label: string; value?: number; icon: React.ElementType; tone?: 'green' | 'amber' | 'blue' }) {
  const color = tone === 'amber' ? 'text-amber-700 bg-amber-50' : tone === 'blue' ? 'text-blue-700 bg-blue-50' : 'text-emerald-800 bg-emerald-50';
  return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><span className={`rounded-xl p-2 ${color}`}><Icon size={17} /></span></div>
    <div className="mt-3 text-3xl font-bold text-slate-900">{value ?? '—'}</div>
  </div>;
}

export const DroneOperations: React.FC = () => {
  const [tab, setTab] = useState<Tab>('overview');
  const [overview, setOverview] = useState<Overview>({});
  const [applications, setApplications] = useState<Application[]>([]);
  const [providers, setProviders] = useState<any>({ pilots: [], companies: [] });
  const [bookings, setBookings] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [selected, setSelected] = useState<Application | null>(null);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reviewReason, setReviewReason] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [credentialsVerified, setCredentialsVerified] = useState(false);
  const [businessVerified, setBusinessVerified] = useState(false);
  const [uploadType, setUploadType] = useState('identity');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [manualType, setManualType] = useState<'individual' | 'company' | 'copilot'>('individual');
  const [manualData, setManualData] = useState({ userId: '', name: '', state: '', district: '', taluk: '', village: '', qualification: '', certificateNumber: '', certificateIssuer: '', droneModel: '', services: ['crop_spraying'], pricePerAcre: '', businessName: '', representative: '' });

  const load = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const [o, a, p, b, r] = await Promise.all([
        adminFetch('/api/admin/drone/overview').then(readResponse<Overview>),
        adminFetch(`/api/admin/drone/applications?status=${encodeURIComponent(statusFilter)}`).then(readResponse<{ applications: Application[] }>),
        adminFetch('/api/admin/drone/providers').then(readResponse<any>),
        adminFetch('/api/admin/drone/bookings').then(readResponse<{ bookings: any[] }>),
        adminFetch('/api/admin/drone/roles').then(readResponse<{ roles: any[] }>),
      ]);
      setOverview(o); setApplications(a.applications); setProviders(p); setBookings(b.bookings); setRoles(r.roles);
      setSelected((previous) => previous ? a.applications.find((app) => app.id === previous.id) || null : null);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load Drone Operations.'); }
    finally { setBusy(false); }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  const pendingCounts = useMemo(() => applications.filter((a) => ['pending', 'under_review', 'more_information_required', 'on_hold'].includes(a.status)).length, [applications]);

  const decide = async (nextStatus: string) => {
    if (!selected) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await readResponse(await adminFetch(`/api/admin/drone/applications/${selected.id}/review`, {
        method: 'POST', body: JSON.stringify({ status: nextStatus, reason: reviewReason, notes: reviewNotes, credentials_verified: credentialsVerified, business_documents_verified: businessVerified }),
      }));
      setNotice(`Application ${nextStatus.replace(/_/g, ' ')}.`); setSelected(null); setReviewReason(''); setReviewNotes('');
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the review.'); }
    finally { setBusy(false); }
  };

  const uploadDoc = async () => {
    if (!selected || !uploadFile) return;
    setBusy(true); setError('');
    try {
      const form = new FormData(); form.append('file', uploadFile);
      await readResponse(await adminFetch(`/api/admin/drone/applications/${selected.id}/documents?document_type=${encodeURIComponent(uploadType)}`, { method: 'POST', body: form }));
      setUploadFile(null); await load(); setNotice('Document uploaded to private storage.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Document upload failed.'); }
    finally { setBusy(false); }
  };

  const openDocument = async (application: Application, documentId: string) => {
    setError('');
    try {
      const data = await readResponse<{ signed_url: string }>(await adminFetch(`/api/admin/drone/applications/${application.id}/documents/${documentId}/url`));
      window.open(data.signed_url, '_blank', 'noopener,noreferrer');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not open document.'); }
  };

  const createManual = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    const serviceAreas = [{ state: manualData.state, district: manualData.district, taluk: manualData.taluk, village: manualData.village }];
    const data: Record<string, any> = manualType === 'company' ? {
      registered_name: manualData.businessName, representative_name: manualData.representative,
      state: manualData.state, district: manualData.district, services: manualData.services, service_areas: serviceAreas,
    } : manualType === 'copilot' ? {
      full_name: manualData.name, state: manualData.state, district: manualData.district, qualification: manualData.qualification,
    } : {
      full_name: manualData.name, state: manualData.state, district: manualData.district, taluk: manualData.taluk,
      village: manualData.village, qualification: manualData.qualification,
      certificate_number: manualData.certificateNumber, certificate_issuer: manualData.certificateIssuer,
      services: manualData.services, price_per_acre: manualData.pricePerAcre,
      availability: { days: [0, 1, 2, 3, 4, 5, 6] }, service_areas: serviceAreas,
      drones: [{ model: manualData.droneModel, capabilities: manualData.services }],
    };
    try {
      await readResponse(await adminFetch('/api/admin/drone/applications/manual', {
        method: 'POST', body: JSON.stringify({ existing_user_id: manualData.userId, application_type: manualType, data }),
      }));
      setNotice('Pending application registered. It is not bookable until documents are reviewed and approved.');
      await load(); setTab('applications');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not register the application.'); }
    finally { setBusy(false); }
  };

  const setProviderStatus = async (type: 'pilot' | 'company', id: string, next: 'approved' | 'suspended') => {
    const reason = window.prompt(`Reason for ${next === 'approved' ? 'reactivation' : 'suspension'} (required):`);
    if (!reason || reason.trim().length < 5) return;
    setBusy(true); setError('');
    try {
      await readResponse(await adminFetch(`/api/admin/drone/providers/${type}/${id}/status`, {
        method: 'PATCH', body: JSON.stringify({ status: next, reason }),
      }));
      setNotice(`${type === 'pilot' ? 'Pilot' : 'Company'} ${next}.`); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update provider status.'); }
    finally { setBusy(false); }
  };

  const setRoleStatus = async (id: string, next: 'approved' | 'rejected' | 'revoked') => {
    const reason = window.prompt(`Reason for ${next}:`);
    if (!reason || reason.trim().length < 5) return;
    setBusy(true); setError('');
    try {
      await readResponse(await adminFetch(`/api/admin/drone/roles/${id}`, { method: 'PATCH', body: JSON.stringify({ status: next, reason }) }));
      setNotice(`Drone role ${next}.`); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update role.'); }
    finally { setBusy(false); }
  };

  return <div className="min-h-full bg-[#FAF8F5] p-4 md:p-7">
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800"><Plane size={17} /> Super Admin / Drone Operations</div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-950">Drone Operations</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">Verify pilots and companies before the farmer app can list or book them. All figures come from stored records.</p>
        </div>
        <button onClick={() => void load()} disabled={busy} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={15} className={busy ? 'animate-spin' : ''} /> Refresh</button>
      </div>

      {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800"><AlertCircle size={17} className="mt-0.5 shrink-0" />{error}</div>}
      {notice && <div role="status" className="mt-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"><CheckCircle2 size={17} className="mt-0.5 shrink-0" />{notice}</div>}

      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((item) => <button key={item.id} onClick={() => setTab(item.id)} className={`shrink-0 border-b-2 px-3 py-3 text-sm font-semibold ${tab === item.id ? 'border-emerald-700 text-emerald-900' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>{item.label}</button>)}
      </div>

      {tab === 'overview' && <>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Pending applications" value={overview.pending_applications} icon={Clock3} tone="amber" />
          <StatCard label="Approved pilots" value={overview.approved_pilots} icon={Users} />
          <StatCard label="Approved companies" value={overview.approved_companies} icon={ShieldCheck} />
          <StatCard label="Active bookings" value={overview.active_bookings} icon={Plane} tone="blue" />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total pilots" value={overview.total_pilots} icon={Users} />
          <StatCard label="Total companies" value={overview.total_companies} icon={ShieldCheck} />
          <StatCard label="Completed bookings" value={overview.completed_bookings} icon={CheckCircle2} />
          <StatCard label="Pending co-pilot/role reviews" value={overview.pending_role_approvals} icon={FileCheck2} tone="amber" />
        </div>
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950"><b>Approval gate:</b> new profiles stay hidden until a Super Admin reviews the required documents, confirms credentials, and approves the profile. Website clients cannot query the mobile provider directory.</div>
      </>}

      {tab === 'applications' && <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="font-bold text-slate-900">Approval queue</h2><p className="mt-1 text-xs text-slate-500">{pendingCounts} records in the selected queue</p></div>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="pending">Pending</option><option value="under_review">Under review</option><option value="more_information_required">More information required</option><option value="on_hold">On hold</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
            </div>
            <div className="mt-3 divide-y divide-slate-100">
              {applications.map((app) => <button key={app.id} onClick={() => { setSelected(app); setReviewReason(''); setReviewNotes(''); }} className={`flex w-full items-center justify-between gap-4 rounded-xl px-3 py-3 text-left hover:bg-slate-50 ${selected?.id === app.id ? 'bg-emerald-50 ring-1 ring-emerald-200' : ''}`}>
                <span className="min-w-0"><span className="block truncate text-sm font-semibold text-slate-900">{app.data.full_name || app.data.registered_name || app.applicant?.name || app.type}</span><span className="mt-1 block text-xs text-slate-500">{app.type} · {app.status.replace(/_/g, ' ')} · {app.applicant?.email || app.applicant?.phone || app.applicant?.user_id}</span></span>
                <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">{app.documents.length} docs <ChevronRight size={16} /></span>
              </button>)}
              {!applications.length && <p className="py-8 text-center text-sm text-slate-500">No applications in this queue.</p>}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="font-bold text-slate-900">Register an existing Agro AI account</h2>
            <p className="mt-1 text-xs text-slate-500">No duplicate user is created. The registration starts pending and still requires document review.</p>
            <form onSubmit={createManual} className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-slate-600">Application type<select value={manualType} onChange={(e) => setManualType(e.target.value as any)} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm"><option value="individual">Individual pilot</option><option value="company">Drone company</option><option value="copilot">Co-pilot</option></select></label>
              <label className="text-xs font-semibold text-slate-600">Existing account user ID<input required value={manualData.userId} onChange={(e) => setManualData({ ...manualData, userId: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              {manualType === 'company' ? <>
                <label className="text-xs font-semibold text-slate-600">Registered company name<input required value={manualData.businessName} onChange={(e) => setManualData({ ...manualData, businessName: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-600">Authorized representative<input required value={manualData.representative} onChange={(e) => setManualData({ ...manualData, representative: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              </> : <>
                <label className="text-xs font-semibold text-slate-600">Pilot / co-pilot name<input required value={manualData.name} onChange={(e) => setManualData({ ...manualData, name: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-600">Qualification<input required value={manualData.qualification} onChange={(e) => setManualData({ ...manualData, qualification: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              </>}
              <label className="text-xs font-semibold text-slate-600">State<input required value={manualData.state} onChange={(e) => setManualData({ ...manualData, state: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              <label className="text-xs font-semibold text-slate-600">District<input required value={manualData.district} onChange={(e) => setManualData({ ...manualData, district: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              {manualType === 'individual' && <>
                <label className="text-xs font-semibold text-slate-600">Certificate number<input required value={manualData.certificateNumber} onChange={(e) => setManualData({ ...manualData, certificateNumber: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-600">Issuing authority<input required value={manualData.certificateIssuer} onChange={(e) => setManualData({ ...manualData, certificateIssuer: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-600">Drone model<input required value={manualData.droneModel} onChange={(e) => setManualData({ ...manualData, droneModel: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
                <label className="text-xs font-semibold text-slate-600">Price per acre (INR)<input required type="number" min="0.01" step="0.01" value={manualData.pricePerAcre} onChange={(e) => setManualData({ ...manualData, pricePerAcre: e.target.value })} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" /></label>
              </>}
              <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Services<select multiple value={manualData.services} onChange={(e) => setManualData({ ...manualData, services: Array.from(e.target.selectedOptions, (option) => option.value) })} className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">{SERVICES.map((service) => <option key={service} value={service}>{service.replace(/_/g, ' ')}</option>)}</select></label>
              <button disabled={busy} className="min-h-11 rounded-xl bg-emerald-800 px-4 text-sm font-bold text-white hover:bg-emerald-900 disabled:opacity-50 sm:col-span-2">Register pending application</button>
            </form>
          </section>
        </div>

        <section className="h-fit rounded-2xl border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4">
          {!selected ? <div className="py-10 text-center text-sm text-slate-500">Choose an application to review.</div> : <>
            <div className="flex items-start justify-between gap-2"><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">{selected.type} application</p><h2 className="mt-1 text-lg font-bold text-slate-900">{selected.data.full_name || selected.data.registered_name || selected.applicant?.name || 'Applicant'}</h2><p className="mt-1 break-all text-xs text-slate-500">{selected.applicant?.email || selected.applicant?.user_id}</p></div><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">{selected.status}</span></div>
            <div className="mt-4 space-y-2 rounded-xl bg-slate-50 p-3 text-xs text-slate-700"><p><b>Service areas:</b> {Array.isArray(selected.data.service_areas) ? selected.data.service_areas.map((area: any) => [area.village, area.district, area.state].filter(Boolean).join(', ')).join(' · ') : [selected.data.district, selected.data.state].filter(Boolean).join(', ') || 'Not provided'}</p><p><b>Services:</b> {(selected.data.services || []).join(', ') || 'Not provided'}</p><p><b>Qualification:</b> {selected.data.qualification || 'Not provided'}</p><p><b>Certificate:</b> {selected.data.certificate_number || 'Not provided'} · expires {selected.data.certificate_expiry || 'not specified'}</p><p><b>Fleet:</b> {(selected.data.drones || []).map((d: any) => d.model).join(', ') || 'Company fleet details not provided'}</p></div>
            <div className="mt-4"><h3 className="text-sm font-bold text-slate-800">Private verification documents</h3><div className="mt-2 space-y-2">{selected.documents.map((doc) => <div key={doc.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-2"><span className="min-w-0"><span className="block text-xs font-semibold text-slate-800">{doc.document_type.replace(/_/g, ' ')}</span><span className="block truncate text-[11px] text-slate-500">{doc.filename} · {(doc.size_bytes / 1024).toFixed(0)} KB</span></span><button onClick={() => void openDocument(selected, doc.id)} className="min-h-9 rounded-lg border border-slate-300 px-2 text-xs font-semibold text-emerald-900">Review</button></div>)}{!selected.documents.length && <p className="text-xs text-slate-500">No documents uploaded.</p>}</div>
              <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2"><select value={uploadType} onChange={(e) => setUploadType(e.target.value)} className="min-h-10 rounded-lg border border-slate-300 px-2 text-xs"><option value="identity">Identity</option><option value="pilot_certificate">Pilot certificate</option><option value="drone_registration">Drone registration</option><option value="business_registration">Business registration</option><option value="qualification">Qualification</option></select><input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} className="min-w-0 text-[11px]" /><button onClick={() => void uploadDoc()} disabled={!uploadFile || busy} className="rounded-lg bg-slate-800 px-3 text-xs font-semibold text-white disabled:opacity-50">Upload</button></div>
            </div>
            <div className="mt-4 space-y-2"><label className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={credentialsVerified} onChange={(e) => setCredentialsVerified(e.target.checked)} />I verified the pilot's identity, credentials and current permissions.</label><label className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={businessVerified} onChange={(e) => setBusinessVerified(e.target.checked)} />I verified company registration and representative documents.</label><textarea value={reviewReason} onChange={(e) => setReviewReason(e.target.value)} placeholder="Decision reason (required for reject, hold or more information)" className="min-h-20 w-full rounded-lg border border-slate-300 p-2 text-xs" /><textarea value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} placeholder="Internal review notes" className="min-h-16 w-full rounded-lg border border-slate-300 p-2 text-xs" /></div>
            <div className="mt-3 grid grid-cols-2 gap-2"><button disabled={busy} onClick={() => void decide('under_review')} className="min-h-10 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 disabled:opacity-50">Start review</button><button disabled={busy} onClick={() => void decide('more_information_required')} className="min-h-10 rounded-lg border border-amber-300 bg-amber-50 text-xs font-bold text-amber-900 disabled:opacity-50">Request information</button><button disabled={busy} onClick={() => void decide('on_hold')} className="min-h-10 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 disabled:opacity-50">Put on hold</button><button disabled={busy} onClick={() => void decide('rejected')} className="min-h-10 rounded-lg border border-red-300 bg-red-50 text-xs font-bold text-red-800 disabled:opacity-50">Reject</button><button disabled={busy || !selected.required_documents_present} onClick={() => void decide('approved')} className="min-h-11 rounded-lg bg-emerald-800 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-50 sm:col-span-2">Approve & publish in farmer app</button></div>
            {!selected.required_documents_present && <p className="mt-2 text-[11px] text-amber-800">Required document types are missing. Upload them before approval.</p>}
            <p className="mt-3 rounded-lg bg-amber-50 p-2 text-[11px] leading-5 text-amber-950">Agro AI approval does not replace DGCA or other statutory licenses and operating permissions. Confirm applicable permissions outside this app.</p>
          </>}
        </section>
      </div>}

      {tab === 'providers' && <div className="mt-5 grid gap-5 xl:grid-cols-2">
        {(['pilots', 'companies'] as const).map((key) => <section key={key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><h2 className="font-bold text-slate-900">{key === 'pilots' ? 'Pilot directory' : 'Company management'}</h2><div className="mt-3 space-y-2">{(providers[key] || []).map((item: any) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><span><b className="block text-sm text-slate-900">{item.name || item.brand_name || item.registered_name}</b><span className="text-xs text-slate-500">{item.district}, {item.state} · {item.status}{item.credentials_verified ? ' · credentials verified' : ''}</span></span><div className="flex items-center gap-2"><button onClick={() => void setProviderStatus(key === 'pilots' ? 'pilot' : 'company', item.id, item.status === 'suspended' ? 'approved' : 'suspended')} className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-bold text-slate-700">{item.status === 'suspended' ? 'Reactivate' : 'Suspend'}</button></div></div>)}{!(providers[key] || []).length && <p className="py-7 text-center text-sm text-slate-500">No real {key} have been registered.</p>}</div></section>)}
      </div>}

      {tab === 'bookings' && <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 p-4"><h2 className="font-bold text-slate-900">Farmer booking requests</h2><p className="mt-1 text-xs text-slate-500">Quoted values come from provider pricing saved with each request.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-slate-50 text-slate-500"><tr><th className="p-3">Service</th><th className="p-3">Area</th><th className="p-3">Location</th><th className="p-3">Date</th><th className="p-3">Quote</th><th className="p-3">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{bookings.map((b) => <tr key={b.id}><td className="p-3 font-semibold">{b.service_category.replace(/_/g, ' ')}</td><td className="p-3">{b.area_acres} ac</td><td className="p-3">{[b.farm_location?.village, b.farm_location?.district, b.farm_location?.state].filter(Boolean).join(', ')}</td><td className="p-3">{b.scheduled_date}</td><td className="p-3">₹{Number(b.quoted_total).toLocaleString('en-IN')}</td><td className="p-3">{b.status.replace(/_/g, ' ')}</td></tr>)}</tbody></table>{!bookings.length && <p className="p-8 text-center text-sm text-slate-500">No drone bookings yet.</p>}</div></div>}

      {tab === 'roles' && <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><h2 className="font-bold text-slate-900">Co-pilot and company role approvals</h2><p className="mt-1 text-xs text-slate-500">A role approval records Agro AI status only. It does not grant statutory drone operating authority.</p><div className="mt-3 divide-y divide-slate-100">{roles.map((role) => <div key={role.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><b className="block text-sm text-slate-900">{role.role.replace(/_/g, ' ')}</b><span className="text-xs text-slate-500">User {role.user_id} · company {role.company_id || 'independent'} · {role.status}</span></div>{role.status === 'pending' ? <div className="flex gap-2"><button onClick={() => void setRoleStatus(role.id, 'approved')} className="min-h-9 rounded-lg bg-emerald-800 px-3 text-xs font-bold text-white">Approve</button><button onClick={() => void setRoleStatus(role.id, 'rejected')} className="min-h-9 rounded-lg border border-red-300 px-3 text-xs font-bold text-red-800">Reject</button></div> : role.status === 'approved' ? <button onClick={() => void setRoleStatus(role.id, 'revoked')} className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-bold">Revoke</button> : null}</div>)}{!roles.length && <p className="py-8 text-center text-sm text-slate-500">No co-pilot or company role requests.</p>}</div></div>}
    </div>
  </div>;
};
