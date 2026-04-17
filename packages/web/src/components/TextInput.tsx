import {
  Box,
  Button,
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  VStack,
} from "@chakra-ui/react";
import { useState } from "react";

interface Props {
  onSubmit: (subject: string) => void;
  isLoading: boolean;
}

export function TextInput({ onSubmit, isLoading }: Props) {
  const [subject, setSubject] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = subject.trim();
    if (trimmed.length > 0) {
      onSubmit(trimmed);
    }
  };

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
            autoFocus
          />
          <FormHelperText>
            O sistema extrai o "DNA sonoro" e gera prompts legalmente seguros
            (sem citar nomes próprios).
          </FormHelperText>
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
