import { createContext, useContext, Dispatch, SetStateAction } from 'react';
import type React from 'react';
import type { Garden } from '../../api/gardens';
import type { Bed, CanvasPlant, GardenPlant, CareData, LibraryInfo } from './types';

export interface PlannerCtxValue {
  gardenId: number;
  garden: Garden | undefined;
  gardens: Garden[] | undefined;
  canvasBeds: Bed[];
  setCanvasBeds: Dispatch<SetStateAction<Bed[]>>;
  paletteBeds: Bed[];
  setPaletteBeds: Dispatch<SetStateAction<Bed[]>>;
  canvasPlants: CanvasPlant[];
  setCanvasPlants: Dispatch<SetStateAction<CanvasPlant[]>>;
  gardenPlants: GardenPlant[];
  setGardenPlants: Dispatch<SetStateAction<GardenPlant[]>>;
  selectedBed: Bed | null;
  setSelectedBed: Dispatch<SetStateAction<Bed | null>>;
  carePanel: CareData | null;
  setCarePanel: Dispatch<SetStateAction<CareData | null>>;
  rightPanelOpen: boolean;
  setRightPanelOpen: Dispatch<SetStateAction<boolean>>;
  rightPanelTab: 'info' | 'timeline' | 'calendar';
  setRightPanelTab: Dispatch<SetStateAction<'info' | 'timeline' | 'calendar'>>;
  groupInfoPlants: GardenPlant[] | null;
  setGroupInfoPlants: Dispatch<SetStateAction<GardenPlant[] | null>>;
  libInfo: LibraryInfo | null;
  setLibInfo: Dispatch<SetStateAction<LibraryInfo | null>>;
  libEditMode: boolean;
  setLibEditMode: Dispatch<SetStateAction<boolean>>;
  libImageMode: boolean;
  setLibImageMode: Dispatch<SetStateAction<boolean>>;
  highlightLibId: number | null;
  setHighlightLibId: Dispatch<SetStateAction<number | null>>;
  weather: unknown;
  tasks: unknown[];
  setTasks: Dispatch<SetStateAction<unknown[]>>;
  taskForm: { title: string; due_date: string; description: string };
  setTaskForm: Dispatch<SetStateAction<{ title: string; due_date: string; description: string }>>;
  taskSaved: string;
  setTaskSaved: Dispatch<SetStateAction<string>>;
  loadPanelData: () => Promise<void>;
  handleAddTask: (e: React.FormEvent) => Promise<void>;
  showLibInfo: (libraryId: number) => Promise<void>;
  showGroupInfo: (group: GardenPlant[]) => Promise<void>;
}

export const PlannerCtx = createContext<PlannerCtxValue | null>(null);

export function usePlannerCtx(): PlannerCtxValue {
  const ctx = useContext(PlannerCtx);
  if (!ctx) throw new Error('usePlannerCtx must be used within a PlannerCtx.Provider');
  return ctx;
}
