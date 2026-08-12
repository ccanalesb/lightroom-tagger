import { useEffect, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export function parseTabFromSearch<T extends string>(
  search: string,
  tabIds: readonly T[],
): T | null {
  const tab = new URLSearchParams(search).get('tab')
  if (tab && tabIds.includes(tab as T)) return tab as T
  return null
}

export function usePageTab<T extends string>(config: {
  pagePath: string
  tabIds: readonly T[]
  defaultTab: T
  storedTab: T
  setStoredTab: (tab: T) => void
}) {
  const { pagePath, tabIds, defaultTab, storedTab, setStoredTab } = config
  const location = useLocation()
  const navigate = useNavigate()

  const urlTab = useMemo(
    () => parseTabFromSearch(location.search, tabIds),
    [location.search, tabIds],
  )

  const storedValidTab = tabIds.includes(storedTab) ? storedTab : defaultTab
  const activeTab = urlTab ?? storedValidTab

  useEffect(() => {
    if (storedTab !== activeTab) {
      setStoredTab(activeTab)
    }
  }, [activeTab, storedTab, setStoredTab])

  useEffect(() => {
    const desiredSearch = activeTab === defaultTab ? '' : `?tab=${activeTab}`
    if (location.search !== desiredSearch) {
      navigate({ pathname: pagePath, search: desiredSearch }, { replace: true })
    }
  }, [activeTab, defaultTab, pagePath, location.search, navigate])

  const handleTabChange = (id: string) => {
    if (!tabIds.includes(id as T)) return
    const next = id as T
    setStoredTab(next)
    navigate(
      { pathname: pagePath, search: next === defaultTab ? '' : `?tab=${next}` },
      { replace: true },
    )
  }

  return { activeTab, handleTabChange }
}
