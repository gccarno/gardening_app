package com.gardenapp.feature.bed.list

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.Bed

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BedListScreen(
    onBack: () -> Unit,
    onOpenBed: (Int) -> Unit,
    onCreateBed: (gardenId: Int) -> Unit,
    viewModel: BedListViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Garden Beds", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
            )
        },
        floatingActionButton = {
            uiState.gardenId?.let { gid ->
                FloatingActionButton(onClick = { onCreateBed(gid) }) {
                    Icon(Icons.Default.Add, "Add bed")
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isRefreshing && uiState.beds.isEmpty() ->
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))

                uiState.beds.isEmpty() ->
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("🪴", style = MaterialTheme.typography.displayLarge)
                        Text("No beds yet", style = MaterialTheme.typography.titleMedium)
                        uiState.gardenId?.let {
                            Button(onClick = { onCreateBed(it) }) { Text("Add First Bed") }
                        }
                    }

                else ->
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        if (uiState.isRefreshing) {
                            item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                        }
                        items(uiState.beds, key = { it.id }) { bed ->
                            BedRow(
                                bed = bed,
                                onClick = { onOpenBed(bed.id) },
                                onDelete = { viewModel.deleteBed(bed.id) },
                                isDeleting = uiState.deletingId == bed.id,
                            )
                        }
                        item { Spacer(Modifier.height(80.dp)) }
                    }
            }
        }
    }
}

@Composable
private fun BedRow(
    bed: Bed,
    onClick: () -> Unit,
    onDelete: () -> Unit,
    isDeleting: Boolean,
) {
    var showDialog by remember { mutableStateOf(false) }
    if (showDialog) {
        AlertDialog(
            onDismissRequest = { showDialog = false },
            title = { Text("Delete Bed") },
            text = { Text("Delete \"${bed.name}\"? All plants in this bed will be removed.") },
            confirmButton = {
                TextButton(
                    onClick = { showDialog = false; onDelete() },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { showDialog = false }) { Text("Cancel") } },
        )
    }

    Card(onClick = onClick, enabled = !isDeleting, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(bed.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "${bed.widthFt.toInt()}ft × ${bed.heightFt.toInt()}ft" +
                        (bed.plantCount?.let { " · $it plant${if (it != 1) "s" else ""}" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                bed.soilNotes?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                }
            }
            if (isDeleting) {
                CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
            } else {
                IconButton(onClick = { showDialog = true }) {
                    Icon(Icons.Default.Delete, "Delete", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
