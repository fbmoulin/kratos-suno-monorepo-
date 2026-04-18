/**
 * Deep-link landing screen for the Spotify mobile OAuth flow (W1-B).
 *
 * When the backend redirects to ``kratossuno://spotify-connected?token=...``,
 * Expo Router matches this route via the ``kratossuno://`` scheme declared in
 * ``app.json``. We save the JWT and bounce to the Spotify tab, which picks up
 * the new ``auth`` state via the ``refresh()`` in ``useAuth``.
 */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Text } from "react-native-paper";

import { setToken } from "@/src/session";

export default function SpotifyConnected() {
  const { token, error } = useLocalSearchParams<{ token?: string; error?: string }>();

  useEffect(() => {
    (async () => {
      if (token) {
        await setToken(token);
      }
      // bounce back to the Spotify tab either way — error is shown briefly first
      router.replace("/(tabs)/spotify");
    })();
  }, [token]);

  return (
    <View style={styles.container}>
      <ActivityIndicator />
      <Text style={styles.text}>
        {error ? `Erro: ${error}` : "Conectando Spotify..."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0a0a0a",
  },
  text: { color: "#e0e0e0", marginTop: 16 },
});
