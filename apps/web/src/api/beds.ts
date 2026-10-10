import { createBedsApi } from '@garden/shared';
export type { Bed, GridPlant, BedPlantDetail, MoistureCheckin, MoistureLevel } from '@garden/shared';

export const {
  fetchBeds, fetchBed, createBed, updateBed, deleteBed,
  fetchBedGrid, placePlantInGrid, fetchBedPlant, saveBedPlantCare, removeBedPlant,
  fetchMoistureCheckins, saveMoistureCheckin,
} = createBedsApi('/api');
