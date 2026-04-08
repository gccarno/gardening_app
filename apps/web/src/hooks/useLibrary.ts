import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchLibrary, fetchLibraryEntry,
  setImagePrimary, deleteImage, addImageFromUrl, uploadImage, quickEditLibrary,
} from '../api/library';

export function useLibrary(params?: { q?: string; type?: string; page?: number }) {
  return useQuery({
    queryKey: ['library', params],
    queryFn: () => fetchLibrary({ ...params, per_page: 50 }),
    placeholderData: (prev) => prev,
  });
}

export function useLibraryEntry(id: number) {
  return useQuery({
    queryKey: ['library', id],
    queryFn: () => fetchLibraryEntry(id),
    enabled: !!id,
  });
}

export function useSetImagePrimary(entryId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setImagePrimary,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library', entryId] }),
  });
}

export function useDeleteImage(entryId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteImage,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library', entryId] }),
  });
}

export function useAddImageUrl(entryId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { url: string; source?: string; attribution?: string }) =>
      addImageFromUrl(entryId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library', entryId] }),
  });
}

export function useUploadImage(entryId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadImage(entryId, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library', entryId] }),
  });
}

export function useQuickEdit(entryId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => quickEditLibrary(entryId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library', entryId] }),
  });
}
