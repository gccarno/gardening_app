package com.gardenapp.feature.identify

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.network.ApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject

data class IdCandidate(
    val name: String?,
    val scientificName: String?,
    val confidence: Double?,
    val libraryId: Int?,
)

data class IdentifyResult(
    val candidates: List<IdCandidate>,
    val diagnosis: String?,
    val careAdvice: String?,
)

data class IdentifyUiState(
    val mode: String = "identify",
    val imageUri: Uri? = null,
    val isLoading: Boolean = false,
    val result: IdentifyResult? = null,
    val error: String? = null,
)

@HiltViewModel
class IdentifyViewModel @Inject constructor(
    private val api: ApiService,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(IdentifyUiState())
    val uiState: StateFlow<IdentifyUiState> = _uiState.asStateFlow()

    fun setMode(mode: String) {
        _uiState.value = _uiState.value.copy(mode = mode, result = null, error = null)
    }

    fun setImage(uri: Uri?) {
        _uiState.value = _uiState.value.copy(imageUri = uri, result = null, error = null)
    }

    fun analyze() {
        val s = _uiState.value
        val uri = s.imageUri ?: return
        if (s.isLoading) return
        viewModelScope.launch {
            _uiState.value = s.copy(isLoading = true, error = null, result = null)
            try {
                val bytes = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                } ?: throw IllegalStateException("Could not read image")
                val part = MultipartBody.Part.createFormData(
                    "image", "photo.jpg",
                    bytes.toRequestBody("image/jpeg".toMediaType()),
                )
                val modeBody = s.mode.toRequestBody("text/plain".toMediaType())
                val json = api.identify(part, modeBody).jsonObject
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    result = parseResult(json),
                )
            } catch (e: Exception) {
                android.util.Log.e("IdentifyVM", "identify failed", e)
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Identification failed. Check your connection (and that the server has an API key configured).",
                )
            }
        }
    }

    private fun parseResult(obj: JsonObject): IdentifyResult {
        val candidates = obj["candidates"]?.jsonArray?.mapNotNull { el ->
            val c = el.jsonObject
            IdCandidate(
                name = c["name"]?.jsonPrimitive?.contentOrNull,
                scientificName = c["scientific_name"]?.jsonPrimitive?.contentOrNull,
                confidence = c["confidence"]?.jsonPrimitive?.doubleOrNull,
                libraryId = (c["library_match"] as? JsonObject)
                    ?.get("library_id")?.jsonPrimitive?.intOrNull,
            )
        } ?: emptyList()
        return IdentifyResult(
            candidates = candidates,
            diagnosis = obj["diagnosis"]?.jsonPrimitive?.contentOrNull,
            careAdvice = obj["care_advice"]?.jsonPrimitive?.contentOrNull,
        )
    }
}
