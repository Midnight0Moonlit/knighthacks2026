import { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const CATALOG = {
  apple: { id: 'apple', name: '🍎 Apple', price: 1.29 },
  banana: { id: 'banana', name: '🍌 Banana', price: 0.59 },
  water: { id: 'water', name: '🍾 Bottled Water', price: 1.99 },
};

type ItemKey = keyof typeof CATALOG;
type LogEntry = { id: number; text: string; type: 'vision' | 'manual' | 'system' };

function StartPage() {
  const navigate = useNavigate();
  return (
    <>
      <header className="top-header">
        <div><strong>SmartCart AI</strong> • Powered by Jetson</div>
        <div className="status-badge"><div className="dot green"></div>Systems Connected</div>
      </header>
      <main className="page-wrapper">
        <h1 className="title-text">Welcome to SmartCart AI</h1>
        <h2 className="subtitle-text">Ready to start your shopping trip?</h2>
        <button className="giant-start-btn" onClick={() => navigate('/budget')}>START ➔</button>
        <p className="helper-text">Tap here to set your budget and begin.</p>
      </main>
    </>
  );
}

function BudgetPage() {
  const navigate = useNavigate();
  const [budget, setBudget] = useState('50.00');

  const startShopping = () => {
    navigate('/cart', { state: { budget: parseFloat(budget) || 0 } });
  };

  return (
    <>
      <header className="top-header">
        <div><strong>SmartCart AI</strong> • Powered by Jetson</div>
        <div className="status-badge"><div className="dot green"></div>Systems Connected</div>
      </header>
      <main className="page-wrapper">
        <h1 className="title-text">Set your shopping budget</h1>
        <p className="subtitle-text">We'll alert you if you go over your budget.</p>
        <div className="budget-card">
          <div className="budget-label">ENTER BUDGET</div>
          <div className="budget-input-wrapper">
            $ <input type="number" className="budget-input" value={budget} onChange={(e) => setBudget(e.target.value)} autoFocus />
          </div>
        </div>
        <button className="budget-btn" onClick={startShopping}>START SHOPPING ➔</button>
      </main>
    </>
  );
}

function CartDashboard() {
  const location = useLocation();
  const budget = location.state?.budget || 0;
  
  const [inventory, setInventory] = useState<Record<ItemKey, number>>({ apple: 0, banana: 0, water: 0 });
  const [totals, setTotals] = useState({ subtotal: 0, tax: 0, total: 0 });
  const [wsStatus, setWsStatus] = useState<'connected' | 'offline' | 'reconnecting'>('offline');
  const [logs, setLogs] = useState<LogEntry[]>([{ id: 0, text: '[SYSTEM] Initialized', type: 'system' }]);
  const [pulsingItem, setPulsingItem] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (text: string, type: 'vision' | 'manual' | 'system') => {
    setLogs((prev) => [{ id: Date.now(), text, type }, ...prev].slice(0, 5));
  };

  const connectWebSocket = () => {
    const wsUrl = `ws://${window.location.host}/ws/cart`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus('connected');
      addLog('[SYSTEM] WebSocket Connected', 'system');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.inventory) setInventory(data.inventory);
        if (data.total !== undefined) setTotals({ subtotal: data.subtotal, tax: data.tax, total: data.total });
        
        if (data.action === 'VISION_ADD' && data.item) {
          setPulsingItem(data.item);
          setTimeout(() => setPulsingItem(null), 500);
          addLog(`[VISION] Added ${CATALOG[data.item as ItemKey].name}`, 'vision');
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = () => {
      setWsStatus('reconnecting');
      addLog('[SYSTEM] Connection lost. Retrying...', 'system');
      setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = () => ws.close();
  };

  useEffect(() => {
    connectWebSocket();
    return () => wsRef.current?.close();
  }, []);

  const sendAction = (action: string, item?: ItemKey) => {
    if (action === 'MANUAL_ADD' && item) {
      setInventory(prev => ({ ...prev, [item]: prev[item] + 1 }));
      addLog(`[MANUAL] Added ${CATALOG[item].name}`, 'manual');
    }
    if (action === 'MANUAL_REMOVE' && item && inventory[item] > 0) {
      setInventory(prev => ({ ...prev, [item]: prev[item] - 1 }));
      addLog(`[MANUAL] Removed ${CATALOG[item].name}`, 'manual');
    }
    if (action === 'RESET') {
      setInventory({ apple: 0, banana: 0, water: 0 });
      addLog('[SYSTEM] Cart Reset', 'system');
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, item }));
    }
  };

  const currentSubtotal = Object.entries(inventory).reduce((acc, [key, qty]) => acc + (CATALOG[key as ItemKey].price * qty), 0);
  const currentTax = currentSubtotal * 0.07;
  const currentTotal = currentSubtotal + currentTax;

  // Progress Bar Math
  const isOverBudget = budget > 0 && currentTotal > budget;
  const progressPercentage = budget > 0 ? Math.min((currentTotal / budget) * 100, 100) : 0;

  return (
    <>
      <header className="top-header dark-header">
        <div><strong>Smart Cart Retrofit</strong></div>
        <div className="status-badge">
          <div className={`dot ${wsStatus === 'connected' ? 'green' : wsStatus === 'reconnecting' ? 'yellow' : 'red'}`}></div>
          {wsStatus === 'connected' ? 'Live' : wsStatus === 'reconnecting' ? 'Reconnecting...' : 'Offline'}
        </div>
        <button className="reset-btn" onClick={() => sendAction('RESET')}>Reset Cart</button>
      </header>

      <main className="dashboard">
        {/* LEFT COLUMN: Catalog & Summary */}
        <div className="catalog-panel">
          <div className="catalog-items">
            {(Object.keys(CATALOG) as ItemKey[]).map((key) => {
              const item = CATALOG[key];
              const qty = inventory[key];
              const isPulsing = pulsingItem === key;

              return (
                <div key={key} className={`catalog-row ${isPulsing ? 'pulse-anim' : ''}`}>
                  <div style={{ flex: 1 }}>
                    <strong>{item.name}</strong>
                    <div style={{ fontSize: '1.2rem', color: '#7f8c8d' }}>${item.price.toFixed(2)}</div>
                  </div>
                  
                  <div className="controls">
                    <button className="touch-btn btn-minus" onClick={() => sendAction('MANUAL_REMOVE', key)}>–</button>
                    <span style={{ fontSize: '2rem', width: '40px', textAlign: 'center' }}>{qty}</span>
                    <button className="touch-btn btn-plus" onClick={() => sendAction('MANUAL_ADD', key)}>+</button>
                  </div>
                  
                  <div style={{ width: '100px', textAlign: 'right', fontWeight: 'bold' }}>
                    ${(item.price * qty).toFixed(2)}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Moved Subtotal & Tax Here */}
          <div className="catalog-summary">
            <div className="summary-line"><span>Subtotal</span> <span>${currentSubtotal.toFixed(2)}</span></div>
            <div className="summary-line"><span>Estimated Tax (7%)</span> <span>${currentTax.toFixed(2)}</span></div>
          </div>
        </div>

        {/* RIGHT COLUMN: Telemetry & Progress Bar */}
        <div className="receipt-panel">
          <div className="receipt-card">
            
            {budget > 0 ? (
              <>
                <div className="progress-header" style={{ color: isOverBudget ? '#e74c3c' : '#2c3e50' }}>
                  <span>Budget: ${budget.toFixed(2)}</span>
                  <span>{isOverBudget ? 'OVER BUDGET' : `${progressPercentage.toFixed(0)}%`}</span>
                </div>
                <div className="progress-container">
                  <div 
                    className={`progress-bar ${isOverBudget ? 'over-budget' : ''}`} 
                    style={{ width: `${progressPercentage}%` }}
                  ></div>
                </div>
              </>
            ) : (
              <div style={{ color: '#7f8c8d', marginBottom: '1.5rem', fontWeight: 'bold', fontSize: '1.25rem' }}>No Budget Set</div>
            )}

            <div className="receipt-total" style={{ color: isOverBudget ? '#e74c3c' : '#2c3e50' }}>
              <span>Total:</span> 
              <span>${currentTotal.toFixed(2)}</span>
            </div>
            
            <button className="checkout-btn" onClick={() => alert(`Checking out total: $${currentTotal.toFixed(2)}`)}>Checkout</button>
          </div>

          <div className="activity-log">
            <div style={{ borderBottom: '1px solid #555', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>ACTIVITY LOG</div>
            {logs.map((log) => (
              <div key={log.id} className={`log-entry log-${log.type}`}>
                {log.text}
              </div>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}

export default function App() {
  return (
    <div className="ipad-viewport">
      <Router>
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/cart" element={<CartDashboard />} />
        </Routes>
      </Router>
    </div>
  );
}