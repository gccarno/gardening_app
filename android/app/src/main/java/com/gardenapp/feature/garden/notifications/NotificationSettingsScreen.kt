package com.gardenapp.feature.garden.notifications

import android.Manifest
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.core.database.entities.NotificationSettingsEntity
import com.gardenapp.core.notifications.NotificationType

private val FREQUENCY_OPTIONS = listOf(1 to "Daily", 2 to "2 days", 3 to "3 days", 7 to "Weekly")
private val HOUR_OPTIONS = listOf(6, 8, 10, 12, 15, 18, 20)

private fun NotificationType.displayName() = when (this) {
    NotificationType.WATERING -> "Watering reminders"
    NotificationType.GROWTH -> "Growth tracking"
    NotificationType.PLANTING -> "Time-of-year planting"
}

private fun NotificationType.description() = when (this) {
    NotificationType.WATERING ->
        "Reminds you when beds need water. Skipped automatically when recent " +
            "rain means the plants are fine."
    NotificationType.GROWTH ->
        "Germination and harvest milestones based on planting dates."
    NotificationType.PLANTING ->
        "Seasonal suggestions for what to sow or transplant now."
}

private fun formatHour(hour: Int) = when {
    hour == 0 -> "12 AM"
    hour < 12 -> "$hour AM"
    hour == 12 -> "12 PM"
    else -> "${hour - 12} PM"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationSettingsScreen(
    onBack: () -> Unit,
    viewModel: NotificationSettingsViewModel = hiltViewModel(),
) {
    val settings by viewModel.settings.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    // API 33+: system notifications need the runtime POST_NOTIFICATIONS grant.
    var pendingEnable by remember { mutableStateOf<NotificationType?>(null) }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        pendingEnable?.let { type ->
            if (granted) viewModel.setEnabled(type, true)
            pendingEnable = null
        }
    }
    var showDeniedSnackbar by remember { mutableStateOf(false) }
    LaunchedEffect(showDeniedSnackbar) {
        if (showDeniedSnackbar) {
            snackbarHostState.showSnackbar(
                "Notification permission denied — enable it in system settings.")
            showDeniedSnackbar = false
        }
    }

    fun requestEnable(type: NotificationType) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            pendingEnable = type
            permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            viewModel.setEnabled(type, true)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Notifications", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                "Choose which reminders this garden sends and how often.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            NotificationType.entries.forEach { type ->
                settings[type]?.let { setting ->
                    NotificationTypeCard(
                        type = type,
                        setting = setting,
                        onToggle = { enabled ->
                            if (enabled) requestEnable(type)
                            else viewModel.setEnabled(type, false)
                        },
                        onFrequency = { viewModel.setFrequency(type, it) },
                        onHour = { viewModel.setHour(type, it) },
                    )
                }
            }
            val isDebuggable =
                context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
            if (isDebuggable) {
                OutlinedButton(
                    onClick = { viewModel.testNow() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("notif-test-now"),
                ) { Text("Test now (debug)") }
            }
        }
    }
}

@Composable
private fun NotificationTypeCard(
    type: NotificationType,
    setting: NotificationSettingsEntity,
    onToggle: (Boolean) -> Unit,
    onFrequency: (Int) -> Unit,
    onHour: (Int) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(type.displayName(), style = MaterialTheme.typography.titleMedium)
                    Text(
                        type.description(),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = setting.enabled,
                    onCheckedChange = onToggle,
                    modifier = Modifier.testTag("notif-switch-${type.name.lowercase()}"),
                )
            }
            if (setting.enabled) {
                Text("Frequency", style = MaterialTheme.typography.labelLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FREQUENCY_OPTIONS.forEach { (days, label) ->
                        FilterChip(
                            selected = setting.frequencyDays == days,
                            onClick = { onFrequency(days) },
                            label = { Text(label) },
                            modifier = Modifier.testTag(
                                "notif-freq-${type.name.lowercase()}-$days"),
                        )
                    }
                }
                HourDropdown(
                    type = type,
                    hourOfDay = setting.hourOfDay,
                    onHour = onHour,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HourDropdown(
    type: NotificationType,
    hourOfDay: Int,
    onHour: (Int) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = "After ${formatHour(hourOfDay)}",
            onValueChange = {},
            readOnly = true,
            label = { Text("Earliest time") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor()
                .testTag("notif-hour-${type.name.lowercase()}"),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            HOUR_OPTIONS.forEach { hour ->
                DropdownMenuItem(
                    text = { Text(formatHour(hour)) },
                    onClick = {
                        onHour(hour)
                        expanded = false
                    },
                )
            }
        }
    }
}
