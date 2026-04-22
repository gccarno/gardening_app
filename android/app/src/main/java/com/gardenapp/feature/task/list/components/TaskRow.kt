package com.gardenapp.feature.task.list.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Task
import com.gardenapp.core.model.TaskType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskRow(
    task: Task,
    onClick: () -> Unit,
    onComplete: () -> Unit,
    onDelete: () -> Unit,
) {
    var showConfirm by remember { mutableStateOf(false) }

    if (showConfirm) {
        AlertDialog(
            onDismissRequest = { showConfirm = false },
            title = { Text("Delete task?") },
            text = { Text("Delete \"${task.title}\"?") },
            confirmButton = {
                TextButton(onClick = { showConfirm = false; onDelete() }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { showConfirm = false }) { Text("Cancel") }
            },
        )
    }

    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.StartToEnd -> { onComplete(); false }
                SwipeToDismissBoxValue.EndToStart -> { showConfirm = true; false }
                else -> false
            }
        },
        positionalThreshold = { it * 0.4f },
    )

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            val direction = dismissState.dismissDirection
            val bg = when (direction) {
                SwipeToDismissBoxValue.StartToEnd -> MaterialTheme.colorScheme.primaryContainer
                SwipeToDismissBoxValue.EndToStart -> MaterialTheme.colorScheme.errorContainer
                else -> Color.Transparent
            }
            val icon = when (direction) {
                SwipeToDismissBoxValue.StartToEnd -> Icons.Default.Check
                SwipeToDismissBoxValue.EndToStart -> Icons.Default.Delete
                else -> null
            }
            val alignment = when (direction) {
                SwipeToDismissBoxValue.StartToEnd -> Alignment.CenterStart
                else -> Alignment.CenterEnd
            }
            Box(
                modifier = Modifier.fillMaxSize().background(bg).padding(horizontal = 20.dp),
                contentAlignment = alignment,
            ) {
                icon?.let { Icon(it, null) }
            }
        },
    ) {
        val typeColor = Color(TaskType.from(task.taskType).color)
        ListItem(
            leadingContent = {
                Box(
                    modifier = Modifier
                        .width(4.dp)
                        .height(40.dp)
                        .background(typeColor, shape = MaterialTheme.shapes.small),
                )
            },
            headlineContent = {
                Text(
                    task.title,
                    fontWeight = FontWeight.Medium,
                    textDecoration = if (task.completed) TextDecoration.LineThrough else null,
                    color = if (task.completed) MaterialTheme.colorScheme.onSurfaceVariant
                    else MaterialTheme.colorScheme.onSurface,
                )
            },
            supportingContent = {
                val parts = listOfNotNull(
                    task.taskType?.replaceFirstChar(Char::uppercase),
                    task.plantName?.let { "Plant: $it" },
                    task.gardenName?.let { "Garden: $it" },
                )
                if (parts.isNotEmpty()) Text(parts.joinToString(" · "))
            },
            trailingContent = {
                task.dueDate?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.labelSmall,
                        color = dueDateColor(it),
                    )
                }
            },
            modifier = Modifier
                .background(MaterialTheme.colorScheme.surface)
                .clickable(onClick = onClick),
        )
    }
}

@Composable
private fun dueDateColor(dueDate: String): androidx.compose.ui.graphics.Color {
    return try {
        val date = java.time.LocalDate.parse(dueDate)
        val today = java.time.LocalDate.now()
        when {
            date.isBefore(today) -> MaterialTheme.colorScheme.error
            date == today -> MaterialTheme.colorScheme.primary
            else -> MaterialTheme.colorScheme.onSurfaceVariant
        }
    } catch (e: Exception) {
        MaterialTheme.colorScheme.onSurfaceVariant
    }
}
