import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [serverResponse, setServerResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 서버 연동 테스트 함수
  const testConnection = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8002/api/test');
      const data = await response.json();
      
      if (data.status === 200) {
        setServerResponse(data);
      }
    } catch (err) {
      setError('서버 연결 실패: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // 컴포넌트 마운트 시 자동 테스트
  useEffect(() => {
    testConnection();
  }, []);

  return (
    <div className="App" style={{ padding: '40px' }}>
      <h1>Admin UI 연동 테스트</h1>
      
      <button 
        onClick={testConnection}
        disabled={loading}
        style={{
          padding: '10px 20px',
          fontSize: '16px',
          cursor: loading ? 'not-allowed' : 'pointer'
        }}
      >
        {loading ? '연결 중...' : '서버 연결 테스트'}
      </button>

      {error && (
        <div style={{ 
          marginTop: '20px', 
          padding: '15px', 
          backgroundColor: '#ffebee',
          color: '#c62828',
          borderRadius: '4px'
        }}>
          <strong>에러:</strong> {error}
        </div>
      )}

      {serverResponse && serverResponse.status === 200 && (
        <div style={{ 
          marginTop: '20px', 
          padding: '15px', 
          backgroundColor: '#e8f5e9',
          color: '#2e7d32',
          borderRadius: '4px'
        }}>
          <h3>✅ 서버 응답 성공!</h3>
          <pre style={{ 
            textAlign: 'left', 
            backgroundColor: '#fff',
            padding: '10px',
            borderRadius: '4px',
            overflow: 'auto'
          }}>
            {JSON.stringify(serverResponse, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;
