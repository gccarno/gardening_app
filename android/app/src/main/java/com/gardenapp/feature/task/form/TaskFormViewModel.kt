package com.gardenapp.feature.task.form

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.TaskType
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.bed.BedRepository
import com.gardenapp.feature.garden.GardenRepository
import com.gardenapp.feature.plant.PlantRepository
import com.gardenapp.feature.task.TaskRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TaskFormUiState(
    val title: String = "",
    val description: String = "",
    val taskType: String? = null,
    val dueDate: String = "",
    val selectedGardenId: Int? = null,
    val selectedBedId: Int? = null,
    val selectedPlantId: Int? = null,
    val gardens: List<Garden> = emptyList(),
    val beds: List<Bed> = emptyList(),
    val plants: List<Plant> = emptyList(),
    val isSaving: Boolean = false,
    val error: String? = null,
    val isEditMode: Boolean = false,
    val taskId: Int? = null,
)

@HiltViewModel
class TaskFormViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val taskRepository: TaskRepository,
    private val gardenRepository: GardenRepository,
    private val bedRepository: BedRepository,
    private val plantRepository: PlantRepository,
) : ViewModel() {

    private val taskId: Int? = savedStateHandle.get<Int>("taskId")?.takeIf { it != -1 }

    private val _uiState = MutableStateFlow(TaskFormUiState(
        isEditMode = taskId != null,
        taskId = taskId,
    ))
    val uiState: StateFlow<TaskFormUiState> = _uiState

    init {
        viewModelScope.launch {
            val gardens = gardenRepository.gardens.first()
            val beds = bedRepository.beds.first()
            val plants = plantRepository.plants.first()
            _uiState.value = _uiState.value.copy(
                gardens = gardens,
                beds = beds,
                plants = plants,
                selectedGardenId = gardens.firstOrNull()?.id,
            )
        }
        if (taskId != null) loadTask()
    }

    private fun loadTask() {
        viewModelScope.launch {
            when (val result = taskRepository.refresh()) {
                is NetworkResult.Success -> {
                    val task = result.data.find { it.id == taskId } ?: return@launch
                    _uiState.value = _uiState.value.copy(
                        title = task.title,
                        description = task.description ?: "",
                        taskType = task.taskType,
                        dueDate = task.dueDate ?: "",
                        selectedGardenId = task.gardenId,
                        selectedBedId = task.bedId,
                        selectedPlantId = task.plantId,
                    )
                }
                else -> {}
            }
        }
    }

    fun onTitleChange(v: String) { _uiState.value = _uiState.value.copy(title = v) }
    fun onDescriptionChange(v: String) { _uiState.value = _uiState.value.copy(description = v) }
    fun onTaskTypeChange(v: String?) { _uiState.value = _uiState.value.copy(taskType = v) }
    fun onDueDateChange(v: String) { _uiState.value = _uiState.value.copy(dueDate = v) }
    fun onGardenSelect(id: Int?) {
        _uiState.value = _uiState.value.copy(selectedGardenId = id, selectedBedId = null, selectedPlantId = null)
    }
    fun onBedSelect(id: Int?) { _uiState.value = _uiState.value.copy(selectedBedId = id) }
    fun onPlantSelect(id: Int?) { _uiState.value = _uiState.value.copy(selectedPlantId = id) }
    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }

    fun save(onSaved: (Int) -> Unit) {
        val state = _uiState.value
        if (state.title.isBlank()) {
            _uiState.value = state.copy(error = "Title is required")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true)
            val result = if (state.isEditMode && taskId != null) {
                taskRepository.updateTask(
                    id = taskId,
                    title = state.title.trim(),
                    description = state.description.ifBlank { null },
                    taskType = state.taskType,
                    dueDate = state.dueDate.ifBlank { null },
                    gardenId = state.selectedGardenId,
                    bedId = state.selectedBedId,
                    plantId = state.selectedPlantId,
                )
            } else {
                taskRepository.createTask(
                    title = state.title.trim(),
                    description = state.description.ifBlank { null },
                    taskType = state.taskType,
                    dueDate = state.dueDate.ifBlank { null },
                    gardenId = state.selectedGardenId,
                    bedId = state.selectedBedId,
                    plantId = state.selectedPlantId,
                )
            }
            when (result) {
                is NetworkResult.Success -> onSaved(result.data.id)
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isSaving = false, error = result.message,
                )
                else -> _uiState.value = _uiState.value.copy(isSaving = false)
            }
        }
    }
}
