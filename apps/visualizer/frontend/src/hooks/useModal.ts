import { useState, useCallback } from 'react'

interface UseModalReturn<T> {
  isOpen: boolean
  selectedItem: T | null
  open: (item: T) => void
  close: () => void
}

export function useModal<T>(): UseModalReturn<T> {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<T | null>(null)

  const open = useCallback((item: T) => {
    setSelectedItem(item)
    setIsOpen(true)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
    setSelectedItem(null)
  }, [])

  return { isOpen, selectedItem, open, close }
}
