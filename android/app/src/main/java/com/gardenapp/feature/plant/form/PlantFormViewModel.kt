package com.gardenapp.feature.plant.form

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import com.gardenapp.feature.plant.PlantRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlantFormUiState(
    val name: String = "",
    val notes: String = "",
    val plantedDate: String = "",
    val selectedGardenId: Int? = null,
    val gardens: List<Garden> = emptyList(),
    val isSaving: Boolean = false,
    val error: String? = null,
    val isEditMode: Boolean = false,
    val plantId: Int? = null,
)

@HiltViewModel
class PlantFormViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val plantRepository: PlantRepository,
    private val gardenRepository: GardenRepository,
) : ViewModel() {

    private val plantId: Int? = savedStateHandle.get<Int>("plantId")?.takeIf { it != -1 }

    private val _uiState = MutableStateFlow(PlantFormUiState(
        isEditMode = plantId != null,
        plantId = plantId,
    ))
    val uiState: StateFlow<PlantFormUiState> = _uiState

    init {
        viewModelScope.launch {
            val gardens = gardenRepository.gardens.first()
            _uiState.value = _uiState.value.copy(
                gardens = gardens,
                selectedGardenId = gardens.firstOrNull()?.id,
            )
        }
        if (plantId != null) loadPlant()
    }

    private fun loadPlant() {
        viewModelScope.launch {
            when (val result = plantRepository.getDetail(plantId!!)) {
                is NetworkResult.Success -> {
                    val p = result.data
                    _uiState.value = _uiState.value.copy(
                        name = p.name,
                        notes = p.notes ?: "",
                        plantedDate = p.plantedDate ?: "",
                        selectedGardenId = p.gardenId,
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> {}
            }
        }
    }

    fun onNameChange(v: String) { _uiState.value = _uiState.value.copy(name = v) }
    fun onNotesChange(v: String) { _uiState.value = _uiState.value.copy(notes = v) }
    fun onPlantedDateChange(v: String) { _uiState.value = _uiState.value.copy(plantedDate = v) }
    fun onGardenSelect(id: Int) { _uiState.value = _uiState.value.copy(selectedGardenId = id) }
    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }

    fun save(onSaved: (Int) -> Unit) {
        val state = _uiState.value
        if (state.name.isBlank()) {
            _uiState.value = state.copy(error = "Plant name is required")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true)
            val result = if (state.isEditMode && plantId != null) {
                plantRepository.updatePlant(
                    id = plantId,
                    name = state.name.trim(),
                    notes = state.notes.ifBlank { null },
                    plantedDate = state.plantedDate.ifBlank { null },
                    expectedHarvest = null,
                )
            } else {
                plantRepository.createPlant(
                    name = state.name.trim(),
                    gardenId = state.selectedGardenId,
                    libraryId = null,
                    plantedDate = state.plantedDate.ifBlank { null },
                    notes = state.notes.ifBlank { null },
                )
            }
            when (result) {
                is NetworkResult.Success -> onSaved(result.data.id)
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isSaving = false, error = result.message,
                )
                else -> _uiState.value = _uiState.value.copy(isSaving = false)
            }
        }
    }
}
