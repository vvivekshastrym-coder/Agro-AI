import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, signOut } from "../lib/useAuth";
import { useApp } from "../lib/AppContext";
import { getDictionary } from "../lib/i18n";
import {
  FarmerProfile as ProfileType,
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

export default function FarmerProfile() {
  const { user, isPhoneVerified } = useAuth();
  const navigate = useNavigate();
  const { language, setLanguage, setLocation, refreshProfile } = useApp();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [fullName, setFullName] = useState("");
  const [prefLang, setPrefLang] = useState(language || "kn");
  const [stateName, setStateName] = useState("Karnataka");
  const [district, setDistrict] = useState("Mandya");
  const [taluk, setTaluk] = useState("");
  const [village, setVillage] = useState("");
  const [onboardingStatus, setOnboardingStatus] = useState<"draft" | "complete">("draft");
  const [notifications, setNotifications] = useState({
    sms: true,
    whatsapp: true,
    weather_alerts: true
  });

  const [farms, setFarms] = useState<Farm[]>([]);
  const [cropsByFarm, setCropsByFarm] = useState<Record<number, FarmCrop[]>>({});
  const [selectedFarmIdx, setSelectedFarmIdx] = useState(0);
  const [newCropName, setNewCropName] = useState("");

  const t = getDictionary(prefLang);

  useEffect(() => {
    async function loadData() {
      if (!user) return;
      setLoading(true);
      try {
        const [profile, loadedFarms] = await Promise.all([
          getFarmerProfile(user.id),
          getFarmerFarms(user.id)
        ]);

        if (profile) {
          setFullName(profile.full_name || "");
          if (profile.language) {
            setPrefLang(profile.language);
            setLanguage(profile.language);
          }
          setStateName(profile.state || "Karnataka");
          setDistrict(profile.district || "Mandya");
          setTaluk(profile.taluk || "");
          setVillage(profile.village || "");
          setOnboardingStatus(profile.onboarding_status || "draft");
          if (profile.notification_preferences) {
            setNotifications(profile.notification_preferences);
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
        } else {
          // Default empty farm
          setFarms([
            {
              name: "Main Farm (ಮುಖ್ಯ ಹೊಲ)",
              farming_types: ["crop"],
              area_value: 3,
              area_unit: "acres",
              ownership: "own",
              irrigation: ["borewell"]
            }
          ]);
          setCropsByFarm({ 0: [] });
        }
      } catch (err: any) {
        console.error("Error loading farmer profile:", err);
        setErrorMessage(err.message || "Failed to load profile.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [user, setLanguage]);

  const handleSaveChanges = async () => {
    if (!user) return;
    setSaving(true);
    setSaveSuccess(false);
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
        notification_preferences: notifications,
        onboarding_status: onboardingStatus
      });

      const savedFarms = await saveFarmsAndCrops(user.id, farms, cropsByFarm);
      if (savedFarms.length > 0) {
        setFarms(savedFarms);
      }

      setLanguage(prefLang);
      if (village && district) {
        setLocation(`${village.trim()}, ${district.trim()}`);
      }
      await refreshProfile();

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      console.error("Save profile error:", err);
      setErrorMessage(err.message || "Failed to save profile changes.");
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    navigate("/login", { replace: true });
  };

  const updateFarm = (index: number, updates: Partial<Farm>) => {
    setFarms((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], ...updates };
      return copy;
    });
  };

  const addFarm = () => {
    const nextIdx = farms.length;
    setFarms((prev) => [
      ...prev,
      {
        name: `Farm ${nextIdx + 1}`,
        farming_types: ["crop"],
        area_value: "",
        area_unit: "acres",
        ownership: "own",
        irrigation: ["borewell"]
      }
    ]);
    setCropsByFarm((prev) => ({ ...prev, [nextIdx]: [] }));
    setSelectedFarmIdx(nextIdx);
  };

  const toggleCrop = (cropName: string) => {
    setCropsByFarm((prev) => {
      const list = prev[selectedFarmIdx] || [];
      const exists = list.some((c) => c.crop_name.toLowerCase() === cropName.toLowerCase());
      let updated: FarmCrop[];
      if (exists) {
        updated = list.filter((c) => c.crop_name.toLowerCase() !== cropName.toLowerCase());
      } else {
        updated = [...list, { crop_name: cropName, area_value: "", sown_on: "" }];
      }
      return { ...prev, [selectedFarmIdx]: updated };
    });
  };

  const addCustomCrop = () => {
    if (!newCropName.trim()) return;
    toggleCrop(newCropName.trim());
    setNewCropName("");
  };

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

  const availableTaluks = KARNATAKA_LOCATION_DATA[district] || [];
  const currentCrops = cropsByFarm[selectedFarmIdx] || [];
  const phone = user?.phone || "";
  const phoneVerified = Boolean(isPhoneVerified);

  if (loading) {
    return (
      <div className="min-h-screen bg-cream flex flex-col items-center justify-center p-6 text-center">
        <div className="w-10 h-10 border-4 border-forest border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-forest font-semibold">Loading profile…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream flex flex-col pb-24">
      {/* Header */}
      <header className="sticky top-0 bg-white/95 backdrop-blur border-b border-forest/10 px-4 py-3 z-20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="w-8 h-8 rounded-full border border-forest/20 flex items-center justify-center text-forest hover:bg-forest/5 active:scale-95"
            aria-label="Back"
          >
            ←
          </button>
          <div>
            <h1 className="text-base font-bold font-serif text-forest">{t.profileTitle}</h1>
            <p className="text-[11px] text-ink-soft">
              {village ? `${village}, ${district}` : "Manage farm & account"}
            </p>
          </div>
        </div>

        <button
          onClick={handleSaveChanges}
          disabled={saving}
          className="px-4 py-1.5 rounded-full bg-forest text-sand text-xs font-bold shadow-sm hover:bg-forest-light active:scale-95 transition-all disabled:opacity-50"
        >
          {saving ? t.saving : t.saveChanges}
        </button>
      </header>

      <main className="max-w-md w-full mx-auto p-4 space-y-5">
        {saveSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-medium flex items-center gap-2">
            <span>✓</span>
            <span>Profile and farm details successfully saved to Supabase!</span>
          </div>
        )}

        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs font-medium">
            {errorMessage}
          </div>
        )}

        {/* Farmer Header Summary Card */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm flex items-center gap-3.5">
          <div className="w-14 h-14 rounded-2xl bg-forest/10 border border-forest/20 flex items-center justify-center text-2xl">
            👨‍🌾
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-forest truncate">
              {fullName || "Farmer Name"}
            </h2>
            <p className="text-xs text-ink-soft truncate">
              {village ? `${village}, ` : ""}{district}, {stateName}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  onboardingStatus === "complete"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}
              >
                {onboardingStatus === "complete" ? t.onboardingCompleteBadge : t.onboardingDraftBadge}
              </span>
              <span className="text-[10px] text-ink-soft">
                {t.profileCompletion} {completion.percentage}%
              </span>
            </div>
          </div>
        </div>

        {/* Read-Only Verified Phone Number Card */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-ink uppercase tracking-wider">
              {t.phoneLabel}
            </label>
            {phoneVerified ? (
              <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                {t.verifiedPhoneBadge}
              </span>
            ) : (
              <span className="text-[11px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                Phone Unverified
              </span>
            )}
          </div>
          <input
            type="text"
            readOnly
            value={phone || (user?.email ? user.email : "No phone associated")}
            className="w-full h-11 px-3.5 rounded-xl border border-forest/15 bg-forest/5 text-forest font-mono text-sm font-semibold cursor-not-allowed"
          />
          <p className="text-[10px] text-ink-soft leading-normal">{t.phoneNoticeKYC}</p>
        </div>

        {/* Basic Details */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-3.5">
          <h3 className="text-xs font-bold text-forest uppercase tracking-wider">Basic Details</h3>
          <div>
            <label className="block text-xs font-bold text-ink mb-1">{t.fullNameLabel}</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Ramesh Gowda"
              className="w-full h-11 px-3.5 rounded-xl border border-forest/20 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-forest font-medium"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-ink mb-1.5">{t.prefLangLabel}</label>
            <div className="grid grid-cols-2 gap-2">
              {SUPPORTED_LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setPrefLang(lang.code)}
                  className={`p-2.5 rounded-xl border text-xs font-bold transition-all text-left flex items-center justify-between ${
                    prefLang === lang.code
                      ? "border-forest bg-forest text-sand"
                      : "border-forest/15 bg-white text-ink hover:bg-forest/5"
                  }`}
                >
                  <span>{lang.native}</span>
                  {prefLang === lang.code && <span>✓</span>}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Location Section */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-3.5">
          <h3 className="text-xs font-bold text-forest uppercase tracking-wider">
            {t.stepLocationTitle}
          </h3>

          <div>
            <label className="block text-xs font-bold text-ink mb-1">{t.stateLabel}</label>
            <select
              value={stateName}
              onChange={(e) => setStateName(e.target.value)}
              className="w-full h-11 px-3 rounded-xl border border-forest/20 bg-white text-xs text-ink focus:outline-none focus:ring-2 focus:ring-forest font-medium"
            >
              <option value="Karnataka">Karnataka</option>
              <option value="Andhra Pradesh">Andhra Pradesh</option>
              <option value="Tamil Nadu">Tamil Nadu</option>
              <option value="Maharashtra">Maharashtra</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-bold text-ink mb-1">{t.districtLabel}</label>
              {stateName === "Karnataka" ? (
                <select
                  value={district}
                  onChange={(e) => {
                    setDistrict(e.target.value);
                    setTaluk("");
                  }}
                  className="w-full h-11 px-2.5 rounded-xl border border-forest/20 bg-white text-xs text-ink focus:outline-none focus:ring-2 focus:ring-forest font-medium"
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
                  className="w-full h-11 px-3 rounded-xl border border-forest/20 text-xs text-ink"
                />
              )}
            </div>

            <div>
              <label className="block text-xs font-bold text-ink mb-1">{t.talukLabel}</label>
              {availableTaluks.length > 0 ? (
                <select
                  value={taluk}
                  onChange={(e) => setTaluk(e.target.value)}
                  className="w-full h-11 px-2.5 rounded-xl border border-forest/20 bg-white text-xs text-ink focus:outline-none focus:ring-2 focus:ring-forest font-medium"
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
                  className="w-full h-11 px-3 rounded-xl border border-forest/20 text-xs text-ink"
                />
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-ink mb-1">{t.villageLabel}</label>
            <input
              type="text"
              value={village}
              onChange={(e) => setVillage(e.target.value)}
              placeholder="e.g. Dudda"
              className="w-full h-11 px-3.5 rounded-xl border border-forest/20 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-forest font-medium"
            />
          </div>
        </div>

        {/* Farms & Crops Management */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-3.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-forest uppercase tracking-wider">
              Farms ({farms.length})
            </h3>
            <button
              type="button"
              onClick={addFarm}
              className="text-xs font-bold text-forest underline hover:text-forest-light"
            >
              + Add Farm
            </button>
          </div>

          {farms.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {farms.map((f, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedFarmIdx(idx)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap ${
                    selectedFarmIdx === idx
                      ? "bg-forest text-sand"
                      : "bg-forest/5 text-forest border border-forest/15"
                  }`}
                >
                  {f.name || `Farm ${idx + 1}`}
                </button>
              ))}
            </div>
          )}

          {farms[selectedFarmIdx] && (
            <div className="space-y-3 border-t border-forest/10 pt-3">
              <div>
                <label className="block text-xs font-bold text-ink mb-1">Farm Name</label>
                <input
                  type="text"
                  value={farms[selectedFarmIdx].name}
                  onChange={(e) => updateFarm(selectedFarmIdx, { name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl border border-forest/20 text-xs text-ink font-medium"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-ink mb-1">{t.landAreaLabel}</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={farms[selectedFarmIdx].area_value}
                    onChange={(e) =>
                      updateFarm(selectedFarmIdx, {
                        area_value: e.target.value === "" ? "" : parseFloat(e.target.value)
                      })
                    }
                    className="flex-1 h-10 px-3 rounded-xl border border-forest/20 text-xs text-ink font-medium"
                  />
                  <select
                    value={farms[selectedFarmIdx].area_unit}
                    onChange={(e) =>
                      updateFarm(selectedFarmIdx, { area_unit: e.target.value as any })
                    }
                    className="w-28 h-10 px-2 rounded-xl border border-forest/20 text-xs text-forest font-bold bg-forest/5"
                  >
                    <option value="acres">Acres</option>
                    <option value="guntas">Guntas</option>
                    <option value="hectares">Hectares</option>
                  </select>
                </div>
              </div>

              {/* Standing Crops on this farm */}
              <div>
                <label className="block text-xs font-bold text-ink mb-1.5">
                  Standing Crops on this Farm
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {COMMON_CROPS.map((cName) => {
                    const isSel = currentCrops.some(
                      (c) => c.crop_name.toLowerCase() === cName.toLowerCase()
                    );
                    return (
                      <button
                        key={cName}
                        type="button"
                        onClick={() => toggleCrop(cName)}
                        className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${
                          isSel
                            ? "bg-forest text-sand border-forest"
                            : "bg-white text-ink border-forest/15 hover:bg-forest/5"
                        }`}
                      >
                        {isSel ? `✓ ${cName}` : `+ ${cName}`}
                      </button>
                    );
                  })}
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newCropName}
                    onChange={(e) => setNewCropName(e.target.value)}
                    placeholder="Add custom crop..."
                    className="flex-1 h-9 px-3 rounded-lg border border-forest/20 text-xs text-ink"
                  />
                  <button
                    type="button"
                    onClick={addCustomCrop}
                    className="px-3 h-9 bg-forest text-sand text-xs font-bold rounded-lg"
                  >
                    Add
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Notification Preferences */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-3">
          <h3 className="text-xs font-bold text-forest uppercase tracking-wider">
            {t.notificationsTitle}
          </h3>

          <label className="flex items-center justify-between p-2 rounded-lg hover:bg-forest/5 cursor-pointer">
            <span className="text-xs font-medium text-ink">{t.smsAlerts}</span>
            <input
              type="checkbox"
              checked={notifications.sms}
              onChange={(e) =>
                setNotifications((n) => ({ ...n, sms: e.target.checked }))
              }
              className="w-4 h-4 text-forest rounded focus:ring-forest"
            />
          </label>

          <label className="flex items-center justify-between p-2 rounded-lg hover:bg-forest/5 cursor-pointer">
            <span className="text-xs font-medium text-ink">{t.whatsappReports}</span>
            <input
              type="checkbox"
              checked={notifications.whatsapp}
              onChange={(e) =>
                setNotifications((n) => ({ ...n, whatsapp: e.target.checked }))
              }
              className="w-4 h-4 text-forest rounded focus:ring-forest"
            />
          </label>

          <label className="flex items-center justify-between p-2 rounded-lg hover:bg-forest/5 cursor-pointer">
            <span className="text-xs font-medium text-ink">{t.weatherAlerts}</span>
            <input
              type="checkbox"
              checked={notifications.weather_alerts}
              onChange={(e) =>
                setNotifications((n) => ({ ...n, weather_alerts: e.target.checked }))
              }
              className="w-4 h-4 text-forest rounded focus:ring-forest"
            />
          </label>
        </div>

        {/* Account Details & Sign Out */}
        <div className="p-4 rounded-2xl bg-white border border-forest/15 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs text-ink-soft">
            <span>{t.accountCreated}</span>
            <span className="font-mono">
              {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "Active"}
            </span>
          </div>

          <button
            type="button"
            onClick={handleSignOut}
            className="w-full h-11 rounded-xl border border-red-200 text-red-600 font-bold text-xs hover:bg-red-50 active:scale-95 transition-all flex items-center justify-center gap-1.5"
          >
            <span>🚪</span>
            <span>{t.logoutBtn}</span>
          </button>
        </div>
      </main>
    </div>
  );
}
