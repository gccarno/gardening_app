package com.gardenapp.feature.bed.detail

import androidx.lifecycle.SavedStateHandle
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedGridResponse
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.MoistureCheckin
import com.gardenapp.core.model.RotationWarnings
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.util.DateUtil
import com.gardenapp.feature.bed.BedRepository
import java.time.LocalDate
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class BedDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: BedRepository

    private val bed = Bed(id = 7, name = "Test Bed", widthFt = 4f, heightFt = 4f)

    /** A 24in plant at the origin covers cells (0,0),(1,0),(0,1),(1,1). */
    private val wideePlant = GridPlant(
        id = 42, gridX = 0, gridY = 0, plantId = 5,
        plantName = "Zucchini", spacingIn = 24f,
    )

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = mockk(relaxed = true)
        // relaxed mockk would hand back a dummy for this nullable read, not null
        coEvery { repository.cachedBedGrid(any()) } returns null
        coEvery { repository.refreshBedGrid(eq(7), any()) } returns
            NetworkResult.Success(
                Cached(BedGridResponse(bed = bed, placed = listOf(wideePlant)), 1_000L)
            )
        coEvery { repository.getRotationWarnings(any(), any()) } returns
            NetworkResult.Success(RotationWarnings(bedId = 7))
        coEvery { repository.getMoistureCheckins(any()) } returns NetworkResult.Success(emptyList())
        coEvery { repository.getBedPlant(42) } returns NetworkResult.Success(
            BedPlantDetail(id = 42, plantId = 5, plantName = "Zucchini", spacingIn = 24f),
        )
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun viewModel() =
        BedDetailViewModel(repository, SavedStateHandle(mapOf("bedId" to "7")))

    @Test
    fun `tapping a non-origin cell of a wide plant opens the care sheet`() = runTest(dispatcher) {
        val vm = viewModel()
        advanceUntilIdle()

        // Cell (1,0) — inside the zucchini's 2x2 footprint but not its origin.
        vm.onCellTap(12, 0)
        advanceUntilIdle()

        val state = vm.uiState.value
        assertNull("should not offer to plant on an occupied cell", state.showPickerForCell)
        assertNotNull("care sheet should open for the covering plant", state.careSheetPlant)
        assertEquals(42, state.careSheetPlant?.id)
    }

    @Test
    fun `tapping a genuinely empty cell opens the plant picker`() = runTest(dispatcher) {
        val vm = viewModel()
        advanceUntilIdle()

        // Cell (2,0) — outside the 2x2 footprint.
        vm.onCellTap(24, 0)
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(Pair(24, 0), state.showPickerForCell)
        assertNull(state.careSheetPlant)
    }

    @Test
    fun `long press on a non-origin cell targets the covering plant for removal`() =
        runTest(dispatcher) {
            val vm = viewModel()
            advanceUntilIdle()

            vm.onCellLongPress(12, 12)
            advanceUntilIdle()

            assertEquals(42, vm.uiState.value.pendingRemoval?.id)
        }

    @Test
    fun `a failed removal keeps the plant on the grid and reports the error`() =
        runTest(dispatcher) {
            coEvery { repository.removePlant(42) } returns NetworkResult.Error("boom")
            val vm = viewModel()
            advanceUntilIdle()

            vm.onCellLongPress(0, 0)
            vm.confirmRemoval()
            advanceUntilIdle()

            val state = vm.uiState.value
            assertTrue("plant must stay until the server confirms", state.placed.any { it.id == 42 })
            assertEquals("boom", state.error)
        }

    @Test
    fun `a successful removal drops the plant from the grid`() = runTest(dispatcher) {
        coEvery { repository.removePlant(42) } returns NetworkResult.Success(Unit)
        val vm = viewModel()
        advanceUntilIdle()

        vm.onCellLongPress(0, 0)
        vm.confirmRemoval()
        advanceUntilIdle()

        assertTrue(vm.uiState.value.placed.none { it.id == 42 })
    }

    @Test
    fun `the cached grid is on screen before the network answers`() = runTest(dispatcher) {
        coEvery { repository.cachedBedGrid(7) } returns
            Cached(BedGridResponse(bed = bed, placed = listOf(wideePlant)), 1_000L)
        coEvery { repository.refreshBedGrid(any(), any()) } coAnswers { awaitCancellation() }

        val vm = viewModel()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals("Test Bed", state.bed?.name)
        assertEquals(1, state.placed.size)
        assertEquals(1_000L, state.gridFetchedAt)
    }

    @Test
    fun `a failed refresh keeps the cached grid instead of emptying it`() = runTest(dispatcher) {
        coEvery { repository.cachedBedGrid(7) } returns
            Cached(BedGridResponse(bed = bed, placed = listOf(wideePlant)), 1_000L)
        coEvery { repository.refreshBedGrid(any(), any()) } returns NetworkResult.Error("offline")

        val vm = viewModel()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals("cached plants must survive a failed refresh", 1, state.placed.size)
        assertTrue(state.refreshFailed)
        assertNull("with a grid on screen the failure belongs in the status line", state.error)
    }

    @Test
    fun `a removal is written through to the cache`() = runTest(dispatcher) {
        coEvery { repository.removePlant(42) } returns NetworkResult.Success(Unit)
        val vm = viewModel()
        advanceUntilIdle()

        vm.onCellLongPress(0, 0)
        vm.confirmRemoval()
        advanceUntilIdle()

        // Otherwise leaving and returning inside the TTL resurrects the plant.
        coVerify { repository.cacheBedGrid(7, match { it.placed.none { p -> p.id == 42 } }) }
    }

    // ── Soil moisture check-ins ──────────────────────────────────────────────

    private val today = DateUtil.formatDate(LocalDate.now())

    private fun checkin(id: Int, date: String, level: String) =
        MoistureCheckin(id = id, bedId = 7, checkDate = date, level = level)

    @Test
    fun `existing check-ins are loaded with the grid`() = runTest(dispatcher) {
        coEvery { repository.getMoistureCheckins(7) } returns
            NetworkResult.Success(listOf(checkin(1, "2026-10-01", "dry")))
        val vm = viewModel()
        advanceUntilIdle()

        assertEquals(listOf("dry"), vm.uiState.value.moistureCheckins.map { it.level })
    }

    @Test
    fun `saving sends the local date and shows the new reading first`() = runTest(dispatcher) {
        coEvery { repository.getMoistureCheckins(7) } returns
            NetworkResult.Success(listOf(checkin(1, "2020-01-01", "ok")))
        coEvery { repository.saveMoistureCheckin(7, "dry", today) } returns
            NetworkResult.Success(checkin(2, today, "dry"))
        val vm = viewModel()
        advanceUntilIdle()

        vm.saveMoisture("dry")
        advanceUntilIdle()

        coVerify { repository.saveMoistureCheckin(7, "dry", today) }
        assertEquals(listOf("dry", "ok"), vm.uiState.value.moistureCheckins.map { it.level })
        assertEquals(false, vm.uiState.value.isSavingMoisture)
    }

    @Test
    fun `a second reading the same day replaces the first`() = runTest(dispatcher) {
        coEvery { repository.getMoistureCheckins(7) } returns
            NetworkResult.Success(listOf(checkin(1, today, "dry")))
        coEvery { repository.saveMoistureCheckin(7, "wet", today) } returns
            NetworkResult.Success(checkin(1, today, "wet"))
        val vm = viewModel()
        advanceUntilIdle()

        vm.saveMoisture("wet")
        advanceUntilIdle()

        assertEquals(listOf("wet"), vm.uiState.value.moistureCheckins.map { it.level })
    }

    @Test
    fun `a failed save keeps the old readings and reports the error`() = runTest(dispatcher) {
        coEvery { repository.getMoistureCheckins(7) } returns
            NetworkResult.Success(listOf(checkin(1, today, "ok")))
        coEvery { repository.saveMoistureCheckin(7, "dry", today) } returns
            NetworkResult.Error("server down")
        val vm = viewModel()
        advanceUntilIdle()

        vm.saveMoisture("dry")
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(listOf("ok"), state.moistureCheckins.map { it.level })
        assertTrue(state.error!!.contains("server down"))
        assertEquals(false, state.isSavingMoisture)
    }

    @Test
    fun `a tap while a save is in flight is ignored`() = runTest(dispatcher) {
        coEvery { repository.getMoistureCheckins(7) } returns NetworkResult.Success(emptyList())
        coEvery { repository.saveMoistureCheckin(7, any(), any()) } returns
            NetworkResult.Success(checkin(2, today, "dry"))
        val vm = viewModel()
        advanceUntilIdle()

        vm.saveMoisture("dry")
        vm.saveMoisture("wet")   // dispatcher has not run the first save yet
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.saveMoistureCheckin(7, any(), any()) }
    }
}
