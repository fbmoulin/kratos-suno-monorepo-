import type { GenerateResponse } from "@kratos-suno/core";
import * as DocumentPicker from "expo-document-picker";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { Button, Card, Snackbar, Text, TextInput } from "react-native-paper";

import { api } from "@/src/apiClient";

interface PickedFile {
  uri: string;
  name: string;
  size: number;
  mimeType?: string;
}

const MAX_SIZE_MB = 25;

export default function AudioScreen() {
  const [file, setFile] = useState<PickedFile | null>(null);
  const [userHint, setUserHint] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickFile = async () => {
    setError(null);
    const result = await DocumentPicker.getDocumentAsync({
      type: ["audio/mpeg", "audio/wav", "audio/flac", "audio/mp4", "audio/ogg"],
      multiple: false,
      copyToCacheDirectory: true,
    });

    if (result.canceled || !result.assets?.[0]) return;

    const asset = result.assets[0];
    if (asset.size && asset.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Arquivo excede ${MAX_SIZE_MB}MB (${(asset.size / 1024 / 1024).toFixed(1)}MB)`);
      return;
    }

    setFile({
      uri: asset.uri,
      name: asset.name,
      size: asset.size ?? 0,
      mimeType: asset.mimeType,
    });
  };

  const handleSubmit = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      // Em RN, monta-se FormData com { uri, name, type }
      const blob = {
        uri: file.uri,
        name: file.name,
        type: file.mimeType ?? "audio/mpeg",
      } as unknown as Blob;

      const result: GenerateResponse = await api.generateFromAudio(
        blob,
        userHint.trim() || undefined,
      );
      router.push({
        pathname: "/result",
        params: { payload: JSON.stringify(result), source: "audio" },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineSmall" style={styles.title}>
          🎧 Por áudio
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Selecione um MP3/WAV/FLAC de até {MAX_SIZE_MB}MB. Analisamos os primeiros 60s.
        </Text>

        <Card style={styles.card} onPress={pickFile}>
          <Card.Content style={styles.cardContent}>
            {file ? (
              <>
                <Text variant="titleMedium" numberOfLines={1}>
                  {file.name}
                </Text>
                <Text variant="bodySmall" style={styles.muted}>
                  {(file.size / 1024 / 1024).toFixed(1)}MB
                  {file.mimeType ? ` · ${file.mimeType}` : ""}
                </Text>
                <Text variant="bodySmall" style={styles.changeHint}>
                  Tocar para trocar
                </Text>
              </>
            ) : (
              <>
                <Text variant="titleMedium" style={styles.pickTitle}>
                  🎵 Selecionar arquivo
                </Text>
                <Text variant="bodySmall" style={styles.muted}>
                  MP3, WAV, FLAC, M4A, OGG
                </Text>
              </>
            )}
          </Card.Content>
        </Card>

        <TextInput
          mode="outlined"
          label="Dica opcional"
          placeholder="Ex: sertanejo universitário"
          value={userHint}
          onChangeText={setUserHint}
          disabled={isLoading}
          style={styles.input}
        />

        <Button
          mode="contained"
          onPress={handleSubmit}
          loading={isLoading}
          disabled={!file || isLoading}
          style={styles.button}
          contentStyle={styles.buttonContent}
        >
          {isLoading ? "Analisando áudio..." : "Analisar e gerar prompts"}
        </Button>
      </View>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError(null)}
        duration={5000}
        action={{ label: "OK", onPress: () => setError(null) }}
      >
        {error}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a" },
  content: { padding: 20, gap: 16 },
  title: { color: "#e0e0e0", marginTop: 20 },
  subtitle: { color: "#a0a0a0" },
  card: { backgroundColor: "#151515", minHeight: 120 },
  cardContent: { alignItems: "center", justifyContent: "center", paddingVertical: 24, gap: 4 },
  pickTitle: { color: "#1DB954" },
  muted: { color: "#808080" },
  changeHint: { color: "#1DB954", marginTop: 8 },
  input: { backgroundColor: "#151515" },
  button: { marginTop: 8 },
  buttonContent: { paddingVertical: 8 },
});
