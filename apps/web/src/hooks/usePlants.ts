import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchPlants, fetchPlant, createPlant, updatePlant,
  deletePlant, setPlantStatus, type Plant,
} from '../api/plants';

export function usePlants(params?: { garden_id?: number; status?: string }) {
  return useQuery({
    queryKey: ['plants', params],
    queryFn: () => fetchPlants(params),
  });
}

export function usePlant(id: number) {
  return useQuery({
    queryKey: ['plants', id],
    queryFn: () => fetchPlant(id),
    enabled: !!id,
  });
}

export function useCreatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createPlant,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plants'] }),
  });
}

export function useUpdatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Partial<Plant>) => updatePlant(id, body),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: ['plants'] });
      qc.invalidateQueries({ queryKey: ['plants', id] });
    },
  });
}

export function useDeletePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deletePlant,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plants'] }),
  });
}

export function useSetPlantStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => setPlantStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plants'] }),
  });
}
