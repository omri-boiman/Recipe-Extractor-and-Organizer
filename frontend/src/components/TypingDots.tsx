import React from 'react'

export default function TypingDots({ className = '' }: { className?: string }) {
  return (
    <div className={`typing-dots ${className}`}> 
      <span />
      <span />
      <span />
    </div>
  )
}
