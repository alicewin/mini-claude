import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import styled from 'styled-components';

const NavContainer = styled.nav`
  position: fixed;
  left: 0;
  top: 0;
  width: 250px;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem 0;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  z-index: 1000;
`;

const Brand = styled.div`
  padding: 0 2rem 2rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  margin-bottom: 2rem;
`;

const BrandTitle = styled.h1`
  color: white;
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
`;

const BrandSubtitle = styled.p`
  color: rgba(255, 255, 255, 0.8);
  margin: 0.5rem 0 0 0;
  font-size: 0.9rem;
`;

const NavList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

const NavItem = styled.li`
  margin: 0;
`;

const NavLink = styled(Link)<{ $isActive: boolean }>`
  display: flex;
  align-items: center;
  padding: 1rem 2rem;
  color: ${props => props.$isActive ? 'white' : 'rgba(255, 255, 255, 0.8)'};
  text-decoration: none;
  transition: all 0.3s ease;
  background: ${props => props.$isActive ? 'rgba(255, 255, 255, 0.2)' : 'transparent'};
  border-right: ${props => props.$isActive ? '3px solid white' : '3px solid transparent'};

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }
`;

const NavIcon = styled.span`
  margin-right: 1rem;
  font-size: 1.2rem;
`;

const NavText = styled.span`
  font-weight: 500;
`;

const Navigation: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/tasks', label: 'Task Tracker', icon: '✅' },
    { path: '/metrics', label: 'Coding Metrics', icon: '📈' },
    { path: '/progress', label: 'Progress', icon: '🎯' }
  ];

  return (
    <NavContainer>
      <Brand>
        <BrandTitle>DevDash</BrandTitle>
        <BrandSubtitle>Productivity Tracker</BrandSubtitle>
      </Brand>
      
      <NavList>
        {navItems.map((item) => (
          <NavItem key={item.path}>
            <NavLink 
              to={item.path} 
              $isActive={location.pathname === item.path}
            >
              <NavIcon>{item.icon}</NavIcon>
              <NavText>{item.label}</NavText>
            </NavLink>
          </NavItem>
        ))}
      </NavList>
    </NavContainer>
  );
};

export default Navigation;