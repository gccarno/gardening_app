package com.gardenapp.feature.garden.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun BulkCareButtons(
    onWaterAll: () -> Unit,
    onFertilizeAll: () -> Unit,
    onMulchAll: () -> Unit,
    isLoading: Boolean = false,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Bulk Care", style = MaterialTheme.typography.titleSmall)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = onWaterAll,
                    enabled = !isLoading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("💧 Water All")
                }
                OutlinedButton(
                    onClick = onFertilizeAll,
                    enabled = !isLoading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("🪴 Fertilize")
                }
                OutlinedButton(
                    onClick = onMulchAll,
                    enabled = !isLoading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("🍂 Mulch")
                }
            }
            if (isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
        }
    }
}
