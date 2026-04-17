import type { GenerateResponse, PromptSource, SunoPromptVariant } from "@kratos-suno/core";
import { getVariantMeta } from "@kratos-suno/core";
import * as Clipboard from "expo-clipboard";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import {
  Button,
  Card,
  Chip,
  Divider,
  IconButton,
  Snackbar,
  Text,
  TextInput,
} from "react-native-paper";

import { api } from "@/src/apiClient";

export default function ResultScreen() {
  const params = useLocalSearchParams<{ payload: string; source: PromptSource }>();
  const result = useMemo<GenerateResponse | null>(() => {
    try {
      return params.payload ? (JSON.parse(params.payload) as GenerateResponse) : null;
    } catch {
      return null;
    }
  }, [params.payload]);

  const [userNote, setUserNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);

  if (!result) {
    return (
      <View style={styles.centerContainer}>
        <Text variant="bodyMedium">Resultado inválido.</Text>
        <Button mode="text" onPress={() => router.back()}>
          Voltar
        </Button>
      </View>
    );
  }

  const { sonic_dna: dna, variants, lyric_template } = result;

  const handleCopy = async (text: string, label: string) => {
    await Clipboard.setStringAsync(text);
    setSnack(`${label} copiado`);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.createSavedPrompt({
        subject: result.subject,
        source: params.source,
        sonic_dna: dna,
        variants,
        lyric_template,
        user_note: userNote.trim() || undefined,
      });
      setSaved(true);
      setSnack("Prompt salvo!");
    } catch (err) {
      setSnack(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text variant="headlineSmall" style={styles.title}>
        🎵 {result.subject}
      </Text>

      <Card style={styles.dnaCard}>
        <Card.Content>
          <Text variant="bodySmall" style={styles.muted}>
            <Text style={styles.bold}>Era:</Text> {dna.era} ·{" "}
            <Text style={styles.bold}>Gênero:</Text> {dna.genre_primary} ·{" "}
            <Text style={styles.bold}>BPM:</Text> {dna.bpm_typical}
          </Text>
          <Text variant="bodySmall" style={[styles.muted, { marginTop: 4 }]}>
            <Text style={styles.bold}>Mood:</Text> {dna.mood_primary} ·{" "}
            <Text style={styles.bold}>Articulação:</Text> {dna.articulation_score}/10
          </Text>
        </Card.Content>
      </Card>

      {variants.map((v) => (
        <VariantCard key={v.label} variant={v} onCopy={handleCopy} />
      ))}

      <Card style={styles.saveCard}>
        <Card.Content style={styles.saveCardContent}>
          <TextInput
            mode="outlined"
            label="Nota opcional"
            placeholder="Ex: pra tentar funk paulista"
            value={userNote}
            onChangeText={setUserNote}
            disabled={saving || saved}
            maxLength={500}
            dense
          />
          <Button
            mode="contained"
            onPress={handleSave}
            loading={saving}
            disabled={saved || saving}
            icon={saved ? "check" : "bookmark-outline"}
            style={{ marginTop: 8 }}
          >
            {saved ? "Salvo" : "Salvar prompt"}
          </Button>
        </Card.Content>
      </Card>

      <Divider style={styles.divider} />

      <View style={styles.lyricsHeader}>
        <Text variant="titleSmall" style={styles.muted}>
          📝 Template de letras
        </Text>
        <IconButton
          icon="content-copy"
          size={18}
          onPress={() => void handleCopy(lyric_template, "Template")}
        />
      </View>
      <Card style={styles.lyricsCard}>
        <Card.Content>
          <Text variant="bodySmall" style={styles.lyricsText}>
            {lyric_template}
          </Text>
        </Card.Content>
      </Card>

      <Text variant="bodySmall" style={styles.disclaimer}>
        {result.disclaimer}
      </Text>

      <Snackbar
        visible={!!snack}
        onDismiss={() => setSnack(null)}
        duration={2000}
      >
        {snack}
      </Snackbar>
    </ScrollView>
  );
}

interface VariantCardProps {
  variant: SunoPromptVariant;
  onCopy: (text: string, label: string) => Promise<void>;
}

function VariantCard({ variant, onCopy }: VariantCardProps) {
  const meta = getVariantMeta(variant.label);
  return (
    <Card style={styles.variantCard}>
      <Card.Content>
        <View style={styles.variantHeader}>
          <View style={{ flex: 1 }}>
            <Text variant="titleMedium">
              {meta.emoji} {meta.label}
            </Text>
            <Text variant="bodySmall" style={styles.muted}>
              {meta.description}
            </Text>
          </View>
          <Chip compact style={styles.charChip}>
            {variant.char_count}/200
          </Chip>
        </View>

        <View style={styles.promptBox}>
          <Text variant="bodyMedium" style={styles.promptText}>
            {variant.prompt}
          </Text>
        </View>

        <Button
          mode="outlined"
          onPress={() => void onCopy(variant.prompt, meta.label)}
          icon="content-copy"
          style={{ marginTop: 8 }}
        >
          Copiar
        </Button>
      </Card.Content>
    </Card>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a" },
  content: { padding: 16, gap: 10 },
  centerContainer: {
    flex: 1,
    backgroundColor: "#0a0a0a",
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
  },
  title: { color: "#e0e0e0", marginBottom: 4 },
  bold: { fontWeight: "bold", color: "#e0e0e0" },
  muted: { color: "#a0a0a0" },
  dnaCard: { backgroundColor: "#1e1e1e" },
  variantCard: { backgroundColor: "#151515", marginVertical: 4 },
  variantHeader: { flexDirection: "row", alignItems: "center" },
  charChip: { backgroundColor: "#1e1e1e" },
  promptBox: {
    marginTop: 10,
    padding: 12,
    backgroundColor: "#0a0a0a",
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#2a2a2a",
  },
  promptText: { color: "#e0e0e0", fontFamily: "monospace" },
  saveCard: { backgroundColor: "#151515", borderWidth: 1, borderColor: "#2a2a2a" },
  saveCardContent: { gap: 4 },
  divider: { backgroundColor: "#2a2a2a", marginVertical: 8 },
  lyricsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  lyricsCard: { backgroundColor: "#151515" },
  lyricsText: { color: "#c0c0c0", fontFamily: "monospace" },
  disclaimer: { color: "#606060", textAlign: "center", marginTop: 12, marginBottom: 24 },
});
