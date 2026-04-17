/**
 * Labels e emojis para a fonte do prompt — compartilhado web/mobile.
 */

import type { PromptSource } from "../types";

export const SOURCE_LABELS: Record<PromptSource, string> = {
  text: "📝 Texto",
  audio: "🎧 Áudio",
  spotify_taste: "🎶 Spotify",
};

export function getSourceLabel(source: PromptSource): string {
  return SOURCE_LABELS[source] ?? source;
}
