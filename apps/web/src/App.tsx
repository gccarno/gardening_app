import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';

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
const PlantDiff     = lazy(() => import('./pages/PlantDiff'));
const Planner       = lazy(() => import('./pages/Planner'));

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<div className="loading-page">Loading…</div>}>
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
          <Route path="/library/:id"       element={<LibraryDetail />} />
          <Route path="/planner"           element={<Planner />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
