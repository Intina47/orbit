export function BlinkingCursor({ className = "" }: { className?: string }) {
  return (
    <span className={`cursor-blink text-primary ${className}`}>{'_'}</span>
  )
}
