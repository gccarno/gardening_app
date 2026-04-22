package com.gardenapp.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DashboardUiState(
    val gardens: List<Garden> = emptyList(),
    val selectedGardenId: Int? = null,
    val dashboard: DashboardData? = null,
    val weather: WeatherData? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repository: DashboardRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        loadInitialData()
    }

    private fun loadInitialData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val defaultId = repository.getDefaultGardenId()
            val gardensResult = repository.getGardens()

            when (gardensResult) {
                is NetworkResult.Success -> {
                    val gardens = gardensResult.data
                    val gardenId = defaultId ?: gardens.firstOrNull()?.id
                    _uiState.value = _uiState.value.copy(
                        gardens = gardens,
                        selectedGardenId = gardenId,
                        isLoading = false,
                    )
                    gardenId?.let { loadDashboardAndWeather(it) }
                }
                is NetworkResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = gardensResult.message,
                    )
                }
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun selectGarden(gardenId: Int) {
        _uiState.value = _uiState.value.copy(selectedGardenId = gardenId)
        loadDashboardAndWeather(gardenId)
    }

    fun refresh() {
        val gardenId = _uiState.value.selectedGardenId
        _uiState.value = _uiState.value.copy(error = null)
        loadInitialData()
        gardenId?.let { loadDashboardAndWeather(it) }
    }

    private fun loadDashboardAndWeather(gardenId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            val dashResult = repository.getDashboard(gardenId)
            val weatherResult = repository.getWeather(gardenId)

            _uiState.value = _uiState.value.copy(
                dashboard = (dashResult as? NetworkResult.Success)?.data,
                weather = (weatherResult as? NetworkResult.Success)?.data,
                isLoading = false,
                error = (dashResult as? NetworkResult.Error)?.message,
            )
        }
    }
}
