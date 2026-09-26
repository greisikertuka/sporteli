/**
 * Deterministic synthetic source rows for REPLAY lineage tables.
 * Values are SYNTHETIC and only illustrate the shape of the canonical tables.
 */
import { POPULATION, type DatasetKey } from "./catalog.ts";

export const ADMIN_UNITS = [
  "Elbasan",
  "Bradashesh",
  "Funarë",
  "Gjergjan",
  "Gjinar",
  "Gracen",
  "Labinot-Fushë",
  "Labinot-Mal",
  "Papër",
  "Shirgjan",
  "Shushicë",
  "Tregan",
  "Zavalinë",
];

/** Synthetic census_2023 basis per unit; sums to POPULATION.census_2023. */
export const CENSUS_BY_UNIT = [80560, 5210, 1380, 2940, 1120, 1730, 5860, 1950, 4620, 4480, 5070, 2690, 3790];

export function populationByUnit(basis: "census_2023" | "civil_registry"): number[] {
  if (basis === "census_2023") return CENSUS_BY_UNIT;
  const factor = POPULATION.civil_registry / POPULATION.census_2023;
  const scaled = CENSUS_BY_UNIT.map((v) => Math.round(v * factor));
  const diff = POPULATION.civil_registry - scaled.reduce((a, b) => a + b, 0);
  scaled[0] += diff;
  return scaled;
}

export const PROGRAMMES: [string, string][] = [
  ["01110", "Planifikim, menaxhim dhe administrim"],
  ["03140", "Mbrojtja civile"],
  ["04520", "Rrugët rurale"],
  ["05100", "Menaxhimi i mbetjeve"],
  ["06200", "Planifikimi urban"],
  ["06440", "Ndriçimi publik"],
  ["08130", "Sporti dhe argëtimi"],
  ["09120", "Arsimi bazë"],
  ["10400", "Kujdesi social për familjet dhe fëmijët"],
];

export const REVENUE_TYPES = [
  "Taksa e ndërtesës",
  "Tarifa e pastrimit",
  "Taksa e ndikimit në infrastrukturë",
  "Taksa e truallit",
  "Gjoba",
  "Qira",
];

export const DIRECTORATES: [string, number, number, number][] = [
  // [synthetic directorate, headcount 31.08.2026, hires 2026, leavers 2026]
  ["Shërbimet Publike", 312, 21, 17],
  ["Financa dhe Buxheti", 64, 4, 3],
  ["Të Ardhurat Vendore", 58, 5, 4],
  ["Burimet Njerëzore", 41, 2, 2],
  ["Planifikimi Urban", 97, 7, 6],
  ["Arsimi dhe Kultura", 186, 12, 10],
  ["Policia Bashkiake", 142, 10, 8],
  ["Shërbimet Sociale", 88, 6, 5],
  ["Kabineti dhe Administrata", 58, 4, 3],
];

const CATEGORIES = [
  "Ndriçim publik",
  "Rrugë dhe trotuare",
  "Pastrim",
  "Gjelbërim",
  "Ujë dhe kanalizime",
  "Leje dhe dokumente",
];
const DEPARTMENTS = ["Shërbimet Publike", "Punët Publike", "Planifikimi Urban", "Shërbimet Sociale"];
const CHANNELS = ["Sportel", "Telefon", "Online", "E-mail"];

/** mulberry32: small deterministic PRNG. */
export function prng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const pad = (n: number) => String(n).padStart(2, "0");

export type Row = { row_no: number; values: Record<string, string | number | null> };

/** Canonical rows for one dataset, starting at the first data row of the file. */
export function datasetRows(dataset: DatasetKey, limit: number, opts: { month?: number; startRow?: number } = {}): Row[] {
  const rand = prng(dataset.length * 7919 + (opts.month ?? 8) * 31 + (opts.startRow ?? 0));
  const out: Row[] = [];
  const pickOf = <T,>(list: T[]) => list[Math.floor(rand() * list.length)];
  switch (dataset) {
    case "requests": {
      const start = opts.startRow ?? 2071;
      for (let i = 0; i < limit; i++) {
        const createdDay = 1 + Math.floor(rand() * 25);
        const createdMonth = createdDay > 20 ? 7 : 8;
        const sla = pickOf([5, 10, 10, 15, 20]);
        const took = Math.max(1, Math.round(sla * (0.3 + rand() * 1.1)));
        const closedDay = Math.min(31, createdDay + took - (createdMonth === 7 ? 20 : 0));
        out.push({
          row_no: start + i * 3 + Math.floor(rand() * 3),
          values: {
            request_id: `K-2026-${String(start + i * 3 - 3).padStart(5, "0")}`,
            created_at: `2026-${pad(createdMonth)}-${pad(createdDay)}`,
            closed_at: `2026-08-${pad(Math.max(1, closedDay))}`,
            category: pickOf(CATEGORIES),
            department: pickOf(DEPARTMENTS),
            admin_unit: pickOf(ADMIN_UNITS.slice(0, 6)),
            channel: pickOf(CHANNELS),
            status: "closed",
            sla_days: sla,
          },
        });
      }
      return out;
    }
    case "budget": {
      const start = opts.startRow ?? 4;
      let r = start;
      for (let m = 1; m <= 8 && out.length < limit; m++) {
        for (const [code, name] of PROGRAMMES) {
          for (const type of ["current", "capital"]) {
            if (out.length >= limit) break;
            const planned = Math.round((8 + rand() * 40) * 1_000_000);
            const ratio = type === "capital" ? 0.25 + rand() * 0.25 : 0.85 + rand() * 0.12;
            out.push({
              row_no: r++,
              values: {
                month: `2026-${pad(m)}-01`,
                programme_code: code,
                programme: name,
                line_type: type,
                planned_lek: planned,
                actual_lek: Math.round(planned * ratio),
              },
            });
          }
        }
      }
      return out;
    }
    case "waste": {
      const start = opts.startRow ?? 93;
      const month = opts.month ?? 8;
      const shares = CENSUS_BY_UNIT.map((v) => v / POPULATION.census_2023);
      ADMIN_UNITS.slice(0, limit).forEach((unit, i) => {
        const tonnes = unit === "Gjinar" && month === 7 ? 0 : Math.round(3712 * shares[i] * (0.9 + rand() * 0.2) * 10) / 10;
        out.push({
          row_no: start + i,
          values: {
            month: `2026-${pad(month)}-01`,
            admin_unit: unit,
            tonnes,
            trips: Math.max(4, Math.round(tonnes / 6.5)),
            households_served: Math.round(CENSUS_BY_UNIT[i] / 3.4),
          },
        });
      });
      return out;
    }
    case "revenue": {
      const start = opts.startRow ?? 4;
      let r = start;
      for (let m = 1; m <= 8 && out.length < limit; m++) {
        for (const type of REVENUE_TYPES) {
          for (const payer of ["Familje", "Biznes"]) {
            if (out.length >= limit) break;
            const planned = Math.round((3 + rand() * 30) * 1_000_000);
            out.push({
              row_no: r++,
              values: {
                month: `2026-${pad(m)}-01`,
                revenue_type: type,
                payer_type: payer,
                planned_lek: planned,
                collected_lek: Math.round(planned * (0.65 + rand() * 0.3)),
              },
            });
          }
        }
      }
      return out;
    }
    case "staff": {
      const start = opts.startRow ?? 4;
      DIRECTORATES.slice(0, limit).forEach(([name, headcount, hires, leavers], i) => {
        out.push({
          row_no: start + i,
          values: { department: name, headcount, hires, leavers, as_of: "2026-08-31" },
        });
      });
      return out;
    }
    case "population": {
      const start = opts.startRow ?? 2;
      ADMIN_UNITS.slice(0, limit).forEach((unit, i) => {
        out.push({
          row_no: start + i,
          values: { admin_unit: unit, basis: "census_2023", residents: CENSUS_BY_UNIT[i] },
        });
      });
      return out;
    }
  }
}
