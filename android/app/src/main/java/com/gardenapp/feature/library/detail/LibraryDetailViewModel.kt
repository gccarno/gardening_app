package com.gardenapp.feature.library.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.LibraryEntry
import com.gardenapp.core.model.LibraryImage
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.garden.GardenRepository
import com.gardenapp.feature.plant.PlantRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LibraryDetailUiState(
    val entry: LibraryEntry? = null,
    val images: List<LibraryImage> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null,
    val message: String? = null,
    val showAddToGarden: Boolean = false,
    val gardens: List<Garden> = emptyList(),
    val isSavingPlant: Boolean = false,
)

@HiltViewModel
class LibraryDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val api: ApiService,
    private val gardenRepository: GardenRepository,
    private val plantRepository: PlantRepository,
) : ViewModel() {

    val entryId: Int = checkNotNull(savedStateHandle["entryId"])

    private val _uiState = MutableStateFlow(LibraryDetailUiState())
    val uiState: StateFlow<LibraryDetailUiState> = _uiState

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val entry = api.getLibraryEntry(entryId)
                val images = try { api.getLibraryImages(entryId) } catch (e: Exception) { emptyList() }
                _uiState.value = _uiState.value.copy(entry = entry, images = images, isLoading = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message ?: "Load failed", isLoading = false)
            }
        }
    }

    fun setPrimaryImage(imageId: Int) {
        viewModelScope.launch {
            try {
                api.setImagePrimary(imageId)
                val images = api.getLibraryImages(entryId)
                _uiState.value = _uiState.value.copy(images = images, message = "Primary image updated")
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message)
            }
        }
    }

    fun openAddToGarden() {
        viewModelScope.launch {
            val gardens = gardenRepository.gardens.first()
            _uiState.value = _uiState.value.copy(showAddToGarden = true, gardens = gardens)
        }
    }

    fun dismissAddToGarden() {
        _uiState.value = _uiState.value.copy(showAddToGarden = false)
    }

    fun addToGarden(
        gardenId: Int,
        plantName: String,
        plantedDate: String?,
        onAdded: (Int) -> Unit,
    ) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSavingPlant = true)
            val result = plantRepository.createPlant(
                name = plantName,
                gardenId = gardenId,
                libraryId = entryId,
                plantedDate = plantedDate?.ifBlank { null },
                notes = null,
            )
            when (result) {
                is NetworkResult.Success -> {
                    _uiState.value = _uiState.value.copy(isSavingPlant = false, showAddToGarden = false)
                    onAdded(result.data.id)
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isSavingPlant = false, error = result.message,
                )
                else -> _uiState.value = _uiState.value.copy(isSavingPlant = false)
            }
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
    fun dismissMessage() { _uiState.value = _uiState.value.copy(message = null) }
}
