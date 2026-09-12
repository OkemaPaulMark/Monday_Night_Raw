import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { matchesApi, playersApi, statsApi } from '../../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle, StatTile } from '../../components/ui'
import PlayerAvatar from '../../components/PlayerAvatar'

function unwrapList(data) {
  if (Array.isArray(data)) return data
  return data?.results || []
}

function PowerIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />
      <line x1="12" y1="2" x2="12" y2="12" />
    </svg>
  )
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

export function AdminDashboardPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    statsApi.dashboard().then(setData).catch((e) => setError(e.message))
  }, [])

  if (!data && !error) return <LoadingState />

  return (
    <div className="space-y-5">
      <SectionTitle>Admin</SectionTitle>
      <ErrorBanner message={error} />
      {data && (
        <>
          <div className="stat-grid">
            <StatTile label="Players" value={data.total_players} />
            <StatTile label="Matches" value={data.total_matches} />
          </div>

          {data.latest_match && (
            <div className="card">
              <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">Latest matchday</p>
              <p className="display text-4xl mt-1">{data.latest_match.goals} goals</p>
              <p className="text-sm text-[var(--color-muted)] mt-1">{data.latest_match.match_date}</p>
              {data.latest_match.potw && (
                <p className="mt-2">
                  <span className="badge">POTW</span> {data.latest_match.potw}
                </p>
              )}
              <Link className="btn btn-secondary mt-4 w-full" to={`/admin/matches/${data.latest_match.id}`}>
                Open
              </Link>
            </div>
          )}

          <div className="grid gap-3">
            {[
              ['Top scorer', data.top_scorer, 'goals'],
              ['Top assister', data.top_assister, 'assists'],
              ['Most POTW', data.most_potw, 'potw'],
            ].map(([label, row, metric]) => (
              <div key={label} className="card flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  {row && (
                    <PlayerAvatar
                      player={{ name: row.name, profile_photo: row.profile_photo }}
                      size={40}
                    />
                  )}
                  <div className="min-w-0">
                    <p className="text-xs text-[var(--color-muted)]">{label}</p>
                    <p className="font-semibold truncate">{row?.name || '—'}</p>
                  </div>
                </div>
                <p className="display text-3xl text-[var(--color-gold)] shrink-0">
                  {row ? row[metric] : '—'}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function AdminPlayersPage() {
  const [players, setPlayers] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function load() {
    try {
      const data = await playersApi.list()
      setPlayers(unwrapList(data))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggleActive(p) {
    setError('')
    setBusyId(p.id)
    try {
      await playersApi.update(p.id, { is_active: !p.is_active })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function onDelete(p) {
    if (!window.confirm(`Delete ${p.name}? This can't be undone.`)) return
    setError('')
    setBusyId(p.id)
    try {
      await playersApi.remove(p.id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4">
      <SectionTitle>Players</SectionTitle>
      <ErrorBanner message={error} />

      <div className="space-y-2">
        {players.map((p) => (
          <div key={p.id} className="player-chip" style={{ marginBottom: 0 }}>
            <Link to={`/players/${p.id}`} className="flex items-center gap-2 min-w-0 flex-1" style={{ color: 'inherit' }}>
              <PlayerAvatar player={p} size={44} />
              <div className="min-w-0">
                <p className="font-semibold truncate">{p.name}</p>
                <p className="text-xs text-[var(--color-muted)]">
                  {p.email || 'No email'} · {p.is_active ? 'Active' : 'Inactive'}
                </p>
              </div>
            </Link>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                className="btn btn-secondary icon-btn"
                disabled={busyId === p.id}
                onClick={() => toggleActive(p)}
                title={p.is_active ? 'Deactivate' : 'Activate'}
                aria-label={p.is_active ? 'Deactivate' : 'Activate'}
              >
                <PowerIcon style={{ opacity: p.is_active ? 1 : 0.4 }} />
              </button>
              <button
                type="button"
                className="btn btn-danger icon-btn"
                disabled={busyId === p.id}
                onClick={() => onDelete(p)}
                title="Delete"
                aria-label="Delete"
              >
                <TrashIcon />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function CreateMatchPage() {
  const navigate = useNavigate()
  const [matchDate, setMatchDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const match = await matchesApi.create({ match_date: matchDate })
      navigate(`/admin/matches/${match.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <SectionTitle>New matchday</SectionTitle>
      <ErrorBanner message={error} />
      <form className="card space-y-3" onSubmit={onSubmit}>
        <p className="text-sm text-[var(--color-muted)]">
          Pick the date, then log who scored and who assisted — no squad
          list or teams needed, just pick from your registered players.
        </p>
        <div className="field">
          <label>Date</label>
          <input type="date" value={matchDate} onChange={(e) => setMatchDate(e.target.value)} required />
        </div>
        <button className="btn btn-primary w-full" disabled={saving} type="submit">
          {saving ? 'Creating…' : 'Continue to goals & assists'}
        </button>
      </form>
    </div>
  )
}

export function MatchWizardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [match, setMatch] = useState(null)
  const [players, setPlayers] = useState([])
  const [goals, setGoals] = useState([])
  const [alsoPlayed, setAlsoPlayed] = useState([])
  const [trackTeams, setTrackTeams] = useState(false)
  const [teamA, setTeamA] = useState([])
  const [teamB, setTeamB] = useState([])
  const [teamAScore, setTeamAScore] = useState('')
  const [teamBScore, setTeamBScore] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function reload() {
    const [m, p] = await Promise.all([matchesApi.get(id), playersApi.list({ is_active: true })])
    setMatch(m)
    setPlayers(unwrapList(p))
    setGoals(
      m.goals.length
        ? m.goals.map((g) => ({ scorer_id: g.scorer.id, assister_id: g.assister?.id ?? null }))
        : [{ scorer_id: '', assister_id: null }],
    )
    // Anyone recorded as a participant who wasn't a scorer/assister must
    // have been explicitly marked "also played" last time.
    const involved = new Set()
    for (const g of m.goals) {
      involved.add(g.scorer.id)
      if (g.assister) involved.add(g.assister.id)
    }
    setAlsoPlayed(
      m.participants.map((row) => row.player.id).filter((pid) => !involved.has(pid)),
    )
    const sideA = m.participants.filter((row) => row.side === 'A').map((row) => row.player.id)
    const sideB = m.participants.filter((row) => row.side === 'B').map((row) => row.player.id)
    setTeamA(sideA)
    setTeamB(sideB)
    setTeamAScore(m.team_a_score ?? '')
    setTeamBScore(m.team_b_score ?? '')
    setTrackTeams(m.has_team_scores || sideA.length > 0 || sideB.length > 0)
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message))
  }, [id])

  function addGoalRow() {
    setGoals((prev) => [...prev, { scorer_id: '', assister_id: null }])
  }

  function removeGoalRow(index) {
    setGoals((prev) => prev.filter((_, i) => i !== index))
  }

  function toggleAlsoPlayed(playerId) {
    setAlsoPlayed((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  function assignTeam(playerId, side) {
    setTeamA((prev) => {
      if (side === 'A') {
        return prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId]
      }
      return prev.filter((x) => x !== playerId)
    })
    setTeamB((prev) => {
      if (side === 'B') {
        return prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId]
      }
      return prev.filter((x) => x !== playerId)
    })
  }

  const involvedInGoals = new Set(
    goals.flatMap((g) => [g.scorer_id, g.assister_id].filter(Boolean).map(Number)),
  )
  const alsoPlayedOptions = players.filter((p) => !involvedInGoals.has(p.id))

  async function saveGoals() {
    setBusy(true)
    setError('')
    try {
      const payload = goals
        .filter((g) => g.scorer_id)
        .map((g, index) => ({
          scorer_id: Number(g.scorer_id),
          assister_id: g.assister_id ? Number(g.assister_id) : null,
          order: index + 1,
        }))
      const alsoPlayedIds = alsoPlayed.filter((pid) => !involvedInGoals.has(pid))
      const m = await matchesApi.setGoals(id, {
        goals: payload,
        alsoPlayed: alsoPlayedIds,
        teamA: trackTeams ? teamA : [],
        teamB: trackTeams ? teamB : [],
        teamAScore: trackTeams && teamAScore !== '' ? Number(teamAScore) : null,
        teamBScore: trackTeams && teamBScore !== '' ? Number(teamBScore) : null,
      })
      setMatch(m)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function finalize() {
    setBusy(true)
    setError('')
    try {
      await saveGoals()
      const m = await matchesApi.finalize(id)
      setMatch(m)
      navigate(`/matches/${m.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function reopen() {
    setBusy(true)
    setError('')
    try {
      const m = await matchesApi.reopen(id)
      setMatch(m)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!match) return <LoadingState />

  return (
    <div className="space-y-4">
      <SectionTitle>Matchday</SectionTitle>
      <p className="text-sm text-[var(--color-muted)] -mt-2">
        {match.match_date} · {match.status}{match.is_finalized ? ' · Finalized' : ''}
      </p>
      <ErrorBanner message={error} />

      {match.is_finalized ? (
        <div className="card space-y-3">
          <p>Finalized — stats, Player of the Week, and Team of the Week are live.</p>
          <Link className="btn btn-primary w-full" to="/awards">View awards</Link>
          <Link className="btn btn-secondary w-full" to={`/matches/${match.id}`}>View stats</Link>
          <button type="button" className="btn btn-danger w-full" onClick={reopen} disabled={busy}>
            Reopen for corrections
          </button>
        </div>
      ) : (
        <div className="card space-y-3">
          <h3 className="font-bold">Goals & assists ({goals.filter((g) => g.scorer_id).length})</h3>
          <p className="text-sm text-[var(--color-muted)]">
            One row per goal — scorer + optional assist, from all registered players.
            No score, no squad list, no teams.
          </p>
          {goals.map((g, index) => (
            <div key={index} className="grid gap-2 border-b border-white/10 pb-3">
              <div className="flex items-center justify-between">
                <p className="text-xs text-[var(--color-muted)]">Goal {index + 1}</p>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ minHeight: 28, padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                  onClick={() => removeGoalRow(index)}
                >
                  Remove
                </button>
              </div>
              <select
                value={g.scorer_id}
                onChange={(e) => {
                  const next = [...goals]
                  next[index] = { ...next[index], scorer_id: e.target.value }
                  setGoals(next)
                }}
              >
                <option value="">Scorer</option>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <select
                value={g.assister_id ?? ''}
                onChange={(e) => {
                  const next = [...goals]
                  next[index] = {
                    ...next[index],
                    assister_id: e.target.value ? e.target.value : null,
                  }
                  setGoals(next)
                }}
              >
                <option value="">Assist — None</option>
                {players.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          ))}
          <button type="button" className="btn btn-secondary w-full" onClick={addGoalRow}>
            Add goal
          </button>

          <div className="border-t border-white/10 pt-3 space-y-2">
            <h3 className="font-bold">Also played ({alsoPlayed.filter((pid) => !involvedInGoals.has(pid)).length})</h3>
            <p className="text-sm text-[var(--color-muted)]">
              Anyone else who played but didn't score or assist — matters for Team
              of the Week, which always fills to 7 when enough people are marked here.
            </p>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {alsoPlayedOptions.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`player-chip ${alsoPlayed.includes(p.id) ? 'selected' : ''}`}
                  onClick={() => toggleAlsoPlayed(p.id)}
                >
                  <PlayerAvatar player={p} size={36} />
                  <span className="font-semibold flex-1 text-left">{p.name}</span>
                </button>
              ))}
              {alsoPlayedOptions.length === 0 && (
                <p className="text-sm text-[var(--color-muted)]">
                  Everyone registered is already a scorer or assister above.
                </p>
              )}
            </div>
          </div>

          <div className="border-t border-white/10 pt-3 space-y-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={trackTeams}
                onChange={(e) => setTrackTeams(e.target.checked)}
              />
              <span className="font-bold">Track teams & score</span>
            </label>
            <p className="text-sm text-[var(--color-muted)]">
              Optional — only if turnout split cleanly into two sides. Enables
              clean sheet / goals conceded stats for defenders and midfielders.
            </p>
            {trackTeams && (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <div className="field">
                    <label htmlFor="team-a-score">Team A score</label>
                    <input
                      id="team-a-score"
                      type="number"
                      min="0"
                      value={teamAScore}
                      onChange={(e) => setTeamAScore(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="team-b-score">Team B score</label>
                    <input
                      id="team-b-score"
                      type="number"
                      min="0"
                      value={teamBScore}
                      onChange={(e) => setTeamBScore(e.target.value)}
                    />
                  </div>
                </div>
                <p className="text-xs text-[var(--color-muted)]">
                  Tap a player to cycle: unassigned → Team A → Team B.
                </p>
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {players.map((p) => {
                    const side = teamA.includes(p.id) ? 'A' : teamB.includes(p.id) ? 'B' : null
                    return (
                      <div key={p.id} className="player-chip" style={{ marginBottom: 0 }}>
                        <PlayerAvatar player={p} size={36} />
                        <span className="font-semibold flex-1 text-left truncate">{p.name}</span>
                        <div className="flex gap-1 shrink-0">
                          <button
                            type="button"
                            className={`btn ${side === 'A' ? 'btn-primary' : 'btn-secondary'}`}
                            style={{ minHeight: 32, padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                            onClick={() => assignTeam(p.id, side === 'A' ? null : 'A')}
                          >
                            A
                          </button>
                          <button
                            type="button"
                            className={`btn ${side === 'B' ? 'btn-primary' : 'btn-secondary'}`}
                            style={{ minHeight: 32, padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                            onClick={() => assignTeam(p.id, side === 'B' ? null : 'B')}
                          >
                            B
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </div>

          <button type="button" className="btn btn-secondary w-full" disabled={busy} onClick={saveGoals}>
            Save goals
          </button>
          <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={finalize}>
            Finalize matchday
          </button>
        </div>
      )}
    </div>
  )
}
