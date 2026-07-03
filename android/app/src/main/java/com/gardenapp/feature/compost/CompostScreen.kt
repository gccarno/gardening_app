package com.gardenapp.feature.compost

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.CompostBin
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private fun stageColor(stage: String): Color = when (stage) {
    "building" -> Color(0xFF8A6A40)
    "active"   -> Color(0xFF5A9E54)
    "curing"   -> Color(0xFF4A80B4)
    "ready"    -> Color(0xFFD4A84B)
    else       -> Color(0xFF7A907A)
}

private fun stageTip(stage: String): String = when (stage) {
    "building" -> "Add alternating layers of greens (nitrogen) and browns (carbon). Keep it moist."
    "active"   -> "Turn the pile every 1–2 weeks. It should heat up to 130–160°F."
    "curing"   -> "Stop adding materials. Let the pile rest and stabilize for 2–4 weeks."
    "ready"    -> "Compost is dark, earthy-smelling, and crumbly. Ready to use!"
    else       -> ""
}

private fun formatDate(iso: String?): String {
    if (iso == null) return "—"
    return try {
        LocalDate.parse(iso).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (e: Exception) {
        android.util.Log.w("CompostScreen", "unparseable date: $iso", e)
        iso
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompostScreen(
    onBack: () -> Unit,
    viewModel: CompostViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }

    if (uiState.showCreateForm) {
        ModalBottomSheet(onDismissRequest = viewModel::hideCreate) {
            CreateBinForm(
                name = uiState.formName,
                startedDate = uiState.formStartedDate,
                isCreating = uiState.isCreating,
                onNameChange = viewModel::updateFormName,
                onDateChange = viewModel::updateFormStartedDate,
                onCreate = viewModel::createBin,
                onCancel = viewModel::hideCreate,
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Compost Helper", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = viewModel::showCreate) {
                Icon(Icons.Default.Add, "New bin")
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            when {
                uiState.isLoading && uiState.bins.isEmpty() -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                uiState.bins.isEmpty() -> {
                    Column(
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("♻️", style = MaterialTheme.typography.displayMedium)
                        Text("No compost bins yet", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Tap + to create your first bin",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        items(uiState.bins, key = { it.id }) { bin ->
                            CompostBinCard(
                                bin = bin,
                                isMatFormOpen = uiState.expandedMatBinId == bin.id,
                                matMaterial = uiState.matFormMaterial,
                                matQuantity = uiState.matFormQuantity,
                                isAddingMat = uiState.isAddingMat,
                                onAdvance = { viewModel.advanceStage(bin.id) },
                                onDelete = { viewModel.deleteBin(bin.id) },
                                onOpenMatForm = { viewModel.openMatForm(bin.id) },
                                onCloseMatForm = viewModel::closeMatForm,
                                onMatMaterialChange = viewModel::updateMatMaterial,
                                onMatQuantityChange = viewModel::updateMatQuantity,
                                onAddMat = { viewModel.addMaterial(bin.id) },
                            )
                        }
                        item { Spacer(Modifier.height(80.dp)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun CompostBinCard(
    bin: CompostBin,
    isMatFormOpen: Boolean,
    matMaterial: String,
    matQuantity: String,
    isAddingMat: Boolean,
    onAdvance: () -> Unit,
    onDelete: () -> Unit,
    onOpenMatForm: () -> Unit,
    onCloseMatForm: () -> Unit,
    onMatMaterialChange: (String) -> Unit,
    onMatQuantityChange: (String) -> Unit,
    onAddMat: () -> Unit,
) {
    var showDeleteDialog by remember { mutableStateOf(false) }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete bin?") },
            text = { Text("\"${bin.name}\" and all its data will be permanently deleted.") },
            confirmButton = {
                TextButton(onClick = { showDeleteDialog = false; onDelete() }) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) { Text("Cancel") }
            },
        )
    }

    val color = stageColor(bin.stage)

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    Text(bin.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Surface(color = color, shape = MaterialTheme.shapes.small) {
                        Text(
                            bin.stage,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = Color.White,
                        )
                    }
                }
                TextButton(
                    onClick = { showDeleteDialog = true },
                    contentPadding = PaddingValues(horizontal = 8.dp),
                ) {
                    Text("Delete", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelSmall)
                }
            }

            // Dates
            Text(
                "Started: ${formatDate(bin.startedDate)}  ·  Est. ready: ${formatDate(bin.estimatedReadyDate)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )

            // Stage tip
            val tip = stageTip(bin.stage)
            if (tip.isNotEmpty()) {
                Text(
                    tip,
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }

            // Materials list
            if (bin.materials.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Materials added:",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                bin.materials.forEach { mat ->
                    val qty = if (mat.quantityLbs != null) " (${mat.quantityLbs} lbs)" else ""
                    Text(
                        "• ${mat.material}$qty — ${mat.dateAdded}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            // Action buttons
            Row(
                modifier = Modifier.padding(top = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (bin.stage != "ready") {
                    OutlinedButton(
                        onClick = onAdvance,
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                    ) {
                        Text("Advance stage →", style = MaterialTheme.typography.labelMedium)
                    }
                }
                OutlinedButton(
                    onClick = if (isMatFormOpen) onCloseMatForm else onOpenMatForm,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                ) {
                    Text(
                        if (isMatFormOpen) "Cancel" else "+ Add material",
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }

            // Inline material form
            AnimatedVisibility(visible = isMatFormOpen) {
                Column(
                    modifier = Modifier
                        .padding(top = 8.dp)
                        .fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = matMaterial,
                        onValueChange = onMatMaterialChange,
                        label = { Text("Material (e.g. kitchen scraps, dry leaves)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = matQuantity,
                        onValueChange = onMatQuantityChange,
                        label = { Text("Weight in lbs (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                    Button(
                        onClick = onAddMat,
                        enabled = matMaterial.isNotBlank() && !isAddingMat,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (isAddingMat) "Adding…" else "Add Material")
                    }
                }
            }
        }
    }
}

@Composable
private fun CreateBinForm(
    name: String,
    startedDate: String,
    isCreating: Boolean,
    onNameChange: (String) -> Unit,
    onDateChange: (String) -> Unit,
    onCreate: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("New Compost Bin", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        OutlinedTextField(
            value = name,
            onValueChange = onNameChange,
            label = { Text("Bin name *") },
            placeholder = { Text("e.g. Back yard pile") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = startedDate,
            onValueChange = onDateChange,
            label = { Text("Started date (YYYY-MM-DD)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("Cancel") }
            Button(
                onClick = onCreate,
                enabled = name.isNotBlank() && !isCreating,
                modifier = Modifier.weight(1f),
            ) {
                Text(if (isCreating) "Creating…" else "Create Bin")
            }
        }
    }
}
