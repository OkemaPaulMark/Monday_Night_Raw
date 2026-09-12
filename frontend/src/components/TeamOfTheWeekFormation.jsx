import PlayerAvatar from './PlayerAvatar'

/** Legacy fallback for recipients with no position on record — guess from rank order. */
function splitFormationByOrder(ordered) {
  const n = ordered.length
  if (n <= 5) {
    return {
      attack: ordered.slice(0, 2),
      mid: ordered.slice(2, 3),
      defense: ordered.slice(3, 5),
    }
  }
  if (n === 6) {
    return {
      attack: ordered.slice(0, 2),
      mid: ordered.slice(2, 4),
      defense: ordered.slice(4, 6),
    }
  }
  return {
    attack: ordered.slice(0, 2),
    mid: ordered.slice(2, 5),
    defense: ordered.slice(5, 7),
  }
}

/** Formation rows by real position: 2 strikers (attack) / 3 midfielders / 2 defenders. */
function splitFormation(recipients) {
  const ordered = [...recipients].sort((a, b) => (a.rank || 99) - (b.rank || 99))
  const attack = []
  const mid = []
  const defense = []
  const unassigned = []
  for (const r of ordered) {
    switch (r.player?.position) {
      case 'STRIKER':
        attack.push(r)
        break
      case 'MIDFIELDER':
        mid.push(r)
        break
      case 'DEFENDER':
        defense.push(r)
        break
      default:
        unassigned.push(r)
    }
  }
  if (attack.length === 0 && mid.length === 0 && defense.length === 0 && unassigned.length > 0) {
    return splitFormationByOrder(unassigned)
  }
  mid.push(...unassigned)
  return { attack, mid, defense }
}

function FormationRow({ players, onSelect }) {
  return (
    <div className="formation-row">
      {players.map((r) => (
        <button
          key={r.id}
          type="button"
          className="formation-player"
          onClick={() => onSelect?.(r.player)}
        >
          <PlayerAvatar player={r.player} size={56} className="formation-avatar" />
          <span className="formation-name">{r.player.name.split(' ')[0]}</span>
        </button>
      ))}
    </div>
  )
}

export default function TeamOfTheWeekFormation({ recipients = [], onSelectPlayer }) {
  const { attack, mid, defense } = splitFormation(recipients)

  return (
    <div className="pitch fade-up">
      <div className="pitch-mark pitch-circle" />
      <div className="pitch-mark pitch-box-top" />
      <div className="pitch-mark pitch-box-bottom" />
      <p className="pitch-label">Attack</p>
      <FormationRow players={attack} onSelect={onSelectPlayer} />
      <FormationRow players={mid} onSelect={onSelectPlayer} />
      <FormationRow players={defense} onSelect={onSelectPlayer} />
      <p className="pitch-label pitch-label-bottom">Defense</p>
      <p className="pitch-hint">Tap a player for stats · {recipients.length}-a-side XI</p>
    </div>
  )
}
