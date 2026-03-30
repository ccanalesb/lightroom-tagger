import { Outlet, NavLink } from 'react-router-dom'
import { APP_TITLE, NAV_DASHBOARD, NAV_INSTAGRAM, NAV_MATCHING, NAV_DESCRIPTIONS, NAV_JOBS, NAV_PROVIDERS } from '../constants/strings'

export function Layout() {
  const navItems = [
    { to: '/', label: NAV_DASHBOARD },
    { to: '/instagram', label: NAV_INSTAGRAM },
    { to: '/matching', label: NAV_MATCHING },
    { to: '/descriptions', label: NAV_DESCRIPTIONS },
    { to: '/jobs', label: NAV_JOBS },
    { to: '/providers', label: NAV_PROVIDERS },
  ]
  
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-white font-bold text-xl">{APP_TITLE}</h1>
            <div className="flex space-x-4">
              {navItems.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded text-sm font-medium ${
                      isActive ? 'bg-gray-900 text-white' : 'text-gray-300 hover:bg-gray-700'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}