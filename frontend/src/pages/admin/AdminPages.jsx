import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { matchesApi, playersApi, statsApi } from '../../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle, StatTile } from '../../components/ui'
import PlayerAvatar from '../../components/PlayerAvatar'

function unwrapList(data) {
  if (Array.isArray(data)) return data
  return data?.results || []
}

function teamSideMap(match) {
  const map = { A: [], B: [] }
  for (const team of match?.teams || []) {
    map[team.side] = team.roster.map((r) => r.player)
  }
  return map
}

const SETUP_STEPS = [
  { id: 1, label: 'Squad' },
  { id: 2, label: 'Teams' },
]

const RESULT_STEPS = [
  { id: 3, label: 'Score' },
  { id: 4, label: 'Goals' },
  { id: 5, label: 'Finish' },
]

const MIN_SQUAD = 10
const MAX_SQUAD = 14

function isValidSquadCount(n) {
  return n >= MIN_SQUAD && n <= MAX_SQUAD && n % 2 === 0
}

function detectPhase(match) {
  if (!match) return 'setup'
  const hasTeams = (match.teams || []).length === 2
    && match.teams.every((t) => (t.roster || []).length > 0)
  const hasScore = match.team_a_score != null && match.team_b_score != null
  if (hasScore || (match.goals || []).length > 0) {
    return 'results'
  }
  if (hasTeams) return 'ready'
  return 'setup'
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
              <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">Latest match</p>
              <p className="display text-4xl mt-1">{data.latest_match.score}</p>
              <p className="text-sm text-[var(--color-muted)] mt-1">{data.latest_match.match_date}</p>
              {data.latest_match.potw && (
                <p className="mt-2">
                  <span className="badge">POTW</span> {data.latest_match.potw}
                </p>
              )}
              <Link className="btn btn-secondary mt-4 w-full" to={`/admin/matches/${data.latest_match.id}`}>
                Open match
              </Link>
            </div>
          )}

          <div className="grid gap-3">
            {[
              ['Top scorer', data.top_scorer, 'goals'],
              ['Top assister', data.top_assister, 'assists'],
              ['Clean sheets', data.most_clean_sheets, 'clean_sheets'],
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
            <button
              type="button"
              className="btn btn-secondary shrink-0"
              style={{ minHeight: 36, padding: '0.3rem 0.7rem' }}
              disabled={busyId === p.id}
              onClick={() => toggleActive(p)}
            >
              {p.is_active ? 'Deactivate' : 'Activate'}
            </button>
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
      <SectionTitle>New match</SectionTitle>
      <ErrorBanner message={error} />
      <form className="card space-y-3" onSubmit={onSubmit}>
        <p className="text-sm text-[var(--color-muted)]">
          Step 1 of match entry — pick the Monday date. Players can RSVP; you’ll confirm a 10–14 player squad next.
        </p>
        <div className="field">
          <label>Monday date</label>
          <input type="date" value={matchDate} onChange={(e) => setMatchDate(e.target.value)} required />
        </div>
        <button className="btn btn-primary w-full" disabled={saving} type="submit">
          {saving ? 'Creating…' : 'Continue to squad'}
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
  const [selected, setSelected] = useState([])
  const [scoreA, setScoreA] = useState(0)
  const [scoreB, setScoreB] = useState(0)
  const [goals, setGoals] = useState([])
  const [ratings, setRatings] = useState(null)
  const [manualA, setManualA] = useState([])
  const [manualB, setManualB] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(1)
  const [phase, setPhase] = useState('setup') // setup | ready | results

  const sides = useMemo(() => teamSideMap(match), [match])
  const playerById = useMemo(() => {
    const map = {}
    for (const p of players) map[p.id] = p
    for (const p of match?.participants?.map((x) => x.player) || []) map[p.id] = p
    return map
  }, [players, match])

  const unassigned = useMemo(() => {
    const taken = new Set([...manualA, ...manualB])
    return (match?.participants || [])
      .map((x) => x.player)
      .filter((p) => !taken.has(p.id))
  }, [match, manualA, manualB])

  async function reload() {
    const [m, p] = await Promise.all([matchesApi.get(id), playersApi.list({ is_active: true })])
    setMatch(m)
    const list = unwrapList(p)
    setPlayers(list)
    const participantIds = m.participants.map((x) => x.player.id)
    setSelected(participantIds.length ? participantIds : list.map((x) => x.id))
    setScoreA(m.team_a_score ?? 0)
    setScoreB(m.team_b_score ?? 0)
    const mapped = teamSideMap(m)
    setManualA(mapped.A.map((x) => x.id))
    setManualB(mapped.B.map((x) => x.id))
    setGoals(
      m.goals.map((g) => ({
        scoring_team: g.scoring_team_side,
        scorer_id: g.scorer.id,
        assister_id: g.assister?.id ?? null,
      })),
    )
    const nextPhase = detectPhase(m)
    setPhase(nextPhase)
    if (nextPhase === 'setup') {
      setStep(m.participants?.length ? 2 : 1)
    } else if (nextPhase === 'results') {
      if ((m.goals || []).length) setStep(5)
      else if (m.team_a_score != null) setStep(4)
      else setStep(3)
    }
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message))
  }, [id])

  function togglePlayer(playerId) {
    setSelected((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  async function saveParticipants() {
    setBusy(true)
    setError('')
    try {
      const m = await matchesApi.setParticipants(id, selected)
      setMatch(m)
      setManualA([])
      setManualB([])
      setStep(2)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function generate(method) {
    setBusy(true)
    setError('')
    try {
      const m = await matchesApi.generateTeams(id, method)
      setMatch(m)
      setRatings(m.team_ratings || null)
      const mapped = teamSideMap(m)
      setManualA(mapped.A.map((x) => x.id))
      setManualB(mapped.B.map((x) => x.id))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function assignManual(playerId, side) {
    const squadCount = match?.participants?.length || selected.length
    const teamCap = Math.max(Math.floor(squadCount / 2), 5)
    setManualA((prev) => prev.filter((x) => x !== playerId))
    setManualB((prev) => prev.filter((x) => x !== playerId))
    if (side === 'A') {
      setManualA((prev) => (prev.length >= teamCap ? prev : [...prev, playerId]))
    }
    if (side === 'B') {
      setManualB((prev) => (prev.length >= teamCap ? prev : [...prev, playerId]))
    }
  }

  function clearAssignment(playerId) {
    setManualA((prev) => prev.filter((x) => x !== playerId))
    setManualB((prev) => prev.filter((x) => x !== playerId))
  }

  async function saveManualTeams() {
    setBusy(true)
    setError('')
    try {
      const m = await matchesApi.setTeams(id, manualA, manualB)
      setMatch(m)
      setRatings(null)
      setPhase('ready')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function rebuildGoalSlots(a, b) {
    const total = Number(a) + Number(b)
    setGoals((prev) => {
      const next = [...prev]
      while (next.length < total) {
        next.push({ scoring_team: 'A', scorer_id: '', assister_id: null })
      }
      return next.slice(0, total)
    })
  }

  async function saveScore() {
    setBusy(true)
    setError('')
    try {
      const m = await matchesApi.setScore(id, Number(scoreA), Number(scoreB))
      setMatch(m)
      rebuildGoalSlots(scoreA, scoreB)
      setStep(4)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function saveGoals() {
    setBusy(true)
    setError('')
    try {
      const payload = goals.map((g, index) => ({
        scoring_team: g.scoring_team,
        scorer_id: Number(g.scorer_id),
        assister_id: g.assister_id ? Number(g.assister_id) : null,
        order: index + 1,
      }))
      const m = await matchesApi.setGoals(id, payload)
      setMatch(m)
      setStep(5)
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
      setPhase('results')
      setStep(3)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!match) return <LoadingState />

  const participantPlayers = match.participants.map((p) => p.player)
  const scorersFor = (side) => sides[side] || []
  const teamCap = Math.max(Math.floor((match.participants.length || selected.length) / 2), 5)
  const teamsReady = sides.A?.length === teamCap && sides.B?.length === teamCap && teamCap >= 5
  const availabilityByPlayer = Object.fromEntries(
    (match.availabilities || []).map((a) => [a.player.id, a.status]),
  )
  const availableIds = players
    .filter((p) => availabilityByPlayer[p.id] === 'AVAILABLE')
    .map((p) => p.id)

  return (
    <div className="space-y-4">
      <SectionTitle>Match day</SectionTitle>
      <p className="text-sm text-[var(--color-muted)] -mt-2">
        {match.match_date} · {match.status}{match.is_finalized ? ' · Finalized' : ''}
        {phase === 'setup' ? ' · Before kickoff' : ''}
        {phase === 'ready' ? ' · Teams set — play first' : ''}
        {phase === 'results' ? ' · After the match' : ''}
      </p>
      <ErrorBanner message={error} />

      {match.is_finalized ? (
        <div className="card space-y-3">
          <p>Finalized — stats, Player of the Match, Player of the Week, and Team of the Week are live.</p>
          <Link className="btn btn-primary w-full" to="/awards">View awards</Link>
          <Link className="btn btn-secondary w-full" to={`/matches/${match.id}`}>View match</Link>
          <button type="button" className="btn btn-danger w-full" onClick={reopen} disabled={busy}>
            Reopen for corrections
          </button>
        </div>
      ) : (
        <>
          {phase === 'setup' && (
            <div className="wizard-steps">
              {SETUP_STEPS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`wizard-step ${step === s.id ? 'active' : ''}`}
                  onClick={() => setStep(s.id)}
                >
                  <span className="num">Before · {s.id}</span>
                  <span className="label">{s.label}</span>
                </button>
              ))}
            </div>
          )}

          {phase === 'results' && (
            <div className="wizard-steps">
              {RESULT_STEPS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`wizard-step ${step === s.id ? 'active' : ''}`}
                  onClick={() => setStep(s.id)}
                >
                  <span className="num">After · {s.id - 2}</span>
                  <span className="label">{s.label}</span>
                </button>
              ))}
            </div>
          )}

          {phase === 'ready' && (
            <div className="card space-y-4">
              <h3 className="font-bold">Teams locked — go play</h3>
              <p className="text-sm text-[var(--color-muted)]">
                Squad and teams are set. Come back after the match to enter the score, goals, and assists.
                Player of the Week and Team of the Week are calculated automatically when you finalize.
              </p>
              <div className="team-board">
                {['A', 'B'].map((side) => (
                  <div key={side} className="team-column">
                    <p className="font-bold mb-2">Team {side}</p>
                    {(sides[side] || []).map((p) => (
                      <div key={p.id} className="player-chip" style={{ cursor: 'default' }}>
                        <PlayerAvatar player={p} size={32} />
                        <span className="text-sm truncate">{p.name}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="btn btn-primary w-full"
                onClick={() => {
                  setPhase('results')
                  setStep(3)
                }}
              >
                Enter match results
              </button>
              <button
                type="button"
                className="btn btn-secondary w-full"
                onClick={() => {
                  setPhase('setup')
                  setStep(2)
                }}
              >
                Edit teams
              </button>
              <Link className="btn btn-secondary w-full" to="/admin/matches">
                Back to matches
              </Link>
            </div>
          )}

          {phase === 'setup' && step === 1 && (
            <div className="card space-y-3">
              <h3 className="font-bold">Confirm tonight’s squad</h3>
              <p className="text-sm text-[var(--color-muted)]">
                Pick an even number between {MIN_SQUAD} and {MAX_SQUAD} (5v5 to 7v7). Player RSVPs show below.
              </p>
              <div className="flex gap-2 flex-wrap">
                <button type="button" className="btn btn-secondary flex-1" onClick={() => setSelected(players.map((p) => p.id).slice(0, MAX_SQUAD))}>
                  Select all
                </button>
                <button
                  type="button"
                  className="btn btn-secondary flex-1"
                  onClick={() => setSelected(availableIds.slice(0, MAX_SQUAD))}
                  disabled={!availableIds.length}
                >
                  Use RSVPs ({availableIds.length})
                </button>
                <button type="button" className="btn btn-secondary flex-1" onClick={() => setSelected([])}>
                  Clear
                </button>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {players.map((p) => {
                  const rsvp = availabilityByPlayer[p.id]
                  return (
                    <button
                      key={p.id}
                      type="button"
                      className={`player-chip ${selected.includes(p.id) ? 'selected' : ''}`}
                      onClick={() => togglePlayer(p.id)}
                    >
                      <PlayerAvatar player={p} size={40} />
                      <span className="font-semibold flex-1 text-left">{p.name}</span>
                      <span className="text-xs text-[var(--color-muted)]">
                        {rsvp === 'AVAILABLE' ? 'RSVP in' : rsvp === 'UNAVAILABLE' ? 'RSVP out' : 'No RSVP'}
                      </span>
                    </button>
                  )
                })}
              </div>
              <p className={`text-sm ${isValidSquadCount(selected.length) ? 'text-[var(--color-muted)]' : 'text-[var(--color-danger)]'}`}>
                {selected.length} selected · need even {MIN_SQUAD}–{MAX_SQUAD}
                {isValidSquadCount(selected.length) ? ` → ${selected.length / 2}v${selected.length / 2}` : ''}
              </p>
              <button
                type="button"
                className="btn btn-primary w-full"
                disabled={busy || !isValidSquadCount(selected.length)}
                onClick={saveParticipants}
              >
                Save squad & continue
              </button>
            </div>
          )}

          {phase === 'setup' && step === 2 && (
            <div className="space-y-3">
              <div className="card space-y-3">
                <h3 className="font-bold">Build teams</h3>
                <p className="text-sm text-[var(--color-muted)]">
                  Set teams now, then stop — results are entered after you play.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => generate('random')}>Random</button>
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => generate('balanced')}>Balanced</button>
                  <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => generate('random')}>Regen</button>
                </div>
                {ratings && (
                  <p className="text-sm text-[var(--color-gold)]">
                    Strength A {ratings.team_a_rating} · B {ratings.team_b_rating}
                  </p>
                )}
              </div>

              <div className="team-board">
                <div className="team-column">
                  <p className="font-bold mb-2">Team A · {manualA.length}/{teamCap}</p>
                  {manualA.map((pid) => {
                    const p = playerById[pid]
                    if (!p) return null
                    return (
                      <button key={pid} type="button" className="player-chip" onClick={() => clearAssignment(pid)}>
                        <PlayerAvatar player={p} size={32} />
                        <span className="text-sm truncate">{p.name.split(' ')[0]}</span>
                      </button>
                    )
                  })}
                </div>
                <div className="team-column">
                  <p className="font-bold mb-2">Team B · {manualB.length}/{teamCap}</p>
                  {manualB.map((pid) => {
                    const p = playerById[pid]
                    if (!p) return null
                    return (
                      <button key={pid} type="button" className="player-chip" onClick={() => clearAssignment(pid)}>
                        <PlayerAvatar player={p} size={32} />
                        <span className="text-sm truncate">{p.name.split(' ')[0]}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {unassigned.length > 0 && (
                <div className="card space-y-2">
                  <p className="font-semibold">Unassigned ({unassigned.length})</p>
                  {unassigned.map((p) => (
                    <div key={p.id} className="flex items-center gap-2">
                      <PlayerAvatar player={p} size={36} />
                      <span className="flex-1 text-sm font-semibold truncate">{p.name}</span>
                      <button type="button" className="btn btn-secondary" style={{ minHeight: 36, padding: '0.25rem 0.55rem' }} onClick={() => assignManual(p.id, 'A')}>A</button>
                      <button type="button" className="btn btn-secondary" style={{ minHeight: 36, padding: '0.25rem 0.55rem' }} onClick={() => assignManual(p.id, 'B')}>B</button>
                    </div>
                  ))}
                </div>
              )}

              <button
                type="button"
                className="btn btn-primary w-full"
                disabled={busy || manualA.length !== teamCap || manualB.length !== teamCap}
                onClick={saveManualTeams}
              >
                Lock teams & wait for kickoff
              </button>
              {teamsReady && (
                <button
                  type="button"
                  className="btn btn-secondary w-full"
                  onClick={() => setPhase('ready')}
                >
                  Teams already saved — continue
                </button>
              )}
            </div>
          )}

          {phase === 'results' && step === 3 && (
            <div className="card space-y-4">
              <h3 className="font-bold">Final score</h3>
              <p className="text-sm text-[var(--color-muted)]">Enter this after the game ends.</p>
              <div className="flex items-center justify-center gap-4">
                <div className="text-center">
                  <p className="text-xs text-[var(--color-muted)] mb-1">Team A</p>
                  <input className="score-input" type="number" min="0" value={scoreA} onChange={(e) => setScoreA(e.target.value)} />
                </div>
                <span className="display text-4xl">—</span>
                <div className="text-center">
                  <p className="text-xs text-[var(--color-muted)] mb-1">Team B</p>
                  <input className="score-input" type="number" min="0" value={scoreB} onChange={(e) => setScoreB(e.target.value)} />
                </div>
              </div>
              <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={saveScore}>
                Save score & enter goals
              </button>
            </div>
          )}

          {phase === 'results' && step === 4 && (
            <div className="card space-y-3">
              <h3 className="font-bold">Goals & assists ({goals.length})</h3>
              <p className="text-sm text-[var(--color-muted)]">One row per goal — scorer + optional assist.</p>
              {goals.map((g, index) => (
                <div key={index} className="grid gap-2 border-b border-white/10 pb-3">
                  <p className="text-xs text-[var(--color-muted)]">Goal {index + 1}</p>
                  <select
                    value={g.scoring_team}
                    onChange={(e) => {
                      const next = [...goals]
                      next[index] = { ...next[index], scoring_team: e.target.value, scorer_id: '' }
                      setGoals(next)
                    }}
                  >
                    <option value="A">Team A</option>
                    <option value="B">Team B</option>
                  </select>
                  <select
                    value={g.scorer_id}
                    onChange={(e) => {
                      const next = [...goals]
                      next[index] = { ...next[index], scorer_id: e.target.value }
                      setGoals(next)
                    }}
                  >
                    <option value="">Scorer</option>
                    {scorersFor(g.scoring_team).map((p) => (
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
                    {participantPlayers.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              ))}
              <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={saveGoals}>
                Save goals
              </button>
            </div>
          )}

          {phase === 'results' && step === 5 && (
            <div className="card space-y-3">
              <h3 className="font-bold">Finalize</h3>
              <p className="display text-5xl text-center text-[var(--color-lime)]">
                {match.team_a_score} — {match.team_b_score}
              </p>
              <p className="text-sm text-center text-[var(--color-muted)]">
                {match.goals.length} goals recorded. Finalizing will update career stats and
                automatically select Player of the Match, Player of the Week, and Team of the
                Week from tonight's performance.
              </p>
              <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={finalize}>
                Finalize match
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
