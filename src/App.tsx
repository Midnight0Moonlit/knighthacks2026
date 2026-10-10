import { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const CATALOG = {
  apple: { id: 'apple', name: '🍎 Apple', price: 1.29 },
  banana: { id: 'banana', name: '🍌 Banana', price: 0.59 },
  water: { id: 'water', name: '💦 Bottled Water', price: 1.99 },
};

type ItemKey = keyof typeof CATALOG;

const MACRO_PROGRESS = [
  { name: 'Protein', current: 72, goal: 120, color: '#f5c542', radius: 108 },
  { name: 'Carbs', current: 145, goal: 250, color: '#42bda0', radius: 81 },
  { name: 'Fat', current: 28, goal: 65, color: '#ed8068', radius: 54 },
];

function StartPage() {
  const navigate = useNavigate();
  return (
    <>
      <header className="top-header">
        <div><strong>Budget Buddies</strong> • Powered by Jetson</div>
        <div className="status-badge"><div className="dot green"></div>Systems Connected</div>
      </header>
      <main className="page-wrapper">
        <h1 className="title-text">Welcome to Budget Buddies!</h1>
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
        <div><strong>Budget Buddies</strong> • Powered by Jetson</div>
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
  const [wsStatus, setWsStatus] = useState<'connected' | 'offline' | 'reconnecting'>('offline');
  const [pulsingItem, setPulsingItem] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);

  const connectWebSocket = () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/cart`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.inventory) setInventory(data.inventory);
        if (data.action === 'VISION_ADD' && data.item) {
          setPulsingItem(data.item);
          setTimeout(() => setPulsingItem(null), 500);
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = () => {
      setWsStatus('reconnecting');
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
    }
    if (action === 'MANUAL_REMOVE' && item && inventory[item] > 0) {
      setInventory(prev => ({ ...prev, [item]: prev[item] - 1 }));
    }
    if (action === 'RESET') {
      setInventory({ apple: 0, banana: 0, water: 0 });
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
      <header className="top-header">
        <div><strong>Budget Buddies</strong></div>
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
                  <div className="catalog-info">
                    <strong>{item.name}</strong>
                    <div className="item-price">${item.price.toFixed(2)}</div>
                  </div>
                  
                  <div className="controls">
                    <button className="touch-btn btn-minus" onClick={() => sendAction('MANUAL_REMOVE', key)}>–</button>
                    <span className="item-quantity">{qty}</span>
                    <button className="touch-btn btn-plus" onClick={() => sendAction('MANUAL_ADD', key)}>+</button>
                  </div>
                  
                  <div className="line-total">
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

          <div className="nutrition-card">
            <h2 className="nutrition-title">Macro Goals</h2>
            <div className="macro-progress-layout">
              <svg
                className="macro-rings"
                viewBox="0 0 260 260"
                role="img"
                aria-label={`Macro progress: ${MACRO_PROGRESS.map((macro) => `${macro.name} ${macro.current} of ${macro.goal} grams`).join(', ')}.`}
              >
                {MACRO_PROGRESS.map((macro) => {
                  const circumference = 2 * Math.PI * macro.radius;
                  const progress = Math.min(macro.current / macro.goal, 1);

                  return (
                    <g key={macro.name} transform="rotate(-90 130 130)">
                      <circle
                        cx="130"
                        cy="130"
                        r={macro.radius}
                        className="macro-ring-track"
                        stroke={macro.color}
                      />
                      <circle
                        cx="130"
                        cy="130"
                        r={macro.radius}
                        className="macro-ring-progress"
                        stroke={macro.color}
                        strokeDasharray={circumference}
                        strokeDashoffset={circumference * (1 - progress)}
                      />
                    </g>
                  );
                })}
              </svg>
              <ul className="macro-progress-list">
                {MACRO_PROGRESS.map((macro) => (
                  <li key={macro.name} className="macro-progress-item">
                    <span className="macro-progress-name">
                      <span className="macro-progress-swatch" style={{ backgroundColor: macro.color }} />
                      {macro.name}
                    </span>
                    <strong>{macro.current}/{macro.goal} g</strong>
                  </li>
                ))}
              </ul>
            </div>
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