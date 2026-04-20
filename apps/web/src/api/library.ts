import { createLibraryApi } from '@garden/shared';
export type { LibraryListEntry, LibraryListResponse } from '@garden/shared';

export const {
  fetchLibrary, fetchLibraryEntry, addPlantFromLibrary,
  perenualSearch, perenualSave,
  setImagePrimary, deleteImage, addImageFromUrl, uploadImage,
  quickEditLibrary, clonePlant, patchLibraryEntry,
} = createLibraryApi('/api');
