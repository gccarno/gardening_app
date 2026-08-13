package com.gardenapp.feature.plant.detail

import androidx.lifecycle.SavedStateHandle
import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.model.Plant
import com.gardenapp.core.model.PlantDetail
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.feature.plant.PlantRepository
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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class PlantDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: PlantRepository

    private val cached = PlantDetail(id = 4, name = "Tomato", status = "growing")
    private val fresh = PlantDetail(id = 4, name = "Tomato", status = "harvested")

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = mockk(relaxed = true)
        coEvery { repository.cachedDetail(any()) } returns null
        coEvery { repository.refreshDetail(any(), any()) } returns
            NetworkResult.Success(Cached(fresh, 5_000L))
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun viewModel() =
        PlantDetailViewModel(SavedStateHandle(mapOf("plantId" to 4)), repository)

    @Test
    fun `the cached plant is on screen before the network answers`() = runTest(dispatcher) {
        coEvery { repository.cachedDetail(4) } returns Cached(cached, 1_000L)
        coEvery { repository.refreshDetail(any(), any()) } coAnswers { awaitCancellation() }

        val vm = viewModel()
        advanceUntilIdle()

        assertEquals("growing", vm.uiState.value.plant?.status)
        assertEquals(1_000L, vm.uiState.value.fetchedAt)
    }

    @Test
    fun `a failed refresh keeps the cached plant instead of blanking it`() = runTest(dispatcher) {
        coEvery { repository.cachedDetail(4) } returns Cached(cached, 1_000L)
        coEvery { repository.refreshDetail(any(), any()) } returns NetworkResult.Error("offline")

        val vm = viewModel()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals("growing", state.plant?.status)
        assertTrue(state.refreshFailed)
        assertNull("with content on screen the failure belongs in the status line", state.error)
    }

    @Test
    fun `a failed refresh with nothing cached reports the error`() = runTest(dispatcher) {
        coEvery { repository.refreshDetail(any(), any()) } returns NetworkResult.Error("offline")

        val vm = viewModel()
        advanceUntilIdle()

        assertNull(vm.uiState.value.plant)
        assertEquals("offline", vm.uiState.value.error)
    }

    @Test
    fun `opening the screen honours the TTL`() = runTest(dispatcher) {
        viewModel()
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.refreshDetail(4, false) }
    }

    @Test
    fun `changing status bypasses the TTL so the edit is never hidden`() = runTest(dispatcher) {
        coEvery { repository.setStatus(4, "harvested") } returns
            NetworkResult.Success(Plant(id = 4, name = "Tomato"))

        val vm = viewModel()
        advanceUntilIdle()

        vm.setStatus("harvested")
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.refreshDetail(4, true) }
        assertEquals("harvested", vm.uiState.value.plant?.status)
    }
}
