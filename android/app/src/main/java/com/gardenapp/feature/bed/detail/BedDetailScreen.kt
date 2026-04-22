package com.gardenapp.feature.bed.detail

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.feature.bed.detail.components.CareTrackingSheet
import com.gardenapp.feature.bed.detail.components.PlantGrid
import com.gardenapp.feature.bed.detail.components.PlantPickerSheet

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BedDetailScreen(
    onBack: () -> Unit,
    onEdit: (Int) -> Unit,
    viewModel: BedDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }
    LaunchedEffect(uiState.message) {
        uiState.message?.let { snackbarHostState.showSnackbar(it); viewModel.dismissMessage() }
    }

    // Plant picker sheet
    if (uiState.showPickerForCell != null) {
        PlantPickerSheet(
            query = uiState.pickerQuery,
            results = uiState.pickerResults,
            isLoading = uiState.pickerLoading,
            onQueryChange = viewModel::onPickerQueryChange,
            onSelect = viewModel::onLibraryEntrySelected,
            onDismiss = viewModel::dismissPicker,
        )
    }

    // Care tracking sheet
    uiState.careSheetPlant?.let { bp ->
        CareTrackingSheet(
            plant = bp,
            lastWatered = uiState.careLastWatered,
            lastFertilized = uiState.careLastFertilized,
            healthNotes = uiState.careHealthNotes,
            isSaving = uiState.isSavingCare,
            onWateredChange = viewModel::onCareWateredChange,
            onFertilizedChange = viewModel::onCareFertilizedChange,
            onNotesChange = viewModel::onCareNotesChange,
            onSave = viewModel::saveCare,
            onDismiss = viewModel::dismissCareSheet,
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.bed?.name ?: "Bed", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
                actions = {
                    uiState.bed?.let { bed ->
                        IconButton(onClick = { onEdit(bed.id) }) { Icon(Icons.Default.Edit, "Edit") }
                    }
                    IconButton(onClick = { viewModel.loadGrid() }) {
                        Icon(Icons.Default.Info, "Refresh")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading && uiState.bed == null ->
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))

                uiState.bed != null -> {
                    val bed = uiState.bed!!
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        // Bed summary
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.padding(12.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                Text(
                                    "${bed.widthFt.toInt()}ft × ${bed.heightFt.toInt()}ft · ${uiState.placed.size} plants",
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                                bed.soilNotes?.let {
                                    Text(it, style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                bed.soilPh?.let {
                                    Text("Soil pH: $it", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }

                        // Instructions
                        Surface(
                            shape = MaterialTheme.shapes.small,
                            color = MaterialTheme.colorScheme.secondaryContainer,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                "Tap empty cell to place a plant  ·  Tap plant to log care  ·  Long press to remove",
                                modifier = Modifier.padding(10.dp),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }

                        // The grid
                        if (uiState.isPlacing) {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                        }

                        PlantGrid(
                            widthFt = bed.widthFt.toInt().coerceAtLeast(1),
                            heightFt = bed.heightFt.toInt().coerceAtLeast(1),
                            placed = uiState.placed,
                            onCellTap = viewModel::onCellTap,
                            onCellLongPress = viewModel::onCellLongPress,
                            modifier = Modifier.fillMaxWidth(),
                        )

                        // Legend
                        if (uiState.placed.isNotEmpty()) {
                            PlantLegend(placed = uiState.placed)
                        }

                        Spacer(Modifier.height(32.dp))
                    }
                }

                else -> Column(
                    modifier = Modifier.align(Alignment.Center).padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text("Could not load bed", style = MaterialTheme.typography.titleMedium)
                    Button(onClick = { viewModel.loadGrid() }) { Text("Retry") }
                }
            }
        }
    }
}

@Composable
private fun PlantLegend(placed: List<com.gardenapp.core.model.GridPlant>) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Plants in this bed", style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            // Distinct plants only
            placed.distinctBy { it.plantId }.forEach { gp ->
                val count = placed.count { it.plantId == gp.plantId }
                Text(
                    "• ${gp.plantName}${if (count > 1) " ×$count" else ""}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
