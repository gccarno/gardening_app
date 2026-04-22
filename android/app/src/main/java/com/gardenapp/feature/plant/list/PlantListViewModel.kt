package com.gardenapp.feature.plant.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Plant
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import com.gardenapp.feature.plant.PlantRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class PlantTab { Planning, Growing, Reminders, Timeline }

data class PlantListUiState(
    val plants: List<Plant> = emptyList(),
    val tab: PlantTab = PlantTab.Planning,
    val isLoading: Boolean = false,
    val error: String? = null,
    val lastFrostDate: String? = null,
    val firstFrostDate: String? = null,
)

@HiltViewModel
class PlantListViewModel @Inject constructor(
    private val plantRepository: PlantRepository,
    private val gardenRepository: GardenRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(PlantListUiState(isLoading = true))
    val uiState: StateFlow<PlantListUiState> = _uiState

    init {
        viewModelScope.launch {
            plantRepository.plants.collectLatest { plants ->
                _uiState.value = _uiState.value.copy(plants = plants)
            }
        }
        viewModelScope.launch {
            gardenRepository.gardens.collectLatest { gardens ->
                val first = gardens.firstOrNull()
                _uiState.value = _uiState.value.copy(
                    lastFrostDate = first?.lastFrostDate,
                    firstFrostDate = first?.firstFrostDate,
                )
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = plantRepository.refresh()
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = result.message)
            }
            _uiState.value = _uiState.value.copy(isLoading = false)
        }
    }

    fun selectTab(tab: PlantTab) {
        _uiState.value = _uiState.value.copy(tab = tab)
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun deletePlant(id: Int) {
        viewModelScope.launch {
            val result = plantRepository.deletePlant(id)
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = result.message)
            }
        }
    }
}
