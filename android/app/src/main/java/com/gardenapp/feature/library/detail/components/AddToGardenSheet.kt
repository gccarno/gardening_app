package com.gardenapp.feature.library.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Garden

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddToGardenSheet(
    gardens: List<Garden>,
    defaultName: String,
    isSaving: Boolean,
    onAdd: (gardenId: Int, name: String, plantedDate: String?) -> Unit,
    onDismiss: () -> Unit,
) {
    var selectedGardenId by remember { mutableStateOf(gardens.firstOrNull()?.id) }
    var plantName by remember { mutableStateOf(defaultName) }
    var plantedDate by remember { mutableStateOf("") }
    var gardenExpanded by remember { mutableStateOf(false) }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Add to Garden", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

            // Garden picker
            if (gardens.isNotEmpty()) {
                val selectedGarden = gardens.find { it.id == selectedGardenId }
                ExposedDropdownMenuBox(expanded = gardenExpanded, onExpandedChange = { gardenExpanded = it }) {
                    OutlinedTextField(
                        value = selectedGarden?.name ?: "Select garden",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Garden") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(gardenExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth(),
                    )
                    ExposedDropdownMenu(expanded = gardenExpanded, onDismissRequest = { gardenExpanded = false }) {
                        gardens.forEach { garden ->
                            DropdownMenuItem(
                                text = { Text(garden.name) },
                                onClick = { gardenExpanded = false; selectedGardenId = garden.id },
                            )
                        }
                    }
                }
            }

            OutlinedTextField(
                value = plantName,
                onValueChange = { plantName = it },
                label = { Text("Plant Name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            OutlinedTextField(
                value = plantedDate,
                onValueChange = { plantedDate = it },
                label = { Text("Planted Date (optional)") },
                placeholder = { Text("YYYY-MM-DD") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = {
                    selectedGardenId?.let { id ->
                        onAdd(id, plantName, plantedDate.ifBlank { null })
                    }
                },
                enabled = !isSaving && selectedGardenId != null && plantName.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isSaving) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                else Text("Add Plant")
            }
        }
    }
}
