"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"

const languages = [
  { code: "en", label: "English" },
  { code: "zh", label: "简体中文" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "ja", label: "日本語" },
  { code: "pt-BR", label: "Português (BR)" },
]

export function LanguageSelector({
  currentLocale,
  label,
}: {
  currentLocale: string
  label: string
}) {
  const pathname = usePathname() ?? "/docs"
  const search = useSearchParams()
  const query = search?.toString() ? `?${search.toString()}` : ""

  return (
    <div className="flex flex-wrap gap-2 items-center text-xs font-semibold text-muted-foreground">
      <span className="uppercase tracking-[0.3em]">{label}</span>
      <div className="flex flex-wrap gap-1">
        {languages.map((language) => (
          <Link
            key={language.code}
            href={`${pathname}${query}`}
            locale={language.code}
            className={`px-3 py-1 rounded-full border transition-all ${
              currentLocale?.startsWith(language.code)
                ? "bg-primary text-background border-transparent"
                : "bg-background/80 border-border hover:border-primary hover:text-primary"
            }`}
          >
            {language.label}
          </Link>
        ))}
      </div>
    </div>
  )
}
