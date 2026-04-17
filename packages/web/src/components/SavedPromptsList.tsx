import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Center,
  Heading,
  HStack,
  IconButton,
  Stack,
  Text,
  useClipboard,
  useToast,
  VStack,
} from "@chakra-ui/react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../apiClient";
import type { SavedPrompt } from "@kratos-suno/core";
import { SOURCE_LABELS } from "@kratos-suno/core";

interface Props {
  onSelect?: (prompt: SavedPrompt) => void;
}

export function SavedPromptsList({ onSelect }: Props) {
  const [items, setItems] = useState<SavedPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listSavedPrompts();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleDelete = async (id: number) => {
    try {
      await api.deleteSavedPrompt(id);
      toast({
        title: "Removido",
        status: "success",
        duration: 1500,
        isClosable: true,
      });
      refresh();
    } catch (err) {
      toast({
        title: "Erro ao remover",
        description: err instanceof Error ? err.message : "",
        status: "error",
      });
    }
  };

  if (loading) {
    return (
      <Center py={8}>
        <Text color="gray.400">Carregando prompts salvos...</Text>
      </Center>
    );
  }

  if (error) {
    return (
      <Alert status="error" borderRadius="md">
        <AlertIcon />
        {error}
      </Alert>
    );
  }

  if (items.length === 0) {
    return (
      <Center py={8}>
        <VStack spacing={2}>
          <Text color="gray.400">Nenhum prompt salvo ainda.</Text>
          <Text fontSize="sm" color="gray.500">
            Gere um prompt e clique em "Salvar" para vê-lo aqui depois.
          </Text>
        </VStack>
      </Center>
    );
  }

  return (
    <Stack spacing={3}>
      {items.map((prompt) => (
        <SavedPromptCard
          key={prompt.id}
          prompt={prompt}
          onDelete={() => handleDelete(prompt.id)}
          onSelect={onSelect ? () => onSelect(prompt) : undefined}
        />
      ))}
    </Stack>
  );
}

function SavedPromptCard({
  prompt,
  onDelete,
  onSelect,
}: {
  prompt: SavedPrompt;
  onDelete: () => void;
  onSelect?: () => void;
}) {
  // Pega a variante "faithful" para copy rápido
  const faithful = prompt.variants.find((v) => v.label === "faithful") || prompt.variants[0];
  const { hasCopied, onCopy } = useClipboard(faithful?.prompt || "");
  const createdAt = new Date(prompt.created_at).toLocaleString("pt-BR");

  return (
    <Box
      p={4}
      borderWidth={1}
      borderRadius="md"
      borderColor="gray.700"
      bg="blackAlpha.300"
    >
      <HStack justify="space-between" mb={2}>
        <VStack align="start" spacing={0}>
          <HStack>
            <Heading size="sm" noOfLines={1}>
              {prompt.subject}
            </Heading>
            <Badge>{SOURCE_LABELS[prompt.source] || prompt.source}</Badge>
          </HStack>
          <Text fontSize="xs" color="gray.500">
            {createdAt} · {prompt.sonic_dna.genre_primary}
            {" · "}
            {prompt.sonic_dna.bpm_typical} BPM
          </Text>
        </VStack>
        <HStack>
          <Button size="xs" onClick={onCopy}>
            {hasCopied ? "Copiado ✓" : "Copiar"}
          </Button>
          {onSelect && (
            <Button size="xs" variant="outline" onClick={onSelect}>
              Ver
            </Button>
          )}
          <IconButton
            aria-label="Remover"
            size="xs"
            variant="ghost"
            colorScheme="red"
            icon={<span>🗑️</span>}
            onClick={onDelete}
          />
        </HStack>
      </HStack>

      {prompt.user_note && (
        <Text fontSize="sm" color="gray.300" fontStyle="italic" mb={2}>
          💭 {prompt.user_note}
        </Text>
      )}

      <Text
        fontFamily="mono"
        fontSize="xs"
        color="gray.300"
        noOfLines={2}
      >
        {faithful?.prompt}
      </Text>
    </Box>
  );
}
