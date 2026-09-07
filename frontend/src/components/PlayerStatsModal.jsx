import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { playersApi } from '../services/endpoints'
import PlayerAvatar from './PlayerAvatar'
import { LoadingState, StatTile } from './ui'

export default function PlayerStatsModal({ playerId, onClose }) {
  const [stats, setStats] = useState(null)
  const [player, setPlayer] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!playerId) return undefined
    let cancelled = false
    setLoading(true)
    setError('')
    Promise.all([playersApi.get(playerId), playersApi.statistics(playerId)])
      .then(([p, s]) => {
        if (!cancelled) {
          setPlayer(p)
          setStats(s)
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [playerId])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!playerId) return null

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal-sheet fade-up"
        role="dialog"
        aria-modal="true"
        aria-label="Player statistics"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <PlayerAvatar player={player || { name: stats?.name }} size={64} />
            <div className="min-w-0">
              <h3 className="display text-3xl leading-none truncate">
                {stats?.name || player?.name || 'Player'}
              </h3>
              <p className="text-xs text-[var(--color-muted)] mt-1">Tap outside or Esc to close</p>
            </div>
          </div>
          <button type="button" className="btn btn-secondary" style={{ minHeight: 40 }} onClick={onClose}>
            Close
          </button>
        </div>

        {loading && <LoadingState />}
        {error && <p className="text-[var(--color-danger)] text-sm">{error}</p>}

        {stats && (
          <>
            <div className="stat-grid mb-4">
              <StatTile label="Matches" value={stats.matches_played} />
              <StatTile label="Win %" value={`${stats.win_rate}%`} />
              <StatTile label="Goals" value={stats.goals} />
              <StatTile label="Assists" value={stats.assists} />
              <StatTile label="G+A" value={stats.goal_contributions} />
              <StatTile label="Clean sheets" value={stats.clean_sheets} />
              <StatTile label="POTW" value={stats.potw} />
              <StatTile label="W-D-L" value={`${stats.wins}-${stats.draws}-${stats.losses}`} />
            </div>
            <Link className="btn btn-primary w-full" to={`/players/${playerId}`} onClick={onClose}>
              Open full profile
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
