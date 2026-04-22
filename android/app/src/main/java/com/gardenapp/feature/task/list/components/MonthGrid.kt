package com.gardenapp.feature.task.list.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gardenapp.core.model.Task
import com.gardenapp.core.model.TaskType
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

private val DAY_HEADERS = listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

@Composable
fun MonthGrid(
    month: Int,
    year: Int,
    tasks: List<Task>,
    selectedDay: String?,
    onDayClick: (String) -> Unit,
    onPrevMonth: () -> Unit,
    onNextMonth: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val today = remember { LocalDate.now() }
    val firstDay = remember(month, year) { LocalDate.of(year, month, 1) }
    val daysInMonth = remember(month, year) { firstDay.lengthOfMonth() }
    // Sunday = 0, so dayOfWeek.value: Mon=1..Sun=7 → need Sun=0
    val startOffset = remember(firstDay) { firstDay.dayOfWeek.value % 7 }

    // Build task lookup: date string → list of tasks
    val tasksByDate = remember(tasks) {
        tasks.filter { it.dueDate != null }.groupBy { it.dueDate!! }
    }

    val monthName = remember(month, year) {
        LocalDate.of(year, month, 1).month.getDisplayName(TextStyle.FULL, Locale.getDefault())
    }

    Column(modifier = modifier) {
        // Month nav header
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onPrevMonth) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Previous") }
            Text(
                "$monthName $year",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            IconButton(onClick = onNextMonth) { Icon(Icons.AutoMirrored.Filled.ArrowForward, "Next") }
        }

        // Day-of-week headers
        Row(modifier = Modifier.fillMaxWidth()) {
            DAY_HEADERS.forEach { label ->
                Text(
                    label,
                    modifier = Modifier.weight(1f),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Spacer(Modifier.height(4.dp))

        // Build cell list: nulls for leading blanks, then day numbers
        val cells = List(startOffset) { null } + (1..daysInMonth).map { it }

        LazyVerticalGrid(
            columns = GridCells.Fixed(7),
            modifier = Modifier.fillMaxWidth(),
            userScrollEnabled = false,
        ) {
            items(cells) { day ->
                if (day == null) {
                    Box(modifier = Modifier.aspectRatio(1f))
                } else {
                    val dateStr = "%04d-%02d-%02d".format(year, month, day)
                    val dayTasks = tasksByDate[dateStr] ?: emptyList()
                    val isToday = today.year == year && today.monthValue == month && today.dayOfMonth == day
                    val isSelected = selectedDay == dateStr

                    DayCell(
                        day = day,
                        tasks = dayTasks,
                        isToday = isToday,
                        isSelected = isSelected,
                        onClick = { onDayClick(dateStr) },
                    )
                }
            }
        }
    }
}

@Composable
private fun DayCell(
    day: Int,
    tasks: List<Task>,
    isToday: Boolean,
    isSelected: Boolean,
    onClick: () -> Unit,
) {
    val bg = when {
        isSelected -> MaterialTheme.colorScheme.primaryContainer
        isToday -> MaterialTheme.colorScheme.secondaryContainer
        else -> Color.Transparent
    }

    Box(
        modifier = Modifier
            .aspectRatio(1f)
            .padding(2.dp)
            .background(bg, shape = MaterialTheme.shapes.small)
            .then(
                if (isToday && !isSelected) Modifier.border(
                    1.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small,
                ) else Modifier
            )
            .clickable(onClick = onClick),
        contentAlignment = Alignment.TopCenter,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(top = 2.dp),
        ) {
            Text(
                day.toString(),
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal,
            )
            if (tasks.isNotEmpty()) {
                Row(
                    horizontalArrangement = Arrangement.Center,
                    modifier = Modifier.padding(top = 1.dp),
                ) {
                    tasks.take(3).forEach { task ->
                        Box(
                            modifier = Modifier
                                .size(5.dp)
                                .padding(horizontal = 1.dp)
                                .background(
                                    Color(TaskType.from(task.taskType).color),
                                    shape = MaterialTheme.shapes.small,
                                ),
                        )
                    }
                }
            }
        }
    }
}
