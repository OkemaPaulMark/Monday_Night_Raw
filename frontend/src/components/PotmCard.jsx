import { Link } from 'react-router-dom'
import { mediaUrl, playerInitials } from '../utils/media'

const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

/**
 * Props:
 *   potm      — dashboard shape: { player_id, name, profile_photo, year, month, goals, assists, potw }
 *   award     — Award object shape: { recipients, year, month } — first recipient used
 *   avatarSize — px number, default 80
 *   onEdit    — if provided, shows an Edit button (admin only)
 */
export default function PotmCard({ potm, award, avatarSize = 80, onEdit }) {
  // Normalise to a single shape
  let data = potm
  if (!data && award) {
    const r = award.recipients?.[0]
    if (!r) return null
    data = {
      player_id: r.player.id,
      name: r.player.name,
      profile_photo: r.player.profile_photo,
      year: award.year,
      month: award.month,
      // performance_score on POTM is the G+A score — show it as G+A
      ga: r.performance_score != null ? Number(r.performance_score) : null,
    }
  }
  if (!data) return null

  const photo = mediaUrl(data.profile_photo)
  const monthLabel = `${MONTH_NAMES[data.month] ?? ''} ${data.year}`
  const dim = `${avatarSize}px`

  return (
    <div className="potm-card" style={{ '--potm-avatar-size': dim }}>
      <div className="potm-glow" />

      {/* Edit button — top right corner */}
      {onEdit && (
        <button
          type="button"
          className="btn btn-secondary potm-edit-btn"
          onClick={(e) => { e.preventDefault(); onEdit() }}
        >
          Edit
        </button>
      )}

      <Link to={`/players/${data.player_id}`} className="potm-inner" style={{ textDecoration: 'none' }}>
        {/* avatar */}
        <div className="potm-avatar-wrap">
          <div className="potm-avatar-ring" style={{ width: dim, height: dim }}>
            {photo ? (
              <img src={photo} alt={data.name} className="potm-avatar-img" />
            ) : (
              <span className="potm-avatar-initials" style={{ fontSize: `${avatarSize * 0.32}px` }}>
                {playerInitials(data.name)}
              </span>
            )}
          </div>
          <div className="potm-crown">🏆</div>
        </div>

        {/* info */}
        <div className="potm-info">
          <p className="potm-label">Player of the Month</p>
          <p className="potm-month">{monthLabel}</p>
          <p className="potm-name">{data.name}</p>
          <div className="potm-stats">
            {data.ga != null ? (
              /* awards page: only G+A composite score available */
              <div className="potm-stat">
                <span className="potm-stat-val">{data.ga}</span>
                <span className="potm-stat-lbl">G+A pts</span>
              </div>
            ) : (
              /* dashboard: full breakdown */
              <>
                <div className="potm-stat">
                  <span className="potm-stat-val">{data.goals}</span>
                  <span className="potm-stat-lbl">Goals</span>
                </div>
                <div className="potm-stat-divider" />
                <div className="potm-stat">
                  <span className="potm-stat-val">{data.assists}</span>
                  <span className="potm-stat-lbl">Assists</span>
                </div>
                <div className="potm-stat-divider" />
                <div className="potm-stat">
                  <span className="potm-stat-val">{data.potw}</span>
                  <span className="potm-stat-lbl">POTW</span>
                </div>
              </>
            )}
          </div>
        </div>
      </Link>
    </div>
  )
}
