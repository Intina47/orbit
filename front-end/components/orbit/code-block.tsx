"use client"

import { useState } from "react"

interface CodeBlockProps {
  code: string
  language?: string
  filename?: string
}

export function CodeBlock({ code, language = "python", filename }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="border border-border my-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-secondary px-4 py-2 border-b border-border">
        <div className="flex items-center gap-3">
          {filename && (
            <span className="text-xs text-muted-foreground">{filename}</span>
          )}
          {!filename && (
            <span className="text-xs text-muted-foreground">{language}</span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {/* Code */}
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
        <code className="text-foreground">{code}</code>
      </pre>
    </div>
  )
}
