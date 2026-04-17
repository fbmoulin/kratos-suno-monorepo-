/**
 * Metadata das variantes — usada tanto no web (cores Chakra) quanto no
 * mobile (cores Paper/NativeWind). Valores genéricos, sem depender de lib.
 */

import type { SunoPromptVariant } from "../types";

export interface VariantMeta {
  label: string;
  emoji: string;
  description: string;
  /** Cor semântica (cada plataforma mapeia para seu design system). */
  semantic: "info" | "success" | "accent";
}

export const VARIANT_META: Record<SunoPromptVariant["label"], VariantMeta> = {
  conservative: {
    label: "Conservadora",
    emoji: "🛡️",
    description: "Máxima aderência ao gênero",
    semantic: "info",
  },
  faithful: {
    label: "Fiel",
    emoji: "🎯",
    description: "Equilibrada (recomendada)",
    semantic: "success",
  },
  creative: {
    label: "Criativa",
    emoji: "🎨",
    description: "Mais rica, pode surpreender",
    semantic: "accent",
  },
};

export function getVariantMeta(label: SunoPromptVariant["label"]): VariantMeta {
  return VARIANT_META[label];
}
