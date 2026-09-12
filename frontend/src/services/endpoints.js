import api from './api'

export const authApi = {
  register: (payload) => api.post('/auth/register/', payload).then((r) => r.data),
  login: (username, password) =>
    api.post('/auth/login/', { username, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout/').then((r) => r.data),
  me: () => api.get('/auth/me/').then((r) => r.data),
  updateMe: (payload) => api.patch('/auth/me/', payload).then((r) => r.data),
}

export const playersApi = {
  list: (params) => api.get('/players/', { params }).then((r) => r.data),
  get: (id) => api.get(`/players/${id}/`).then((r) => r.data),
  update: (id, payload) => api.patch(`/players/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/players/${id}/`).then((r) => r.data),
  statistics: (id) => api.get(`/players/${id}/statistics/`).then((r) => r.data),
  matchHistory: (id) => api.get(`/players/${id}/match-history/`).then((r) => r.data),
  uploadPhoto: (id, file) => {
    const form = new FormData()
    form.append('profile_photo', file)
    return api.post(`/players/${id}/upload-photo/`, form).then((r) => r.data)
  },
}

export const matchesApi = {
  list: (params) => api.get('/matches/', { params }).then((r) => r.data),
  get: (id) => api.get(`/matches/${id}/`).then((r) => r.data),
  create: (payload) => api.post('/matches/', payload).then((r) => r.data),
  setGoals: (id, {
    goals,
    alsoPlayed = [],
    teamA = [],
    teamB = [],
    teamAScore = null,
    teamBScore = null,
  }) =>
    api.post(`/matches/${id}/goals/`, {
      goals,
      also_played: alsoPlayed,
      team_a: teamA,
      team_b: teamB,
      team_a_score: teamAScore,
      team_b_score: teamBScore,
    }).then((r) => r.data),
  finalize: (id) => api.post(`/matches/${id}/finalize/`).then((r) => r.data),
  reopen: (id) => api.post(`/matches/${id}/reopen/`).then((r) => r.data),
  getAvailability: (id) => api.get(`/matches/${id}/availability/`).then((r) => r.data),
  setAvailability: (id, status, player_id) =>
    api
      .post(`/matches/${id}/availability/`, player_id ? { status, player_id } : { status })
      .then((r) => r.data),
}

export const statsApi = {
  leaderboard: (ordering = '-goals') =>
    api.get('/leaderboard/', { params: { ordering } }).then((r) => r.data),
  dashboard: () => api.get('/dashboard/').then((r) => r.data),
}

export const awardsApi = {
  weekly: (params) => api.get('/awards/weekly/', { params }).then((r) => r.data),
  monthly: (params) => api.get('/awards/monthly/', { params }).then((r) => r.data),
  generateMonthly: (year, month) =>
    api.post('/awards/monthly/', { year, month }).then((r) => r.data),
  confirm: (id) => api.post(`/awards/${id}/confirm/`).then((r) => r.data),
  setTotwRecipients: (id, playerIds) =>
    api.post(`/awards/${id}/set-totw/`, { player_ids: playerIds }).then((r) => r.data),
}
