import type { CapacitorConfig } from "@capacitor/cli";

// Agro AI native shell configuration.
// To build native Android/iOS apps locally:
//   1. Export this project to GitHub and git clone it
//   2. bun install
//   3. bunx cap add android   (and/or)   bunx cap add ios
//   4. bunx cap sync
//   5. bunx cap open android   (opens Android Studio to build .aab for Play Store)
//      bunx cap open ios       (opens Xcode to build .ipa for App Store)
//
// The `server.url` below loads the live published web app inside the native
// shell, so any update you publish on Lovable instantly appears in the
// installed app — no resubmission needed for content changes.
const config: CapacitorConfig = {
  appId: "app.lovable.agroai",
  appName: "Agro AI",
  webDir: "dist",
  server: {
    url: "https://kisan-aaha-gyaan.lovable.app",
    cleartext: false,
    androidScheme: "https",
  },
  android: {
    backgroundColor: "#FFF8EC",
  },
  ios: {
    backgroundColor: "#FFF8EC",
    contentInset: "always",
  },
};

export default config;
