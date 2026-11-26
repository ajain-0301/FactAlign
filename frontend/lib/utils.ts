import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "—" : Number(v).toFixed(digits);

export const ms = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v < 1000 ? `${v.toFixed(v < 10 ? 1 : 0)} ms` : `${(v / 1000).toFixed(2)} s`;

export function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function countWords(text: string) {
  // Must mirror backend TOKEN_RE (numbers like "6.5" or "1,50,000" are a single word).
  const m = text.trim().match(/\d+(?:[.,]\d+)*|[\w\u0900-\u0963\u0966-\u097F]+/g);
  return m ? m.length : 0;
}

export function download(filename: string, content: string, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const LANG_LABEL: Record<string, string> = {
  auto: "Auto-detect", hi: "Hindi", en: "English", hinglish: "Hindi-English (code-mixed)", all: "All languages",
};
export const LANG_SHORT: Record<string, string> = { hi: "Hindi", en: "English", hinglish: "Hinglish" };
export const STRATEGY_LABEL: Record<string, string> = { standard: "Standard", factuality: "Factuality-aware" };

export function languageBucket(language: string) {
  const normalized = language.trim().toLowerCase();
  return normalized === "en" || normalized === "english" || normalized === "hinglish"
    ? "hinglish"
    : language;
}
