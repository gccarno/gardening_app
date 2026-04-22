package com.gardenapp.feature.dashboard.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.DashboardMetrics

@Composable
fun MetricsRow(metrics: DashboardMetrics, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        MetricCard("Beds", metrics.bedCount.toString(), Modifier.weight(1f))
        MetricCard("Plants", metrics.plantCount.toString(), Modifier.weight(1f))
        MetricCard("Active", metrics.plantsActive.toString(), Modifier.weight(1f))
        MetricCard(
            label = "Tasks",
            value = metrics.taskCount.toString(),
            modifier = Modifier.weight(1f),
            badge = if (metrics.overdueTasks > 0) metrics.overdueTasks.toString() else null,
        )
    }
}

@Composable
private fun MetricCard(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    badge: String? = null,
) {
    Card(modifier = modifier) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Box {
                Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                if (badge != null) {
                    Badge(
                        modifier = Modifier.align(Alignment.TopEnd),
                        containerColor = MaterialTheme.colorScheme.error,
                    ) { Text(badge) }
                }
            }
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
