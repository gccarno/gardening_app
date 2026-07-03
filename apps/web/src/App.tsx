import { lazy, Suspense, type ReactNode } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { AuthProvider, useAuth, getStoredToken } from './auth/AuthContext';

const Dashboard     = lazy(() => import('./pages/Dashboard'));
const GardenList    = lazy(() => import('./pages/GardenList'));
const GardenDetail  = lazy(() => import('./pages/GardenDetail'));
const BedList       = lazy(() => import('./pages/BedList'));
const BedDetail     = lazy(() => import('./pages/BedDetail'));
const PlantList     = lazy(() => import('./pages/PlantList'));
const PlantDetail   = lazy(() => import('./pages/PlantDetail'));
const TaskList      = lazy(() => import('./pages/TaskList'));
const TaskDetail    = lazy(() => import('./pages/TaskDetail'));
const LibraryBrowser = lazy(() => import('./pages/LibraryBrowser'));
const LibraryDetail = lazy(() => import('./pages/LibraryDetail'));
const LibraryEdit   = lazy(() => import('./pages/LibraryEdit'));
const PlantDiff     = lazy(() => import('./pages/PlantDiff'));
const Planner       = lazy(() => import('./pages/Planner'));
const SeedRoom      = lazy(() => import('./pages/SeedRoom'));
const Journal       = lazy(() => import('./pages/Journal'));
const Compost       = lazy(() => import('./pages/Compost'));
const Login         = lazy(() => import('./pages/Login'));
const Identify      = lazy(() => import('./pages/Identify'));

function RequireAuth({ children }: { children: ReactNode }) {
  // Token presence gates the app; invalid tokens get bounced to /login by
  // the shared 401 handler on the first API call.
  if (!getStoredToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Suspense fallback={<div className="loading-page">Loading…</div>}>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <Login />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <Layout>
                <Routes>
                  <Route path="/"                  element={<Navigate to="/planner" replace />} />
                  <Route path="/dashboard"         element={<Dashboard />} />
                  <Route path="/gardens"           element={<GardenList />} />
                  <Route path="/gardens/:id"       element={<GardenDetail />} />
                  <Route path="/beds"              element={<BedList />} />
                  <Route path="/beds/:id"          element={<BedDetail />} />
                  <Route path="/plants"            element={<PlantList />} />
                  <Route path="/plants/:id"        element={<PlantDetail />} />
                  <Route path="/tasks"             element={<TaskList />} />
                  <Route path="/tasks/:id"         element={<TaskDetail />} />
                  <Route path="/library"           element={<LibraryBrowser />} />
                  <Route path="/library/diff"      element={<PlantDiff />} />
                  <Route path="/library/:id/edit"  element={<LibraryEdit />} />
                  <Route path="/library/:id"       element={<LibraryDetail />} />
                  <Route path="/planner"           element={<Planner />} />
                  <Route path="/seed-room"         element={<SeedRoom />} />
                  <Route path="/journal"           element={<Journal />} />
                  <Route path="/compost"           element={<Compost />} />
                  <Route path="/identify"          element={<Identify />} />
                </Routes>
              </Layout>
            </RequireAuth>
          }
        />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
