import type {
  GenerateResponse,
  SpotifyArtist,
  SpotifyTimeRange,
  TasteProfile,
} from "@kratos-suno/core";
import { useAuth } from "@kratos-suno/core";
import { router, useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useState } from "react";
import { FlatList, Image, StyleSheet, View } from "react-native";
import {
  ActivityIndicator,
  Button,
  Card,
  Chip,
  SegmentedButtons,
  Snackbar,
  Text,
} from "react-native-paper";

import { api } from "@/src/apiClient";

const TIME_RANGE_OPTIONS: Array<{ value: SpotifyTimeRange; label: string }> = [
  { value: "short_term", label: "4 sem" },
  { value: "medium_term", label: "6 meses" },
  { value: "long_term", label: "Anos" },
];

export default function SpotifyScreen() {
  const { auth, isLoading: authLoading, loginWithSpotify, logout, refresh } = useAuth({
    client: api,
    // W1-B: mobile flow — backend issues JWT via /mobile-callback + deep link
    platform: "mobile",
    onOpenAuthUrl: async (url) => {
      // Abre browser nativo para o flow PKCE do Spotify. Depois do callback,
      // o backend redireciona para kratossuno://spotify-connected?token=<jwt>
      // — o listener em app/_layout.tsx captura e salva o token.
      await WebBrowser.openAuthSessionAsync(url, "kratossuno://spotify-connected");
    },
  });

  // W1-B: re-check auth when the tab gains focus — the deep link handler
  // in _layout.tsx persists the JWT, and refresh() picks up the new state.
  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const [profile, setProfile] = useState<TasteProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<SpotifyTimeRange>("medium_term");
  const [error, setError] = useState<string | null>(null);
  const [generatingFor, setGeneratingFor] = useState<string | null>(null);

  useEffect(() => {
    if (!auth?.authenticated) {
      setProfile(null);
      return;
    }
    setProfileLoading(true);
    setError(null);
    api
      .getTasteProfile(timeRange)
      .then(setProfile)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro"))
      .finally(() => setProfileLoading(false));
  }, [auth?.authenticated, timeRange]);

  const handleArtistPress = async (artist: SpotifyArtist) => {
    setGeneratingFor(artist.spotify_id);
    try {
      const result: GenerateResponse = await api.generateFromText({ subject: artist.name });
      router.push({
        pathname: "/result",
        params: { payload: JSON.stringify(result), source: "spotify_taste" },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro");
    } finally {
      setGeneratingFor(null);
    }
  };

  if (authLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!auth?.authenticated) {
    return (
      <View style={styles.centerContainer}>
        <Text variant="headlineSmall" style={styles.title}>
          🎶 Conecte seu Spotify
        </Text>
        <Text variant="bodyMedium" style={styles.description}>
          Gere prompts Suno a partir dos artistas que você mais ouve. Usamos apenas
          leitura de top artists (escopo user-top-read).
        </Text>
        <Button
          mode="contained"
          onPress={() => void loginWithSpotify()}
          style={styles.loginButton}
          contentStyle={styles.buttonContent}
          icon="music"
        >
          Conectar com Spotify
        </Button>
        <Button mode="text" onPress={() => void refresh()} style={styles.refreshButton}>
          Já conectei — verificar novamente
        </Button>
        <Text variant="bodySmall" style={styles.warning}>
          ⚠️ Em abril/2026 o Spotify descontinuou audio-features e preview_url.
          Esta integração usa apenas metadados de artistas e gêneros.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text variant="bodySmall" style={styles.muted}>
            Conectado como
          </Text>
          <Text variant="titleMedium">{auth.display_name ?? auth.spotify_user_id}</Text>
        </View>
        <Button mode="text" compact onPress={() => void logout()}>
          Sair
        </Button>
      </View>

      <SegmentedButtons
        value={timeRange}
        onValueChange={(v) => setTimeRange(v as SpotifyTimeRange)}
        buttons={TIME_RANGE_OPTIONS}
        style={styles.segmented}
      />

      {profile && profile.dominant_genres.length > 0 && (
        <View style={styles.genresContainer}>
          <Text variant="labelSmall" style={styles.sectionTitle}>
            GÊNEROS DOMINANTES
          </Text>
          <View style={styles.chipsRow}>
            {profile.dominant_genres.slice(0, 8).map((g) => (
              <Chip key={g} compact style={styles.chip}>
                {g}
              </Chip>
            ))}
          </View>
        </View>
      )}

      <Text variant="labelSmall" style={[styles.sectionTitle, styles.listHeader]}>
        TOP ARTISTAS — TOQUE PARA GERAR PROMPT
      </Text>

      {profileLoading ? (
        <ActivityIndicator style={{ marginTop: 20 }} />
      ) : (
        <FlatList
          data={profile?.top_artists ?? []}
          keyExtractor={(item) => item.spotify_id}
          renderItem={({ item }) => (
            <Card
              style={styles.artistCard}
              onPress={() => void handleArtistPress(item)}
              disabled={generatingFor !== null}
            >
              <Card.Content style={styles.artistRow}>
                {item.image_url ? (
                  <Image source={{ uri: item.image_url }} style={styles.avatar} />
                ) : (
                  <View style={[styles.avatar, styles.avatarPlaceholder]} />
                )}
                <View style={styles.artistMeta}>
                  <Text variant="titleMedium">{item.name}</Text>
                  {item.genres.length > 0 && (
                    <Text variant="bodySmall" style={styles.muted} numberOfLines={1}>
                      {item.genres.slice(0, 3).join(" · ")}
                    </Text>
                  )}
                </View>
                {generatingFor === item.spotify_id ? (
                  <ActivityIndicator size="small" />
                ) : (
                  <Text style={styles.arrow}>›</Text>
                )}
              </Card.Content>
            </Card>
          )}
          contentContainerStyle={styles.listContent}
        />
      )}

      <Snackbar
        visible={!!error}
        onDismiss={() => setError(null)}
        duration={4000}
        action={{ label: "OK", onPress: () => setError(null) }}
      >
        {error}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a" },
  centerContainer: {
    flex: 1,
    backgroundColor: "#0a0a0a",
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
    gap: 16,
  },
  title: { color: "#e0e0e0", textAlign: "center" },
  description: { color: "#a0a0a0", textAlign: "center", marginHorizontal: 24 },
  loginButton: { marginTop: 8 },
  buttonContent: { paddingVertical: 6 },
  refreshButton: { marginTop: 4 },
  warning: { color: "#808080", textAlign: "center", marginTop: 16, marginHorizontal: 24 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
  },
  muted: { color: "#a0a0a0" },
  segmented: { marginHorizontal: 16, marginBottom: 8 },
  sectionTitle: { color: "#808080", letterSpacing: 1 },
  listHeader: { paddingHorizontal: 16, paddingTop: 16 },
  genresContainer: { paddingHorizontal: 16, marginTop: 8 },
  chipsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 6 },
  chip: { backgroundColor: "#1e1e1e" },
  artistCard: { backgroundColor: "#151515", marginHorizontal: 16, marginVertical: 4 },
  artistRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 4 },
  avatar: { width: 48, height: 48, borderRadius: 24 },
  avatarPlaceholder: { backgroundColor: "#2a2a2a" },
  artistMeta: { flex: 1 },
  arrow: { color: "#1DB954", fontSize: 24 },
  listContent: { paddingBottom: 20 },
});
