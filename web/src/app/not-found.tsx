import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <div className="not-found">
      <p className="kicker">404</p>
      <h1 className="display-title">{t("title")}</h1>
      <p className="page-description">{t("body")}</p>
      <Link className="civic-button primary" href="/">
        {t("home")}
      </Link>
    </div>
  );
}
