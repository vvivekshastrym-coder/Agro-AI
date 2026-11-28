import { Capacitor } from "@capacitor/core";
import { FirebaseAppCheck } from "@capacitor-firebase/app-check";
import { supabase } from "./supabaseClient";

const API_BASE_URL = ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "https://www.agroai.live").replace(/\/+$/, "");
let appCheckInitialization: Promise<void> | null = null;

async function getAttestationToken(): Promise<string> {
  if (Capacitor.getPlatform() !== "android") {
    throw new Error("Drone Services are available only in the Agro AI Android app.");
  }
  if (!appCheckInitialization) {
    appCheckInitialization = FirebaseAppCheck.initialize({ isTokenAutoRefreshEnabled: true });
  }
  await appCheckInitialization;
  const result = await FirebaseAppCheck.getToken({ forceRefresh: false });
  if (!result.token) throw new Error("This Android app could not verify its installation. Update the Agro AI app and try again.");
  return result.token;
}

async function droneFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const [{ data: { session } }, appCheckToken] = await Promise.all([
    supabase.auth.getSession(), getAttestationToken(),
  ]);
  if (!session?.access_token) throw new Error("Sign in to use Drone Services.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  headers.set("X-Agro-Client", "android");
  headers.set("X-Firebase-AppCheck", appCheckToken);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || detail?.error?.message || "Drone Services could not complete that request.");
  }
  return payload as T;
}

export type DroneService = "crop_spraying" | "surveying" | "mapping" | "crop_monitoring" | "other";
export type DroneProvider = {
  pilot_id: string;
  name: string;
  photo_url?: string | null;
  verified: boolean;
  company?: string | null;
  services: DroneService[];
  qualification?: string | null;
  experience_years: number;
  languages: string[];
  drones: Array<{ manufacturer?: string | null; model: string; capabilities: DroneService[]; payload_litres?: number | null }>;
  service_areas: Array<{ state: string; district: string; taluk?: string | null; village?: string | null }>;
  price_per_acre: number;
  minimum_booking_amount?: number | null;
  availability: { days?: number[] };
  rating?: number | null;
  review_count: number;
  completed_services: number;
};

export type DroneQuote = {
  currency: "INR";
  area_acres: number;
  rate_per_acre: number;
  base_service_amount: number;
  minimum_booking_amount: number;
  total: number;
};

export const droneServices = {
  providers: (params: { service: DroneService; state: string; district: string; taluk?: string; village?: string; scheduled_date?: string }) => {
    const search = new URLSearchParams({ service: params.service, state: params.state, district: params.district });
    if (params.taluk) search.set("taluk", params.taluk);
    if (params.village) search.set("village", params.village);
    if (params.scheduled_date) search.set("scheduled_date", params.scheduled_date);
    return droneFetch<{ available: boolean; providers: DroneProvider[]; message?: string }>(`/api/drone/providers?${search.toString()}`);
  },
  applications: () => droneFetch<{ applications: Array<{ id: string; type: string; status: string; submitted_at?: string; reviewed_at?: string; review_notes?: string }> }>("/api/drone/applications/mine"),
  createApplication: (application_type: "individual" | "company" | "copilot", data: Record<string, unknown>) =>
    droneFetch<{ id: string; status: string }>("/api/drone/applications", { method: "POST", body: JSON.stringify({ application_type, data }) }),
  updateApplication: (id: string, data: Record<string, unknown>) =>
    droneFetch<{ id: string; status: string }>(`/api/drone/applications/${id}`, { method: "PATCH", body: JSON.stringify({ data }) }),
  uploadDocument: (id: string, documentType: string, file: File) => {
    const form = new FormData(); form.append("file", file);
    return droneFetch(`/api/drone/applications/${id}/documents?document_type=${encodeURIComponent(documentType)}`, { method: "POST", body: form });
  },
  submitApplication: (id: string) => droneFetch(`/api/drone/applications/${id}/submit`, { method: "POST" }),
  createBooking: (body: { provider_pilot_id: string; service_category: DroneService; state: string; district: string; taluk?: string; village?: string; area_acres: number; scheduled_date: string; farmer_notes?: string }) =>
    droneFetch<{ id: string; status: string; quote: DroneQuote; message: string }>("/api/drone/bookings", { method: "POST", body: JSON.stringify(body) }),
  myBookings: () => droneFetch<{ bookings: Array<Record<string, any>> }>("/api/drone/bookings/mine"),
  cancelBooking: (id: string, reason: string) => droneFetch(`/api/drone/bookings/${id}/cancel?reason=${encodeURIComponent(reason)}`, { method: "POST" }),
  confirmCompletion: (id: string) => droneFetch(`/api/drone/bookings/${id}/confirm-completion`, { method: "POST" }),
  reviewBooking: (id: string, rating: number, review: string) => droneFetch(`/api/drone/bookings/${id}/review`, { method: "POST", body: JSON.stringify({ rating, review }) }),
};
