import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchGardens,
  fetchGarden,
  fetchDashboard,
  fetchDefaultGarden,
  fetchWateringStatus,
  createGarden,
  updateGarden,
  deleteGarden,
  setDefaultGarden,
  type Garden,
} from '../api/gardens';

export function useGardens() {
  return useQuery({ queryKey: ['gardens'], queryFn: fetchGardens });
}

export function useGarden(id: number) {
  return useQuery({ queryKey: ['gardens', id], queryFn: () => fetchGarden(id), enabled: !!id });
}

export function useDashboard(gardenId?: number) {
  return useQuery({
    queryKey: ['dashboard', gardenId],
    queryFn: () => fetchDashboard(gardenId),
  });
}

export function useDefaultGarden() {
  return useQuery({ queryKey: ['defaultGarden'], queryFn: fetchDefaultGarden });
}

export function useWateringStatus(gardenId?: number) {
  return useQuery({
    queryKey: ['wateringStatus', gardenId],
    queryFn: () => fetchWateringStatus(gardenId!),
    enabled: !!gardenId,
    staleTime: 60_000,
  });
}

export function useCreateGarden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createGarden,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gardens'] }),
  });
}

export function useUpdateGarden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Partial<Garden>) => updateGarden(id, body),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: ['gardens'] });
      qc.invalidateQueries({ queryKey: ['gardens', id] });
    },
  });
}

export function useDeleteGarden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteGarden,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gardens'] }),
  });
}

export function useSetDefaultGarden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setDefaultGarden,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['defaultGarden'] }),
  });
}
