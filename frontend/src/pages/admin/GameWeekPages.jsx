import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { gameWeeksApi, gameWeekTeamsApi, matchesApi, playersApi } from '../../services/endpoints'
import { ErrorBanner, LoadingState, SectionTitle } from '../../components/ui'
import PlayerAvatar from '../../components/PlayerAvatar'

function unwrapList(data) {
  if (Array.isArray(data)) return data
  return data?.results || []
}

function TeamEditor({ team, players, gameWeekId, onSaved }) {
  const isNew = !team
  const [editing, setEditing] = useState(isNew)
  const [name, setName] = useState(team?.name || '')
  const [memberIds, setMemberIds] = useState((team?.players || []).map((p) => p.id))
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function toggleMember(playerId) {
    setMemberIds((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  async function save() {
    if (!name.trim()) {
      setError('Team name is required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      if (isNew) {
        await gameWeekTeamsApi.create({ game_week: gameWeekId, name, player_ids: memberIds })
      } else {
        await gameWeekTeamsApi.update(team.id, { name, player_ids: memberIds })
      }
      setEditing(false)
      await onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!window.confirm(`Delete team "${team.name}"?`)) return
    setSaving(true)
    setError('')
    try {
      await gameWeekTeamsApi.remove(team.id)
      await onSaved()
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <div className="card">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="font-bold">Team {team.name}</p>
            <p className="text-xs text-[var(--color-muted)]">{team.players.length} players</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn btn-secondary" style={{ minHeight: 32, padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="btn btn-danger" style={{ minHeight: 32, padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={remove} disabled={saving}>
              Delete
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card space-y-2">
      <ErrorBanner message={error} />
      <div className="field">
        <label>Team name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. A" />
      </div>
      <p className="text-xs text-[var(--color-muted)]">Roster — reused automatically for every fixture this team plays.</p>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {players.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`player-chip ${memberIds.includes(p.id) ? 'selected' : ''}`}
            onClick={() => toggleMember(p.id)}
          >
            <PlayerAvatar player={p} size={32} />
            <span className="font-semibold flex-1 text-left">{p.name}</span>
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {!isNew && (
          <button type="button" className="btn btn-secondary w-full" onClick={() => setEditing(false)} disabled={saving}>
            Cancel
          </button>
        )}
        <button type="button" className={`btn btn-primary w-full ${isNew ? 'col-span-2' : ''}`} onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save team'}
        </button>
      </div>
    </div>
  )
}

function FixtureCard({ index, fixture, teams, players, onSaved }) {
  const [goals, setGoals] = useState(
    fixture.goals.length
      ? fixture.goals.map((g) => ({ scorer_id: g.scorer.id, assister_id: g.assister?.id ?? null }))
      : [{ scorer_id: '', assister_id: null }],
  )
  const [teamAId, setTeamAId] = useState(fixture.team_a || '')
  const [teamBId, setTeamBId] = useState(fixture.team_b || '')
  const [teamAScore, setTeamAScore] = useState(fixture.team_a_score ?? '')
  const [teamBScore, setTeamBScore] = useState(fixture.team_b_score ?? '')
  const [teamAIds, setTeamAIds] = useState(
    fixture.participants.filter((row) => row.side === 'A').map((row) => row.player.id),
  )
  const [teamBIds, setTeamBIds] = useState(
    fixture.participants.filter((row) => row.side === 'B').map((row) => row.player.id),
  )
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function selectTeam(side, teamId) {
    const team = teams.find((t) => String(t.id) === String(teamId))
    const rosterIds = team ? team.players.map((p) => p.id) : []
    if (side === 'A') {
      setTeamAId(teamId)
      setTeamAIds(rosterIds)
    } else {
      setTeamBId(teamId)
      setTeamBIds(rosterIds)
    }
  }

  function toggleRoster(side, playerId) {
    const setter = side === 'A' ? setTeamAIds : setTeamBIds
    setter((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  function addGoalRow() {
    setGoals((prev) => [...prev, { scorer_id: '', assister_id: null }])
  }

  function removeGoalRow(idx) {
    setGoals((prev) => prev.filter((_, i) => i !== idx))
  }

  const fixturePlayerIds = new Set([...teamAIds, ...teamBIds])
  const fixturePlayers = fixturePlayerIds.size
    ? players.filter((p) => fixturePlayerIds.has(p.id))
    : players

  async function save() {
    setBusy(true)
    setError('')
    try {
      const payload = goals
        .filter((g) => g.scorer_id)
        .map((g, i) => ({
          scorer_id: Number(g.scorer_id),
          assister_id: g.assister_id ? Number(g.assister_id) : null,
          order: i + 1,
        }))
      await matchesApi.setGoals(fixture.id, {
        goals: payload,
        teamA: teamAIds,
        teamB: teamBIds,
        teamAScore: teamAScore !== '' ? Number(teamAScore) : null,
        teamBScore: teamBScore !== '' ? Number(teamBScore) : null,
        teamAGroup: teamAId || null,
        teamBGroup: teamBId || null,
      })
      await onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-bold">Fixture {index + 1}</h3>
        {fixture.is_finalized && <span className="badge">Finalized</span>}
      </div>
      <ErrorBanner message={error} />

      <div className="grid grid-cols-2 gap-2">
        <div className="field">
          <label>Team A</label>
          <select value={teamAId} onChange={(e) => selectTeam('A', e.target.value)}>
            <option value="">Choose team</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Team B</label>
          <select value={teamBId} onChange={(e) => selectTeam('B', e.target.value)}>
            <option value="">Choose team</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Score A</label>
          <input type="number" min="0" value={teamAScore} onChange={(e) => setTeamAScore(e.target.value)} />
        </div>
        <div className="field">
          <label>Score B</label>
          <input type="number" min="0" value={teamBScore} onChange={(e) => setTeamBScore(e.target.value)} />
        </div>
      </div>

      {(teamAId || teamBId) && (
        <p className="text-xs text-[var(--color-muted)]">
          Roster prefilled from each team — uncheck anyone who sat this fixture out.
        </p>
      )}
      {(teamAId || teamBId) && (
        <div className="grid gap-2 sm:grid-cols-2">
          {['A', 'B'].map((side) => {
            const teamId = side === 'A' ? teamAId : teamBId
            const team = teams.find((t) => String(t.id) === String(teamId))
            if (!team) return null
            const ids = side === 'A' ? teamAIds : teamBIds
            return (
              <div key={side} className="space-y-1 max-h-48 overflow-y-auto">
                {team.players.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`player-chip ${ids.includes(p.id) ? 'selected' : ''}`}
                    style={{ marginBottom: 0 }}
                    onClick={() => toggleRoster(side, p.id)}
                  >
                    <PlayerAvatar player={p} size={28} />
                    <span className="text-sm font-semibold flex-1 text-left truncate">{p.name}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      )}

      <div className="border-t border-white/10 pt-3 space-y-2">
        <h4 className="font-bold text-sm">Goals & assists ({goals.filter((g) => g.scorer_id).length})</h4>
        {goals.map((g, i) => (
          <div key={i} className="grid gap-2 border-b border-white/10 pb-2">
            <div className="flex items-center justify-between">
              <p className="text-xs text-[var(--color-muted)]">Goal {i + 1}</p>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ minHeight: 26, padding: '0.1rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => removeGoalRow(i)}
              >
                Remove
              </button>
            </div>
            <select
              value={g.scorer_id}
              onChange={(e) => {
                const next = [...goals]
                next[i] = { ...next[i], scorer_id: e.target.value }
                setGoals(next)
              }}
            >
              <option value="">Scorer</option>
              {fixturePlayers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={g.assister_id ?? ''}
              onChange={(e) => {
                const next = [...goals]
                next[i] = { ...next[i], assister_id: e.target.value ? e.target.value : null }
                setGoals(next)
              }}
            >
              <option value="">Assist — None</option>
              {fixturePlayers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        ))}
        <button type="button" className="btn btn-secondary w-full" onClick={addGoalRow}>
          Add goal
        </button>
      </div>

      <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={save}>
        {busy ? 'Saving…' : 'Save fixture'}
      </button>
    </div>
  )
}

export function AdminGameWeekPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [gameWeek, setGameWeek] = useState(null)
  const [players, setPlayers] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function reload() {
    const [gw, p] = await Promise.all([gameWeeksApi.get(id), playersApi.list({ is_active: true })])
    setGameWeek(gw)
    setPlayers(unwrapList(p))
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message))
  }, [id])

  async function addFixture() {
    setBusy(true)
    setError('')
    try {
      await matchesApi.create({ match_date: gameWeek.week_date, game_week: gameWeek.id })
      await reload()
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
      await gameWeeksApi.finalize(id)
      await reload()
      navigate('/awards')
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
      await gameWeeksApi.reopen(id)
      await reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!gameWeek) return <LoadingState />

  return (
    <div className="space-y-4">
      <SectionTitle>Game week</SectionTitle>
      <p className="text-sm text-[var(--color-muted)] -mt-2">
        {gameWeek.week_date} · {gameWeek.status}
      </p>
      <ErrorBanner message={error} />

      {gameWeek.is_finalized ? (
        <div className="card space-y-3">
          <p>Finalized — stats, Player of the Week, and Team of the Week are live for the whole evening.</p>
          <Link className="btn btn-primary w-full" to="/awards">View awards</Link>
          <Link className="btn btn-secondary w-full" to={`/game-weeks/${gameWeek.id}`}>View stats</Link>
          <button type="button" className="btn btn-danger w-full" onClick={reopen} disabled={busy}>
            Reopen for corrections
          </button>
        </div>
      ) : (
        <>
          <div>
            <h3 className="font-bold mb-2">Teams</h3>
            <div className="space-y-2">
              {gameWeek.teams.map((t) => (
                <TeamEditor key={t.id} team={t} players={players} gameWeekId={gameWeek.id} onSaved={reload} />
              ))}
              <TeamEditor team={null} players={players} gameWeekId={gameWeek.id} onSaved={reload} />
            </div>
          </div>

          <div>
            <h3 className="font-bold mb-2">Fixtures</h3>
            <div className="space-y-3">
              {gameWeek.fixtures.map((fixture, index) => (
                <FixtureCard
                  key={fixture.id}
                  index={index}
                  fixture={fixture}
                  teams={gameWeek.teams}
                  players={players}
                  onSaved={reload}
                />
              ))}
              <button type="button" className="btn btn-secondary w-full" onClick={addFixture} disabled={busy}>
                Add fixture
              </button>
            </div>
          </div>

          <button type="button" className="btn btn-primary w-full" onClick={finalize} disabled={busy}>
            Finalize game week
          </button>
        </>
      )}
    </div>
  )
}
