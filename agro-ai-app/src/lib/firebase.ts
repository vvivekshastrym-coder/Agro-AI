/**
 * Agro AI Firebase Client (React / TypeScript)
 * Project: gen-lang-client-0224945015 (AGRO AI)
 */

import { initializeApp, getApps, getApp, FirebaseApp } from "firebase/app";
import { getAuth, Auth, RecaptchaVerifier, signInWithPhoneNumber, ConfirmationResult } from "firebase/auth";

export const firebaseConfig = {
  apiKey: "AIzaSyC-Dj9TJoFMZeCfYTrC77mFwQchgjDhPYs",
  authDomain: "gen-lang-client-0224945015.firebaseapp.com",
  projectId: "gen-lang-client-0224945015",
  storageBucket: "gen-lang-client-0224945015.firebasestorage.app",
  messagingSenderId: "390368260977",
  appId: "1:390368260977:web:d3076ca38d0e18fd1dbcd0",
  measurementId: "G-CBLVGBDRWR"
};

export const app: FirebaseApp = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
export const auth: Auth = getAuth(app);

let confirmationResult: ConfirmationResult | null = null;

export function setupRecaptcha(containerId = "recaptcha-container"): RecaptchaVerifier {
  return new RecaptchaVerifier(auth, containerId, {
    size: "invisible",
    callback: () => {}
  });
}

export async function sendFirebasePhoneOtp(phone: string, appVerifier: RecaptchaVerifier): Promise<ConfirmationResult> {
  const formatted = phone.startsWith("+") ? phone : `+91${phone.replace(/\D/g, "")}`;
  confirmationResult = await signInWithPhoneNumber(auth, formatted, appVerifier);
  return confirmationResult;
}

export async function verifyFirebasePhoneOtp(code: string) {
  if (!confirmationResult) throw new Error("No active OTP verification session found.");
  const res = await confirmationResult.confirm(code);
  return res.user;
}
