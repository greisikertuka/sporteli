/**
 * REPLAY routing for free-text questions (the example chips carry their own id).
 *
 * Offline there is no model and no sandbox, so a typed question can only be routed to a
 * passport whose recorded answer exists, refused like the API refuses it, or answered
 * "not answerable" with the API's own recorded "try an example question" reply. The label
 * of the answer is always the one the live API recorded; nothing is composed here.
 */
import { SNAPSHOT } from "./snapshot.ts";

export type Route =
  | { kind: "passport"; code: string }
  | { kind: "blocked" }
  | { kind: "write" }
  | { kind: "none" };

const normalise = (text: string) =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[^a-z0-9.,\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/** Statements the guard refuses outright (contract §6: writes, DDL, table functions). */
const WRITE = /^\s*(delete|drop|update|insert|alter|truncate|create|attach|copy|pragma)\b/i;

/** Requests for individual-level personal data. */
const PERSONAL = [/\bemr(at|i|in)\b/, /\btelefon/, /\bnames?\b/, /\bphones?\b/, /\be-?mail/, /\bnumr(i|in|at) personal/, /\badres/];

/** Extra phrasings per passport, on top of its canonical question (sq and en). */
const KEYWORDS: Record<string, string[]> = {
  "REQ-01": ["pranuan", "pranuara", "regjistruan", "received", "how many requests"],
  "REQ-02": ["brenda afatit", "on time", "within the deadline", "within deadline"],
  "REQ-03": ["afat te kaluar", "vonuara", "overdue", "past deadline", "past their deadline"],
  "REQ-04": ["koha mesatare", "sa dite", "average resolution", "resolution time", "how many days"],
  "FIN-01": ["zbatimi i buxhetit", "buxhet", "budget execution", "budget"],
  "FIN-02": ["investim", "kapitale", "capital", "investment"],
  "WST-01": ["ton mbetje", "mbetje", "grumbulluan", "waste collected", "tonnes"],
  "WST-02": ["per banor", "kg", "per resident", "per capita"],
  "WST-03": ["kosto per ton", "kushton", "cost per tonne", "cost per ton"],
  "REV-01": ["arketuar", "arketimi", "taksa", "taxes", "fees collected", "revenue"],
  "REV-02": ["mbulon", "mbulimi", "tarifa e pastrimit", "cleaning fee", "cost coverage", "covers"],
  "HR-01": ["punonjes", "1.000 banore", "staff per", "employees", "1,000 residents"],
  "HR-02": ["rotacion", "largime", "turnover", "leavers"],
};

const STOP = new Set(
  "sa si cili cila cilat eshte jane ne te e i per nga me dhe se u a ka kane what how many much is are the of in to for by and does do".split(" "),
);
const tokens = (text: string) => normalise(text).split(/[\s.,-]+/).filter((t) => t.length > 2 && !STOP.has(t));

export function routeQuestion(question: string): Route {
  if (WRITE.test(question)) return { kind: "write" };
  const text = normalise(question);
  if (!text) return { kind: "none" };
  if (PERSONAL.some((p) => p.test(text))) return { kind: "blocked" };

  const example = SNAPSHOT.examples.find(
    (e) => e.passport_code && (normalise(e.question.sq) === text || normalise(e.question.en) === text),
  );
  if (example?.passport_code) return { kind: "passport", code: example.passport_code };

  const words = new Set(tokens(question));
  let best: { code: string; score: number } | null = null;
  for (const [code, passport] of Object.entries(SNAPSHOT.passports.full)) {
    const phrase = (KEYWORDS[code] ?? []).reduce((s, k) => (text.includes(normalise(k)) ? s + normalise(k).length : s), 0);
    const overlap = [...new Set([...tokens(passport.question.sq), ...tokens(passport.question.en)])].filter((w) => words.has(w)).length;
    const score = phrase + overlap * 3;
    if (score > 0 && (!best || score > best.score)) best = { code, score };
  }
  return best && best.score >= 4 ? { kind: "passport", code: best.code } : { kind: "none" };
}
