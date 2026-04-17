/**
 * Tema Paper — dark mode com acentos brand (espelha o Chakra do web).
 */

import { MD3DarkTheme } from "react-native-paper";

export const theme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: "#1DB954",        // Spotify green (matching brand.500 do web)
    onPrimary: "#FFFFFF",
    primaryContainer: "#128c3b",
    secondary: "#9b59b6",
    background: "#0a0a0a",
    surface: "#151515",
    surfaceVariant: "#1e1e1e",
    onSurface: "#e0e0e0",
    onSurfaceVariant: "#a0a0a0",
    error: "#ff6b6b",
  },
};
