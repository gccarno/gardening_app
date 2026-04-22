package com.gardenapp.feature.garden.form

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GardenFormUiState(
    val name: String = "",
    val description: String = "",
    val zipCode: String = "",
    val wateringFrequencyDays: String = "",
    val waterSource: String = "",
    val unit: String = "ft",
    // Loaded when editing
    val existingGarden: Garden? = null,
    val isSaving: Boolean = false,
    val error: String? = null,
    val savedGardenId: Int? = null, // non-null signals navigation after save
)

@HiltViewModel
class GardenFormViewModel @Inject constructor(
    private val repository: GardenRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int? = savedStateHandle.get<String>("gardenId")?.toIntOrNull()

    private val _uiState = MutableStateFlow(GardenFormUiState())
    val uiState: StateFlow<GardenFormUiState> = _uiState.asStateFlow()

    init {
        gardenId?.let { loadGarden(it) }
    }

    private fun loadGarden(id: Int) {
        viewModelScope.launch {
            when (val result = repository.getGarden(id)) {
                is NetworkResult.Success -> {
                    val g = result.data
                    _uiState.value = _uiState.value.copy(
                        name = g.name,
                        description = g.description ?: "",
                        zipCode = g.zipCode ?: "",
                        wateringFrequencyDays = g.wateringFrequencyDays?.toString() ?: "",
                        waterSource = g.waterSource ?: "",
                        unit = g.unit,
                        existingGarden = g,
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> Unit
            }
        }
    }

    fun onNameChange(v: String) = update { copy(name = v) }
    fun onDescriptionChange(v: String) = update { copy(description = v) }
    fun onZipChange(v: String) = update { copy(zipCode = v.take(5)) }
    fun onWateringFreqChange(v: String) = update { copy(wateringFrequencyDays = v.filter(Char::isDigit).take(3)) }
    fun onWaterSourceChange(v: String) = update { copy(waterSource = v) }
    fun onUnitChange(v: String) = update { copy(unit = v) }
    fun dismissError() = update { copy(error = null) }

    fun save() {
        val state = _uiState.value
        if (state.name.isBlank()) {
            _uiState.value = state.copy(error = "Name is required")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true, error = null)
            val result = if (gardenId == null) {
                repository.createGarden(
                    name = state.name.trim(),
                    description = state.description.takeIf { it.isNotBlank() },
                    zipCode = state.zipCode.takeIf { it.length == 5 },
                )
            } else {
                repository.updateGarden(
                    id = gardenId,
                    fields = buildMap {
                        put("name", state.name.trim())
                        put("description", state.description.takeIf { it.isNotBlank() })
                        put("zip_code", state.zipCode.takeIf { it.length == 5 })
                        put("unit", state.unit)
                        state.wateringFrequencyDays.toIntOrNull()?.let { put("watering_frequency_days", it) }
                        state.waterSource.takeIf { it.isNotBlank() }?.let { put("water_source", it) }
                    },
                )
            }
            when (result) {
                is NetworkResult.Success -> _uiState.value =
                    _uiState.value.copy(isSaving = false, savedGardenId = result.data.id)
                is NetworkResult.Error -> _uiState.value =
                    _uiState.value.copy(isSaving = false, error = result.message)
                else -> Unit
            }
        }
    }

    private fun update(block: GardenFormUiState.() -> GardenFormUiState) {
        _uiState.value = _uiState.value.block()
    }
}
