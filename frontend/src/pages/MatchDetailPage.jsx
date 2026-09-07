import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { matchesApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'
import PlayerStatsModal from '../components/PlayerStatsModal'

export default function MatchDetailPage() {
  const { id } = useParams()
  const [match, setMatch] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedPlayerId, setSelectedPlayerId] = useState(null)

  useEffect(() => {
    matchesApi
      .get(id)
      .then(setMatch)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <LoadingState />
  if (error) return <ErrorBanner message={error} />
  if (!match) return null

  const teamA = match.teams.find((t) => t.side === 'A')
  const teamB = match.teams.find((t) => t.side === 'B')

  return (
    <div className="space-y-4">
      <SectionTitle>{match.match_date}</SectionTitle>
      <div className="card text-center">
        <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">{match.status}</p>
        <p className="display text-6xl text-[var(--color-lime)] mt-2">
          {match.team_a_score != null ? `${match.team_a_score} — ${match.team_b_score}` : 'TBD'}
        </p>
        {(match.potw || []).length > 0 && (
          <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
            {match.potw.map((p) => (
              <button
                key={p.id}
                type="button"
                className="inline-flex items-center gap-2"
                onClick={() => setSelectedPlayerId(p.id)}
              >
                <span className="badge">POTW</span>
                <PlayerAvatar player={p} size={36} />
                <span>{p.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[['Team A', teamA], ['Team B', teamB]].map(([label, team]) => (
          <div key={label} className="card">
            <h3 className="font-bold mb-2">{label}</h3>
            <div className="space-y-2">
              {(team?.roster || []).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="player-chip"
                  onClick={() => setSelectedPlayerId(r.player.id)}
                >
                  <PlayerAvatar player={r.player} size={36} />
                  <span className="text-sm font-semibold">{r.player.name}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="font-bold mb-2">Goals</h3>
        <ul className="space-y-2 text-sm">
          {match.goals.map((g) => (
            <li key={g.id} className="flex items-center gap-2">
              <button type="button" onClick={() => setSelectedPlayerId(g.scorer.id)}>
                <PlayerAvatar player={g.scorer} size={28} />
              </button>
              <span>
                {g.order}. {g.scorer.name}
                {g.assister ? ` (A: ${g.assister.name})` : ''}
                <span className="text-[var(--color-muted)]"> · Team {g.scoring_team_side}</span>
              </span>
            </li>
          ))}
          {match.goals.length === 0 && <li className="text-[var(--color-muted)]">No goals recorded.</li>}
        </ul>
      </div>

      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
