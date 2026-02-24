export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="py-12 md:py-16 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-10">
          {/* Left */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-2 h-2 bg-primary" />
              <span className="text-foreground font-bold tracking-widest text-sm">ORBIT</span>
            </div>
            <p className="text-muted-foreground text-sm leading-relaxed max-w-sm mb-6">
              Memory infrastructure for AI products that need long-term user understanding, cleaner retrieval, and fewer moving parts.
            </p>
            <div className="text-muted-foreground text-sm">
              hello@theorbit.dev
            </div>
          </div>

          {/* Right: links */}
          <div className="flex flex-wrap gap-x-10 gap-y-4">
            {[
              { label: "Documentation", href: "/docs" },
              { label: "GitHub", href: "#" },
              { label: "Examples", href: "#" },
              { label: "Status", href: "#" },
              { label: "Changelog", href: "#" },
              { label: "Support", href: "#" },
            ].map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors tracking-wide"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-border py-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            2026 Orbit. Keep the good memories.
          </p>
          <p className="text-xs text-muted-foreground">
            Built for developers who ship.
          </p>
        </div>
      </div>
    </footer>
  )
}
