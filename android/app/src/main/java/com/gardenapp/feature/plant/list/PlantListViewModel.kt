package com.gardenapp.feature.plant.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.SyncChange
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
    // Sync
    val syncOpen: Boolean = false,
    val syncChanges: List<SyncChange> = emptyList(),
    val syncLoading: Boolean = false,
    val syncApplying: Boolean = false,
    val syncSelected: Set<Int> = emptySet(),
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

    // ── Sync ─────────────────────────────────────────────────────────────────

    fun openSync() {
        _uiState.value = _uiState.value.copy(syncOpen = true, syncLoading = true, syncChanges = emptyList(), syncSelected = emptySet())
        viewModelScope.launch {
            when (val r = plantRepository.getSyncPreview()) {
                is NetworkResult.Success -> {
                    val changes = r.data.changes
                    _uiState.value = _uiState.value.copy(
                        syncChanges = changes,
                        syncSelected = changes.indices.toSet(),
                        syncLoading = false,
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(syncLoading = false, error = r.message)
                else -> _uiState.value = _uiState.value.copy(syncLoading = false)
            }
        }
    }

    fun dismissSync() { _uiState.value = _uiState.value.copy(syncOpen = false) }

    fun toggleSyncItem(index: Int) {
        val current = _uiState.value.syncSelected.toMutableSet()
        if (current.contains(index)) current.remove(index) else current.add(index)
        _uiState.value = _uiState.value.copy(syncSelected = current)
    }

    fun toggleAllSync() {
        val allIndices = _uiState.value.syncChanges.indices.toSet()
        val current = _uiState.value.syncSelected
        _uiState.value = _uiState.value.copy(
            syncSelected = if (current == allIndices) emptySet() else allIndices,
        )
    }

    fun applySync() {
        val s = _uiState.value
        val toApply = s.syncSelected.sorted().map { s.syncChanges[it] }
        if (toApply.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(syncApplying = true)
            plantRepository.applySync(toApply)
            _uiState.value = _uiState.value.copy(syncApplying = false, syncOpen = false)
        }
    }
}
