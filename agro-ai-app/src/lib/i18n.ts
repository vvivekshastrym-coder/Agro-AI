// agro-ai-app/src/lib/i18n.ts
// Comprehensive internationalization for Phone OTP Auth, Onboarding & Profile

import { SUPPORTED_LANGUAGES } from "./farmerProfile";
export { SUPPORTED_LANGUAGES };

export type LanguageCode = "kn" | "en" | "hi" | "te" | "ta";

export interface Translations {
  tagline: string;
  phoneLabel: string;
  phonePlaceholder: string;
  continueBtn: string;
  termsNotice: string;
  termsLink: string;
  privacyLink: string;
  emailOption: string;
  phoneOption: string;
  emailLabel: string;
  emailPlaceholder: string;
  sendLinkBtn: string;
  checkEmailMsg: string;

  // OTP Screen
  otpTitle: string;
  otpSubtitle: string;
  otpMaskedPrefix: string;
  changeNumber: string;
  verifyBtn: string;
  verifyingBtn: string;
  resendPrefix: string;
  resendAction: string;
  errWrongOtp: string;
  errExpiredOtp: string;
  errRateLimited: string;
  errGeneric: string;

  // Onboarding
  onboardingHeader: string;
  saveAndExit: string;
  draftSaved: string;
  stepBasicsTitle: string;
  stepBasicsSub: string;
  fullNameLabel: string;
  fullNamePlaceholder: string;
  prefLangLabel: string;
  fallbackNoteTe: string;
  fallbackNoteTa: string;

  stepLocationTitle: string;
  stepLocationSub: string;
  stateLabel: string;
  districtLabel: string;
  selectDistrict: string;
  talukLabel: string;
  selectTaluk: string;
  villageLabel: string;
  villagePlaceholder: string;
  gpsDetectBtn: string;
  gpsDetecting: string;
  gpsPrivacyNote: string;

  stepFarmTitle: string;
  stepFarmSub: string;
  farmingTypeLabel: string;
  landAreaLabel: string;
  areaUnitLabel: string;
  ownershipLabel: string;
  irrigationLabel: string;
  addAnotherFarm: string;
  farmNumberTitle: string;

  stepCropsTitle: string;
  stepCropsSub: string;
  searchCropsPlaceholder: string;
  sownDateLabel: string;
  cropAreaLabel: string;
  skipAddLater: string;
  customCropPlaceholder: string;

  reviewTitle: string;
  reviewSub: string;
  profileCompletion: string;
  requiredFieldsDone: string;
  editStep: string;
  submitProfile: string;
  submitting: string;
  backBtn: string;
  nextBtn: string;

  // Profile Page
  profileTitle: string;
  verifiedPhoneBadge: string;
  phoneNoticeKYC: string;
  accountCreated: string;
  onboardingCompleteBadge: string;
  onboardingDraftBadge: string;
  saveChanges: string;
  saving: string;
  logoutBtn: string;
  notificationsTitle: string;
  smsAlerts: string;
  whatsappReports: string;
  weatherAlerts: string;
}

export const I18N: Record<LanguageCode, Translations> = {
  kn: {
    tagline: "ನಿಮ್ಮ ಹೊಲದ ಪ್ರತಿಯೊಂದು ನಿರ್ಧಾರಕ್ಕೂ — ನಿಮ್ಮ ಜೊತೆ Agro AI.",
    phoneLabel: "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ",
    phonePlaceholder: "98765 43210",
    continueBtn: "ಮುಂದುವರಿಯಿರಿ",
    termsNotice: "ಮುಂದುವರಿಯುವ ಮೂಲಕ, ನೀವು Agro AI ನಿಯಮಗಳು ಮತ್ತು ಗೌಪ್ಯತಾ ನೀತಿಯನ್ನು ಒಪ್ಪುತ್ತೀರಿ.",
    termsLink: "ಸೇವಾ ನಿಯಮಗಳು",
    privacyLink: "ಗೌಪ್ಯತಾ ನೀತಿ",
    emailOption: "ಇಮೇಲ್ ಮೂಲಕ ಲಾಗಿನ್ ಮಾಡಿ",
    phoneOption: "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಮೂಲಕ ಲಾಗಿನ್ ಮಾಡಿ",
    emailLabel: "ಇಮೇಲ್ ವಿಳಾಸ",
    emailPlaceholder: "you@example.com",
    sendLinkBtn: "ಲಾಗಿನ್ ಲಿಂಕ್ ಕಳುಹಿಸಿ",
    checkEmailMsg: "ನಿಮ್ಮ ಇಮೇಲ್ ಪರೀಕ್ಷಿಸಿ. ಲಾಗಿನ್ ಲಿಂಕ್ ಕಳುಹಿಸಲಾಗಿದೆ.",

    otpTitle: "OTP ಪರಿಶೀಲಿಸಿ",
    otpSubtitle: "ನಿಮ್ಮ ಮೊಬೈಲ್ ಸಂಖ್ಯೆಗೆ 6-ಅಂಕಿಯ OTP ಕೋಡ್ ಕಳುಹಿಸಲಾಗಿದೆ.",
    otpMaskedPrefix: "ಕಳುಹಿಸಲಾದ ಸಂಖ್ಯೆ:",
    changeNumber: "ಸಂಖ್ಯೆ ಬದಲಾಯಿಸಿ",
    verifyBtn: "ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಪ್ರವೇಶಿಸಿ",
    verifyingBtn: "ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…",
    resendPrefix: "ಮರುಕಳುಹಿಸಲು ಕಾಯಿರಿ:",
    resendAction: "ಮತ್ತೊಮ್ಮೆ OTP ಕಳುಹಿಸಿ",
    errWrongOtp: "ನಮೂದಿಸಿದ OTP ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಸರಿಯಾದ ಕೋಡ್ ನಮೂದಿಸಿ.",
    errExpiredOtp: "ಈ OTP ಅವಧಿ ಮೀರಿದೆ. ದಯವಿಟ್ಟು ಹೊಸ OTP ಪಡೆದುಕೊಳ್ಳಿ.",
    errRateLimited: "ತುಂಬಾ ಪ್ರಯತ್ನಗಳು ನಡೆದಿವೆ. ದಯವಿಟ್ಟು ಕೆಲವು ನಿಮಿಷಗಳ ನಂತರ ಪ್ರಯತ್ನಿಸಿ.",
    errGeneric: "ದೃಢೀಕರಣ ವಿಫಲವಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸಿ.",

    onboardingHeader: "ರೈತರ ನೋಂದಣಿ (Farmer Setup)",
    saveAndExit: "ಉಳಿಸಿ ಹೊರಡಿ",
    draftSaved: "ಡ್ರಾಫ್ಟ್ ಸುರಕ್ಷಿತವಾಗಿ ಉಳಿದಿದೆ",
    stepBasicsTitle: "1. ಮೂಲ ವಿವರಗಳು",
    stepBasicsSub: "ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ಅನುಕೂಲಕರ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
    fullNameLabel: "ಪೂರ್ಣ ಹೆಸರು *",
    fullNamePlaceholder: "ಉದಾ: ರಮೇಶ್ ಗೌಡ",
    prefLangLabel: "ಆದ್ಯತೆಯ ಭಾಷೆ *",
    fallbackNoteTe: "ಗಮನಿಸಿ: ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ವಿವರಗಳು ಕಾಣಿಸುತ್ತವೆ. ತೆಲುಗು ಸೌಲಭ್ಯ ಶೀಘ್ರದಲ್ಲೇ ಬರಲಿದೆ.",
    fallbackNoteTa: "ಗಮನಿಸಿ: ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ವಿವರಗಳು ಕಾಣಿಸುತ್ತವೆ. ತಮಿಳು ಸೌಲಭ್ಯ ಶೀಘ್ರದಲ್ಲೇ ಬರಲಿದೆ.",

    stepLocationTitle: "2. ಜಮೀನಿನ ಸ್ಥಳ",
    stepLocationSub: "ನಿಮ್ಮ ಗ್ರಾಮದ ಹವಾಮಾನ ಮತ್ತು ಮಂಡಿ ದರಗಳನ್ನು ಒದಗಿಸಲು ಇದು ಅಗತ್ಯ.",
    stateLabel: "ರಾಜ್ಯ *",
    districtLabel: "ಜಿಲ್ಲೆ *",
    selectDistrict: "ಜಿಲ್ಲೆ ಆಯ್ಕೆಮಾಡಿ",
    talukLabel: "ತಾಲೂಕು",
    selectTaluk: "ತಾಲೂಕು ಆಯ್ಕೆಮಾಡಿ",
    villageLabel: "ಗ್ರಾಮ / ಊರು *",
    villagePlaceholder: "ಉದಾ: ದುದ್ದ, ಮಂಡ್ಯ",
    gpsDetectBtn: "📍 ನನ್ನ ಸ್ಥಳ ಗುರುತಿಸಿ (ಐಚ್ಛಿಕ)",
    gpsDetecting: "ಸ್ಥಳ ಪತ್ತೆಮಾಡಲಾಗುತ್ತಿದೆ...",
    gpsPrivacyNote: "ಗೌಪ್ಯತೆ ಭರವಸೆ: ನಿಮ್ಮ ನಿಖರವಾದ ಜಮೀನಿನ ಸ್ಥಳವನ್ನು ಯಾರೊಂದಿಗೂ ಹಂಚಿಕೊಳ್ಳುವುದಿಲ್ಲ.",

    stepFarmTitle: "3. ಕೃಷಿ ಜಮೀನು",
    stepFarmSub: "ನಿಮ್ಮ ಭೂಮಿ ವಿಸ್ತೀರ್ಣ ಮತ್ತು ನೀರಿನ ಸೌಲಭ್ಯದ ವಿವರಗಳು.",
    farmingTypeLabel: "ಕೃಷಿ ವಿಧಾನ (ಬಹು ಆಯ್ಕೆ)",
    landAreaLabel: "ಜಮೀನಿನ ವಿಸ್ತೀರ್ಣ *",
    areaUnitLabel: "ಪ್ರಮಾಣ",
    ownershipLabel: "ಮಾಲೀಕತ್ವ",
    irrigationLabel: "ನೀರಾವರಿ ಸೌಲಭ್ಯ",
    addAnotherFarm: "+ ಮತ್ತೊಂದು ಜಮೀನು ಸೇರಿಸಿ",
    farmNumberTitle: "ಜಮೀನು",

    stepCropsTitle: "4. ಬೆಳೆಯುತ್ತಿರುವ ಬೆಳೆಗಳು",
    stepCropsSub: "ಸರಿಯಾದ ರೋಗ ತಪಾಸಣೆ ಮತ್ತು ಮಾರುಕಟ್ಟೆ ಸಲಹೆಗಾಗಿ ಬೆಳೆಗಳನ್ನು ಆರಿಸಿ.",
    searchCropsPlaceholder: "ಬೆಳೆ ಹುಡುಕಿ...",
    sownDateLabel: "ಬಿತ್ತನೆ ದಿನಾಂಕ (ಐಚ್ಛಿಕ)",
    cropAreaLabel: "ವಿಸ್ತೀರ್ಣ (ಐಚ್ಛಿಕ)",
    skipAddLater: "ಈಗ ಬಿಟ್ಟುಬಿಡಿ, ನಂತರ ಸೇರಿಸಿ →",
    customCropPlaceholder: "ಇತರ ಬೆಳೆಯ ಹೆಸರು ನಮೂದಿಸಿ",

    reviewTitle: "ವಿವರಗಳ ಪರಿಶೀಲನೆ",
    reviewSub: "ನಿಮ್ಮ ವಿವರಗಳು ಸರಿಯಾಗಿವೆಯೇ ಎಂದು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.",
    profileCompletion: "ಪ್ರೊಫೈಲ್ ಪೂರ್ಣತೆ:",
    requiredFieldsDone: "ಅಗತ್ಯವಿರುವ ಎಲ್ಲಾ ವಿವರಗಳನ್ನು ಭರ್ತಿ ಮಾಡಲಾಗಿದೆ.",
    editStep: "ಬದಲಿಸಿ",
    submitProfile: "ನೋಂದಣಿ ಪೂರ್ಣಗೊಳಿಸಿ",
    submitting: "ಉಳಿಸಲಾಗುತ್ತಿದೆ…",
    backBtn: "ಹಿಂದಕ್ಕೆ",
    nextBtn: "ಮುಂದೆ",

    profileTitle: "ರೈತರ ಪ್ರೊಫೈಲ್",
    verifiedPhoneBadge: "✓ Supabase ಮೂಲಕ ಪರಿಶೀಲಿತ ಮೊಬೈಲ್",
    phoneNoticeKYC: "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಪರಿಶೀಲನೆಗೊಂಡಿದೆ (ಸರ್ಕಾರಿ ರೈತ ಗುರುತು ಚೀಟಿ ಅಲ್ಲ).",
    accountCreated: "ಖಾತೆ ರಚನೆ ದಿನಾಂಕ:",
    onboardingCompleteBadge: "ಸಂಪೂರ್ಣ ಪ್ರೊಫೈಲ್",
    onboardingDraftBadge: "ಅಪೂರ್ಣ (ಡ್ರಾಫ್ಟ್)",
    saveChanges: "ಬದಲಾವಣೆಗಳನ್ನು ಉಳಿಸಿ",
    saving: "ಉಳಿಸಲಾಗುತ್ತಿದೆ...",
    logoutBtn: "ಸೈನ್ ಔಟ್ (Logout)",
    notificationsTitle: "ಅಧಿಸೂಚನೆ ಆದ್ಯತೆಗಳು",
    smsAlerts: "SMS ಮುನ್ಸೂಚನೆಗಳು",
    whatsappReports: "ದೈನಂದಿನ ವಾಟ್ಸಾಪ್ ಕೃಷಿ ವರದಿ",
    weatherAlerts: "ತುರ್ತು ಹವಾಮಾನ ಎಚ್ಚರಿಕೆಗಳು"
  },

  en: {
    tagline: "ನಿಮ್ಮ ಹೊಲದ ಪ್ರತಿಯೊಂದು ನಿರ್ಧಾರಕ್ಕೂ — ನಿಮ್ಮ ಜೊತೆ Agro AI.",
    phoneLabel: "Mobile number",
    phonePlaceholder: "98765 43210",
    continueBtn: "Continue",
    termsNotice: "By continuing, you agree to Agro AI's Terms of Service and Privacy Policy.",
    termsLink: "Terms of Service",
    privacyLink: "Privacy Policy",
    emailOption: "Sign in with email instead",
    phoneOption: "Sign in with phone OTP",
    emailLabel: "Email address",
    emailPlaceholder: "you@example.com",
    sendLinkBtn: "Send sign-in link",
    checkEmailMsg: "Check your email for a sign-in link.",

    otpTitle: "Verify OTP",
    otpSubtitle: "Enter the 6-digit OTP code sent to your mobile number.",
    otpMaskedPrefix: "Code sent to:",
    changeNumber: "Change number",
    verifyBtn: "Verify & Continue",
    verifyingBtn: "Verifying…",
    resendPrefix: "Resend in:",
    resendAction: "Resend OTP",
    errWrongOtp: "Incorrect OTP. Please check the code and try again.",
    errExpiredOtp: "This OTP has expired. Please request a new one.",
    errRateLimited: "Too many attempts. Please wait a few minutes before requesting another OTP.",
    errGeneric: "Verification failed. Please try again.",

    onboardingHeader: "Farmer Setup",
    saveAndExit: "Save & Exit",
    draftSaved: "Draft saved safely",
    stepBasicsTitle: "1. Basics",
    stepBasicsSub: "Tell us your name and how you'd like Agro AI to talk to you.",
    fullNameLabel: "Full Name *",
    fullNamePlaceholder: "e.g. Ramesh Gowda",
    prefLangLabel: "Preferred Language *",
    fallbackNoteTe: "Note: Screen text is displayed in English. Telugu localization is coming soon.",
    fallbackNoteTa: "Note: Screen text is displayed in English. Tamil localization is coming soon.",

    stepLocationTitle: "2. Farm Location",
    stepLocationSub: "Enables hyperlocal weather forecasts and local Mandi APMC prices.",
    stateLabel: "State *",
    districtLabel: "District *",
    selectDistrict: "Select District",
    talukLabel: "Taluk",
    selectTaluk: "Select Taluk",
    villageLabel: "Village / Town *",
    villagePlaceholder: "e.g. Dudda, Mandya",
    gpsDetectBtn: "📍 Detect current location (optional)",
    gpsDetecting: "Detecting location...",
    gpsPrivacyNote: "Privacy Guarantee: Exact farm GPS coordinates are never published or shared publicly.",

    stepFarmTitle: "3. Farm Details",
    stepFarmSub: "Details about your land parcel, irrigation and farming style.",
    farmingTypeLabel: "Farming Type (select all that apply)",
    landAreaLabel: "Land Area *",
    areaUnitLabel: "Unit",
    ownershipLabel: "Ownership",
    irrigationLabel: "Irrigation Source",
    addAnotherFarm: "+ Add another farm",
    farmNumberTitle: "Farm",

    stepCropsTitle: "4. Standing Crops",
    stepCropsSub: "Used to customize pest risk warnings, fertilizer timing and market trends.",
    searchCropsPlaceholder: "Search crops (e.g. Tomato, Ragi)...",
    sownDateLabel: "Sowing Date (optional)",
    cropAreaLabel: "Area under crop (optional)",
    skipAddLater: "Skip, add crops later →",
    customCropPlaceholder: "Enter custom crop name",

    reviewTitle: "Review & Confirm",
    reviewSub: "Review your farm profile before finalizing.",
    profileCompletion: "Profile Completion:",
    requiredFieldsDone: "All core required fields are complete.",
    editStep: "Edit",
    submitProfile: "Complete Farmer Setup",
    submitting: "Submitting…",
    backBtn: "Back",
    nextBtn: "Continue",

    profileTitle: "Farmer Profile",
    verifiedPhoneBadge: "✓ Phone Verified via Supabase Auth",
    phoneNoticeKYC: "Phone number is verified. (Does not represent government farmer KYC verification).",
    accountCreated: "Member since:",
    onboardingCompleteBadge: "Complete Profile",
    onboardingDraftBadge: "Draft (Incomplete)",
    saveChanges: "Save Changes",
    saving: "Saving...",
    logoutBtn: "Sign Out",
    notificationsTitle: "Notification Preferences",
    smsAlerts: "SMS alerts for price spikes",
    whatsappReports: "Daily 6:30 AM WhatsApp Farm Brief",
    weatherAlerts: "Severe weather and spray window warnings"
  },

  hi: {
    tagline: "ನಿಮ್ಮ ಹೊಲದ ಪ್ರತಿಯೊಂದು ನಿರ್ಧಾರಕ್ಕೂ — ನಿಮ್ಮ ಜೊತೆ Agro AI.",
    phoneLabel: "मोबाइल नंबर",
    phonePlaceholder: "98765 43210",
    continueBtn: "जारी रखें",
    termsNotice: "जारी रखकर, आप एग्रो AI की सेवा की शर्तों और गोपनीयता नीति से सहमत होते हैं।",
    termsLink: "सेवा की शर्तें",
    privacyLink: "गोपनीयता नीति",
    emailOption: "ईमेल से साइन इन करें",
    phoneOption: "मोबाइल OTP से साइन इन करें",
    emailLabel: "ईमेल पता",
    emailPlaceholder: "you@example.com",
    sendLinkBtn: "साइन-इन लिंक भेजें",
    checkEmailMsg: "साइन-इन लिंक के लिए अपना ईमेल चेक करें।",

    otpTitle: "OTP सत्यापित करें",
    otpSubtitle: "आपके मोबाइल नंबर पर भेजा गया 6-अंकों का OTP कोड दर्ज करें।",
    otpMaskedPrefix: "कोड भेजा गया:",
    changeNumber: "नंबर बदलें",
    verifyBtn: "सत्यापित करें और आगे बढ़ें",
    verifyingBtn: "सत्यापित हो रहा है…",
    resendPrefix: "पुनः भेजने का समय:",
    resendAction: "OTP फिर से भेजें",
    errWrongOtp: "गलत OTP। कृपया कोड जांचें और पुनः प्रयास करें।",
    errExpiredOtp: "यह OTP समाप्त हो चुका है। कृपया नया OTP मांगें।",
    errRateLimited: "बहुत अधिक प्रयास। कृपया कुछ मिनट बाद पुनः प्रयास करें।",
    errGeneric: "सत्यापन विफल। कृपया पुनः प्रयास करें।",

    onboardingHeader: "किसान प्रोफाइल सेटअप",
    saveAndExit: "सहेजें और बाहर निकलें",
    draftSaved: "ड्राफ्ट सुरक्षित रूप से सहेजा गया",
    stepBasicsTitle: "1. बुनियादी जानकारी",
    stepBasicsSub: "अपना नाम और पसंदीदा भाषा चुनें।",
    fullNameLabel: "पूरा नाम *",
    fullNamePlaceholder: "उदा: रमेश कुमार",
    prefLangLabel: "पसंदीदा भाषा *",
    fallbackNoteTe: "नोट: टेक्स्ट अंग्रेजी में दिखाया गया है। तेलुगु सुविधा जल्द आ रही है।",
    fallbackNoteTa: "नोट: टेक्स्ट अंग्रेजी में दिखाया गया है। तमिल सुविधा जल्द आ रही है।",

    stepLocationTitle: "2. खेत का स्थान",
    stepLocationSub: "सटीक स्थानीय मौसम और नजदीकी मंडी भाव के लिए आवश्यक।",
    stateLabel: "राज्य *",
    districtLabel: "जिला *",
    selectDistrict: "जिला चुनें",
    talukLabel: "तहसील / ब्लॉक",
    selectTaluk: "तहसील चुनें",
    villageLabel: "गांव / कस्बा *",
    villagePlaceholder: "उदा: मांड्या",
    gpsDetectBtn: "📍 वर्तमान स्थान का पता लगाएं (वैकल्पिक)",
    gpsDetecting: "स्थान ढूंढा जा रहा है...",
    gpsPrivacyNote: "गोपनीयता की गारंटी: आपके खेत का सटीक स्थान कभी भी सार्वजनिक रूप से साझा नहीं किया जाता है।",

    stepFarmTitle: "3. खेत का विवरण",
    stepFarmSub: "जमीन का आकार, सिंचाई और खेती के प्रकार की जानकारी।",
    farmingTypeLabel: "खेती का प्रकार (सभी लागू विकल्प चुनें)",
    landAreaLabel: "जमीन का क्षेत्रफल *",
    areaUnitLabel: "इकाई",
    ownershipLabel: "स्वामित्व",
    irrigationLabel: "सिंचाई का साधन",
    addAnotherFarm: "+ दूसरा खेत जोड़ें",
    farmNumberTitle: "खेत",

    stepCropsTitle: "4. फसलें",
    stepCropsSub: "कीट रोग चेतावनी और मंडी सलाह के लिए फसलें चुनें।",
    searchCropsPlaceholder: "फसल खोजें (उदा: टमाटर, धान)...",
    sownDateLabel: "बुवाई की तारीख (वैकल्पिक)",
    cropAreaLabel: "फसल का रकबा (वैकल्पिक)",
    skipAddLater: "छोड़ें, बाद में फसलें जोड़ें →",
    customCropPlaceholder: "अन्य फसल का नाम दर्ज करें",

    reviewTitle: "समीक्षा और पुष्टि",
    reviewSub: "अंतिम रूप देने से पहले अपने विवरण की जांच करें।",
    profileCompletion: "प्रोफ़ाइल पूर्णता:",
    requiredFieldsDone: "सभी आवश्यक विवरण पूरे हैं।",
    editStep: "संशोधित करें",
    submitProfile: "सेटअप पूरा करें",
    submitting: "सहेज रहे हैं…",
    backBtn: "पीछे",
    nextBtn: "आगे बढ़ें",

    profileTitle: "किसान प्रोफ़ाइल",
    verifiedPhoneBadge: "✓ Supabase द्वारा सत्यापित मोबाइल",
    phoneNoticeKYC: "मोबाइल नंबर सत्यापित है (सरकारी किसान सत्यापन नहीं)।",
    accountCreated: "खाता निर्माण तिथि:",
    onboardingCompleteBadge: "पूर्ण प्रोफ़ाइल",
    onboardingDraftBadge: "अपूर्ण (ड्राफ्ट)",
    saveChanges: "बदलाव सहेजें",
    saving: "सहेजा जा रहा है...",
    logoutBtn: "लॉगआउट (Sign Out)",
    notificationsTitle: "अधिसूचना प्राथमिकताएं",
    smsAlerts: "SMS अलर्ट",
    whatsappReports: "दैनिक सुबह 6:30 बजे व्हाट्सएप रिपोर्ट",
    weatherAlerts: "मौसम और छिड़काव चेतावनी"
  },

  te: {
    // Falls back cleanly to English with visible notice
    get tagline() { return I18N.en.tagline; },
    get phoneLabel() { return I18N.en.phoneLabel; },
    get phonePlaceholder() { return I18N.en.phonePlaceholder; },
    get continueBtn() { return I18N.en.continueBtn; },
    get termsNotice() { return I18N.en.termsNotice; },
    get termsLink() { return I18N.en.termsLink; },
    get privacyLink() { return I18N.en.privacyLink; },
    get emailOption() { return I18N.en.emailOption; },
    get phoneOption() { return I18N.en.phoneOption; },
    get emailLabel() { return I18N.en.emailLabel; },
    get emailPlaceholder() { return I18N.en.emailPlaceholder; },
    get sendLinkBtn() { return I18N.en.sendLinkBtn; },
    get checkEmailMsg() { return I18N.en.checkEmailMsg; },

    get otpTitle() { return I18N.en.otpTitle; },
    get otpSubtitle() { return I18N.en.otpSubtitle; },
    get otpMaskedPrefix() { return I18N.en.otpMaskedPrefix; },
    get changeNumber() { return I18N.en.changeNumber; },
    get verifyBtn() { return I18N.en.verifyBtn; },
    get verifyingBtn() { return I18N.en.verifyingBtn; },
    get resendPrefix() { return I18N.en.resendPrefix; },
    get resendAction() { return I18N.en.resendAction; },
    get errWrongOtp() { return I18N.en.errWrongOtp; },
    get errExpiredOtp() { return I18N.en.errExpiredOtp; },
    get errRateLimited() { return I18N.en.errRateLimited; },
    get errGeneric() { return I18N.en.errGeneric; },

    get onboardingHeader() { return I18N.en.onboardingHeader; },
    get saveAndExit() { return I18N.en.saveAndExit; },
    get draftSaved() { return I18N.en.draftSaved; },
    get stepBasicsTitle() { return I18N.en.stepBasicsTitle; },
    get stepBasicsSub() { return I18N.en.stepBasicsSub; },
    get fullNameLabel() { return I18N.en.fullNameLabel; },
    get fullNamePlaceholder() { return I18N.en.fullNamePlaceholder; },
    get prefLangLabel() { return I18N.en.prefLangLabel; },
    fallbackNoteTe: "Note: Screen text is displayed in English. Telugu localization is in beta.",
    get fallbackNoteTa() { return I18N.en.fallbackNoteTa; },

    get stepLocationTitle() { return I18N.en.stepLocationTitle; },
    get stepLocationSub() { return I18N.en.stepLocationSub; },
    get stateLabel() { return I18N.en.stateLabel; },
    get districtLabel() { return I18N.en.districtLabel; },
    get selectDistrict() { return I18N.en.selectDistrict; },
    get talukLabel() { return I18N.en.talukLabel; },
    get selectTaluk() { return I18N.en.selectTaluk; },
    get villageLabel() { return I18N.en.villageLabel; },
    get villagePlaceholder() { return I18N.en.villagePlaceholder; },
    get gpsDetectBtn() { return I18N.en.gpsDetectBtn; },
    get gpsDetecting() { return I18N.en.gpsDetecting; },
    get gpsPrivacyNote() { return I18N.en.gpsPrivacyNote; },

    get stepFarmTitle() { return I18N.en.stepFarmTitle; },
    get stepFarmSub() { return I18N.en.stepFarmSub; },
    get farmingTypeLabel() { return I18N.en.farmingTypeLabel; },
    get landAreaLabel() { return I18N.en.landAreaLabel; },
    get areaUnitLabel() { return I18N.en.areaUnitLabel; },
    get ownershipLabel() { return I18N.en.ownershipLabel; },
    get irrigationLabel() { return I18N.en.irrigationLabel; },
    get addAnotherFarm() { return I18N.en.addAnotherFarm; },
    get farmNumberTitle() { return I18N.en.farmNumberTitle; },

    get stepCropsTitle() { return I18N.en.stepCropsTitle; },
    get stepCropsSub() { return I18N.en.stepCropsSub; },
    get searchCropsPlaceholder() { return I18N.en.searchCropsPlaceholder; },
    get sownDateLabel() { return I18N.en.sownDateLabel; },
    get cropAreaLabel() { return I18N.en.cropAreaLabel; },
    get skipAddLater() { return I18N.en.skipAddLater; },
    get customCropPlaceholder() { return I18N.en.customCropPlaceholder; },

    get reviewTitle() { return I18N.en.reviewTitle; },
    get reviewSub() { return I18N.en.reviewSub; },
    get profileCompletion() { return I18N.en.profileCompletion; },
    get requiredFieldsDone() { return I18N.en.requiredFieldsDone; },
    get editStep() { return I18N.en.editStep; },
    get submitProfile() { return I18N.en.submitProfile; },
    get submitting() { return I18N.en.submitting; },
    get backBtn() { return I18N.en.backBtn; },
    get nextBtn() { return I18N.en.nextBtn; },

    get profileTitle() { return I18N.en.profileTitle; },
    get verifiedPhoneBadge() { return I18N.en.verifiedPhoneBadge; },
    get phoneNoticeKYC() { return I18N.en.phoneNoticeKYC; },
    get accountCreated() { return I18N.en.accountCreated; },
    get onboardingCompleteBadge() { return I18N.en.onboardingCompleteBadge; },
    get onboardingDraftBadge() { return I18N.en.onboardingDraftBadge; },
    get saveChanges() { return I18N.en.saveChanges; },
    get saving() { return I18N.en.saving; },
    get logoutBtn() { return I18N.en.logoutBtn; },
    get notificationsTitle() { return I18N.en.notificationsTitle; },
    get smsAlerts() { return I18N.en.smsAlerts; },
    get whatsappReports() { return I18N.en.whatsappReports; },
    get weatherAlerts() { return I18N.en.weatherAlerts; }
  },

  ta: {
    // Falls back cleanly to English with visible notice
    get tagline() { return I18N.en.tagline; },
    get phoneLabel() { return I18N.en.phoneLabel; },
    get phonePlaceholder() { return I18N.en.phonePlaceholder; },
    get continueBtn() { return I18N.en.continueBtn; },
    get termsNotice() { return I18N.en.termsNotice; },
    get termsLink() { return I18N.en.termsLink; },
    get privacyLink() { return I18N.en.privacyLink; },
    get emailOption() { return I18N.en.emailOption; },
    get phoneOption() { return I18N.en.phoneOption; },
    get emailLabel() { return I18N.en.emailLabel; },
    get emailPlaceholder() { return I18N.en.emailPlaceholder; },
    get sendLinkBtn() { return I18N.en.sendLinkBtn; },
    get checkEmailMsg() { return I18N.en.checkEmailMsg; },

    get otpTitle() { return I18N.en.otpTitle; },
    get otpSubtitle() { return I18N.en.otpSubtitle; },
    get otpMaskedPrefix() { return I18N.en.otpMaskedPrefix; },
    get changeNumber() { return I18N.en.changeNumber; },
    get verifyBtn() { return I18N.en.verifyBtn; },
    get verifyingBtn() { return I18N.en.verifyingBtn; },
    get resendPrefix() { return I18N.en.resendPrefix; },
    get resendAction() { return I18N.en.resendAction; },
    get errWrongOtp() { return I18N.en.errWrongOtp; },
    get errExpiredOtp() { return I18N.en.errExpiredOtp; },
    get errRateLimited() { return I18N.en.errRateLimited; },
    get errGeneric() { return I18N.en.errGeneric; },

    get onboardingHeader() { return I18N.en.onboardingHeader; },
    get saveAndExit() { return I18N.en.saveAndExit; },
    get draftSaved() { return I18N.en.draftSaved; },
    get stepBasicsTitle() { return I18N.en.stepBasicsTitle; },
    get stepBasicsSub() { return I18N.en.stepBasicsSub; },
    get fullNameLabel() { return I18N.en.fullNameLabel; },
    get fullNamePlaceholder() { return I18N.en.fullNamePlaceholder; },
    get prefLangLabel() { return I18N.en.prefLangLabel; },
    get fallbackNoteTe() { return I18N.en.fallbackNoteTe; },
    fallbackNoteTa: "Note: Screen text is displayed in English. Tamil localization is in beta.",

    get stepLocationTitle() { return I18N.en.stepLocationTitle; },
    get stepLocationSub() { return I18N.en.stepLocationSub; },
    get stateLabel() { return I18N.en.stateLabel; },
    get districtLabel() { return I18N.en.districtLabel; },
    get selectDistrict() { return I18N.en.selectDistrict; },
    get talukLabel() { return I18N.en.talukLabel; },
    get selectTaluk() { return I18N.en.selectTaluk; },
    get villageLabel() { return I18N.en.villageLabel; },
    get villagePlaceholder() { return I18N.en.villagePlaceholder; },
    get gpsDetectBtn() { return I18N.en.gpsDetectBtn; },
    get gpsDetecting() { return I18N.en.gpsDetecting; },
    get gpsPrivacyNote() { return I18N.en.gpsPrivacyNote; },

    get stepFarmTitle() { return I18N.en.stepFarmTitle; },
    get stepFarmSub() { return I18N.en.stepFarmSub; },
    get farmingTypeLabel() { return I18N.en.farmingTypeLabel; },
    get landAreaLabel() { return I18N.en.landAreaLabel; },
    get areaUnitLabel() { return I18N.en.areaUnitLabel; },
    get ownershipLabel() { return I18N.en.ownershipLabel; },
    get irrigationLabel() { return I18N.en.irrigationLabel; },
    get addAnotherFarm() { return I18N.en.addAnotherFarm; },
    get farmNumberTitle() { return I18N.en.farmNumberTitle; },

    get stepCropsTitle() { return I18N.en.stepCropsTitle; },
    get stepCropsSub() { return I18N.en.stepCropsSub; },
    get searchCropsPlaceholder() { return I18N.en.searchCropsPlaceholder; },
    get sownDateLabel() { return I18N.en.sownDateLabel; },
    get cropAreaLabel() { return I18N.en.cropAreaLabel; },
    get skipAddLater() { return I18N.en.skipAddLater; },
    get customCropPlaceholder() { return I18N.en.customCropPlaceholder; },

    get reviewTitle() { return I18N.en.reviewTitle; },
    get reviewSub() { return I18N.en.reviewSub; },
    get profileCompletion() { return I18N.en.profileCompletion; },
    get requiredFieldsDone() { return I18N.en.requiredFieldsDone; },
    get editStep() { return I18N.en.editStep; },
    get submitProfile() { return I18N.en.submitProfile; },
    get submitting() { return I18N.en.submitting; },
    get backBtn() { return I18N.en.backBtn; },
    get nextBtn() { return I18N.en.nextBtn; },

    get profileTitle() { return I18N.en.profileTitle; },
    get verifiedPhoneBadge() { return I18N.en.verifiedPhoneBadge; },
    get phoneNoticeKYC() { return I18N.en.phoneNoticeKYC; },
    get accountCreated() { return I18N.en.accountCreated; },
    get onboardingCompleteBadge() { return I18N.en.onboardingCompleteBadge; },
    get onboardingDraftBadge() { return I18N.en.onboardingDraftBadge; },
    get saveChanges() { return I18N.en.saveChanges; },
    get saving() { return I18N.en.saving; },
    get logoutBtn() { return I18N.en.logoutBtn; },
    get notificationsTitle() { return I18N.en.notificationsTitle; },
    get smsAlerts() { return I18N.en.smsAlerts; },
    get whatsappReports() { return I18N.en.whatsappReports; },
    get weatherAlerts() { return I18N.en.weatherAlerts; }
  }
};

export function getDictionary(lang: string): Translations {
  const norm = (lang || "").toLowerCase();
  if (norm.startsWith("kn") || norm === "kannada") return I18N.kn;
  if (norm.startsWith("hi") || norm === "hindi") return I18N.hi;
  if (norm.startsWith("te") || norm === "telugu") return I18N.te;
  if (norm.startsWith("ta") || norm === "tamil") return I18N.ta;
  return I18N.en;
}
