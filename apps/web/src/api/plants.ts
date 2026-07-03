import { createPlantsApi } from '@garden/shared';
export type { Plant, LibraryEntry, PlantDetail, PlantGroup, SuccessionGroup, SyncChange } from '@garden/shared';

export const {
  fetchPlants, fetchPlant, createPlant, updatePlant, deletePlant,
  setPlantStatus, fetchLibraryNames,
  bulkDeletePlants, bulkStatusPlants, bulkCarePlants,
  fetchSyncPreview, applySync,
} = createPlantsApi('/api');
