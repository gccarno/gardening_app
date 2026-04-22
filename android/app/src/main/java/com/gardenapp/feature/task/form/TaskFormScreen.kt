package com.gardenapp.feature.task.form

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.Garden
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.TaskType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskFormScreen(
    onBack: () -> Unit,
    onSaved: (Int) -> Unit,
    viewModel: TaskFormViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (uiState.isEditMode) "Edit Task" else "New Task", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = uiState.title,
                onValueChange = viewModel::onTitleChange,
                label = { Text("Title *") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            // Task type dropdown
            TypeDropdown(
                selected = uiState.taskType,
                onSelect = viewModel::onTaskTypeChange,
            )

            OutlinedTextField(
                value = uiState.dueDate,
                onValueChange = viewModel::onDueDateChange,
                label = { Text("Due Date") },
                placeholder = { Text("YYYY-MM-DD") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider()
            Text("Associations (optional)", style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)

            // Garden picker
            if (uiState.gardens.isNotEmpty()) {
                AssociationDropdown(
                    label = "Garden",
                    selectedId = uiState.selectedGardenId,
                    items = uiState.gardens,
                    itemLabel = { it.name },
                    itemId = { it.id },
                    onSelect = { viewModel.onGardenSelect(it) },
                )
            }

            // Bed picker (filtered by garden)
            val availableBeds = if (uiState.selectedGardenId != null)
                uiState.beds.filter { it.gardenId == uiState.selectedGardenId }
            else uiState.beds

            if (availableBeds.isNotEmpty()) {
                AssociationDropdown(
                    label = "Bed",
                    selectedId = uiState.selectedBedId,
                    items = availableBeds,
                    itemLabel = { it.name },
                    itemId = { it.id },
                    onSelect = { viewModel.onBedSelect(it) },
                )
            }

            // Plant picker (filtered by garden)
            val availablePlants = if (uiState.selectedGardenId != null)
                uiState.plants.filter { it.gardenId == uiState.selectedGardenId }
            else uiState.plants

            if (availablePlants.isNotEmpty()) {
                AssociationDropdown(
                    label = "Plant",
                    selectedId = uiState.selectedPlantId,
                    items = availablePlants,
                    itemLabel = { it.name },
                    itemId = { it.id },
                    onSelect = { viewModel.onPlantSelect(it) },
                )
            }

            OutlinedTextField(
                value = uiState.description,
                onValueChange = viewModel::onDescriptionChange,
                label = { Text("Description") },
                maxLines = 3,
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(8.dp))

            Button(
                onClick = { viewModel.save(onSaved) },
                enabled = !uiState.isSaving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (uiState.isSaving) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                else Text(if (uiState.isEditMode) "Save Changes" else "Create Task")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TypeDropdown(selected: String?, onSelect: (String?) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selected?.replaceFirstChar(Char::uppercase) ?: "— Any type —",
            onValueChange = {},
            readOnly = true,
            label = { Text("Task Type") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("— Any type —") },
                onClick = { expanded = false; onSelect(null) },
            )
            TaskType.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.displayName) },
                    onClick = { expanded = false; onSelect(type.value) },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> AssociationDropdown(
    label: String,
    selectedId: Int?,
    items: List<T>,
    itemLabel: (T) -> String,
    itemId: (T) -> Int,
    onSelect: (Int?) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedItem = items.find { itemId(it) == selectedId }

    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selectedItem?.let { itemLabel(it) } ?: "— None —",
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("— None —") },
                onClick = { expanded = false; onSelect(null) },
            )
            items.forEach { item ->
                DropdownMenuItem(
                    text = { Text(itemLabel(item)) },
                    onClick = { expanded = false; onSelect(itemId(item)) },
                )
            }
        }
    }
}
