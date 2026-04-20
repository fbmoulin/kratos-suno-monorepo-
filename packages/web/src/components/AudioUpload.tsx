import {
  Box,
  Button,
  FormControl,
  FormHelperText,
  FormLabel,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";

interface Props {
  onSubmit: (file: File, userHint?: string) => void;
  isLoading: boolean;
}

const ACCEPTED = {
  "audio/mpeg": [".mp3"],
  "audio/wav": [".wav"],
  "audio/flac": [".flac"],
  "audio/mp4": [".m4a"],
  "audio/ogg": [".ogg"],
};

const MAX_SIZE_MB = 25;

export function AudioUpload({ onSubmit, isLoading }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [userHint, setUserHint] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError(null);
    const f = acceptedFiles[0];
    if (!f) return;
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Arquivo excede ${MAX_SIZE_MB}MB`);
      return;
    }
    setFile(f);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: false,
    disabled: isLoading,
  });

  const handleSubmit = () => {
    if (file) {
      onSubmit(file, userHint.trim() || undefined);
    }
  };

  return (
    <VStack spacing={4} align="stretch">
      <FormControl>
        <FormLabel>Arquivo de áudio</FormLabel>
        <Box
          {...getRootProps()}
          p={{ base: 4, md: 8 }}
          borderWidth={2}
          borderStyle="dashed"
          borderColor={isDragActive ? "brand.500" : "gray.500"}
          borderRadius="md"
          cursor="pointer"
          textAlign="center"
          bg={isDragActive ? "whiteAlpha.100" : "transparent"}
          _hover={{ borderColor: "brand.500" }}
          opacity={isLoading ? 0.5 : 1}
        >
          <input {...getInputProps()} />
          {file ? (
            <Text>
              <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(1)}MB)
            </Text>
          ) : isDragActive ? (
            <Text>Solte o arquivo aqui...</Text>
          ) : (
            <Text color="gray.400">
              Arraste um MP3/WAV/FLAC/M4A/OGG aqui, ou clique para escolher
            </Text>
          )}
        </Box>
        <FormHelperText>
          Máximo {MAX_SIZE_MB}MB. Análise dos primeiros 60 segundos.
        </FormHelperText>
        {error && (
          <Text color="red.400" fontSize="sm" mt={2}>
            {error}
          </Text>
        )}
      </FormControl>

      <FormControl>
        <FormLabel>Dica opcional</FormLabel>
        <Input
          value={userHint}
          onChange={(e) => setUserHint(e.target.value)}
          placeholder='Ex: "sertanejo universitário", "indie rock dos anos 2000"'
          isDisabled={isLoading}
        />
        <FormHelperText>
          Ajuda o modelo a interpretar corretamente gêneros regionais.
        </FormHelperText>
      </FormControl>

      <Button
        colorScheme="brand"
        size="lg"
        onClick={handleSubmit}
        isLoading={isLoading}
        loadingText="Analisando áudio..."
        isDisabled={!file}
      >
        Analisar e gerar prompts
      </Button>
    </VStack>
  );
}
