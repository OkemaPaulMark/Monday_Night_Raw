import { useEffect, useMemo, useState } from 'react'
import { awardsApi, gameWeeksApi, matchesApi, playersApi } from '../services/endpoints'
import { useAuth } from '../context/AuthContext'
import { ErrorBanner, LoadingState, SectionTitle, EmptyState } from '../components/ui'
import TeamOfTheWeekFormation from '../components/TeamOfTheWeekFormation'
import PlayerStatsModal from '../components/PlayerStatsModal'
import PlayerAvatar from '../components/PlayerAvatar'
import PotmCard from '../components/PotmCard'
import { POSITIONS } from '../constants'

function positionLabel(value) {
  return POSITIONS.find((p) => p.value === value)?.label || 'No position'
}

function groupWeeklyByMatch(weekly) {
  const map = new Map()
  for (const award of weekly) {
    if (!award.match && !award.game_week) continue
    const key = award.match ? `m${award.match}` : `gw${award.game_week}`
    if (!map.has(key)) {
      map.set(key, {
        weekKey: key,
        matchId: award.match,
        gameWeekId: award.game_week,
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
  const [selectedWeekKey, setSelectedWeekKey] = useState('')
  const [editingKind, setEditingKind] = useState(null) // null | 'potw' | 'totw'
  const [matchParticipants, setMatchParticipants] = useState([])
  const [manualIds, setManualIds] = useState([])
  const [editError, setEditError] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const now = new Date()
  // Default to previous month — current month's POTM isn't awarded until it ends
  const defaultMonth = now.getMonth() === 0 ? 12 : now.getMonth()
  const defaultYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()
  const [year, setYear] = useState(defaultYear)
  const [month, setMonth] = useState(defaultMonth)
  const [editingPotm, setEditingPotm] = useState(false)
  const [monthPlayers, setMonthPlayers] = useState([])
  const [potmManualIds, setPotmManualIds] = useState([])
  const [potmEditError, setPotmEditError] = useState('')
  const [potmSaving, setPotmSaving] = useState(false)

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
    setEditingPotm(false)
  }, [year, month])

  const weeklyGroups = useMemo(() => groupWeeklyByMatch(weekly), [weekly])

  // Default to latest match day whenever award data refreshes
  useEffect(() => {
    if (!weeklyGroups.length) {
      setSelectedWeekKey('')
      return
    }
    const latestKey = weeklyGroups[0].weekKey
    setSelectedWeekKey((current) => {
      if (current && weeklyGroups.some((g) => g.weekKey === current)) {
        return current
      }
      return latestKey
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

  const selectedGroup = weeklyGroups.find((g) => g.weekKey === selectedWeekKey)
  const potw = selectedGroup?.awards.find((a) => a.award_type === 'POTW')
  const totw = selectedGroup?.awards.find((a) => a.award_type === 'TOTW')

  useEffect(() => {
    setEditingKind(null)
    setEditError('')
  }, [selectedWeekKey])

  async function startEdit(kind) {
    setEditError('')
    const award = kind === 'potw' ? potw : totw
    setManualIds((award?.recipients || []).map((r) => r.player.id))
    setEditingKind(kind)
    try {
      if (selectedGroup.matchId) {
        const m = await matchesApi.get(selectedGroup.matchId)
        setMatchParticipants(m.participants.map((row) => row.player))
      } else {
        const gw = await gameWeeksApi.get(selectedGroup.gameWeekId)
        const byId = new Map()
        for (const fixture of gw.fixtures) {
          for (const row of fixture.participants) {
            byId.set(row.player.id, row.player)
          }
        }
        setMatchParticipants([...byId.values()])
      }
    } catch (e) {
      setEditError(e.message)
    }
  }

  function toggleManualPlayer(playerId) {
    setManualIds((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  async function saveManualEdit() {
    setEditSaving(true)
    setEditError('')
    try {
      if (editingKind === 'potw') {
        await awardsApi.setPotwRecipients(potw.id, manualIds)
      } else {
        await awardsApi.setTotwRecipients(totw.id, manualIds)
      }
      await load()
      setEditingKind(null)
    } catch (e) {
      setEditError(e.message)
    } finally {
      setEditSaving(false)
    }
  }

  const potmAward = monthly.find((a) => a.award_type === 'POTM_MONTH')
  const nowDate = new Date()
  const isCurrentMonth = year === nowDate.getFullYear() && month === nowDate.getMonth() + 1
  const nonPotm = monthly.filter((a) => a.award_type !== 'POTM_MONTH')

  async function startPotmEdit() {
    setPotmEditError('')
    setPotmManualIds((potmAward?.recipients || []).map((r) => r.player.id))
    try {
      const all = await playersApi.list({ is_active: true })
      const allList = Array.isArray(all) ? all : (all?.results || [])
      setMonthPlayers(allList)
    } catch (e) {
      setPotmEditError(e.message)
    }
    setEditingPotm(true)
  }

  function togglePotmPlayer(playerId) {
    setPotmManualIds((prev) =>
      prev.includes(playerId) ? prev.filter((x) => x !== playerId) : [...prev, playerId],
    )
  }

  async function savePotmEdit() {
    setPotmSaving(true)
    setPotmEditError('')
    try {
      await awardsApi.setPotmRecipients(potmAward.id, potmManualIds)
      await load()
      setEditingPotm(false)
    } catch (e) {
      setPotmEditError(e.message)
    } finally {
      setPotmSaving(false)
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
            value={selectedWeekKey}
            onChange={(e) => setSelectedWeekKey(e.target.value)}
          >
            {weeklyGroups.map((g, index) => (
              <option key={g.weekKey} value={g.weekKey}>
                {formatMatchDay(g.matchDate)}
                {g.gameWeekId ? ' · game week' : ''}
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
            <div className="card space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-bold">Player of the Week</h3>
                <div className="flex items-center gap-2">
                  {potw?.is_confirmed ? <span className="badge">Confirmed</span> : null}
                  {isAdmin && potw && editingKind !== 'potw' && (
                    <button type="button" className="btn btn-secondary" style={{ minHeight: 32, padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={() => startEdit('potw')}>
                      Edit
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-[var(--color-muted)] -mt-2">
                {formatMatchDay(selectedGroup.matchDate)}
              </p>

              {editingKind === 'potw' ? (
                <div className="space-y-3">
                  <ErrorBanner message={editError} />
                  <p className="text-sm text-[var(--color-muted)]">
                    Pick who won Player of the Week for this match day. Tap more
                    than one to declare a tie — order sets the rank shown.
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
                    <button type="button" className="btn btn-secondary w-full" onClick={() => setEditingKind(null)} disabled={editSaving}>
                      Cancel
                    </button>
                    <button type="button" className="btn btn-primary w-full" onClick={saveManualEdit} disabled={editSaving || manualIds.length === 0}>
                      {editSaving ? 'Saving…' : 'Save'}
                    </button>
                  </div>
                </div>
              ) : (
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
              )}
            </div>

            {totw ? (
              <div className="card space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold">Team of the Week</h3>
                  <div className="flex items-center gap-2">
                    <span className="badge">{totw.recipients.length}-a-side XI</span>
                    {isAdmin && editingKind !== 'totw' && (
                      <button type="button" className="btn btn-secondary" style={{ minHeight: 32, padding: '0.25rem 0.6rem', fontSize: '0.75rem' }} onClick={() => startEdit('totw')}>
                        Edit lineup
                      </button>
                    )}
                  </div>
                </div>

                {editingKind === 'totw' ? (
                  <div className="space-y-3">
                    <ErrorBanner message={editError} />
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
                      <button type="button" className="btn btn-secondary w-full" onClick={() => setEditingKind(null)} disabled={editSaving}>
                        Cancel
                      </button>
                      <button type="button" className="btn btn-primary w-full" onClick={saveManualEdit} disabled={editSaving}>
                        {editSaving ? 'Saving…' : 'Save lineup'}
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
      ) : (
        <div className="space-y-3">
          {potmAward ? (
            editingPotm ? (
              <div className="card space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold">Player of the Month</h3>
                  <span className="badge">{potmAward.year}-{String(potmAward.month).padStart(2, '0')}</span>
                </div>
                <ErrorBanner message={potmEditError} />
                <p className="text-sm text-[var(--color-muted)]">
                  Pick who won Player of the Month. Tap more than one to declare a tie.
                </p>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {monthPlayers.map((p) => {
                    const idx = potmManualIds.indexOf(p.id)
                    return (
                      <button
                        key={p.id}
                        type="button"
                        className={`player-chip ${idx >= 0 ? 'selected' : ''}`}
                        onClick={() => togglePotmPlayer(p.id)}
                      >
                        <PlayerAvatar player={p} size={36} />
                        <div className="min-w-0 flex-1 text-left">
                          <p className="font-semibold truncate">{p.name}</p>
                        </div>
                        {idx >= 0 && <span className="badge">#{idx + 1}</span>}
                      </button>
                    )
                  })}
                  {monthPlayers.length === 0 && (
                    <p className="text-sm text-[var(--color-muted)]">No players found for this month.</p>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" className="btn btn-secondary w-full" onClick={() => setEditingPotm(false)} disabled={potmSaving}>
                    Cancel
                  </button>
                  <button type="button" className="btn btn-primary w-full" onClick={savePotmEdit} disabled={potmSaving || potmManualIds.length === 0}>
                    {potmSaving ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
            ) : (
              <PotmCard
                award={potmAward}
                avatarSize={110}
                onEdit={isAdmin ? startPotmEdit : undefined}
              />
            )
          ) : (
            <div className="potm-pending-card">
              <div className="potm-pending-glow" />
              <div className="potm-pending-inner">
                <span className="potm-pending-icon">🏆</span>
                <div>
                  <p className="potm-pending-title">Player of the Month</p>
                  <p className="potm-pending-sub">
                    {isCurrentMonth
                      ? 'Still being decided — check back when the month ends.'
                      : 'No award recorded for this month.'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {nonPotm.length === 0 && !isCurrentMonth && (
            <EmptyState>No awards recorded for this month.</EmptyState>
          )}
          {nonPotm.map((award) => {
            const statLabel = {
              GOLDEN_BOOT: 'goals',
              TOP_ASSISTER: 'assists',
              MOST_POTW: 'POTW',
            }[award.award_type]

            const rankGroups = []
            for (const r of award.recipients) {
              const last = rankGroups[rankGroups.length - 1]
              if (last && last.rank === r.rank) {
                last.players.push(r)
              } else {
                rankGroups.push({ rank: r.rank, players: [r] })
              }
            }
            let displayRank = 1
            const rankDisplay = []
            for (const group of rankGroups) {
              for (const r of group.players) {
                rankDisplay.push({ recipient: r, label: displayRank })
              }
              displayRank += group.players.length
            }

            return (
              <div key={award.id} className="card">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-bold">{award.award_type_display}</h3>
                  {award.is_confirmed
                    ? <span className="badge">Confirmed</span>
                    : <span className="badge">Pending</span>}
                </div>
                <p className="text-xs text-[var(--color-muted)] mt-1">
                  {award.year}-{String(award.month).padStart(2, '0')}
                </p>
                <div className="mt-3 space-y-2">
                  {rankDisplay.map(({ recipient: r, label }) => (
                    <button
                      key={r.id}
                      type="button"
                      className="player-chip"
                      onClick={() => setSelectedPlayerId(r.player.id)}
                    >
                      <PlayerAvatar player={r.player} size={40} />
                      <div className="min-w-0 text-left flex-1">
                        <p className="font-semibold truncate">{label}. {r.player.name}</p>
                      </div>
                      {statLabel && r.stat_value != null && (
                        <span className="display text-xl text-[var(--color-gold)] shrink-0">
                          {r.stat_value} <span className="text-xs text-[var(--color-muted)]">{statLabel}</span>
                        </span>
                      )}
                    </button>
                  ))}
                  {award.recipients.length === 0 && (
                    <p className="text-sm text-[var(--color-muted)]">No recipients recorded.</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <PlayerStatsModal
        playerId={selectedPlayerId}
        onClose={() => setSelectedPlayerId(null)}
      />
    </div>
  )
}
