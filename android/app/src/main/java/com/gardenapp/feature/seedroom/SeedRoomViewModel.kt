package com.gardenapp.feature.seedroom

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.SeedTray
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class SeedRoomUiState(
    val trays: Map<Int, SeedTray> = emptyMap(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val addSlot: Int? = null,
    val formPlantName: String = "",
    val formSowDate: String = LocalDate.now().toString(),
    val formNotes: String = "",
    val isSaving: Boolean = false,
)

@HiltViewModel
class SeedRoomViewModel @Inject constructor(
    private val repository: SeedRoomRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int = checkNotNull(savedStateHandle["gardenId"])

    private val _uiState = MutableStateFlow(SeedRoomUiState(isLoading = true))
    val uiState: StateFlow<SeedRoomUiState> = _uiState

    init { load() }

    private fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = repository.getTrays(gardenId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                    trays = result.data.associateBy { it.slotNumber },
                    isLoading = false,
                )
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isLoading = false, error = result.message,
                )
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun openAddSlot(slot: Int) {
        _uiState.value = _uiState.value.copy(
            addSlot = slot,
            formPlantName = "",
            formSowDate = LocalDate.now().toString(),
            formNotes = "",
        )
    }

    fun dismissAdd() { _uiState.value = _uiState.value.copy(addSlot = null) }

    fun updatePlantName(v: String) { _uiState.value = _uiState.value.copy(formPlantName = v) }
    fun updateSowDate(v: String) { _uiState.value = _uiState.value.copy(formSowDate = v) }
    fun updateNotes(v: String) { _uiState.value = _uiState.value.copy(formNotes = v) }

    fun saveSlot() {
        val state = _uiState.value
        val slot = state.addSlot ?: return
        if (state.formPlantName.isBlank()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true)
            val result = repository.addTray(
                gardenId = gardenId,
                slotNumber = slot,
                plantName = state.formPlantName,
                sowDate = state.formSowDate.ifBlank { null },
                notes = state.formNotes.ifBlank { null },
            )
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(isSaving = false, error = result.message)
            } else {
                dismissAdd()
                _uiState.value = _uiState.value.copy(isSaving = false)
                load()
            }
        }
    }

    fun advanceStage(trayId: Int) {
        viewModelScope.launch {
            when (val result = repository.advanceStage(trayId)) {
                is NetworkResult.Success -> {
                    val updated = result.data
                    _uiState.value = _uiState.value.copy(
                        trays = _uiState.value.trays.toMutableMap().also {
                            it[updated.slotNumber] = updated
                        },
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun removeTray(trayId: Int) {
        viewModelScope.launch {
            when (val result = repository.removeTray(trayId)) {
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> load()
            }
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
}
