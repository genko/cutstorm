import { create } from "zustand";

export type FontCategory =
  | "display"
  | "sans"
  | "geometric"
  | "serif"
  | "handwritten"
  | "cjk";

export type FontEntry = {
  family: string;
  category: FontCategory;
  scripts: string[];
  url: string;
};

type FontStoreState = {
  fonts: FontEntry[];
  loaded: boolean;
};

export const useFontStore = create<FontStoreState>(() => ({
  fonts: [],
  loaded: false,
}));

export const CATEGORY_LABEL: Record<FontCategory, string> = {
  display: "Display",
  sans: "Sans",
  geometric: "Geometric",
  serif: "Serif",
  handwritten: "Handwritten",
  cjk: "CJK",
};

const CATEGORY_ORDER: FontCategory[] = [
  "display",
  "sans",
  "geometric",
  "serif",
  "handwritten",
  "cjk",
];

export function fontsByCategory(fonts: FontEntry[]): Array<{
  category: FontCategory;
  items: FontEntry[];
}> {
  const buckets = new Map<FontCategory, FontEntry[]>();
  for (const f of fonts) {
    if (!buckets.has(f.category)) buckets.set(f.category, []);
    buckets.get(f.category)!.push(f);
  }
  return CATEGORY_ORDER.filter((c) => buckets.has(c)).map((c) => ({
    category: c,
    items: (buckets.get(c) ?? []).sort((a, b) => a.family.localeCompare(b.family)),
  }));
}

async function register(entry: FontEntry): Promise<void> {
  try {
    const face = new FontFace(entry.family, `url(${entry.url})`);
    const loaded = await face.load();
    (document as any).fonts.add(loaded);
  } catch (err) {
    console.warn(`font.register failed family=${entry.family}`, err);
  }
}

export async function loadFonts(): Promise<void> {
  let list: FontEntry[] = [];
  try {
    const res = await fetch("/api/fonts");
    if (!res.ok) throw new Error(`fonts endpoint: ${res.status}`);
    const body = await res.json();
    list = (body.fonts ?? []) as FontEntry[];
  } catch (err) {
    console.warn("fonts.fetch failed — picker will be empty", err);
    useFontStore.setState({ fonts: [], loaded: true });
    return;
  }
  // Kick off parallel @font-face registration; don't block the UI on it.
  await Promise.all(list.map(register));
  useFontStore.setState({ fonts: list, loaded: true });
}
