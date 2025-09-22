import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Navbar = ({ user, onLogout }) => {
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  const hasPermission = (permission) => {
    return user.permissions && user.permissions.includes(permission);
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary">
      <div className="container-fluid">
        <Link className="navbar-brand fw-bold" to="/dashboard">
          Clinical DeID System
        </Link>
        
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarNav"
          aria-controls="navbarNav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        
        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav me-auto">
            <li className="nav-item">
              <Link 
                className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`} 
                to="/dashboard"
              >
                Dashboard
              </Link>
            </li>
            
            {hasPermission('create_job') && (
              <li className="nav-item">
                <Link 
                  className={`nav-link ${isActive('/deidentify') ? 'active' : ''}`} 
                  to="/deidentify"
                >
                  De-Identify
                </Link>
              </li>
            )}
            
            <li className="nav-item">
              <Link 
                className={`nav-link ${isActive('/jobs') ? 'active' : ''}`} 
                to="/jobs"
              >
                Jobs
              </Link>
            </li>
            
            {hasPermission('manage_policies') && (
              <li className="nav-item">
                <Link 
                  className={`nav-link ${isActive('/policies') ? 'active' : ''}`} 
                  to="/policies"
                >
                  Policies
                </Link>
              </li>
            )}
            
            {hasPermission('view_audit_logs') && (
              <li className="nav-item">
                <Link 
                  className={`nav-link ${isActive('/audit') ? 'active' : ''}`} 
                  to="/audit"
                >
                  Audit
                </Link>
              </li>
            )}
          </ul>
          
          <ul className="navbar-nav">
            <li className="nav-item dropdown">
              <a
                className="nav-link dropdown-toggle"
                href="#"
                id="navbarDropdown"
                role="button"
                data-bs-toggle="dropdown"
                aria-expanded="false"
              >
                <i className="fas fa-user me-1"></i>
                {user.username}
                <span className="badge bg-secondary ms-2">{user.role}</span>
              </a>
              
              <ul className="dropdown-menu dropdown-menu-end">
                <li>
                  <span className="dropdown-item-text">
                    <small className="text-muted">Logged in as</small><br />
                    <strong>{user.username}</strong><br />
                    <small className="text-muted">Role: {user.role}</small>
                  </span>
                </li>
                <li><hr className="dropdown-divider" /></li>
                <li>
                  <button className="dropdown-item" onClick={onLogout}>
                    <i className="fas fa-sign-out-alt me-2"></i>
                    Logout
                  </button>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;