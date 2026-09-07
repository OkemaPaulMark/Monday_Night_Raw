import { useEffect, useState } from 'react'
import { statsApi } from '../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle } from '../components/ui'

export default function StandingsPage() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    statsApi
      .standings()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4">
      <SectionTitle>Team labels</SectionTitle>
      <p className="text-sm text-[var(--color-muted)] -mt-2">
        Cumulative Team A / Team B labels across matches (not permanent clubs).
      </p>
      <ErrorBanner message={error} />
      {loading ? (
        <LoadingState />
      ) : (
        <div className="card table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Team</th>
                <th>P</th>
                <th>W</th>
                <th>D</th>
                <th>L</th>
                <th>GD</th>
                <th>Pts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.side}>
                  <td>{r.team}</td>
                  <td>{r.matches_played}</td>
                  <td>{r.wins}</td>
                  <td>{r.draws}</td>
                  <td>{r.losses}</td>
                  <td>{r.goal_difference}</td>
                  <td>{r.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
