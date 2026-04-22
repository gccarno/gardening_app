package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail

@Composable
fun CalendarTab(plant: PlantDetail) {
    if (plant.tasks.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text(
                "No tasks for this plant",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    val (completed, pending) = plant.tasks.partition { it.completed }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (pending.isNotEmpty()) {
            item { Text("Upcoming", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold) }
            items(pending) { task ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(task.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                            task.taskType?.let { Text(it, style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                        task.dueDate?.let {
                            Text(it, style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        }
        if (completed.isNotEmpty()) {
            item { Spacer(Modifier.height(8.dp)) }
            item { Text("Completed", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold) }
            items(completed) { task ->
                ListItem(
                    headlineContent = { Text(task.title, color = MaterialTheme.colorScheme.onSurfaceVariant) },
                    supportingContent = { task.dueDate?.let { Text(it) } },
                )
            }
        }
    }
}
