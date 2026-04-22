package com.gardenapp.feature.garden.list

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.feature.garden.list.components.GardenCard

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GardenListScreen(
    onOpenGarden: (Int) -> Unit,
    onCreateGarden: () -> Unit,
    viewModel: GardenListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.dismissError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Gardens", fontWeight = FontWeight.Bold) },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateGarden) {
                Icon(Icons.Default.Add, contentDescription = "Add garden")
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isRefreshing && uiState.gardens.isEmpty() -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                uiState.gardens.isEmpty() -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("🌱", style = MaterialTheme.typography.displayLarge)
                        Text("No gardens yet", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Tap + to create your first garden",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Button(onClick = onCreateGarden) { Text("Create Garden") }
                    }
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        if (uiState.isRefreshing) {
                            item {
                                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                            }
                        }
                        items(uiState.gardens, key = { it.id }) { garden ->
                            GardenCard(
                                garden = garden,
                                onClick = { onOpenGarden(garden.id) },
                                onDelete = { viewModel.deleteGarden(garden.id) },
                                isDeleting = uiState.deletingId == garden.id,
                            )
                        }
                        item { Spacer(Modifier.height(80.dp)) } // FAB clearance
                    }
                }
            }
        }
    }
}
