import { createGardensApi } from '@garden/shared';
export type { Garden, DashboardData } from '@garden/shared';

export const {
  fetchGardens, fetchGarden, createGarden, updateGarden, deleteGarden,
  fetchDashboard, fetchDefaultGarden, setDefaultGarden,
  fetchWateringStatus, sendChat, restartModel,
} = createGardensApi('/api');
