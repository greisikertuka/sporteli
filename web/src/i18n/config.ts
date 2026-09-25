export const locales = ["sq", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "sq";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(value: string | undefined): value is Locale {
  return locales.includes(value as Locale);
}
