package com.gardenapp.feature.bed.form

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

data class BedFormUiState(
    val name: String = "",
    val widthFt: String = "4",
    val heightFt: String = "8",
    val soilNotes: String = "",
    val soilPh: String = "",
    val clayPct: String = "",
    val compostPct: String = "",
    val sandPct: String = "",
    val isSaving: Boolean = false,
    val error: String? = null,
    val savedBedId: Int? = null,
    val isEditing: Boolean = false,
)

@HiltViewModel
class BedFormViewModel @Inject constructor(
    private val repository: BedRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val bedId: Int? = savedStateHandle.get<String>("bedId")?.toIntOrNull()
    val gardenId: Int? = savedStateHandle.get<String>("gardenId")?.toIntOrNull()

    private val _uiState = MutableStateFlow(BedFormUiState(isEditing = bedId != null))
    val uiState: StateFlow<BedFormUiState> = _uiState.asStateFlow()

    init {
        bedId?.let { loadBed(it) }
    }

    private fun loadBed(id: Int) {
        viewModelScope.launch {
            when (val r = repository.getBed(id)) {
                is NetworkResult.Success -> {
                    val b = r.data
                    _uiState.value = _uiState.value.copy(
                        name = b.name,
                        widthFt = b.widthFt.toString(),
                        heightFt = b.heightFt.toString(),
                        soilNotes = b.soilNotes ?: "",
                        soilPh = b.soilPh?.toString() ?: "",
                        clayPct = b.clayPct?.toInt()?.toString() ?: "",
                        compostPct = b.compostPct?.toInt()?.toString() ?: "",
                        sandPct = b.sandPct?.toInt()?.toString() ?: "",
                    )
                }
                is NetworkResult.Error -> update { copy(error = r.message) }
                else -> Unit
            }
        }
    }

    fun onNameChange(v: String) = update { copy(name = v) }
    fun onWidthChange(v: String) = update { copy(widthFt = v.filter { it.isDigit() || it == '.' }.take(5)) }
    fun onHeightChange(v: String) = update { copy(heightFt = v.filter { it.isDigit() || it == '.' }.take(5)) }
    fun onSoilNotesChange(v: String) = update { copy(soilNotes = v) }
    fun onSoilPhChange(v: String) = update { copy(soilPh = v.filter { it.isDigit() || it == '.' }.take(4)) }
    fun onClayChange(v: String) = update { copy(clayPct = v.filter(Char::isDigit).take(3)) }
    fun onCompostChange(v: String) = update { copy(compostPct = v.filter(Char::isDigit).take(3)) }
    fun onSandChange(v: String) = update { copy(sandPct = v.filter(Char::isDigit).take(3)) }
    fun dismissError() = update { copy(error = null) }

    fun save() {
        val s = _uiState.value
        if (s.name.isBlank()) { update { copy(error = "Name is required") }; return }
        val w = s.widthFt.toFloatOrNull() ?: run { update { copy(error = "Invalid width") }; return }
        val h = s.heightFt.toFloatOrNull() ?: run { update { copy(error = "Invalid height") }; return }

        viewModelScope.launch {
            update { copy(isSaving = true, error = null) }
            val result = if (bedId == null) {
                val gid = gardenId ?: run {
                    update { copy(isSaving = false, error = "No garden selected") }; return@launch
                }
                repository.createBed(gid, s.name.trim(), w, h)
            } else {
                val fields = buildMap<String, Any?> {
                    put("name", s.name.trim())
                    put("width_ft", w)
                    put("height_ft", h)
                    s.soilNotes.takeIf { it.isNotBlank() }?.let { put("soil_notes", it) }
                    s.soilPh.toFloatOrNull()?.let { put("soil_ph", it) }
                    s.clayPct.toFloatOrNull()?.let { put("clay_pct", it) }
                    s.compostPct.toFloatOrNull()?.let { put("compost_pct", it) }
                    s.sandPct.toFloatOrNull()?.let { put("sand_pct", it) }
                }
                repository.updateBed(bedId, fields).let { r ->
                    if (r is NetworkResult.Success) NetworkResult.Success(repository.getBed(bedId).let {
                        if (it is NetworkResult.Success) it.data else null
                    })
                    else r
                }
            }
            when (result) {
                is NetworkResult.Success -> update { copy(isSaving = false, savedBedId = (result.data as? Bed)?.id ?: bedId) }
                is NetworkResult.Error -> update { copy(isSaving = false, error = result.message) }
                else -> Unit
            }
        }
    }

    private fun update(block: BedFormUiState.() -> BedFormUiState) {
        _uiState.value = _uiState.value.block()
    }
}
