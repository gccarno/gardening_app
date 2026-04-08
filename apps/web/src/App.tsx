import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import GardenList from './pages/GardenList';
import GardenDetail from './pages/GardenDetail';
import BedList from './pages/BedList';
import BedDetail from './pages/BedDetail';
import PlantList from './pages/PlantList';
import PlantDetail from './pages/PlantDetail';
import TaskList from './pages/TaskList';
import TaskDetail from './pages/TaskDetail';
import LibraryBrowser from './pages/LibraryBrowser';
import LibraryDetail from './pages/LibraryDetail';
import Planner from './pages/Planner';

export default function App() {
  return (
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
        <Route path="/library/:id"       element={<LibraryDetail />} />
        <Route path="/planner"           element={<Planner />} />
      </Routes>
    </Layout>
  );
}
