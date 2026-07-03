package com.gardenapp.feature.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.savedMessage) {
        uiState.savedMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearSavedMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
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
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Server Configuration", style = MaterialTheme.typography.titleMedium)

            OutlinedTextField(
                value = uiState.serverUrl,
                onValueChange = { viewModel.updateUrl(it) },
                label = { Text("Server URL") },
                placeholder = { Text("http://192.168.1.x:8000") },
                supportingText = {
                    Text("Enter the IP address of your backend server.\nEmulator default: http://10.0.2.2:8000")
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = { viewModel.saveUrl() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Save & Apply")
            }

            HorizontalDivider()

            Text("Account", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(
                onClick = { viewModel.signOut() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Sign out")
            }

            HorizontalDivider()

            Text("About", style = MaterialTheme.typography.titleMedium)
            Text(
                "Garden Planner connects to your local FastAPI backend. " +
                    "Make sure the backend is running and accessible on your network.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
