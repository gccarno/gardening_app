package com.gardenapp.feature.library.detail.tabs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.LibraryEntry
import kotlinx.serialization.json.*

// ── Shared helpers ────────────────────────────────────────────────────────────

@Composable
private fun SectionTitle(title: String) {
    Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun EmptyState(text: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium)
    }
}

// ── Overview Tab ──────────────────────────────────────────────────────────────

@Composable
fun LibraryOverviewTab(entry: LibraryEntry) {
    Column(
        modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        entry.scientificName?.let {
            Text(it, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        SectionTitle("Growing Info")
        InfoRow("Type", entry.type?.replaceFirstChar(Char::uppercase) ?: "—")
        InfoRow("Sunlight", entry.sunlight ?: "—")
        InfoRow("Water", entry.water ?: "—")
        InfoRow("Spacing", entry.spacingIn?.let { "${it.toInt()} in" } ?: "—")
        InfoRow("Days to germination", entry.daysToGermination?.toString() ?: "—")
        InfoRow("Days to harvest", entry.daysToHarvest?.toString() ?: "—")
        InfoRow("Difficulty", entry.difficulty?.replaceFirstChar(Char::uppercase) ?: "—")

        if (entry.minZone != null || entry.maxZone != null) {
            HorizontalDivider()
            SectionTitle("Climate")
            InfoRow("USDA Zones", "${entry.minZone ?: "?"} – ${entry.maxZone ?: "?"}")
            if (entry.tempMinF != null && entry.tempMaxF != null) {
                InfoRow("Temp range", "${entry.tempMinF.toInt()}°F – ${entry.tempMaxF.toInt()}°F")
            }
        }

        entry.family?.let {
            HorizontalDivider()
            SectionTitle("Taxonomy")
            InfoRow("Family", it)
            entry.layer?.let { l -> InfoRow("Layer", l) }
            entry.edibleParts?.let { e -> InfoRow("Edible parts", e) }
        }

        entry.permapeopleDescription?.let {
            HorizontalDivider()
            Text(it, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ── Seasons Tab ───────────────────────────────────────────────────────────────

@Composable
fun LibrarySeasonsTab(entry: LibraryEntry) {
    if (entry.bloomMonths == null && entry.fruitMonths == null && entry.growthMonths == null) {
        EmptyState("No seasonal data available")
        return
    }
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionTitle("Seasonal Activity")
        entry.growthMonths?.let { InfoRow("Growth months", it) }
        entry.bloomMonths?.let { InfoRow("Bloom months", it) }
        entry.fruitMonths?.let { InfoRow("Fruit months", it) }
    }
}

// ── Companions Tab ────────────────────────────────────────────────────────────

@Composable
fun LibraryCompanionsTab(entry: LibraryEntry) {
    val good = entry.goodNeighbors
    val bad = entry.badNeighbors
    if (good.isEmpty() && bad.isEmpty()) { EmptyState("No companion data"); return }

    LazyColumn(modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (good.isNotEmpty()) {
            item { Text("Good Neighbors", style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary) }
            items(good) { name ->
                Surface(shape = MaterialTheme.shapes.small,
                    color = MaterialTheme.colorScheme.primaryContainer,
                    modifier = Modifier.fillMaxWidth()) {
                    Text(name, modifier = Modifier.padding(10.dp),
                        style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        if (bad.isNotEmpty()) {
            item { Spacer(Modifier.height(8.dp)) }
            item { Text("Bad Neighbors", style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.error) }
            items(bad) { name ->
                Surface(shape = MaterialTheme.shapes.small,
                    color = MaterialTheme.colorScheme.errorContainer,
                    modifier = Modifier.fillMaxWidth()) {
                    Text(name, modifier = Modifier.padding(10.dp),
                        style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

// ── Soil Tab ──────────────────────────────────────────────────────────────────

@Composable
fun LibrarySoilTab(entry: LibraryEntry) {
    if (entry.soilType == null && entry.soilPhMin == null) { EmptyState("No soil data"); return }
    Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Soil Requirements")
        entry.soilType?.let { InfoRow("Soil type", it) }
        if (entry.soilPhMin != null || entry.soilPhMax != null) {
            InfoRow("pH range", "${entry.soilPhMin ?: "?"} – ${entry.soilPhMax ?: "?"}")
        }
    }
}

// ── How to Grow Tab ───────────────────────────────────────────────────────────

@Composable
fun LibraryHowToGrowTab(entry: LibraryEntry) {
    val howToGrow = entry.howToGrow
    if (howToGrow == null) { EmptyState("No growing guide available"); return }

    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        renderJsonElement(howToGrow)
    }
}

@Composable
private fun renderJsonElement(element: JsonElement) {
    when (element) {
        is JsonObject -> element.entries.forEach { (key, value) ->
            Text(key.replace("_", " ").replaceFirstChar(Char::uppercase),
                style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            renderJsonElement(value)
            Spacer(Modifier.height(4.dp))
        }
        is JsonArray -> element.forEach { item ->
            when (item) {
                is JsonPrimitive -> Text("• ${item.content}", style = MaterialTheme.typography.bodyMedium)
                else -> renderJsonElement(item)
            }
        }
        is JsonPrimitive -> Text(element.content, style = MaterialTheme.typography.bodyMedium)
        else -> {}
    }
}

// ── Nutrition Tab ─────────────────────────────────────────────────────────────

@Composable
fun LibraryNutritionTab(entry: LibraryEntry) {
    val nutrition = entry.nutrition
    if (nutrition == null) { EmptyState("No nutrition data"); return }
    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle("Nutritional Info")
        when (nutrition) {
            is JsonObject -> nutrition.entries.forEach { (k, v) ->
                InfoRow(k.replace("_", " ").replaceFirstChar(Char::uppercase),
                    (v as? JsonPrimitive)?.content ?: v.toString())
            }
            is JsonPrimitive -> Text(nutrition.content, style = MaterialTheme.typography.bodyMedium)
            else -> Text(nutrition.toString(), style = MaterialTheme.typography.bodySmall)
        }
    }
}

// ── FAQs Tab ──────────────────────────────────────────────────────────────────

@Composable
fun LibraryFaqsTab(entry: LibraryEntry) {
    val faqs = entry.faqs
    if (faqs == null) { EmptyState("No FAQs available"); return }

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

    if (entries.isEmpty()) { EmptyState("No FAQs available"); return }

    LazyColumn(modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        itemsIndexed(entries) { _, (q, a) ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(q, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                    if (a.isNotBlank()) Text(a, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
