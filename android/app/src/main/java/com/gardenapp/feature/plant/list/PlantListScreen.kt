package com.gardenapp.feature.plant.list

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.ui.components.SkeletonList
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.SyncChange
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

    // Sync dialog
    if (uiState.syncOpen) {
        SyncDialog(
            changes = uiState.syncChanges,
            selected = uiState.syncSelected,
            loading = uiState.syncLoading,
            applying = uiState.syncApplying,
            onToggle = viewModel::toggleSyncItem,
            onToggleAll = viewModel::toggleAllSync,
            onApply = viewModel::applySync,
            onDismiss = viewModel::dismissSync,
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Plants", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = viewModel::openSync) {
                        Icon(Icons.Default.Sync, "Sync with beds")
                    }
                },
            )
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
                    SkeletonList()
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
        headlineContent = {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(plant.name, fontWeight = FontWeight.Medium)
                plant.successionLabel?.let { label ->
                    Badge(containerColor = MaterialTheme.colorScheme.secondaryContainer) {
                        Text(label, color = MaterialTheme.colorScheme.onSecondaryContainer)
                    }
                }
            }
        },
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

@Composable
private fun SyncDialog(
    changes: List<SyncChange>,
    selected: Set<Int>,
    loading: Boolean,
    applying: Boolean,
    onToggle: (Int) -> Unit,
    onToggleAll: () -> Unit,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Sync with beds") },
        text = {
            when {
                loading -> Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                changes.isEmpty() -> Text("Everything is in sync — no differences found.")
                else -> Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("${changes.size} difference${if (changes.size != 1) "s" else ""} found",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onClick = onToggleAll) {
                            Text(if (selected.size == changes.size) "Deselect all" else "Select all",
                                style = MaterialTheme.typography.labelSmall)
                        }
                    }
                    changes.forEachIndexed { i, change ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(checked = selected.contains(i), onCheckedChange = { onToggle(i) })
                            Column(modifier = Modifier.weight(1f)) {
                                Text(change.plantName, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                                val fieldLabel = if (change.field == "last_watered") "💧 Last watered" else "🌿 Last fertilized"
                                val dirLabel = if (change.direction == "bed_to_plant") "Bed → Plant" else "Plant → Beds"
                                Text("$fieldLabel · $dirLabel", style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(
                                    "${change.plantValue ?: "—"} → ${change.proposedValue ?: "—"}",
                                    style = MaterialTheme.typography.labelSmall,
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            if (changes.isNotEmpty()) {
                Button(
                    onClick = onApply,
                    enabled = selected.isNotEmpty() && !applying,
                ) {
                    if (applying) CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    else Text("Apply ${selected.size}")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Close") }
        },
    )
}
