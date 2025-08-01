import axios from 'axios';
import { CodingMetrics } from '../types/metrics';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

class MetricsService {
  async getCodingMetrics(): Promise<CodingMetrics> {
    try {
      const [todayResponse, weeklyResponse] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/metrics/today`),
        axios.get(`${API_BASE_URL}/api/metrics/weekly`)
      ]);

      const todayData = todayResponse.data;
      const weeklyData = weeklyResponse.data;

      return {
        linesOfCode: todayData.lines_of_code || 0,
        commits: todayData.commits || 0,
        focusTime: todayData.focus_time || '0h 0m',
        testCoverage: `${todayData.test_coverage || 0}%`,
        codeReviews: todayData.code_reviews || 0,
        bugReports: todayData.bug_reports || 0,
        dailyActivity: weeklyData.map((day: any) => ({
          day: day.day,
          date: day.date,
          linesOfCode: day.lines_of_code,
          commits: day.commits,
          focusTime: day.focus_time_minutes
        }))
      };
    } catch (error) {
      console.error('Failed to fetch coding metrics:', error);
      // Return mock data for demo
      return this.getMockMetrics();
    }
  }

  private getMockMetrics(): CodingMetrics {
    return {
      linesOfCode: 247,
      commits: 8,
      focusTime: '4h 32m',
      testCoverage: '87%',
      codeReviews: 3,
      bugReports: 1,
      dailyActivity: [
        { day: 'Mon', date: '2024-01-15', linesOfCode: 180, commits: 4, focusTime: 240 },
        { day: 'Tue', date: '2024-01-16', linesOfCode: 220, commits: 6, focusTime: 300 },
        { day: 'Wed', date: '2024-01-17', linesOfCode: 195, commits: 3, focusTime: 180 },
        { day: 'Thu', date: '2024-01-18', linesOfCode: 267, commits: 7, focusTime: 320 },
        { day: 'Fri', date: '2024-01-19', linesOfCode: 247, commits: 8, focusTime: 272 },
        { day: 'Sat', date: '2024-01-20', linesOfCode: 120, commits: 2, focusTime: 150 },
        { day: 'Sun', date: '2024-01-21', linesOfCode: 89, commits: 1, focusTime: 90 }
      ]
    };
  }

  async updateMetrics(metrics: Partial<CodingMetrics>): Promise<void> {
    try {
      await axios.post(`${API_BASE_URL}/api/metrics/update`, metrics);
    } catch (error) {
      console.error('Failed to update metrics:', error);
    }
  }
}

export const metricsService = new MetricsService();