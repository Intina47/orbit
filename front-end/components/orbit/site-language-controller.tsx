"use client"

import { useEffect, useMemo, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

const COOKIE_NAME = "ORBIT_SITE_LANG"

type Language = {
  code: string
  label: string
}

const LANGUAGES: Language[] = [
  { code: "en", label: "English" },
  { code: "zh", label: "简体中文" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "ja", label: "日本語" },
  { code: "pt-BR", label: "Português (BR)" },
]

const ORIGINAL_TEXT = new WeakMap<Text, string>()
const TRANSLATION_CACHE = new Map<string, string>()

const tagBlacklist = new Set([
  "CODE",
  "PRE",
  "SCRIPT",
  "STYLE",
  "NOSCRIPT",
  "TEXTAREA",
  "INPUT",
  "OPTION",
  "SVG",
])

function normalizeLang(raw: string | null | undefined): string {
  if (!raw) {
    return "en"
  }
  const lower = raw.toLowerCase()
  if (lower.startsWith("zh")) {
    return "zh"
  }
  if (lower.startsWith("es")) {
    return "es"
  }
  if (lower.startsWith("de")) {
    return "de"
  }
  if (lower.startsWith("ja")) {
    return "ja"
  }
  if (lower === "pt-br" || lower === "pt_br" || lower.startsWith("pt")) {
    return "pt-BR"
  }
  return "en"
}

function setLangCookie(lang: string) {
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(lang)}; Path=/; Max-Age=31536000; SameSite=Lax`
}

function getLangFromCookie(): string | null {
  const raw = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((item) => item.startsWith(`${COOKIE_NAME}=`))
  if (!raw) {
    return null
  }
  return decodeURIComponent(raw.split("=")[1] ?? "")
}

function shouldTranslateText(value: string): boolean {
  if (!value.trim()) {
    return false
  }
  if (value.length > 300) {
    return false
  }
  if (value.includes("orbit_pk_") || value.includes("sk-")) {
    return false
  }
  if (/^[a-f0-9-]{32,}$/i.test(value.trim())) {
    return false
  }
  if (/^[A-Za-z0-9+/_=-]{24,}$/.test(value.trim())) {
    return false
  }
  return true
}

function collectTextNodes(root: HTMLElement): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const output: Text[] = []
  let current = walker.nextNode()
  while (current) {
    if (current.nodeType === Node.TEXT_NODE) {
      const textNode = current as Text
      const value = textNode.textContent?.trim() ?? ""
      const parent = textNode.parentElement
      if (
        value &&
        shouldTranslateText(value) &&
        parent &&
        !tagBlacklist.has(parent.tagName) &&
        !parent.closest("[data-no-translate]")
      ) {
        output.push(textNode)
      }
    }
    current = walker.nextNode()
  }
  return output
}

async function translateText(text: string, lang: string): Promise<string> {
  const cacheKey = `${lang}::${text}`
  const cached = TRANSLATION_CACHE.get(cacheKey)
  if (cached) {
    return cached
  }
  const url = new URL("https://translate.googleapis.com/translate_a/single")
  url.searchParams.set("client", "gtx")
  url.searchParams.set("sl", "en")
  url.searchParams.set("tl", lang)
  url.searchParams.set("dt", "t")
  url.searchParams.set("q", text)
  const response = await fetch(url.toString())
  if (!response.ok) {
    throw new Error(`translate_request_failed:${response.status}`)
  }
  const payload = (await response.json()) as unknown[]
  const parts = Array.isArray(payload[0]) ? payload[0] : []
  const translated = parts
    .map((item) => (Array.isArray(item) && typeof item[0] === "string" ? item[0] : ""))
    .join("")
    .trim()
  const value = translated || text
  TRANSLATION_CACHE.set(cacheKey, value)
  return value
}

function SiteLanguageSelector({
  lang,
  onSelect,
}: {
  lang: string
  onSelect: (nextLang: string) => void
}) {
  return (
    <div className="fixed right-4 top-[76px] z-40 md:right-8">
      <div className="border border-border bg-background/95 backdrop-blur px-3 py-2 rounded-xl shadow-lg" data-no-translate>
        <label htmlFor="site-lang-picker" className="block text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
          Language
        </label>
        <select
          id="site-lang-picker"
          value={lang}
          onChange={(event) => onSelect(event.target.value)}
          className="text-xs bg-background border border-border rounded-md px-2 py-1 text-foreground"
        >
          {LANGUAGES.map((language) => (
            <option key={language.code} value={language.code}>
              {language.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

export function SiteLanguageController() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [activeLang, setActiveLang] = useState("en")

  const queryLang = useMemo(() => normalizeLang(searchParams?.get("lang")), [searchParams])

  useEffect(() => {
    const cookieLang = normalizeLang(getLangFromCookie())
    const initial = queryLang !== "en" ? queryLang : cookieLang
    setActiveLang(initial)
  }, [queryLang])

  useEffect(() => {
    setLangCookie(activeLang)
  }, [activeLang])

  useEffect(() => {
    const root = document.querySelector<HTMLElement>("[data-site-root]")
    if (!root) {
      return
    }
    const textNodes = collectTextNodes(root)
    for (const node of textNodes) {
      if (!ORIGINAL_TEXT.has(node)) {
        ORIGINAL_TEXT.set(node, node.textContent ?? "")
      }
    }
    if (activeLang === "en") {
      for (const node of textNodes) {
        const original = ORIGINAL_TEXT.get(node)
        if (typeof original === "string") {
          node.textContent = original
        }
      }
      return
    }
    let cancelled = false
    const run = async () => {
      for (const node of textNodes) {
        if (cancelled) {
          return
        }
        const original = ORIGINAL_TEXT.get(node)
        if (!original || !original.trim()) {
          continue
        }
        try {
          const translated = await translateText(original, activeLang)
          if (!cancelled) {
            node.textContent = translated
          }
        } catch {
          if (!cancelled) {
            node.textContent = original
          }
        }
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [activeLang, pathname])

  const onSelect = (nextLang: string) => {
    const normalized = normalizeLang(nextLang)
    setActiveLang(normalized)
    const params = new URLSearchParams(searchParams?.toString() ?? "")
    if (normalized === "en") {
      params.delete("lang")
    } else {
      params.set("lang", normalized)
    }
    const query = params.toString()
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false })
  }

  return <SiteLanguageSelector lang={activeLang} onSelect={onSelect} />
}
