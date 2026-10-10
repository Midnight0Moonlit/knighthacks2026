import { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const CATALOG = {
  apples: { id: 'apples', name: '🍎 Apples', price: 1.29 },
  bananas: { id: 'bananas', name: '🍌 Bananas', price: 0.59 },
  beans: { id: 'beans', name: '🫘 Beans', price: 1.29 },
  donuts: { id: 'donuts', name: '🍩 Donuts', price: 1.25 },
  'water bottle': { id: 'water bottle', name: '💦 Water Bottle', price: 1.99 },
} as const;

type ItemKey = keyof typeof CATALOG;
type MacroKey = 'protein' | 'carbs' | 'fat';

type MacroProgress = {
  key: MacroKey;
  name: string;
  current: number;
  goal: number;
  color: string;
  radius: number;
};

const DEFAULT_MACRO_GOALS: MacroProgress[] = [
  { key: 'protein', name: 'Protein', current: 0, goal: 120, color: '#f5c542', radius: 108 },
  { key: 'carbs', name: 'Carbs', current: 0, goal: 250, color: '#42bda0', radius: 81 },
  { key: 'fat', name: 'Fat', current: 0, goal: 65, color: '#ed8068', radius: 54 },
];

const DEFAULT_GOALS: Record<MacroKey, number> = { protein: 120, carbs: 250, fat: 65 };

const fetchJson = async (url: string, options?: RequestInit) => {
  console.log(`[frontend] fetch ${url} ${options ? 'with payload' : 'without payload'}`);
  const response = await fetch(url, options);
  console.log(`[frontend] response from ${url}: status=${response.status}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
};

const buildInventoryFromStore = (foods: Record<string, number> = {}) => {
  const base = { apples: 0, bananas: 0, beans: 0, donuts: 0, 'water bottle': 0 } as Record<ItemKey, number>;
  for (const key of Object.keys(base) as ItemKey[]) {
    base[key] = Number(foods[key] ?? 0);
  }
  return base;
};

const normalizeMacroProgress = (payload: any, goals: Record<MacroKey, number>): MacroProgress[] => {
  const totals = payload?.totals ?? { carbs: 0, protein: 0, fat: 0 };
  const order = [
    { name: 'Protein', key: 'protein' as const, color: '#f5c542', radius: 108 },
    { name: 'Carbs', key: 'carbs' as const, color: '#42bda0', radius: 81 },
    { name: 'Fat', key: 'fat' as const, color: '#ed8068', radius: 54 },
  ];

  return order.map((macro) => ({
    key: macro.key,
    name: macro.name,
    current: Number(totals[macro.key] ?? 0),
    goal: goals[macro.key],
    color: macro.color,
    radius: macro.radius,
  }));
};

function StartPage() {
  const navigate = useNavigate();
  return (
    <>
      <header className="top-header">
        <div><strong>Budget Buddies</strong></div>
      </header>
      <main className="page-wrapper">
        <button className="giant-start-btn" onClick={() => navigate('/budget')}>START SHOPPING</button>
      </main>
    </>
  );
}

function BudgetPage() {
  const navigate = useNavigate();
  const [budget, setBudget] = useState('50.00');

  const startShopping = async () => {
    const parsedBudget = parseFloat(budget) || 0;
    console.log(`[frontend] saving budget ${parsedBudget}`);

    try {
      await fetchJson('/api/brain/budget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ budget: parsedBudget }),
      });
    } catch (error) {
      console.warn('[frontend] budget API unavailable; continuing to cart page anyway', error);
    }

    navigate('/cart', { state: { budget: parsedBudget } });
  };

  return (
    <>
      <header className="top-header">
        <div><strong>Budget Buddies</strong></div>
      </header>
      <main className="page-wrapper">
        <div className="budget-card">
          <div className="budget-label">ENTER BUDGET</div>
          <div className="budget-input-wrapper">
            $ <input type="number" className="budget-input" value={budget} onChange={(e) => setBudget(e.target.value)} autoFocus />
          </div>
        </div>
        <button className="budget-btn" onClick={startShopping}>BEGIN</button>
      </main>
    </>
  );
}

function CartDashboard() {
  const location = useLocation();
  const [budget, setBudget] = useState<number>(Number(location.state?.budget ?? 0));
  const [budgetInput, setBudgetInput] = useState(String(Number(location.state?.budget ?? 0)));
  const [inventory, setInventory] = useState<Record<ItemKey, number>>({
    apples: 0,
    bananas: 0,
    beans: 0,
    donuts: 0,
    'water bottle': 0,
  });
  const [macroProgress, setMacroProgress] = useState<MacroProgress[]>(DEFAULT_MACRO_GOALS);
  const [macroLoadStatus, setMacroLoadStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [macroLoadError, setMacroLoadError] = useState('');
  const [macroGoalInputs, setMacroGoalInputs] = useState<Record<MacroKey, string>>({
    protein: String(DEFAULT_GOALS.protein),
    carbs: String(DEFAULT_GOALS.carbs),
    fat: String(DEFAULT_GOALS.fat),
  });
  const [isPageSettingsOpen, setIsPageSettingsOpen] = useState(false);
  const macroGoals: Record<MacroKey, number> = {
    protein: macroProgress.find((macro) => macro.key === 'protein')?.goal ?? DEFAULT_GOALS.protein,
    carbs: macroProgress.find((macro) => macro.key === 'carbs')?.goal ?? DEFAULT_GOALS.carbs,
    fat: macroProgress.find((macro) => macro.key === 'fat')?.goal ?? DEFAULT_GOALS.fat,
  };
  const [settingsError, setSettingsError] = useState('');
  const [pulsingItem, setPulsingItem] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const macroPollingRef = useRef(false);

  const loadMacrosAsync = async () => {
    if (macroPollingRef.current) return;
    macroPollingRef.current = true;
    console.log('[frontend] requesting macro totals from backend');
    setMacroLoadStatus('loading');
    setMacroLoadError('');

    try {
      while (true) {
        try {
          const payload = await fetchJson('/api/macros');
          console.log('[frontend] macro payload:', payload);

          if (payload?.status === 'ready') {
            setMacroProgress(normalizeMacroProgress(payload, macroGoals));
            setMacroLoadStatus('ready');
            return;
          }
          if (payload?.status === 'error') {
            setMacroLoadStatus('error');
            setMacroLoadError(payload.error || 'Could not load macros from Gemini.');
            return;
          }
        } catch (error) {
          console.error('[frontend] macro fetch failed; retrying', error);
        }

        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    } finally {
      macroPollingRef.current = false;
    }
  };

  const refreshBrainData = async () => {
    try {
      const brainData = await fetchJson('/api/brain');
      const foodStore = brainData?.foods ?? {};
      console.log('[frontend] received brain data', brainData);
      setInventory(buildInventoryFromStore(foodStore));
      const loadedBudget = Number(brainData?.budget ?? 0);
      setBudget(loadedBudget);
      setBudgetInput(String(loadedBudget));
    } catch (error) {
      console.error('[frontend] could not load brain data', error);
    }

    void loadMacrosAsync().catch((error) => {
      console.error('[frontend] macro polling failed', error);
    });
  };

  const connectWebSocket = () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/cart`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;


    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.inventory) setInventory(buildInventoryFromStore(data.inventory));
        if (data.action === 'VISION_ADD' && data.item) {
          setPulsingItem(data.item);
          setTimeout(() => setPulsingItem(null), 500);
        }
      } catch (err) {
        console.error('Failed to parse WS message', err);
      }
    };

    ws.onerror = () => ws.close();
  };

  useEffect(() => {
    console.log('[frontend] CartDashboard mounted');
    fetchJson('/api/cart/entered', { method: 'POST' })
      .then(() => refreshBrainData())
      .catch((error) => {
        console.error('[frontend] could not register cart entry', error);
        setMacroLoadStatus('error');
        setMacroLoadError('Could not start nutrition lookups. Please reload the cart.');
    });
    connectWebSocket();
    return () => wsRef.current?.close();
  }, []);

  const sendAction = async (action: string, item?: ItemKey) => {
    if (action === 'MANUAL_ADD' && item) {
      console.log(`[frontend] manual add ${item}`);
      await fetchJson('/api/brain/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item, quantity: 1, operation: 'add' }),
      });
    }
    if (action === 'MANUAL_REMOVE' && item) {
      console.log(`[frontend] manual remove ${item}`);
      await fetchJson('/api/brain/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item, quantity: 1, operation: 'subtract' }),
      });
    }
    if (action === 'RESET') {
      console.log('[frontend] resetting cart');
      for (const key of Object.keys(CATALOG) as ItemKey[]) {
        await fetchJson('/api/brain/items', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item: key, quantity: 0, operation: 'set' }),
        });
      }
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, item }));
    }

    await refreshBrainData();
  };

  const saveSettings = async () => {
    const nextBudget = Number(budgetInput);
    const nextGoals = {
      protein: Number(macroGoalInputs.protein),
      carbs: Number(macroGoalInputs.carbs),
      fat: Number(macroGoalInputs.fat),
    };
    if (!Number.isFinite(nextBudget) || nextBudget < 0
      || Object.values(nextGoals).some((goal) => !Number.isFinite(goal) || goal <= 0)) {
      setSettingsError('Enter a valid budget and positive macro goals before saving.');
      return;
    }

    try {
      await fetchJson('/api/brain/budget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ budget: nextBudget }),
      });
      setBudget(nextBudget);
      setMacroProgress((current) => current.map((macro) => ({
        ...macro,
        goal: nextGoals[macro.key],
      })));
      setSettingsError('');
      setIsPageSettingsOpen(false);
    } catch (error) {
      console.error('[frontend] could not save updated budget', error);
      setSettingsError('Could not save settings. Please try again.');
    }
  };

  const currentSubtotal = (Object.keys(CATALOG) as ItemKey[]).reduce((acc, key) => {
    const qty = inventory[key] ?? 0;
    return acc + CATALOG[key].price * qty;
  }, 0);
  const currentTax = currentSubtotal * 0.07;
  const currentTotal = currentSubtotal + currentTax;
  const isOverBudget = budget > 0 && currentTotal > budget;
  const progressPercentage = budget > 0 ? Math.min((currentTotal / budget) * 100, 100) : 0;

  return (
    <>
      <header className="top-header">
        <div><strong>Budget Buddies</strong></div>
        <div className="header-actions">
          <button className="reset-btn" onClick={() => sendAction('RESET')}>Reset Cart</button>
          <button
            className="page-settings-button"
            type="button"
            aria-label="Page settings"
            aria-expanded={isPageSettingsOpen}
            aria-controls="page-settings"
            onClick={() => setIsPageSettingsOpen((isOpen) => !isOpen)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
              <circle cx="15" cy="7" r="2" />
              <circle cx="9" cy="17" r="2" />
            </svg>
          </button>
          {isPageSettingsOpen && (
            <div className="page-settings-panel" id="page-settings" aria-label="Page settings">
              <h2>Settings</h2>
              <label className="macro-goal-field">
                <span>Budget</span>
                <span className="macro-goal-input-wrap">
                  <span>$</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={budgetInput}
                    onChange={(event) => setBudgetInput(event.target.value)}
                    aria-label="Shopping budget"
                  />
                </span>
              </label>
              <div className="settings-divider" />
              <h3>Daily macro goals</h3>
              {macroProgress.map((macro) => (
                <label className="macro-goal-field" key={macro.key}>
                  <span>{macro.name}</span>
                  <span className="macro-goal-input-wrap">
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={macroGoalInputs[macro.key]}
                      onChange={(event) => {
                        setMacroGoalInputs((current) => ({ ...current, [macro.key]: event.target.value }));
                      }}
                      onBlur={() => {
                        if (!macroGoalInputs[macro.key] || Number(macroGoalInputs[macro.key]) <= 0) {
                          setMacroGoalInputs((current) => ({ ...current, [macro.key]: String(macro.goal) }));
                        }
                      }}
                      aria-label={`${macro.name} daily goal in grams`}
                    />
                    <span>g</span>
                  </span>
                </label>
              ))}
              {settingsError && <p className="settings-error" role="alert">{settingsError}</p>}
              <button className="settings-save-button" type="button" onClick={saveSettings}>Save changes</button>
            </div>
          )}
        </div>
      </header>

      <main className="dashboard">
        <div className="catalog-panel">
          <div className="catalog-items">
            {(Object.keys(CATALOG) as ItemKey[]).map((key) => {
              const item = CATALOG[key];
              const qty = inventory[key] ?? 0;
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

                  <div className="line-total">${(item.price * qty).toFixed(2)}</div>
                </div>
              );
            })}
          </div>

          <div className="catalog-summary">
            <div className="summary-line"><span>Subtotal</span> <span>${currentSubtotal.toFixed(2)}</span></div>
            <div className="summary-line"><span>Estimated Tax (7%)</span> <span>${currentTax.toFixed(2)}</span></div>
          </div>
        </div>

        <div className="receipt-panel">
          <div className="nutrition-card">
            <h2 className="nutrition-title">Macro Goals</h2>
            {macroLoadStatus === 'error' ? (
              <p className="macro-load-error" role="alert">{macroLoadError}</p>
            ) : macroLoadStatus === 'ready' ? (
              <div className="macro-progress-layout">
                <svg
                  className="macro-rings"
                  viewBox="0 0 260 260"
                  role="img"
                  aria-label={`Macro progress: ${macroProgress.map((macro) => `${macro.name} ${macro.current} of ${macro.goal} grams`).join(', ')}.`}
                >
                  {macroProgress.map((macro) => {
                    const circumference = 2 * Math.PI * macro.radius;
                    const progress = Math.min(macro.current / macro.goal, 1);

                    return (
                      <g key={macro.name} transform="rotate(-90 130 130)">
                        <circle cx="130" cy="130" r={macro.radius} className="macro-ring-track" stroke={macro.color} />
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
                  {macroProgress.map((macro) => (
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
            ) : (
              <p className="macro-load-message">
                Looking up nutrition for your cart. Foods added during a lookup are checked in the next batch.
              </p>
            )}
          </div>
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