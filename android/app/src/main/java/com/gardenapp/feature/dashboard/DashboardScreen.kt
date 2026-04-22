package com.gardenapp.feature.dashboard

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.feature.dashboard.components.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToSettings: () -> Unit,
    onNavigateToGarden: (Int) -> Unit,
    viewModel: DashboardViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Garden Planner", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, "Refresh")
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, "Settings")
                    }
                },
            )
        },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading && uiState.dashboard == null -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
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

                        Spacer(Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
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
