import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { playersApi } from '../services/endpoints'
import PlayerAvatar from '../components/PlayerAvatar'

const playerLinks = [
  { to: '/', label: 'Home', end: true },
  { to: '/leaderboard', label: 'Board' },
  { to: '/awards', label: 'Awards' },
  { to: '/matches', label: 'Matches' },
  { to: '/profile', label: 'Me' },
]

const adminLinks = [
  { to: '/admin', label: 'Admin', end: true },
  { to: '/admin/matches', label: 'Matches' },
  { to: '/admin/players', label: 'Players' },
  { to: '/leaderboard', label: 'Board' },
  { to: '/awards', label: 'Awards' },
]

export default function AppLayout() {
  const { user, isAdmin, logout } = useAuth()
  const links = isAdmin ? adminLinks : playerLinks
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const [avatarPlayer, setAvatarPlayer] = useState(null)

  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username

  useEffect(() => {
    if (!menuOpen) return undefined
    function onClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [menuOpen])

  useEffect(() => {
    if (!user?.player_id) {
      setAvatarPlayer(null)
      return
    }
    let cancelled = false
    playersApi.get(user.player_id).then((p) => {
      if (!cancelled) setAvatarPlayer(p)
    }).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [user?.player_id])

  return (
    <div className="app-shell">
      <header className="page" style={{ paddingBottom: 0 }}>
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-muted)]">Private league</p>
            <h1 className="display text-4xl text-[var(--color-lime)] leading-none">Monday Night Raw</h1>
          </div>
          <div className="menu-anchor" ref={menuRef}>
            <button
              type="button"
              className="avatar-trigger"
              aria-label="Account menu"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <PlayerAvatar player={avatarPlayer || { name: displayName }} size={40} />
            </button>
            {menuOpen && (
              <div className="menu-panel card">
                <button
                  type="button"
                  className="menu-item"
                  onClick={() => {
                    setMenuOpen(false)
                    logout()
                  }}
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          {user?.username}
          {isAdmin ? ' · Admin' : ''}
        </p>
      </header>

      <main className="page fade-up">
        <Outlet />
      </main>

      <nav className="bottom-nav">
        {links.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
            <span>{link.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
