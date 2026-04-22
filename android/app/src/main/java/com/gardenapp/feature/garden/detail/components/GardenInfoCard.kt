package com.gardenapp.feature.garden.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Garden

@Composable
fun GardenInfoCard(garden: Garden, modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            garden.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
                HorizontalDivider()
            }

            val rows = buildList {
                val location = listOfNotNull(garden.city, garden.state).joinToString(", ")
                if (location.isNotEmpty()) add("📍 Location" to location)
                garden.usdaZone?.let { add("🌿 USDA Zone" to it) }
                garden.zoneTempRange?.let { add("🌡️ Temp Range" to it) }
                garden.lastFrostDate?.let { add("❄️ Last Spring Frost" to it) }
                garden.firstFrostDate?.let { add("🍂 First Fall Frost" to it) }
                garden.wateringFrequencyDays?.let { add("💧 Water Every" to "$it days") }
                garden.waterSource?.let { add("🚿 Water Source" to it) }
                add("📐 Units" to if (garden.unit == "ft") "Feet" else "Meters")
            }

            rows.forEach { (label, value) ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                }
            }
        }
    }
}
