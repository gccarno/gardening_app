package com.gardenapp.feature.bed.detail

import androidx.lifecycle.SavedStateHandle
import com.gardenapp.core.model.Bed
import com.gardenapp.core.model.BedGridResponse
import com.gardenapp.core.model.BedPlantDetail
import com.gardenapp.core.model.GridPlant
import com.gardenapp.core.model.RotationWarnings
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.bed.BedRepository
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
        coEvery { repository.getBedGrid(7) } returns
            NetworkResult.Success(BedGridResponse(bed = bed, placed = listOf(wideePlant)))
        coEvery { repository.getRotationWarnings(any(), any()) } returns
            NetworkResult.Success(RotationWarnings(bedId = 7))
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
}
