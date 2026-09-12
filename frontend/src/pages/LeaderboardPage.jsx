import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { statsApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'

const SORTS = [
  { value: '-goal_contributions', label: 'G+A' },
  { value: '-matches_played', label: 'Matches played' },
  { value: '-goals', label: 'Goals' },
  { value: '-assists', label: 'Assists' },
  { value: '-clean_sheets', label: 'Clean sheets' },
  { value: '-potw', label: 'POTW' },
]

export default function LeaderboardPage() {
  const [ordering, setOrdering] = useState('-goal_contributions')
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    statsApi
      .leaderboard(ordering)
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [ordering])

  return (
    <div className="space-y-4">
      <SectionTitle>Leaderboard</SectionTitle>
      <div className="field">
        <label htmlFor="sort">Sort by</label>
        <select id="sort" value={ordering} onChange={(e) => setOrdering(e.target.value)}>
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      <ErrorBanner message={error} />
      {loading ? (
        <LoadingState />
      ) : (
        <div className="card table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>MP</th>
                <th>G</th>
                <th>A</th>
                <th>CS</th>
                <th>POTW</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.player_id}>
                  <td>{row.rank}</td>
                  <td>
                    <Link
                      to={`/players/${row.player_id}`}
                      className="inline-flex items-center gap-2 font-semibold text-[var(--color-lime)]"
                    >
                      <PlayerAvatar
                        player={{ name: row.name, profile_photo: row.profile_photo }}
                        size={32}
                      />
                      {row.name}
                    </Link>
                  </td>
                  <td>{row.matches_played}</td>
                  <td>{row.goals}</td>
                  <td>{row.assists}</td>
                  <td>{row.clean_sheets}</td>
                  <td>{row.potw}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
