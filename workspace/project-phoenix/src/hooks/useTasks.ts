import { useState, useEffect } from 'react';
import { Task } from '../types/metrics';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

export const useTasks = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/tasks`);
      setTasks(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
      setError('Failed to fetch tasks');
      // Use mock data for demo
      setTasks(getMockTasks());
    } finally {
      setLoading(false);
    }
  };

  const getMockTasks = (): Task[] => [
    {
      id: 1,
      title: "Implement user authentication",
      description: "Add login/logout functionality",
      status: "completed",
      priority: "high",
      createdAt: "2024-01-21T09:00:00Z",
      completedAt: "2024-01-21T11:30:00Z",
      estimatedHours: 4,
      actualHours: 2.5
    },
    {
      id: 2,
      title: "Write unit tests for API",
      description: "Coverage for all endpoints",
      status: "in_progress",
      priority: "medium",
      createdAt: "2024-01-21T10:00:00Z",
      estimatedHours: 6,
      actualHours: 3
    },
    {
      id: 3,
      title: "Optimize database queries",
      description: "Improve performance",
      status: "pending",
      priority: "medium",
      createdAt: "2024-01-21T14:00:00Z",
      estimatedHours: 3
    },
    {
      id: 4,
      title: "Update documentation",
      description: "API docs and README",
      status: "completed",
      priority: "low",
      createdAt: "2024-01-21T16:00:00Z",
      completedAt: "2024-01-21T17:00:00Z",
      estimatedHours: 2,
      actualHours: 1
    },
    {
      id: 5,
      title: "Fix responsive design issues",
      description: "Mobile compatibility",
      status: "pending",
      priority: "high",
      createdAt: "2024-01-21T18:00:00Z",
      estimatedHours: 4
    }
  ];

  const completedToday = tasks.filter(task => {
    if (task.status !== 'completed' || !task.completedAt) return false;
    const today = new Date().toDateString();
    const completedDate = new Date(task.completedAt).toDateString();
    return today === completedDate;
  }).length;

  return {
    tasks,
    loading,
    error,
    completedToday,
    refetch: fetchTasks
  };
};