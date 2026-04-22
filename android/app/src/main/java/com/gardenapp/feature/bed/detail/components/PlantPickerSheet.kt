package com.gardenapp.feature.bed.detail.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gardenapp.core.model.LibraryListEntry

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlantPickerSheet(
    query: String,
    results: List<LibraryListEntry>,
    isLoading: Boolean,
    onQueryChange: (String) -> Unit,
    onSelect: (LibraryListEntry) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
            Text(
                "Choose a Plant",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 12.dp),
            )

            OutlinedTextField(
                value = query,
                onValueChange = onQueryChange,
                placeholder = { Text("Search plants…") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(8.dp))

            when {
                isLoading -> Box(
                    modifier = Modifier.fillMaxWidth().height(120.dp),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }

                results.isEmpty() && query.isNotBlank() -> Box(
                    modifier = Modifier.fillMaxWidth().height(80.dp),
                    contentAlignment = Alignment.Center,
                ) { Text("No results for \"$query\"", color = MaterialTheme.colorScheme.onSurfaceVariant) }

                else -> LazyColumn(
                    modifier = Modifier.heightIn(max = 400.dp),
                    contentPadding = PaddingValues(bottom = 32.dp),
                ) {
                    items(results, key = { it.id }) { entry ->
                        ListItem(
                            headlineContent = { Text(entry.name, fontWeight = FontWeight.Medium) },
                            supportingContent = {
                                val details = listOfNotNull(
                                    entry.type?.replaceFirstChar(Char::uppercase),
                                    entry.spacingIn?.let { "${it.toInt()}in spacing" },
                                    entry.daysToHarvest?.let { "${it}d to harvest" },
                                ).joinToString(" · ")
                                if (details.isNotEmpty()) Text(details)
                            },
                            trailingContent = {
                                entry.difficulty?.let {
                                    Badge(containerColor = difficultyColor(it)) { Text(it) }
                                }
                            },
                            modifier = Modifier.clickable { onSelect(entry) },
                        )
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun difficultyColor(difficulty: String): androidx.compose.ui.graphics.Color = when (difficulty.lowercase()) {
    "easy" -> MaterialTheme.colorScheme.primaryContainer
    "medium" -> MaterialTheme.colorScheme.secondaryContainer
    "hard" -> MaterialTheme.colorScheme.errorContainer
    else -> MaterialTheme.colorScheme.surfaceVariant
}
