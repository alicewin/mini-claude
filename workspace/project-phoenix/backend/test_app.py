import pytest
import json
from datetime import datetime, date
from app import app, db, Task, CodingSession

@pytest.fixture
def client():
    """Create a test client for the Flask application"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    return {
        'title': 'Test Task',
        'description': 'This is a test task',
        'priority': 'high',
        'estimated_hours': 2.5
    }

@pytest.fixture
def sample_metrics():
    """Create sample metrics for testing"""
    return {
        'lines_of_code': 100,
        'commits': 3,
        'focus_time_minutes': 120,
        'files_modified': 5
    }

class TestHealthCheck:
    def test_health_check(self, client):
        """Test the health check endpoint"""
        response = client.get('/api/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data

class TestTaskAPI:
    def test_get_empty_tasks(self, client):
        """Test getting tasks when none exist"""
        response = client.get('/api/tasks')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data == []

    def test_create_task(self, client, sample_task):
        """Test creating a new task"""
        response = client.post('/api/tasks', 
                             data=json.dumps(sample_task),
                             content_type='application/json')
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['title'] == sample_task['title']
        assert data['description'] == sample_task['description']
        assert data['priority'] == sample_task['priority']
        assert data['estimated_hours'] == sample_task['estimated_hours']
        assert data['status'] == 'pending'
        assert 'id' in data
        assert 'created_at' in data

    def test_get_tasks_after_creation(self, client, sample_task):
        """Test getting tasks after creating one"""
        # Create a task
        client.post('/api/tasks', 
                   data=json.dumps(sample_task),
                   content_type='application/json')
        
        # Get all tasks
        response = client.get('/api/tasks')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['title'] == sample_task['title']

    def test_filter_tasks_by_status(self, client, sample_task):
        """Test filtering tasks by status"""
        # Create tasks with different statuses
        task1 = sample_task.copy()
        task1['title'] = 'Pending Task'
        
        task2 = sample_task.copy()
        task2['title'] = 'Completed Task'
        
        # Create tasks
        response1 = client.post('/api/tasks', 
                               data=json.dumps(task1),
                               content_type='application/json')
        task1_id = json.loads(response1.data)['id']
        
        client.post('/api/tasks', 
                   data=json.dumps(task2),
                   content_type='application/json')
        
        # Update one task to completed
        client.put(f'/api/tasks/{task1_id}',
                  data=json.dumps({'status': 'completed'}),
                  content_type='application/json')
        
        # Filter by pending status
        response = client.get('/api/tasks?status=pending')
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['title'] == 'Completed Task'
        
        # Filter by completed status
        response = client.get('/api/tasks?status=completed')
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['title'] == 'Pending Task'

    def test_update_task(self, client, sample_task):
        """Test updating an existing task"""
        # Create a task
        response = client.post('/api/tasks', 
                              data=json.dumps(sample_task),
                              content_type='application/json')
        task_id = json.loads(response.data)['id']
        
        # Update the task
        update_data = {
            'title': 'Updated Task',
            'status': 'in_progress',
            'actual_hours': 1.5
        }
        
        response = client.put(f'/api/tasks/{task_id}',
                             data=json.dumps(update_data),
                             content_type='application/json')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['title'] == 'Updated Task'
        assert data['status'] == 'in_progress'
        assert data['actual_hours'] == 1.5

    def test_complete_task_sets_completion_time(self, client, sample_task):
        """Test that completing a task sets the completion time"""
        # Create a task
        response = client.post('/api/tasks', 
                              data=json.dumps(sample_task),
                              content_type='application/json')
        task_id = json.loads(response.data)['id']
        
        # Complete the task
        response = client.put(f'/api/tasks/{task_id}',
                             data=json.dumps({'status': 'completed'}),
                             content_type='application/json')
        
        data = json.loads(response.data)
        assert data['status'] == 'completed'
        assert data['completed_at'] is not None

    def test_delete_task(self, client, sample_task):
        """Test deleting a task"""
        # Create a task
        response = client.post('/api/tasks', 
                              data=json.dumps(sample_task),
                              content_type='application/json')
        task_id = json.loads(response.data)['id']
        
        # Delete the task
        response = client.delete(f'/api/tasks/{task_id}')
        assert response.status_code == 204
        
        # Verify task is deleted
        response = client.get('/api/tasks')
        data = json.loads(response.data)
        assert len(data) == 0

    def test_update_nonexistent_task(self, client):
        """Test updating a task that doesn't exist"""
        response = client.put('/api/tasks/999',
                             data=json.dumps({'title': 'Updated'}),
                             content_type='application/json')
        assert response.status_code == 404

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist"""
        response = client.delete('/api/tasks/999')
        assert response.status_code == 404

class TestMetricsAPI:
    def test_get_today_metrics_creates_session(self, client):
        """Test that getting today's metrics creates a new session if none exists"""
        response = client.get('/api/metrics/today')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['lines_of_code'] == 0
        assert data['commits'] == 0
        assert data['focus_time_minutes'] == 0
        assert data['completed_tasks'] == 0
        assert data['focus_time'] == '0h 0m'

    def test_update_metrics(self, client, sample_metrics):
        """Test updating today's metrics"""
        response = client.post('/api/metrics/update',
                              data=json.dumps(sample_metrics),
                              content_type='application/json')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['lines_of_code'] == sample_metrics['lines_of_code']
        assert data['commits'] == sample_metrics['commits']
        assert data['focus_time_minutes'] == sample_metrics['focus_time_minutes']
        assert data['files_modified'] == sample_metrics['files_modified']

    def test_metrics_accumulate(self, client, sample_metrics):
        """Test that metrics accumulate when updated multiple times"""
        # Update metrics first time
        client.post('/api/metrics/update',
                   data=json.dumps(sample_metrics),
                   content_type='application/json')
        
        # Update metrics second time
        response = client.post('/api/metrics/update',
                              data=json.dumps(sample_metrics),
                              content_type='application/json')
        
        data = json.loads(response.data)
        assert data['lines_of_code'] == sample_metrics['lines_of_code'] * 2
        assert data['commits'] == sample_metrics['commits'] * 2

    def test_get_weekly_metrics(self, client):
        """Test getting weekly metrics"""
        response = client.get('/api/metrics/weekly')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 7  # 7 days
        
        # Check that each day has required fields
        for day_data in data:
            assert 'date' in day_data
            assert 'day' in day_data
            assert 'lines_of_code' in day_data
            assert 'commits' in day_data
            assert 'focus_time_minutes' in day_data

    def test_focus_time_formatting(self, client):
        """Test that focus time is formatted correctly"""
        # Update with 125 minutes (2h 5m)
        metrics = {'focus_time_minutes': 125}
        client.post('/api/metrics/update',
                   data=json.dumps(metrics),
                   content_type='application/json')
        
        response = client.get('/api/metrics/today')
        data = json.loads(response.data)
        assert data['focus_time'] == '2h 5m'

class TestTaskModel:
    def test_task_to_dict(self):
        """Test Task model to_dict method"""
        task = Task(
            title='Test Task',
            description='Test Description',
            status='pending',
            priority='high'
        )
        
        task_dict = task.to_dict()
        assert task_dict['title'] == 'Test Task'
        assert task_dict['description'] == 'Test Description'
        assert task_dict['status'] == 'pending'
        assert task_dict['priority'] == 'high'

class TestCodingSessionModel:
    def test_coding_session_to_dict(self):
        """Test CodingSession model to_dict method"""
        session = CodingSession(
            date=date.today(),
            lines_of_code=100,
            commits=5,
            focus_time_minutes=120
        )
        
        session_dict = session.to_dict()
        assert session_dict['lines_of_code'] == 100
        assert session_dict['commits'] == 5
        assert session_dict['focus_time_minutes'] == 120

class TestErrorHandling:
    def test_404_error_handler(self, client):
        """Test 404 error handling"""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert 'error' in data

    def test_invalid_json_400_error(self, client):
        """Test 400 error for invalid JSON"""
        response = client.post('/api/tasks',
                              data='invalid json',
                              content_type='application/json')
        assert response.status_code == 400

if __name__ == '__main__':
    pytest.main([__file__])