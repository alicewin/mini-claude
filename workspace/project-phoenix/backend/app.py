from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from typing import Dict, List, Any

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///productivity.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(app)

# Database Models
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')
    priority = db.Column(db.String(20), default='medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    estimated_hours = db.Column(db.Float)
    actual_hours = db.Column(db.Float)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours
        }

class CodingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    lines_of_code = db.Column(db.Integer, default=0)
    commits = db.Column(db.Integer, default=0)
    focus_time_minutes = db.Column(db.Integer, default=0)
    files_modified = db.Column(db.Integer, default=0)
    test_coverage = db.Column(db.Float, default=0.0)
    code_reviews = db.Column(db.Integer, default=0)
    bug_reports = db.Column(db.Integer, default=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'lines_of_code': self.lines_of_code,
            'commits': self.commits,
            'focus_time_minutes': self.focus_time_minutes,
            'files_modified': self.files_modified,
            'test_coverage': self.test_coverage,
            'code_reviews': self.code_reviews,
            'bug_reports': self.bug_reports
        }

# API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks with optional filtering"""
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    
    query = Task.query
    
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)
    
    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify([task.to_dict() for task in tasks])

@app.route('/api/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    data = request.get_json()
    
    task = Task(
        title=data.get('title'),
        description=data.get('description'),
        priority=data.get('priority', 'medium'),
        estimated_hours=data.get('estimated_hours')
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify(task.to_dict()), 201

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id: int):
    """Update an existing task"""
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    
    # Update fields
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'status' in data:
        task.status = data['status']
        if data['status'] == 'completed' and not task.completed_at:
            task.completed_at = datetime.utcnow()
    if 'priority' in data:
        task.priority = data['priority']
    if 'actual_hours' in data:
        task.actual_hours = data['actual_hours']
    
    db.session.commit()
    return jsonify(task.to_dict())

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id: int):
    """Delete a task"""
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return '', 204

@app.route('/api/metrics/today', methods=['GET'])
def get_today_metrics():
    """Get today's coding metrics"""
    today = datetime.utcnow().date()
    session = CodingSession.query.filter(CodingSession.date == today).first()
    
    if not session:
        # Create empty session for today
        session = CodingSession(date=today)
        db.session.add(session)
        db.session.commit()
    
    # Get completed tasks today
    completed_today = Task.query.filter(
        Task.status == 'completed',
        Task.completed_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    metrics = session.to_dict()
    metrics['completed_tasks'] = completed_today
    metrics['focus_time'] = f"{session.focus_time_minutes // 60}h {session.focus_time_minutes % 60}m"
    
    return jsonify(metrics)

@app.route('/api/metrics/weekly', methods=['GET'])
def get_weekly_metrics():
    """Get last 7 days of coding metrics"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=6)
    
    sessions = CodingSession.query.filter(
        CodingSession.date >= start_date,
        CodingSession.date <= end_date
    ).order_by(CodingSession.date).all()
    
    # Fill in missing days with zero data
    daily_data = []
    current_date = start_date
    
    while current_date <= end_date:
        session = next((s for s in sessions if s.date == current_date), None)
        
        if session:
            data = session.to_dict()
        else:
            data = {
                'date': current_date.isoformat(),
                'lines_of_code': 0,
                'commits': 0,
                'focus_time_minutes': 0,
                'files_modified': 0
            }
        
        data['day'] = current_date.strftime('%a')  # Mon, Tue, etc.
        daily_data.append(data)
        current_date += timedelta(days=1)
    
    return jsonify(daily_data)

@app.route('/api/metrics/update', methods=['POST'])
def update_metrics():
    """Update today's coding metrics"""
    data = request.get_json()
    today = datetime.utcnow().date()
    
    session = CodingSession.query.filter(CodingSession.date == today).first()
    if not session:
        session = CodingSession(date=today)
        db.session.add(session)
    
    # Update metrics
    if 'lines_of_code' in data:
        session.lines_of_code += data['lines_of_code']
    if 'commits' in data:
        session.commits += data['commits']
    if 'focus_time_minutes' in data:
        session.focus_time_minutes += data['focus_time_minutes']
    if 'files_modified' in data:
        session.files_modified += data['files_modified']
    if 'test_coverage' in data:
        session.test_coverage = data['test_coverage']
    if 'code_reviews' in data:
        session.code_reviews += data['code_reviews']
    if 'bug_reports' in data:
        session.bug_reports += data['bug_reports']
    
    db.session.commit()
    return jsonify(session.to_dict())

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)