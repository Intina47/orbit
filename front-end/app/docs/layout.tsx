import type { Metadata } from "next"
import { Nav } from "@/components/orbit/nav"
import { DocsSidebar } from "@/components/orbit/docs-sidebar"
import { DocsAiSetupFab } from "@/components/orbit/docs-ai-setup-fab"

export const metadata: Metadata = {
  title: "Docs | Orbit",
  description: "Developer documentation for Orbit memory infrastructure: integration patterns, API reference, personalization behavior, and production operations.",
}

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Nav />
      <div className="flex">
        <DocsSidebar />
        <main className="flex-1 min-w-0">
          <div className="max-w-3xl mx-auto px-6 md:px-10 py-12 md:py-16">
            {children}
          </div>
        </main>
      </div>
      <DocsAiSetupFab />
    </div>
  )
}
