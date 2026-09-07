import PlayerAvatar from './PlayerAvatar'

/** Formation rows by squad size (TOTW size = team size: 5 / 6 / 7). */
function splitFormation(recipients) {
  const ordered = [...recipients].sort((a, b) => (a.rank || 99) - (b.rank || 99))
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
