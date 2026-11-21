import React, { useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Award,
  Bell,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Files,
  LayoutDashboard,
  LogOut,
  Menu,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  Upload,
  UserRound
} from 'lucide-react'

const centreNavigation = [
  [
    'Overview',
    [
      ['Dashboard', '/', LayoutDashboard],
      ['Upload New Batch', '/upload', Upload],
      ['My Batches', '/batches', Files]
    ]
  ],
  [
    'Workflow',
    [
      ['Pending Approvals', '/pending', ClipboardCheck],
      ['Returned for Corrections', '/returned', RotateCcw],
      ['Certificates', '/certificates', Award]
    ]
  ],
  ['Account', [['Profile & Settings', '/profile', Settings]]]
]

const officerNavigation = [
  [
    'Overview',
    [
      ['Dashboard', '/', LayoutDashboard],
      ['Pending Reviews', '/district/pending', ClipboardCheck]
    ]
  ],
  [
    'Workflow',
    [
      ['Approved Batches', '/district/approved', Award],
      ['Review History', '/district/history', Files]
    ]
  ],
  [
    'Account',
    [
      ['Notifications', '/district/notifications', Bell],
      ['Profile & Settings', '/profile', Settings]
    ]
  ]
]

const qualityNavigation = [
  [
    'Overview',
    [
      ['Dashboard', '/', LayoutDashboard],
      ['Review Queue', '/quality/pending', ClipboardCheck]
    ]
  ],
  [
    'Workflow',
    [
      ['Approved Batches', '/quality/approved', Award],
      ['Review History', '/quality/history', Files]
    ]
  ],
  ['Account', [['Profile & Settings', '/profile', Settings]]]
]

const stateNavigation = [
  [
    'Overview',
    [
      ['Dashboard', '/', LayoutDashboard],
      ['Final Approval Queue', '/state/pending', ClipboardCheck]
    ]
  ],
  [
    'Workflow',
    [
      ['Approved Batches', '/state/approved', Award],
      ['Review History', '/state/history', Files]
    ]
  ],
  ['Account', [['Profile & Settings', '/profile', Settings]]]
]

export function Layout({ user, onLogout, returnedCount }) {
  const [sidebar, setSidebar] = useState(false)
  const [panel, setPanel] = useState('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const officer = user.role === 'DISTRICT_OFFICER'
  const quality = user.role === 'QUALITY_TEAM'
  const stateOffice = user.role === 'STATE_OFFICE'
  const centre = user.role === 'TRAINING_CENTRE'
  const role = stateOffice
    ? 'State Office'
    : quality
      ? 'Quality Team'
      : officer
        ? 'District Officer'
        : centre
          ? 'Training Centre'
          : user.role.replaceAll('_', ' ')
  const navigation = stateOffice
    ? stateNavigation
    : quality
      ? qualityNavigation
      : officer
        ? officerNavigation
        : centre
          ? centreNavigation
          : officerNavigation.slice(-1).map(([group, items]) => [group, items.slice(-1)])

  const { pathname } = useLocation()
  const navigate = useNavigate()

  const title =
    navigation.flatMap(([, items]) => items).find(([, to]) => pathname === to)?.[0] ??
    (pathname.endsWith('/edit') ? 'Edit Batch' : 'Batch Details')

  const toggle = (value) => setPanel((current) => (current === value ? '' : value))

  async function logout() {
    setPanel('')
    setSidebar(false)
    try {
      await onLogout()
    } catch (failure) {
      setError(failure.message)
    }
  }

  return (
    <div
      className="shell"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          setPanel('')
          setSidebar(false)
        }
      }}
    >
      {sidebar && (
        <button className="scrim" aria-label="Close navigation" onClick={() => setSidebar(false)} />
      )}

      <aside className={'sidebar' + (sidebar ? ' open' : '')}>
        <Link className="brand" to="/" onClick={() => setSidebar(false)}>
          <span className="brand-mark">
            <ShieldCheck size={23} />
          </span>

          <span>
            <strong>CertiFlow</strong>
            <small>{role} Portal</small>
          </span>
        </Link>

        <nav aria-label="Main navigation">
          {navigation.map(([group, items]) => (
            <div className="nav-group" key={group}>
              <p>{group}</p>

              {items.map(([label, to, Icon]) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  onClick={() => {
                    setSidebar(false)
                    setPanel('')
                  }}
                >
                  <Icon size={18} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="avatar">
              <UserRound size={17} aria-hidden="true" />
            </span>

            <div>
              <strong>{user.name}</strong>
              <small>{role}</small>

              {user.centre?.name && <small>{user.centre?.name}</small>}
            </div>
          </div>

          <button onClick={logout}>
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebar(true)}
            >
              <Menu size={21} />
            </button>

            <span>{role}</span>

            <ChevronRight size={15} />

            <strong>{title}</strong>
          </div>

          <div className="top-actions">
            <button
              className="icon-button"
              aria-label="Search batches"
              aria-expanded={panel === 'search'}
              onClick={() => toggle('search')}
            >
              <Search size={19} />
            </button>

            <button
              className="icon-button notification"
              aria-label="Notifications"
              aria-expanded={panel === 'notifications'}
              onClick={() => toggle('notifications')}
            >
              <Bell size={19} />

              {returnedCount > 0 && <i />}
            </button>

            <div className="top-divider" />

            <button
              className="profile-button"
              aria-label="Account menu"
              aria-expanded={panel === 'profile'}
              onClick={() => toggle('profile')}
            >
              <span className="avatar">
                <UserRound size={17} aria-hidden="true" />
              </span>

              <span className="profile-name">
                <strong>{user.name}</strong>
                <small>{role}</small>
              </span>

              <ChevronDown size={15} />
            </button>
          </div>

          {panel && (
            <div className="popover card">
              {panel === 'search' && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    navigate(
                      (stateOffice
                        ? '/state/pending'
                        : quality
                          ? '/quality/pending'
                          : officer
                            ? '/district/pending'
                            : '/batches') +
                        (quality || stateOffice ? '?search=' : '?q=') +
                        encodeURIComponent(query)
                    )
                    setPanel('')
                  }}
                >
                  <label htmlFor="global-search">Search batches</label>

                  <div className="inline">
                    <input
                      autoFocus
                      id="global-search"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Batch ID or name"
                    />

                    <button className="button primary">Search</button>
                  </div>
                </form>
              )}

              {panel === 'notifications' && (
                <>
                  <strong>Notifications</strong>

                  {returnedCount > 0 ? (
                    <>
                      <p>
                        {returnedCount} {returnedCount === 1 ? 'batch requires' : 'batches require'}{' '}
                        corrections.
                      </p>

                      <Link to="/returned" onClick={() => setPanel('')}>
                        View returned batches
                      </Link>
                    </>
                  ) : officer ? (
                    <Link to="/district/notifications" onClick={() => setPanel('')}>
                      View district notifications
                    </Link>
                  ) : (
                    <p>No notifications available.</p>
                  )}
                </>
              )}

              {panel === 'profile' && (
                <>
                  <Link to="/profile" onClick={() => setPanel('')}>
                    <Settings size={16} />
                    Profile & Settings
                  </Link>

                  <button className="text-button" onClick={logout}>
                    <LogOut size={16} />
                    Log out
                  </button>
                </>
              )}
            </div>
          )}
        </header>

        <main className="content" id="main-content">
          {error && (
            <p className="notice error" role="alert">
              {error}
            </p>
          )}
          <Outlet />
        </main>

        <footer className="workspace-footer">
          <span>© 2026 CertiFlow</span>

          <span>
            <CircleHelp size={15} />
            {role} Portal
          </span>
        </footer>
      </div>
    </div>
  )
}
