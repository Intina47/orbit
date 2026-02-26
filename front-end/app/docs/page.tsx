import Link from "next/link"
import { cookies, headers } from "next/headers"
import { CodeBlock } from "@/components/orbit/code-block"
import { LanguageSelector } from "@/components/language-selector"
import { getDocsTranslation } from "@/locales/docs"

function detectLocale() {
  const localeFromCookie = cookies().get("NEXT_LOCALE")?.value
  const localeFromHeader = headers().get("x-next-locale")
  return localeFromCookie ?? localeFromHeader ?? "en"
}

export default function DocsOverview() {
  const locale = detectLocale()
  const translation = getDocsTranslation(locale)

  return (
    <div>
      {/* Header */}
      <div className="mb-16">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-px bg-primary" />
          <span className="text-primary text-xs tracking-[0.3em] uppercase text-glow-sm">
            Documentation
          </span>
        </div>
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-4xl md:text-5xl font-bold text-foreground tracking-tight mb-3">
              {translation.headerTitle}
            </h1>
            <p className="text-muted-foreground text-base md:text-lg leading-relaxed max-w-xl">
              {translation.headerDescription}
            </p>
          </div>
          <LanguageSelector currentLocale={locale} label={translation.languageSelectorLabel} />
        </div>
      </div>

      {/* Quick install */}
      <div className="border border-border mb-16">
        <div className="bg-secondary px-4 py-2 border-b border-border">
          <span className="text-xs text-muted-foreground">{translation.quickInstallTitle}</span>
        </div>
        <div className="p-4">
          <code className="text-primary text-sm">{translation.quickInstallCommand}</code>
        </div>
      </div>

      <div className="border border-primary/30 bg-primary/5 p-6 mb-12 rounded-3xl shadow-[0_0_60px_rgba(255,255,255,0.08)]">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">{translation.labTitle}</p>
            <p className="text-sm text-foreground font-semibold">{translation.labSubtitle}</p>
          </div>
          <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs">{translation.labBadge}</span>
        </div>
        <p className="text-xs text-muted-foreground mb-4">{translation.labDescription}</p>
        <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground mb-2">{translation.promptLabel}</p>
        <CodeBlock code={`Prompt blueprint:\n${translation.promptExample}\n`} language="text" filename="prompt.txt" />
        <p className="text-xs text-muted-foreground mt-4">{translation.promptFooter}</p>
      </div>

      {/* Section grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border">
        {translation.sections.map((section) => (
          <div key={section.title} className="bg-background p-8">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-4 h-px bg-primary" />
              <h2 className="text-xs tracking-[0.3em] uppercase text-muted-foreground font-bold">{section.title}</h2>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-6">{section.description}</p>
            <div className="space-y-2">
              {section.links.map((link) => (
                <Link key={link.href} href={link.href} className="flex items-center gap-2 text-sm text-foreground hover:text-primary transition-colors group">
                  <span className="text-muted-foreground group-hover:text-primary transition-colors">{">"}</span>
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
