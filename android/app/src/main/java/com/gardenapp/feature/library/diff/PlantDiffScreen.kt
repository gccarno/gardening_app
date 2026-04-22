package com.gardenapp.feature.library.diff

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.model.LibraryEntry

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlantDiffScreen(
    onBack: () -> Unit,
    viewModel: PlantDiffViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Compare Plants", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
            )
        },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading -> CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                uiState.entryA != null && uiState.entryB != null -> {
                    DiffContent(a = uiState.entryA!!, b = uiState.entryB!!)
                }
                uiState.error != null -> Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(uiState.error!!, color = MaterialTheme.colorScheme.error)
                    Button(onClick = { viewModel.load() }) { Text("Retry") }
                }
            }
        }
    }
}

@Composable
private fun DiffContent(a: LibraryEntry, b: LibraryEntry) {
    val rows = remember(a, b) { buildDiffRows(a, b) }

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        // Header
        item {
            Row(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                Text("", modifier = Modifier.weight(0.3f))
                Text(a.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center, modifier = Modifier.weight(0.35f))
                Text(b.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center, modifier = Modifier.weight(0.35f))
            }
            HorizontalDivider()
        }

        items(rows) { row ->
            DiffRow(label = row.first, valueA = row.second, valueB = row.third)
            HorizontalDivider()
        }
    }
}

@Composable
private fun DiffRow(label: String, valueA: String, valueB: String) {
    val different = valueA != valueB && valueA != "—" && valueB != "—"
    val bg = if (different) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.3f)
    else MaterialTheme.colorScheme.surface

    Surface(color = bg) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(0.3f))
            Text(valueA, style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center, modifier = Modifier.weight(0.35f),
                fontWeight = if (different) FontWeight.Bold else FontWeight.Normal)
            Text(valueB, style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center, modifier = Modifier.weight(0.35f),
                fontWeight = if (different) FontWeight.Bold else FontWeight.Normal)
        }
    }
}

private fun buildDiffRows(a: LibraryEntry, b: LibraryEntry): List<Triple<String, String, String>> {
    fun str(v: Any?) = v?.toString() ?: "—"
    return listOf(
        Triple("Scientific name", str(a.scientificName), str(b.scientificName)),
        Triple("Type", str(a.type), str(b.type)),
        Triple("Sunlight", str(a.sunlight), str(b.sunlight)),
        Triple("Water", str(a.water), str(b.water)),
        Triple("Spacing (in)", str(a.spacingIn?.toInt()), str(b.spacingIn?.toInt())),
        Triple("Days to germinate", str(a.daysToGermination), str(b.daysToGermination)),
        Triple("Days to harvest", str(a.daysToHarvest), str(b.daysToHarvest)),
        Triple("Difficulty", str(a.difficulty), str(b.difficulty)),
        Triple("USDA zones", "${str(a.minZone)}–${str(a.maxZone)}", "${str(b.minZone)}–${str(b.maxZone)}"),
        Triple("Soil type", str(a.soilType), str(b.soilType)),
        Triple("Soil pH", "${str(a.soilPhMin)}–${str(a.soilPhMax)}", "${str(b.soilPhMin)}–${str(b.soilPhMax)}"),
        Triple("Temp range (°F)", "${str(a.tempMinF?.toInt())}–${str(a.tempMaxF?.toInt())}", "${str(b.tempMinF?.toInt())}–${str(b.tempMaxF?.toInt())}"),
        Triple("Layer", str(a.layer), str(b.layer)),
        Triple("Family", str(a.family), str(b.family)),
    )
}
