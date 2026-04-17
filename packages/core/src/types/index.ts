// Types espelhando backend/app/schemas/sonic_dna.py

export type VariantLabel = "conservative" | "faithful" | "creative";
export type VocalGender = "male" | "female" | "mixed" | "instrumental";
export type SubjectType = "artist" | "band" | "song";

export interface SonicDNA {
  subject: string;
  subject_type: SubjectType;
  era: string;
  genre_primary: string;
  genre_secondary: string | null;
  bpm_min: number;
  bpm_max: number;
  bpm_typical: number;
  mood_primary: string;
  mood_secondary: string | null;
  instruments: string[];
  vocal_gender: VocalGender;
  vocal_timbre: string | null;
  vocal_delivery: string | null;
  production_palette: string[];
  articulation_score: number;
  forbidden_terms: string[];
}

export interface SunoPromptVariant {
  label: VariantLabel;
  prompt: string;
  char_count: number;
  tags_count: number;
}

export interface GenerateResponse {
  subject: string;
  sonic_dna: SonicDNA;
  variants: SunoPromptVariant[];
  lyric_template: string;
  disclaimer: string;
}

export interface GenerateTextRequest {
  subject: string;
  variants_to_generate?: number;
  language_hint?: string;
}

export interface ApiError {
  detail: string;
}

// --- Fase 3: Spotify + Saved Prompts ---

export interface SpotifyArtist {
  spotify_id: string;
  name: string;
  genres: string[];
  image_url: string | null;
}

export type SpotifyTimeRange = "short_term" | "medium_term" | "long_term";

export interface TasteProfile {
  top_artists: SpotifyArtist[];
  dominant_genres: string[];
  time_range: SpotifyTimeRange;
}

export interface AuthStatus {
  authenticated: boolean;
  spotify_user_id: string | null;
  display_name: string | null;
  expires_at: string | null;
}

export interface SpotifyAuthURL {
  authorize_url: string;
  state: string;
}

export type PromptSource = "text" | "audio" | "spotify_taste";

export interface SavedPromptCreate {
  subject: string;
  source: PromptSource;
  sonic_dna: SonicDNA;
  variants: SunoPromptVariant[];
  lyric_template: string;
  user_note?: string;
}

export interface SavedPrompt {
  id: number;
  subject: string;
  source: PromptSource;
  sonic_dna: SonicDNA;
  variants: SunoPromptVariant[];
  lyric_template: string;
  user_note: string | null;
  created_at: string;
}

export interface SavedPromptList {
  items: SavedPrompt[];
  total: number;
}
