package com.gardenapp.feature.plant.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.PlantDetail
import kotlinx.serialization.json.*

@Composable
fun FaqsTab(plant: PlantDetail) {
    val faqs = plant.library?.faqs

    if (faqs == null) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No FAQs available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    val entries: List<Pair<String, String>> = remember(faqs) {
        when (faqs) {
            is JsonArray -> faqs.mapNotNull { item ->
                if (item is JsonObject) {
                    val q = item["question"]?.jsonPrimitive?.contentOrNull
                        ?: item["q"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                    val a = item["answer"]?.jsonPrimitive?.contentOrNull
                        ?: item["a"]?.jsonPrimitive?.contentOrNull ?: ""
                    q to a
                } else null
            }
            is JsonObject -> faqs.entries.map { (k, v) ->
                k to (v as? JsonPrimitive)?.content.orEmpty()
            }
            else -> emptyList()
        }
    }

    if (entries.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("No FAQs available", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        itemsIndexed(entries) { _, (q, a) ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(q, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                    if (a.isNotBlank()) {
                        Text(a, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
