import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { gameWeeksApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'
import PlayerStatsModal from '../components/PlayerStatsModal'

export default function GameWeekDetailPage() {
  const { id } = useParams()
  const [gameWeek, setGameWeek] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedPlayerId, setSelectedPlayerId] = useState(null)

  useEffect(() => {
    gameWeeksApi
      .get(id)
      .then(setGameWeek)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <LoadingState />
  if (error) return <ErrorBanner message={error} />
  if (!gameWeek) return null

  const totalGoals = gameWeek.fixtures.reduce((sum, f) => sum + f.goals.length, 0)

  return (
    <div className="space-y-4">
      <SectionTitle>{gameWeek.week_date}</SectionTitle>
      <div className="card text-center">
        <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">
          {gameWeek.status} · {gameWeek.fixtures.length} {gameWeek.fixtures.length === 1 ? 'fixture' : 'fixtures'}
        </p>
        <p className="display text-6xl text-[var(--color-lime)] mt-2">
          {gameWeek.is_finalized ? totalGoals : 'TBD'}
        </p>
        <p className="text-xs text-[var(--color-muted)] mt-1">
          {gameWeek.is_finalized ? 'goals across the evening' : 'not finalized yet'}
        </p>
      </div>

      <div className="space-y-3">
        {gameWeek.fixtures.map((fixture, index) => (
          <div key={fixture.id} className="card">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-bold">Fixture {index + 1}</h3>
              {fixture.has_team_scores && (
                <span className="badge">
                  {fixture.team_a_name || 'A'} {fixture.team_a_score} : {fixture.team_b_score} {fixture.team_b_name || 'B'}
                </span>
              )}
            </div>
            <ul className="space-y-2 text-sm mt-2">
              {fixture.goals.map((g) => (
                <li key={g.id} className="flex items-center gap-2">
                  <button type="button" onClick={() => setSelectedPlayerId(g.scorer.id)}>
                    <PlayerAvatar player={g.scorer} size={28} />
                  </button>
                  <span>
                    {g.order}. {g.scorer.name}
                    {g.assister ? ` (A: ${g.assister.name})` : ''}
                  </span>
                </li>
              ))}
              {fixture.goals.length === 0 && (
                <li className="text-[var(--color-muted)]">No goals recorded.</li>
              )}
            </ul>
          </div>
        ))}
        {gameWeek.fixtures.length === 0 && (
          <p className="text-sm text-[var(--color-muted)]">No fixtures added yet.</p>
        )}
      </div>

      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
