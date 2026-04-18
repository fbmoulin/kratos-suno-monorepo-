import { Stack, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as Linking from "expo-linking";
import { useEffect } from "react";
import { PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { handleSpotifyConnectedUrl } from "@/src/deepLinks";
import { theme } from "@/src/theme";

export default function RootLayout() {
  useEffect(() => {
    // W1-B: capture spotify-connected deep links from warm starts
    const sub = Linking.addEventListener("url", ({ url }) => {
      if (url.includes("spotify-connected")) {
        void handleSpotifyConnectedUrl(url).then((result) => {
          if (result.ok) {
            router.replace("/(tabs)/spotify");
          }
        });
      }
    });

    // Also handle cold starts where the app is launched via the deep link
    void (async () => {
      const initial = await Linking.getInitialURL();
      if (initial && initial.includes("spotify-connected")) {
        await handleSpotifyConnectedUrl(initial);
      }
    })();

    return () => sub.remove();
  }, []);

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <StatusBar style="light" />
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen
            name="result"
            options={{
              presentation: "modal",
              headerShown: true,
              title: "Prompts gerados",
            }}
          />
          <Stack.Screen
            name="spotify-connected"
            options={{ headerShown: false }}
          />
        </Stack>
      </PaperProvider>
    </SafeAreaProvider>
  );
}
