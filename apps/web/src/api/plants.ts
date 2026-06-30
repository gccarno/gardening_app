import { createPlantsApi } from '@garden/shared';
export type { Plant, LibraryEntry, PlantDetail, PlantGroup, SuccessionGroup } from '@garden/shared';

export const {
  fetchPlants, fetchPlant, createPlant, updatePlant, deletePlant,
  setPlantStatus, fetchLibraryNames,
  bulkDeletePlants, bulkStatusPlants, bulkCarePlants,
} = createPlantsApi('/api');
