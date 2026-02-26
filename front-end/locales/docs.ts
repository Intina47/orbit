export type DocsLocale = "en" | "zh" | "es" | "de" | "ja" | "pt-BR"

type SectionLink = {
  label: string
  href: string
}

type SectionDefinition = {
  title: string
  description: string
  links: SectionLink[]
}

export type DocsTranslation = {
  headerTitle: string
  headerDescription: string
  quickInstallTitle: string
  quickInstallCommand: string
  labBadge: string
  labSubtitle: string
  labTitle: string
  labDescription: string
  promptLabel: string
  promptExample: string
  promptFooter: string
  languageSelectorLabel: string
  sections: SectionDefinition[]
}

const baseSections: SectionDefinition[] = [
  {
    title: "Getting Started",
    description:
      "Pick Cloud vs Self-Hosted setup, install Orbit, and run your first end-to-end memory loop in minutes.",
    links: [
      { label: "Quickstart", href: "/docs/quickstart" },
      { label: "Installation & Setup Routes", href: "/docs/installation" },
    ],
  },
  {
    title: "Core Concepts",
    description:
      "Understand the contract: event ingestion, retrieval quality, feedback signals, and inferred memory.",
    links: [
      { label: "Integration Guide", href: "/docs/integration-guide" },
      { label: "Event Taxonomy", href: "/docs/event-taxonomy" },
      { label: "Personalization", href: "/docs/personalization" },
    ],
  },
  {
    title: "API Reference",
    description: "Method-by-method SDK docs and endpoint-by-endpoint REST reference.",
    links: [
      { label: "API Reference", href: "/docs/api-reference" },
      { label: "SDK Methods", href: "/docs/sdk-methods" },
      { label: "REST Endpoints", href: "/docs/rest-endpoints" },
    ],
  },
  {
    title: "Guides",
    description: "Production-style examples for FastAPI, OpenClaw integration, and live chatbot testing.",
    links: [
      { label: "FastAPI Integration", href: "/docs/fastapi-integration" },
      { label: "OpenClaw Plugin", href: "/docs/openclaw-plugin" },
      { label: "Examples", href: "/docs/examples" },
    ],
  },
  {
    title: "Operations",
    description:
      "Deploy, configure, monitor, and troubleshoot Orbit with a Postgres-first runtime path.",
    links: [
      { label: "Cloud Dashboard", href: "/dashboard" },
      { label: "Deployment", href: "/docs/deployment" },
      { label: "Configuration", href: "/docs/configuration" },
      { label: "Monitoring", href: "/docs/monitoring" },
      { label: "Troubleshooting", href: "/docs/troubleshooting" },
    ],
  },
  {
    title: "Metadata & Keywords",
    description: "See the stack, keywords, and docs signals we highlight for SEO/clarity.",
    links: [{ label: "Metadata Blueprint", href: "/docs/metadata" }],
  },
]

export const docsTranslations: Record<DocsLocale, DocsTranslation> = {
  en: {
    headerTitle: "Orbit Developer Docs",
    headerDescription:
      "Orbit is memory infrastructure for developer-facing AI products. Send signals, retrieve focused context, close the loop with feedback, and let memory quality improve over time.",
    quickInstallTitle: "Quick install",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "Marvelous tone",
    labSubtitle: "Floating AI-assisted onboarding",
    labTitle: "Orbit Setup Lab",
    labDescription:
      "Tap the Setup with AI helper that trails this page. Tell it your runtime (Cloud, Self-hosted, hybrid), your adapter, and we will build the exact prompt to copy into ChatGPT, Claude, or Cursor.",
    promptLabel: "Prompt blueprint",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "This keeps the docs humane and playful; the AI takes care of the boilerplate while you focus on the behavior you want.",
    languageSelectorLabel: "View docs in",
    sections: baseSections,
  },
  zh: {
    headerTitle: "Orbit 开发者文档",
    headerDescription:
      "Orbit 是面向开发者的记忆基础设施。发送信号、检索焦点上下文、使用反馈闭环，并让记忆质量随时间增长。",
    quickInstallTitle: "快速安装",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "Marvelous 风格",
    labSubtitle: "浮动 AI 辅助引导",
    labTitle: "Orbit 制服实验室",
    labDescription:
      "点击页面右侧的“AI 帮助设置”，告诉它你正在使用的运行环境（云、私有部署、混合）、所选适配器，我们会为你生成可粘贴到 ChatGPT、Claude 或 Cursor 的完整提示。",
    promptLabel: "提示模板",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "这样可以让文档保持自然有趣，AI 帮你完成常规样板，开发者只需专注行为预期。",
    languageSelectorLabel: "查看语言",
    sections: baseSections.map((section) => ({
      ...section,
      description: section.description.replace("Pick Cloud vs Self-Hosted", "选择云端或自托管").replace(
        "Understand the contract",
        "理解契约"
      ),
    })),
  },
  es: {
    headerTitle: "Documentación de Orbit",
    headerDescription:
      "Orbit es infraestructura de memoria para productos de IA orientados a desarrolladores. Envía señales, recupera contexto centrado y cierra el loop con feedback mientras la calidad de la memoria mejora con el tiempo.",
    quickInstallTitle: "Instalación rápida",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "Tono juguetón",
    labSubtitle: "Onboarding asistido por IA",
    labTitle: "Laboratorio de Setup Orbit",
    labDescription:
      "Activa el helper ‘Setup with AI’ que acompaña esta página. Indícale tu entorno (Cloud, Autoalojado, híbrido) y el adaptador; te retornamos el prompt exacto para ChatGPT, Claude o Cursor.",
    promptLabel: "Esquema del prompt",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "Así mantenemos la doc amigable y divertida: la IA genera el boilerplate mientras tú defines la conducta que esperas.",
    languageSelectorLabel: "Ver docs en",
    sections: baseSections,
  },
  de: {
    headerTitle: "Orbit Entwicklermaterial",
    headerDescription:
      "Orbit liefert Gedächtnisinfrastruktur für Entwickler-orientierte KI-Produkte. Sende Signale, hole fokussierten Kontext und schließe die Schleife per Feedback, während die Gedächtnisqualität wächst.",
    quickInstallTitle: "Schnellinstallation",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "Marvelous Ton",
    labSubtitle: "KI-gestütztes Onboarding",
    labTitle: "Orbit Setup-Labor",
    labDescription:
      "Nutze den „Setup with AI“-Helper rechts auf der Seite. Beschreibe dein Runtime-Szenario (Cloud, Self-Hosted, Hybrid) und Adapter, wir generieren das Prompt für ChatGPT, Claude oder Cursor.",
    promptLabel: "Prompt-Vorlage",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "So bleiben die Docs lebendig: die KI übernimmt die Boilerplate, du formulierst nur das gewünschte Verhalten.",
    languageSelectorLabel: "Docs anzeigen in",
    sections: baseSections,
  },
  ja: {
    headerTitle: "Orbit 開発者ドキュメント",
    headerDescription:
      "Orbit は開発者向け AI 製品のための記憶インフラです。信号を送信し、焦点の当たったコンテキストを取得し、フィードバックでループを閉じ、時間とともに記憶の質を高めます。",
    quickInstallTitle: "即時インストール",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "マーベラス調",
    labSubtitle: "AI アシストのセットアップ",
    labTitle: "Orbit セットアップラボ",
    labDescription:
      "ページ右下の「Setup with AI」をタップし、Cloud／セルフホスト／ハイブリッドなどの環境と使用アダプターを伝えてください。ChatGPT・Claude・Cursor 向けのプロンプトを生成します。",
    promptLabel: "プロンプトの型",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "こうすることでドキュメントは自然で楽しいまま。AI が定型コードを作り、あなたは望む振る舞いに集中できます。",
    languageSelectorLabel: "言語を選ぶ",
    sections: baseSections,
  },
  "pt-BR": {
    headerTitle: "Docs do Orbit",
    headerDescription:
      "Orbit é a infraestrutura de memória para produtos de IA focados em desenvolvedores. Envie sinais, recupere contexto e feche o loop com feedback enquanto a qualidade da memória melhora.",
    quickInstallTitle: "Instalação rápida",
    quickInstallCommand: "pip install orbit-memory",
    labBadge: "Tom brincalhão",
    labSubtitle: "Onboarding orientado por IA",
    labTitle: "Laboratório Setup Orbit",
    labDescription:
      "Use o helper “Setup with AI” que acompanha esta página. Diga qual runtime você usa (Cloud, Self-hosted, híbrido) e qual adaptador; entregamos o prompt pronto para o ChatGPT, Claude ou Cursor.",
    promptLabel: "Blueprint do prompt",
    promptExample:
      '"Generate an Orbit MemoryEngine init snippet in Python using the Ollama adapter. Show ingest + retrieve call for entity_id \'alice\' with conflict-aware metadata."',
    promptFooter:
      "Assim mantemos a doc leve e divertida; a IA cuida do boilerplate enquanto você define o comportamento que precisa.",
    languageSelectorLabel: "Ver em",
    sections: baseSections,
  },
}

export function getDocsTranslation(locale: string | undefined): DocsTranslation {
  if (!locale) {
    return docsTranslations.en
  }
  const normalized = locale.replace("pt-br", "pt-BR").toLowerCase()
  if (normalized.startsWith("zh")) {
    return docsTranslations.zh
  }
  if (normalized.startsWith("es")) {
    return docsTranslations.es
  }
  if (normalized.startsWith("de")) {
    return docsTranslations.de
  }
  if (normalized.startsWith("ja")) {
    return docsTranslations.ja
  }
  if (normalized === "pt-br") {
    return docsTranslations["pt-BR"]
  }
  return docsTranslations.en
}
