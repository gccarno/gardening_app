package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail

@Composable
fun CompanionsTab(plant: PlantDetail) {
    val lib = plant.library
    val good = lib?.goodNeighbors ?: emptyList()
    val bad = lib?.badNeighbors ?: emptyList()

    if (good.isEmpty() && bad.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No companion data available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (good.isNotEmpty()) {
            item {
                Text("Good Neighbors", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary)
            }
            items(good) { name ->
                CompanionChip(name = name, color = MaterialTheme.colorScheme.primaryContainer)
            }
        }
        if (bad.isNotEmpty()) {
            item { Spacer(Modifier.height(8.dp)) }
            item {
                Text("Bad Neighbors", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.error)
            }
            items(bad) { name ->
                CompanionChip(name = name, color = MaterialTheme.colorScheme.errorContainer)
            }
        }
    }
}

@Composable
private fun CompanionChip(name: String, color: Color) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = color,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            name,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
