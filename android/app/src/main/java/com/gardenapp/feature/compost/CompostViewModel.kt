package com.gardenapp.feature.compost

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.CompostBin
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class CompostUiState(
    val bins: List<CompostBin> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val showCreateForm: Boolean = false,
    val formName: String = "",
    val formStartedDate: String = LocalDate.now().toString(),
    val isCreating: Boolean = false,
    val expandedMatBinId: Int? = null,
    val matFormMaterial: String = "",
    val matFormQuantity: String = "",
    val isAddingMat: Boolean = false,
)

@HiltViewModel
class CompostViewModel @Inject constructor(
    private val repository: CompostRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val gardenId: Int = checkNotNull(savedStateHandle["gardenId"])

    private val _uiState = MutableStateFlow(CompostUiState(isLoading = true))
    val uiState: StateFlow<CompostUiState> = _uiState

    init { load() }

    private fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            when (val result = repository.getBins(gardenId)) {
                is NetworkResult.Success -> _uiState.value = _uiState.value.copy(
                    bins = result.data,
                    isLoading = false,
                )
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(
                    isLoading = false, error = result.message,
                )
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun showCreate() { _uiState.value = _uiState.value.copy(showCreateForm = true) }
    fun hideCreate() {
        _uiState.value = _uiState.value.copy(
            showCreateForm = false,
            formName = "",
            formStartedDate = LocalDate.now().toString(),
        )
    }

    fun updateFormName(v: String) { _uiState.value = _uiState.value.copy(formName = v) }
    fun updateFormStartedDate(v: String) { _uiState.value = _uiState.value.copy(formStartedDate = v) }

    fun createBin() {
        val state = _uiState.value
        if (state.formName.isBlank()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isCreating = true)
            val result = repository.createBin(
                gardenId = gardenId,
                name = state.formName,
                startedDate = state.formStartedDate.ifBlank { null },
            )
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(isCreating = false, error = result.message)
            } else {
                hideCreate()
                _uiState.value = _uiState.value.copy(isCreating = false)
                load()
            }
        }
    }

    fun advanceStage(binId: Int) {
        viewModelScope.launch {
            when (val result = repository.advanceStage(binId)) {
                is NetworkResult.Success -> {
                    val updated = result.data
                    _uiState.value = _uiState.value.copy(
                        bins = _uiState.value.bins.map { if (it.id == updated.id) updated else it },
                    )
                }
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun deleteBin(binId: Int) {
        viewModelScope.launch {
            when (val result = repository.deleteBin(binId)) {
                is NetworkResult.Error -> _uiState.value = _uiState.value.copy(error = result.message)
                else -> load()
            }
        }
    }

    fun openMatForm(binId: Int) {
        _uiState.value = _uiState.value.copy(
            expandedMatBinId = binId,
            matFormMaterial = "",
            matFormQuantity = "",
        )
    }

    fun closeMatForm() { _uiState.value = _uiState.value.copy(expandedMatBinId = null) }

    fun updateMatMaterial(v: String) { _uiState.value = _uiState.value.copy(matFormMaterial = v) }
    fun updateMatQuantity(v: String) { _uiState.value = _uiState.value.copy(matFormQuantity = v) }

    fun addMaterial(binId: Int) {
        val state = _uiState.value
        if (state.matFormMaterial.isBlank()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isAddingMat = true)
            val qty = state.matFormQuantity.toDoubleOrNull()
            val result = repository.addMaterial(
                binId = binId,
                material = state.matFormMaterial,
                quantityLbs = qty,
            )
            if (result is NetworkResult.Error) {
                _uiState.value = _uiState.value.copy(isAddingMat = false, error = result.message)
            } else if (result is NetworkResult.Success) {
                val updated = result.data
                _uiState.value = _uiState.value.copy(
                    bins = _uiState.value.bins.map { if (it.id == updated.id) updated else it },
                    isAddingMat = false,
                    expandedMatBinId = null,
                )
            }
        }
    }

    fun dismissError() { _uiState.value = _uiState.value.copy(error = null) }
}
