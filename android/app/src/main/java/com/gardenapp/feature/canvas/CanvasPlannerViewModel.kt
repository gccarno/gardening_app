package com.gardenapp.feature.canvas

import androidx.compose.ui.geometry.Offset
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.CanvasPlant
import com.gardenapp.core.model.CanvasSnapshot
import com.gardenapp.core.model.ViewTransform
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CanvasPlannerUiState(
    val gardenId: Int = 0,
    val sidebarBeds: List<Bed> = emptyList(),      // all beds in garden (for sidebar)
    val placedBeds: List<Bed> = emptyList(),        // beds with pos_x/pos_y set
    val canvasPlants: List<CanvasPlant> = emptyList(),
    val transform: ViewTransform = ViewTransform(scale = 1f, translateX = 32f, translateY = 32f),
    val selectedBedId: Int? = null,
    val selectedPlantId: Int? = null,
    val showRightPanel: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
    val canUndo: Boolean = false,
    val canRedo: Boolean = false,
)

@HiltViewModel
class CanvasPlannerViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: CanvasPlannerRepository,
) : ViewModel() {

    private val gardenId: Int = checkNotNull(savedStateHandle["gardenId"])

    private val _uiState = MutableStateFlow(CanvasPlannerUiState(gardenId = gardenId))
    val uiState: StateFlow<CanvasPlannerUiState> = _uiState

    private val undoStack = ArrayDeque<CanvasSnapshot>()
    private val redoStack = ArrayDeque<CanvasSnapshot>()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val bedsResult = repository.loadBeds(gardenId)
            val plantsResult = repository.loadCanvasPlants(gardenId)

            if (bedsResult is NetworkResult.Success) {
                val all = bedsResult.data
                _uiState.value = _uiState.value.copy(
                    sidebarBeds = all,
                    placedBeds = all.filter { it.posX != null && it.posY != null },
                )
            } else if (bedsResult is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = bedsResult.message)
            }

            if (plantsResult is NetworkResult.Success) {
                _uiState.value = _uiState.value.copy(canvasPlants = plantsResult.data)
            }

            _uiState.value = _uiState.value.copy(isLoading = false)
        }
    }

    fun setTransform(transform: ViewTransform) {
        _uiState.value = _uiState.value.copy(transform = transform)
    }

    fun selectBed(bedId: Int?) {
        _uiState.value = _uiState.value.copy(selectedBedId = bedId, selectedPlantId = null)
    }

    fun selectPlant(plantId: Int?) {
        _uiState.value = _uiState.value.copy(selectedPlantId = plantId, selectedBedId = null)
    }

    // Local move (during drag, no API call)
    fun moveBedLocal(bedId: Int, delta: Offset) {
        val beds = _uiState.value.placedBeds.map { bed ->
            if (bed.id == bedId) bed.copy(posX = (bed.posX ?: 0f) + delta.x, posY = (bed.posY ?: 0f) + delta.y)
            else bed
        }
        _uiState.value = _uiState.value.copy(placedBeds = beds)
    }

    fun movePlantLocal(plantId: Int, delta: Offset) {
        val plants = _uiState.value.canvasPlants.map { plant ->
            if (plant.id == plantId) plant.copy(posX = plant.posX + delta.x, posY = plant.posY + delta.y)
            else plant
        }
        _uiState.value = _uiState.value.copy(canvasPlants = plants)
    }

    // Commit after drag ends — sync to API and push undo
    fun commitBedMove(bedId: Int) {
        val bed = _uiState.value.placedBeds.find { it.id == bedId } ?: return
        pushUndo()
        viewModelScope.launch {
            repository.updateBedPosition(bedId, bed.posX ?: 0f, bed.posY ?: 0f)
        }
    }

    fun commitPlantMove(plantId: Int) {
        val plant = _uiState.value.canvasPlants.find { it.id == plantId } ?: return
        pushUndo()
        viewModelScope.launch {
            repository.updateCanvasPlantPosition(plantId, plant.posX, plant.posY)
        }
    }

    // Add a bed from sidebar to canvas at a default position
    fun addBedToCanvas(bed: Bed) {
        if (_uiState.value.placedBeds.any { it.id == bed.id }) return
        val newPosX = 2f
        val newPosY = (_uiState.value.placedBeds.size * 12f) + 2f
        val updatedBed = bed.copy(posX = newPosX, posY = newPosY)
        val newPlaced = _uiState.value.placedBeds + updatedBed
        pushUndo()
        _uiState.value = _uiState.value.copy(placedBeds = newPlaced)
        viewModelScope.launch {
            repository.updateBedPosition(bed.id, newPosX, newPosY)
        }
    }

    fun toggleRightPanel() {
        _uiState.value = _uiState.value.copy(showRightPanel = !_uiState.value.showRightPanel)
    }

    fun undo() {
        val snapshot = undoStack.removeLastOrNull() ?: return
        redoStack.addLast(currentSnapshot())
        if (redoStack.size > 20) redoStack.removeFirst()
        restoreSnapshot(snapshot)
        updateUndoRedoState()
    }

    fun redo() {
        val snapshot = redoStack.removeLastOrNull() ?: return
        undoStack.addLast(currentSnapshot())
        restoreSnapshot(snapshot)
        updateUndoRedoState()
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }

    private fun pushUndo() {
        undoStack.addLast(currentSnapshot())
        if (undoStack.size > 20) undoStack.removeFirst()
        redoStack.clear()
        updateUndoRedoState()
    }

    private fun currentSnapshot() = CanvasSnapshot(
        beds = _uiState.value.placedBeds,
        canvasPlants = _uiState.value.canvasPlants,
    )

    private fun restoreSnapshot(snapshot: CanvasSnapshot) {
        _uiState.value = _uiState.value.copy(
            placedBeds = snapshot.beds,
            canvasPlants = snapshot.canvasPlants,
        )
    }

    private fun updateUndoRedoState() {
        _uiState.value = _uiState.value.copy(
            canUndo = undoStack.isNotEmpty(),
            canRedo = redoStack.isNotEmpty(),
        )
    }
}
