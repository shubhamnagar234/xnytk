import React from 'react';
import { NavLink } from 'react-router-dom';
import { Wind, BarChart3, BookOpen, Clock } from 'lucide-react';

export const Navbar: React.FC = () => {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <NavLink to="/" className="brand">
          <div className="brand-icon">
            <Wind size={20} strokeWidth={2.5} />
          </div>
          <div>
            <span className="brand-title">UK Wind Forecast Desk</span>
            <span className="brand-badge">Day-Ahead Buying</span>
          </div>
        </NavLink>

        <nav className="nav-links">
          <NavLink
            to="/"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            end
          >
            <Clock size={16} />
            Decision View
          </NavLink>

          <NavLink
            to="/accuracy"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            <BarChart3 size={16} />
            Accuracy & Horizon
          </NavLink>

          <NavLink
            to="/methodology"
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            <BookOpen size={16} />
            Methodology
          </NavLink>
        </nav>
      </div>
    </header>
  );
};
