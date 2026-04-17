import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Badge,
  Box,
  Button,
  Code,
  Divider,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
  Textarea,
  useClipboard,
  useToast,
  VStack,
} from "@chakra-ui/react";
import { useState } from "react";
import { api } from "../apiClient";
import type {
  GenerateResponse,
  PromptSource,
  SunoPromptVariant,
} from "@kratos-suno/core";

interface Props {
  result: GenerateResponse;
  source: PromptSource;
  onReset: () => void;
}

const VARIANT_CONFIG: Record<
  string,
  { emoji: string; label: string; description: string; color: string }
> = {
  conservative: {
    emoji: "🛡️",
    label: "Conservadora",
    description: "Máxima aderência ao gênero",
    color: "blue",
  },
  faithful: {
    emoji: "🎯",
    label: "Fiel",
    description: "Equilibrada (recomendada)",
    color: "green",
  },
  creative: {
    emoji: "🎨",
    label: "Criativa",
    description: "Mais rica, pode surpreender",
    color: "purple",
  },
};

function VariantCard({ variant }: { variant: SunoPromptVariant }) {
  const config = VARIANT_CONFIG[variant.label];
  const { hasCopied, onCopy } = useClipboard(variant.prompt);
  const toast = useToast();

  const handleCopy = () => {
    onCopy();
    toast({
      title: "Copiado!",
      description: "Cole no campo Style do Suno (Custom Mode)",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  return (
    <Box
      borderWidth={1}
      borderRadius="md"
      p={4}
      borderColor={`${config.color}.700`}
      bg="blackAlpha.300"
    >
      <HStack justify="space-between" mb={2}>
        <HStack>
          <Text fontSize="xl">{config.emoji}</Text>
          <VStack align="start" spacing={0}>
            <Heading size="sm">{config.label}</Heading>
            <Text fontSize="xs" color="gray.400">
              {config.description}
            </Text>
          </VStack>
        </HStack>
        <HStack>
          <Badge colorScheme={config.color} fontSize="xs">
            {variant.char_count}/200 chars
          </Badge>
          <Badge variant="outline" fontSize="xs">
            {variant.tags_count} tags
          </Badge>
        </HStack>
      </HStack>
      <Code
        p={3}
        borderRadius="md"
        display="block"
        whiteSpace="pre-wrap"
        bg="blackAlpha.500"
        fontSize="sm"
      >
        {variant.prompt}
      </Code>
      <Button
        mt={3}
        size="sm"
        colorScheme={config.color}
        variant="outline"
        onClick={handleCopy}
        width="full"
      >
        {hasCopied ? "Copiado ✓" : "Copiar prompt"}
      </Button>
    </Box>
  );
}

export function ResultsDisplay({ result, source, onReset }: Props) {
  const { sonic_dna: dna, variants, lyric_template } = result;
  const { hasCopied: lyricsCopied, onCopy: copyLyrics } = useClipboard(lyric_template);
  const toast = useToast();

  const [userNote, setUserNote] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.createSavedPrompt({
        subject: result.subject,
        source,
        sonic_dna: dna,
        variants,
        lyric_template,
        user_note: userNote.trim() || undefined,
      });
      setIsSaved(true);
      toast({
        title: "Prompt salvo!",
        description: "Você pode encontrá-lo na aba 💾 Salvos",
        status: "success",
        duration: 2500,
        isClosable: true,
      });
    } catch (err) {
      toast({
        title: "Erro ao salvar",
        description: err instanceof Error ? err.message : "Tente novamente",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <VStack spacing={6} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">
          🎵 Prompts gerados para:{" "}
          <Text as="span" color="brand.500">
            {result.subject}
          </Text>
        </Heading>
        <Button size="sm" variant="ghost" onClick={onReset}>
          ← Nova consulta
        </Button>
      </HStack>

      {/* DNA resumido */}
      <Box bg="blackAlpha.400" p={4} borderRadius="md">
        <Text fontSize="sm" color="gray.300">
          <strong>Era:</strong> {dna.era} · <strong>Gênero:</strong>{" "}
          {dna.genre_primary}
          {dna.genre_secondary && ` / ${dna.genre_secondary}`} ·{" "}
          <strong>BPM:</strong> {dna.bpm_typical} · <strong>Mood:</strong>{" "}
          {dna.mood_primary} · <strong>Articulação:</strong>{" "}
          {dna.articulation_score}/10
        </Text>
      </Box>

      {/* Variantes */}
      <Stack spacing={4}>
        {variants.map((v) => (
          <VariantCard key={v.label} variant={v} />
        ))}
      </Stack>

      {/* Salvar prompt */}
      <Box bg="blackAlpha.300" p={4} borderRadius="md" borderWidth={1} borderColor="gray.700">
        <HStack spacing={3} align="flex-start">
          <Input
            placeholder="Nota opcional (ex: 'pra tentar um funk com DJ Marky')"
            value={userNote}
            onChange={(e) => setUserNote(e.target.value)}
            isDisabled={isSaving || isSaved}
            maxLength={500}
            size="sm"
            flex={1}
          />
          <Button
            size="sm"
            colorScheme={isSaved ? "green" : "brand"}
            onClick={handleSave}
            isLoading={isSaving}
            loadingText="Salvando..."
            isDisabled={isSaved}
            minW="140px"
          >
            {isSaved ? "✓ Salvo" : "💾 Salvar prompt"}
          </Button>
        </HStack>
      </Box>

      <Divider />

      {/* Template de letras */}
      <Box>
        <HStack justify="space-between" mb={2}>
          <Heading size="sm">📝 Template para o campo Lyrics</Heading>
          <Button size="xs" onClick={copyLyrics}>
            {lyricsCopied ? "Copiado ✓" : "Copiar"}
          </Button>
        </HStack>
        <Textarea
          value={lyric_template}
          readOnly
          rows={lyric_template.split("\n").length}
          fontFamily="mono"
          fontSize="sm"
          bg="blackAlpha.500"
        />
      </Box>

      {/* Detalhes técnicos (DNA completo) */}
      <Accordion allowToggle>
        <AccordionItem border="none">
          <AccordionButton px={0}>
            <Box flex={1} textAlign="left">
              <Text fontWeight="bold" fontSize="sm">
                🔬 DNA técnico completo
              </Text>
            </Box>
            <AccordionIcon />
          </AccordionButton>
          <AccordionPanel pb={4} px={0}>
            <Code
              display="block"
              whiteSpace="pre-wrap"
              p={3}
              fontSize="xs"
              borderRadius="md"
            >
              {JSON.stringify(dna, null, 2)}
            </Code>
          </AccordionPanel>
        </AccordionItem>
      </Accordion>

      <Text fontSize="xs" color="gray.500" textAlign="center">
        {result.disclaimer}
      </Text>
    </VStack>
  );
}
