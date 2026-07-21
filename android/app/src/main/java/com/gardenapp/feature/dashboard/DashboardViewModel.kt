package com.gardenapp.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

data class ChatMessage(val id: String, val role: String, val text: String)

data class DashboardUiState(
    val gardens: List<Garden> = emptyList(),
    val selectedGardenId: Int? = null,
    val dashboard: DashboardData? = null,
    val weather: WeatherData? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
    // Tip of the day
    val tipOfDay: String? = null,
    // Chat
    val chatOpen: Boolean = false,
    val chatMessages: List<ChatMessage> = listOf(
        ChatMessage("init", "bot", "Hi! I'm your garden assistant. Ask me about planting, pests, companions, schedules — or say \"add [plant] to my garden\"!")
    ),
    val chatInput: String = "",
    val chatLoading: Boolean = false,
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repository: DashboardRepository,
    private val api: ApiService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    // Not in UI state — internal chat tracking.
    // Capped so a long-lived session can't grow memory unboundedly.
    private val conversationHistory = mutableListOf<Map<String, String>>()
    private var sessionId: String = java.util.UUID.randomUUID().toString()

    private fun trimConversationHistory() {
        while (conversationHistory.size > MAX_CHAT_HISTORY) conversationHistory.removeAt(0)
    }

    init {
        loadInitialData()
        loadTipOfDay()
    }

    private fun loadInitialData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val defaultId = repository.getDefaultGardenId()
            val gardensResult = repository.getGardens()

            when (gardensResult) {
                is NetworkResult.Success -> {
                    val gardens = gardensResult.data
                    val gardenId = defaultId ?: gardens.firstOrNull()?.id
                    _uiState.value = _uiState.value.copy(
                        gardens = gardens,
                        selectedGardenId = gardenId,
                        isLoading = false,
                    )
                    gardenId?.let { loadDashboardAndWeather(it) }
                }
                is NetworkResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = gardensResult.message,
                    )
                }
                NetworkResult.Loading -> Unit
            }
        }
    }

    fun selectGarden(gardenId: Int) {
        _uiState.value = _uiState.value.copy(selectedGardenId = gardenId)
        loadDashboardAndWeather(gardenId)
    }

    fun refresh() {
        val gardenId = _uiState.value.selectedGardenId
        _uiState.value = _uiState.value.copy(error = null)
        loadInitialData()
        gardenId?.let { loadDashboardAndWeather(it) }
    }

    private fun loadDashboardAndWeather(gardenId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            val dashResult = repository.getDashboard(gardenId)
            val weatherResult = repository.getWeather(gardenId)

            _uiState.value = _uiState.value.copy(
                dashboard = (dashResult as? NetworkResult.Success)?.data,
                weather = (weatherResult as? NetworkResult.Success)?.data,
                isLoading = false,
                error = (dashResult as? NetworkResult.Error)?.message,
            )
        }
    }

    // ── Tip of the day ───────────────────────────────────────────────────────

    private fun loadTipOfDay() {
        viewModelScope.launch {
            val tip = repository.getTipOfDay()
            _uiState.value = _uiState.value.copy(tipOfDay = tip)
        }
    }

    // ── Chat ─────────────────────────────────────────────────────────────────

    fun openChat() { _uiState.value = _uiState.value.copy(chatOpen = true) }
    fun closeChat() { _uiState.value = _uiState.value.copy(chatOpen = false) }
    fun setChatInput(v: String) { _uiState.value = _uiState.value.copy(chatInput = v) }

    fun sendChat(overrideText: String? = null) {
        val text = (overrideText ?: _uiState.value.chatInput).trim()
        if (text.isEmpty() || _uiState.value.chatLoading) return

        val userMsg = ChatMessage(java.util.UUID.randomUUID().toString(), "user", text)
        _uiState.value = _uiState.value.copy(
            chatMessages = _uiState.value.chatMessages + userMsg,
            chatInput = "",
            chatLoading = true,
        )
        conversationHistory.add(mapOf("role" to "user", "content" to text))

        viewModelScope.launch {
            try {
                val gardenId = _uiState.value.selectedGardenId
                val body = buildMap<String, Any?> {
                    put("message", text)
                    put("garden_id", gardenId)
                    put("session_id", sessionId)
                    put("conversation_history", conversationHistory.dropLast(1))
                }
                val result = api.sendChat(body)
                val obj = result as? JsonObject
                val reply = obj?.get("reply")?.jsonPrimitive?.contentOrNull ?: "No response."
                obj?.get("session_id")?.jsonPrimitive?.contentOrNull?.let { sessionId = it }
                obj?.get("conversation_history")?.jsonArray?.let { arr ->
                    conversationHistory.clear()
                    arr.forEach { el ->
                        val m = el.jsonObject
                        conversationHistory.add(
                            mapOf(
                                "role" to (m["role"]?.jsonPrimitive?.contentOrNull ?: ""),
                                "content" to (m["content"]?.jsonPrimitive?.contentOrNull ?: ""),
                            )
                        )
                    }
                }
                conversationHistory.add(mapOf("role" to "assistant", "content" to reply))
                trimConversationHistory()
                val botMsg = ChatMessage(java.util.UUID.randomUUID().toString(), "bot", reply)
                _uiState.value = _uiState.value.copy(
                    chatMessages = _uiState.value.chatMessages + botMsg,
                    chatLoading = false,
                )
            } catch (e: Exception) {
                conversationHistory.removeLastOrNull()
                val errMsg = ChatMessage(
                    java.util.UUID.randomUUID().toString(), "bot",
                    "Could not reach the assistant. Check your connection and try again.",
                )
                _uiState.value = _uiState.value.copy(
                    chatMessages = _uiState.value.chatMessages + errMsg,
                    chatLoading = false,
                )
            }
        }
    }

    companion object {
        private const val MAX_CHAT_HISTORY = 60  // messages (30 exchanges)
    }
}
