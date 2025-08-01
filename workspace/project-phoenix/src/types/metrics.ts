export interface CodingMetrics {
  linesOfCode: number;
  commits: number;
  focusTime: string;
  testCoverage: string;
  codeReviews: number;
  bugReports: number;
  dailyActivity: DailyActivity[];
}

export interface DailyActivity {
  day: string;
  date: string;
  linesOfCode: number;
  commits: number;
  focusTime: number;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed';
  priority: 'low' | 'medium' | 'high';
  createdAt: string;
  completedAt?: string;
  estimatedHours?: number;
  actualHours?: number;
}