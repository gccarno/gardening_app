package com.gardenapp.feature.seedroom

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.SeedTray

private val SEED_STAGES = listOf("sowing", "germinating", "seedling", "hardening", "ready")

private fun stageColor(stage: String): Color = when (stage) {
    "sowing"      -> Color(0xFF8A6A40)
    "germinating" -> Color(0xFF5A9E54)
    "seedling"    -> Color(0xFF3A8C5A)
    "hardening"   -> Color(0xFF4A80B4)
    "ready"       -> Color(0xFFD4A84B)
    else          -> Color(0xFF7A907A)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SeedRoomScreen(
    onBack: () -> Unit,
    viewModel: SeedRoomViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    if (uiState.addSlot != null) {
        ModalBottomSheet(onDismissRequest = viewModel::dismissAdd) {
            AddSeedForm(
                slot = uiState.addSlot!!,
                plantName = uiState.formPlantName,
                sowDate = uiState.formSowDate,
                notes = uiState.formNotes,
                isSaving = uiState.isSaving,
                onPlantNameChange = viewModel::updatePlantName,
                onSowDateChange = viewModel::updateSowDate,
                onNotesChange = viewModel::updateNotes,
                onSave = viewModel::saveSlot,
                onCancel = viewModel::dismissAdd,
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Seed Room", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        if (uiState.isLoading && uiState.trays.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
            ) {
                // Stage legend
                Row(
                    modifier = Modifier
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    SEED_STAGES.forEach { stage ->
                        StagePill(stage = stage, color = stageColor(stage))
                    }
                }

                HorizontalDivider()

                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),
                    contentPadding = PaddingValues(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items((1..24).toList()) { slot ->
                        val tray = uiState.trays[slot]
                        if (tray == null) {
                            EmptySlotCard(
                                slot = slot,
                                onClick = { viewModel.openAddSlot(slot) },
                            )
                        } else {
                            FilledSlotCard(
                                tray = tray,
                                onAdvance = { viewModel.advanceStage(tray.id) },
                                onRemove = { viewModel.removeTray(tray.id) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StagePill(stage: String, color: Color) {
    Surface(
        color = color,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            stage,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall,
            color = Color.White,
        )
    }
}

@Composable
private fun EmptySlotCard(slot: Int, onClick: () -> Unit) {
    OutlinedCard(
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(0.75f)
            .clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                "$slot",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "+ Add",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun FilledSlotCard(
    tray: SeedTray,
    onAdvance: () -> Unit,
    onRemove: () -> Unit,
) {
    var showConfirm by remember { mutableStateOf(false) }

    if (showConfirm) {
        AlertDialog(
            onDismissRequest = { showConfirm = false },
            title = { Text("Remove seed?") },
            text = { Text("\"${tray.plantName}\" will be removed from slot ${tray.slotNumber}.") },
            confirmButton = {
                TextButton(onClick = { showConfirm = false; onRemove() }) {
                    Text("Remove", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showConfirm = false }) { Text("Cancel") }
            },
        )
    }

    val color = stageColor(tray.stage)
    Card(
        border = BorderStroke(2.dp, color),
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(0.75f),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                StagePill(stage = tray.stage, color = color)
                TextButton(
                    onClick = { showConfirm = true },
                    contentPadding = PaddingValues(0.dp),
                    modifier = Modifier.size(20.dp),
                ) {
                    Text("×", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelLarge)
                }
            }
            Spacer(Modifier.height(4.dp))
            Text(
                tray.plantName,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
            )
            tray.sowDate?.let {
                Text(
                    "Sown: $it",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.weight(1f))
            if (tray.stage != "ready") {
                TextButton(
                    onClick = onAdvance,
                    contentPadding = PaddingValues(horizontal = 4.dp, vertical = 2.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Advance →", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
private fun AddSeedForm(
    slot: Int,
    plantName: String,
    sowDate: String,
    notes: String,
    isSaving: Boolean,
    onPlantNameChange: (String) -> Unit,
    onSowDateChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "Add seed to slot $slot",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        OutlinedTextField(
            value = plantName,
            onValueChange = onPlantNameChange,
            label = { Text("Plant name *") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = sowDate,
            onValueChange = onSowDateChange,
            label = { Text("Sow date (YYYY-MM-DD)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = notes,
            onValueChange = onNotesChange,
            label = { Text("Notes (optional)") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
            maxLines = 4,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("Cancel") }
            Button(
                onClick = onSave,
                enabled = plantName.isNotBlank() && !isSaving,
                modifier = Modifier.weight(1f),
            ) {
                Text(if (isSaving) "Saving…" else "Add Seed")
            }
        }
    }
}
