package com.gardenapp.feature.bed.list

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Bed
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.bed.BedRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BedListUiState(
    val beds: List<Bed> = emptyList(),
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val deletingId: Int? = null,
    val gardenId: Int? = null,
)

@HiltViewModel
class BedListViewModel @Inject constructor(
    private val repository: BedRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int? = savedStateHandle.get<String>("gardenId")?.toIntOrNull()

    private val _uiState = MutableStateFlow(BedListUiState(gardenId = gardenId))
    val uiState: StateFlow<BedListUiState> = _uiState.asStateFlow()

    init {
        Log.d(TAG, "init gardenId=$gardenId")
        if (gardenId != null) {
            repository.bedsForGarden(gardenId)
                .onEach { beds ->
                    Log.d(TAG, "bedsForGarden emit count=${beds.size}")
                    _uiState.value = _uiState.value.copy(beds = beds)
                }
                .launchIn(viewModelScope)
            refresh()
        } else {
            Log.e(TAG, "init gardenId is null — beds will not load")
            _uiState.value = _uiState.value.copy(error = "Garden not found")
        }
    }

    fun refresh() {
        val id = gardenId ?: return
        viewModelScope.launch {
            Log.d(TAG, "refresh gardenId=$id")
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            val result = repository.refreshBeds(id)
            if (result is NetworkResult.Error) {
                Log.e(TAG, "refresh error: ${result.message}")
                _uiState.value = _uiState.value.copy(error = "Could not refresh beds")
            } else if (result is NetworkResult.Success) {
                Log.d(TAG, "refresh ok count=${result.data.size}")
            }
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun deleteBed(id: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletingId = id)
            repository.deleteBed(id)
            _uiState.value = _uiState.value.copy(deletingId = null)
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }

    companion object {
        private const val TAG = "BedListVM"
    }
}
