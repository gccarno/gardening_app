package com.gardenapp.feature.library.browser

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.cachedIn
import com.gardenapp.core.network.ApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

data class PerenualResult(val id: String, val name: String, val scientificName: String?)

@OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
@HiltViewModel
class LibraryBrowserViewModel @Inject constructor(
    private val api: ApiService,
) : ViewModel() {

    private val _query = MutableStateFlow("")
    private val _typeFilter = MutableStateFlow<String?>(null)
    private val _compareIds = MutableStateFlow<Set<Int>>(emptySet())
    private val _perenualQuery = MutableStateFlow("")
    private val _perenualResults = MutableStateFlow<List<PerenualResult>>(emptyList())
    private val _perenualLoading = MutableStateFlow(false)
    private val _perenualError = MutableStateFlow<String?>(null)

    val query: StateFlow<String> = _query
    val typeFilter: StateFlow<String?> = _typeFilter
    val compareIds: StateFlow<Set<Int>> = _compareIds
    val perenualQuery: StateFlow<String> = _perenualQuery
    val perenualResults: StateFlow<List<PerenualResult>> = _perenualResults
    val perenualLoading: StateFlow<Boolean> = _perenualLoading
    val perenualError: StateFlow<String?> = _perenualError

    val pagedLibrary = combine(_query, _typeFilter) { q, type -> q to type }
        .debounce(300L)
        .flatMapLatest { (q, type) ->
            Pager(PagingConfig(pageSize = 20, prefetchDistance = 5)) {
                LibraryBrowserPagingSource(api, q.ifBlank { null }, type)
            }.flow
        }
        .cachedIn(viewModelScope)

    fun onQueryChange(q: String) { _query.value = q }

    fun onTypeFilterChange(type: String?) {
        _typeFilter.value = if (_typeFilter.value == type) null else type
    }

    fun toggleCompare(id: Int) {
        val current = _compareIds.value
        _compareIds.value = if (id in current) {
            current - id
        } else if (current.size < 2) {
            current + id
        } else {
            current
        }
    }

    fun clearCompare() { _compareIds.value = emptySet() }

    fun onPerenualQueryChange(q: String) { _perenualQuery.value = q }

    fun searchPerenual() {
        val q = _perenualQuery.value.trim()
        if (q.isBlank()) return
        viewModelScope.launch(kotlinx.coroutines.Dispatchers.IO) {
            _perenualLoading.value = true
            _perenualError.value = null
            try {
                val result = api.perenualSearch(q)
                val items = when (result) {
                    is JsonObject -> {
                        val data = result["data"] as? JsonArray ?: JsonArray(emptyList())
                        data.mapNotNull { el ->
                            val obj = (el as? JsonObject) ?: return@mapNotNull null
                            PerenualResult(
                                id = obj["id"]?.jsonPrimitive?.content ?: "",
                                name = obj["common_name"]?.jsonPrimitive?.content ?: "Unknown",
                                scientificName = obj["scientific_name"]?.jsonPrimitive?.content,
                            )
                        }
                    }
                    is JsonArray -> result.mapNotNull { el ->
                        val obj = (el as? JsonObject) ?: return@mapNotNull null
                        PerenualResult(
                            id = obj["id"]?.jsonPrimitive?.content ?: "",
                            name = obj["common_name"]?.jsonPrimitive?.content ?: "Unknown",
                            scientificName = obj["scientific_name"]?.jsonPrimitive?.content,
                        )
                    }
                    else -> emptyList()
                }
                _perenualResults.value = items
            } catch (e: Exception) {
                _perenualError.value = e.message ?: "Search failed"
            }
            _perenualLoading.value = false
        }
    }
}

