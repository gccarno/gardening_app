package com.gardenapp.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navDeepLink
import com.gardenapp.feature.dashboard.DashboardScreen
import com.gardenapp.feature.bed.detail.BedDetailScreen
import com.gardenapp.feature.bed.form.BedFormScreen
import com.gardenapp.feature.bed.list.BedListScreen
import com.gardenapp.feature.garden.detail.GardenDetailScreen
import com.gardenapp.feature.garden.form.GardenFormScreen
import com.gardenapp.feature.garden.list.GardenListScreen
import com.gardenapp.feature.library.browser.LibraryBrowserScreen
import com.gardenapp.feature.library.detail.LibraryDetailScreen
import com.gardenapp.feature.library.diff.PlantDiffScreen
import com.gardenapp.feature.plant.detail.PlantDetailScreen
import com.gardenapp.feature.plant.form.PlantFormScreen
import com.gardenapp.feature.plant.list.PlantListScreen
import com.gardenapp.feature.settings.SettingsScreen
import com.gardenapp.feature.task.form.TaskFormScreen
import com.gardenapp.feature.canvas.CanvasPlannerScreen
import com.gardenapp.feature.identify.IdentifyScreen
import com.gardenapp.feature.task.list.TaskListScreen
import com.gardenapp.feature.journal.JournalScreen
import com.gardenapp.feature.seedroom.SeedRoomScreen
import com.gardenapp.feature.compost.CompostScreen

private data class BottomNavItem(
    val screen: Screen,
    val label: String,
    val icon: ImageVector,
)

private val bottomNavItems = listOf(
    BottomNavItem(Screen.Dashboard, "Dashboard", Icons.Default.Dashboard),
    BottomNavItem(Screen.Gardens, "Gardens", Icons.Default.LocalFlorist),
    BottomNavItem(Screen.Plants, "Plants", Icons.Default.Spa),
    BottomNavItem(Screen.Tasks, "Tasks", Icons.Default.CheckCircle),
    BottomNavItem(Screen.Library, "Library", Icons.Default.MenuBook),
)

private val bottomNavRoutes = bottomNavItems.map { it.screen.route }.toSet()

@Composable
fun GardenNavGraph() {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val showBottomBar = bottomNavRoutes.any { route ->
        navBackStackEntry?.destination?.hierarchy?.any { it.route == route } == true
    }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    bottomNavItems.forEach { item ->
                        NavigationBarItem(
                            icon = { Icon(item.icon, contentDescription = item.label) },
                            label = { Text(item.label) },
                            selected = navBackStackEntry?.destination?.hierarchy?.any {
                                it.route == item.screen.route
                            } == true,
                            onClick = {
                                navController.navigate(item.screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Dashboard.route,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Screen.Dashboard.route) {
                DashboardScreen(
                    onNavigateToSettings = { navController.navigate(Screen.Settings.route) },
                    onNavigateToGarden = { id -> navController.navigate(Screen.GardenDetail.route(id)) },
                    onNavigateToIdentify = { navController.navigate(Screen.Identify.route) },
                )
            }
            composable(Screen.Identify.route) {
                IdentifyScreen(
                    onOpenLibraryEntry = { id -> navController.navigate(Screen.LibraryDetail.route(id)) },
                )
            }
            composable(Screen.Gardens.route) {
                GardenListScreen(
                    onOpenGarden = { id -> navController.navigate(Screen.GardenDetail.route(id)) },
                    onCreateGarden = { navController.navigate(Screen.GardenForm.route()) },
                )
            }
            composable(Screen.Plants.route) {
                PlantListScreen(
                    onNavigateToDetail = { id -> navController.navigate(Screen.PlantDetail.route(id)) },
                    onNavigateToCreate = { navController.navigate(Screen.PlantForm.route()) },
                )
            }
            composable(Screen.Tasks.route) {
                TaskListScreen(
                    onNavigateToCreate = { navController.navigate(Screen.TaskForm.route()) },
                    onNavigateToDetail = { id -> navController.navigate(Screen.TaskForm.route(id)) },
                )
            }
            composable(Screen.Library.route) {
                LibraryBrowserScreen(
                    onNavigateToDetail = { id -> navController.navigate(Screen.LibraryDetail.route(id)) },
                    onNavigateToDiff = { aId, bId -> navController.navigate(Screen.PlantDiff.route(aId, bId)) },
                )
            }
            composable(Screen.Settings.route) {
                SettingsScreen(onBack = { navController.popBackStack() })
            }
            composable(
                Screen.GardenDetail.route,
                deepLinks = listOf(navDeepLink { uriPattern = "gardenapp://garden/{gardenId}" }),
            ) {
                GardenDetailScreen(
                    onBack = { navController.popBackStack() },
                    onEdit = { id -> navController.navigate(Screen.GardenForm.route(id)) },
                    onOpenPlanner = { id -> navController.navigate(Screen.CanvasPlanner.route(id)) },
                    onOpenBeds = { id -> navController.navigate(Screen.BedList.route(id)) },
                    onOpenJournal = { id -> navController.navigate(Screen.Journal.route(id)) },
                    onOpenSeedRoom = { id -> navController.navigate(Screen.SeedRoom.route(id)) },
                    onOpenCompost = { id -> navController.navigate(Screen.Compost.route(id)) },
                )
            }
            composable(Screen.Journal.route) {
                JournalScreen(onBack = { navController.popBackStack() })
            }
            composable(Screen.SeedRoom.route) {
                SeedRoomScreen(onBack = { navController.popBackStack() })
            }
            composable(Screen.Compost.route) {
                CompostScreen(onBack = { navController.popBackStack() })
            }
            composable(Screen.GardenForm.route) {
                GardenFormScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { id ->
                        navController.navigate(Screen.GardenDetail.route(id)) {
                            popUpTo(Screen.GardenForm.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.CanvasPlanner.route) {
                CanvasPlannerScreen(onBack = { navController.popBackStack() })
            }
            composable(Screen.BedList.route) {
                BedListScreen(
                    onBack = { navController.popBackStack() },
                    onOpenBed = { id -> navController.navigate(Screen.BedDetail.route(id)) },
                    onCreateBed = { gardenId -> navController.navigate(Screen.BedForm.route(gardenId = gardenId)) },
                )
            }
            composable(
                Screen.BedDetail.route,
                deepLinks = listOf(navDeepLink { uriPattern = "gardenapp://bed/{bedId}/grid" }),
            ) {
                BedDetailScreen(
                    onBack = { navController.popBackStack() },
                    onEdit = { id -> navController.navigate(Screen.BedForm.route(bedId = id)) },
                )
            }
            composable(Screen.BedForm.route) {
                BedFormScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { id ->
                        navController.navigate(Screen.BedDetail.route(id)) {
                            popUpTo(Screen.BedForm.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.PlantDetail.route) {
                PlantDetailScreen(
                    onBack = { navController.popBackStack() },
                    onEdit = { id -> navController.navigate(Screen.PlantForm.route(id)) },
                )
            }
            composable(Screen.PlantForm.route) {
                PlantFormScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { id ->
                        navController.navigate(Screen.PlantDetail.route(id)) {
                            popUpTo(Screen.PlantForm.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.TaskDetail.route) {
                TaskFormScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { navController.popBackStack() },
                )
            }
            composable(Screen.TaskForm.route) {
                TaskFormScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { navController.popBackStack() },
                )
            }
            composable(Screen.LibraryDetail.route) {
                LibraryDetailScreen(
                    onBack = { navController.popBackStack() },
                    onNavigateToPlant = { id -> navController.navigate(Screen.PlantDetail.route(id)) },
                )
            }
            composable(Screen.PlantDiff.route) {
                PlantDiffScreen(onBack = { navController.popBackStack() })
            }
        }
    }
}

@Composable
private fun SessionStub(title: String, emoji: String, session: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(emoji, style = MaterialTheme.typography.displayMedium)
            Text(title, style = MaterialTheme.typography.headlineMedium)
            Text("Coming in $session", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
