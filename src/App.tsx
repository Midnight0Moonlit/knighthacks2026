import { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const CATALOG = {
  apples: { id: 'apples', name: '🍎 Apples', price: 1.29 },
  bananas: { id: 'bananas', name: '🍌 Bananas', price: 0.59 },
  'buffalo sauce': { id: 'buffalo sauce', name: '🌶️ Buffalo Sauce', price: 4.99 },
  'barbecue sauce': { id: 'barbecue sauce', name: '🍖 Barbecue Sauce', price: 2.49 },
  'water bottle': { id: 'water bottle', name: '💦 Water Bottle', price: 1.99 },
} as const;

type ItemKey = keyof typeof CATALOG;
type MacroKey = 'protein' | 'carbs' | 'fat';
type DietaryRestrictionOption = { id: string; label: string };

const CAMERA_ITEM_ALIASES: Record<string, ItemKey> = {
  apple: 'apples',
  apples: 'apples',
  banana: 'bananas',
  bananas: 'bananas',
  bottle: 'water bottle',
  bottles: 'water bottle',
  water: 'water bottle',
  'water bottle': 'water bottle',
  'water bottles': 'water bottle',
  'buffalo sauce': 'buffalo sauce',
  'buffalo sauces': 'buffalo sauce',
  'barbecue sauce': 'barbecue sauce',
  'bbq sauce': 'barbecue sauce',
  'barbeque sauce': 'barbecue sauce',
};

const ITEM_ALLERGENS: Partial<Record<ItemKey, string[]>> = {
  'buffalo sauce': ['soy'],
};

const normalizeAllergen = (value: string) => {
  const normalized = value.trim().toLowerCase().replace(/[^a-z0-9]/g, '');
  if (normalized === 'soy' || normalized === 'soybean' || normalized === 'soybeans') return 'soy';
  return normalized;
};

const getCatalogDisplayName = (item: ItemKey, showWarning: boolean) => {
  if (item === 'buffalo sauce' && showWarning) return '⚠️ Buffalo Sauce';
  return CATALOG[item].name;
};

const normalizeCatalogItemKey = (itemName: string): ItemKey | null => {
  const normalizedName = itemName.trim().toLowerCase().replace(/[_-]+/g, ' ');
  return CAMERA_ITEM_ALIASES[normalizedName] ?? null;
};

const RECIPE_PREVIEWS: {
  title: string;
  description: string;
  ingredients: ItemKey[];
  time: string;
  badge: string;
  steps: string[];
}[] = [
  {
    title: 'Apple & Banana Fruit Bowl',
    description: 'A fresh, naturally sweet snack with crisp and creamy fruit in every bite.',
    ingredients: ['apples', 'bananas'],
    time: '5 min',
    badge: 'No-cook',
    steps: ['Wash and slice the apples and bananas.', 'Arrange the fruit in a bowl and enjoy.'],
  },
  {
    title: 'Quick Buffalo Sauce',
    description: 'Serve buffalo sauce alongside a meal for a quick, flavorful kick.',
    ingredients: ['buffalo sauce'],
    time: '6 min',
    badge: 'Quick',
    steps: ['Pour the buffalo sauce into a serving dish.', 'Serve alongside your favorite prepared meal.'],
  },
  {
    title: 'Barbecue Apple Snack',
    description: 'Pair a crisp apple snack with a savory barbecue-inspired side.',
    ingredients: ['apples', 'barbecue sauce'],
    time: '5 min',
    badge: 'Snack',
    steps: ['Wash and slice the apple.', 'Serve with your prepared barbecue item.'],
  },
  {
    title: 'Buffalo Sauce with Barbecue Sauce',
    description: 'Pair buffalo sauce with barbecue sauce for a quick, savory dip.',
    ingredients: ['buffalo sauce', 'barbecue sauce'],
    time: '8 min',
    badge: 'Easy',
    steps: ['Mix the buffalo sauce and barbecue sauce to taste.', 'Serve as a dip or sauce for your favorite meal.'],
  },
  {
    title: 'Crisp Apple Snack',
    description: 'A simple, refreshing snack made with the apples in your cart.',
    ingredients: ['apples'],
    time: '2 min',
    badge: 'No-cook',
    steps: ['Wash the apple.', 'Slice and serve as a crisp snack.'],
  },
  {
    title: 'Banana Snack Plate',
    description: 'A quick, ready-to-eat snack using your bananas.',
    ingredients: ['bananas'],
    time: '2 min',
    badge: 'No-cook',
    steps: ['Peel the banana.', 'Slice or enjoy whole.'],
  },
];

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
const MOCK_CAMERA_INVENTORY_URL = '/mock_camera_inventory.json';

const fetchJson = async (url: string, options?: RequestInit) => {
  console.log(`[frontend] fetch ${url} ${options ? 'with payload' : 'without payload'}`);
  const response = await fetch(url, options);
  console.log(`[frontend] response from ${url}: status=${response.status}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
};

const buildInventoryFromStore = (foods: Record<string, unknown> = {}) => {
  const base = {
    apples: 0,
    bananas: 0,
    'buffalo sauce': 0,
    'barbecue sauce': 0,
    'water bottle': 0,
  } as Record<ItemKey, number>;
  for (const [itemName, quantity] of Object.entries(foods)) {
    const key = normalizeCatalogItemKey(itemName);
    const parsedQuantity = Number(quantity);
    if (key && Number.isFinite(parsedQuantity) && parsedQuantity > 0) {
      const nextQuantity = base[key] + Math.floor(parsedQuantity);
      base[key] = key === 'barbecue sauce' || key === 'buffalo sauce'
        ? Math.min(nextQuantity, 1)
        : nextQuantity;
    }
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
        <div className="brand-lockup">
          <img className="header-logo" src="/s_logo_cream.png" alt="" aria-hidden="true" />
          <strong>Sophro Shoppers</strong>
        </div>
      </header>
      <main className="page-wrapper">
        <img className="start-page-logo" src="/s_logo_green.png" alt="" aria-hidden="true" />
        <button className="giant-start-btn" onClick={() => navigate('/dietary-restrictions')}>START SHOPPING</button>
      </main>
    </>
  );
}

function DietaryRestrictionsPage() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<DietaryRestrictionOption[]>([]);
  const [selectedRestrictions, setSelectedRestrictions] = useState<string[]>([]);
  const [otherRestrictions, setOtherRestrictions] = useState<string[]>([]);
  const [otherRestrictionInput, setOtherRestrictionInput] = useState('');
  const [isOtherEntryOpen, setIsOtherEntryOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setErrorMessage('');

    fetchJson('/api/brain')
      .then(async (brainData) => {
        const available = brainData?.available_dietary_restrictions;
        if (!Array.isArray(available) || available.some(
          (option) => typeof option?.id !== 'string' || typeof option?.label !== 'string',
        )) {
          throw new Error('The backend returned an invalid dietary restrictions list.');
        }

        const selected = brainData?.dietary_restrictions;
        if (!Array.isArray(selected) || selected.some((id) => typeof id !== 'string')) {
          throw new Error('The backend returned invalid saved dietary restrictions.');
        }

        const otherSelected = brainData?.other_dietary_restrictions;
        if (!Array.isArray(otherSelected) || otherSelected.some((name) => typeof name !== 'string')) {
          throw new Error('The backend returned invalid other dietary restrictions.');
        }

        if (isActive) {
          setOptions(available);
          setSelectedRestrictions([]);
          setOtherRestrictions([]);
          setIsOtherEntryOpen(false);
        }

        await fetchJson('/api/brain/dietary-restrictions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dietary_restrictions: [],
            other_dietary_restrictions: [],
          }),
        });
      })
      .catch((error: unknown) => {
        console.error('[frontend] could not load dietary restrictions', error);
        if (isActive) {
          setErrorMessage('Could not load dietary restrictions. Please try again.');
        }
      })
      .finally(() => {
        if (isActive) setIsLoading(false);
      });

    return () => {
      isActive = false;
    };
  }, [loadAttempt]);

  const toggleRestriction = (restrictionId: string) => {
    setSelectedRestrictions((current) => (
      current.includes(restrictionId)
        ? current.filter((id) => id !== restrictionId)
        : [...current, restrictionId]
    ));
  };

  const addOtherRestriction = () => {
    const restriction = otherRestrictionInput.trim().replace(/\s+/g, ' ');
    if (!restriction) return;
    if (restriction.length > 80) {
      setErrorMessage('Allergy names must be 80 characters or fewer.');
      return;
    }
    if (otherRestrictions.some((existing) => existing.toLocaleLowerCase() === restriction.toLocaleLowerCase())) {
      setErrorMessage('That allergy is already on your list.');
      return;
    }

    setErrorMessage('');
    setOtherRestrictions((current) => [...current, restriction]);
    setOtherRestrictionInput('');
  };

  const toggleOtherRestrictions = () => {
    setIsOtherEntryOpen((isOpen) => {
      if (isOpen) {
        setOtherRestrictions([]);
        setOtherRestrictionInput('');
      }
      return !isOpen;
    });
  };

  const continueToBudget = async () => {
    setIsSaving(true);
    setErrorMessage('');
    try {
      await fetchJson('/api/brain/dietary-restrictions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dietary_restrictions: selectedRestrictions,
          other_dietary_restrictions: otherRestrictions,
        }),
      });
      navigate('/budget');
    } catch (error) {
      console.error('[frontend] could not save dietary restrictions', error);
      setErrorMessage('Could not save your choices. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <header className="top-header">
        <div className="brand-lockup">
          <img className="header-logo" src="/s_logo_cream.png" alt="" aria-hidden="true" />
          <strong>Sophro Shoppers</strong>
        </div>
      </header>
      <main className="page-wrapper dietary-page-wrapper">
        <section className="budget-card dietary-card" aria-labelledby="dietary-title">
          <h1 className="dietary-title" id="dietary-title">Dietary restrictions</h1>
          {isLoading ? (
            <p className="dietary-status" role="status">Loading dietary options…</p>
          ) : errorMessage && options.length === 0 ? (
            <div className="dietary-load-error">
              <p className="dietary-error" role="alert">{errorMessage}</p>
              <button className="dietary-retry-button" type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="dietary-choice-grid" aria-label="Common food allergens">
                {options.map((option) => {
                  const isSelected = selectedRestrictions.includes(option.id);
                  return (
                    <button
                      className={`dietary-choice${isSelected ? ' is-selected' : ''}`}
                      type="button"
                      key={option.id}
                      aria-pressed={isSelected}
                      onClick={() => toggleRestriction(option.id)}
                    >
                      {option.label}
                    </button>
                  );
                })}
                <button
                  className={`dietary-choice dietary-other-choice${isOtherEntryOpen ? ' is-selected' : ''}`}
                  type="button"
                  aria-expanded={isOtherEntryOpen}
                  aria-pressed={isOtherEntryOpen}
                  onClick={toggleOtherRestrictions}
                >
                  Others
                </button>
              </div>
              {isOtherEntryOpen && (
                <div className="other-allergy-entry">
                  <label htmlFor="other-allergy-input">Add another allergy</label>
                  <div className="other-allergy-input-row">
                    <input
                      id="other-allergy-input"
                      type="text"
                      maxLength={80}
                      value={otherRestrictionInput}
                      onChange={(event) => setOtherRestrictionInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          addOtherRestriction();
                        }
                      }}
                      placeholder="Enter allergy"
                    />
                    <button type="button" onClick={addOtherRestriction} disabled={!otherRestrictionInput.trim()}>
                      Add
                    </button>
                  </div>
                  {otherRestrictions.length > 0 && (
                    <ul className="other-allergy-list" aria-label="Added allergies">
                      {otherRestrictions.map((restriction) => (
                        <li key={restriction}>
                          <span>{restriction}</span>
                          <button
                            type="button"
                            aria-label={`Remove ${restriction}`}
                            onClick={() => setOtherRestrictions((current) => current.filter((item) => item !== restriction))}
                          >
                            ×
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </>
          )}
        </section>
        {errorMessage && options.length > 0 && <p className="dietary-error" role="alert">{errorMessage}</p>}
        <button
          className="budget-btn dietary-continue-btn"
          type="button"
          disabled={isLoading || options.length === 0 || isSaving}
          onClick={continueToBudget}
        >
          {isSaving ? 'Saving…' : selectedRestrictions.length === 0 && !isOtherEntryOpen ? 'Skip' : 'Continue'}
        </button>
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
        <div className="brand-lockup">
          <img className="header-logo" src="/s_logo_cream.png" alt="" aria-hidden="true" />
          <strong>Sophro Shoppers</strong>
        </div>
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
    'buffalo sauce': 0,
    'barbecue sauce': 0,
    'water bottle': 0,
  });
  const [macroProgress, setMacroProgress] = useState<MacroProgress[]>(DEFAULT_MACRO_GOALS);
  const [dietaryRestrictionIds, setDietaryRestrictionIds] = useState<string[]>([]);
  const [otherDietaryRestrictions, setOtherDietaryRestrictions] = useState<string[]>([]);
  const [pendingAllergenWarning, setPendingAllergenWarning] = useState<{
    item: ItemKey;
    allergens: string[];
  } | null>(null);
  const [allergenWarningError, setAllergenWarningError] = useState('');
  const [acceptedAllergenItems, setAcceptedAllergenItems] = useState<ItemKey[]>([]);
  const [macroLoadStatus, setMacroLoadStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [macroLoadError, setMacroLoadError] = useState('');
  const [pendingMacroItems, setPendingMacroItems] = useState<string[]>([]);
  const [recipePreference, setRecipePreference] = useState('');
  const [isRecipeMode, setIsRecipeMode] = useState(false);
  const [recipeIndex, setRecipeIndex] = useState(0);
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
  const cameraInventorySignatureRef = useRef('');
  const recipeSwipeStartRef = useRef<{ x: number; y: number } | null>(null);

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
            setPendingMacroItems([]);
            setMacroLoadStatus('ready');
            return;
          }
          if (payload?.status === 'pending') {
            setPendingMacroItems(payload.pending_items ?? []);
          }
          if (payload?.status === 'error') {
            setPendingMacroItems(payload.pending_items ?? []);
            setMacroLoadError(payload.error || 'Could not load macros from Gemini.');
            setMacroLoadStatus('error');
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

  const refreshBrainData = async (acceptEmptyInventory = false) => {
    try {
      const brainData = await fetchJson('/api/brain');
      const foodStore = brainData?.foods ?? {};
      console.log('[frontend] received brain data', brainData);
      setDietaryRestrictionIds(
        Array.isArray(brainData?.dietary_restrictions)
          ? brainData.dietary_restrictions.filter((restriction: unknown): restriction is string => typeof restriction === 'string')
          : [],
      );
      setOtherDietaryRestrictions(
        Array.isArray(brainData?.other_dietary_restrictions)
          ? brainData.other_dietary_restrictions.filter((restriction: unknown): restriction is string => typeof restriction === 'string')
          : [],
      );
      const backendInventory = buildInventoryFromStore(foodStore);
      const hasBackendInventory = Object.values(backendInventory).some((quantity) => quantity > 0);
      if (acceptEmptyInventory || hasBackendInventory) {
        setInventory(backendInventory);
      }
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

  const loadMockCameraInventory = async () => {
    try {
      const cameraInventory = await fetchJson(`${MOCK_CAMERA_INVENTORY_URL}?t=${Date.now()}`);
      if (!cameraInventory || typeof cameraInventory !== 'object' || Array.isArray(cameraInventory)) {
        throw new Error('Mock camera inventory must be a JSON object of item counts.');
      }
      const inventoryFromFixture = buildInventoryFromStore(cameraInventory);
      const signature = JSON.stringify(cameraInventory);
      if (signature === cameraInventorySignatureRef.current) return;
      cameraInventorySignatureRef.current = signature;
      setInventory(inventoryFromFixture);

      await Promise.all(
        (Object.keys(CATALOG) as ItemKey[]).map((item) =>
          fetchJson('/api/brain/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              item,
              quantity: inventoryFromFixture[item] ?? 0,
              operation: 'set',
            }),
          }).catch((error) => {
            console.error(`[frontend] could not sync camera item ${item}`, error);
          }),
        ),
      );
    } catch (error) {
      console.error('[frontend] could not load mock camera inventory', error);
    }
  };

  const connectWebSocket = () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/cart`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;


    ws.onmessage = (event) => {
      try {
        const parsedMessage: unknown = JSON.parse(event.data);
        if (!parsedMessage || typeof parsedMessage !== 'object' || Array.isArray(parsedMessage)) {
          throw new Error('Camera message must be a JSON object.');
        }
        const data = parsedMessage as Record<string, unknown>;
        const cameraInventory = data.inventory ?? data.cart_snapshot;
        if (cameraInventory && typeof cameraInventory === 'object' && !Array.isArray(cameraInventory)) {
          setInventory(buildInventoryFromStore(cameraInventory as Record<string, unknown>));
        }
        const isCameraAddition = data.action === 'VISION_ADD' || data.event === 'ADD';
        const itemKey = typeof data.item === 'string' ? normalizeCatalogItemKey(data.item) : null;
        if (isCameraAddition && itemKey) {
          setPulsingItem(itemKey);
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
    const cameraInventoryPoller = window.setInterval(() => {
      void loadMockCameraInventory();
    }, 1000);
    fetchJson('/api/cart/entered', { method: 'POST' })
      .then(() => refreshBrainData())
      .then(() => loadMockCameraInventory())
      .catch((error) => {
        console.error('[frontend] could not register cart entry', error);
        setMacroLoadStatus('error');
        setMacroLoadError('Could not start nutrition lookups. Please reload the cart.');
    });
    connectWebSocket();
    return () => {
      window.clearInterval(cameraInventoryPoller);
      wsRef.current?.close();
    };
  }, []);

  const getMatchingItemAllergens = (item: ItemKey) => {
    const restrictedAllergens = new Set([
      ...dietaryRestrictionIds,
      ...otherDietaryRestrictions,
    ].map(normalizeAllergen));
    return (ITEM_ALLERGENS[item] ?? [])
      .filter((allergen) => restrictedAllergens.has(normalizeAllergen(allergen)))
      .map((allergen) => allergen === 'soy' ? 'Soy' : allergen);
  };

  useEffect(() => {
    if (pendingAllergenWarning || acceptedAllergenItems.length > 0) return;

    const warningItem = (Object.keys(CATALOG) as ItemKey[]).find(
      (item) => inventory[item] > 0 && getMatchingItemAllergens(item).length > 0,
    );
    if (!warningItem) return;

    setAllergenWarningError('');
    setPendingAllergenWarning({
      item: warningItem,
      allergens: getMatchingItemAllergens(warningItem),
    });
  }, [
    acceptedAllergenItems.length,
    dietaryRestrictionIds,
    inventory,
    otherDietaryRestrictions,
    pendingAllergenWarning,
  ]);

  const sendAction = async (action: string, item?: ItemKey, acceptAllergenWarning = false) => {
    if (action === 'MANUAL_ADD' && item && !acceptAllergenWarning && !acceptedAllergenItems.includes(item)) {
      const allergens = getMatchingItemAllergens(item);
      if (allergens.length > 0) {
        setPendingAllergenWarning({ item, allergens });
        setAllergenWarningError('');
        return;
      }
    }

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
      const brainData = await fetchJson('/api/brain/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item, quantity: 1, operation: 'subtract' }),
      });
      if (Number(brainData?.foods?.[item] ?? 0) === 0) {
        setAcceptedAllergenItems((accepted) => accepted.filter((acceptedItem) => acceptedItem !== item));
      }
    }
    if (action === 'MANUAL_ADD' && item && acceptAllergenWarning) {
      setAcceptedAllergenItems((accepted) => accepted.includes(item) ? accepted : [...accepted, item]);
    }
    if (action === 'RESET') {
      console.log('[frontend] resetting cart');
      setAcceptedAllergenItems([]);
      setPendingAllergenWarning(null);
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

    await refreshBrainData(true);
  };

  const acceptPendingAllergenWarning = async () => {
    const item = pendingAllergenWarning?.item;
    if (!item) return;
    setAllergenWarningError('');
    try {
      await sendAction('MANUAL_ADD', item, true);
      setPendingAllergenWarning(null);
    } catch (error) {
      console.error('[frontend] could not add allergen-warning item after acceptance', error);
      setAllergenWarningError('Could not add this item. Please try again.');
    }
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
  const availableRecipes = RECIPE_PREVIEWS.filter((recipe) =>
    recipe.ingredients.every((item) => inventory[item] > 0),
  );
  const selectedRecipeIndex = availableRecipes.length > 0
    ? recipeIndex % availableRecipes.length
    : 0;
  const selectedRecipe = availableRecipes[selectedRecipeIndex];

  const showRecipe = (direction: -1 | 1) => {
    if (availableRecipes.length < 2) return;
    setRecipeIndex((current) => (
      (current + direction + availableRecipes.length) % availableRecipes.length
    ));
  };

  const handleRecipeSwipe = (x: number, y: number) => {
    const start = recipeSwipeStartRef.current;
    recipeSwipeStartRef.current = null;
    if (!start) return;

    const horizontalDistance = x - start.x;
    const verticalDistance = y - start.y;
    if (Math.abs(horizontalDistance) < 45 || Math.abs(horizontalDistance) < Math.abs(verticalDistance) * 1.2) {
      return;
    }
    showRecipe(horizontalDistance < 0 ? 1 : -1);
  };

  return (
    <>
      <header className="top-header">
        <div className="brand-lockup">
          <img className="header-logo" src="/s_logo_cream.png" alt="" aria-hidden="true" />
          <strong>Sophro Shoppers</strong>
        </div>
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

      <main className={`dashboard${isRecipeMode ? ' recipe-mode' : ''}`}>
        <div className={`receipt-card budget-overview${isRecipeMode ? ' recipe-budget-overview' : ''}`}>
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
            <div className="no-budget-message">No Budget Set</div>
          )}
        </div>
        <div className="catalog-panel">
          {isRecipeMode ? (
            <section className="recipe-inventory" aria-labelledby="recipe-inventory-title">
              <div className="recipe-inventory-heading">
                <p className="recipe-eyebrow">Your ingredients</p>
                <h2 id="recipe-inventory-title">In your cart</h2>
              </div>
              {Object.entries(inventory).some(([, quantity]) => quantity > 0) ? (
                <ul className="recipe-inventory-list">
                  {(Object.keys(CATALOG) as ItemKey[])
                    .filter((key) => inventory[key] > 0)
                    .map((key) => (
                      <li className="recipe-inventory-item" key={key}>
                        <span className={acceptedAllergenItems.includes(key) ? 'allergen-accepted-name' : undefined}>
                          {getCatalogDisplayName(key, acceptedAllergenItems.includes(key))}
                        </span>
                        <span className="recipe-inventory-quantity">× {inventory[key]}</span>
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="recipe-empty-state">
                  Your cart is empty. Switch to Shopping Mode to add ingredients.
                </p>
              )}
            </section>
          ) : (
            <>
              <div className="catalog-items">
                {(Object.keys(CATALOG) as ItemKey[])
                  .filter((key) => (inventory[key] ?? 0) > 0)
                  .map((key) => {
                  const item = CATALOG[key];
                  const qty = inventory[key] ?? 0;
                  const isPulsing = pulsingItem === key;

                  return (
                    <div key={key} className={`catalog-row ${isPulsing ? 'pulse-anim' : ''}`}>
                      <div className="catalog-info">
                        <strong className={acceptedAllergenItems.includes(key) ? 'allergen-accepted-name' : undefined}>
                          {getCatalogDisplayName(key, acceptedAllergenItems.includes(key))}
                        </strong>
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
                {!Object.values(inventory).some((quantity) => quantity > 0) && (
                  <p className="recipe-empty-state">Your shopping list is empty. Add an item to begin.</p>
                )}
              </div>

              <div className="catalog-summary">
                <div className="summary-line"><span>Subtotal</span> <span>${currentSubtotal.toFixed(2)}</span></div>
                <div className="summary-line"><span>Estimated Tax (7%)</span> <span>${currentTax.toFixed(2)}</span></div>
                <div className="summary-line summary-total" style={{ color: isOverBudget ? '#e74c3c' : '#2c3e50' }}>
                  <span>Total</span>
                  <span>${currentTotal.toFixed(2)}</span>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="receipt-panel">
          {!isRecipeMode && pendingAllergenWarning ? (
            <section className="allergen-warning-card" role="alert" aria-live="assertive">
              <h2>Allergy Warning</h2>
              <p>
                {CATALOG[pendingAllergenWarning.item].name.replace(/^\S+\s*/, '')} contains a dietary restriction you are trying to avoid:{' '}
                <strong>{pendingAllergenWarning.allergens.join(', ')}</strong>
              </p>
              {allergenWarningError && <p role="alert">{allergenWarningError}</p>}
              <button type="button" onClick={() => void acceptPendingAllergenWarning()}>
                Accept
              </button>
            </section>
          ) : !isRecipeMode && <div className="nutrition-card">
            <h2 className="nutrition-title">Macro Goals</h2>
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
            {macroLoadStatus === 'error' ? (
              <p className="macro-load-error" role="alert">
                {macroLoadError} Existing macro totals are still shown.
              </p>
            ) : macroLoadStatus === 'loading' ? (
              <p className="macro-load-message" role="status">
                {pendingMacroItems.length > 0
                  ? `Gathering new macros for ${pendingMacroItems.join(', ')}. Existing totals stay visible until they are ready.`
                  : 'Gathering updated macros for your cart. Existing totals stay visible until they are ready.'}
              </p>
            ) : null}
          </div>}
          {!isRecipeMode && (
            <button
              className="mode-toggle-button shopping-mode-toggle"
              type="button"
              aria-pressed={false}
              onClick={() => setIsRecipeMode(true)}
            >
              Recipe Mode
            </button>
          )}
          {isRecipeMode && (
            <button
              className="mode-toggle-button recipe-mode-toggle"
              type="button"
              aria-pressed={true}
              onClick={() => setIsRecipeMode(false)}
            >
              Shopping Mode
            </button>
          )}
          {isRecipeMode && <section className="recipe-card" aria-labelledby="recipe-card-title">
            <div className="recipe-card-heading">
              <div>
                <p className="recipe-eyebrow">Made for your cart</p>
                <h2 className="nutrition-title" id="recipe-card-title">Recipe</h2>
              </div>
            </div>
            <label className="recipe-preference-label" htmlFor="recipe-preference">
              What sounds good?
            </label>
            <input
              className="recipe-preference-input"
              id="recipe-preference"
              type="text"
              value={recipePreference}
              onChange={(event) => setRecipePreference(event.target.value)}
              placeholder="e.g. quick, vegetarian, high-protein"
            />

            {selectedRecipe ? (
              <div
                className="recipe-swipe-area is-swipe-enabled"
                role="region"
                aria-label="Swipeable recipe suggestions"
                aria-live="polite"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'ArrowRight') showRecipe(1);
                  if (event.key === 'ArrowLeft') showRecipe(-1);
                }}
                onPointerDown={(event) => {
                  if (event.pointerType === 'touch') return;
                  event.currentTarget.setPointerCapture(event.pointerId);
                  recipeSwipeStartRef.current = { x: event.clientX, y: event.clientY };
                }}
                onPointerUp={(event) => {
                  if (event.pointerType === 'touch') return;
                  handleRecipeSwipe(event.clientX, event.clientY);
                }}
                onPointerCancel={(event) => {
                  if (event.pointerType !== 'touch') recipeSwipeStartRef.current = null;
                }}
                onTouchStart={(event) => {
                  const touch = event.touches[0];
                  if (touch) recipeSwipeStartRef.current = { x: touch.clientX, y: touch.clientY };
                }}
                onTouchEnd={(event) => {
                  const touch = event.changedTouches[0];
                  if (touch) handleRecipeSwipe(touch.clientX, touch.clientY);
                }}
                onTouchCancel={() => {
                  recipeSwipeStartRef.current = null;
                }}
              >
                <article className="recipe-featured recipe-featured-large" key={selectedRecipe.title}>
                  <div className="recipe-featured-topline">
                    <span className="recipe-badge">{selectedRecipe.badge}</span>
                    <span className="recipe-time">⏱ {selectedRecipe.time}</span>
                  </div>
                  <p className="recipe-eyebrow">A little inspiration</p>
                  <h3>{selectedRecipe.title}</h3>
                  <p className="recipe-featured-description">{selectedRecipe.description}</p>
                  <div className="recipe-ingredients">
                    {selectedRecipe.ingredients.map((item) => (
                      <span className="recipe-ingredient" key={item}>
                        {CATALOG[item].name}
                      </span>
                    ))}
                  </div>
                  <div className="recipe-directions">
                    <h4>Quick steps</h4>
                    <ol>
                      {selectedRecipe.steps.map((step) => <li key={step}>{step}</li>)}
                    </ol>
                  </div>
                </article>
              </div>
            ) : (
              <p className="recipe-empty-state">
                Add apples, bananas, buffalo sauce, or barbecue sauce in Shopping Mode to discover ideas for your cart.
              </p>
            )}
            {availableRecipes.length > 1 && (
              <div className="recipe-navigation" aria-label="Recipe navigation">
                <button type="button" onClick={() => showRecipe(-1)} aria-label="Previous recipe">←</button>
                <span>{selectedRecipeIndex + 1} / {availableRecipes.length}</span>
                <button type="button" onClick={() => showRecipe(1)} aria-label="Next recipe">→</button>
              </div>
            )}
          </section>}
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
          <Route path="/dietary-restrictions" element={<DietaryRestrictionsPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/cart" element={<CartDashboard />} />
        </Routes>
      </Router>
    </div>
  );
}