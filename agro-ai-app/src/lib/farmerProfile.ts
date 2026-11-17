import { supabase } from "./supabaseClient";

export interface NotificationPreferences {
  sms: boolean;
  whatsapp: boolean;
  weather_alerts: boolean;
}

export interface FarmerProfile {
  user_id: string;
  full_name: string;
  language: string;
  state: string;
  district: string;
  taluk: string;
  village: string;
  notification_preferences: NotificationPreferences;
  onboarding_status: "draft" | "complete";
  created_at?: string;
  updated_at?: string;
}

export interface Farm {
  id?: string;
  user_id?: string;
  name: string;
  farming_types: string[];
  area_value: number | "";
  area_unit: "acres" | "hectares" | "guntas";
  ownership: "own" | "leased" | "tenant";
  irrigation: string[];
  created_at?: string;
}

export interface FarmCrop {
  id?: string;
  farm_id?: string;
  crop_name: string;
  area_value: number | "";
  sown_on: string;
  created_at?: string;
}

export const SUPPORTED_LANGUAGES = [
  { code: "kn", label: "ಕನ್ನಡ (Kannada)", native: "ಕನ್ನಡ" },
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "हिंदी (Hindi)", native: "हिंदी" },
  { code: "te", label: "తెలుగు (Telugu - Beta)", native: "తెలుగు" },
  { code: "ta", label: "தமிழ் (Tamil - Beta)", native: "தமிழ்" }
];

export const KARNATAKA_LOCATION_DATA: Record<string, string[]> = {
  Mandya: ["Mandya", "Maddur", "Malavalli", "Pandavapura", "Nagamangala", "Krishnarajpet", "Srirangapatna"],
  Mysuru: ["Mysuru", "Hunsur", "Nanjangud", "T. Narasipura", "Piriyapatna", "Heggadadevankote", "Saragur"],
  Hassan: ["Hassan", "Arsikere", "Channarayapatna", "Holenarasipura", "Sakleshpur", "Alur", "Arkalgud", "Belur"],
  Kolar: ["Kolar", "Bangarapet", "Malur", "Mulbagal", "Srinivaspur"],
  Tumakuru: ["Tumakuru", "Gubbi", "Kunigal", "Madhugiri", "Pavagada", "Sira", "Tiptur", "Chikkanayakanahalli", "Turuvekere", "Koratagere"],
  Belagavi: ["Belagavi", "Bailhongal", "Chikkodi", "Gokak", "Hukkeri", "Khanapur", "Athani", "Ramdurg", "Raybag", "Saundatti"],
  Davanagere: ["Davanagere", "Harihar", "Honnali", "Channagiri", "Jagalur", "Nyamathi"],
  Shivamogga: ["Shivamogga", "Bhadravati", "Sagar", "Shikaripura", "Soraba", "Tirthahalli", "Hosanagara"],
  Ballari: ["Ballari", "Kampli", "Siruguppa", "Kurugodu", "Sandur"],
  Kalaburagi: ["Kalaburagi", "Afzalpur", "Aland", "Chincholi", "Chitapur", "Jevargi", "Sedam"],
  Ramanagara: ["Ramanagara", "Channapatna", "Kanakapura", "Magadi"],
  Chikkamagaluru: ["Chikkamagaluru", "Kadur", "Koppa", "Mudigere", "Narasimharajapura", "Sringeri", "Tarikere"],
  Chitradurga: ["Chitradurga", "Challakere", "Hiriyur", "Holalkere", "Hosadurga", "Molakalmuru"],
  Bengaluru_Rural: ["Devanahalli", "Doddaballapura", "Hosakote", "Nelamangala"],
  Chikkaballapur: ["Chikkaballapur", "Bagepalli", "Chintamani", "Gauribidanur", "Gudibanda", "Sidlaghatta"]
};

export const COMMON_CROPS = [
  "Ragi",
  "Paddy",
  "Maize",
  "Sugarcane",
  "Coconut",
  "Arecanut",
  "Tomato",
  "Onion",
  "Potato",
  "Beans",
  "Chilli",
  "Pulses",
  "Other"
];

export const FARMING_TYPES = [
  { id: "crop", label: "Field Crops (ಬೆಳೆಗಳು)" },
  { id: "vegetable", label: "Vegetables (ತರಕಾರಿಗಳು)" },
  { id: "fruit", label: "Horticulture / Fruits (ಹಣ್ಣಿನ ತೋಟ)" },
  { id: "dairy_livestock", label: "Dairy / Livestock (ಹೈನುಗಾರಿಕೆ)" },
  { id: "mixed", label: "Mixed Farming (ಮಿಶ್ರ ಕೃಷಿ)" },
  { id: "other", label: "Other (ಇತರೆ)" }
];

export const IRRIGATION_SOURCES = [
  { id: "borewell", label: "Borewell (ಬೋರ್‌ವೆಲ್)" },
  { id: "canal", label: "Canal (ಕಾಲುವೆ ನೀರು)" },
  { id: "rainfed", label: "Rainfed (ಮಳೆ ಆಶ್ರಿತ)" },
  { id: "drip", label: "Drip Irrigation (ಹನಿ ನೀರಾವರಿ)" },
  { id: "sprinkler", label: "Sprinkler (ತುಂತುರು ನೀರಾವರಿ)" }
];

export const LAND_OWNERSHIP_OPTIONS = [
  { id: "own", label: "Own (ಸ್ವಂತ)" },
  { id: "leased", label: "Leased (ಗುತ್ತಿಗೆ)" },
  { id: "tenant", label: "Tenant (ಪಾಲುದಾರ)" }
];

/**
 * Calculates profile completion percentage based ONLY on real required fields:
 * - full_name (required)
 * - language (required)
 * - state (required)
 * - district (required)
 * - village (required)
 * - at least 1 farm with name and area/farming types
 */
export function calculateProfileCompletion(profile?: Partial<FarmerProfile> | null, farms?: Farm[]): {
  percentage: number;
  missing: string[];
} {
  const missing: string[] = [];
  let score = 0;
  const total = 6;

  if (profile?.full_name?.trim()) {
    score++;
  } else {
    missing.push("Full Name");
  }

  if (profile?.language?.trim()) {
    score++;
  } else {
    missing.push("Language");
  }

  if (profile?.state?.trim()) {
    score++;
  } else {
    missing.push("State");
  }

  if (profile?.district?.trim()) {
    score++;
  } else {
    missing.push("District");
  }

  if (profile?.village?.trim()) {
    score++;
  } else {
    missing.push("Village");
  }

  const hasValidFarm = Boolean(
    farms &&
      farms.length > 0 &&
      farms.some((f) => f.name?.trim() && (typeof f.area_value === "number" || f.farming_types?.length > 0))
  );

  if (hasValidFarm) {
    score++;
  } else {
    missing.push("At least one Farm details");
  }

  const percentage = Math.round((score / total) * 100);
  return { percentage, missing };
}

/**
 * Fetch a farmer's profile from Supabase by user_id
 */
export async function getFarmerProfile(userId: string): Promise<FarmerProfile | null> {
  const { data, error } = await supabase
    .from("farmer_profiles")
    .select("*")
    .eq("user_id", userId)
    .maybeSingle();

  if (error) {
    console.error("Error fetching farmer profile:", error);
    return null;
  }
  return data as FarmerProfile | null;
}

/**
 * Fetch all farms for a farmer
 */
export async function getFarmerFarms(userId: string): Promise<Farm[]> {
  const { data, error } = await supabase
    .from("farms")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("Error fetching farms:", error);
    return [];
  }
  return (data || []) as Farm[];
}

/**
 * Fetch crops associated with farm IDs
 */
export async function getFarmCrops(farmIds: string[]): Promise<FarmCrop[]> {
  if (!farmIds || farmIds.length === 0) return [];
  const { data, error } = await supabase
    .from("farm_crops")
    .select("*")
    .in("farm_id", farmIds)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("Error fetching farm crops:", error);
    return [];
  }
  return (data || []) as FarmCrop[];
}

/**
 * Save or update a farmer profile (Upserts on user_id)
 */
export async function saveFarmerProfile(profile: Partial<FarmerProfile> & { user_id: string }): Promise<FarmerProfile> {
  const payload = {
    ...profile,
    updated_at: new Date().toISOString()
  };

  const { data, error } = await supabase
    .from("farmer_profiles")
    .upsert(payload, { onConflict: "user_id" })
    .select()
    .single();

  if (error) throw error;
  return data as FarmerProfile;
}

/**
 * Persist farms and their crops in a clean operation
 */
export async function saveFarmsAndCrops(
  userId: string,
  farms: Farm[],
  cropsByFarmIndex: Record<number, FarmCrop[]>
): Promise<Farm[]> {
  const savedFarms: Farm[] = [];

  for (let i = 0; i < farms.length; i++) {
    const f = farms[i];
    const farmPayload: any = {
      user_id: userId,
      name: f.name || `Farm ${i + 1}`,
      farming_types: f.farming_types || [],
      area_value: typeof f.area_value === "number" ? f.area_value : null,
      area_unit: f.area_unit || "acres",
      ownership: f.ownership || "own",
      irrigation: f.irrigation || []
    };

    if (f.id) {
      farmPayload.id = f.id;
    }

    const { data: savedFarm, error: farmErr } = await supabase
      .from("farms")
      .upsert(farmPayload)
      .select()
      .single();

    if (farmErr) throw farmErr;
    savedFarms.push(savedFarm as Farm);

    // Save crops for this farm
    const farmCrops = cropsByFarmIndex[i] || [];
    if (farmCrops.length > 0) {
      for (const crop of farmCrops) {
        if (!crop.crop_name?.trim()) continue;
        const cropPayload: any = {
          farm_id: savedFarm.id,
          crop_name: crop.crop_name,
          area_value: typeof crop.area_value === "number" ? crop.area_value : null,
          sown_on: crop.sown_on || null
        };
        if (crop.id) cropPayload.id = crop.id;

        const { error: cropErr } = await supabase.from("farm_crops").upsert(cropPayload);
        if (cropErr) {
          console.warn("Error saving crop:", cropErr);
        }
      }
    }
  }

  return savedFarms;
}
