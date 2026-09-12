import { useEffect, useMemo, useState } from 'react'
import { awardsApi, matchesApi } from '../services/endpoints'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, LoadingState, SectionTitle, EmptyState } from '../components/ui'
import TeamOfTheWeekFormation from '../components/TeamOfTheWeekFormation'
import PlayerStatsModal from '../components/PlayerStatsModal'
import PlayerAvatar from '../components/PlayerAvatar'
import { POSITIONS } from '../constants'

function positionLabel(value) {
  return POSITIONS.find((p) => p.value === value)?.label || 'No position'
}

function groupWeeklyByMatch(weekly) {
  const map = new Map()
  for (const award of weekly) {
    if (!award.match) continue
    const key = String(award.match)
    if (!map.has(key)) {
      map.set(key, {
        matchId: award.match,
        matchDate: award.match_date,
        awards: [],
      })
    }
    const group = map.get(key)
    if (!group.matchDate && award.match_date) {
      group.matchDate = award.match_date
    }
    group.awards.push(award)
  }
  // Newest match day first
  return [...map.values()].sort((a, b) => {
    const da = a.matchDate || ''
    const db = b.matchDate || ''
    return db.localeCompare(da)
  })
}

function formatMatchDay(dateStr) {
  if (!dateStr) return 'Unknown date'
  const d = new Date(`${dateStr}T12:00:00`)
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default function AwardsPage() {
  const { isAdmin } = useAuth()
  const [tab, setTab] = useState('weekly')
  const [weekly, setWeekly] = useState([])
  const [monthly, setMonthly] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedPlayerId, setSelectedPlayerId] = useState(null)
  const [selectedMatchId, setSelectedMatchId] = useState('')
  const [editingTotw, setEditingTotw] = useState(false)
  const [matchParticipants, setMatchParticipants] = useState([])
  const [manualIds, setManualIds] = useState([])
  const [totwError, setTotwError] = useState('')
  const [totwSaving, setTotwSaving] = useState(false)
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [w, m] = await Promise.all([
        awardsApi.weekly(),
        awardsApi.monthly({ year, month }),
      ])
      setWeekly(w)
      setMonthly(m)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [year, month])

  const weeklyGroups = useMemo(() => groupWeeklyByMatch(weekly), [weekly])

  // Default to latest match day whenever award data refreshes
  useEffect(() => {
    if (!weeklyGroups.length) {
      setSelectedMatchId('')
      return
    }
    const latestId = String(weeklyGroups[0].matchId)
    setSelectedMatchId((current) => {
      if (current && weeklyGroups.some((g) => String(g.matchId) === current)) {
        return current
      }
      return latestId
    })
  }, [weeklyGroups])

  async function generateMonthly() {
    try {
      await awardsApi.generateMonthly(year, month)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const selectedGroup = weeklyGroups.find(
    (g) => String(g.matchId) === String(selectedMatchId),
  )
  const potw = selectedGroup?.awards.find((a) => a.award_type === 'POTW')
  const totw = selectedGroup?.awards.find((a) => a.award_type === 'TOTW')

  useEffect(() => {
    setEditingTotw(false)
    setTotwError('')
  }, [selectedMatchId])

  async function startEditTotw() {
    setTotwError('')
    setManualIds((totw?.recipients || []).map((r) => r.player.id))
    setEditingTotw(true)
    try {
      const m = await matchesApi.get(selectedGroup.matchId)
      setMatchParticipants(m.participants.map((row) => row.player))
    } catch (e) {
      setTotwError(e.message)
    }
  }

  function toggleManualPlayer(playerId) {
    setManualIds((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  async function saveManualTotw() {
    setTotwSaving(true)
    setTotwError('')
    try {
      await awardsApi.setTotwRecipients(totw.id, manualIds)
      await load()
      setEditingTotw(false)
    } catch (e) {
      setTotwError(e.message)
    } finally {
      setTotwSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <SectionTitle>Awards</SectionTitle>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" className={`btn ${tab === 'weekly' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setTab('weekly')}>
          Weekly
        </button>
        <button type="button" className={`btn ${tab === 'monthly' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setTab('monthly')}>
          Monthly
        </button>
      </div>

      {tab === 'weekly' && weeklyGroups.length > 0 && (
        <div className="field">
          <label htmlFor="match-day">Match day</label>
          <select
            id="match-day"
            value={selectedMatchId}
            onChange={(e) => setSelectedMatchId(e.target.value)}
          >
            {weeklyGroups.map((g, index) => (
              <option key={g.matchId} value={String(g.matchId)}>
                {formatMatchDay(g.matchDate)}
                {index === 0 ? ' · Latest' : ''}
              </option>
            ))}
          </select>
        </div>
      )}

      {tab === 'monthly' && (
        <div className="card grid grid-cols-2 gap-3">
          <div className="field">
            <label>Year</label>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Month</label>
            <input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} />
          </div>
          {isAdmin && (
            <button type="button" className="btn btn-secondary col-span-2" onClick={generateMonthly}>
              Generate / refresh monthly awards
            </button>
          )}
        </div>
      )}

      <ErrorBanner message={error} />
      {loading ? (
        <LoadingState />
      ) : tab === 'weekly' ? (
        !selectedGroup ? (
          <EmptyState>No weekly awards yet.</EmptyState>
        ) : (
          <div className="space-y-3">
            <div className="card">
              <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className="font-bold">Player of the Week</h3>
                {potw?.is_confirmed ? <span className="badge">Confirmed</span> : null}
              </div>
              <p className="text-xs text-[var(--color-muted)] mb-3">
                {formatMatchDay(selectedGroup.matchDate)}
              </p>
              <div className="space-y-2">
                {(potw?.recipients || []).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className="player-chip"
                    onClick={() => setSelectedPlayerId(r.player.id)}
                  >
                    <PlayerAvatar player={r.player} size={40} />
                    <div className="min-w-0 text-left">
                      <p className="font-semibold truncate">{r.player.name}</p>
                    </div>
                  </button>
                ))}
                {!potw && <p className="text-sm text-[var(--color-muted)]">No POTW recorded.</p>}
              </div>
            </div>

            {totw ? (
              <div className="card space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold">Team of the Week</h3>
                  <div className="flex items-center gap-2">
                    <span className="badge">{totw.recipients.length}-a-side XI</span>
                    {isAdmin && !editingTotw && (
                      <button type="button" className="btn btn-secondary" style={{ minHeight: 32, padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={startEditTotw}>
                        Edit lineup
                      </button>
                    )}
                  </div>
                </div>

                {editingTotw ? (
                  <div className="space-y-3">
                    <ErrorBanner message={totwError} />
                    <p className="text-sm text-[var(--color-muted)]">
                      Pick who's in the Team of the Week for this match day. Tap in
                      the order you want them ranked.
                    </p>
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {matchParticipants.map((p) => {
                        const idx = manualIds.indexOf(p.id)
                        return (
                          <button
                            key={p.id}
                            type="button"
                            className={`player-chip ${idx >= 0 ? 'selected' : ''}`}
                            onClick={() => toggleManualPlayer(p.id)}
                          >
                            <PlayerAvatar player={p} size={36} />
                            <div className="min-w-0 flex-1 text-left">
                              <p className="font-semibold truncate">{p.name}</p>
                              <p className="text-xs text-[var(--color-muted)]">{positionLabel(p.position)}</p>
                            </div>
                            {idx >= 0 && <span className="badge">#{idx + 1}</span>}
                          </button>
                        )
                      })}
                      {matchParticipants.length === 0 && (
                        <p className="text-sm text-[var(--color-muted)]">No participants recorded for this match.</p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" className="btn btn-secondary w-full" onClick={() => setEditingTotw(false)} disabled={totwSaving}>
                        Cancel
                      </button>
                      <button type="button" className="btn btn-primary w-full" onClick={saveManualTotw} disabled={totwSaving}>
                        {totwSaving ? 'Saving…' : 'Save lineup'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <TeamOfTheWeekFormation
                    recipients={totw.recipients}
                    onSelectPlayer={(player) => setSelectedPlayerId(player.id)}
                  />
                )}
              </div>
            ) : (
              <EmptyState>No Team of the Week for this match day.</EmptyState>
            )}
          </div>
        )
      ) : monthly.length === 0 ? (
        <EmptyState>No monthly awards yet.</EmptyState>
      ) : (
        <div className="space-y-3">
          {monthly.map((award) => (
            <div key={award.id} className="card">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-bold">{award.award_type_display}</h3>
                {award.is_confirmed ? <span className="badge">Confirmed</span> : <span className="badge">Pending</span>}
              </div>
              <p className="text-xs text-[var(--color-muted)] mt-1">
                {award.year}-{String(award.month).padStart(2, '0')}
              </p>
              <div className="mt-3 space-y-2">
                {award.recipients.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className="player-chip"
                    onClick={() => setSelectedPlayerId(r.player.id)}
                  >
                    <PlayerAvatar player={r.player} size={40} />
                    <div className="min-w-0 text-left flex-1">
                      <p className="font-semibold truncate">
                        {r.rank ? `#${r.rank} ` : ''}{r.player.name}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
