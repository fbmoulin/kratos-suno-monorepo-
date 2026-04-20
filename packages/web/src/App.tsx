import {
  Alert,
  AlertDescription,
  AlertIcon,
  AlertTitle,
  Box,
  Button,
  CloseButton,
  Container,
  Heading,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Text,
  useToast,
  VStack,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { ApiHttpError, type GenerateResponse, type PromptSource } from "@kratos-suno/core";
import { api } from "./apiClient";
import { AudioUpload } from "./components/AudioUpload";
import { ResultsDisplay } from "./components/ResultsDisplay";
import { SavedPromptsList } from "./components/SavedPromptsList";
import { SpotifyTab } from "./components/SpotifyTab";
import { TextInput } from "./components/TextInput";
import { parseApiError } from "./lib/parseApiError";

interface ResultState {
  result: GenerateResponse;
  source: PromptSource;
}

export default function App() {
  const [state, setState] = useState<ResultState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [tabIndex, setTabIndex] = useState(0);
  const toast = useToast();

  // Detecta retorno do callback Spotify (?spotify=connected) e muda para a aba
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("spotify") === "connected") {
      setTabIndex(2); // índice da aba Spotify
      toast({
        title: "Spotify conectado!",
        status: "success",
        duration: 2500,
        isClosable: true,
      });
      // Limpa o query param da URL sem recarregar a página
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [toast]);

  const handleError = (err: unknown) => {
    const parsed = parseApiError(err);
    const requestId = err instanceof ApiHttpError ? err.requestId : undefined;
    toast({
      duration: 6000,
      isClosable: true,
      position: "top",
      render: ({ onClose }) => (
        <Alert
          status={parsed.status}
          variant="solid"
          borderRadius="md"
          alignItems="flex-start"
          pr={8}
          role="alert"
        >
          <AlertIcon />
          <Box flex="1">
            <AlertTitle>{parsed.title}</AlertTitle>
            <AlertDescription display="block" fontSize="sm">
              {parsed.description}
              {requestId && (
                <Text as="span" display="block" fontSize="xs" opacity={0.75} mt={1}>
                  ID: {requestId.slice(0, 8)}
                </Text>
              )}
            </AlertDescription>
            {parsed.action && (
              <Button
                mt={2}
                size="sm"
                colorScheme="whiteAlpha"
                onClick={() => {
                  parsed.action?.onClick();
                  onClose();
                }}
              >
                {parsed.action.label}
              </Button>
            )}
          </Box>
          <CloseButton
            position="absolute"
            right={1}
            top={1}
            onClick={onClose}
          />
        </Alert>
      ),
    });
  };

  const handleText = async (subject: string) => {
    setIsLoading(true);
    try {
      const result = await api.generateFromText({ subject });
      setState({ result, source: "text" });
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAudio = async (file: File, userHint?: string) => {
    setIsLoading(true);
    try {
      const result = await api.generateFromAudio(file, userHint);
      setState({ result, source: "audio" });
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  };

  // Quando o usuário escolhe um artista da aba Spotify, gera via fluxo /text
  // mas marca source como spotify_taste
  const handleSpotifyArtist = async (artistName: string) => {
    setIsLoading(true);
    try {
      const result = await api.generateFromText({ subject: artistName });
      setState({ result, source: "spotify_taste" });
    } catch (err) {
      handleError(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxW={{ base: "full", md: "3xl" }} px={{ base: 4, md: 0 }} py={{ base: 6, md: 10 }}>
      <VStack spacing={8} align="stretch">
        <Box textAlign="center">
          <Heading size={{ base: "lg", md: "xl" }} mb={2}>
            🎵 Kratos Suno Prompt
          </Heading>
          <Text color="gray.400" fontSize={{ base: "sm", md: "md" }}>
            Gere prompts profissionais para Suno AI a partir de nome, áudio ou seu Spotify
          </Text>
        </Box>

        {state ? (
          <ResultsDisplay
            result={state.result}
            source={state.source}
            onReset={() => setState(null)}
          />
        ) : (
          <Tabs
            variant="enclosed"
            colorScheme="brand"
            index={tabIndex}
            onChange={setTabIndex}
          >
            <TabList>
              <Tab>📝 Texto</Tab>
              <Tab>🎧 Áudio</Tab>
              <Tab>🎶 Meu Spotify</Tab>
              <Tab>💾 Salvos</Tab>
            </TabList>
            <TabPanels>
              <TabPanel px={0} py={6}>
                <TextInput onSubmit={handleText} isLoading={isLoading} />
              </TabPanel>
              <TabPanel px={0} py={6}>
                <AudioUpload onSubmit={handleAudio} isLoading={isLoading} />
              </TabPanel>
              <TabPanel px={0} py={6}>
                <SpotifyTab onChooseArtist={handleSpotifyArtist} />
              </TabPanel>
              <TabPanel px={0} py={6}>
                <SavedPromptsList />
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}

        <Text fontSize="xs" color="gray.500" textAlign="center">
          Os prompts respeitam o limite de 200 caracteres do Suno e não contêm
          nomes próprios protegidos por direitos autorais.
        </Text>
      </VStack>
    </Container>
  );
}
