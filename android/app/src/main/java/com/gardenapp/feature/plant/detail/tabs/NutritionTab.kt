package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail
import kotlinx.serialization.json.*

@Composable
fun NutritionTab(plant: PlantDetail) {
    val nutrition = plant.library?.nutrition

    if (nutrition == null) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No nutrition data available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        SectionTitle("Nutritional Info")
        when (nutrition) {
            is JsonObject -> {
                nutrition.entries.forEach { (key, value) ->
                    InfoRow(
                        key.replace("_", " ").replaceFirstChar(Char::uppercase),
                        (value as? JsonPrimitive)?.content ?: value.toString(),
                    )
                }
            }
            is JsonPrimitive -> Text(nutrition.content, style = MaterialTheme.typography.bodyMedium)
            else -> Text(nutrition.toString(), style = MaterialTheme.typography.bodySmall)
        }
    }
}
