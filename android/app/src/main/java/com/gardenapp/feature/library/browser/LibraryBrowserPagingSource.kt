package com.gardenapp.feature.library.browser

import androidx.paging.PagingSource
import androidx.paging.PagingState
import com.gardenapp.core.model.LibraryListEntry
import com.gardenapp.core.network.ApiService

class LibraryBrowserPagingSource(
    private val api: ApiService,
    private val query: String?,
    private val type: String?,
) : PagingSource<Int, LibraryListEntry>() {

    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, LibraryListEntry> {
        val page = params.key ?: 1
        return try {
            val response = api.getLibrary(
                query = query,
                type = type,
                page = page,
                perPage = params.loadSize,
            )
            LoadResult.Page(
                data = response.entries,
                prevKey = if (page == 1) null else page - 1,
                nextKey = if (page >= response.pages) null else page + 1,
            )
        } catch (e: Exception) {
            LoadResult.Error(e)
        }
    }

    override fun getRefreshKey(state: PagingState<Int, LibraryListEntry>): Int = 1
}
