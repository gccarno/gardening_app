package com.gardenapp.feature.garden.detail.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

/**
 * Shown in place of the weather widget when weather didn't load. A garden
 * with no coordinates gets a ZIP box (the backend geocodes on save); any
 * other failure shows the actual error and a retry button.
 */
@Composable
fun WeatherProblemCard(
    needsLocation: Boolean,
    error: String?,
    currentZip: String?,
    isSavingZip: Boolean,
    zipError: String?,
    onSaveZip: (String) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedCard(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (needsLocation) {
                var zip by rememberSaveable { mutableStateOf(currentZip.orEmpty()) }
                Text(
                    "Add a ZIP code to get forecasts for this garden",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = zip,
                        onValueChange = { zip = it.take(10) },
                        label = { Text("ZIP code") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        isError = zipError != null,
                        modifier = Modifier.weight(1f),
                    )
                    Button(
                        onClick = { onSaveZip(zip) },
                        enabled = zip.isNotBlank() && !isSavingZip,
                    ) {
                        if (isSavingZip) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                        } else {
                            Text("Save")
                        }
                    }
                }
                zipError?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
            } else {
                Text("Weather unavailable", style = MaterialTheme.typography.bodyMedium)
                Text(
                    error ?: "Unknown error",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
                TextButton(onClick = onRetry) { Text("Retry") }
            }
        }
    }
}
