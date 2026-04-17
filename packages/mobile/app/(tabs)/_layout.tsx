import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { theme } from "@/src/theme";

type IoniconsName = React.ComponentProps<typeof Ionicons>["name"];

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.onSurfaceVariant,
        tabBarStyle: { backgroundColor: theme.colors.surface, borderTopWidth: 0 },
        headerStyle: { backgroundColor: theme.colors.background },
        headerTintColor: theme.colors.onSurface,
      }}
    >
      <Tabs.Screen
        name="text"
        options={{
          title: "Texto",
          tabBarIcon: iconFor("text-outline"),
        }}
      />
      <Tabs.Screen
        name="audio"
        options={{
          title: "Áudio",
          tabBarIcon: iconFor("musical-notes-outline"),
        }}
      />
      <Tabs.Screen
        name="spotify"
        options={{
          title: "Spotify",
          tabBarIcon: iconFor("logo-music-note-outline" as IoniconsName),
        }}
      />
      <Tabs.Screen
        name="saved"
        options={{
          title: "Salvos",
          tabBarIcon: iconFor("bookmark-outline"),
        }}
      />
    </Tabs>
  );
}

function iconFor(name: IoniconsName) {
  return ({ color, size }: { color: string; size: number }) => (
    <Ionicons name={name} size={size} color={color} />
  );
}
