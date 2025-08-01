import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useCodingMetrics } from '../hooks/useCodingMetrics';
import { useTasks } from '../hooks/useTasks';

const DashboardContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
`;

const Card = styled.div`
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const Title = styled.h2`
  margin: 0 0 1rem 0;
  color: #333;
  font-size: 1.5rem;
`;

const Metric = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #eee;
  
  &:last-child {
    border-bottom: none;
  }
`;

const MetricLabel = styled.span`
  color: #666;
`;

const MetricValue = styled.span`
  font-weight: bold;
  color: #333;
`;

const Dashboard: React.FC = () => {
  const { metrics, loading: metricsLoading } = useCodingMetrics();
  const { tasks, completedToday, loading: tasksLoading } = useTasks();

  const chartData = metrics?.dailyActivity || [];

  return (
    <div>
      <h1>Developer Productivity Dashboard</h1>
      <DashboardContainer>
        <Card>
          <Title>Today's Summary</Title>
          <Metric>
            <MetricLabel>Lines of Code</MetricLabel>
            <MetricValue>{metrics?.linesOfCode || 0}</MetricValue>
          </Metric>
          <Metric>
            <MetricLabel>Commits</MetricLabel>
            <MetricValue>{metrics?.commits || 0}</MetricValue>
          </Metric>
          <Metric>
            <MetricLabel>Tasks Completed</MetricLabel>
            <MetricValue>{completedToday || 0}</MetricValue>
          </Metric>
          <Metric>
            <MetricLabel>Focus Time</MetricLabel>
            <MetricValue>{metrics?.focusTime || '0h 0m'}</MetricValue>
          </Metric>
        </Card>

        <Card>
          <Title>Weekly Activity</Title>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Line 
                type="monotone" 
                dataKey="linesOfCode" 
                stroke="#8884d8" 
                strokeWidth={2}
                name="Lines of Code"
              />
              <Line 
                type="monotone" 
                dataKey="commits" 
                stroke="#82ca9d" 
                strokeWidth={2}
                name="Commits"
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <Title>Recent Tasks</Title>
          {tasksLoading ? (
            <p>Loading tasks...</p>
          ) : (
            <div>
              {tasks?.slice(0, 5).map((task) => (
                <Metric key={task.id}>
                  <MetricLabel>{task.title}</MetricLabel>
                  <MetricValue>{task.status}</MetricValue>
                </Metric>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <Title>Code Quality Metrics</Title>
          <Metric>
            <MetricLabel>Test Coverage</MetricLabel>
            <MetricValue>{metrics?.testCoverage || '0%'}</MetricValue>
          </Metric>
          <Metric>
            <MetricLabel>Code Reviews</MetricLabel>
            <MetricValue>{metrics?.codeReviews || 0}</MetricValue>
          </Metric>
          <Metric>
            <MetricLabel>Bug Reports</MetricLabel>
            <MetricValue>{metrics?.bugReports || 0}</MetricValue>
          </Metric>
        </Card>
      </DashboardContainer>
    </div>
  );
};

export default Dashboard;