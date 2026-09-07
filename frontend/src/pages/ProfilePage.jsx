import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { playersApi } from '../services/endpoints'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, LoadingState, SectionTitle, StatTile } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'

export default function ProfilePage({ self = false }) {
  const { id } = useParams()
  const { user, isAdmin } = useAuth()
  const playerId = self ? user?.player_id : Number(id)
  const [stats, setStats] = useState(null)
  const [player, setPlayer] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef(null)

  const canUpload =
    Boolean(playerId) &&
    (isAdmin || (self && user?.player_id === playerId))

  async function load() {
    if (!playerId) {
      setLoading(false)
      setError(self ? 'No player profile linked to this account.' : 'Player not found.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const [p, s, h] = await Promise.all([
        playersApi.get(playerId),
        playersApi.statistics(playerId),
        playersApi.matchHistory(playerId),
      ])
      setPlayer(p)
      setStats(s)
      setHistory(h)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [playerId, self])

  async function onPhotoChange(e) {
    const file = e.target.files?.[0]
    if (!file || !playerId) return
    setUploading(true)
    setError('')
    try {
      const updated = await playersApi.uploadPhoto(playerId, file)
      setPlayer(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  if (loading) return <LoadingState />
  if (error && !stats) return <ErrorBanner message={error} />

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} />
      <div className="card flex items-center gap-4">
        <PlayerAvatar player={player || { name: stats?.name }} size={84} />
        <div className="min-w-0 flex-1">
          <SectionTitle>{stats?.name || player?.name}</SectionTitle>
          {canUpload && (
            <div className="mt-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="user"
                className="hidden"
                onChange={onPhotoChange}
              />
              <button
                type="button"
                className="btn btn-secondary"
                style={{ minHeight: 40, padding: '0.4rem 0.85rem' }}
                disabled={uploading}
                onClick={() => fileRef.current?.click()}
              >
                {uploading ? 'Uploading…' : player?.profile_photo ? 'Change photo' : 'Upload photo'}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="stat-grid">
        <StatTile label="Matches" value={stats.matches_played} />
        <StatTile label="Win %" value={`${stats.win_rate}%`} />
        <StatTile label="Goals" value={stats.goals} />
        <StatTile label="Assists" value={stats.assists} />
        <StatTile label="G+A" value={stats.goal_contributions} />
        <StatTile label="Clean sheets" value={stats.clean_sheets} />
        <StatTile label="POTW" value={stats.potw} />
        <StatTile label="Wins" value={stats.wins} />
        <StatTile label="Draws" value={stats.draws} />
        <StatTile label="Losses" value={stats.losses} />
      </div>

      <div>
        <h3 className="display text-2xl mb-2">Match history</h3>
        <div className="space-y-2">
          {history.map((m) => (
            <Link key={m.match_id} to={`/matches/${m.match_id}`} className="card block">
              <div className="flex justify-between gap-3">
                <div>
                  <p className="font-semibold">{m.match_date}</p>
                  <p className="text-sm text-[var(--color-muted)]">
                    {m.team} vs {m.opponent} · {m.score}
                  </p>
                </div>
                <span className="display text-3xl text-[var(--color-lime)]">{m.result}</span>
              </div>
              <p className="text-xs text-[var(--color-muted)] mt-2">
                G {m.goals} · A {m.assists}
                {m.clean_sheet ? ' · CS' : ''}
                {m.potw ? ' · POTW' : ''}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
