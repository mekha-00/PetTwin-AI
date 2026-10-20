/**
 * Route table for Phases 3-5.
 *
 * Every screen under `AppLayout` is wrapped in `ProtectedRoute`. `RequireAuth`
 * exists for `/login` and `/register`, which redirect an already-signed-in user
 * to the dashboard rather than showing a form they do not need.
 *
 * Some routes pass `roles`, restricting them to a kind of account: `/patients`
 * is the veterinarian's patient list, while ownership screens are for pet
 * parents. `/reference` is open to every signed-in account because it answers
 * from public literature and never reads a pet's record. The API enforces the
 * real permissions regardless.
 */
import { Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import RequireAuth from './components/RequireAuth'
import AddPet from './pages/AddPet'
import ClinicalReference from './pages/ClinicalReference'
import Dashboard from './pages/Dashboard'
import DigitalTwin from './pages/DigitalTwin'
import HealthTimeline from './pages/HealthTimeline'
import Login from './pages/auth/Login'
import MyPets from './pages/MyPets'
import NotFound from './pages/NotFound'
import Patients from './pages/Patients'
import PetDetails from './pages/PetDetails'
import Register from './pages/auth/Register'

const OWNER_ROLES = ['pet_owner']

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<RequireAuth><Login /></RequireAuth>} />
      <Route path="/register" element={<RequireAuth><Register /></RequireAuth>} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route
          path="/pets"
          element={
            <ProtectedRoute roles={OWNER_ROLES}>
              <MyPets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pets/new"
          element={
            <ProtectedRoute roles={OWNER_ROLES}>
              <AddPet />
            </ProtectedRoute>
          }
        />
        <Route path="/patients" element={<Patients />} />
        <Route path="/reference" element={<ClinicalReference />} />
        <Route path="/pets/:petId" element={<PetDetails />} />
        <Route path="/pets/:petId/digital-twin" element={<DigitalTwin />} />
        <Route path="/pets/:petId/timeline" element={<HealthTimeline />} />
      </Route>

      <Route path="/index.html" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
