import { Outlet, NavLink } from 'react-router-dom';
import { ThemeToggle } from './ui/ThemeToggle';
import {
  APP_TITLE,
  NAV_ANALYTICS,
  NAV_DASHBOARD,
  NAV_IDENTITY,
  NAV_IMAGES,
  NAV_PROCESSING,
} from '../constants/strings';

export function Layout() {
  const navItems = [
    { to: '/', label: NAV_DASHBOARD, exact: true },
    { to: '/images', label: NAV_IMAGES },
    { to: '/analytics', label: NAV_ANALYTICS },
    { to: '/identity', label: NAV_IDENTITY },
    { to: '/processing', label: NAV_PROCESSING },
  ];

  return (
    <div className="min-h-screen bg-bg transition-colors duration-200">
      <header className="sticky top-0 z-50 bg-bg/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-8">
              <h1 className="text-lg font-semibold text-text">{APP_TITLE}</h1>

              <nav className="hidden md:flex items-center space-x-1">
                {navItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.exact}
                    className={({ isActive }) =>
                      `px-3 py-1.5 rounded-base text-sm font-medium transition-all duration-150
                      ${isActive
                        ? 'bg-accent text-white shadow-sm font-semibold'
                        : 'text-text-secondary hover:bg-surface hover:text-text'}`
                    }
                    style={({ isActive }) =>
                      isActive ? { backgroundColor: 'var(--color-accent)', color: 'white' } : undefined
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>

            <ThemeToggle />
          </div>
        </div>

        <div className="md:hidden border-t border-border">
          <nav className="px-4 py-2 flex overflow-x-auto space-x-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-base text-sm font-medium whitespace-nowrap transition-all
                  ${isActive
                    ? 'bg-accent text-white shadow-sm font-semibold'
                    : 'text-text-secondary hover:bg-surface hover:text-text'}`
                }
                style={({ isActive }) =>
                  isActive ? { backgroundColor: 'var(--color-accent)', color: 'white' } : undefined
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
