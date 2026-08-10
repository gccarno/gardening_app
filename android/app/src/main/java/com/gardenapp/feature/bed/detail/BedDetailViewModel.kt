package com.gardenapp.feature.bed.detail

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.HealthScore
import com.gardenapp.core.model.LibraryListEntry
import com.gardenapp.core.model.PlantObservation
import com.gardenapp.core.model.RotationWarnings
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.bed.BedRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BedDetailUiState(
    val bed: Bed? = null,
    val placed: List<GridPlant> = emptyList(),
    val isLoading: Boolean = false,
    val isPlacing: Boolean = false,
    val error: String? = null,
    val message: String? = null,
    // Plant picker sheet
    val showPickerForCell: Pair<Int, Int>? = null,   // (gridX, gridY) in inches
    val pickerQuery: String = "",
    val pickerResults: List<LibraryListEntry> = emptyList(),
    val pickerLoading: Boolean = false,
    // Pending plant removal (long press → confirm)
    val pendingRemoval: GridPlant? = null,
    // Rotation conflict confirmation before placing a picked plant
    val pendingPlacement: LibraryListEntry? = null,
    val placementWarning: String? = null,
    // Care tracking sheet
    val careSheetPlant: BedPlantDetail? = null,
    val careLastWatered: String = "",
    val careLastFertilized: String = "",
    val careLastHarvest: String = "",
    val careHealthNotes: String = "",
    val careStage: String = "",
    val carePlantedDate: String = "",
    val careTransplantDate: String = "",
    val carePlantNotes: String = "",
    val isSavingCare: Boolean = false,
    // Observations (shown in care sheet)
    val observations: List<PlantObservation> = emptyList(),
    val healthScore: HealthScore? = null,
    val obsLoading: Boolean = false,
    // Observation add form
    val showObsForm: Boolean = false,
    val obsType: String = "healthy",
    val obsSeverity: Int = 3,
    val obsNotes: String = "",
    // Rotation warnings
    val rotationWarnings: RotationWarnings? = null,
)

@HiltViewModel
class BedDetailViewModel @Inject constructor(
    private val repository: BedRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val bedId: Int = checkNotNull(savedStateHandle.get<String>("bedId")?.toInt())

    private val _uiState = MutableStateFlow(BedDetailUiState())
    val uiState: StateFlow<BedDetailUiState> = _uiState.asStateFlow()

    private var searchJob: Job? = null

    /** Cell (inches) the picker was opened for; survives the rotation-warning confirm step. */
    private var targetCell: Pair<Int, Int>? = null

    init {
        Log.d(TAG, "init bedId=$bedId")
        loadGrid()
    }

    fun loadGrid() {
        viewModelScope.launch {
            Log.d(TAG, "loadGrid bedId=$bedId")
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val r = repository.getBedGrid(bedId)) {
                is NetworkResult.Success -> {
                    Log.d(TAG, "loadGrid ok bed='${r.data.bed.name}' placed=${r.data.placed.size}")
                    _uiState.value = _uiState.value.copy(
                        bed = r.data.bed, placed = r.data.placed, isLoading = false,
                    )
                }
                is NetworkResult.Error -> {
                    Log.e(TAG, "loadGrid error: ${r.message}")
                    _uiState.value = _uiState.value.copy(
                        isLoading = false, error = r.message,
                    )
                }
                else -> Unit
            }
            loadRotationWarnings()
        }
    }

    private fun loadRotationWarnings() {
        viewModelScope.launch {
            when (val r = repository.getRotationWarnings(bedId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(rotationWarnings = r.data)
                else -> Unit
            }
        }
    }

    // ── Plant placement ──────────────────────────────────────────────────────

    /** Resolves the plant covering this cell — a plant wider than 12in covers several. */
    private fun plantAt(gridX: Int, gridY: Int): GridPlant? =
        cellToPlantMap(_uiState.value.placed)[
            Pair(gridX / INCHES_PER_CELL, gridY / INCHES_PER_CELL)
        ]

    fun onCellTap(gridX: Int, gridY: Int) {
        val bp = plantAt(gridX, gridY)
        if (bp != null) {
            // Open care sheet
            openCareSheet(bp.id)
        } else {
            // Open plant picker
            _uiState.value = _uiState.value.copy(
                showPickerForCell = Pair(gridX, gridY),
                pickerQuery = "",
                pickerResults = emptyList(),
            )
            searchLibrary("")
        }
    }

    fun onCellLongPress(gridX: Int, gridY: Int) {
        val bp = plantAt(gridX, gridY) ?: return
        _uiState.value = _uiState.value.copy(pendingRemoval = bp)
    }

    fun dismissRemoval() { _uiState.value = _uiState.value.copy(pendingRemoval = null) }

    fun confirmRemoval() {
        val bp = _uiState.value.pendingRemoval ?: return
        _uiState.value = _uiState.value.copy(pendingRemoval = null)
        viewModelScope.launch {
            when (val r = repository.removePlant(bp.id)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                    placed = _uiState.value.placed.filter { it.id != bp.id },
                    message = "${bp.plantName} removed",
                )
                is NetworkResult.Error -> {
                    Log.e(TAG, "removePlant error: ${r.message}")
                    _uiState.value = _uiState.value.copy(
                        error = r.message ?: "Could not remove ${bp.plantName}",
                    )
                }
                else -> Unit
            }
        }
    }

    // ── Plant picker ─────────────────────────────────────────────────────────

    fun onPickerQueryChange(q: String) {
        _uiState.value = _uiState.value.copy(pickerQuery = q)
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(300) // debounce
            searchLibrary(q)
        }
    }

    private fun searchLibrary(q: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(pickerLoading = true)
            when (val r = repository.searchLibrary(q)) {
                is NetworkResult.Success ->
                    _uiState.value = _uiState.value.copy(pickerResults = r.data.entries, pickerLoading = false)
                is NetworkResult.Error ->
                    _uiState.value = _uiState.value.copy(pickerLoading = false)
                else -> Unit
            }
        }
    }

    /**
     * Checks crop rotation for the candidate before placing. On a conflict the user
     * gets a confirm step (matching the web's pre-placement warning); otherwise the
     * plant goes straight in.
     */
    fun onLibraryEntrySelected(entry: LibraryListEntry) {
        val cell = _uiState.value.showPickerForCell ?: return
        targetCell = cell
        _uiState.value = _uiState.value.copy(showPickerForCell = null, isPlacing = true)
        viewModelScope.launch {
            val r = repository.getRotationWarnings(bedId, entry.id)
            val warning = (r as? NetworkResult.Success)
                ?.data?.takeIf { it.conflict }?.warning
            if (warning != null) {
                _uiState.value = _uiState.value.copy(
                    isPlacing = false, pendingPlacement = entry, placementWarning = warning,
                )
            } else {
                placePlant(entry)
            }
        }
    }

    fun dismissPlacement() {
        targetCell = null
        _uiState.value = _uiState.value.copy(pendingPlacement = null, placementWarning = null)
    }

    fun confirmPlacement() {
        val entry = _uiState.value.pendingPlacement ?: return
        _uiState.value = _uiState.value.copy(
            pendingPlacement = null, placementWarning = null, isPlacing = true,
        )
        viewModelScope.launch { placePlant(entry) }
    }

    private suspend fun placePlant(entry: LibraryListEntry) {
        val cell = targetCell ?: return
        val spacingIn = entry.spacingIn?.toInt()?.coerceAtLeast(6) ?: 12
        Log.d(TAG, "placePlant cell=${cell} libraryId=${entry.id} spacing=$spacingIn")
        when (val r = repository.placePlant(bedId, cell.first, cell.second, entry.id, spacingIn)) {
            is NetworkResult.Success -> {
                Log.d(TAG, "placePlant ok id=${r.data.id} name='${r.data.plantName}'")
                val newPlant = GridPlant(
                    id = r.data.id, gridX = cell.first, gridY = cell.second,
                    plantId = r.data.plantId, plantName = r.data.plantName,
                    imageFilename = r.data.imageFilename, spacingIn = r.data.spacingIn,
                )
                _uiState.value = _uiState.value.copy(
                    placed = _uiState.value.placed + newPlant,
                    isPlacing = false,
                    message = "${entry.name} placed",
                )
                loadRotationWarnings()
            }
            is NetworkResult.Error -> {
                Log.e(TAG, "placePlant error: ${r.message}")
                _uiState.value = _uiState.value.copy(
                    isPlacing = false,
                    error = if (r.message?.contains("409") == true || r.message?.contains("overlap") == true)
                        "That cell is already occupied" else r.message,
                )
            }
            else -> Unit
        }
        targetCell = null
    }

    fun dismissPicker() { _uiState.value = _uiState.value.copy(showPickerForCell = null) }

    // ── Care tracking sheet ──────────────────────────────────────────────────

    private fun openCareSheet(bedPlantId: Int) {
        viewModelScope.launch {
            when (val r = repository.getBedPlant(bedPlantId)) {
                is NetworkResult.Success -> {
                    val bp = r.data
                    _uiState.value = _uiState.value.copy(
                        careSheetPlant = bp,
                        careLastWatered = bp.lastWatered ?: "",
                        careLastFertilized = bp.lastFertilized ?: "",
                        careLastHarvest = bp.lastHarvest ?: "",
                        careHealthNotes = bp.healthNotes ?: "",
                        careStage = bp.stage ?: "",
                        carePlantedDate = bp.plantedDate ?: "",
                        careTransplantDate = bp.transplantDate ?: "",
                        carePlantNotes = bp.plantNotes ?: "",
                    )
                    loadObservations(bedPlantId)
                }
                else -> Unit
            }
        }
    }

    fun onCareWateredChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careLastWatered = v)
    }
    fun onCareFertilizedChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careLastFertilized = v)
    }
    fun onCareHarvestChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careLastHarvest = v)
    }
    fun onCareNotesChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careHealthNotes = v)
    }
    fun onCareStageChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careStage = v)
    }
    fun onCarePlantedDateChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(carePlantedDate = v)
    }
    fun onCareTransplantDateChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careTransplantDate = v)
    }
    fun onCarePlantNotesChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(carePlantNotes = v)
    }

    fun saveCare() {
        val bp = _uiState.value.careSheetPlant ?: return
        val s = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingCare = true)
            val r = repository.saveCare(
                bp.id,
                lastWatered = s.careLastWatered.takeIf { it.isNotBlank() },
                lastFertilized = s.careLastFertilized.takeIf { it.isNotBlank() },
                lastHarvest = s.careLastHarvest.takeIf { it.isNotBlank() },
                healthNotes = s.careHealthNotes.takeIf { it.isNotBlank() },
                stage = s.careStage.takeIf { it.isNotBlank() },
                plantedDate = s.carePlantedDate.takeIf { it.isNotBlank() },
                transplantDate = s.careTransplantDate.takeIf { it.isNotBlank() },
                plantNotes = s.carePlantNotes.takeIf { it.isNotBlank() },
            )
            _uiState.value = when (r) {
                is NetworkResult.Error -> _uiState.value.copy(
                    isSavingCare = false, error = r.message ?: "Could not save care",
                )
                else -> _uiState.value.copy(
                    isSavingCare = false, careSheetPlant = null, message = "Care saved",
                )
            }
        }
    }

    fun dismissCareSheet() {
        _uiState.value = _uiState.value.copy(
            careSheetPlant = null,
            careStage = "",
            observations = emptyList(),
            healthScore = null,
            showObsForm = false,
        )
    }
    fun dismissMessage() { _uiState.value = _uiState.value.copy(message = null) }
    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }

    // ── Observations ─────────────────────────────────────────────────────────

    private fun loadObservations(bedPlantId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(obsLoading = true)
            when (val r = repository.getObservations(bedPlantId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(observations = r.data, obsLoading = false)
                else -> _uiState.value = _uiState.value.copy(obsLoading = false)
            }
            when (val r = repository.getHealthScore(bedPlantId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(healthScore = r.data)
                else -> Unit
            }
        }
    }

    fun showObsForm() { _uiState.value = _uiState.value.copy(showObsForm = true, obsType = "healthy", obsSeverity = 3, obsNotes = "") }
    fun dismissObsForm() { _uiState.value = _uiState.value.copy(showObsForm = false) }
    fun setObsType(v: String) { _uiState.value = _uiState.value.copy(obsType = v) }
    fun setObsSeverity(v: Int) { _uiState.value = _uiState.value.copy(obsSeverity = v) }
    fun setObsNotes(v: String) { _uiState.value = _uiState.value.copy(obsNotes = v) }

    fun submitObservation() {
        val bp = _uiState.value.careSheetPlant ?: return
        val s = _uiState.value
        viewModelScope.launch {
            repository.createObservation(bp.id, s.obsType, s.obsSeverity, s.obsNotes.takeIf { it.isNotBlank() }, null)
            _uiState.value = _uiState.value.copy(showObsForm = false)
            loadObservations(bp.id)
        }
    }

    fun deleteObservation(obsId: Int) {
        val bpId = _uiState.value.careSheetPlant?.id ?: return
        viewModelScope.launch {
            repository.deleteObservation(obsId)
            loadObservations(bpId)
        }
    }

    companion object {
        private const val TAG = "BedDetailVM"
    }
}
