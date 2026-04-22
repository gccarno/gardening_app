package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail

@Composable
fun SoilTab(plant: PlantDetail) {
    val lib = plant.library

    if (lib == null || (lib.soilType == null && lib.soilPhMin == null && lib.soilPhMax == null)) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No soil data available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionTitle("Soil Requirements")
        lib.soilType?.let { InfoRow("Soil type", it) }
        if (lib.soilPhMin != null || lib.soilPhMax != null) {
            InfoRow("pH range", "${lib.soilPhMin ?: "?"} – ${lib.soilPhMax ?: "?"}")
        }
    }
}
