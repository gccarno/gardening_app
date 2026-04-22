package com.gardenapp.feature.canvas.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.CanvasPlant

@Composable
fun RightInfoPanel(
    placedBeds: List<Bed>,
    canvasPlants: List<CanvasPlant>,
    selectedBedId: Int?,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }

    Surface(
        modifier = modifier.width(200.dp).fillMaxHeight(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 4.dp,
    ) {
        Column {
            TabRow(selectedTabIndex = tab) {
                Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Summary") })
                Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Plants") })
            }

            when (tab) {
                0 -> SummaryTab(placedBeds, selectedBedId)
                1 -> PlantsTab(canvasPlants)
            }
        }
    }
}

@Composable
private fun SummaryTab(placedBeds: List<Bed>, selectedBedId: Int?) {
    val bed = placedBeds.find { it.id == selectedBedId }

    Column(
        modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (bed != null) {
            Text("Selected Bed", style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(bed.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text("${bed.widthFt.toInt()} × ${bed.heightFt.toInt()} ft",
                style = MaterialTheme.typography.bodySmall)
            bed.soilNotes?.let {
                Spacer(Modifier.height(4.dp))
                Text("Soil: $it", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            bed.soilPh?.let {
                Text("pH: $it", style = MaterialTheme.typography.bodySmall)
            }
        } else {
            Text("Canvas", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text("Beds on canvas", style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("${placedBeds.size}", style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Text("Tap a bed to see details", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun PlantsTab(canvasPlants: List<CanvasPlant>) {
    Column(
        modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text("Canvas Plants", style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (canvasPlants.isEmpty()) {
            Text("No plants placed yet", style = MaterialTheme.typography.bodySmall)
        } else {
            canvasPlants.forEach { plant ->
                Text("• ${plant.name}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
