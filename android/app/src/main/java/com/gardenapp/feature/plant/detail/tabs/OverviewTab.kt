package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail

@Composable
fun OverviewTab(plant: PlantDetail) {
    val lib = plant.library
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (lib == null) {
            Text(
                "No library entry linked to this plant.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@Column
        }

        lib.scientificName?.let {
            Text(it, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        SectionTitle("Growing Info")
        InfoRow("Type", lib.type?.replaceFirstChar(Char::uppercase) ?: "—")
        InfoRow("Sunlight", lib.sunlight ?: "—")
        InfoRow("Water", lib.water ?: "—")
        InfoRow("Spacing", lib.spacingIn?.let { "${it.toInt()} in" } ?: "—")
        InfoRow("Days to germination", lib.daysToGermination?.toString() ?: "—")
        InfoRow("Days to harvest", lib.daysToHarvest?.toString() ?: "—")
        InfoRow("Difficulty", lib.difficulty?.replaceFirstChar(Char::uppercase) ?: "—")

        lib.family?.let {
            HorizontalDivider()
            SectionTitle("Taxonomy")
            InfoRow("Family", it)
            lib.layer?.let { l -> InfoRow("Layer", l) }
            lib.edibleParts?.let { e -> InfoRow("Edible parts", e) }
        }

        val zoneMin = lib.minZone
        val zoneMax = lib.maxZone
        if (zoneMin != null || zoneMax != null) {
            HorizontalDivider()
            SectionTitle("Climate")
            InfoRow("USDA Zones", "${zoneMin ?: "?"} – ${zoneMax ?: "?"}")
            lib.tempMinF?.let { min ->
                lib.tempMaxF?.let { max ->
                    InfoRow("Temp range", "${min.toInt()}°F – ${max.toInt()}°F")
                }
            }
        }

        lib.permapeopleDescription?.let {
            HorizontalDivider()
            Text(it, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
internal fun SectionTitle(title: String) {
    Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
}

@Composable
internal fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f))
    }
}
