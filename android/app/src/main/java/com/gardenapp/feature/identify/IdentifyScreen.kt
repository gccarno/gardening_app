package com.gardenapp.feature.identify

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage

private val MODES = listOf(
    "identify" to "What plant?",
    "health" to "Health",
    "disease" to "Disease",
    "pest" to "Pest",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IdentifyScreen(
    onOpenLibraryEntry: (Int) -> Unit,
    viewModel: IdentifyViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> viewModel.setImage(uri) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Identify") }) },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    "Snap or pick a photo — get a species ID, health check, or pest/disease diagnosis.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MODES.forEach { (mode, label) ->
                        FilterChip(
                            selected = uiState.mode == mode,
                            onClick = { viewModel.setMode(mode) },
                            label = { Text(label) },
                        )
                    }
                }
            }
            item {
                Card(
                    onClick = {
                        picker.launch(PickVisualMediaRequest(
                            ActivityResultContracts.PickVisualMedia.ImageOnly))
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(220.dp),
                ) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        if (uiState.imageUri != null) {
                            AsyncImage(
                                model = uiState.imageUri,
                                contentDescription = "Selected photo",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize(),
                            )
                        } else {
                            Text("Tap to choose a photo",
                                 color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            item {
                Button(
                    onClick = viewModel::analyze,
                    enabled = uiState.imageUri != null && !uiState.isLoading,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp), strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("Analyzing…")
                    } else {
                        Text("Analyze photo")
                    }
                }
            }
            uiState.error?.let { err ->
                item { Text(err, color = MaterialTheme.colorScheme.error) }
            }
            uiState.result?.let { result ->
                items(result.candidates) { c ->
                    Card(
                        onClick = { c.libraryId?.let(onOpenLibraryEntry) },
                        enabled = c.libraryId != null,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(Modifier.padding(12.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(c.name ?: "Unknown",
                                     style = MaterialTheme.typography.titleMedium)
                                Spacer(Modifier.weight(1f))
                                c.confidence?.let {
                                    AssistChip(onClick = {},
                                               label = { Text("${(it * 100).toInt()}%") })
                                }
                            }
                            c.scientificName?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall,
                                     color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (c.libraryId != null) {
                                Text("View in library →",
                                     style = MaterialTheme.typography.labelMedium,
                                     color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
                result.diagnosis?.let { d ->
                    item {
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(12.dp)) {
                                Text("Assessment", style = MaterialTheme.typography.titleSmall)
                                Text(d, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
                result.careAdvice?.let { advice ->
                    item {
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(12.dp)) {
                                Text("What to do", style = MaterialTheme.typography.titleSmall)
                                Text(advice, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}
