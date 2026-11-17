/**
 * Agro AI Firebase Client Integration
 * Project: gen-lang-client-0224945015 (AGRO AI)
 * 
 * Provides Firebase App, Firebase Authentication (Phone OTP & Google Auth),
 * and Firestore integration for Agro AI.
 */

// Production Firebase Configuration
export const firebaseConfig = {
  apiKey: "AIzaSyC-Dj9TJoFMZeCfYTrC77mFwQchgjDhPYs",
  authDomain: "gen-lang-client-0224945015.firebaseapp.com",
  projectId: "gen-lang-client-0224945015",
  storageBucket: "gen-lang-client-0224945015.firebasestorage.app",
  messagingSenderId: "390368260977",
  appId: "1:390368260977:web:d3076ca38d0e18fd1dbcd0",
  measurementId: "G-CBLVGBDRWR"
};

let _firebaseApp = null;
let _firebaseAuth = null;
let _recaptchaVerifier = null;
let _confirmationResult = null;

/**
 * Initializes Firebase App instance
 */
export async function getFirebaseApp() {
  if (_firebaseApp) return _firebaseApp;
  try {
    const { initializeApp, getApps } = await import("https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js");
    const apps = getApps();
    if (apps.length > 0) {
      _firebaseApp = apps[0];
    } else {
      _firebaseApp = initializeApp(firebaseConfig);
    }
    return _firebaseApp;
  } catch (err) {
    console.warn("Firebase SDK initialization error:", err);
    return null;
  }
}

/**
 * Gets Firebase Auth instance
 */
export async function getFirebaseAuth() {
  if (_firebaseAuth) return _firebaseAuth;
  const app = await getFirebaseApp();
  if (!app) return null;
  try {
    const { getAuth } = await import("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js");
    _firebaseAuth = getAuth(app);
    return _firebaseAuth;
  } catch (err) {
    console.warn("Firebase Auth load error:", err);
    return null;
  }
}

/**
 * Prepares reCAPTCHA verifier for Phone OTP
 */
export async function setupRecaptcha(containerId = "recaptcha-container") {
  const auth = await getFirebaseAuth();
  if (!auth) return null;
  const { RecaptchaVerifier } = await import("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js");

  if (_recaptchaVerifier) {
    try { _recaptchaVerifier.clear(); } catch (_) {}
  }

  _recaptchaVerifier = new RecaptchaVerifier(auth, containerId, {
    size: "invisible",
    callback: () => {
      // reCAPTCHA solved
    },
    "expired-callback": () => {
      console.warn("reCAPTCHA expired. Please retry.");
    }
  });

  return _recaptchaVerifier;
}

/**
 * Sends real SMS OTP via Firebase Authentication
 * (Free 10,000 SMS/month across India and globally)
 */
export async function sendFirebasePhoneOtp(phoneNumber, containerId = "recaptcha-container") {
  const auth = await getFirebaseAuth();
  if (!auth) throw new Error("Firebase Auth is not initialized.");
  const { signInWithPhoneNumber } = await import("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js");

  const verifier = await setupRecaptcha(containerId);
  const formattedPhone = phoneNumber.startsWith("+") ? phoneNumber : `+91${phoneNumber.replace(/\D/g, "")}`;

  _confirmationResult = await signInWithPhoneNumber(auth, formattedPhone, verifier);
  return {
    success: true,
    message: `OTP sent successfully via Firebase to ${formattedPhone}`
  };
}

/**
 * Verifies the 6-digit OTP code with Firebase
 */
export async function verifyFirebasePhoneOtp(code) {
  if (!_confirmationResult) {
    throw new Error("No pending OTP request found. Please request a code first.");
  }
  const result = await _confirmationResult.confirm(code);
  return result.user;
}

/**
 * Sign in using Google Authentication via Firebase Auth
 */
export async function signInWithGoogleFirebase() {
  const auth = await getFirebaseAuth();
  if (!auth) throw new Error("Firebase Auth is not initialized.");
  const { GoogleAuthProvider, signInWithPopup } = await import("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js");
  const provider = new GoogleAuthProvider();
  provider.addScope("email");
  provider.addScope("profile");
  
  const result = await signInWithPopup(auth, provider);
  const user = result.user;
  const idToken = await user.getIdToken();
  
  const googleSession = {
    access_token: idToken,
    token_type: "bearer",
    user: {
      id: user.uid,
      email: user.email,
      phone: user.phoneNumber || null,
      user_metadata: {
        full_name: user.displayName || (user.email ? user.email.split("@")[0] : "Farmer"),
        name: user.displayName,
        avatar_url: user.photoURL || "",
      },
      app_metadata: {
        provider: "google",
      },
    },
  };

  localStorage.setItem("kisanAuth", "true");
  localStorage.setItem("kisanUser", JSON.stringify({
    id: user.uid,
    email: user.email,
    name: user.displayName || "Farmer Partner",
    avatar: user.photoURL || ""
  }));

  window.dispatchEvent(new CustomEvent("agro:signed-in", { detail: googleSession }));
  return googleSession;
}

// Global window registration for non-module script access
if (typeof window !== "undefined") {
  window.AgroFirebase = {
    firebaseConfig,
    getFirebaseApp,
    getFirebaseAuth,
    setupRecaptcha,
    sendFirebasePhoneOtp,
    verifyFirebasePhoneOtp,
    signInWithGoogleFirebase
  };
}

