import {
  Box,
  Button,
  Flex,
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useState } from "react";

interface Props {
  onSubmit: (subject: string) => void;
  isLoading: boolean;
}

const MAX_SUBJECT_LENGTH = 200;
const WARNING_THRESHOLD = 180;

export function TextInput({ onSubmit, isLoading }: Props) {
  const [subject, setSubject] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = subject.trim();
    if (trimmed.length > 0) {
      onSubmit(trimmed);
    }
  };

  const isWarning = subject.length > WARNING_THRESHOLD;

  return (
    <Box as="form" onSubmit={handleSubmit}>
      <VStack spacing={4} align="stretch">
        <FormControl>
          <FormLabel>Nome do artista, banda ou música</FormLabel>
          <Input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Ex: Coldplay, Bohemian Rhapsody, Djavan"
            size="lg"
            isDisabled={isLoading}
            isInvalid={isWarning}
            maxLength={MAX_SUBJECT_LENGTH}
            autoFocus
          />
          <Flex justify="space-between" align="baseline" mt={1}>
            <FormHelperText mt={0}>
              O sistema extrai o "DNA sonoro" e gera prompts legalmente seguros
              (sem citar nomes próprios).
            </FormHelperText>
            <Text
              data-testid="subject-char-counter"
              data-warning={isWarning ? "true" : undefined}
              role="status"
              aria-live="polite"
              fontSize="xs"
              color={isWarning ? "red.400" : "gray.400"}
              flexShrink={0}
              ml={2}
            >
              {subject.length}/{MAX_SUBJECT_LENGTH}
            </Text>
          </Flex>
        </FormControl>
        <Button
          type="submit"
          colorScheme="brand"
          size="lg"
          isLoading={isLoading}
          loadingText="Analisando..."
          isDisabled={subject.trim().length === 0}
        >
          Gerar prompts Suno
        </Button>
      </VStack>
    </Box>
  );
}
