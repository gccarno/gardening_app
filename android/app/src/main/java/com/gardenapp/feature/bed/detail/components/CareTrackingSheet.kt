package com.gardenapp.feature.bed.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.WaterDrop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.HealthScore
import com.gardenapp.core.model.PlantObservation
import com.gardenapp.core.util.DateUtil
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private val OBS_TYPES = listOf("healthy", "new_growth", "flowering", "harvest_ready",
    "yellowing", "wilting", "pest_damage", "disease")

/** Growth stages accepted by POST /api/bedplants/{id}/care — matches the web planner. */
private val STAGES = listOf("seedling", "growing", "harvesting", "done")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CareTrackingSheet(
    plant: BedPlantDetail,
    lastWatered: String,
    lastFertilized: String,
    lastHarvest: String,
    healthNotes: String,
    stage: String,
    plantedDate: String,
    transplantDate: String,
    plantNotes: String,
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
    onHarvestChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onStageChange: (String) -> Unit,
    onPlantedDateChange: (String) -> Unit,
    onTransplantDateChange: (String) -> Unit,
    onPlantNotesChange: (String) -> Unit,
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
                if (stage.isNotBlank()) Badge { Text(stage) }
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

            // Last watered — with a "Today" shortcut, the most common action
            DateField(
                value = lastWatered,
                onValueChange = onWateredChange,
                label = "Last Watered",
                previously = plant.lastWatered,
                leading = { Icon(Icons.Default.WaterDrop, null, tint = MaterialTheme.colorScheme.primary) },
                showToday = true,
            )

            DateField(
                value = lastFertilized,
                onValueChange = onFertilizedChange,
                label = "Last Fertilized",
                previously = plant.lastFertilized,
            )

            DateField(
                value = lastHarvest,
                onValueChange = onHarvestChange,
                label = "Last Harvest",
                previously = plant.lastHarvest,
            )

            // Growth stage
            StageDropdown(stage = stage, onStageChange = onStageChange)

            // Health notes
            OutlinedTextField(
                value = healthNotes,
                onValueChange = onNotesChange,
                label = { Text("Health Notes") },
                placeholder = { Text("e.g. Yellowing lower leaves, aphids on stem…") },
                maxLines = 3,
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider()
            Text("Planting", style = MaterialTheme.typography.titleSmall)

            DateField(
                value = plantedDate,
                onValueChange = onPlantedDateChange,
                label = "Planted",
                previously = plant.plantedDate,
            )

            DateField(
                value = transplantDate,
                onValueChange = onTransplantDateChange,
                label = "Transplanted",
                previously = plant.transplantDate,
            )

            OutlinedTextField(
                value = plantNotes,
                onValueChange = onPlantNotesChange,
                label = { Text("Plant Notes") },
                placeholder = { Text("e.g. Started indoors, variety notes…") },
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

/**
 * Read-only date field that opens a Material date picker. Values round-trip as
 * ISO `YYYY-MM-DD`, which is what the care endpoint expects.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    previously: String?,
    leading: (@Composable () -> Unit)? = null,
    showToday: Boolean = false,
) {
    var showPicker by remember { mutableStateOf(false) }

    if (showPicker) {
        val initialMillis = DateUtil.parseDate(value)
            ?.atStartOfDay(ZoneOffset.UTC)?.toInstant()?.toEpochMilli()
        val state = rememberDatePickerState(initialSelectedDateMillis = initialMillis)
        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let {
                        onValueChange(
                            DateUtil.formatDate(
                                Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate(),
                            ),
                        )
                    }
                    showPicker = false
                }) { Text("OK") }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) { Text("Cancel") }
            },
        ) { DatePicker(state = state) }
    }

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        OutlinedTextField(
            value = if (value.isBlank()) "" else DateUtil.displayDate(value),
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            placeholder = { Text("Not set") },
            leadingIcon = leading,
            trailingIcon = {
                Row {
                    if (value.isNotBlank()) {
                        IconButton(onClick = { onValueChange("") }) {
                            Icon(Icons.Default.Clear, "Clear $label")
                        }
                    }
                    IconButton(onClick = { showPicker = true }) {
                        Icon(Icons.Default.DateRange, "Pick $label")
                    }
                }
            },
            supportingText = previously?.let { { Text("Previously: ${DateUtil.displayDate(it)}") } },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().testTag("date-field-$label"),
        )
        if (showToday) {
            TextButton(onClick = { onValueChange(DateUtil.formatDate(LocalDate.now())) }) {
                Text("Today")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StageDropdown(stage: String, onStageChange: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = stage.replaceFirstChar(Char::uppercase),
            onValueChange = {},
            readOnly = true,
            label = { Text("Stage") },
            placeholder = { Text("Not set") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth().testTag("stage-dropdown"),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            STAGES.forEach { s ->
                DropdownMenuItem(
                    text = { Text(s.replaceFirstChar(Char::uppercase)) },
                    onClick = { onStageChange(s); expanded = false },
                )
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
