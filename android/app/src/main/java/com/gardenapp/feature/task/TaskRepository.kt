package com.gardenapp.feature.task

import com.gardenapp.core.database.dao.TaskDao
import com.gardenapp.core.database.entities.toEntity
import com.gardenapp.core.database.entities.toTask
import com.gardenapp.core.model.Task
import com.gardenapp.core.network.ApiService
import com.gardenapp.core.network.NetworkResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TaskRepository @Inject constructor(
    private val api: ApiService,
    private val taskDao: TaskDao,
) {
    val tasks: Flow<List<Task>> = taskDao.getAllTasks().map { list -> list.map { it.toTask() } }

    suspend fun refresh(): NetworkResult<List<Task>> = try {
        val fresh = api.getTasks()
        taskDao.upsertAll(fresh.map { it.toEntity() })
        NetworkResult.Success(fresh)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun completeTask(id: Int): NetworkResult<Task> = try {
        val result = api.toggleTaskComplete(id)
        taskDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun createTask(
        title: String,
        description: String?,
        taskType: String?,
        dueDate: String?,
        gardenId: Int?,
        bedId: Int?,
        plantId: Int?,
    ): NetworkResult<Task> = try {
        val body = buildMap<String, Any?> {
            put("title", title)
            description?.let { put("description", it) }
            taskType?.let { put("task_type", it) }
            dueDate?.let { put("due_date", it) }
            gardenId?.let { put("garden_id", it) }
            bedId?.let { put("bed_id", it) }
            plantId?.let { put("plant_id", it) }
        }
        val result = api.createTask(body)
        taskDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun updateTask(
        id: Int,
        title: String,
        description: String?,
        taskType: String?,
        dueDate: String?,
        gardenId: Int?,
        bedId: Int?,
        plantId: Int?,
    ): NetworkResult<Task> = try {
        val body = buildMap<String, Any?> {
            put("title", title)
            put("description", description)
            put("task_type", taskType)
            put("due_date", dueDate)
            put("garden_id", gardenId)
            put("bed_id", bedId)
            put("plant_id", plantId)
        }
        val result = api.updateTask(id, body)
        taskDao.upsertAll(listOf(result.toEntity()))
        NetworkResult.Success(result)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun deleteTask(id: Int): NetworkResult<Unit> = try {
        api.deleteTask(id)
        refresh()
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }

    suspend fun quickTask(gardenId: Int, plantId: Int?, taskType: String?): NetworkResult<Unit> = try {
        val body = buildMap<String, Any?> {
            plantId?.let { put("plant_id", it) }
            taskType?.let { put("task_type", it) }
        }
        api.createQuickTask(gardenId, body)
        refresh()
        NetworkResult.Success(Unit)
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network error")
    }
}
