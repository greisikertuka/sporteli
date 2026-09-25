export type CsvPreview = { headers: string[]; rows: string[][] };
export type ColumnMapping = { id: number; department: number; status: number };
export const MAX_CSV_BYTES = 1_000_000;

/** Local, bounded RFC-4180-style comma-separated preview; nothing is transmitted. */
export function parseCsv(input: string): CsvPreview {
  if (new TextEncoder().encode(input).length > MAX_CSV_BYTES)
    throw new Error("size");
  const text = input.replace(/^\uFEFF/, "");
  const records: string[][] = [];
  let row: string[] = [],
    cell = "",
    quoted = false,
    afterQuote = false;
  const pushRow = () => {
    row.push(cell);
    cell = "";
    if (
      row.length > 1 ||
      row.some((value) => value.trim() !== "") ||
      afterQuote
    )
      records.push(row);
    row = [];
    afterQuote = false;
  };
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (char === '"') {
        quoted = false;
        afterQuote = true;
      } else cell += char;
    } else if (char === '"') {
      if (cell || afterQuote) throw new Error("format");
      quoted = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
      afterQuote = false;
    } else if (char === "\n" || char === "\r") {
      pushRow();
      if (char === "\r" && text[i + 1] === "\n") i++;
    } else {
      if (afterQuote) throw new Error("format");
      cell += char;
    }
  }
  if (quoted) throw new Error("format");
  if (cell || row.length || afterQuote) pushRow();
  if (records.length < 2) throw new Error("empty");
  const headers = records[0].map((value) => value.trim());
  if (
    headers.some((value) => !value) ||
    new Set(headers.map((value) => value.toLowerCase())).size !== headers.length
  )
    throw new Error("headers");
  const rows = records.slice(1);
  if (rows.some((record) => record.length !== headers.length))
    throw new Error("format");
  if (headers.length > 50 || rows.length > 10000) throw new Error("size");
  return { headers, rows };
}

export function validateMapping(
  mapping: ColumnMapping,
  columnCount: number,
): boolean {
  const indices = Object.values(mapping);
  return (
    indices.every(
      (index) => Number.isInteger(index) && index >= 0 && index < columnCount,
    ) && new Set(indices).size === 3
  );
}
