import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const PolicyManager = ({ user }) => {
  const [policies, setPolicies] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      const response = await axios.get('/api/v1/policies');
      setPolicies(response.data.policies || {});
    } catch (error) {
      toast.error('Failed to load policies');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-12">
          <h1 className="h3 mb-4">Policy Manager</h1>
          
          {user.permissions.includes('manage_policies') ? (
            <div>
              <div className="alert alert-info">
                <h6>Policy Management</h6>
                <p className="mb-0">
                  This interface allows authorized users to create and manage de-identification policies.
                  Policies define how different types of entities should be transformed.
                </p>
              </div>
              
              <div className="card">
                <div className="card-header">
                  <h6 className="card-title mb-0">Available Policies</h6>
                </div>
                <div className="card-body">
                  {loading ? (
                    <div className="text-center">
                      <div className="spinner-border" role="status">
                        <span className="visually-hidden">Loading...</span>
                      </div>
                    </div>
                  ) : (
                    <div className="row">
                      {Object.entries(policies).map(([policyId, policy]) => (
                        <div key={policyId} className="col-md-6 mb-3">
                          <div className="card">
                            <div className="card-body">
                              <h6 className="card-title">{policyId}</h6>
                              <p className="text-muted">{policy.entity_count} transformation rules</p>
                              
                              <div className="small">
                                {policy.transformations.slice(0, 5).map((transform, index) => (
                                  <div key={index} className="d-flex justify-content-between mb-1">
                                    <span>{transform.entity_type}:</span>
                                    <span className="badge bg-light text-dark">{transform.transformation}</span>
                                  </div>
                                ))}
                                {policy.transformations.length > 5 && (
                                  <div className="text-muted">
                                    ... and {policy.transformations.length - 5} more
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="alert alert-warning">
              <h6>Access Restricted</h6>
              <p className="mb-0">
                You do not have permission to manage policies. Contact your administrator for access.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PolicyManager;