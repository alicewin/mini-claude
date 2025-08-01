import React from 'react';
import styled from 'styled-components';

const Container = styled.div`
  padding: 2rem;
`;

const Title = styled.h1`
  color: #333;
  margin-bottom: 2rem;
`;

const ComingSoon = styled.div`
  text-align: center;
  padding: 4rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const TaskTracker: React.FC = () => {
  return (
    <Container>
      <Title>Task Tracker</Title>
      <ComingSoon>
        <h2>🚧 Coming Soon</h2>
        <p>Task management interface will be available here</p>
      </ComingSoon>
    </Container>
  );
};

export default TaskTracker;