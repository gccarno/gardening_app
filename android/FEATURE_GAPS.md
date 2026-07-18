# Android Feature Gaps

Features that exist in the React web app (`apps/web/`) but are not yet implemented in the Android app. Check items off as they are ported.

Last audited: 2026-07-02

---

## Platform-only (intentional)

- **Account registration & garden sharing management** — web-only by design.
  Android has sign-in (`feature/auth/LoginScreen.kt`, token in DataStore,
  `AuthInterceptor`) and sign-out (Settings), but creating accounts and
  managing Owner/Editor/Viewer members happens on the web app
  (`GardenMembers.tsx` on the garden detail page).

---

## High Priority

- [x] **Seed Room** (`SeedRoom.tsx`)
  - 24-slot virtual seed tray shelf per garden
  - Stages: sowing → germinating → seedling → hardening → ready
  - API: `GET/POST /api/gardens/{id}/seed-room`, `POST /api/seed-room/{id}/advance-stage`, `DELETE /api/seed-room/{id}`

- [x] **Journal** (`Journal.tsx`)
  - Date-based garden journal entries with tags
  - Pagination (20 per page), delete support
  - API: `GET/POST /api/gardens/{id}/journal`, `GET/PUT/DELETE /api/journal/{id}`

- [x] **Compost** (`Compost.tsx`)
  - Bin management with stage tracking: building → active → curing → ready
  - Material logging (name, date, weight in lbs)
  - API: `GET/POST /api/gardens/{id}/compost`, `PUT/DELETE /api/compost/{id}`, `POST /api/compost/{id}/add-material`, `POST /api/compost/{id}/advance-stage`

---

## Medium Priority

- [x] **AI Chat Widget** (`ChatWidget.tsx`)
  - Floating FAB opens a bottom sheet chat assistant
  - Contextual to current garden (name + zone)
  - Conversation history maintained in ViewModel (not persisted)
  - API: `POST /api/chat`, `POST /api/chat/restart-model`
  - Quick-start suggestion chips on first open
  - Note: requires Ollama/Anthropic/OpenAI backend running

- [x] **Rain Log** (Dashboard)
  - Manual rainfall entry with slider (0–4 in) and date field
  - API: `POST /api/gardens/{id}/log-rain`
  - Shows "✓ Saved" confirmation for 2 seconds

- [x] **Crop Rotation Warnings** (`BedDetail.tsx`)
  - Shows botanical family conflicts within a bed
  - Loads on bed detail open; shown as a teal card below the plant legend
  - API: `GET /api/beds/{id}/rotation-warnings`

- [x] **Plant Sync Modal** (`PlantList.tsx`)
  - Reconciles care date discrepancies between `Plant` and `BedPlant` records
  - Sync icon button in Plants top bar; dialog with select-all and per-item checkboxes
  - API: `GET /api/plants/sync-preview`, `POST /api/plants/sync`

---

## Low Priority

- [x] **Tip of the Day** (Dashboard)
  - Daily gardening tip from ChromaDB RAG
  - Shown as a card on the Dashboard when tip is available
  - API: `GET /api/tip-of-the-day`

- [x] **Succession Wave Labels** (Plant list)
  - Badge shown next to plant name in PlantListScreen when `succession_label` is set
  - Data already returned by the API; `successionLabel` added to Plant model + DB entity

- [ ] **Full Library Edit** (`LibraryEdit.tsx`)
  - 10-tab editor for all PlantLibrary fields
  - Android has `quick-edit` only (`POST /api/library/{id}/quick-edit`)
  - Full edit uses `PATCH /api/library/{id}`

- [ ] **Canvas Annotations / Drawing Tools** (`Canvas/AnnotationOverlay.tsx`)
  - Shape drawing overlay on the planner canvas (rectangles, lines, circles, colors, patterns)
  - API: `GET/POST /api/gardens/{id}/annotations` — already wired in ApiService

- [ ] **Garden/Bed Background Image Upload**
  - Upload a custom background image behind the planner or bed grid
  - API: `POST /api/gardens/{id}/upload-background`, `POST /api/beds/{id}/upload-background`

- [x] **Plant Health Observations** (BedDetail care sheet)
  - Per-bed-plant health observations with type, severity, notes, and health score
  - Shown in the care tracking bottom sheet alongside care log
  - API: `GET/POST /api/bedplants/{id}/observations`, `DELETE /api/observations/{id}`, `GET /api/bedplants/{id}/health-score`

---

## Platform-Specific (Intentionally Web-Only)

- **Settings screen (server URL)** — Android-only, web is same-origin
- **Offline caching (Room DB)** — Android-only
- **Network status banner** — Android-only
- **Deep links** (`gardenapp://garden/{id}`) — Android-only
- **Notifications (watering / growth / time-of-year planting)** — Android-only.
  Hourly WorkManager worker + per-garden settings (enable, frequency, earliest
  hour per type) stored device-local in Room (`notification_settings`).
  Watering reminders delegate rain-skip to `GET /api/gardens/{id}/watering-status`
  (backend watering engine: 14-day rainfall + forecast → urgency score).
  System notifications (channels per type) + in-app snackbar when foregrounded
  (`core/notifications/`). The web app has no equivalent and none is planned.
