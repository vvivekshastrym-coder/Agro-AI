import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/useAuth";
import { useApp } from "../lib/AppContext";
import { getDictionary } from "../lib/i18n";
import {
  FarmerProfile,
  Farm,
  FarmCrop,
  SUPPORTED_LANGUAGES,
  KARNATAKA_LOCATION_DATA,
  COMMON_CROPS,
  FARMING_TYPES,
  IRRIGATION_SOURCES,
  LAND_OWNERSHIP_OPTIONS,
  calculateProfileCompletion,
  getFarmerProfile,
  getFarmerFarms,
  getFarmCrops,
  saveFarmerProfile,
  saveFarmsAndCrops
} from "../lib/farmerProfile";

export default function Onboarding() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { language, setLanguage, setLocation, refreshProfile } = useApp();

  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1); // 1: Basics, 2: Location, 3: Farm, 4: Crops, 5: Review
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [savingDraft, setSavingDraft] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [fullName, setFullName] = useState("");
  const [prefLang, setPrefLang] = useState(language || "kn");
  const [stateName, setStateName] = useState("Karnataka");
  const [district, setDistrict] = useState("Mandya");
  const [taluk, setTaluk] = useState("");
  const [village, setVillage] = useState("");
  const [gpsDetecting, setGpsDetecting] = useState(false);
  const [gpsNote, setGpsNote] = useState<string | null>(null);

  // Farm State (Supports multiple farms)
  const [farms, setFarms] = useState<Farm[]>([
    {
      name: "Main Farm (ಮುಖ್ಯ ಹೊಲ)",
      farming_types: ["crop"],
      area_value: "",
      area_unit: "acres",
      ownership: "own",
      irrigation: ["borewell"]
    }
  ]);
  const [currentFarmIdx, setCurrentFarmIdx] = useState(0);

  // Crops State per farm index
  const [cropsByFarm, setCropsByFarm] = useState<Record<number, FarmCrop[]>>({
    0: []
  });
  const [cropSearch, setCropSearch] = useState("");
  const [customCropName, setCustomCropName] = useState("");

  const t = getDictionary(prefLang);

  // Load existing profile / draft on mount
  useEffect(() => {
    async function loadDraft() {
      if (!user) return;
      try {
        const [profile, loadedFarms] = await Promise.all([
          getFarmerProfile(user.id),
          getFarmerFarms(user.id)
        ]);

        if (profile) {
          if (profile.full_name) setFullName(profile.full_name);
          if (profile.language) {
            setPrefLang(profile.language);
            setLanguage(profile.language);
          }
          if (profile.state) setStateName(profile.state);
          if (profile.district) setDistrict(profile.district);
          if (profile.taluk) setTaluk(profile.taluk);
          if (profile.village) setVillage(profile.village);

          // If profile is already marked complete, redirect to home
          if (profile.onboarding_status === "complete") {
            navigate("/", { replace: true });
            return;
          }
        }

        if (loadedFarms && loadedFarms.length > 0) {
          setFarms(loadedFarms);
          const farmIds = loadedFarms.map((f) => f.id).filter(Boolean) as string[];
          if (farmIds.length > 0) {
            const loadedCrops = await getFarmCrops(farmIds);
            const grouped: Record<number, FarmCrop[]> = {};
            loadedFarms.forEach((f, idx) => {
              grouped[idx] = loadedCrops.filter((c) => c.farm_id === f.id);
            });
            setCropsByFarm(grouped);
          }
        }
      } catch (err) {
        console.error("Failed to load onboarding draft:", err);
      } finally {
        setLoadingInitial(false);
      }
    }
    loadDraft();
  }, [user, navigate, setLanguage]);

  // Available taluks for currently selected Karnataka district
  const availableTaluks = KARNATAKA_LOCATION_DATA[district] || [];

  // GPS auto-detection handler (Optional)
  const handleDetectGPS = () => {
    if (!navigator.geolocation) {
      setGpsNote("GPS not supported on this browser.");
      return;
    }
    setGpsDetecting(true);
    setGpsNote(null);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;
          // Approximate district/state lookup via Nominatim
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
            { headers: { "User-Agent": "AgroAI/1.0" } }
          );
          if (res.ok) {
            const data = await res.json();
            const addr = data.address || {};
            const detectedState = addr.state || "Karnataka";
            const detectedDistrict = addr.state_district || addr.county || addr.city || "";
            const detectedVillage = addr.village || addr.suburb || addr.town || "";

            setStateName(detectedState);
            // Match with Karnataka districts if available
            const matchedDist = Object.keys(KARNATAKA_LOCATION_DATA).find(
              (d) => d.toLowerCase() === detectedDistrict.toLowerCase()
            );
            if (matchedDist) setDistrict(matchedDist);
            if (detectedVillage) setVillage(detectedVillage);
            setGpsNote(`✓ Location matched: ${detectedVillage ? detectedVillage + ", " : ""}${detectedDistrict || detectedState}`);
          } else {
            setGpsNote(`✓ Coordinates detected (${latitude.toFixed(2)}, ${longitude.toFixed(2)})`);
          }
        } catch {
          setGpsNote("Location retrieved via GPS. Please confirm district & village.");
        } finally {
          setGpsDetecting(false);
        }
      },
      (err) => {
        console.warn("GPS error:", err.message);
        setGpsDetecting(false);
        setGpsNote("Could not detect location. You can select your district and village manually.");
      },
      { timeout: 10000, enableHighAccuracy: false }
    );
  };

  // Draft auto-saver
  const saveCurrentDraft = async (showNotification = true): Promise<boolean> => {
    if (!user) return false;
    setSavingDraft(true);
    setErrorMessage(null);
    try {
      await saveFarmerProfile({
        user_id: user.id,
        full_name: fullName.trim(),
        language: prefLang,
        state: stateName.trim(),
        district: district.trim(),
        taluk: taluk.trim(),
        village: village.trim(),
        notification_preferences: { sms: true, whatsapp: true, weather_alerts: true },
        onboarding_status: "draft"
      });

      const savedFarms = await saveFarmsAndCrops(user.id, farms, cropsByFarm);
      if (savedFarms.length > 0) {
        setFarms(savedFarms);
      }

      if (showNotification) {
        setStatusMessage(t.draftSaved);
        setTimeout(() => setStatusMessage(null), 3000);
      }
      return true;
    } catch (err: any) {
      console.error("Save draft error:", err);
      setErrorMessage(err.message || "Failed to save draft. Please retry.");
      return false;
    } finally {
      setSavingDraft(false);
    }
  };

  // Step 1 Validation
  const validateStep1 = () => {
    if (!fullName.trim()) {
      setErrorMessage("Please enter your full name (ಹೆಸರನ್ನು ನಮೂದಿಸಿ).");
      return false;
    }
    setErrorMessage(null);
    return true;
  };

  // Step 2 Validation
  const validateStep2 = () => {
    if (!stateName.trim() || !district.trim() || !village.trim()) {
      setErrorMessage("Please provide your State, District and Village (ಗ್ರಾಮದ ವಿವರ ನಮೂದಿಸಿ).");
      return false;
    }
    setErrorMessage(null);
    return true;
  };

  // Step 3 Validation
  const validateStep3 = () => {
    const mainFarm = farms[0];
    if (!mainFarm || mainFarm.area_value === "" || Number(mainFarm.area_value) <= 0) {
      setErrorMessage("Please enter land area for at least one farm (ಜಮೀನಿನ ವಿಸ್ತೀರ್ಣ ನಮೂದಿಸಿ).");
      return false;
    }
    setErrorMessage(null);
    return true;
  };

  const handleNext = async () => {
    if (step === 1) {
      if (!validateStep1()) return;
      await saveCurrentDraft(false);
      setLanguage(prefLang);
      setStep(2);
    } else if (step === 2) {
      if (!validateStep2()) return;
      await saveCurrentDraft(false);
      setLocation(`${village.trim()}, ${district.trim()}`);
      setStep(3);
    } else if (step === 3) {
      if (!validateStep3()) return;
      await saveCurrentDraft(false);
      setStep(4);
    } else if (step === 4) {
      await saveCurrentDraft(false);
      setStep(5);
    }
  };

  const handleBack = () => {
    setErrorMessage(null);
    if (step > 1) {
      setStep((s) => (s - 1) as any);
    }
  };

  const handleFinalSubmit = async () => {
    if (!user) return;
    if (!validateStep1() || !validateStep2() || !validateStep3()) {
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    try {
      await saveFarmerProfile({
        user_id: user.id,
        full_name: fullName.trim(),
        language: prefLang,
        state: stateName.trim(),
        district: district.trim(),
        taluk: taluk.trim(),
        village: village.trim(),
        notification_preferences: { sms: true, whatsapp: true, weather_alerts: true },
        onboarding_status: "complete"
      });

      await saveFarmsAndCrops(user.id, farms, cropsByFarm);

      setLanguage(prefLang);
      setLocation(`${village.trim()}, ${district.trim()}`);
      await refreshProfile();

      navigate("/", { replace: true });
    } catch (err: any) {
      console.error("Submission failed:", err);
      setErrorMessage(err.message || "Failed to complete setup. Please retry.");
    } finally {
      setSubmitting(false);
    }
  };

  // Farm manipulation helpers
  const updateFarm = (index: number, updates: Partial<Farm>) => {
    setFarms((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], ...updates };
      return copy;
    });
  };

  const addAnotherFarm = () => {
    const nextIdx = farms.length;
    setFarms((prev) => [
      ...prev,
      {
        name: `Farm ${nextIdx + 1} (ಜಮೀನು ${nextIdx + 1})`,
        farming_types: ["crop"],
        area_value: "",
        area_unit: "acres",
        ownership: "own",
        irrigation: ["borewell"]
      }
    ]);
    setCropsByFarm((prev) => ({ ...prev, [nextIdx]: [] }));
    setCurrentFarmIdx(nextIdx);
  };

  // Crop toggle helper for current farm
  const currentCrops = cropsByFarm[currentFarmIdx] || [];

  const toggleCrop = (cropName: string) => {
    setCropsByFarm((prev) => {
      const list = prev[currentFarmIdx] || [];
      const exists = list.some((c) => c.crop_name.toLowerCase() === cropName.toLowerCase());
      let updated: FarmCrop[];
      if (exists) {
        updated = list.filter((c) => c.crop_name.toLowerCase() !== cropName.toLowerCase());
      } else {
        updated = [...list, { crop_name: cropName, area_value: "", sown_on: "" }];
      }
      return { ...prev, [currentFarmIdx]: updated };
    });
  };

  const updateCropDetails = (cropName: string, updates: Partial<FarmCrop>) => {
    setCropsByFarm((prev) => {
      const list = prev[currentFarmIdx] || [];
      const updated = list.map((c) => (c.crop_name === cropName ? { ...c, ...updates } : c));
      return { ...prev, [currentFarmIdx]: updated };
    });
  };

  const addCustomCrop = () => {
    if (!customCropName.trim()) return;
    toggleCrop(customCropName.trim());
    setCustomCropName("");
  };

  // Profile completion calculation strictly based on 6 core required fields
  const completion = calculateProfileCompletion(
    {
      full_name: fullName,
      language: prefLang,
      state: stateName,
      district,
      village
    },
    farms
  );

  if (loadingInitial) {
    return (
      <div className="min-h-screen bg-cream flex flex-col items-center justify-center p-6 text-center">
        <div className="w-10 h-10 border-4 border-forest border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-forest font-semibold">Loading your setup…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      {/* Sticky Header with Progress Bar */}
      <header className="sticky top-0 bg-white/95 backdrop-blur border-b border-forest/10 px-4 py-3 z-20">
        <div className="flex items-center justify-between max-w-md mx-auto">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-forest text-sand font-bold text-xs flex items-center justify-center">
              {step < 5 ? step : "✓"}
            </span>
            <div>
              <h1 className="text-sm font-bold text-forest font-serif">{t.onboardingHeader}</h1>
              <p className="text-[11px] text-ink-soft">
                {step === 5 ? "Review & Confirm" : `Step ${step} of 4`}
              </p>
            </div>
          </div>
          <button
            onClick={() => saveCurrentDraft(true)}
            disabled={savingDraft}
            className="text-xs font-semibold text-forest hover:text-forest-light px-3 py-1.5 rounded-full border border-forest/20 hover:bg-forest/5 active:scale-95 transition-all"
          >
            {savingDraft ? "Saving…" : t.saveAndExit}
          </button>
        </div>

        {/* Progress Line */}
        <div className="w-full bg-forest/10 h-1.5 rounded-full mt-2.5 overflow-hidden max-w-md mx-auto">
          <div
            className="bg-forest h-full transition-all duration-300"
            style={{ width: `${Math.min(100, (step / 4) * 100)}%` }}
          />
        </div>
      </header>

      {/* Floating Status Notification */}
      {statusMessage && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 bg-forest text-sand text-xs font-medium px-4 py-2 rounded-full shadow-lg z-30 animate-fade-in">
          {statusMessage}
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-md w-full mx-auto p-4 pb-28">
        {errorMessage && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
            {errorMessage}
          </div>
        )}

        {/* STEP 1: BASICS */}
        {step === 1 && (
          <div className="space-y-5 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold font-serif text-forest">{t.stepBasicsTitle}</h2>
              <p className="text-xs text-ink-soft mt-1">{t.stepBasicsSub}</p>
            </div>

            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">{t.fullNameLabel}</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={t.fullNamePlaceholder}
                className="w-full h-12 px-4 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-ink mb-2">{t.prefLangLabel}</label>
              <div className="grid grid-cols-1 gap-2">
                {SUPPORTED_LANGUAGES.map((lang) => {
                  const isSelected = prefLang === lang.code;
                  return (
                    <button
                      key={lang.code}
                      type="button"
                      onClick={() => setPrefLang(lang.code)}
                      className={`w-full p-3.5 rounded-xl border text-left flex items-center justify-between transition-all ${
                        isSelected
                          ? "border-forest bg-forest/10 ring-2 ring-forest"
                          : "border-forest/15 bg-white hover:bg-forest/5"
                      }`}
                    >
                      <div>
                        <span className="text-sm font-bold text-forest">{lang.label}</span>
                        {(lang.code === "te" || lang.code === "ta") && (
                          <p className="text-[11px] text-amber-700 mt-0.5">
                            {lang.code === "te" ? t.fallbackNoteTe : t.fallbackNoteTa}
                          </p>
                        )}
                      </div>
                      <div
                        className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                          isSelected ? "border-forest bg-forest text-white" : "border-gray-300"
                        }`}
                      >
                        {isSelected && <span className="text-[10px]">✓</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: LOCATION */}
        {step === 2 && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold font-serif text-forest">{t.stepLocationTitle}</h2>
              <p className="text-xs text-ink-soft mt-1">{t.stepLocationSub}</p>
            </div>

            {/* GPS Optional Detection */}
            <div className="p-3.5 rounded-xl bg-forest/5 border border-forest/15 space-y-2">
              <button
                type="button"
                onClick={handleDetectGPS}
                disabled={gpsDetecting}
                className="w-full h-11 bg-white hover:bg-forest/5 active:bg-forest/10 border border-forest/20 text-forest font-semibold text-xs rounded-lg flex items-center justify-center gap-2 transition-colors shadow-sm"
              >
                {gpsDetecting ? t.gpsDetecting : t.gpsDetectBtn}
              </button>
              {gpsNote && <p className="text-[11px] text-forest font-medium">{gpsNote}</p>}
              <p className="text-[10px] text-ink-soft leading-tight">{t.gpsPrivacyNote}</p>
            </div>

            {/* State */}
            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">{t.stateLabel}</label>
              <select
                value={stateName}
                onChange={(e) => setStateName(e.target.value)}
                className="w-full h-12 px-3 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
              >
                <option value="Karnataka">Karnataka (ಕರ್ನಾಟಕ)</option>
                <option value="Andhra Pradesh">Andhra Pradesh</option>
                <option value="Tamil Nadu">Tamil Nadu</option>
                <option value="Maharashtra">Maharashtra</option>
                <option value="Other">Other</option>
              </select>
            </div>

            {/* District */}
            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">{t.districtLabel}</label>
              {stateName === "Karnataka" ? (
                <select
                  value={district}
                  onChange={(e) => {
                    setDistrict(e.target.value);
                    setTaluk(""); // Reset taluk when district changes
                  }}
                  className="w-full h-12 px-3 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
                >
                  {Object.keys(KARNATAKA_LOCATION_DATA).map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  placeholder="Enter district name"
                  className="w-full h-12 px-4 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
                />
              )}
            </div>

            {/* Taluk */}
            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">{t.talukLabel}</label>
              {availableTaluks.length > 0 ? (
                <select
                  value={taluk}
                  onChange={(e) => setTaluk(e.target.value)}
                  className="w-full h-12 px-3 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
                >
                  <option value="">{t.selectTaluk}</option>
                  {availableTaluks.map((tlk) => (
                    <option key={tlk} value={tlk}>
                      {tlk}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={taluk}
                  onChange={(e) => setTaluk(e.target.value)}
                  placeholder="Enter Taluk / Tehsil"
                  className="w-full h-12 px-4 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
                />
              )}
            </div>

            {/* Village */}
            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">{t.villageLabel}</label>
              <input
                type="text"
                value={village}
                onChange={(e) => setVillage(e.target.value)}
                placeholder={t.villagePlaceholder}
                className="w-full h-12 px-4 rounded-xl border border-forest/20 bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-forest font-medium"
              />
            </div>
          </div>
        )}

        {/* STEP 3: FARM DETAILS */}
        {step === 3 && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold font-serif text-forest">{t.stepFarmTitle}</h2>
              <p className="text-xs text-ink-soft mt-1">{t.stepFarmSub}</p>
            </div>

            {/* Multiple Farm Tabs */}
            {farms.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {farms.map((f, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setCurrentFarmIdx(idx)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-colors ${
                      currentFarmIdx === idx
                        ? "bg-forest text-sand"
                        : "bg-white border border-forest/20 text-forest"
                    }`}
                  >
                    {f.name || `Farm ${idx + 1}`}
                  </button>
                ))}
              </div>
            )}

            {/* Current Farm Fields */}
            {farms[currentFarmIdx] && (
              <div className="p-4 rounded-2xl bg-white border border-forest/15 space-y-4 shadow-sm">
                <div>
                  <label className="block text-xs font-bold text-ink mb-1">
                    {t.farmNumberTitle} Name
                  </label>
                  <input
                    type="text"
                    value={farms[currentFarmIdx].name}
                    onChange={(e) => updateFarm(currentFarmIdx, { name: e.target.value })}
                    placeholder="e.g. Main Plot"
                    className="w-full h-11 px-3.5 rounded-xl border border-forest/20 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-forest"
                  />
                </div>

                {/* Land Area and Unit */}
                <div>
                  <label className="block text-xs font-bold text-ink mb-1">{t.landAreaLabel}</label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={farms[currentFarmIdx].area_value}
                      onChange={(e) =>
                        updateFarm(currentFarmIdx, {
                          area_value: e.target.value === "" ? "" : parseFloat(e.target.value)
                        })
                      }
                      placeholder="e.g. 3.5"
                      className="flex-1 h-12 px-4 rounded-xl border border-forest/20 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-forest"
                    />
                    <select
                      value={farms[currentFarmIdx].area_unit}
                      onChange={(e) =>
                        updateFarm(currentFarmIdx, { area_unit: e.target.value as any })
                      }
                      className="w-32 h-12 px-3 rounded-xl border border-forest/20 bg-forest/5 text-forest text-xs font-bold focus:outline-none focus:ring-2 focus:ring-forest"
                    >
                      <option value="acres">Acres (ಎಕರೆ)</option>
                      <option value="guntas">Guntas (ಗುಂಟೆ)</option>
                      <option value="hectares">Hectares (ಹೆಕ್ಟೇರ್)</option>
                    </select>
                  </div>
                </div>

                {/* Ownership */}
                <div>
                  <label className="block text-xs font-bold text-ink mb-1.5">{t.ownershipLabel}</label>
                  <div className="grid grid-cols-3 gap-2">
                    {LAND_OWNERSHIP_OPTIONS.map((opt) => {
                      const isSel = farms[currentFarmIdx].ownership === opt.id;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => updateFarm(currentFarmIdx, { ownership: opt.id as any })}
                          className={`h-11 rounded-xl text-xs font-bold border transition-all ${
                            isSel
                              ? "bg-forest text-sand border-forest"
                              : "bg-forest/5 text-ink-soft border-transparent hover:bg-forest/10"
                          }`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Farming Type (Multi-select) */}
                <div>
                  <label className="block text-xs font-bold text-ink mb-1.5">
                    {t.farmingTypeLabel}
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {FARMING_TYPES.map((ft) => {
                      const isChecked = (farms[currentFarmIdx].farming_types || []).includes(ft.id);
                      return (
                        <button
                          key={ft.id}
                          type="button"
                          onClick={() => {
                            const current = farms[currentFarmIdx].farming_types || [];
                            const updated = isChecked
                              ? current.filter((x) => x !== ft.id)
                              : [...current, ft.id];
                            updateFarm(currentFarmIdx, { farming_types: updated });
                          }}
                          className={`p-2.5 rounded-xl text-xs font-medium border text-left transition-all flex items-center justify-between ${
                            isChecked
                              ? "border-forest bg-forest/10 text-forest font-bold"
                              : "border-forest/15 bg-white text-ink-soft hover:bg-forest/5"
                          }`}
                        >
                          <span>{ft.label}</span>
                          {isChecked && <span className="text-forest text-xs font-bold">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Irrigation (Multi-select) */}
                <div>
                  <label className="block text-xs font-bold text-ink mb-1.5">
                    {t.irrigationLabel}
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {IRRIGATION_SOURCES.map((ir) => {
                      const isChecked = (farms[currentFarmIdx].irrigation || []).includes(ir.id);
                      return (
                        <button
                          key={ir.id}
                          type="button"
                          onClick={() => {
                            const current = farms[currentFarmIdx].irrigation || [];
                            const updated = isChecked
                              ? current.filter((x) => x !== ir.id)
                              : [...current, ir.id];
                            updateFarm(currentFarmIdx, { irrigation: updated });
                          }}
                          className={`p-2.5 rounded-xl text-xs font-medium border text-left transition-all flex items-center justify-between ${
                            isChecked
                              ? "border-forest bg-forest/10 text-forest font-bold"
                              : "border-forest/15 bg-white text-ink-soft hover:bg-forest/5"
                          }`}
                        >
                          <span>{ir.label}</span>
                          {isChecked && <span className="text-forest text-xs font-bold">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Add Another Farm Option */}
            <button
              type="button"
              onClick={addAnotherFarm}
              className="w-full py-3 border-2 border-dashed border-forest/30 text-forest font-bold text-xs rounded-xl hover:bg-forest/5 transition-colors"
            >
              {t.addAnotherFarm}
            </button>
          </div>
        )}

        {/* STEP 4: CROPS */}
        {step === 4 && (
          <div className="space-y-4 animate-fade-in">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold font-serif text-forest">{t.stepCropsTitle}</h2>
                <p className="text-xs text-ink-soft mt-1">{t.stepCropsSub}</p>
              </div>
              <button
                type="button"
                onClick={() => setStep(5)}
                className="text-xs font-bold text-forest underline hover:text-forest-light whitespace-nowrap pl-2 pt-1"
              >
                {t.skipAddLater}
              </button>
            </div>

            {/* Farm Selector if multiple */}
            {farms.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {farms.map((f, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setCurrentFarmIdx(idx)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap ${
                      currentFarmIdx === idx
                        ? "bg-forest text-sand"
                        : "bg-white border border-forest/20 text-forest"
                    }`}
                  >
                    {f.name || `Farm ${idx + 1}`}
                  </button>
                ))}
              </div>
            )}

            {/* Search Input */}
            <input
              type="text"
              value={cropSearch}
              onChange={(e) => setCropSearch(e.target.value)}
              placeholder={t.searchCropsPlaceholder}
              className="w-full h-11 px-4 rounded-xl border border-forest/20 bg-white text-xs font-medium text-ink focus:outline-none focus:ring-2 focus:ring-forest"
            />

            {/* Crop Chips Selection */}
            <div className="flex flex-wrap gap-2">
              {COMMON_CROPS.filter((c) =>
                c.toLowerCase().includes(cropSearch.toLowerCase().trim())
              ).map((cName) => {
                const isSelected = currentCrops.some(
                  (c) => c.crop_name.toLowerCase() === cName.toLowerCase()
                );
                return (
                  <button
                    key={cName}
                    type="button"
                    onClick={() => toggleCrop(cName)}
                    className={`px-3.5 py-2 rounded-full text-xs font-semibold border transition-all ${
                      isSelected
                        ? "bg-forest text-sand border-forest shadow-sm"
                        : "bg-white text-ink border-forest/15 hover:bg-forest/5"
                    }`}
                  >
                    {isSelected ? `✓ ${cName}` : `+ ${cName}`}
                  </button>
                );
              })}
            </div>

            {/* Custom Crop Input */}
            <div className="flex gap-2 pt-1">
              <input
                type="text"
                value={customCropName}
                onChange={(e) => setCustomCropName(e.target.value)}
                placeholder={t.customCropPlaceholder}
                className="flex-1 h-11 px-3.5 rounded-xl border border-forest/20 bg-white text-xs text-ink focus:outline-none focus:ring-2 focus:ring-forest"
              />
              <button
                type="button"
                onClick={addCustomCrop}
                className="px-4 h-11 bg-forest text-sand text-xs font-bold rounded-xl hover:bg-forest-light transition-colors"
              >
                Add
              </button>
            </div>

            {/* Config for selected crops (Optional sowing date and area) */}
            {currentCrops.length > 0 && (
              <div className="pt-2 space-y-3">
                <h3 className="text-xs font-bold text-forest uppercase tracking-wider">
                  Selected Crops ({currentCrops.length})
                </h3>
                {currentCrops.map((crop) => (
                  <div
                    key={crop.crop_name}
                    className="p-3.5 rounded-xl bg-white border border-forest/15 space-y-2.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-forest">🌱 {crop.crop_name}</span>
                      <button
                        type="button"
                        onClick={() => toggleCrop(crop.crop_name)}
                        className="text-xs text-red-600 hover:text-red-700 font-semibold"
                      >
                        Remove
                      </button>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[11px] font-medium text-ink-soft mb-1">
                          {t.cropAreaLabel}
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          value={crop.area_value ?? ""}
                          onChange={(e) =>
                            updateCropDetails(crop.crop_name, {
                              area_value: e.target.value === "" ? "" : parseFloat(e.target.value)
                            })
                          }
                          placeholder="e.g. 1.5"
                          className="w-full h-9 px-2.5 rounded-lg border border-forest/20 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-forest"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-ink-soft mb-1">
                          {t.sownDateLabel}
                        </label>
                        <input
                          type="date"
                          value={crop.sown_on || ""}
                          onChange={(e) =>
                            updateCropDetails(crop.crop_name, { sown_on: e.target.value })
                          }
                          className="w-full h-9 px-2.5 rounded-lg border border-forest/20 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-forest"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STEP 5: REVIEW SCREEN */}
        {step === 5 && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold font-serif text-forest">{t.reviewTitle}</h2>
              <p className="text-xs text-ink-soft mt-1">{t.reviewSub}</p>
            </div>

            {/* Profile Completion Card */}
            <div className="p-4 rounded-2xl bg-forest text-sand space-y-2 shadow-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold opacity-90">{t.profileCompletion}</span>
                <span className="text-xl font-bold font-serif">{completion.percentage}%</span>
              </div>
              <div className="w-full bg-white/20 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-sand h-full transition-all duration-300"
                  style={{ width: `${completion.percentage}%` }}
                />
              </div>
              <p className="text-[11px] opacity-80">
                {completion.percentage === 100
                  ? t.requiredFieldsDone
                  : `Missing required: ${completion.missing.join(", ")}`}
              </p>
            </div>

            {/* Review Sections */}
            {/* 1. Basics */}
            <div className="p-3.5 rounded-xl bg-white border border-forest/15 space-y-1 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-forest">1. Basics</span>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="text-xs font-semibold text-forest underline hover:text-forest-light"
                >
                  {t.editStep}
                </button>
              </div>
              <p className="text-sm font-semibold text-ink">{fullName || "—"}</p>
              <p className="text-xs text-ink-soft">
                Language: {SUPPORTED_LANGUAGES.find((l) => l.code === prefLang)?.label || prefLang}
              </p>
            </div>

            {/* 2. Location */}
            <div className="p-3.5 rounded-xl bg-white border border-forest/15 space-y-1 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-forest">2. Location</span>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="text-xs font-semibold text-forest underline hover:text-forest-light"
                >
                  {t.editStep}
                </button>
              </div>
              <p className="text-sm font-semibold text-ink">
                {village ? `${village}, ` : ""}
                {taluk ? `${taluk}, ` : ""}
                {district}, {stateName}
              </p>
            </div>

            {/* 3. Farm & Irrigation */}
            <div className="p-3.5 rounded-xl bg-white border border-forest/15 space-y-2 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-forest">3. Farm Details</span>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="text-xs font-semibold text-forest underline hover:text-forest-light"
                >
                  {t.editStep}
                </button>
              </div>
              {farms.map((f, i) => (
                <div key={i} className="text-xs text-ink-soft border-t border-forest/10 pt-1.5">
                  <p className="font-bold text-forest text-xs">{f.name}</p>
                  <p>
                    Area: {f.area_value || "—"} {f.area_unit} ({f.ownership})
                  </p>
                  <p>
                    Irrigation:{" "}
                    {f.irrigation?.length > 0 ? f.irrigation.join(", ") : "Not specified"}
                  </p>
                </div>
              ))}
            </div>

            {/* 4. Crops */}
            <div className="p-3.5 rounded-xl bg-white border border-forest/15 space-y-2 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-forest">4. Standing Crops</span>
                <button
                  type="button"
                  onClick={() => setStep(4)}
                  className="text-xs font-semibold text-forest underline hover:text-forest-light"
                >
                  {t.editStep}
                </button>
              </div>
              {Object.entries(cropsByFarm).some(([_, crops]) => crops.length > 0) ? (
                <div className="flex flex-wrap gap-1.5">
                  {Object.values(cropsByFarm)
                    .flat()
                    .map((c, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 bg-forest/10 text-forest font-semibold rounded-full text-xs"
                      >
                        🌱 {c.crop_name}
                        {c.area_value ? ` (${c.area_value} ac)` : ""}
                      </span>
                    ))}
                </div>
              ) : (
                <p className="text-xs text-ink-soft italic">No crops added yet (can add later)</p>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Sticky Bottom Actions */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-forest/10 p-4 z-20">
        <div className="max-w-md mx-auto flex items-center gap-3">
          {step > 1 && (
            <button
              type="button"
              onClick={handleBack}
              disabled={submitting}
              className="w-1/3 h-12 rounded-xl border border-forest/20 text-forest font-bold text-xs hover:bg-forest/5 active:scale-95 transition-all"
            >
              {t.backBtn}
            </button>
          )}

          {step < 5 ? (
            <button
              type="button"
              onClick={handleNext}
              className="flex-1 h-12 rounded-xl bg-forest hover:bg-forest-light active:scale-[0.99] text-sand font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2"
            >
              <span>{t.nextBtn}</span>
              <span>→</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleFinalSubmit}
              disabled={submitting || completion.percentage < 50}
              className="flex-1 h-12 rounded-xl bg-forest hover:bg-forest-light active:scale-[0.99] text-sand font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <span>{submitting ? t.submitting : t.submitProfile}</span>
              <span>✓</span>
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
