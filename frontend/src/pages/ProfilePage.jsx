import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { playersApi } from '../services/endpoints'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, LoadingState, SectionTitle, StatTile } from '../components/ui'
import PlayerAvatar from '../components/PlayerAvatar'
import { POSITIONS } from '../constants'

function positionLabel(value) {
  return POSITIONS.find((p) => p.value === value)?.label || null
}

export default function ProfilePage({ self = false }) {
  const { id } = useParams()
  const { user, isAdmin, updateProfile, refreshAvatarPlayer } = useAuth()
  const playerId = self ? user?.player_id : Number(id)
  const [stats, setStats] = useState(null)
  const [player, setPlayer] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef(null)

  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editUsername, setEditUsername] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editPosition, setEditPosition] = useState('')
  const [editError, setEditError] = useState('')
  const [saving, setSaving] = useState(false)

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

  function startEdit() {
    setEditError('')
    setEditName(player?.name || '')
    setEditUsername(user?.username || '')
    setEditEmail(player?.email || user?.email || '')
    setEditPosition(player?.position || '')
    setEditing(true)
  }

  async function saveProfile(e) {
    e.preventDefault()
    setSaving(true)
    setEditError('')
    try {
      const payload = { name: editName, username: editUsername, email: editEmail }
      if (editPosition) payload.position = editPosition
      await updateProfile(payload)
      await load()
      if (self) refreshAvatarPlayer()
      setEditing(false)
    } catch (err) {
      setEditError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function onPhotoChange(e) {
    const file = e.target.files?.[0]
    if (!file || !playerId) return
    setUploading(true)
    setError('')
    try {
      const updated = await playersApi.uploadPhoto(playerId, file)
      setPlayer(updated)
      if (self) refreshAvatarPlayer()
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
          {player && (
            <p className="text-xs text-[var(--color-muted)]">
              {positionLabel(player.position) || (self ? 'No position set yet' : 'No position set')}
            </p>
          )}
          {canUpload && !self && (
            <div className="mt-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
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
          {self && (
            <button
              type="button"
              className="btn btn-secondary mt-2"
              style={{ minHeight: 40, padding: '0.4rem 0.85rem' }}
              onClick={() => (editing ? setEditing(false) : startEdit())}
            >
              {editing ? 'Cancel' : 'Edit profile'}
            </button>
          )}
        </div>
      </div>

      {self && editing && (
        <form className="card space-y-3" onSubmit={saveProfile}>
          <ErrorBanner message={editError} />
          <div className="field">
            <label>Photo</label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={onPhotoChange}
            />
            <button
              type="button"
              className="btn btn-secondary w-full"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? 'Uploading…' : player?.profile_photo ? 'Change photo' : 'Upload photo'}
            </button>
          </div>
          <div className="field">
            <label htmlFor="edit-name">Name</label>
            <input id="edit-name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="edit-username">Username</label>
            <input id="edit-username" value={editUsername} onChange={(e) => setEditUsername(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="edit-position">Position</label>
            <select id="edit-position" value={editPosition} onChange={(e) => setEditPosition(e.target.value)}>
              <option value="">Not set</option>
              {POSITIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit-email">Email</label>
            <input id="edit-email" type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} required />
          </div>
          <button className="btn btn-primary w-full" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      )}

      <div className="stat-grid">
        <StatTile label="Matches" value={stats.matches_played} />
        <StatTile label="Goals" value={stats.goals} />
        <StatTile label="Assists" value={stats.assists} />
        <StatTile label="G+A" value={stats.goal_contributions} />
        <StatTile label="POTW" value={stats.potw} />
      </div>

      <div>
        <h3 className="display text-2xl mb-2">Match history</h3>
        <div className="space-y-2">
          {history.map((m) => (
            <Link key={m.match_id} to={`/matches/${m.match_id}`} className="card block">
              <p className="font-semibold">{m.match_date}</p>
              <p className="text-xs text-[var(--color-muted)] mt-1">
                G {m.goals} · A {m.assists}
                {m.potw ? ' · POTW' : ''}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
