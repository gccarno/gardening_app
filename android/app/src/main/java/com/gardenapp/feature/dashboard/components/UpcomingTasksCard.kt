package com.gardenapp.feature.dashboard.components

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.DashboardTask
import com.gardenapp.core.model.TaskType
import com.gardenapp.core.util.DateUtil

@Composable
fun UpcomingTasksCard(
    tasks: List<DashboardTask>,
    onSeeAll: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Upcoming Tasks", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                TextButton(onClick = onSeeAll) { Text("See all") }
            }

            if (tasks.isEmpty()) {
                Text(
                    "No upcoming tasks",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                tasks.forEach { task ->
                    TaskRow(task = task)
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
        }
    }
}

@Composable
private fun TaskRow(task: DashboardTask) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val taskType = TaskType.from(task.taskType)
        Surface(
            shape = MaterialTheme.shapes.extraSmall,
            color = MaterialTheme.colorScheme.secondaryContainer,
            modifier = Modifier.size(32.dp),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(taskTypeEmoji(taskType), style = MaterialTheme.typography.bodyMedium)
            }
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(task.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            val subtitle = buildList {
                task.plantName?.let { add(it) }
                task.dueDate?.let { add(DateUtil.relativeDate(it)) }
            }.joinToString(" · ")
            if (subtitle.isNotEmpty()) {
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private fun taskTypeEmoji(type: TaskType): String = when (type) {
    TaskType.SEEDING -> "🌱"
    TaskType.TRANSPLANTING -> "🌿"
    TaskType.WATERING -> "💧"
    TaskType.FERTILIZING -> "🪴"
    TaskType.MULCHING -> "🍂"
    TaskType.WEEDING -> "🌾"
    TaskType.HARVEST -> "🥕"
    TaskType.OTHER -> "📋"
}
