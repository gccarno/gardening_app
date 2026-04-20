import { createPlantsApi } from '@garden/shared';
export type { Plant, LibraryEntry, PlantDetail } from '@garden/shared';

export const {
  fetchPlants, fetchPlant, createPlant, updatePlant, deletePlant,
  setPlantStatus, fetchLibraryNames,
} = createPlantsApi('/api');
