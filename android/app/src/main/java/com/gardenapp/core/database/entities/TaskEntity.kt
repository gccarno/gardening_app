package com.gardenapp.core.database.entities

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gardenapp.core.model.Task

@Entity(tableName = "tasks")
data class TaskEntity(
    @PrimaryKey val id: Int,
    val title: String,
    val description: String? = null,
    @ColumnInfo(name = "task_type") val taskType: String? = null,
    @ColumnInfo(name = "due_date") val dueDate: String? = null,
    val completed: Boolean = false,
    @ColumnInfo(name = "completed_date") val completedDate: String? = null,
    @ColumnInfo(name = "plant_id") val plantId: Int? = null,
    @ColumnInfo(name = "garden_id") val gardenId: Int? = null,
    @ColumnInfo(name = "bed_id") val bedId: Int? = null,
    @ColumnInfo(name = "plant_name") val plantName: String? = null,
    @ColumnInfo(name = "garden_name") val gardenName: String? = null,
    @ColumnInfo(name = "bed_name") val bedName: String? = null,
)

fun TaskEntity.toTask() = Task(
    id = id, title = title, description = description, taskType = taskType,
    dueDate = dueDate, completed = completed, completedDate = completedDate,
    plantId = plantId, gardenId = gardenId, bedId = bedId,
    plantName = plantName, gardenName = gardenName, bedName = bedName,
)

fun Task.toEntity() = TaskEntity(
    id = id, title = title, description = description, taskType = taskType,
    dueDate = dueDate, completed = completed, completedDate = completedDate,
    plantId = plantId, gardenId = gardenId, bedId = bedId,
    plantName = plantName, gardenName = gardenName, bedName = bedName,
)
