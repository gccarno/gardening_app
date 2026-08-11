package com.gardenapp.feature.dashboard

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.ui.components.CacheStatusLine
import com.gardenapp.core.ui.components.SkeletonList
import com.gardenapp.feature.dashboard.components.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToSettings: () -> Unit,
    onNavigateToGarden: (Int) -> Unit,
    onNavigateToIdentify: () -> Unit = {},
    viewModel: DashboardViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val listState = rememberLazyListState()

    // Scroll to bottom when new chat messages arrive
    LaunchedEffect(uiState.chatMessages.size) {
        if (uiState.chatMessages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.chatMessages.size - 1)
        }
    }

    if (uiState.chatOpen) {
        ModalBottomSheet(
            onDismissRequest = viewModel::closeChat,
            sheetState = sheetState,
        ) {
            ChatSheet(
                messages = uiState.chatMessages,
                input = uiState.chatInput,
                loading = uiState.chatLoading,
                listState = listState,
                onInputChange = viewModel::setChatInput,
                onSend = { viewModel.sendChat() },
                onChipClick = { viewModel.sendChat(it) },
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Garden Planner", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onNavigateToIdentify) {
                        Icon(Icons.Default.PhotoCamera, "Identify plant")
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, "Refresh")
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, "Settings")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = viewModel::openChat) {
                Icon(Icons.Default.Chat, "Open garden assistant")
            }
        },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isRefreshing && uiState.dashboard == null -> {
                    SkeletonList(count = 4)
                }
                uiState.error != null && uiState.dashboard == null -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Text("Cannot reach server", style = MaterialTheme.typography.titleMedium)
                        Text(
                            uiState.error ?: "",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Button(onClick = { viewModel.refresh() }) { Text("Retry") }
                        OutlinedButton(onClick = onNavigateToSettings) { Text("Change Server URL") }
                    }
                }
                else -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        // Refreshing over content already on screen
                        if (uiState.isRefreshing) {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                        }

                        // Garden selector
                        if (uiState.gardens.size > 1) {
                            GardenSelector(
                                gardens = uiState.gardens.map { it.id to it.name },
                                selectedId = uiState.selectedGardenId,
                                onSelect = { viewModel.selectGarden(it) },
                            )
                        } else if (uiState.gardens.isNotEmpty()) {
                            Text(
                                uiState.gardens.first().name,
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold,
                            )
                        }

                        CacheStatusLine(
                            fetchedAt = uiState.dashboardFetchedAt,
                            isRefreshing = uiState.isRefreshing,
                            refreshFailed = uiState.refreshFailed,
                        )

                        // Metrics
                        uiState.dashboard?.metrics?.let { metrics ->
                            MetricsRow(metrics = metrics)
                        }

                        // Seasonal hint
                        uiState.dashboard?.let { dash ->
                            if (dash.season.isNotEmpty()) {
                                SeasonalHintCard(dashboard = dash)
                            }
                        }

                        // Weather
                        uiState.weather?.let { weather ->
                            Text("Weather", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            WeatherWidget(weather = weather)
                        }

                        // Tip of the day
                        uiState.tipOfDay?.let { tip ->
                            TipOfDayCard(tip = tip)
                        }

                        // Upcoming tasks
                        uiState.dashboard?.let { dash ->
                            UpcomingTasksCard(
                                tasks = dash.upcomingTasks,
                                onSeeAll = { /* navigate to tasks */ },
                            )
                        }

                        // Recent plants
                        uiState.dashboard?.let { dash ->
                            if (dash.recentPlants.isNotEmpty()) {
                                RecentPlantsCard(plants = dash.recentPlants)
                            }
                        }

                        Spacer(Modifier.height(72.dp)) // FAB clearance
                    }
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun GardenSelector(
    gardens: List<Pair<Int, String>>,
    selectedId: Int?,
    onSelect: (Int) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedName = gardens.find { it.first == selectedId }?.second ?: "Select Garden"

    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selectedName,
            onValueChange = {},
            readOnly = true,
            label = { Text("Garden") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            gardens.forEach { (id, name) ->
                DropdownMenuItem(
                    text = { Text(name) },
                    onClick = { onSelect(id); expanded = false },
                )
            }
        }
    }
}

@Composable
private fun TipOfDayCard(tip: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("💡 Tip of the Day", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(tip, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun RecentPlantsCard(plants: List<com.gardenapp.core.model.DashboardPlant>) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Recent Plants", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            plants.forEach { plant ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(plant.name, style = MaterialTheme.typography.bodyMedium)
                    plant.status?.let {
                        Badge { Text(it) }
                    }
                }
            }
        }
    }
}

private val CHAT_CHIPS = listOf(
    "What should I plant this month?",
    "Check companion planting for my beds",
    "What tasks are coming up?",
    "What is ready to harvest?",
)

@Composable
private fun ChatSheet(
    messages: List<ChatMessage>,
    input: String,
    loading: Boolean,
    listState: androidx.compose.foundation.lazy.LazyListState,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onChipClick: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 400.dp, max = 600.dp)
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            "🤖 Garden Assistant",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
        ) {
            items(messages) { msg ->
                ChatBubble(msg)
            }
            if (loading) {
                item {
                    Row {
                        Spacer(Modifier.width(8.dp))
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text("Thinking…", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }

        // Quick-start chips (only before first user message)
        if (messages.none { it.role == "user" }) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                CHAT_CHIPS.take(2).forEach { chip ->
                    SuggestionChip(
                        onClick = { onChipClick(chip) },
                        label = { Text(chip, style = MaterialTheme.typography.labelSmall) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                CHAT_CHIPS.drop(2).forEach { chip ->
                    SuggestionChip(
                        onClick = { onChipClick(chip) },
                        label = { Text(chip, style = MaterialTheme.typography.labelSmall) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = onInputChange,
                placeholder = { Text("Ask about planting, companions…") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { onSend() }),
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onSend, enabled = input.isNotBlank() && !loading) {
                Icon(Icons.Default.Send, "Send")
            }
        }
    }
}

@Composable
private fun ChatBubble(msg: ChatMessage) {
    val isUser = msg.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = if (isUser) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.secondaryContainer,
            modifier = Modifier.widthIn(max = 280.dp),
        ) {
            Text(
                msg.text,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            )
        }
    }
}
