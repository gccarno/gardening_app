package com.gardenapp.feature.task.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.Task
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.task.TaskRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

enum class TaskViewMode { List, Calendar }

data class TaskListUiState(
    val tasks: List<Task> = emptyList(),
    val mode: TaskViewMode = TaskViewMode.List,
    val isLoading: Boolean = false,
    val error: String? = null,
    val showCompleted: Boolean = false,
    val selectedDay: String? = null,
    val currentMonthYear: Pair<Int, Int> = run {
        val now = LocalDate.now()
        now.monthValue to now.year
    },
)

@HiltViewModel
class TaskListViewModel @Inject constructor(
    private val repository: TaskRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(TaskListUiState(isLoading = true))
    val uiState: StateFlow<TaskListUiState> = _uiState

    init {
        viewModelScope.launch {
            repository.tasks.collectLatest { tasks ->
                _uiState.value = _uiState.value.copy(tasks = tasks)
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.refresh()
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = result.message)
            }
            _uiState.value = _uiState.value.copy(isLoading = false)
        }
    }

    fun toggleMode() {
        _uiState.value = _uiState.value.copy(
            mode = if (_uiState.value.mode == TaskViewMode.List) TaskViewMode.Calendar else TaskViewMode.List,
        )
    }

    fun toggleShowCompleted() {
        _uiState.value = _uiState.value.copy(showCompleted = !_uiState.value.showCompleted)
    }

    fun completeTask(id: Int) {
        viewModelScope.launch {
            val result = repository.completeTask(id)
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = result.message)
            }
        }
    }

    fun deleteTask(id: Int) {
        viewModelScope.launch {
            val result = repository.deleteTask(id)
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(error = result.message)
            }
        }
    }

    fun selectDay(dateStr: String?) {
        _uiState.value = _uiState.value.copy(selectedDay = dateStr)
    }

    fun prevMonth() {
        val (month, year) = _uiState.value.currentMonthYear
        val newMonth = if (month == 1) 12 else month - 1
        val newYear = if (month == 1) year - 1 else year
        _uiState.value = _uiState.value.copy(currentMonthYear = newMonth to newYear)
    }

    fun nextMonth() {
        val (month, year) = _uiState.value.currentMonthYear
        val newMonth = if (month == 12) 1 else month + 1
        val newYear = if (month == 12) year + 1 else year
        _uiState.value = _uiState.value.copy(currentMonthYear = newMonth to newYear)
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
}
