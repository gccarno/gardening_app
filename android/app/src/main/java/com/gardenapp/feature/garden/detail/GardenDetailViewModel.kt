package com.gardenapp.feature.garden.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GardenDetailUiState(
    val garden: Garden? = null,
    val weather: WeatherData? = null,
    val isLoading: Boolean = false,
    val isBulkCaring: Boolean = false,
    val error: String? = null,
    val bulkCareMessage: String? = null,
)

@HiltViewModel
class GardenDetailViewModel @Inject constructor(
    private val repository: GardenRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int = checkNotNull(savedStateHandle.get<String>("gardenId")?.toInt())

    private val _uiState = MutableStateFlow(GardenDetailUiState())
    val uiState: StateFlow<GardenDetailUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val r = repository.getGarden(gardenId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(garden = r.data)
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = r.message)
                else -> Unit
            }
            // Load weather in parallel (non-blocking on garden)
            when (val w = repository.getWeather(gardenId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(weather = w.data)
                else -> Unit // weather is optional; don't show error
            }
            _uiState.value = _uiState.value.copy(isLoading = false)
        }
    }

    fun bulkCare(action: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isBulkCaring = true)
            val label = when (action) {
                "water" -> "watered"
                "fertilize" -> "fertilized"
                "mulch" -> "mulched"
                else -> action
            }
            when (val r = repository.bulkCare(gardenId, action)) {
                is NetworkResult.Success ->
                    _uiState.value = _uiState.value.copy(bulkCareMessage = "All beds $label ✓")
                is NetworkResult.Error ->
                    _uiState.value = _uiState.value.copy(error = r.message)
                else -> Unit
            }
            _uiState.value = _uiState.value.copy(isBulkCaring = false)
        }
    }

    fun dismissError() = _uiState.value.let { _uiState.value = it.copy(error = null) }
    fun dismissBulkCareMessage() = _uiState.value.let { _uiState.value = it.copy(bulkCareMessage = null) }
}
