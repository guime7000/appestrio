import { ref } from "vue";

export type Theme = "light" | "dark";

const STORAGE_KEY = "appestrio-theme";

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function readStoredTheme(): Theme | null {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : null;
}

function applyTheme(next: Theme) {
  document.documentElement.setAttribute("data-theme", next);
}

const theme = ref<Theme>(readStoredTheme() ?? (systemPrefersDark() ? "dark" : "light"));
applyTheme(theme.value);

export function useTheme() {
  function setTheme(next: Theme) {
    theme.value = next;
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  function toggleTheme() {
    setTheme(theme.value === "dark" ? "light" : "dark");
  }

  return { theme, setTheme, toggleTheme };
}
