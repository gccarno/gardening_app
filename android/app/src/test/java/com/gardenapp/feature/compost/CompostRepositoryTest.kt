package com.gardenapp.feature.compost

import com.gardenapp.core.model.CompostBin
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class CompostRepositoryTest {

    private val api = mockk<ApiService>()
    private val repository = CompostRepository(api)

    private fun bin(id: Int = 1) = CompostBin(
        id = id, gardenId = 3, name = "Main bin", stage = "building",
        createdAt = "2026-06-01T12:00:00",
    )

    @Test
    fun `getBins returns success`() = runTest {
        coEvery { api.getCompostBins(3) } returns listOf(bin())
        val result = repository.getBins(3)
        assertTrue(result is NetworkResult.Success)
        assertEquals("Main bin", (result as NetworkResult.Success).data[0].name)
    }

    @Test
    fun `http errors keep their status code`() = runTest {
        val error = HttpException(Response.error<Any>(
            404, "not found".toResponseBody("text/plain".toMediaType())))
        coEvery { api.getCompostBins(3) } throws error
        val result = repository.getBins(3)
        assertTrue(result is NetworkResult.Error)
        assertEquals(404, (result as NetworkResult.Error).code)
    }

    @Test
    fun `network failures map to error without code`() = runTest {
        coEvery { api.getCompostBins(3) } throws java.io.IOException("timeout")
        val result = repository.getBins(3)
        assertTrue(result is NetworkResult.Error)
        assertEquals(null, (result as NetworkResult.Error).code)
    }

    @Test
    fun `createBin posts name and optional date`() = runTest {
        coEvery { api.createCompostBin(3, mapOf("name" to "New bin")) } returns bin(2)
        val result = repository.createBin(3, "New bin", null)
        assertTrue(result is NetworkResult.Success)
        assertEquals(2, (result as NetworkResult.Success).data.id)
    }
}
