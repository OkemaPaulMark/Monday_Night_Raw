import api from './api'

export const authApi = {
  register: (payload) => api.post('/auth/register/', payload).then((r) => r.data),
  login: (username, password) =>
    api.post('/auth/login/', { username, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout/').then((r) => r.data),
  me: () => api.get('/auth/me/').then((r) => r.data),
}

export const playersApi = {
  list: (params) => api.get('/players/', { params }).then((r) => r.data),
  get: (id) => api.get(`/players/${id}/`).then((r) => r.data),
  update: (id, payload) => api.patch(`/players/${id}/`, payload).then((r) => r.data),
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
  setParticipants: (id, player_ids) =>
    api.post(`/matches/${id}/participants/`, { player_ids }).then((r) => r.data),
  setTeams: (id, team_a, team_b) =>
    api.post(`/matches/${id}/teams/`, { team_a, team_b }).then((r) => r.data),
  generateTeams: (id, method) =>
    api.post(`/matches/${id}/generate-teams/`, { method }).then((r) => r.data),
  setScore: (id, team_a_score, team_b_score) =>
    api.post(`/matches/${id}/score/`, { team_a_score, team_b_score }).then((r) => r.data),
  setGoals: (id, goals) =>
    api.post(`/matches/${id}/goals/`, { goals }).then((r) => r.data),
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
  standings: () => api.get('/standings/').then((r) => r.data),
  dashboard: () => api.get('/dashboard/').then((r) => r.data),
}

export const awardsApi = {
  weekly: (params) => api.get('/awards/weekly/', { params }).then((r) => r.data),
  monthly: (params) => api.get('/awards/monthly/', { params }).then((r) => r.data),
  generateMonthly: (year, month) =>
    api.post('/awards/monthly/', { year, month }).then((r) => r.data),
  confirm: (id) => api.post(`/awards/${id}/confirm/`).then((r) => r.data),
}
