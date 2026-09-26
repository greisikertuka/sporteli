/**
 * REPLAY fixture for the SMP 2024 Annex A coverage pack (al_smp, contract §3).
 *
 * Honesty note: the official Albanian names of the 52 indicators live in the API's
 * `al_smp.yaml`. This offline snapshot does NOT reproduce them: mapped items carry
 * the name of our own passport, the rest a neutral placeholder, and every item says
 * so in its note. The state classification follows the contract exactly.
 */
import type { Coverage, CoverageItem, IndicatorState, L10n } from "../api";
import { countCoverage } from "../labels.ts";

const AREA_1: L10n = { sq: "Aneksi A · treguesit 1–40", en: "Annex A · indicators 1–40" };
const AREA_2: L10n = {
  sq: "Aneksi A · financat vendore (41–52)",
  en: "Annex A · local finance (41–52)",
};

const COMPUTABLE: Record<number, { code: string; name: string }> = {
  13: { code: "REV-02", name: "Mbulimi i kostos së mbetjeve nga tarifa" },
  14: { code: "WST-02", name: "Mbetje për banor (kg/banor/vit)" },
  15: { code: "WST-03", name: "Kosto për ton mbetje" },
  23: { code: "HR-02", name: "Shkalla e rotacionit të punonjësve" },
  25: { code: "HR-01", name: "Punonjës për 1.000 banorë" },
};
const DOCUMENT = new Set([5, 16, 22, 26, 27, 28, 30, 31, 35, 40]);

const OFFICIAL_NAME_NOTE: L10n = {
  sq: "Emri zyrtar i Aneksit A shfaqet kur API është aktive (paketa al_smp).",
  en: "The official Annex A name is shown when the API is live (al_smp pack).",
};

function item(number: number): CoverageItem {
  if (number >= 41) {
    return {
      number,
      area: AREA_2,
      name_sq: `Treguesi financiar #${number}`,
      state: "national",
      passport_code: null,
      owner: null,
      note: {
        sq: "Burimi: Ministria e Financave, llogaritur nga AMVV. Sportel nuk e llogarit.",
        en: "Source: Ministry of Finance, computed by AMVV. Sportel does not compute it.",
      },
    };
  }
  const mapped = COMPUTABLE[number];
  if (mapped) {
    return {
      number,
      area: AREA_1,
      name_sq: mapped.name,
      state: "computable",
      passport_code: mapped.code,
      owner: null,
      note: {
        sq: `Llogaritet nga pasaporta ${mapped.code} kur eksportet e nevojshme janë ngarkuar.`,
        en: `Computed by passport ${mapped.code} once the required exports are loaded.`,
      },
    };
  }
  if (DOCUMENT.has(number)) {
    return {
      number,
      area: AREA_1,
      name_sq: `Treguesi #${number} · kontroll dokumenti`,
      state: "document",
      passport_code: null,
      owner: { sq: "Sektori i Statistikës dhe Performancës", en: "Statistics and Performance Sector" },
      note: {
        sq: "Kontroll: plani ose publikimi ekziston (lidhje + konfirmim nga një person).",
        en: "Check: the plan or publication exists (link + a person's confirmation).",
      },
    };
  }
  return {
    number,
    area: AREA_1,
    name_sq: `Treguesi #${number}`,
    state: "missing",
    passport_code: null,
    owner: null,
    note: OFFICIAL_NAME_NOTE,
  };
}

export function buildCoverage(): Coverage {
  const items = Array.from({ length: 52 }, (_, i) => item(i + 1));
  const { counts, total } = countCoverage(items);
  return {
    pack: "al_smp",
    label: { sq: "SMP 2024 · Aneksi A", en: "SMP 2024 · Annex A" },
    approval: "pending",
    counts: counts as Record<IndicatorState, number>,
    total,
    items,
  };
}
