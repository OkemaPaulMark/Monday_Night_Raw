import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import AppLayout from './layouts/AppLayout'
import { ProtectedRoute } from './routes/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import LeaderboardPage from './pages/LeaderboardPage'
import AwardsPage from './pages/AwardsPage'
import ProfilePage from './pages/ProfilePage'
import MatchesPage from './pages/MatchesPage'
import MatchDetailPage from './pages/MatchDetailPage'
import GameWeekDetailPage from './pages/GameWeekDetailPage'
import {
  AdminDashboardPage,
  AdminPlayersPage,
  CreateMatchPage,
  MatchWizardPage,
} from './pages/admin/AdminPages'
import { AdminGameWeekPage } from './pages/admin/GameWeekPages'

function HomeRedirect() {
  const { isAdmin } = useAuth()
  return <Navigate to={isAdmin ? '/admin' : '/dashboard'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<HomeRedirect />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="leaderboard" element={<LeaderboardPage />} />
              <Route path="awards" element={<AwardsPage />} />
              <Route path="matches" element={<MatchesPage />} />
              <Route path="matches/:id" element={<MatchDetailPage />} />
              <Route path="game-weeks/:id" element={<GameWeekDetailPage />} />
              <Route path="profile" element={<ProfilePage self />} />
              <Route path="players/:id" element={<ProfilePage />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute adminOnly />}>
            <Route element={<AppLayout />}>
              <Route path="admin" element={<AdminDashboardPage />} />
              <Route path="admin/players" element={<AdminPlayersPage />} />
              <Route path="admin/matches" element={<MatchesPage />} />
              <Route path="admin/matches/new" element={<CreateMatchPage />} />
              <Route path="admin/matches/:id" element={<MatchWizardPage />} />
              <Route path="admin/game-weeks/:id" element={<AdminGameWeekPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
