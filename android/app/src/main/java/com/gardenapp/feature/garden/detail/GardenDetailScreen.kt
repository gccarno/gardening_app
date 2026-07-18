package com.gardenapp.feature.garden.detail

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Grass
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Recycling
import androidx.compose.material.icons.filled.Eco
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gardenapp.feature.dashboard.components.WeatherWidget
import com.gardenapp.feature.garden.detail.components.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GardenDetailScreen(
    onBack: () -> Unit,
    onEdit: (Int) -> Unit,
    onOpenPlanner: (Int) -> Unit,
    onOpenBeds: (Int) -> Unit,
    onOpenJournal: (Int) -> Unit,
    onOpenSeedRoom: (Int) -> Unit,
    onOpenCompost: (Int) -> Unit,
    onOpenNotifications: (Int) -> Unit,
    viewModel: GardenDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let { snackbarHostState.showSnackbar(it); viewModel.dismissError() }
    }
    LaunchedEffect(uiState.bulkCareMessage) {
        uiState.bulkCareMessage?.let { snackbarHostState.showSnackbar(it); viewModel.dismissBulkCareMessage() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.garden?.name ?: "Garden", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                    }
                },
                actions = {
                    uiState.garden?.let { garden ->
                        IconButton(onClick = { onOpenPlanner(garden.id) }) {
                            Icon(Icons.Default.Map, "Open Planner")
                        }
                        IconButton(onClick = { onOpenNotifications(garden.id) }) {
                            Icon(Icons.Default.Notifications, "Notification Settings")
                        }
                        IconButton(onClick = { onEdit(garden.id) }) {
                            Icon(Icons.Default.Edit, "Edit")
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        Box(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            when {
                uiState.isLoading && uiState.garden == null -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                uiState.garden != null -> {
                    val garden = uiState.garden!!
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        // Frost context banner
                        FrostContextBanner(garden = garden)

                        // Garden info
                        GardenInfoCard(garden = garden)

                        // Beds navigation
                        OutlinedButton(
                            onClick = { onOpenBeds(garden.id) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.Grass, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("View Beds")
                        }

                        // Journal navigation
                        OutlinedButton(
                            onClick = { onOpenJournal(garden.id) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.MenuBook, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Garden Journal")
                        }

                        // Seed Room navigation
                        OutlinedButton(
                            onClick = { onOpenSeedRoom(garden.id) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.Eco, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Seed Room")
                        }

                        // Compost navigation
                        OutlinedButton(
                            onClick = { onOpenCompost(garden.id) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.Recycling, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Compost Helper")
                        }

                        // Bulk care
                        BulkCareButtons(
                            onWaterAll = { viewModel.bulkCare("water") },
                            onFertilizeAll = { viewModel.bulkCare("fertilize") },
                            onMulchAll = { viewModel.bulkCare("mulch") },
                            isLoading = uiState.isBulkCaring,
                        )

                        // Weather
                        uiState.weather?.let { weather ->
                            Text(
                                "Weather",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            WeatherWidget(weather = weather)
                        } ?: run {
                            if (!uiState.isLoading) {
                                OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                                    Box(
                                        modifier = Modifier.fillMaxWidth().padding(24.dp),
                                        contentAlignment = Alignment.Center,
                                    ) {
                                        Text(
                                            "Weather unavailable — add a ZIP code to enable forecasts",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }

                        Spacer(Modifier.height(16.dp))
                    }
                }
                else -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("Garden not found", style = MaterialTheme.typography.titleMedium)
                        Button(onClick = onBack) { Text("Go Back") }
                    }
                }
            }
        }
    }
}
