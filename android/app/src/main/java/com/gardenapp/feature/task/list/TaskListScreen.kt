package com.gardenapp.feature.task.list

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.Task
import com.gardenapp.feature.task.list.components.MonthGrid
import com.gardenapp.feature.task.list.components.TaskRow
import java.time.LocalDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskListScreen(
    onNavigateToCreate: () -> Unit,
    onNavigateToDetail: (Int) -> Unit,
    viewModel: TaskListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    // Day-detail bottom sheet
    if (uiState.selectedDay != null) {
        val dayTasks = uiState.tasks.filter { it.dueDate == uiState.selectedDay }
        ModalBottomSheet(onDismissRequest = { viewModel.selectDay(null) }) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .padding(bottom = 32.dp),
            ) {
                Text(
                    uiState.selectedDay!!,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
                if (dayTasks.isEmpty()) {
                    Text(
                        "No tasks on this day",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 16.dp),
                    )
                } else {
                    dayTasks.forEach { task ->
                        TaskRow(
                            task = task,
                            onClick = { viewModel.selectDay(null); onNavigateToDetail(task.id) },
                            onComplete = { viewModel.completeTask(task.id) },
                            onDelete = { viewModel.deleteTask(task.id) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Tasks", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = viewModel::toggleMode) {
                        Icon(
                            if (uiState.mode == TaskViewMode.List) Icons.Default.CalendarMonth
                            else Icons.Default.List,
                            contentDescription = "Toggle view",
                        )
                    }
                    if (uiState.mode == TaskViewMode.List) {
                        TextButton(onClick = viewModel::toggleShowCompleted) {
                            Text(if (uiState.showCompleted) "Hide done" else "Show done")
                        }
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onNavigateToCreate) {
                Icon(Icons.Default.Add, "Add task")
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading && uiState.tasks.isEmpty() -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                uiState.mode == TaskViewMode.Calendar -> {
                    val (month, year) = uiState.currentMonthYear
                    MonthGrid(
                        month = month,
                        year = year,
                        tasks = uiState.tasks,
                        selectedDay = uiState.selectedDay,
                        onDayClick = viewModel::selectDay,
                        onPrevMonth = viewModel::prevMonth,
                        onNextMonth = viewModel::nextMonth,
                        modifier = Modifier.fillMaxWidth().padding(8.dp),
                    )
                }
                else -> {
                    val visible = if (uiState.showCompleted) uiState.tasks
                    else uiState.tasks.filter { !it.completed }

                    if (visible.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(
                                "No tasks — tap + to add one",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        val grouped = groupByDate(visible)
                        LazyColumn(modifier = Modifier.fillMaxSize()) {
                            grouped.forEach { (header, tasks) ->
                                item(key = header) {
                                    Text(
                                        header,
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                                    )
                                }
                                items(tasks, key = { it.id }) { task ->
                                    TaskRow(
                                        task = task,
                                        onClick = { onNavigateToDetail(task.id) },
                                        onComplete = { viewModel.completeTask(task.id) },
                                        onDelete = { viewModel.deleteTask(task.id) },
                                    )
                                    HorizontalDivider()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun groupByDate(tasks: List<Task>): LinkedHashMap<String, List<Task>> {
    val today = LocalDate.now()
    val weekEnd = today.plusDays(7)
    val result = LinkedHashMap<String, List<Task>>()
    val overdue = mutableListOf<Task>()
    val todayList = mutableListOf<Task>()
    val thisWeek = mutableListOf<Task>()
    val later = mutableListOf<Task>()
    val noDate = mutableListOf<Task>()

    tasks.forEach { task ->
        val due = task.dueDate?.let {
            try { LocalDate.parse(it) } catch (e: Exception) { null }
        }
        when {
            due == null -> noDate.add(task)
            due.isBefore(today) -> overdue.add(task)
            due == today -> todayList.add(task)
            due.isBefore(weekEnd) -> thisWeek.add(task)
            else -> later.add(task)
        }
    }

    if (overdue.isNotEmpty()) result["Overdue"] = overdue
    if (todayList.isNotEmpty()) result["Today"] = todayList
    if (thisWeek.isNotEmpty()) result["This Week"] = thisWeek
    if (later.isNotEmpty()) result["Later"] = later
    if (noDate.isNotEmpty()) result["No Due Date"] = noDate
    return result
}
