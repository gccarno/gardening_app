package com.gardenapp.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.WeatherData
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
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
    val dashboardFetchedAt: Long? = null,
    val weather: WeatherData? = null,
    val isRefreshing: Boolean = false,
    val refreshFailed: Boolean = false,
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
        repository.gardens
            .onEach { gardens -> _uiState.update { it.copy(gardens = gardens) } }
            .launchIn(viewModelScope)
        start()
    }

    /** Paints from disk first — no network in the critical path — then refreshes. */
    private fun start() {
        viewModelScope.launch {
            val gardenId = repository.cachedDefaultGardenId()
                ?: repository.gardens.first().firstOrNull()?.id
            val cached = gardenId?.let { repository.cachedDashboard(it) }
            _uiState.update {
                it.copy(
                    selectedGardenId = gardenId ?: it.selectedGardenId,
                    dashboard = cached?.value ?: it.dashboard,
                    dashboardFetchedAt = cached?.fetchedAt ?: it.dashboardFetchedAt,
                    tipOfDay = repository.cachedTipForToday() ?: it.tipOfDay,
                )
            }
            refresh(force = false)
        }
    }

    /**
     * The single network entry point. Everything that can go out at once does; on a
     * warm start the garden id is already known, so nothing waits on anything else.
     */
    fun refresh(force: Boolean = true) {
        viewModelScope.launch {
            _uiState.update { it.copy(isRefreshing = true, error = null, refreshFailed = false) }
            val known = _uiState.value.selectedGardenId

            // Neither of these blocks the dashboard: gardens reach the UI through the
            // Room flow, and the id is only needed when we don't already have one.
            // Both swallow their own failures, so nothing here can escape.
            val gardensJob = async { repository.refreshGardens() }
            val defaultIdJob = async { repository.refreshDefaultGardenId() }

            // The tip lands on its own so a slow tip can't hold up the dashboard.
            launch {
                repository.refreshTipOfDay()?.let { tip ->
                    _uiState.update { it.copy(tipOfDay = tip) }
                }
            }

            // Only a first-ever launch gets here without an id, and only that pays for
            // the extra round trip.
            val gardenId = known
                ?: defaultIdJob.await()
                ?: (gardensJob.await() as? NetworkResult.Success)?.data?.firstOrNull()?.id

            if (gardenId == null) {
                _uiState.update { it.copy(isRefreshing = false) }
                return@launch
            }
            _uiState.update { it.copy(selectedGardenId = gardenId) }
            loadGarden(gardenId, force)
        }
    }

    fun selectGarden(gardenId: Int) {
        viewModelScope.launch {
            val cached = repository.cachedDashboard(gardenId)
            _uiState.update {
                it.copy(
                    selectedGardenId = gardenId,
                    dashboard = cached?.value,
                    dashboardFetchedAt = cached?.fetchedAt,
                    weather = null,
                    isRefreshing = true,
                    error = null,
                    refreshFailed = false,
                )
            }
            repository.setDefaultGardenIdLocally(gardenId)
            loadGarden(gardenId, force = false)
        }
    }

    /** Dashboard + weather for one garden, in parallel. */
    private suspend fun loadGarden(gardenId: Int, force: Boolean) = coroutineScope {
        val dashJob = async { repository.refreshDashboard(gardenId, force) }
        val weatherJob = async { repository.getWeather(gardenId) }
        val dashResult = dashJob.await()
        val weatherResult = weatherJob.await()
        val dashboard = (dashResult as? NetworkResult.Success)?.data

        _uiState.update { state ->
            state.copy(
                // Keep what is already on screen when a refresh fails — a flaky
                // network must never blank a populated dashboard.
                dashboard = dashboard?.value ?: state.dashboard,
                dashboardFetchedAt = dashboard?.fetchedAt ?: state.dashboardFetchedAt,
                weather = (weatherResult as? NetworkResult.Success)?.data ?: state.weather,
                isRefreshing = false,
                refreshFailed = dashResult is NetworkResult.Error,
                // Only worth a full error screen when there is nothing to show;
                // otherwise the staleness line carries the message.
                error = (dashResult as? NetworkResult.Error)?.message
                    ?.takeIf { state.dashboard == null },
            )
        }
    }

    // ── Chat ─────────────────────────────────────────────────────────────────

    fun openChat() { _uiState.update { it.copy(chatOpen = true) } }
    fun closeChat() { _uiState.update { it.copy(chatOpen = false) } }
    fun setChatInput(v: String) { _uiState.update { it.copy(chatInput = v) } }

    fun sendChat(overrideText: String? = null) {
        val text = (overrideText ?: _uiState.value.chatInput).trim()
        if (text.isEmpty() || _uiState.value.chatLoading) return

        val userMsg = ChatMessage(java.util.UUID.randomUUID().toString(), "user", text)
        _uiState.update {
            it.copy(
                chatMessages = it.chatMessages + userMsg,
                chatInput = "",
                chatLoading = true,
            )
        }
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
                _uiState.update {
                    it.copy(chatMessages = it.chatMessages + botMsg, chatLoading = false)
                }
            } catch (e: Exception) {
                conversationHistory.removeLastOrNull()
                val errMsg = ChatMessage(
                    java.util.UUID.randomUUID().toString(), "bot",
                    "Could not reach the assistant. Check your connection and try again.",
                )
                _uiState.update {
                    it.copy(chatMessages = it.chatMessages + errMsg, chatLoading = false)
                }
            }
        }
    }

    companion object {
        private const val MAX_CHAT_HISTORY = 60  // messages (30 exchanges)
    }
}
