package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail

private val STATUSES = listOf("planning", "seeded", "germinated", "seedling", "transplanted", "growing", "harvested", "dormant")

@Composable
fun MyPlantTab(
    plant: PlantDetail,
    isSavingStatus: Boolean,
    onSetStatus: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Status picker
        Text("Status", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
            OutlinedTextField(
                value = plant.status?.replaceFirstChar(Char::uppercase) ?: "Planning",
                onValueChange = {},
                readOnly = true,
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                modifier = Modifier.menuAnchor().fillMaxWidth(),
                enabled = !isSavingStatus,
            )
            ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                STATUSES.forEach { s ->
                    DropdownMenuItem(
                        text = { Text(s.replaceFirstChar(Char::uppercase)) },
                        onClick = { expanded = false; onSetStatus(s) },
                    )
                }
            }
        }

        HorizontalDivider()
        Text("Dates", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        InfoRow("Planted", plant.plantedDate ?: "—")
        InfoRow("Transplant", plant.transplantDate ?: "—")
        InfoRow("Expected Harvest", plant.expectedHarvest ?: "—")

        // Bed assignments
        if (plant.bedAssignments.isNotEmpty()) {
            HorizontalDivider()
            Text("Beds", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            plant.bedAssignments.forEach { ba ->
                Text(
                    "• ${ba.bedName}${ba.gardenName?.let { " ($it)" } ?: ""}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }

        // Notes
        plant.tasks.takeIf { it.isNotEmpty() }?.let { tasks ->
            HorizontalDivider()
            Text("Upcoming Tasks", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            tasks.take(5).forEach { t ->
                Text(
                    "• ${t.title}${t.dueDate?.let { " — $it" } ?: ""}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (t.completed) MaterialTheme.colorScheme.onSurfaceVariant
                    else MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}
