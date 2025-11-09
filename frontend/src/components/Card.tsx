import React from 'react'

type CardProps = React.PropsWithChildren<{
  active?: boolean
  onClick?: () => void
  className?: string
}>

export default function Card({ active, onClick, className = '', children }: CardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.() } }}
      className={`recipe-card rounded-xl text-left cursor-pointer h-full flex flex-col ${active ? 'recipe-card-active' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
