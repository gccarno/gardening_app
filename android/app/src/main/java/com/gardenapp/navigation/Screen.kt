package com.gardenapp.navigation

sealed class Screen(val route: String) {
    // Bottom nav roots
    data object Dashboard : Screen("dashboard")
    data object Gardens : Screen("gardens")
    data object Plants : Screen("plants")
    data object Tasks : Screen("tasks")
    data object Library : Screen("library")

    // Garden stack
    data object GardenDetail : Screen("gardens/{gardenId}") {
        fun route(gardenId: Int) = "gardens/$gardenId"
    }
    data object GardenForm : Screen("gardens/form?gardenId={gardenId}") {
        fun route(gardenId: Int? = null) =
            if (gardenId != null) "gardens/form?gardenId=$gardenId" else "gardens/form"
    }
    data object CanvasPlanner : Screen("planner/{gardenId}") {
        fun route(gardenId: Int) = "planner/$gardenId"
    }

    // Bed stack
    data object BedList : Screen("beds?gardenId={gardenId}") {
        fun route(gardenId: Int) = "beds?gardenId=$gardenId"
    }
    data object BedDetail : Screen("beds/{bedId}") {
        fun route(bedId: Int) = "beds/$bedId"
    }
    data object BedForm : Screen("beds/form?bedId={bedId}&gardenId={gardenId}") {
        fun route(bedId: Int? = null, gardenId: Int? = null): String {
            val params = buildList {
                bedId?.let { add("bedId=$it") }
                gardenId?.let { add("gardenId=$it") }
            }.joinToString("&")
            return if (params.isEmpty()) "beds/form" else "beds/form?$params"
        }
    }

    // Plant stack
    data object PlantDetail : Screen("plants/{plantId}") {
        fun route(plantId: Int) = "plants/$plantId"
    }
    data object PlantForm : Screen("plants/form?plantId={plantId}") {
        fun route(plantId: Int? = null) =
            if (plantId != null) "plants/form?plantId=$plantId" else "plants/form"
    }

    // Task stack
    data object TaskDetail : Screen("tasks/{taskId}") {
        fun route(taskId: Int) = "tasks/$taskId"
    }
    data object TaskForm : Screen("tasks/form?taskId={taskId}") {
        fun route(taskId: Int? = null) =
            if (taskId != null) "tasks/form?taskId=$taskId" else "tasks/form"
    }

    // Library stack
    data object LibraryDetail : Screen("library/{entryId}") {
        fun route(entryId: Int) = "library/$entryId"
    }
    data object PlantDiff : Screen("library/diff?aId={aId}&bId={bId}") {
        fun route(aId: Int, bId: Int) = "library/diff?aId=$aId&bId=$bId"
    }

    // Settings
    data object Settings : Screen("settings")
}
