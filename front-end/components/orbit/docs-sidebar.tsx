"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"

const sections = [
  {
    title: "Getting Started",
    items: [
      { label: "Overview", href: "/docs" },
      { label: "Quickstart", href: "/docs/quickstart" },
      { label: "Installation & Setup", href: "/docs/installation" },
    ],
  },
  {
    title: "Core Concepts",
    items: [
      { label: "Integration Guide", href: "/docs/integration-guide" },
      { label: "Event Taxonomy", href: "/docs/event-taxonomy" },
      { label: "Personalization", href: "/docs/personalization" },
    ],
  },
  {
    title: "API",
    items: [
      { label: "API Reference", href: "/docs/api-reference" },
      { label: "SDK Methods", href: "/docs/sdk-methods" },
      { label: "REST Endpoints", href: "/docs/rest-endpoints" },
    ],
  },
  {
    title: "Guides",
    items: [
      { label: "FastAPI Integration", href: "/docs/fastapi-integration" },
      { label: "OpenClaw Plugin", href: "/docs/openclaw-plugin" },
      { label: "Examples", href: "/docs/examples" },
    ],
  },
  {
    title: "Operations",
    items: [
      { label: "Deployment", href: "/docs/deployment" },
      { label: "Configuration", href: "/docs/configuration" },
      { label: "Monitoring", href: "/docs/monitoring" },
      { label: "Troubleshooting", href: "/docs/troubleshooting" },
    ],
  },
]

export function DocsSidebar() {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed bottom-6 right-6 z-50 bg-primary text-primary-foreground w-12 h-12 flex items-center justify-center border border-border"
        aria-label="Toggle documentation sidebar"
      >
        <span className="text-lg">{mobileOpen ? "X" : "="}</span>
      </button>

      {/* Sidebar */}
      <aside
        className={`fixed lg:sticky top-[65px] left-0 z-40 h-[calc(100vh-65px)] w-72 bg-background border-r border-border overflow-y-auto transition-transform duration-200 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <div className="py-8 px-6">
          {sections.map((section) => (
            <div key={section.title} className="mb-8">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-4 h-px bg-border" />
                <span className="text-[10px] tracking-[0.3em] uppercase text-muted-foreground font-bold">
                  {section.title}
                </span>
              </div>
              <ul className="space-y-1">
                {section.items.map((item) => {
                  const isActive = pathname === item.href
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setMobileOpen(false)}
                        className={`block px-3 py-2 text-sm transition-colors ${
                          isActive
                            ? "text-primary bg-primary/5 border-l-2 border-primary text-glow-sm"
                            : "text-muted-foreground hover:text-foreground border-l-2 border-transparent hover:border-border"
                        }`}
                      >
                        {item.label}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  )
}
