import type { SavedPrompt } from "@kratos-suno/core";
import { SOURCE_LABELS } from "@kratos-suno/core";
import { useCallback, useEffect, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, View } from "react-native";
import {
  ActivityIndicator,
  Card,
  Chip,
  IconButton,
  Snackbar,
  Text,
} from "react-native-paper";

import { api } from "@/src/apiClient";

export default function SavedScreen() {
  const [items, setItems] = useState<SavedPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.listSavedPrompts();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const handleDelete = async (id: number) => {
    try {
      await api.deleteSavedPrompt(id);
      setItems((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover");
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text variant="headlineSmall" style={styles.title}>
          💾 Nada salvo ainda
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Gere um prompt e toque em "Salvar" para vê-lo aqui.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={items}
        keyExtractor={(item) => String(item.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#1DB954" />
        }
        renderItem={({ item }) => {
          const faithful =
            item.variants.find((v) => v.label === "faithful") ?? item.variants[0];
          const createdAt = new Date(item.created_at).toLocaleString("pt-BR");
          return (
            <Card style={styles.card}>
              <Card.Content>
                <View style={styles.header}>
                  <View style={styles.headerLeft}>
                    <Text variant="titleMedium" numberOfLines={1}>
                      {item.subject}
                    </Text>
                    <View style={styles.metaRow}>
                      <Chip compact style={styles.chip}>
                        {SOURCE_LABELS[item.source] ?? item.source}
                      </Chip>
                      <Text variant="bodySmall" style={styles.muted}>
                        {item.sonic_dna.genre_primary} · {item.sonic_dna.bpm_typical} BPM
                      </Text>
                    </View>
                  </View>
                  <IconButton
                    icon="delete-outline"
                    size={20}
                    onPress={() => void handleDelete(item.id)}
                    iconColor="#ff6b6b"
                  />
                </View>

                <Text variant="bodySmall" style={styles.timestamp}>
                  {createdAt}
                </Text>

                {item.user_note && (
                  <Text variant="bodySmall" style={styles.note}>
                    💭 {item.user_note}
                  </Text>
                )}

                {faithful && (
                  <View style={styles.promptBox}>
                    <Text variant="bodySmall" style={styles.promptText} numberOfLines={3}>
                      {faithful.prompt}
                    </Text>
                  </View>
                )}
              </Card.Content>
            </Card>
          );
        }}
        contentContainerStyle={styles.listContent}
      />

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
    gap: 12,
  },
  title: { color: "#e0e0e0", textAlign: "center" },
  subtitle: { color: "#a0a0a0", textAlign: "center" },
  card: { backgroundColor: "#151515", marginHorizontal: 16, marginVertical: 6 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  headerLeft: { flex: 1 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4, flexWrap: "wrap" },
  chip: { backgroundColor: "#1e1e1e", height: 24 },
  muted: { color: "#808080" },
  timestamp: { color: "#606060", marginTop: 4 },
  note: { color: "#a0a0a0", marginTop: 8, fontStyle: "italic" },
  promptBox: {
    marginTop: 10,
    padding: 10,
    backgroundColor: "#0a0a0a",
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#2a2a2a",
  },
  promptText: { color: "#c0c0c0", fontFamily: "monospace" },
  listContent: { paddingVertical: 12 },
});
