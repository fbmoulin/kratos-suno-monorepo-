import type { GenerateResponse } from "@kratos-suno/core";
import { router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { Button, Snackbar, Text, TextInput } from "react-native-paper";

import { api } from "@/src/apiClient";

export default function TextScreen() {
  const [subject, setSubject] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const trimmed = subject.trim();
    if (!trimmed) return;
    setIsLoading(true);
    setError(null);
    try {
      const result: GenerateResponse = await api.generateFromText({ subject: trimmed });
      router.push({
        pathname: "/result",
        params: {
          payload: JSON.stringify(result),
          source: "text",
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      <View style={styles.content}>
        <Text variant="headlineSmall" style={styles.title}>
          📝 Por texto
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Digite o nome de um artista, banda ou música.
        </Text>

        <TextInput
          mode="outlined"
          label="Nome"
          placeholder="Ex: Coldplay, Bohemian Rhapsody, Djavan"
          value={subject}
          onChangeText={setSubject}
          autoCapitalize="words"
          autoCorrect={false}
          disabled={isLoading}
          style={styles.input}
          returnKeyType="go"
          onSubmitEditing={handleSubmit}
        />

        <Button
          mode="contained"
          onPress={handleSubmit}
          loading={isLoading}
          disabled={!subject.trim() || isLoading}
          style={styles.button}
          contentStyle={styles.buttonContent}
        >
          {isLoading ? "Analisando..." : "Gerar prompts Suno"}
        </Button>

        <Text variant="bodySmall" style={styles.helper}>
          O sistema extrai o "DNA sonoro" e gera 3 variantes legalmente seguras
          (sem citar nomes próprios).
        </Text>
      </View>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError(null)}
        duration={5000}
        action={{ label: "OK", onPress: () => setError(null) }}
      >
        {error}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a" },
  content: { padding: 20, gap: 16 },
  title: { color: "#e0e0e0", marginTop: 20 },
  subtitle: { color: "#a0a0a0" },
  input: { backgroundColor: "#151515" },
  button: { marginTop: 8 },
  buttonContent: { paddingVertical: 8 },
  helper: { color: "#808080", marginTop: 8, fontStyle: "italic" },
});
