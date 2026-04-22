package com.gardenapp.feature.bed.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.WaterDrop
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.util.DateUtil

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CareTrackingSheet(
    plant: BedPlantDetail,
    lastWatered: String,
    lastFertilized: String,
    healthNotes: String,
    isSaving: Boolean,
    onWateredChange: (String) -> Unit,
    onFertilizedChange: (String) -> Unit,
    onNotesChange: (String) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
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
        }
    }
}
