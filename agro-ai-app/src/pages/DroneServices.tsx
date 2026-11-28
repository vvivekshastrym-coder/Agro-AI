import { useCallback, useEffect, useMemo, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { useApp } from "../lib/AppContext";
import { droneServices, DroneProvider, DroneQuote, DroneService } from "../lib/droneApi";

type AppTab = "find" | "bookings" | "apply";
const SERVICE_OPTIONS: Array<{ value: DroneService; label: string }> = [
  { value: "crop_spraying", label: "Crop spraying" },
  { value: "surveying", label: "Farm surveying" },
  { value: "mapping", label: "Farm mapping" },
  { value: "crop_monitoring", label: "Crop monitoring" },
  { value: "other", label: "Other approved service" },
];
const WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function todayString() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function currency(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

function statusLabel(status: string) {
  return status.replace(/_/g, " ").replace(/^./, (x) => x.toUpperCase());
}

export default function DroneServices() {
  const { profile } = useApp();
  const [tab, setTab] = useState<AppTab>("find");
  const [service, setService] = useState<DroneService>("crop_spraying");
  const [location, setLocation] = useState({
    state: profile?.state || "Karnataka",
    district: profile?.district || "",
    taluk: profile?.taluk || "",
    village: profile?.village || "",
  });
  const [searchDate, setSearchDate] = useState("");
  const [providers, setProviders] = useState<DroneProvider[]>([]);
  const [searched, setSearched] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<DroneProvider | null>(null);
  const [area, setArea] = useState("1");
  const [bookingDate, setBookingDate] = useState("");
  const [bookingNotes, setBookingNotes] = useState("");
  const [quote, setQuote] = useState<DroneQuote | null>(null);
  const [bookings, setBookings] = useState<Array<Record<string, any>>>([]);
  const [applications, setApplications] = useState<Array<Record<string, any>>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [applicationType, setApplicationType] = useState<"individual" | "company" | "copilot">("individual");
  const [applicationId, setApplicationId] = useState("");
  const [documents, setDocuments] = useState<Array<{ type: string; file: File }>>([]);
  const [form, setForm] = useState({
    fullName: profile?.full_name || "", companyName: "", brandName: "", representative: "",
    state: profile?.state || "Karnataka", district: profile?.district || "", taluk: profile?.taluk || "", village: profile?.village || "",
    qualification: "", certificateNumber: "", certificateIssuer: "", certificateExpiry: "", yearsExperience: "0",
    manufacturer: "", droneModel: "", serialNumber: "", registrationNumber: "", payload: "", equipment: "",
    ratePerAcre: "", minimumBooking: "", services: ["crop_spraying"] as string[], days: [0, 1, 2, 3, 4, 5, 6] as number[],
  });

  const isAndroid = Capacitor.getPlatform() === "android";
  const quoteEstimate = useMemo(() => {
    const acres = Number(area);
    if (!selectedProvider || !Number.isFinite(acres) || acres <= 0) return null;
    return Math.max(acres * selectedProvider.price_per_acre, selectedProvider.minimum_booking_amount || 0);
  }, [area, selectedProvider]);

  const loadBookings = useCallback(async () => {
    const data = await droneServices.myBookings();
    setBookings(data.bookings);
  }, []);
  const loadApplications = useCallback(async () => {
    const data = await droneServices.applications();
    setApplications(data.applications);
  }, []);

  useEffect(() => {
    if (!isAndroid) return;
    void Promise.all([loadBookings(), loadApplications()]).catch((e) => setError(e instanceof Error ? e.message : "Could not load your drone records."));
  }, [isAndroid, loadBookings, loadApplications]);

  const search = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setNotice(""); setSearched(false);
    if (!location.district.trim()) { setBusy(false); setError("Enter your farm district to find providers."); return; }
    try {
      const result = await droneServices.providers({ service, ...location, scheduled_date: searchDate || undefined });
      setProviders(result.providers); setSearched(true);
      if (!result.available) setNotice(result.message || "No approved provider is available for this service and location yet.");
    } catch (e) { setError(e instanceof Error ? e.message : "Provider search failed."); }
    finally { setBusy(false); }
  };

  const submitBooking = async () => {
    if (!selectedProvider) return;
    setBusy(true); setError(""); setNotice(""); setQuote(null);
    try {
      const result = await droneServices.createBooking({
        provider_pilot_id: selectedProvider.pilot_id, service_category: service,
        ...location, area_acres: Number(area), scheduled_date: bookingDate,
        farmer_notes: bookingNotes || undefined,
      });
      setQuote(result.quote); setNotice(result.message); setSelectedProvider(null);
      await loadBookings(); setTab("bookings");
    } catch (e) { setError(e instanceof Error ? e.message : "Booking request failed."); }
    finally { setBusy(false); }
  };

  const createOrUpdateApplication = async () => {
    setBusy(true); setError(""); setNotice("");
    const serviceAreas = [{ state: form.state, district: form.district, taluk: form.taluk || undefined, village: form.village || undefined }];
    const data: Record<string, any> = applicationType === "company" ? {
      registered_name: form.companyName, brand_name: form.brandName || undefined,
      representative_name: form.representative, state: form.state, district: form.district,
      address: [form.village, form.taluk, form.district, form.state].filter(Boolean).join(", "),
      services: form.services, service_areas: serviceAreas,
    } : applicationType === "copilot" ? {
      full_name: form.fullName, state: form.state, district: form.district,
      qualification: form.qualification,
    } : {
      full_name: form.fullName, state: form.state, district: form.district,
      taluk: form.taluk || undefined, village: form.village || undefined,
      qualification: form.qualification, certificate_number: form.certificateNumber,
      certificate_issuer: form.certificateIssuer, certificate_expiry: form.certificateExpiry || undefined,
      years_experience: Number(form.yearsExperience || 0), services: form.services,
      service_areas: serviceAreas, price_per_acre: form.ratePerAcre,
      minimum_booking_amount: form.minimumBooking || undefined,
      availability: { days: form.days },
      drones: [{ manufacturer: form.manufacturer || undefined, model: form.droneModel,
        serial_number: form.serialNumber || undefined, registration_number: form.registrationNumber || undefined,
        payload_litres: form.payload || undefined, equipment_details: form.equipment || undefined,
        capabilities: form.services }],
    };
    try {
      const app = applicationId
        ? await droneServices.updateApplication(applicationId, data)
        : await droneServices.createApplication(applicationType, data);
      setApplicationId(app.id);
      for (const doc of documents) await droneServices.uploadDocument(app.id, doc.type, doc.file);
      setDocuments([]);
      setNotice(`Draft saved. Upload the required documents, then submit application ${app.id.slice(0, 8)}.`);
      await loadApplications();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save the application."); }
    finally { setBusy(false); }
  };

  const submitApplication = async () => {
    if (!applicationId) { setError("Save the application draft before submitting."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await droneServices.submitApplication(applicationId);
      setNotice("Application submitted. It will remain hidden from farmers until the Super Admin approves it.");
      setApplicationId(""); await loadApplications();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not submit the application."); }
    finally { setBusy(false); }
  };

  const chooseDocument = (type: string, file?: File) => {
    if (!file) return;
    setDocuments((current) => [...current.filter((doc) => doc.type !== type), { type, file }]);
  };

  const cancelBooking = async (booking: Record<string, any>) => {
    const reason = window.prompt("Why are you cancelling this service request?");
    if (!reason || reason.trim().length < 5) return;
    setBusy(true); setError("");
    try { await droneServices.cancelBooking(booking.id, reason); await loadBookings(); setNotice("Booking cancelled."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not cancel booking."); }
    finally { setBusy(false); }
  };

  const confirmCompletion = async (booking: Record<string, any>) => {
    setBusy(true); setError("");
    try { await droneServices.confirmCompletion(booking.id); await loadBookings(); setNotice("Service completion confirmed. You can now rate the provider."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not confirm completion."); }
    finally { setBusy(false); }
  };

  const submitReview = async (booking: Record<string, any>) => {
    const rating = Number(window.prompt("Rate this completed service from 1 to 5:"));
    if (!Number.isInteger(rating) || rating < 1 || rating > 5) return;
    const review = window.prompt("Optional review:") || "";
    setBusy(true); setError("");
    try { await droneServices.reviewBooking(booking.id, rating, review); await loadBookings(); setNotice("Review submitted."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not submit review."); }
    finally { setBusy(false); }
  };

  if (!isAndroid) {
    return <div className="p-5"><div className="rounded-3xl border border-line bg-white p-6 text-center shadow-soft"><div className="text-4xl">🚁</div><h2 className="mt-3 font-display text-xl font-bold text-forest">Drone Services are Android app only</h2><p className="mt-2 text-sm text-ink-soft">Open Agro AI on your Android phone to find approved providers or apply as a drone pilot.</p></div></div>;
  }

  return <div className="flex flex-col gap-4 p-4 pb-28 lg:p-8">
    <div><div className="text-xs font-semibold text-forest">Approved network</div><h2 className="mt-1 font-display text-2xl font-bold text-forest">🚁 Drone Services</h2><p className="mt-1 text-sm text-ink-soft">Search real, verified providers by service and farm location.</p></div>
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div>}
    {quote && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Saved quote: {currency(quote.total)} for {quote.area_acres} acres.</div>}

    <div className="grid grid-cols-3 gap-2 rounded-2xl bg-leaf-pale p-1">
      {([['find', 'Find'], ['bookings', 'Bookings'], ['apply', 'Apply']] as Array<[AppTab, string]>).map(([id, label]) => <button key={id} onClick={() => { setTab(id); setError(""); setNotice(""); if (id === 'bookings') void loadBookings(); if (id === 'apply') void loadApplications(); }} className={`min-h-10 rounded-xl text-sm font-bold ${tab === id ? 'bg-white text-forest shadow-sm' : 'text-forest/70'}`}>{label}</button>)}
    </div>

    {tab === "find" && <>
      <form onSubmit={search} className="grid gap-3 rounded-3xl border border-line bg-white p-4 shadow-soft sm:grid-cols-2">
        <label className="text-xs font-semibold text-ink-soft sm:col-span-2">Service<select value={service} onChange={(e) => setService(e.target.value as DroneService)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink">{SERVICE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="text-xs font-semibold text-ink-soft">State<input required value={location.state} onChange={(e) => setLocation({ ...location, state: e.target.value })} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
        <label className="text-xs font-semibold text-ink-soft">District<input required value={location.district} onChange={(e) => setLocation({ ...location, district: e.target.value })} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
        <label className="text-xs font-semibold text-ink-soft">Taluk (optional)<input value={location.taluk} onChange={(e) => setLocation({ ...location, taluk: e.target.value })} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
        <label className="text-xs font-semibold text-ink-soft">Village (optional)<input value={location.village} onChange={(e) => setLocation({ ...location, village: e.target.value })} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
        <label className="text-xs font-semibold text-ink-soft sm:col-span-2">Preferred date (optional)<input type="date" min={todayString()} value={searchDate} onChange={(e) => setSearchDate(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink" /></label>
        <button disabled={busy} className="min-h-12 rounded-full bg-forest px-5 text-sm font-bold text-white disabled:opacity-60 sm:col-span-2">{busy ? "Searching…" : "Find approved providers"}</button>
      </form>
      {searched && !providers.length && <div className="rounded-2xl border border-dashed border-line bg-white p-6 text-center"><div className="text-3xl">🛰️</div><p className="mt-2 font-semibold text-forest">No approved provider is available here yet.</p><p className="mt-1 text-sm text-ink-soft">Try a nearby district or check again later. We will not display unapproved providers.</p></div>}
      <div className="flex flex-col gap-3">
        {providers.map((provider) => <ProviderCard key={provider.pilot_id} provider={provider} onBook={() => { setSelectedProvider(provider); setBookingDate(searchDate); setArea("1"); setBookingNotes(""); }} />)}
      </div>
      {selectedProvider && <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-3 sm:items-center" onClick={() => setSelectedProvider(null)}><section role="dialog" aria-modal="true" aria-label="Request drone service booking" className="w-full max-w-md rounded-3xl bg-cream p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3"><div><h3 className="font-display text-xl font-bold text-forest">Request service</h3><p className="text-sm text-ink-soft">{selectedProvider.name}</p></div><button onClick={() => setSelectedProvider(null)} className="min-h-10 min-w-10 rounded-full border border-line bg-white text-ink">×</button></div>
        <label className="mt-4 block text-xs font-semibold text-ink-soft">Farm area (acres)<input type="number" min="0.1" step="0.1" value={area} onChange={(e) => setArea(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink" /></label>
        <label className="mt-3 block text-xs font-semibold text-ink-soft">Preferred service date<input type="date" min={todayString()} value={bookingDate} onChange={(e) => setBookingDate(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink" /></label>
        <label className="mt-3 block text-xs font-semibold text-ink-soft">Notes for provider (optional)<textarea value={bookingNotes} onChange={(e) => setBookingNotes(e.target.value)} maxLength={1500} className="mt-1 min-h-20 w-full rounded-xl border border-line bg-white p-3 text-sm text-ink" /></label>
        <div className="mt-3 rounded-xl bg-white p-3 text-sm"><div className="flex justify-between"><span>Configured rate</span><span>{currency(selectedProvider.price_per_acre)} / acre</span></div>{selectedProvider.minimum_booking_amount ? <div className="mt-1 flex justify-between"><span>Minimum booking</span><span>{currency(selectedProvider.minimum_booking_amount)}</span></div> : null}<div className="mt-2 flex justify-between border-t border-line pt-2 font-bold text-forest"><span>Estimated total</span><span>{quoteEstimate === null ? "Enter acreage" : currency(quoteEstimate)}</span></div><p className="mt-1 text-[11px] text-ink-soft">Final price comes from the provider's saved rate and minimum. No payment is collected here.</p></div>
        <button disabled={busy || !bookingDate || !quoteEstimate} onClick={() => void submitBooking()} className="mt-4 min-h-12 w-full rounded-full bg-forest text-sm font-bold text-white disabled:opacity-50">{busy ? "Sending…" : "Send booking request"}</button>
      </section></div>}
    </>}

    {tab === "bookings" && <div className="flex flex-col gap-3">
      {!bookings.length && <div className="rounded-2xl border border-line bg-white p-6 text-center text-sm text-ink-soft">Your drone booking history will appear here.</div>}
      {bookings.map((booking) => <section key={booking.id} className="rounded-2xl border border-line bg-white p-4 shadow-soft"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold text-forest">{SERVICE_OPTIONS.find((item) => item.value === booking.service_category)?.label || booking.service_category}</h3><p className="mt-1 text-xs text-ink-soft">{[booking.farm_location?.village, booking.farm_location?.taluk, booking.farm_location?.district, booking.farm_location?.state].filter(Boolean).join(", ")}</p></div><span className="rounded-full bg-leaf-pale px-3 py-1 text-xs font-bold text-forest">{statusLabel(booking.status)}</span></div><div className="mt-3 grid grid-cols-2 gap-2 text-sm"><div><span className="block text-xs text-ink-soft">Area</span>{booking.area_acres} acres</div><div><span className="block text-xs text-ink-soft">Date</span>{booking.scheduled_date}</div><div className="col-span-2"><span className="block text-xs text-ink-soft">Quoted price</span><b>{currency(booking.quoted_total)}</b></div></div>
        {booking.status === "requested" && booking.farmer_user_id !== "" && <button onClick={() => void cancelBooking(booking)} className="mt-3 min-h-10 rounded-full border border-red-200 px-4 text-xs font-bold text-red-800">Cancel request</button>}
        {booking.status === "awaiting_farmer_confirmation" && <button onClick={() => void confirmCompletion(booking)} className="mt-3 min-h-10 rounded-full bg-forest px-4 text-xs font-bold text-white">Confirm service completed</button>}
        {booking.status === "completed" && <button onClick={() => void submitReview(booking)} className="mt-3 min-h-10 rounded-full border border-line px-4 text-xs font-bold text-forest">Rate completed service</button>}
      </section>)}
    </div>}

    {tab === "apply" && <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">Agro AI's internal approval does not replace DGCA or other applicable statutory licenses and operating permissions. Submit documents for verification; do not claim a credential has been checked until it has.</div>
      <section className="rounded-3xl border border-line bg-white p-4 shadow-soft">
        <h3 className="font-display text-xl font-bold text-forest">Apply to join the network</h3>
        <label className="mt-3 block text-xs font-semibold text-ink-soft">Application type<select value={applicationType} onChange={(e) => { setApplicationType(e.target.value as any); setApplicationId(""); setDocuments([]); }} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm"><option value="individual">Individual drone pilot</option><option value="company">Drone service company</option><option value="copilot">Co-pilot / crew member</option></select></label>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {applicationType === "company" ? <><TextField label="Registered company name" value={form.companyName} onChange={(companyName) => setForm({ ...form, companyName })} /><TextField label="Brand name (optional)" value={form.brandName} onChange={(brandName) => setForm({ ...form, brandName })} /><TextField label="Authorized representative" value={form.representative} onChange={(representative) => setForm({ ...form, representative })} /></> : <><TextField label="Full name" value={form.fullName} onChange={(fullName) => setForm({ ...form, fullName })} /><TextField label="Qualification" value={form.qualification} onChange={(qualification) => setForm({ ...form, qualification })} /></>}
          <TextField label="State" value={form.state} onChange={(state) => setForm({ ...form, state })} />
          <TextField label="District" value={form.district} onChange={(district) => setForm({ ...form, district })} />
          {applicationType !== "company" && <><TextField label="Taluk" value={form.taluk} onChange={(taluk) => setForm({ ...form, taluk })} /><TextField label="Village" value={form.village} onChange={(village) => setForm({ ...form, village })} /></>}
          {applicationType === "individual" && <>
            <TextField label="Pilot certificate number" value={form.certificateNumber} onChange={(certificateNumber) => setForm({ ...form, certificateNumber })} />
            <TextField label="Issuing authority" value={form.certificateIssuer} onChange={(certificateIssuer) => setForm({ ...form, certificateIssuer })} />
            <TextField label="Certificate expiry (if applicable)" type="date" value={form.certificateExpiry} onChange={(certificateExpiry) => setForm({ ...form, certificateExpiry })} />
            <TextField label="Years of experience" type="number" value={form.yearsExperience} onChange={(yearsExperience) => setForm({ ...form, yearsExperience })} />
            <TextField label="Drone model" value={form.droneModel} onChange={(droneModel) => setForm({ ...form, droneModel })} />
            <TextField label="Manufacturer" value={form.manufacturer} onChange={(manufacturer) => setForm({ ...form, manufacturer })} />
            <TextField label="Drone serial number" value={form.serialNumber} onChange={(serialNumber) => setForm({ ...form, serialNumber })} />
            <TextField label="Registration / identification number" value={form.registrationNumber} onChange={(registrationNumber) => setForm({ ...form, registrationNumber })} />
            <TextField label="Payload (litres, optional)" value={form.payload} onChange={(payload) => setForm({ ...form, payload })} />
            <TextField label="Price per acre (INR)" type="number" value={form.ratePerAcre} onChange={(ratePerAcre) => setForm({ ...form, ratePerAcre })} />
            <TextField label="Minimum booking (INR, optional)" type="number" value={form.minimumBooking} onChange={(minimumBooking) => setForm({ ...form, minimumBooking })} />
            <TextField label="Spraying / other equipment" value={form.equipment} onChange={(equipment) => setForm({ ...form, equipment })} />
          </>}
        </div>
        {applicationType !== "copilot" && <fieldset className="mt-4"><legend className="text-xs font-semibold text-ink-soft">Services offered</legend><div className="mt-2 grid grid-cols-2 gap-2">{SERVICE_OPTIONS.map((option) => <label key={option.value} className="flex min-h-10 items-center gap-2 rounded-xl border border-line px-3 text-xs"><input type="checkbox" checked={form.services.includes(option.value)} onChange={(e) => setForm({ ...form, services: e.target.checked ? [...form.services, option.value] : form.services.filter((x) => x !== option.value) })} />{option.label}</label>)}</div></fieldset>}
        {applicationType === "individual" && <fieldset className="mt-4"><legend className="text-xs font-semibold text-ink-soft">Availability (days)</legend><div className="mt-2 flex flex-wrap gap-2">{WEEK_DAYS.map((day, index) => <label key={day} className="flex min-h-9 items-center gap-1.5 rounded-full border border-line px-3 text-xs"><input type="checkbox" checked={form.days.includes(index)} onChange={(e) => setForm({ ...form, days: e.target.checked ? [...form.days, index] : form.days.filter((x) => x !== index) })} />{day}</label>)}</div></fieldset>}

        <div className="mt-4 rounded-2xl bg-cream p-3"><h4 className="text-sm font-bold text-forest">Private verification documents</h4><p className="mt-1 text-xs text-ink-soft">PDF, PNG or JPEG · up to 10 MB each. Stored privately and shared only with authorized reviewers.</p>
          {(applicationType === "individual" ? [["identity", "Identity document"], ["pilot_certificate", "Pilot certificate"], ["drone_registration", "Drone registration"]] : applicationType === "company" ? [["identity", "Representative identity"], ["business_registration", "Business registration"]] : [["identity", "Identity document"], ["qualification", "Qualification document"]]).map(([kind, label]) => <label key={kind} className="mt-3 block text-xs font-semibold text-ink-soft">{label}<input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => chooseDocument(kind, e.target.files?.[0])} className="mt-1 block min-h-10 w-full text-xs" /></label>)}
          {applicationId && <p className="mt-2 break-all text-[11px] text-emerald-900">Draft ID: {applicationId}</p>}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2"><button disabled={busy} onClick={() => void createOrUpdateApplication()} className="min-h-11 rounded-full border border-forest text-sm font-bold text-forest disabled:opacity-50">{busy ? "Saving…" : "Save draft & upload"}</button><button disabled={busy || !applicationId} onClick={() => void submitApplication()} className="min-h-11 rounded-full bg-forest text-sm font-bold text-white disabled:opacity-50">Submit for review</button></div>
      </section>
      <section className="rounded-3xl border border-line bg-white p-4 shadow-soft"><h3 className="font-semibold text-forest">Your applications</h3>{applications.length ? applications.map((app) => <div key={app.id} className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-cream p-3"><div><b className="text-sm text-forest">{statusLabel(app.type)}</b><div className="text-xs text-ink-soft">{app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : "Draft"}{app.review_notes ? ` · ${app.review_notes}` : ""}</div></div><span className="rounded-full bg-leaf-pale px-3 py-1 text-xs font-bold text-forest">{statusLabel(app.status)}</span></div>) : <p className="mt-2 text-sm text-ink-soft">No applications submitted.</p>}</section>
    </div>}
  </div>;
}

function TextField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return <label className="block text-xs font-semibold text-ink-soft">{label}<input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink" /></label>;
}

function ProviderCard({ provider, onBook }: { provider: DroneProvider; onBook: () => void }) {
  return <section className="rounded-3xl border border-line bg-white p-4 shadow-soft">
    <div className="flex items-start gap-3"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-leaf-pale text-2xl">🚁</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-bold text-forest">{provider.name}</h3><span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-800">✓ Verified</span></div>{provider.company && <p className="text-xs text-ink-soft">{provider.company}</p>}<p className="mt-1 text-xs text-ink-soft">{provider.qualification || "Credentials verified"} · {provider.experience_years} years experience</p></div></div>
    <div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div className="rounded-xl bg-cream p-2.5"><span className="block text-ink-soft">Configured rate</span><b className="mt-0.5 block text-forest">{currency(provider.price_per_acre)} / acre</b></div><div className="rounded-xl bg-cream p-2.5"><span className="block text-ink-soft">Completed services</span><b className="mt-0.5 block text-forest">{provider.completed_services}</b></div><div className="rounded-xl bg-cream p-2.5"><span className="block text-ink-soft">Rating</span><b className="mt-0.5 block text-forest">{provider.rating ? `★ ${provider.rating} (${provider.review_count})` : "No reviews yet"}</b></div><div className="rounded-xl bg-cream p-2.5"><span className="block text-ink-soft">Availability</span><b className="mt-0.5 block text-forest">{(provider.availability.days || []).map((day) => WEEK_DAYS[day]).join(", ") || "Not listed"}</b></div></div>
    <p className="mt-3 text-xs text-ink-soft"><b className="text-forest">Drone:</b> {provider.drones.map((drone) => [drone.manufacturer, drone.model].filter(Boolean).join(" ")).join(" · ")}</p>
    <p className="mt-1 text-xs text-ink-soft"><b className="text-forest">Areas:</b> {provider.service_areas.map((area) => [area.village, area.taluk, area.district, area.state].filter(Boolean).join(", ")).join(" · ")}</p>
    <p className="mt-1 text-xs text-ink-soft"><b className="text-forest">Languages:</b> {provider.languages.join(", ") || "Not specified"}</p>
    <button onClick={onBook} className="mt-4 min-h-11 w-full rounded-full bg-forest text-sm font-bold text-white">Request a booking</button>
  </section>;
}
