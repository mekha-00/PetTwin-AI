/**
 * Authenticated shell: header, navigation, and the sign-out control.
 *
 * The sidebar collapses to a horizontal bar on small screens. Navigation is
 * filtered by the account's role: a veterinarian sees their shared patients
 * rather than "Add Pet", while a pet parent sees the ownership controls.
 */
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  BookOpenText,
  LayoutDashboard,
  LogOut,
  Menu,
  PawPrint,
  PlusCircle,
  Stethoscope,
  X,
} from 'lucide-react'

import { useAuth } from '../context/authContext'

// `roles: null` means every signed-in account sees the item.
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true, roles: null },
  {
    to: '/pets',
    label: 'My Pets',
    icon: PawPrint,
    end: false,
    roles: ['pet_owner'],
  },
  {
    to: '/pets/new',
    label: 'Add Pet',
    icon: PlusCircle,
    end: true,
    roles: ['pet_owner'],
  },
  {
    to: '/patients',
    label: 'My Patients',
    icon: Stethoscope,
    end: true,
    roles: ['veterinarian', 'clinic_staff'],
  },
  {
    to: '/reference',
    label: 'Clinical Reference',
    icon: BookOpenText,
    end: true,
    roles: null,
  },
]

function navItemsFor(role) {
  return NAV_ITEMS.filter((item) => item.roles === null || item.roles.includes(role))
}

function navClasses({ isActive }) {
  return [
    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-brand-soft text-brand-dark' : 'text-ink-soft hover:bg-canvas',
  ].join(' ')
}

export default function AppLayout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const navItems = navItemsFor(user?.role)
  const isVet = user?.role === 'veterinarian' || user?.role === 'clinic_staff'

  function handleSignOut() {
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <PawPrint className="h-5 w-5 text-brand" aria-hidden="true" />
            <span>PetTwin AI</span>
            <span className="badge bg-canvas text-ink-soft">Phase 5</span>
          </Link>

          <div className="flex items-center gap-3">
            {user?.full_name || user?.email ? (
              <span className="hidden text-sm text-ink-soft sm:inline">
                {user.full_name || user.email}
              </span>
            ) : null}
            <button type="button" onClick={handleSignOut} className="btn btn-secondary">
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary sm:hidden"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-label="Toggle navigation"
            >
              {menuOpen ? (
                <X className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Menu className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {menuOpen ? (
          <nav className="border-t border-line px-4 py-2 sm:hidden">
            <ul className="flex flex-col gap-1">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={navClasses}
                    onClick={() => setMenuOpen(false)}
                  >
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
      </header>

      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        <aside className="hidden w-52 shrink-0 sm:block">
          <nav className="sticky top-20">
            <ul className="flex flex-col gap-1">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.end} className={navClasses}>
                    <item.icon className="h-4 w-4" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>

            <div className="card mt-6 p-4">
              <h2 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-ink-soft uppercase">
                <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                Digital Twin
              </h2>
              <p className="mt-2 text-xs leading-relaxed text-ink-soft">
                {isVet
                  ? 'Assembled on demand from the patient\u2019s verified records. Software-based, not sensor-based.'
                  : 'Assembled on demand from each pet\u2019s records. Software-based, not sensor-based.'}
              </p>
            </div>
          </nav>
        </aside>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
