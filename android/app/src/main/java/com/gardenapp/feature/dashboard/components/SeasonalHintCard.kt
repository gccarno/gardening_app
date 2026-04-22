package com.gardenapp.feature.dashboard.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.DashboardData

@Composable
fun SeasonalHintCard(dashboard: DashboardData, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(dashboard.seasonIcon, style = MaterialTheme.typography.titleLarge)
                Text(
                    text = dashboard.season.replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            if (dashboard.hintText.isNotEmpty()) {
                Text(
                    text = "${dashboard.hintAction} ${dashboard.hintText}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (dashboard.hintCrops.isNotEmpty()) {
                Text(
                    text = dashboard.hintCrops,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
            }
            dashboard.frostContext?.let {
                HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
                Text(text = it, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
            }
        }
    }
}
