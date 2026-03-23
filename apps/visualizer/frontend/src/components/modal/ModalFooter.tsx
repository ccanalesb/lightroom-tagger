import { ReactNode } from 'react'

interface ModalFooterProps {
  children: ReactNode
}

export function ModalFooter({ children }: ModalFooterProps) {
  return (
    <div className="border-t border-gray-200 p-4 flex justify-end gap-2">
      {children}
    </div>
  )
}
