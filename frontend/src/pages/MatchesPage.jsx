import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { matchesApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle, EmptyState } from '../components/ui'
import { useAuth } from '../context/AuthContext'

function unwrapList(data) {
  if (Array.isArray(data)) return data
  return data?.results || []
}

function myAvailability(match, playerId) {
  if (!playerId) return null
  return (match.availabilities || []).find((a) => a.player.id === playerId) || null
}

export default function MatchesPage() {
  const { isAdmin, user } = useAuth()
  const [matches, setMatches] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  async function load() {
    const data = await matchesApi.list()
    setMatches(unwrapList(data))
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
        Matches
      </SectionTitle>
      {!isAdmin && (
        <p className="text-sm text-[var(--color-muted)] -mt-2">
          Toggle whether you’re in for an upcoming Monday. Admin confirms the final squad (10–14 players).
        </p>
      )}
      <ErrorBanner message={error} />
      {loading ? (
        <LoadingState />
      ) : matches.length === 0 ? (
        <EmptyState>No matches yet.</EmptyState>
      ) : (
        <div className="space-y-3">
          {matches.map((m) => {
            const openForRsvp = !m.is_finalized && m.status !== 'COMPLETED'
            const mine = myAvailability(m, user?.player_id)
            return (
              <div key={m.id} className="card space-y-3">
                <Link
                  to={isAdmin ? `/admin/matches/${m.id}` : `/matches/${m.id}`}
                  className="flex justify-between items-start gap-3"
                >
                  <div>
                    <p className="font-semibold">{m.match_date}</p>
                    <p className="text-sm text-[var(--color-muted)]">
                      {m.status}
                      {m.squad_size ? ` · Squad ${m.squad_size}` : ''}
                    </p>
                  </div>
                  <p className="display text-4xl text-[var(--color-lime)]">
                    {m.team_a_score != null ? `${m.team_a_score}-${m.team_b_score}` : 'vs'}
                  </p>
                </Link>

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
