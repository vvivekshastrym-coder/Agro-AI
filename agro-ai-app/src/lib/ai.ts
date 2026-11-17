import { supabase } from "./supabaseClient";

/**
 * All AI calls go through Supabase Edge Functions so the Anthropic API key
 * never reaches the browser. Each function reads ANTHROPIC_API_KEY from
 * Supabase secrets (see the functions under supabase/functions and the README).
 */

export async function agroChat(
  message: string,
  language: string,
  location: string,
  farmSummary?: string
) {
  const { data, error } = await supabase.functions.invoke("agro-chat", {
    body: { message, language, location, farmSummary }
  });
  if (error) throw error;
  return data.reply as string;
}

export async function diagnoseLeaf(imageBase64: string, mediaType: string, cropHint: string, language: string) {
  const { data, error } = await supabase.functions.invoke("diagnose-leaf", {
    body: { imageBase64, mediaType, cropHint, language }
  });
  if (error) throw error;
  return data as { severity: string; report: string };
}

export async function mandiPrice(crop: string, state: string, language: string) {
  const { data, error } = await supabase.functions.invoke("mandi-price", {
    body: { crop, state, language }
  });
  if (error) throw error;
  return data as { available: boolean; price?: string; trend?: string; summary: string };
}

/** Open-Meteo is free, keyless, and CORS-friendly — called directly from the browser. */
export async function fetchWeather(lat: number, lon: number) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode&timezone=auto&forecast_days=5`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Weather request failed");
  return res.json();
}

/** Free, keyless geocoding for turning a place name into lat/lon (Open-Meteo's own geocoder). */
export async function geocode(place: string) {
  const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(place)}&count=1&language=en&format=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Geocoding failed");
  const data = await res.json();
  if (!data.results || !data.results.length) throw new Error("Location not found");
  const r = data.results[0];
  return { lat: r.latitude, lon: r.longitude, label: `${r.name}, ${r.admin1 ?? ""}`.trim() };
}
