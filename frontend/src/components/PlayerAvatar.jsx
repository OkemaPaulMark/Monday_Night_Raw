import { mediaUrl, playerInitials } from '../utils/media'

export default function PlayerAvatar({ player, size = 48, className = '' }) {
  const name = player?.name || 'Player'
  const photo = mediaUrl(player?.profile_photo)
  const dim = typeof size === 'number' ? `${size}px` : size

  return (
    <div
      className={`player-avatar ${className}`}
      style={{ width: dim, height: dim }}
      title={name}
      aria-label={name}
    >
      {photo ? (
        <img src={photo} alt={name} />
      ) : (
        <span>{playerInitials(name)}</span>
      )}
    </div>
  )
}
