import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchBeds, fetchBed, createBed, updateBed, deleteBed,
  fetchBedGrid, placePlantInGrid, fetchBedPlant, saveBedPlantCare, removeBedPlant,
  type Bed,
} from '../api/beds';

export function useBeds(gardenId?: number) {
  return useQuery({
    queryKey: ['bedsList', gardenId],
    queryFn: () => fetchBeds(gardenId),
  });
}

export function useBed(id: number) {
  return useQuery({
    queryKey: ['bed', id],
    queryFn: () => fetchBed(id),
    enabled: !!id,
  });
}

export function useBedGrid(bedId: number) {
  return useQuery({
    queryKey: ['bedGrid', bedId],
    queryFn: () => fetchBedGrid(bedId),
    enabled: !!bedId,
    staleTime: 0,
  });
}

export function useBedPlant(bpId: number | null) {
  return useQuery({
    queryKey: ['bedPlant', bpId],
    queryFn: () => fetchBedPlant(bpId!),
    enabled: !!bpId,
  });
}

export function useCreateBed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createBed,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bedsList'] }),
  });
}

export function useUpdateBed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Partial<Bed>) => updateBed(id, body),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: ['bedsList'] });
      qc.invalidateQueries({ queryKey: ['bed', id] });
    },
  });
}

export function useDeleteBed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteBed,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bedsList'] }),
  });
}

export function usePlaceInGrid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bedId, ...body }: { bedId: number; library_id: number; grid_x: number; grid_y: number }) =>
      placePlantInGrid(bedId, body),
    onSuccess: (_d, { bedId }) => qc.invalidateQueries({ queryKey: ['bedGrid', bedId] }),
  });
}

export function useSaveBedPlantCare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bpId, ...body }: { bpId: number; last_watered?: string | null; last_fertilized?: string | null; health_notes?: string | null }) =>
      saveBedPlantCare(bpId, body),
    onSuccess: (_d, { bpId }) => qc.invalidateQueries({ queryKey: ['bedPlant', bpId] }),
  });
}

export function useRemoveBedPlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bpId, bedId }: { bpId: number; bedId: number }) => removeBedPlant(bpId),
    onSuccess: (_d, { bedId }) => qc.invalidateQueries({ queryKey: ['bedGrid', bedId] }),
  });
}
