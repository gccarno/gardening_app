package com.gardenapp.feature.garden.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GardenListUiState(
    val gardens: List<Garden> = emptyList(),
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val deletingId: Int? = null,
)

@HiltViewModel
class GardenListViewModel @Inject constructor(
    private val repository: GardenRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(GardenListUiState())
    val uiState: StateFlow<GardenListUiState> = _uiState.asStateFlow()

    init {
        // Observe Room cache — instant display
        repository.gardens
            .onEach { gardens -> _uiState.value = _uiState.value.copy(gardens = gardens) }
            .launchIn(viewModelScope)
        // Then refresh from network
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            when (val result = repository.refreshGardens()) {
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> Unit
            }
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun deleteGarden(id: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletingId = id)
            repository.deleteGarden(id)
            _uiState.value = _uiState.value.copy(deletingId = null)
        }
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
