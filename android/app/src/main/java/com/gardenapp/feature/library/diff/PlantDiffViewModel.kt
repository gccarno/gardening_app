package com.gardenapp.feature.library.diff

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.LibraryEntry
import com.gardenapp.core.network.ApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlantDiffUiState(
    val entryA: LibraryEntry? = null,
    val entryB: LibraryEntry? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

@HiltViewModel
class PlantDiffViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val api: ApiService,
) : ViewModel() {

    private val aId: Int = checkNotNull(savedStateHandle["aId"])
    private val bId: Int = checkNotNull(savedStateHandle["bId"])

    private val _uiState = MutableStateFlow(PlantDiffUiState())
    val uiState: StateFlow<PlantDiffUiState> = _uiState

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val a = api.getLibraryEntry(aId)
                val b = api.getLibraryEntry(bId)
                _uiState.value = _uiState.value.copy(entryA = a, entryB = b, isLoading = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message ?: "Load failed", isLoading = false)
            }
        }
    }
}
