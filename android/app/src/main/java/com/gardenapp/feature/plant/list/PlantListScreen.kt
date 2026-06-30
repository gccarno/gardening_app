package com.gardenapp.feature.plant.list

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.Plant
import com.gardenapp.feature.plant.list.components.GanttChart
import java.time.LocalDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlantListScreen(
    onNavigateToDetail: (Int) -> Unit,
    onNavigateToCreate: () -> Unit,
    viewModel: PlantListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Plants", fontWeight = FontWeight.Bold) })
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onNavigateToCreate) {
                Icon(Icons.Default.Add, "Add plant")
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            val tabs = PlantTab.entries
            TabRow(selectedTabIndex = tabs.indexOf(uiState.tab)) {
                tabs.forEach { tab ->
                    Tab(
                        selected = uiState.tab == tab,
                        onClick = { viewModel.selectTab(tab) },
                        text = { Text(tab.name) },
                    )
                }
            }

            when {
                uiState.isLoading && uiState.plants.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                else -> {
                    when (uiState.tab) {
                        PlantTab.Timeline -> GanttTab(
                            plants = uiState.plants,
                            lastFrostDate = uiState.lastFrostDate,
                            firstFrostDate = uiState.firstFrostDate,
                        )
                        else -> {
                            val filtered = uiState.plants.filter { matchesTab(it, uiState.tab) }
                            PlantTabList(
                                plants = filtered,
                                tab = uiState.tab,
                                onPlantClick = onNavigateToDetail,
                                onDeletePlant = viewModel::deletePlant,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PlantTabList(
    plants: List<Plant>,
    tab: PlantTab,
    onPlantClick: (Int) -> Unit,
    onDeletePlant: (Int) -> Unit,
) {
    if (plants.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(
                emptyMessage(tab),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(vertical = 8.dp),
    ) {
        items(plants, key = { it.id }) { plant ->
            PlantRow(plant = plant, onClick = { onPlantClick(plant.id) }, onDelete = { onDeletePlant(plant.id) })
            HorizontalDivider()
        }
    }
}

@Composable
private fun PlantRow(plant: Plant, onClick: () -> Unit, onDelete: () -> Unit) {
    var showConfirm by remember { mutableStateOf(false) }

    if (showConfirm) {
        AlertDialog(
            onDismissRequest = { showConfirm = false },
            title = { Text("Remove plant?") },
            text = { Text("Delete \"${plant.name}\"?") },
            confirmButton = { TextButton(onClick = { showConfirm = false; onDelete() }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { showConfirm = false }) { Text("Cancel") } },
        )
    }

    ListItem(
        headlineContent = { Text(plant.name, fontWeight = FontWeight.Medium) },
        supportingContent = {
            val parts = listOfNotNull(
                plant.type?.replaceFirstChar(Char::uppercase),
                plant.bedNames.firstOrNull()?.let { "in $it" },
                plant.plantedDate?.let { "Planted $it" },
            )
            if (parts.isNotEmpty()) Text(parts.joinToString(" · "))
        },
        trailingContent = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                plant.status?.let {
                    Badge(containerColor = statusContainerColor(it)) { Text(it) }
                }
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = { showConfirm = true }) {
                    Icon(Icons.Default.Delete, "Delete", tint = MaterialTheme.colorScheme.error)
                }
            }
        },
        modifier = Modifier.clickable(onClick = onClick),
    )
}

@Composable
private fun GanttTab(plants: List<Plant>, lastFrostDate: String?, firstFrostDate: String?) {
    Column(modifier = Modifier.fillMaxSize().padding(8.dp)) {
        // Legend
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(bottom = 8.dp)) {
            LegendDot(color = MaterialTheme.colorScheme.primary, label = "Today")
            if (lastFrostDate != null) LegendDot(color = androidx.compose.ui.graphics.Color(0xFF2196F3), label = "Last frost")
            if (firstFrostDate != null) LegendDot(color = androidx.compose.ui.graphics.Color(0xFFFF9800), label = "First frost")
        }
        if (plants.none { it.plantedDate != null }) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    "Add a planted date to plants to see them here",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            GanttChart(
                plants = plants.filter { it.plantedDate != null },
                lastFrostDate = lastFrostDate,
                firstFrostDate = firstFrostDate,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun LegendDot(color: androidx.compose.ui.graphics.Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Surface(modifier = Modifier.size(8.dp), shape = MaterialTheme.shapes.small, color = color) {}
        Text(label, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun statusContainerColor(status: String) = when (status.lowercase()) {
    "growing", "active" -> MaterialTheme.colorScheme.primaryContainer
    "harvested" -> MaterialTheme.colorScheme.secondaryContainer
    "planning", "seeded" -> MaterialTheme.colorScheme.tertiaryContainer
    else -> MaterialTheme.colorScheme.surfaceVariant
}

private fun matchesTab(plant: Plant, tab: PlantTab): Boolean = when (tab) {
    PlantTab.Planning -> plant.status == null || plant.status in setOf("planning", "seeded", "germinated", "seedling")
    PlantTab.Growing -> plant.status in setOf("growing", "active", "transplanted")
    PlantTab.Reminders -> {
        val harvest = plant.expectedHarvest ?: return false
        try {
            val days = java.time.temporal.ChronoUnit.DAYS.between(LocalDate.now(), LocalDate.parse(harvest))
            days in 0..30
        } catch (e: Exception) { false }
    }
    PlantTab.Timeline -> true
}

private fun emptyMessage(tab: PlantTab) = when (tab) {
    PlantTab.Planning -> "No plants in planning — tap + to add one"
    PlantTab.Growing -> "No plants currently growing"
    PlantTab.Reminders -> "No harvests due in the next 30 days"
    PlantTab.Timeline -> ""
}
