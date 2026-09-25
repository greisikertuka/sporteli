import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { defaultLocale, isLocale, LOCALE_COOKIE } from "./config";

export default getRequestConfig(async ({ locale: requestedLocale }) => {
  const stored = (await cookies()).get(LOCALE_COOKIE)?.value;
  const locale = isLocale(requestedLocale)
    ? requestedLocale
    : isLocale(stored)
      ? stored
      : defaultLocale;
  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
