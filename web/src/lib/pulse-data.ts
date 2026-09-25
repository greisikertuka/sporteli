/** Synthetic, aggregate-only fixtures. Never present these as municipal records. */
export const departments = ["public", "urban", "social", "finance"] as const;
export type Department = (typeof departments)[number];
export type DepartmentFilter = Department | "all";
export type Period = "august" | "september";
export type Metrics = {
  received: number;
  resolved: number;
  onTime: number;
  overdue: number;
  onTimeRate: number;
};

const values: Record<
  Period,
  Record<Department, [number, number, number, number]>
> = {
  september: {
    public: [486, 420, 328, 28],
    urban: [312, 280, 246, 9],
    social: [264, 256, 249, 3],
    finance: [186, 180, 170, 2],
  },
  august: {
    public: [458, 390, 290, 16],
    urban: [300, 260, 217, 12],
    social: [250, 236, 221, 4],
    finance: [174, 162, 155, 2],
  },
};

export function getMetrics(
  department: DepartmentFilter,
  period: Period,
): Metrics {
  const entries =
    department === "all"
      ? Object.values(values[period])
      : [values[period][department]];
  const sums = entries.reduce<number[]>(
    (total, row) => total.map((n, i) => n + row[i]),
    [0, 0, 0, 0],
  );
  return {
    received: sums[0],
    resolved: sums[1],
    onTime: sums[2],
    overdue: sums[3],
    onTimeRate: sums[1] ? (sums[2] / sums[1]) * 100 : 0,
  };
}

export function getTrend(department: DepartmentFilter, period: Period) {
  // Allocate the rounding remainder to the last department so every filter reconciles.
  const portion = (total: number) => {
    if (department === "all") return total;
    const split = {
      public: Math.round(total * 0.39),
      urban: Math.round(total * 0.25),
      social: Math.round(total * 0.21),
      finance: 0,
    };
    split.finance = total - split.public - split.urban - split.social;
    return split[department];
  };
  const early = [
    [894, 830],
    [958, 881],
    [1040, 966],
    [990, 965],
  ].map(([received, resolved], i) => ({
    month: i + 4,
    received: portion(received),
    resolved: portion(resolved),
  }));
  const august = getMetrics(department, "august");
  const september = getMetrics(department, "september");
  return [
    ...early,
    { month: 8, received: august.received, resolved: august.resolved },
    ...(period === "september"
      ? [
          {
            month: 9,
            received: september.received,
            resolved: september.resolved,
          },
        ]
      : []),
  ];
}

export const sources = [
  {
    id: "public-requests",
    department: "public",
    filename: "sherbimet_publike_shtator.csv",
    rows: 486,
    updated: "2026-09-24",
    stale: false,
  },
  {
    id: "urban-requests",
    department: "urban",
    filename: "urbanistika_shtator.csv",
    rows: 312,
    updated: "2026-09-18",
    stale: true,
  },
  {
    id: "social-requests",
    department: "social",
    filename: "sherbimet_sociale_shtator.csv",
    rows: 264,
    updated: "2026-09-24",
    stale: false,
  },
  {
    id: "finance-requests",
    department: "finance",
    filename: "financa_shtator.csv",
    rows: 186,
    updated: "2026-09-24",
    stale: false,
  },
] as const;

export const SAMPLE_CSV =
  "request_id,department,status,created_at\nEP-001,public,open,2026-09-01\nEP-002,public,closed,2026-09-02\nEP-003,urban,open,2026-09-03\nEP-004,social,closed,2026-09-04\nEP-005,finance,closed,2026-09-05";

export function numberFormatter(locale: string, digits = 0) {
  // Explicit conventions avoid ICU locale-support differences during hydration.
  return {
    format(value: number) {
      const [integer, fraction] = value.toFixed(digits).split(".");
      const grouped = integer.replace(
        /\B(?=(\d{3})+(?!\d))/g,
        locale === "sq" ? "." : ",",
      );
      return (
        grouped + (fraction ? `${locale === "sq" ? "," : "."}${fraction}` : "")
      );
    },
  };
}

export function monthLabel(month: number, locale: string) {
  const labels =
    locale === "sq"
      ? [
          "jan",
          "shk",
          "mar",
          "pri",
          "maj",
          "qer",
          "korr",
          "gush",
          "sht",
          "tet",
          "nën",
          "dhj",
        ]
      : [
          "Jan",
          "Feb",
          "Mar",
          "Apr",
          "May",
          "Jun",
          "Jul",
          "Aug",
          "Sep",
          "Oct",
          "Nov",
          "Dec",
        ];
  return labels[month - 1];
}

export function formatSourceDate(isoDate: string, locale: string) {
  const [, month, day] = isoDate.split("-").map(Number);
  return `${day} ${monthLabel(month, locale)}`;
}
