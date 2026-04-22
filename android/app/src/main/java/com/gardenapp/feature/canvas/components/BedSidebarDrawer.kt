package com.gardenapp.feature.canvas.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Bed

@Composable
fun BedSidebarDrawer(
    sidebarBeds: List<Bed>,
    placedBedIds: Set<Int>,
    onAddBed: (Bed) -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.width(160.dp).fillMaxHeight(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 4.dp,
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
                Text(
                    "Beds",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                )
            }

            if (sidebarBeds.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No beds", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(8.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(sidebarBeds, key = { it.id }) { bed ->
                        val isPlaced = bed.id in placedBedIds
                        BedSidebarItem(
                            bed = bed,
                            isPlaced = isPlaced,
                            onAdd = { onAddBed(bed) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun BedSidebarItem(bed: Bed, isPlaced: Boolean, onAdd: () -> Unit) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = if (isPlaced) MaterialTheme.colorScheme.primaryContainer
        else MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(bed.name, style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium, maxLines = 1)
                Text("${bed.widthFt.toInt()}×${bed.heightFt.toInt()}ft",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (!isPlaced) {
                IconButton(onClick = onAdd, modifier = Modifier.size(24.dp)) {
                    Icon(Icons.Default.Add, "Add to canvas",
                        modifier = Modifier.size(16.dp))
                }
            }
        }
    }
}
