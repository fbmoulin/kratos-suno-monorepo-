import {
  Alert,
  AlertIcon,
  Avatar,
  Badge,
  Box,
  Button,
  Center,
  Flex,
  HStack,
  Heading,
  Image,
  Select,
  Skeleton,
  SkeletonCircle,
  Stack,
  Tag,
  Text,
  VStack,
  Wrap,
  WrapItem,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import type { SpotifyArtist, SpotifyTimeRange, TasteProfile } from "@kratos-suno/core";
import { useAuth } from "@kratos-suno/core";
import { api } from "../apiClient";

interface Props {
  onChooseArtist: (artistName: string) => void;
}

const TIME_RANGE_LABELS: Record<SpotifyTimeRange, string> = {
  short_term: "Últimas 4 semanas",
  medium_term: "Últimos 6 meses",
  long_term: "Histórico longo",
};

export function SpotifyTab({ onChooseArtist }: Props) {
  const { auth, isLoading: authLoading, loginWithSpotify, logout } = useAuth({
    client: api,
    onOpenAuthUrl: (url) => {
      window.location.href = url;
    },
  });
  const [profile, setProfile] = useState<TasteProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<SpotifyTimeRange>("medium_term");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auth?.authenticated) {
      setProfile(null);
      return;
    }
    setProfileLoading(true);
    setError(null);
    api.getTasteProfile(timeRange)
      .then(setProfile)
      .catch((err) => setError(err.message))
      .finally(() => setProfileLoading(false));
  }, [auth?.authenticated, timeRange]);

  // Estado: carregando auth status inicial
  if (authLoading) {
    return (
      <Center py={10}>
        <Text color="gray.400">Verificando sessão...</Text>
      </Center>
    );
  }

  // Estado: não autenticado
  if (!auth?.authenticated) {
    return (
      <VStack spacing={6} py={8} textAlign="center">
        <Image
          src="https://storage.googleapis.com/pr-newsroom-wp/1/2018/11/Spotify_Logo_RGB_Green.png"
          alt="Spotify"
          maxH="48px"
          fallbackSrc=""
        />
        <Heading size="md">Conecte seu Spotify</Heading>
        <Text color="gray.400" maxW="md">
          Gere prompts Suno a partir dos artistas que você mais ouve.
          Usamos apenas leitura de top artists (escopo{" "}
          <code>user-top-read</code>), sem acesso a dados pessoais.
        </Text>
        <Button
          colorScheme="brand"
          size="lg"
          onClick={loginWithSpotify}
        >
          🎧 Conectar com Spotify
        </Button>
        <Text fontSize="xs" color="gray.500" maxW="md">
          ⚠️ Em abril/2026 o Spotify descontinuou os endpoints de audio-features
          e preview_url. Esta integração usa apenas dados de artistas e gêneros,
          não BPM nem prévia de áudio.
        </Text>
      </VStack>
    );
  }

  // Estado: autenticado
  return (
    <VStack spacing={5} align="stretch">
      <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
        <HStack>
          <Avatar size="sm" name={auth.display_name || undefined} />
          <Box>
            <Text fontSize="sm" color="gray.400">
              Conectado como
            </Text>
            <Text fontWeight="bold">
              {auth.display_name || auth.spotify_user_id}
            </Text>
          </Box>
        </HStack>
        <HStack>
          <Select
            size="sm"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as SpotifyTimeRange)}
            maxW="200px"
          >
            {Object.entries(TIME_RANGE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
          <Button size="sm" variant="outline" onClick={logout}>
            Desconectar
          </Button>
        </HStack>
      </Flex>

      {error && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          {error}
        </Alert>
      )}

      {/* Gêneros dominantes */}
      {profile && profile.dominant_genres.length > 0 && (
        <Box>
          <Heading size="xs" mb={2} color="gray.300">
            GÊNEROS DOMINANTES
          </Heading>
          <Wrap>
            {profile.dominant_genres.slice(0, 10).map((g) => (
              <WrapItem key={g}>
                <Tag colorScheme="brand" size="md">
                  {g}
                </Tag>
              </WrapItem>
            ))}
          </Wrap>
        </Box>
      )}

      {/* Top artists */}
      <Box>
        <Heading size="xs" mb={3} color="gray.300">
          SEUS TOP ARTISTAS — CLIQUE PARA GERAR PROMPT
        </Heading>
        {profileLoading ? (
          <Stack spacing={3}>
            {[1, 2, 3, 4].map((i) => (
              <HStack key={i}>
                <SkeletonCircle size="12" />
                <Skeleton h="12" flex={1} />
              </HStack>
            ))}
          </Stack>
        ) : profile ? (
          <Stack spacing={2}>
            {profile.top_artists.map((artist) => (
              <ArtistRow
                key={artist.spotify_id}
                artist={artist}
                onClick={() => onChooseArtist(artist.name)}
              />
            ))}
          </Stack>
        ) : null}
      </Box>
    </VStack>
  );
}

function ArtistRow({
  artist,
  onClick,
}: {
  artist: SpotifyArtist;
  onClick: () => void;
}) {
  return (
    <HStack
      p={3}
      borderRadius="md"
      bg="blackAlpha.400"
      cursor="pointer"
      _hover={{ bg: "blackAlpha.500", transform: "translateX(2px)" }}
      transition="all 0.15s"
      onClick={onClick}
    >
      <Avatar size="md" src={artist.image_url || undefined} name={artist.name} />
      <Box flex={1}>
        <Text fontWeight="bold">{artist.name}</Text>
        {artist.genres.length > 0 && (
          <Text fontSize="xs" color="gray.400" noOfLines={1}>
            {artist.genres.slice(0, 3).join(" · ")}
          </Text>
        )}
      </Box>
      <Badge colorScheme="brand" variant="outline">
        Gerar →
      </Badge>
    </HStack>
  );
}
