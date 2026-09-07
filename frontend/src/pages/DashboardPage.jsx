import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { statsApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle, StatTile } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'
import { useAuth } from '../context/AuthContext'

function LeaderCard({ label, row, metric }) {
  if (!row) {
    return (
      <div className="card flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--color-muted)]">{label}</p>
          <p className="font-semibold">—</p>
        </div>
      </div>
    )
  }
  return (
    <Link to={`/players/${row.player_id}`} className="card flex items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <PlayerAvatar player={{ name: row.name, profile_photo: row.profile_photo }} size={40} />
        <div className="min-w-0">
          <p className="text-xs text-[var(--color-muted)]">{label}</p>
          <p className="font-semibold truncate">{row.name}</p>
        </div>
      </div>
      <p className="display text-3xl text-[var(--color-gold)] shrink-0">
        {row[metric] ?? '—'}
      </p>
    </Link>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    statsApi
      .dashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingState />
  if (error) return <ErrorBanner message={error} />

  return (
    <div className="space-y-5">
      <SectionTitle>Dashboard</SectionTitle>
      <p className="text-[var(--color-muted)] -mt-2">
        Welcome back{user?.first_name ? `, ${user.first_name}` : ''}.
      </p>

      <div className="stat-grid">
        <StatTile label="Players" value={data.total_players} />
        <StatTile label="Matches" value={data.total_matches} />
      </div>

      {data.latest_match && (
        <div className="card">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">Latest match</p>
          <p className="display text-4xl mt-1">{data.latest_match.score}</p>
          <p className="text-sm text-[var(--color-muted)] mt-1">{data.latest_match.match_date}</p>
          {data.latest_match.potw && (
            <p className="mt-2">
              <span className="badge">POTW</span> {data.latest_match.potw}
            </p>
          )}
          <Link className="btn btn-secondary mt-4 w-full" to={`/matches/${data.latest_match.id}`}>
            View match
          </Link>
        </div>
      )}

      <div className="grid gap-3">
        <LeaderCard label="Top scorer" row={data.top_scorer} metric="goals" />
        <LeaderCard label="Top assister" row={data.top_assister} metric="assists" />
        <LeaderCard label="Clean sheets" row={data.most_clean_sheets} metric="clean_sheets" />
        <LeaderCard label="Most POTW" row={data.most_potw} metric="potw" />
      </div>
    </div>
  )
}
