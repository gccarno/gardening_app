package com.gardenapp.feature.journal

import com.gardenapp.core.model.JournalEntry
import com.gardenapp.core.model.JournalPage
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import com.gardenapp.core.network.toNetworkError
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class JournalRepository @Inject constructor(
    private val api: ApiService,
) {
    suspend fun getJournal(gardenId: Int, page: Int): NetworkResult<JournalPage> = try {
        NetworkResult.Success(api.getJournal(gardenId, page))
    } catch (e: Exception) {
        e.toNetworkError("JournalRepo")
    }

    suspend fun createEntry(
        gardenId: Int,
        title: String,
        body: String?,
        entryDate: String,
        tags: List<String>,
    ): NetworkResult<JournalEntry> = try {
        val requestBody = buildMap<String, Any?> {
            put("title", title)
            body?.let { put("body", it) }
            put("entry_date", entryDate)
            put("tags", tags)
        }
        NetworkResult.Success(api.createJournalEntry(gardenId, requestBody))
    } catch (e: Exception) {
        e.toNetworkError("JournalRepo")
    }

    suspend fun deleteEntry(id: Int): NetworkResult<Unit> = try {
        api.deleteJournalEntry(id)
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        e.toNetworkError("JournalRepo")
    }
}

