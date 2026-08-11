package com.gardenapp.feature.dashboard

import com.gardenapp.core.database.entities.Cached
import com.gardenapp.core.model.DashboardData
import com.gardenapp.core.model.DashboardMetrics
import com.gardenapp.core.model.Garden
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DashboardViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: DashboardRepository
    private lateinit var api: ApiService

    private val garden = Garden(id = 3, name = "Backyard")
    private val cachedDash = DashboardData(metrics = DashboardMetrics(bedCount = 2), season = "Summer")
    private val freshDash = DashboardData(metrics = DashboardMetrics(bedCount = 9), season = "Summer")

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = mockk(relaxed = true)
        api = mockk(relaxed = true)

        every { repository.gardens } returns flowOf(listOf(garden))
        coEvery { repository.refreshGardens() } returns NetworkResult.Success(listOf(garden))
        coEvery { repository.cachedDefaultGardenId() } returns 3
        coEvery { repository.refreshDefaultGardenId() } returns 3
        coEvery { repository.cachedTipForToday() } returns null
        coEvery { repository.refreshTipOfDay() } returns "Water deeply"
        coEvery { repository.cachedDashboard(any()) } returns null
        coEvery { repository.refreshDashboard(any(), any()) } returns
            NetworkResult.Success(Cached(freshDash, 5_000L))
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun viewModel() = DashboardViewModel(repository, api)

    @Test
    fun `cached dashboard is on screen while the refresh is still in flight`() =
        runTest(dispatcher) {
            coEvery { repository.cachedDashboard(3) } returns Cached(cachedDash, 1_000L)
            coEvery { repository.refreshDashboard(any(), any()) } coAnswers { awaitCancellation() }

            val vm = viewModel()
            advanceUntilIdle()

            val state = vm.uiState.value
            assertEquals("cache must paint before the network answers", 2, state.dashboard?.metrics?.bedCount)
            assertEquals(1_000L, state.dashboardFetchedAt)
            assertTrue(state.isRefreshing)
        }

    @Test
    fun `a failed refresh keeps the cached dashboard instead of blanking it`() =
        runTest(dispatcher) {
            coEvery { repository.cachedDashboard(3) } returns Cached(cachedDash, 1_000L)
            coEvery { repository.refreshDashboard(any(), any()) } returns NetworkResult.Error("boom")

            val vm = viewModel()
            advanceUntilIdle()

            val state = vm.uiState.value
            assertEquals("cached content must survive a failed refresh", 2, state.dashboard?.metrics?.bedCount)
            assertEquals(1_000L, state.dashboardFetchedAt)
            assertTrue(state.refreshFailed)
            assertNull("with content on screen the failure belongs in the status line", state.error)
        }

    @Test
    fun `a failed refresh with nothing cached surfaces the error screen`() = runTest(dispatcher) {
        coEvery { repository.cachedDashboard(3) } returns null
        coEvery { repository.refreshDashboard(any(), any()) } returns NetworkResult.Error("boom")

        val vm = viewModel()
        advanceUntilIdle()

        assertNull(vm.uiState.value.dashboard)
        assertEquals("boom", vm.uiState.value.error)
    }

    @Test
    fun `a fresh refresh replaces the cached dashboard and its timestamp`() = runTest(dispatcher) {
        coEvery { repository.cachedDashboard(3) } returns Cached(cachedDash, 1_000L)

        val vm = viewModel()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(9, state.dashboard?.metrics?.bedCount)
        assertEquals(5_000L, state.dashboardFetchedAt)
        assertFalse(state.isRefreshing)
        assertFalse(state.refreshFailed)
        assertEquals("Water deeply", state.tipOfDay)
    }

    @Test
    fun `startup fetches the dashboard exactly once`() = runTest(dispatcher) {
        val vm = viewModel()
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.refreshDashboard(3, any()) }
        assertEquals(3, vm.uiState.value.selectedGardenId)
    }

    @Test
    fun `startup honours the TTL but the refresh button forces a fetch`() = runTest(dispatcher) {
        val vm = viewModel()
        advanceUntilIdle()
        coVerify(exactly = 1) { repository.refreshDashboard(3, false) }

        vm.refresh()
        advanceUntilIdle()
        coVerify(exactly = 1) { repository.refreshDashboard(3, true) }
    }

    @Test
    fun `the dashboard call does not wait on the default-garden call`() = runTest(dispatcher) {
        // A cached id means the dashboard request can go out immediately; if it were
        // still sequenced behind this call it would never be made.
        coEvery { repository.refreshDefaultGardenId() } coAnswers { awaitCancellation() }

        val vm = viewModel()
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.refreshDashboard(3, any()) }
        assertEquals(9, vm.uiState.value.dashboard?.metrics?.bedCount)
    }

    @Test
    fun `selecting a garden paints its cache and remembers it`() = runTest(dispatcher) {
        val vm = viewModel()
        advanceUntilIdle()

        coEvery { repository.cachedDashboard(8) } returns Cached(cachedDash, 2_000L)
        vm.selectGarden(8)
        advanceUntilIdle()

        assertEquals(8, vm.uiState.value.selectedGardenId)
        coVerify { repository.setDefaultGardenIdLocally(8) }
        coVerify { repository.refreshDashboard(8, any()) }
    }
}
