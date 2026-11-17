import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "./useAuth";
import {
  FarmerProfile,
  Farm,
  FarmCrop,
  getFarmerProfile,
  getFarmerFarms,
  getFarmCrops
} from "./farmerProfile";

interface AppState {
  language: string;
  setLanguage: (l: string) => void;
  location: string;
  setLocation: (l: string) => void;
  profile: FarmerProfile | null;
  farms: Farm[];
  crops: FarmCrop[];
  farmSummary: string;
  refreshProfile: () => Promise<void>;
  loadingProfile: boolean;
}

const AppContext = createContext<AppState | null>(null);

function buildFarmSummary(
  profile: FarmerProfile | null,
  farms: Farm[],
  crops: FarmCrop[]
): string {
  const parts: string[] = [];
  if (profile) {
    const loc = [profile.village, profile.taluk, profile.district, profile.state]
      .filter(Boolean)
      .join(", ");
    if (loc) parts.push(`Location: ${loc}`);
    if (profile.full_name) parts.push(`Farmer: ${profile.full_name}`);
  }
  if (farms.length > 0) {
    const totalArea = farms.reduce(
      (acc, f) => acc + (typeof f.area_value === "number" ? f.area_value : 0),
      0
    );
    const unit = farms[0]?.area_unit || "acres";
    if (totalArea > 0) parts.push(`Land: ${totalArea} ${unit}`);
    const irrigation = Array.from(new Set(farms.flatMap((f) => f.irrigation || []))).join(", ");
    if (irrigation) parts.push(`Irrigation: ${irrigation}`);
  }
  if (crops.length > 0) {
    const cropNames = Array.from(new Set(crops.map((c) => c.crop_name))).join(", ");
    parts.push(`Standing Crops: ${cropNames}`);
  }
  return parts.join(". ");
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  const [language, setLanguageState] = useState(
    () => localStorage.getItem("agroai_lang") || "kn"
  );
  const [location, setLocationState] = useState(
    () => localStorage.getItem("agroai_loc") || "Mandya, Karnataka"
  );

  const [profile, setProfile] = useState<FarmerProfile | null>(null);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [crops, setCrops] = useState<FarmCrop[]>([]);
  const [loadingProfile, setLoadingProfile] = useState(false);

  const setLanguage = useCallback((l: string) => {
    setLanguageState(l);
    localStorage.setItem("agroai_lang", l);
  }, []);

  const setLocation = useCallback((loc: string) => {
    setLocationState(loc);
    localStorage.setItem("agroai_loc", loc);
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!user) {
      setProfile(null);
      setFarms([]);
      setCrops([]);
      return;
    }
    setLoadingProfile(true);
    try {
      const [loadedProfile, loadedFarms] = await Promise.all([
        getFarmerProfile(user.id),
        getFarmerFarms(user.id)
      ]);

      if (loadedProfile) {
        setProfile(loadedProfile);
        if (loadedProfile.language) {
          setLanguage(loadedProfile.language);
        }
        if (loadedProfile.village && loadedProfile.district) {
          setLocation(`${loadedProfile.village}, ${loadedProfile.district}`);
        } else if (loadedProfile.district) {
          setLocation(`${loadedProfile.district}, ${loadedProfile.state || "Karnataka"}`);
        }
      }

      if (loadedFarms && loadedFarms.length > 0) {
        setFarms(loadedFarms);
        const farmIds = loadedFarms.map((f) => f.id).filter(Boolean) as string[];
        if (farmIds.length > 0) {
          const loadedCrops = await getFarmCrops(farmIds);
          setCrops(loadedCrops);
        } else {
          setCrops([]);
        }
      } else {
        setFarms([]);
        setCrops([]);
      }
    } catch (err) {
      console.error("Failed to load user farmer profile:", err);
    } finally {
      setLoadingProfile(false);
    }
  }, [user, setLanguage, setLocation]);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const farmSummary = useMemo(
    () => buildFarmSummary(profile, farms, crops),
    [profile, farms, crops]
  );

  return (
    <AppContext.Provider
      value={{
        language,
        setLanguage,
        location,
        setLocation,
        profile,
        farms,
        crops,
        farmSummary,
        refreshProfile,
        loadingProfile
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
