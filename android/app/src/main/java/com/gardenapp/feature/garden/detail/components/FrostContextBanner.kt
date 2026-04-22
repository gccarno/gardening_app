package com.gardenapp.feature.garden.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Garden
import com.gardenapp.core.util.DateUtil

@Composable
fun FrostContextBanner(garden: Garden, modifier: Modifier = Modifier) {
    val lastFrostDays = DateUtil.daysUntil(garden.lastFrostDate)
    val firstFrostDays = DateUtil.daysUntil(garden.firstFrostDate)

    val (emoji, message, containerColor) = when {
        lastFrostDays != null && lastFrostDays > 0 ->
            Triple("❄️", "Last spring frost in $lastFrostDays days (${DateUtil.displayDate(garden.lastFrostDate)})",
                MaterialTheme.colorScheme.primaryContainer)
        firstFrostDays != null && firstFrostDays in 0..60 ->
            Triple("🍂", "First fall frost in $firstFrostDays days (${DateUtil.displayDate(garden.firstFrostDate)})",
                MaterialTheme.colorScheme.tertiaryContainer)
        garden.usdaZone != null ->
            Triple("🌿", "USDA Zone ${garden.usdaZone}${garden.zoneTempRange?.let { " · $it" } ?: ""}",
                MaterialTheme.colorScheme.secondaryContainer)
        else -> return
    }

    Surface(
        shape = MaterialTheme.shapes.medium,
        color = containerColor,
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(emoji, style = MaterialTheme.typography.titleMedium)
            Text(message, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
        }
    }
}
