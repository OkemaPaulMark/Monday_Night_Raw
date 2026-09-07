import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner } from '../components/ui'

export default function LoginPage() {
  const { login, user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    const isAdminUser = user.is_app_admin || user.role === 'ADMIN'
    const from = location.state?.from?.pathname
    const fallback = isAdminUser ? '/admin' : '/'
    // A stale `from` can belong to a previously logged-out account (e.g. a
    // player's /profile), so only honor it when it fits the current role.
    const target = from && (isAdminUser ? from.startsWith('/admin') : !from.startsWith('/admin'))
      ? from
      : fallback
    return <Navigate to={target} replace />
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const loggedIn = await login(username, password)
      navigate(loggedIn.is_app_admin || loggedIn.role === 'ADMIN' ? '/admin' : '/', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center p-4">
      <div className="w-full max-w-md fade-up">
        <div className="mb-8 text-center">
          <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-muted)]">7-a-side league</p>
          <h1 className="display text-6xl text-[var(--color-lime)] leading-none mt-2">Monday Night Raw</h1>
          <p className="mt-3 text-[var(--color-muted)]">Stats, awards, and Monday bragging rights.</p>
        </div>

        <form className="card space-y-4" onSubmit={onSubmit}>
          <ErrorBanner message={error} />
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button className="btn btn-primary w-full" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="text-xs text-[var(--color-muted)] text-center">
            New player? <Link to="/register" className="underline">Create an account</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
