import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { theme } from "@/src/theme";

export default function RootLayout() {
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
        </Stack>
      </PaperProvider>
    </SafeAreaProvider>
  );
}
