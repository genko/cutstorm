import { Word } from "./store";

// Single-char sentence terminators. Three-dot "..." ends on ".", so the
// last-char check catches it without a special case.
const SENTENCE_END = new Set([".", "?", "!", "…"]);

export function chunksBySentence(words: Word[], chunkSize: number): Word[][] {
  const n = Math.max(1, chunkSize);
  const out: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    const text = (w.text ?? "").replace(/\s+$/, "");
    const endsSentence =
      text.length > 0 && SENTENCE_END.has(text[text.length - 1]);
    if (endsSentence || cur.length >= n) {
      out.push(cur);
      cur = [];
    }
  }
  if (cur.length > 0) out.push(cur);
  return out;
}
