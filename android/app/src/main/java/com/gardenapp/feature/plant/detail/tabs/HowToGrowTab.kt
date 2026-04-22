package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail
import kotlinx.serialization.json.*

@Composable
fun HowToGrowTab(plant: PlantDetail) {
    val howToGrow = plant.library?.howToGrow

    if (howToGrow == null) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No growing guide available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        renderJsonElement(howToGrow)
    }
}

@Composable
private fun renderJsonElement(element: JsonElement) {
    when (element) {
        is JsonObject -> {
            element.entries.forEach { (key, value) ->
                Text(
                    key.replace("_", " ").replaceFirstChar(Char::uppercase),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                renderJsonElement(value)
                Spacer(Modifier.height(4.dp))
            }
        }
        is JsonArray -> {
            element.forEach { item ->
                when (item) {
                    is JsonPrimitive -> Text("• ${item.content}", style = MaterialTheme.typography.bodyMedium)
                    else -> renderJsonElement(item)
                }
            }
        }
        is JsonPrimitive -> {
            Text(element.content, style = MaterialTheme.typography.bodyMedium)
        }
        else -> {}
    }
}
