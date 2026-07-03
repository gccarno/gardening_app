package com.gardenapp.feature.garden.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
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

    private val gardenId: Int? = savedStateHandle.get<String>("gardenId")?.toIntOrNull()

    private val _uiState = MutableStateFlow(GardenDetailUiState())
    val uiState: StateFlow<GardenDetailUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        val gardenId = gardenId ?: run {
            _uiState.value = _uiState.value.copy(error = "Garden not found", isLoading = false)
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val gardenDeferred = async { repository.getGarden(gardenId) }
            val weatherDeferred = async { repository.getWeather(gardenId) }
            val gardenResult = gardenDeferred.await()
            val weatherResult = weatherDeferred.await()
            _uiState.value = _uiState.value.copy(
                garden = (gardenResult as? NetworkResult.Success)?.data
                    ?: _uiState.value.garden,
                weather = (weatherResult as? NetworkResult.Success)?.data,
                error = (gardenResult as? NetworkResult.Error)?.message,
                isLoading = false,
            )
        }
    }

    fun bulkCare(action: String) {
        val gardenId = gardenId ?: return
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
