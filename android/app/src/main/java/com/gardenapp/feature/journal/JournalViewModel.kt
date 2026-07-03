package com.gardenapp.feature.journal

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.JournalEntry
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class JournalUiState(
    val entries: List<JournalEntry> = emptyList(),
    val page: Int = 1,
    val totalPages: Int = 1,
    val isLoading: Boolean = false,
    val error: String? = null,
    val showForm: Boolean = false,
    val formTitle: String = "",
    val formBody: String = "",
    val formDate: String = LocalDate.now().toString(),
    val formTags: String = "",
    val isSaving: Boolean = false,
)

@HiltViewModel
class JournalViewModel @Inject constructor(
    private val repository: JournalRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int = checkNotNull(savedStateHandle["gardenId"])

    private val _uiState = MutableStateFlow(JournalUiState(isLoading = true))
    val uiState: StateFlow<JournalUiState> = _uiState

    init { loadPage(1) }

    private fun loadPage(page: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = repository.getJournal(gardenId, page)) {
                is NetworkResult.Success -> {
                    val data = result.data
                    _uiState.value = _uiState.value.copy(
                        entries = data.entries,
                        page = data.page,
                        totalPages = if (data.total == 0) 1 else (data.total + 19) / 20,
                        isLoading = false,
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = result.message,
                )
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun prevPage() { if (_uiState.value.page > 1) loadPage(_uiState.value.page - 1) }
    fun nextPage() { if (_uiState.value.page < _uiState.value.totalPages) loadPage(_uiState.value.page + 1) }

    fun showForm() { _uiState.value = _uiState.value.copy(showForm = true) }
    fun hideForm() {
        _uiState.value = _uiState.value.copy(
            showForm = false,
            formTitle = "",
            formBody = "",
            formTags = "",
            formDate = LocalDate.now().toString(),
        )
    }

    fun updateTitle(v: String) { _uiState.value = _uiState.value.copy(formTitle = v) }
    fun updateBody(v: String) { _uiState.value = _uiState.value.copy(formBody = v) }
    fun updateDate(v: String) { _uiState.value = _uiState.value.copy(formDate = v) }
    fun updateTags(v: String) { _uiState.value = _uiState.value.copy(formTags = v) }

    fun saveEntry() {
        val state = _uiState.value
        if (state.formTitle.isBlank()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSaving = true)
            val tags = state.formTags.split(",").map { it.trim() }.filter { it.isNotEmpty() }
            val result = repository.createEntry(
                gardenId = gardenId,
                title = state.formTitle,
                body = state.formBody.ifBlank { null },
                entryDate = state.formDate,
                tags = tags,
            )
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(isSaving = false, error = result.message)
            } else {
                hideForm()
                _uiState.value = _uiState.value.copy(isSaving = false)
                loadPage(1)
            }
        }
    }

    fun deleteEntry(id: Int) {
        viewModelScope.launch {
            when (val result = repository.deleteEntry(id)) {
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> loadPage(_uiState.value.page)
            }
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
}
