package com.gardenapp.feature.bed.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.WaterDrop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.HealthScore
import com.gardenapp.core.model.PlantObservation
import com.gardenapp.core.util.DateUtil

private val OBS_TYPES = listOf("healthy", "new_growth", "flowering", "harvest_ready",
    "yellowing", "wilting", "pest_damage", "disease")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CareTrackingSheet(
    plant: BedPlantDetail,
    lastWatered: String,
    lastFertilized: String,
    healthNotes: String,
    isSaving: Boolean,
    observations: List<PlantObservation>,
    healthScore: HealthScore?,
    obsLoading: Boolean,
    showObsForm: Boolean,
    obsType: String,
    obsSeverity: Int,
    obsNotes: String,
    onWateredChange: (String) -> Unit,
    onFertilizedChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
    onShowObsForm: () -> Unit,
    onDismissObsForm: () -> Unit,
    onObsTypeChange: (String) -> Unit,
    onObsSeverityChange: (Int) -> Unit,
    onObsNotesChange: (String) -> Unit,
    onSubmitObs: () -> Unit,
    onDeleteObs: (Int) -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text(plant.plantName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    plant.scientificName?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                plant.stage?.let { Badge { Text(it) } }
            }

            // Quick stats row
            val stats = listOfNotNull(
                plant.sunlight?.let { "☀️ $it" },
                plant.water?.let { "💧 $it" },
                plant.spacingIn?.let { "📐 ${it.toInt()}in" },
                plant.daysToHarvest?.let { "🥕 ${it}d" },
            )
            if (stats.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    stats.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
            }

            // Health score
            if (healthScore != null) {
                val scoreColor = when (healthScore.label) {
                    "good" -> MaterialTheme.colorScheme.primary
                    "fair" -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.error
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Health:", style = MaterialTheme.typography.bodySmall)
                    Badge(containerColor = scoreColor) {
                        Text("${healthScore.healthScore} · ${healthScore.label}")
                    }
                }
            }

            HorizontalDivider()
            Text("Care Log", style = MaterialTheme.typography.titleSmall)

            // Last watered
            OutlinedTextField(
                value = lastWatered,
                onValueChange = onWateredChange,
                label = { Text("Last Watered") },
                placeholder = { Text("YYYY-MM-DD") },
                trailingIcon = { Icon(Icons.Default.WaterDrop, null, tint = MaterialTheme.colorScheme.primary) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
                supportingText = {
                    plant.lastWatered?.let {
                        Text("Previously: ${DateUtil.displayDate(it)}")
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            // Last fertilized
            OutlinedTextField(
                value = lastFertilized,
                onValueChange = onFertilizedChange,
                label = { Text("Last Fertilized") },
                placeholder = { Text("YYYY-MM-DD") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
                supportingText = {
                    plant.lastFertilized?.let {
                        Text("Previously: ${DateUtil.displayDate(it)}")
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            // Health notes
            OutlinedTextField(
                value = healthNotes,
                onValueChange = onNotesChange,
                label = { Text("Health Notes") },
                placeholder = { Text("e.g. Yellowing lower leaves, aphids on stem…") },
                maxLines = 3,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = onSave,
                enabled = !isSaving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isSaving) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                else Text("Save Care")
            }

            HorizontalDivider()

            // Observations section
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Observations", style = MaterialTheme.typography.titleSmall)
                IconButton(onClick = onShowObsForm) {
                    Icon(Icons.Default.Add, "Add observation")
                }
            }

            if (showObsForm) {
                ObservationForm(
                    obsType = obsType,
                    severity = obsSeverity,
                    notes = obsNotes,
                    onTypeChange = onObsTypeChange,
                    onSeverityChange = onObsSeverityChange,
                    onNotesChange = onObsNotesChange,
                    onSubmit = onSubmitObs,
                    onCancel = onDismissObsForm,
                )
            }

            if (obsLoading) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp).align(Alignment.CenterHorizontally), strokeWidth = 2.dp)
            } else if (observations.isEmpty() && !showObsForm) {
                Text(
                    "No observations yet. Tap + to add one.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                observations.forEach { obs ->
                    ObservationRow(obs = obs, onDelete = { onDeleteObs(obs.id) })
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ObservationForm(
    obsType: String,
    severity: Int,
    notes: String,
    onTypeChange: (String) -> Unit,
    onSeverityChange: (Int) -> Unit,
    onNotesChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("New Observation", style = MaterialTheme.typography.titleSmall)

            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                OutlinedTextField(
                    value = obsType,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Type") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    OBS_TYPES.forEach { t ->
                        DropdownMenuItem(
                            text = { Text(t.replace('_', ' ').replaceFirstChar(Char::uppercase)) },
                            onClick = { onTypeChange(t); expanded = false },
                        )
                    }
                }
            }

            Text("Severity: $severity", style = MaterialTheme.typography.bodySmall)
            Slider(
                value = severity.toFloat(),
                onValueChange = { onSeverityChange(it.toInt()) },
                valueRange = 1f..5f,
                steps = 3,
                modifier = Modifier.fillMaxWidth(),
            )

            OutlinedTextField(
                value = notes,
                onValueChange = onNotesChange,
                label = { Text("Notes (optional)") },
                maxLines = 2,
                modifier = Modifier.fillMaxWidth(),
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("Cancel") }
                Button(onClick = onSubmit, modifier = Modifier.weight(1f)) { Text("Add") }
            }
        }
    }
}

@Composable
private fun ObservationRow(obs: PlantObservation, onDelete: () -> Unit) {
    val isNegative = obs.observationType in setOf("yellowing", "wilting", "pest_damage", "disease")
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    obs.observationType.replace('_', ' ').replaceFirstChar(Char::uppercase),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                )
                Badge(containerColor = if (isNegative) MaterialTheme.colorScheme.errorContainer
                                        else MaterialTheme.colorScheme.primaryContainer) {
                    Text("${obs.severity}/5")
                }
            }
            Text(obs.observationDate, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            obs.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.Delete, "Delete", tint = MaterialTheme.colorScheme.error)
        }
    }
}
