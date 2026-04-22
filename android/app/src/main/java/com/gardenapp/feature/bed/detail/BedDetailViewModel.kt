package com.gardenapp.feature.bed.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.LibraryListEntry
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
    // Care tracking sheet
    val careSheetPlant: BedPlantDetail? = null,
    val careLastWatered: String = "",
    val careLastFertilized: String = "",
    val careHealthNotes: String = "",
    val isSavingCare: Boolean = false,
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

    init { loadGrid() }

    fun loadGrid() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val r = repository.getBedGrid(bedId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                    bed = r.data.bed, placed = r.data.placed, isLoading = false,
                )
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isLoading = false, error = r.message,
                )
                else -> Unit
            }
        }
    }

    // ── Plant placement ──────────────────────────────────────────────────────

    fun onCellTap(gridX: Int, gridY: Int) {
        val occupied = _uiState.value.placed.any { it.gridX == gridX && it.gridY == gridY }
        if (occupied) {
            // Open care sheet
            val bp = _uiState.value.placed.find { it.gridX == gridX && it.gridY == gridY }
            bp?.let { openCareSheet(it.id) }
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
        val bp = _uiState.value.placed.find { it.gridX == gridX && it.gridY == gridY } ?: return
        viewModelScope.launch {
            repository.removePlant(bp.id)
            _uiState.value = _uiState.value.copy(
                placed = _uiState.value.placed.filter { it.id != bp.id },
                message = "${bp.plantName} removed",
            )
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

    fun onLibraryEntrySelected(entry: LibraryListEntry) {
        val cell = _uiState.value.showPickerForCell ?: return
        val spacingIn = entry.spacingIn?.toInt()?.coerceAtLeast(6) ?: 12
        _uiState.value = _uiState.value.copy(showPickerForCell = null, isPlacing = true)
        viewModelScope.launch {
            when (val r = repository.placePlant(bedId, cell.first, cell.second, entry.id, spacingIn)) {
                is NetworkResult.Success -> {
                    // Add to local state immediately; full reload refreshes ordering
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
                }
                is NetworkResult.Error ->
                    _uiState.value = _uiState.value.copy(
                        isPlacing = false,
                        error = if (r.message?.contains("409") == true || r.message?.contains("overlap") == true)
                            "That cell is already occupied" else r.message,
                    )
                else -> Unit
            }
        }
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
                        careHealthNotes = bp.healthNotes ?: "",
                    )
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
    fun onCareNotesChange(v: String) = _uiState.value.let {
        _uiState.value = it.copy(careHealthNotes = v)
    }

    fun saveCare() {
        val bp = _uiState.value.careSheetPlant ?: return
        val s = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingCare = true)
            repository.saveCare(
                bp.id,
                lastWatered = s.careLastWatered.takeIf { it.isNotBlank() },
                lastFertilized = s.careLastFertilized.takeIf { it.isNotBlank() },
                healthNotes = s.careHealthNotes.takeIf { it.isNotBlank() },
            )
            _uiState.value = _uiState.value.copy(isSavingCare = false, careSheetPlant = null, message = "Care saved")
        }
    }

    fun dismissCareSheet() { _uiState.value = _uiState.value.copy(careSheetPlant = null) }
    fun dismissMessage() { _uiState.value = _uiState.value.copy(message = null) }
    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
}
