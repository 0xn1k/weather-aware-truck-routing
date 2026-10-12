import { create } from "zustand";
import { applyTheme, getStoredTheme, type Theme } from "@/lib/theme";

interface UiState {
  theme: Theme;
  toggleTheme: () => void;

  selectedRouteId: string | null;
  setSelectedRouteId: (id: string | null) => void;

  sliderHour: number;
  setSliderHour: (hour: number) => void;
  isPlaying: boolean;
  togglePlaying: () => void;

  detailsModalRouteId: string | null;
  openDetails: (id: string) => void;
  closeDetails: () => void;

  // Trip details sidebar: full form vs collapsed to a compact read-only
  // summary + "Edit trip" button, so the map/results can use the freed
  // width (App.tsx). Collapsing is only offered once a trip has actually
  // been planned — before that there's nothing to summarize.
  formExpanded: boolean;
  setFormExpanded: (expanded: boolean) => void;
}

const initialTheme = getStoredTheme();
applyTheme(initialTheme);

export const useUiStore = create<UiState>((set, get) => ({
  theme: initialTheme,
  toggleTheme: () => {
    const next = get().theme === "light" ? "dark" : "light";
    applyTheme(next);
    set({ theme: next });
  },

  selectedRouteId: null,
  setSelectedRouteId: (id) => set({ selectedRouteId: id }),

  sliderHour: 0,
  setSliderHour: (hour) => set({ sliderHour: Math.max(0, Math.min(48, hour)) }),
  isPlaying: false,
  togglePlaying: () => set({ isPlaying: !get().isPlaying }),

  detailsModalRouteId: null,
  openDetails: (id) => set({ detailsModalRouteId: id }),
  closeDetails: () => set({ detailsModalRouteId: null }),

  formExpanded: true,
  setFormExpanded: (expanded) => set({ formExpanded: expanded }),
}));
