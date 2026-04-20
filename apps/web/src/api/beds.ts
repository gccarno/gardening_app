import { createBedsApi } from '@garden/shared';
export type { Bed, GridPlant, BedPlantDetail } from '@garden/shared';

export const {
  fetchBeds, fetchBed, createBed, updateBed, deleteBed,
  fetchBedGrid, placePlantInGrid, fetchBedPlant, saveBedPlantCare, removeBedPlant,
} = createBedsApi('/api');
