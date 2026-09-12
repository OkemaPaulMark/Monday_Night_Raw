import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner } from '../components/ui'
import { POSITIONS } from '../constants'

export default function RegisterPage() {
  const { register, user, loading } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [position, setPosition] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await register({ name, username, email, password, position })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Registration failed')
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
          <p className="mt-3 text-[var(--color-muted)]">Create your player account.</p>
        </div>

        <form className="card space-y-4" onSubmit={onSubmit}>
          <ErrorBanner message={error} />
          <div className="field">
            <label htmlFor="name">Full name</label>
            <input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="position">Position</label>
            <select id="position" value={position} onChange={(e) => setPosition(e.target.value)} required>
              <option value="" disabled>Select your position</option>
              {POSITIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary w-full" type="submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
          <p className="text-xs text-[var(--color-muted)] text-center">
            Already have an account? <Link to="/login" className="underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
