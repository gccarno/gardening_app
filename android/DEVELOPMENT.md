# Android App — Development Plan & Progress

## Overview

Native Android app (Kotlin + Jetpack Compose) replicating the garden planner web app.
Backend: existing FastAPI at `apps/backend/` — unchanged, no auth needed.

## Stack

- **Kotlin + Jetpack Compose** + MVVM
- **Retrofit 2.11** + kotlinx.serialization — API layer
- **Room 2.6** — local SQLite caching
- **Hilt 2.51** — dependency injection
- **Navigation Compose 2.8** — routing
- **Coil 2.7** — image loading (`/static/` paths)
- **Paging 3** — paginated library (8,988 plants)
- **DataStore** — server URL + settings

Architecture per feature: `Screen.kt` → `ViewModel.kt` → `Repository.kt` → `DAO.kt` + `ApiService.kt`

## How to Run

1. Start backend: `cd apps/backend && uv run uvicorn app.main:app --reload`
2. Open `android/` folder in Android Studio
3. Sync Gradle, run on emulator or device
4. Default server URL is the Render cloud backend (`https://garden-app-wa0b.onrender.com`, see `USING_RENDER.md`); for a local backend on the emulator use `http://10.0.2.2:8000`
5. Physical device with a local backend: go to Settings tab, enter your machine's LAN IP (e.g. `http://192.168.1.x:8000`)

---

## Sessions

### ✅ Session 1 — Foundation + Dashboard
**Status: COMPLETE**

Deliverables:
- [x] Gradle project with all dependencies
- [x] All domain models (Garden, Weather, Task, Bed, Plant, Library, CanvasPlant)
- [x] Full ApiService with all 60+ endpoints declared
- [x] Hilt DI: NetworkModule, DatabaseModule
- [x] Room database: GardenDatabase, GardenDao, WeatherDao
- [x] Dynamic server URL via ServerConfig + DynamicBaseUrlInterceptor
- [x] Bottom navigation (Dashboard / Gardens / Plants / Tasks / Library)
- [x] Dashboard screen: garden selector, weather widget, 7-day forecast, metrics, seasonal hint, upcoming tasks
- [x] Settings screen: server URL backed by DataStore
- [x] Material3 theme with garden-green palette

Key files:
```
core/network/ApiService.kt              — all 60+ endpoints
core/network/ServerConfig.kt            — dynamic base URL singleton
core/di/NetworkModule.kt, DatabaseModule.kt
core/model/Garden.kt, Weather.kt, Task.kt, Bed.kt, Plant.kt, Library.kt, CanvasPlant.kt
core/database/GardenDatabase.kt + dao/ + entities/
feature/dashboard/DashboardScreen.kt + DashboardViewModel.kt + DashboardRepository.kt
feature/dashboard/components/WeatherWidget.kt, MetricsRow.kt, UpcomingTasksCard.kt, SeasonalHintCard.kt
feature/settings/SettingsScreen.kt + SettingsViewModel.kt
navigation/Screen.kt, NavGraph.kt
```

---

### ✅ Session 2 — Gardens CRUD
**Status: COMPLETE**

Deliverables:
- [x] Gardens list (FAB to create, delete with confirm dialog)
- [x] Garden form with ZIP field — backend enriches zone/frost/city/state on save
- [x] Garden detail: weather widget, bulk care buttons (Water/Fertilize/Mulch all), frost context banner, garden info card
- [x] Room caching for gardens list (cache-first, network refresh on open)

Key files created:
```
feature/garden/GardenRepository.kt                         — CRUD + weather + bulk care + Room cache
feature/garden/list/GardenListViewModel.kt
feature/garden/list/GardenListScreen.kt
feature/garden/list/components/GardenCard.kt               — zone chips, frost date, delete dialog
feature/garden/form/GardenFormViewModel.kt                 — create/edit, SavedStateHandle for gardenId
feature/garden/form/GardenFormScreen.kt                    — ZIP field with lookup note, unit toggle
feature/garden/detail/GardenDetailViewModel.kt
feature/garden/detail/GardenDetailScreen.kt
feature/garden/detail/components/BulkCareButtons.kt
feature/garden/detail/components/FrostContextBanner.kt     — color-coded by days until frost
feature/garden/detail/components/GardenInfoCard.kt
```

NavGraph: `Screen.Gardens`, `Screen.GardenDetail`, `Screen.GardenForm` — all wired

---

### ✅ Session 3 — Beds CRUD + Plant Grid
**Status: COMPLETE**

Deliverables:
- [x] Beds list (within a garden), create/edit/delete
- [x] Bed form: soil inputs (pH, clay/compost/sand %), grid dimensions
- [x] Interactive 1ft-cell grid: tap to place, tap occupied to open care sheet, long press to remove
- [x] "View Beds" button on GardenDetailScreen navigates to BedList

Key files created:
```
core/database/entities/BedEntity.kt
core/database/dao/BedDao.kt
feature/bed/BedRepository.kt
feature/bed/list/BedListScreen.kt + BedListViewModel.kt
feature/bed/form/BedFormScreen.kt + BedFormViewModel.kt
feature/bed/detail/BedDetailScreen.kt + BedDetailViewModel.kt
feature/bed/detail/components/PlantGrid.kt        ← Compose Canvas + tap/long-press gestures
feature/bed/detail/components/CareTrackingSheet.kt
feature/bed/detail/components/PlantPickerSheet.kt
```

Notes:
- `GardenDatabase` bumped to version 2 with `fallbackToDestructiveMigration()`
- Grid positions stored in inches (gridX/Y). UI col = gridX/12; multi-cell spans via `ceil(spacingIn/12)`
- Backend returns 409 on overlap → surfaced as "That cell is already occupied"
- "View Beds" button added to GardenDetailScreen; wired in NavGraph via `onOpenBeds`

---

### ✅ Session 4 — Plants List + Plant Detail
**Status: COMPLETE**

Deliverables:
- [x] Plants list: 4 tabs — Planning / Growing / Reminders / Timeline
- [x] Timeline tab: horizontal Gantt chart with frost date overlay lines (spring/fall)
- [x] Plant detail: 8 tabs (My Plant / Overview / Calendar / How to Grow / Companions / Soil / Nutrition / FAQs)
- [x] Status transitions via dropdown in My Plant tab
- [x] Plant create/edit form with garden picker

Key files created:
```
core/database/entities/PlantEntity.kt
core/database/dao/PlantDao.kt
feature/plant/PlantRepository.kt
feature/plant/list/PlantListViewModel.kt
feature/plant/list/PlantListScreen.kt             ← replaced stub
feature/plant/list/components/GanttChart.kt       ← Canvas, horizontalScroll, frost lines
feature/plant/detail/PlantDetailViewModel.kt
feature/plant/detail/PlantDetailScreen.kt         ← ScrollableTabRow, 8 tabs
feature/plant/detail/tabs/MyPlantTab.kt           ← status dropdown + dates + tasks
feature/plant/detail/tabs/OverviewTab.kt
feature/plant/detail/tabs/CalendarTab.kt
feature/plant/detail/tabs/HowToGrowTab.kt
feature/plant/detail/tabs/CompanionsTab.kt
feature/plant/detail/tabs/SoilTab.kt
feature/plant/detail/tabs/NutritionTab.kt
feature/plant/detail/tabs/FaqsTab.kt
feature/plant/form/PlantFormViewModel.kt
feature/plant/form/PlantFormScreen.kt
```

Notes:
- `GardenDatabase` bumped to version 3 with PlantEntity
- GanttChart: X-axis = Jan–Dec current year (52 weeks), bars color-coded by status
- Frost lines: blue dashed = lastFrostDate, orange dashed = firstFrostDate (from first garden)
- Reminders tab = plants with expectedHarvest within 30 days
- JSON tabs (HowToGrow, Nutrition, FAQs) use recursive renderer for JsonObject/Array/Primitive

---

### ✅ Session 5 — Tasks (List + Calendar)
**Status: COMPLETE**

Deliverables:
- [x] Tasks list: grouped by due date (Overdue/Today/This Week/Later/No Date), color-coded left bar by type
- [x] Swipe-to-complete (SwipeToDismissBox, left→complete, right→delete confirm)
- [x] Calendar month view: 7-column LazyVerticalGrid with colored dots per day, prev/next navigation
- [x] Day tap → ModalBottomSheet with tasks for that day
- [x] Task create/edit form with cascading garden→bed→plant pickers
- [x] TaskRepository.quickTask() wired to POST /api/gardens/{id}/quick-task

Key files created:
```
core/database/entities/TaskEntity.kt
core/database/dao/TaskDao.kt
feature/task/TaskRepository.kt
feature/task/list/TaskListViewModel.kt
feature/task/list/TaskListScreen.kt           ← replaced stub
feature/task/list/components/MonthGrid.kt     ← LazyVerticalGrid 7-col, task dots
feature/task/list/components/TaskRow.kt       ← SwipeToDismissBox
feature/task/form/TaskFormViewModel.kt
feature/task/form/TaskFormScreen.kt           ← cascading dropdowns
```

Notes:
- GardenDatabase bumped to version 4 with TaskEntity
- TaskDetail and TaskForm routes both render TaskFormScreen (edit vs. create via SavedStateHandle)
- Added `beds: Flow<List<Bed>>` to BedRepository for cross-garden lookups in TaskForm
- Calendar dots: up to 3 colored dots per day, color = TaskType.color

---

### ✅ Session 6 — Library Browser + Detail
**Status: COMPLETE**

Deliverables:
- [x] Library browser: search bar (300ms debounce), type filter chips (vegetable/herb/fruit/flower/tree/shrub), Paging 3 LazyColumn
- [x] Perenual external search tab (GET /api/perenual/search)
- [x] Library detail: 8 tabs (Overview/Seasons/How to Grow/Companions/Soil/Nutrition/FAQs/Images)
- [x] Image gallery: HorizontalPager with set-primary button
- [x] "Add to Garden" flow: ModalBottomSheet → garden picker → name/date → POST /api/plants → navigate to PlantDetail
- [x] Compare mode: checkbox in browser row (max 2), Compare icon triggers → PlantDiffScreen (side-by-side, diff rows highlighted)

Key files created:
```
feature/library/browser/LibraryBrowserPagingSource.kt    ← PagingSource<Int, LibraryListEntry>
feature/library/browser/LibraryBrowserViewModel.kt       ← Pager + debounce + Perenual
feature/library/browser/LibraryBrowserScreen.kt          ← replaced stub
feature/library/detail/LibraryDetailViewModel.kt
feature/library/detail/LibraryDetailScreen.kt            ← ScrollableTabRow, 8 tabs
feature/library/detail/tabs/LibraryTabs.kt               ← all tab composables in one file
feature/library/detail/components/ImageGalleryPager.kt   ← HorizontalPager + Coil
feature/library/detail/components/AddToGardenSheet.kt
feature/library/diff/PlantDiffViewModel.kt
feature/library/diff/PlantDiffScreen.kt                  ← side-by-side diff, red highlight on mismatch
```

Notes:
- No Room cache for library (8,988 entries served by Paging 3 network-only)
- Image URLs: `ServerConfig.baseUrl + "/static/plant_images/" + filename`
- Compare triggers via `compareIds: Set<Int>` in ViewModel; fires when size == 2

---

### ✅ Session 7 — Canvas Planner
**Status: COMPLETE**

Deliverables:
- [x] Canvas planner accessible from Garden Detail ("Open Planner" button)
- [x] Pinch-to-zoom (0.3x–2x) + two-finger pan via detectTransformGestures
- [x] Left sidebar (160dp): bed list, "+" button to add unplaced beds to canvas
- [x] Beds = labeled colored rectangles, drag to reposition, synced via POST /api/beds/{id}/position
- [x] Plants = colored circles with label, drag to reposition, synced via API
- [x] Right slide-in panel (200dp): Summary tab (selected bed info) + Plants tab (canvas plant list)
- [x] Undo/redo for move operations (ArrayDeque, max 20 per stack)

Key files created:
```
core/model/CanvasState.kt                        ← ViewTransform (scale/translateX/Y + clampedScale), CanvasSnapshot
feature/canvas/CanvasPlannerRepository.kt        ← loadBeds, loadCanvasPlants, updateBedPosition, updateCanvasPlantPosition
feature/canvas/CanvasPlannerViewModel.kt         ← CanvasPlannerUiState, undo/redo stacks, moveBedLocal/commitBedMove
feature/canvas/CanvasPlannerScreen.kt            ← replaced stub
feature/canvas/components/PlannerCanvas.kt       ← PIXELS_PER_FOOT=80, BED_COLORS[8], withTransform, hit-test, 3 pointerInput layers
feature/canvas/components/BedSidebarDrawer.kt
feature/canvas/components/CanvasToolbar.kt       ← Back, title, scale label, zoom ±, undo/redo, info panel toggle
feature/canvas/components/RightInfoPanel.kt      ← 2-tab Summary/Plants panel
```

Notes:
- `PIXELS_PER_FOOT = 80f` — bed at 4×8ft renders as 320×640px at 1x zoom
- Zoom centroid math: `newTx = centroid.x - ratio*(centroid.x - oldTx)` keeps point under fingers fixed
- Bed drag vs pan: tap selects bed first; `detectDragGestures` routes to `moveBedLocal` if `selectedBedId != null`, else pans
- `screenToWorld(pos)`: `x = (pos.x - translateX) / (scale * PPF)`, used for tap hit-testing
- Undo snapshot saved before each `commitBedMove`, `commitPlantMove`, `addBedToCanvas`
- No Room cache (canvas state is purely server-side + live ViewModel)

---

### ✅ Session 8 — Polish + Offline Handling
**Status: COMPLETE**

Deliverables:
- [x] Offline banner (ConnectivityManager callbackFlow), shown app-wide via MainActivity injection
- [x] Skeleton shimmer loaders — `SkeletonCard` + `SkeletonList` composables with animated Brush shimmer
- [x] Reusable `EmptyState` composable (title, subtitle, optional action button)
- [x] Deep links: `gardenapp://garden/{id}` → GardenDetail; `gardenapp://bed/{id}/grid` → BedDetail
- [x] Instrumented DAO tests: GardenDaoTest (6 cases), BedDaoTest (7 cases)

Key files created:
```
core/util/NetworkMonitor.kt                      ← @Singleton, callbackFlow with onAvailable/onLost, initial state emit
core/ui/components/OfflineBanner.kt              ← AnimatedVisibility slide-in banner on errorContainer
core/ui/components/SkeletonCard.kt               ← shimmerBrush() + SkeletonLine + SkeletonCard + SkeletonList
core/ui/components/EmptyState.kt                 ← reusable centered title/subtitle/action
androidTest/java/com/gardenapp/GardenDaoTest.kt  ← 6 in-memory Room tests
androidTest/java/com/gardenapp/BedDaoTest.kt     ← 7 in-memory Room tests
```

Files updated:
```
MainActivity.kt               ← @Inject NetworkMonitor, OfflineBanner above GardenNavGraph
AndroidManifest.xml           ← two deep-link intent-filters (gardenapp scheme)
navigation/NavGraph.kt        ← navDeepLink on GardenDetail + BedDetail composables
app/build.gradle.kts          ← room-testing, coroutines-test, core-ktx for androidTest
```

Notes:
- `NetworkMonitor` injected into `MainActivity` via field injection (`@Inject lateinit var`)
- `isOnline` collected as state with `initial = true` to avoid false offline flash on launch
- `SkeletonCard` and `SkeletonList` are standalone composables — drop-in replacement for `CircularProgressIndicator` in list screens
- DAO tests use `Room.inMemoryDatabaseBuilder` + `allowMainThreadQueries()` + `runTest` from coroutines-test
- App icon and splash screen left to v2 (requires design assets)

---

### ✅ Session — Startup caching + loading states
**Status: COMPLETE**

The app felt slow to start. The cause was the Dashboard: it is the nav start destination
and had no local cache at all, so launch meant four **serial** round trips
(`settings/default-garden` → `gardens` → `dashboard` → `weather`) before anything rendered
— against a Render free instance that takes 30–60 s to wake.

Deliverables:
- [x] Room caches for the dashboard, bed grid, plant detail, and two scalars (default garden, tip)
- [x] Every cached read is a pair: `cachedX()` (disk only, instant) + `refreshX(force)` (TTL-gated)
- [x] Dashboard refresh is parallel; a warm launch has **zero** serial dependencies
- [x] A failed refresh no longer blanks a populated screen (the old code clobbered to `null`)
- [x] `refresh()` no longer double-fetches the dashboard
- [x] Shimmer skeletons on cold load; thin progress bar over cached content while refreshing
- [x] "Updated 2h ago" / "Offline — showing saved data" status line
- [x] Room schema export enabled + real `Migration(6,7)` + `MigrationTest`
- [x] Cache cleared on sign-out and on server-URL change

Key files created:
```
core/database/entities/CacheEntities.kt   ← 4 JSON-blob entities + Cached<T> wrapper
core/database/dao/CacheDao.kt             ← one DAO for all 4 cache tables
core/database/Migrations.kt               ← MIGRATION_6_7 (SQL copied from schemas/7.json)
core/database/CacheCleaner.kt             ← clearAll() in one transaction
core/ui/components/CacheStatusLine.kt     ← staleness / offline line
app/schemas/…/6.json, 7.json              ← exported Room schemas (checked in)
androidTest/…/CacheDaoTest.kt             ← 8 in-memory Room tests
androidTest/…/MigrationTest.kt            ← runMigrationsAndValidate + settings-survive-upgrade
test/…/DashboardViewModelTest.kt          ← 8 tests (cache-first, null-clobber, double-fetch, parallelism)
test/…/PlantDetailViewModelTest.kt        ← 5 tests
test/…/core/util/DateUtilTest.kt          ← relativeSince boundaries
```

Notes:
- **TTLs**: dashboard 5 min, bed grid 2 min (edits write through), plant detail 5 min,
  default garden 24 h (refresh gate only — the cached value is always returned),
  tip of day is **day-keyed, not TTL-keyed** (the backend derives it from the date).
- **Blobs, not columns.** `plant_detail_cache` in particular must stay out of the `plants`
  table: `PlantDetail` and `Plant` carry different fields and every upsert is `REPLACE`, so
  folding one into the other would null the list screen's columns.
- **Room now exports schemas** (`app/schemas`, wired as an androidTest asset dir). This is
  what makes `MigrationTest` possible — Room throws rather than falling back destructively
  when a migration exists but leaves an unexpected schema, so a typo would be a launch crash.
  Regenerate migration SQL from the exported JSON; never retype it.
- **`notification_settings` is not a cache** — it is device-local, opt-in, and unrecoverable.
  `CacheCleaner` and the migration both deliberately preserve it.
- The cache is **not** keyed by server URL; instead it is wiped whenever the URL changes
  (`SettingsViewModel.saveUrl`, `LoginViewModel.login` — both writers must do it). Prod and a
  LAN backend reuse the same integer ids, so a mixed database shows the wrong garden.
- OkHttp `readTimeout` 30 s → 60 s: 30 s reliably failed on Render's cold start. The connect
  timeout stays at 15 s, so a genuinely dead server still fails fast.
- Writes are still online-only. There is no offline mutation queue, and no incremental sync —
  the backend has no `updated_at`, ETag, `?since=`, or tombstones, so refresh is full-replace.

---

## Features Deferred to v2

| Feature | Reason |
|---|---|
| SVG annotation drawing tools (7 modes) | High complexity, low mobile utility |
| Plant Diff copy/bulk-fill | Power-user workflow |
| Bed resize handles on canvas | Fiddly on touch |
| Library clone entry | Admin workflow |
| Gantt chart interactive editing | Unusable on touch |
| Task drag-to-reschedule on calendar | Complex gesture conflicts |
| AI chat widget | Requires session management |

---

## Key Reference Files (Web App)

| Purpose | File |
|---|---|
| All API types | `packages/shared/src/gardens.ts`, `beds.ts`, `plants.ts`, `tasks.ts`, `library.ts` |
| Backend endpoints | `apps/backend/app/routers/` |
| SQLAlchemy models | `apps/backend/app/db/models.py` |
| Canvas planner types | `apps/web/src/components/Planner/types.ts` |
