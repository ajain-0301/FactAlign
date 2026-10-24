"use client";
import * as React from "react";
import { api } from "@/lib/api";
import type { Health, SettingsState } from "@/lib/types";

interface AppCtx {
  health: Health | null;
  settings: SettingsState | null;
  backendDown: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
  setSettings: (s: SettingsState) => void;
}
const Ctx = React.createContext<AppCtx>({
  health: null, settings: null, backendDown: false, loading: true, refresh: async () => {}, setSettings: () => {},
});
export const useApp = () => React.useContext(Ctx);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [settings, setSettings] = React.useState<SettingsState | null>(null);
  const [backendDown, setDown] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const [h, s] = await Promise.all([api.health(), api.settings()]);
      setHealth(h);
      setSettings(s);
      setDown(false);
    } catch {
      setDown(true);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const t = setInterval(() => api.health().then((h) => { setHealth(h); setDown(false); }).catch(() => setDown(true)), 30000);
    return () => clearInterval(t);
  }, [refresh]);

  return <Ctx.Provider value={{ health, settings, backendDown, loading, refresh, setSettings }}>{children}</Ctx.Provider>;
}
