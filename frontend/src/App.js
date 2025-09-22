import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Components
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import DeIdentification from './components/DeIdentification';
import JobMonitor from './components/JobMonitor';
import PolicyManager from './components/PolicyManager';
import AuditViewer from './components/AuditViewer';
import Navbar from './components/Navbar';

// Configure axios defaults
axios.defaults.baseURL = 'http://localhost:8000';

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored token on app load
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');
    
    if (token && userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        
        // Set axios default authorization header
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      } catch (error) {
        console.error('Error parsing stored user data:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    
    setLoading(false);
  }, []);

  const login = async (credentials) => {
    try {
      const response = await axios.post('/auth/login', credentials);
      const { access_token, user: userData } = response.data;
      
      // Store token and user data
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(userData));
      
      // Set axios authorization header
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      setUser(userData);
      toast.success('Login successful!');
      
      return true;
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      toast.error(message);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
    toast.info('Logged out successfully');
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '100vh' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <div className="App">
        {user && <Navbar user={user} onLogout={logout} />}
        
        <div className={user ? 'container-fluid mt-4' : ''}>
          <Routes>
            <Route path="/login" element={
              user ? <Navigate to="/dashboard" /> : <Login onLogin={login} />
            } />
            
            <Route path="/dashboard" element={
              user ? <Dashboard user={user} /> : <Navigate to="/login" />
            } />
            
            <Route path="/deidentify" element={
              user ? <DeIdentification user={user} /> : <Navigate to="/login" />
            } />
            
            <Route path="/jobs" element={
              user ? <JobMonitor user={user} /> : <Navigate to="/login" />
            } />
            
            <Route path="/policies" element={
              user ? <PolicyManager user={user} /> : <Navigate to="/login" />
            } />
            
            <Route path="/audit" element={
              user ? <AuditViewer user={user} /> : <Navigate to="/login" />
            } />
            
            <Route path="/" element={
              user ? <Navigate to="/dashboard" /> : <Navigate to="/login" />
            } />
          </Routes>
        </div>
        
        <ToastContainer
          position="top-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
        />
      </div>
    </Router>
  );
};

export default App;