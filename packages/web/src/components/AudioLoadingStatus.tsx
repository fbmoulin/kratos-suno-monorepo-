import { Text, VStack } from "@chakra-ui/react";
import { useEffect, useState } from "react";

const STATUS_MESSAGES = [
  "Extraindo áudio...",
  "Analisando estilo...",
  "Gerando prompts...",
] as const;

const ROTATION_SECONDS = 5;

interface Props {
  isLoading: boolean;
}

export function AudioLoadingStatus({ isLoading }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setElapsed(0);
      return;
    }
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [isLoading]);

  if (!isLoading) return null;

  const statusIndex =
    Math.floor(elapsed / ROTATION_SECONDS) % STATUS_MESSAGES.length;

  return (
    <VStack spacing={1} mt={4} align="center">
      <Text fontSize="xs" color="gray.400">
        Isso pode levar 30-40 segundos
      </Text>
      <Text fontSize="sm" color="gray.300">
        {STATUS_MESSAGES[statusIndex]}
      </Text>
      <Text fontSize="xs" color="gray.500">⏱ {elapsed}s</Text>
    </VStack>
  );
}
