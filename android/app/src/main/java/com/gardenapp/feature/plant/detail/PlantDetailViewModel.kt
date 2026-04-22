package com.gardenapp.feature.plant.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.PlantDetail
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.plant.PlantRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlantDetailUiState(
    val plant: PlantDetail? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
    val isSavingStatus: Boolean = false,
    val message: String? = null,
)

@HiltViewModel
class PlantDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: PlantRepository,
) : ViewModel() {

    private val plantId: Int = checkNotNull(savedStateHandle["plantId"])

    private val _uiState = MutableStateFlow(PlantDetailUiState())
    val uiState: StateFlow<PlantDetailUiState> = _uiState

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = repository.getDetail(plantId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                    plant = result.data, isLoading = false,
                )
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    error = result.message, isLoading = false,
                )
                else -> _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

    fun setStatus(status: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingStatus = true)
            when (val result = repository.setStatus(plantId, status)) {
                is NetworkResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isSavingStatus = false,
                        message = "Status updated to $status",
                    )
                    load()
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isSavingStatus = false, error = result.message,
                )
                else -> _uiState.value = _uiState.value.copy(isSavingStatus = false)
            }
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
    fun dismissMessage() { _uiState.value = _uiState.value.copy(message = null) }
}
