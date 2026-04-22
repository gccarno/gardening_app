package com.gardenapp.feature.garden.form

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GardenFormScreen(
    onBack: () -> Unit,
    onSaved: (gardenId: Int) -> Unit,
    viewModel: GardenFormViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.savedGardenId) {
        uiState.savedGardenId?.let { onSaved(it) }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.dismissError()
        }
    }

    val isEditing = uiState.existingGarden != null
    val title = if (isEditing) "Edit Garden" else "New Garden"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
                actions = {
                    TextButton(
                        onClick = { viewModel.save() },
                        enabled = !uiState.isSaving && uiState.name.isNotBlank(),
                    ) {
                        if (uiState.isSaving) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        } else {
                            Text("Save")
                        }
                    }
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
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Name
            OutlinedTextField(
                value = uiState.name,
                onValueChange = viewModel::onNameChange,
                label = { Text("Garden Name *") },
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            // Description
            OutlinedTextField(
                value = uiState.description,
                onValueChange = viewModel::onDescriptionChange,
                label = { Text("Description") },
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                minLines = 2,
                maxLines = 4,
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider()
            Text("Location", style = MaterialTheme.typography.titleSmall)

            // ZIP code field with enrichment note
            OutlinedTextField(
                value = uiState.zipCode,
                onValueChange = viewModel::onZipChange,
                label = { Text("ZIP Code (US)") },
                placeholder = { Text("e.g. 90210") },
                supportingText = {
                    Text(
                        if (uiState.zipCode.length == 5)
                            "✓ Location, USDA zone & frost dates will be looked up on save"
                        else
                            "Enter 5-digit ZIP to auto-fill zone and frost dates"
                    )
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true,
                isError = uiState.zipCode.isNotEmpty() && uiState.zipCode.length != 5,
                modifier = Modifier.fillMaxWidth(),
            )

            // Show existing location data if editing
            uiState.existingGarden?.let { g ->
                val locationParts = listOfNotNull(g.city, g.state).joinToString(", ")
                if (locationParts.isNotEmpty() || g.usdaZone != null) {
                    Surface(
                        shape = MaterialTheme.shapes.small,
                        color = MaterialTheme.colorScheme.secondaryContainer,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            if (locationParts.isNotEmpty()) {
                                Text("📍 $locationParts", style = MaterialTheme.typography.bodyMedium)
                            }
                            g.usdaZone?.let {
                                Text("🌿 USDA Zone $it", style = MaterialTheme.typography.bodyMedium)
                            }
                            g.lastFrostDate?.let {
                                Text("❄️ Last frost: $it", style = MaterialTheme.typography.bodySmall)
                            }
                            g.firstFrostDate?.let {
                                Text("🍂 First fall frost: $it", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }

            HorizontalDivider()
            Text("Watering", style = MaterialTheme.typography.titleSmall)

            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = uiState.wateringFrequencyDays,
                    onValueChange = viewModel::onWateringFreqChange,
                    label = { Text("Frequency (days)") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = uiState.waterSource,
                    onValueChange = viewModel::onWaterSourceChange,
                    label = { Text("Water Source") },
                    placeholder = { Text("e.g. Hose, Drip") },
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }

            HorizontalDivider()
            Text("Units", style = MaterialTheme.typography.titleSmall)

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("ft" to "Feet", "m" to "Meters").forEach { (value, label) ->
                    FilterChip(
                        selected = uiState.unit == value,
                        onClick = { viewModel.onUnitChange(value) },
                        label = { Text(label) },
                    )
                }
            }

            Spacer(Modifier.height(32.dp))
        }
    }
}
