import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { gameWeeksApi, matchesApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle, EmptyState } from '../components/ui'
import { useAuth } from '../context/AuthContext'

function unwrapList(data) {
  if (Array.isArray(data)) return data
  return data?.results || []
}

function TrashIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function myAvailability(match, playerId) {
  if (!playerId) return null
  return (match.availabilities || []).find((a) => a.player.id === playerId) || null
}

export default function MatchesPage() {
  const { isAdmin, user } = useAuth()
  const [matches, setMatches] = useState([])
  const [gameWeeks, setGameWeeks] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  async function load() {
    const [matchData, gameWeekData] = await Promise.all([
      matchesApi.list(),
      gameWeeksApi.list(),
    ])
    setMatches(unwrapList(matchData).filter((m) => !m.game_week))
    setGameWeeks(unwrapList(gameWeekData))
  }

  useEffect(() => {
    load()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function setRsvp(matchId, status) {
    setBusyId(matchId)
    setError('')
    try {
      await matchesApi.setAvailability(matchId, status)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  async function deleteRow(row) {
    const label = row.kind === 'gameWeek' ? 'this game week and all its fixtures' : 'this matchday'
    if (!window.confirm(`Delete ${label}? This can't be undone.`)) return
    const key = `${row.kind}-${row.data.id}`
    setBusyId(key)
    setError('')
    try {
      if (row.kind === 'gameWeek') {
        await gameWeeksApi.remove(row.data.id)
      } else {
        await matchesApi.remove(row.data.id)
      }
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const rows = [
    ...matches.map((m) => ({ kind: 'match', date: m.match_date, data: m })),
    ...gameWeeks.map((gw) => ({ kind: 'gameWeek', date: gw.week_date, data: gw })),
  ].sort((a, b) => b.date.localeCompare(a.date))

  return (
    <div className="space-y-4">
      <SectionTitle
        action={
          isAdmin ? (
            <Link className="btn btn-primary" style={{ minHeight: 40, padding: '0.4rem 0.8rem' }} to="/admin/matches/new">
              New
            </Link>
          ) : null
        }
      >
        Stats
      </SectionTitle>
      {!isAdmin && (
        <p className="text-sm text-[var(--color-muted)] -mt-2">
          Toggle whether you’re in for an upcoming Monday. Admin logs goals and assists after.
        </p>
      )}
      <ErrorBanner message={error} />
      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState>No matches yet.</EmptyState>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            if (row.kind === 'gameWeek') {
              const gw = row.data
              const busyKey = `gameWeek-${gw.id}`
              return (
                <div key={`gw-${gw.id}`} className="card space-y-2">
                  <div className="flex items-start gap-3">
                    <Link
                      to={isAdmin ? `/admin/game-weeks/${gw.id}` : `/game-weeks/${gw.id}`}
                      className="flex justify-between items-start gap-3 flex-1 min-w-0"
                    >
                      <div>
                        <p className="font-semibold">{gw.week_date}</p>
                        <p className="text-sm text-[var(--color-muted)]">
                          {gw.status} · {gw.fixtures.length} {gw.fixtures.length === 1 ? 'fixture' : 'fixtures'}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="display text-4xl text-[var(--color-lime)] leading-none">
                          {gw.is_finalized ? gw.fixtures.reduce((sum, f) => sum + f.goals.length, 0) : '—'}
                        </p>
                        {gw.is_finalized && <p className="text-xs text-[var(--color-muted)]">goals</p>}
                      </div>
                    </Link>
                    {isAdmin && (
                      <button
                        type="button"
                        className="btn btn-danger icon-btn shrink-0"
                        disabled={busyId === busyKey}
                        onClick={() => deleteRow(row)}
                        title="Delete"
                        aria-label="Delete game week"
                      >
                        <TrashIcon />
                      </button>
                    )}
                  </div>
                </div>
              )
            }

            const m = row.data
            const openForRsvp = !m.is_finalized && m.status !== 'COMPLETED'
            const mine = myAvailability(m, user?.player_id)
            const busyKey = `match-${m.id}`
            return (
              <div key={m.id} className="card space-y-3">
                <div className="flex items-start gap-3">
                  <Link
                    to={isAdmin ? `/admin/matches/${m.id}` : `/matches/${m.id}`}
                    className="flex justify-between items-start gap-3 flex-1 min-w-0"
                  >
                    <div>
                      <p className="font-semibold">{m.match_date}</p>
                      <p className="text-sm text-[var(--color-muted)]">
                        {m.status}
                        {m.squad_size ? ` · ${m.squad_size} on the scoresheet` : ''}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="display text-4xl text-[var(--color-lime)] leading-none">
                        {m.is_finalized ? m.goals?.length ?? 0 : '—'}
                      </p>
                      {m.is_finalized && <p className="text-xs text-[var(--color-muted)]">goals</p>}
                    </div>
                  </Link>
                  {isAdmin && (
                    <button
                      type="button"
                      className="btn btn-danger icon-btn shrink-0"
                      disabled={busyId === busyKey}
                      onClick={() => deleteRow(row)}
                      title="Delete"
                      aria-label="Delete matchday"
                    >
                      <TrashIcon />
                    </button>
                  )}
                </div>

                {!isAdmin && openForRsvp && user?.player_id && (
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      className={`btn ${mine?.status === 'AVAILABLE' ? 'btn-primary' : 'btn-secondary'}`}
                      disabled={busyId === m.id}
                      onClick={() => setRsvp(m.id, 'AVAILABLE')}
                    >
                      I’m in
                    </button>
                    <button
                      type="button"
                      className={`btn ${mine?.status === 'UNAVAILABLE' ? 'btn-danger' : 'btn-secondary'}`}
                      disabled={busyId === m.id}
                      onClick={() => setRsvp(m.id, 'UNAVAILABLE')}
                    >
                      Out
                    </button>
                  </div>
                )}
                {!isAdmin && mine && (
                  <p className="text-xs text-[var(--color-muted)]">
                    Your RSVP: {mine.status === 'AVAILABLE' ? 'Available' : 'Unavailable'}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
