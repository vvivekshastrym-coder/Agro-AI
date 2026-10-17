import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.CAPACITOR_SERVER_URL;

const config: CapacitorConfig = {
  appId: "com.agroai.kisan",
  appName: "Agro AI",
  webDir: "dist",
  ...(serverUrl
    ? {
        server: {
          url: serverUrl,
          cleartext: true,
          androidScheme: "https",
        },
      }
    : {
        server: {
          androidScheme: "https",
        },
      }),
  android: {
    backgroundColor: "#FFF8EC",
    allowMixedContent: true,
  },
  ios: {
    backgroundColor: "#FFF8EC",
    contentInset: "always",
  },
};

export default config;
