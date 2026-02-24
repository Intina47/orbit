"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

export function Nav() {
  const pathname = usePathname()
  const isDocs = pathname.startsWith("/docs")
  const isDashboard = pathname.startsWith("/dashboard")

  return (
    <nav className="w-full border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-5 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-2 h-2 bg-primary" />
            <span className="text-foreground font-bold tracking-widest text-sm">ORBIT</span>
          </Link>
          <div className="hidden md:flex items-center gap-6 text-xs tracking-wider text-muted-foreground">
            <Link
              href="/docs"
              className={`hover:text-foreground transition-colors ${isDocs ? "text-primary text-glow-sm" : ""}`}
            >
              DOCS
            </Link>
            <Link href="/docs/api-reference" className="hover:text-foreground transition-colors">
              API
            </Link>
            <Link
              href="/dashboard"
              className={`hover:text-foreground transition-colors ${isDashboard ? "text-primary text-glow-sm" : ""}`}
            >
              DASHBOARD
            </Link>
            <Link href="/docs/quickstart" className="hover:text-foreground transition-colors">
              QUICKSTART
            </Link>
            <a href="https://github.com/intina47/orbit" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
              GITHUB
            </a>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {!isDocs && !isDashboard && (
            <div className="hidden md:flex items-center gap-8 text-xs tracking-wider text-muted-foreground">
              <a href="#problem" className="hover:text-foreground transition-colors">PROBLEM</a>
              <a href="#how-it-works" className="hover:text-foreground transition-colors">HOW IT WORKS</a>
              <a href="#metrics" className="hover:text-foreground transition-colors">METRICS</a>
            </div>
          )}
          <Link
            href={isDocs || isDashboard ? "/" : "#cta"}
            className="border border-foreground px-5 py-2 text-foreground text-xs tracking-wider hover:bg-foreground hover:text-background transition-all duration-200"
          >
            {isDocs || isDashboard ? "HOME" : "START BUILDING"}
          </Link>
        </div>
      </div>
    </nav>
  )
}
