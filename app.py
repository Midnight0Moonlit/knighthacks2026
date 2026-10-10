import threading
import time

from flask import Flask, jsonify, request

from brain import Brain
from gemini import get_item_macros_for_names

app = Flask(__name__)
brain = Brain("brain.json")

ai_thread = None
ai_lock = threading.Lock()


def _start_ai_worker_if_needed():
    global ai_thread
    pending_items = brain.get_pending_items()
    if not pending_items:
        return

    if ai_thread is not None and ai_thread.is_alive():
        print(f"[app] AI worker already running for pending items: {pending_items}")
        return

    ai_thread = threading.Thread(target=_process_pending_item_macros, daemon=True)
    ai_thread.start()
    print(f"[app] started AI nutrition worker for pending items: {pending_items}")


def _process_pending_item_macros():
    global ai_thread
    print("[app] AI nutrition worker started")

    try:
        while True:
            pending_items = brain.get_pending_items()
            if not pending_items:
                print("[app] no pending nutrition items; worker exiting")
                break

            last_ai_run = brain.get_last_ai_run()
            elapsed_since_last_ai = time.time() - last_ai_run
            if elapsed_since_last_ai < 60:
                wait_time = 60 - elapsed_since_last_ai
                print(f"[app] AI throttle active; waiting {wait_time:.1f}s before processing {pending_items}")
                time.sleep(wait_time)

            pending_items = brain.get_pending_items()
            if not pending_items:
                print("[app] pending items cleared before AI call")
                break

            print(f"[app] asking Gemini for new item macros: {pending_items}")
            nutrition_updates = get_item_macros_for_names(pending_items)
            if nutrition_updates:
                brain.apply_ai_nutrition(nutrition_updates)
            brain.set_last_ai_run(time.time())
            print(f"[app] AI nutrition update saved to brain: {nutrition_updates}")
            break
    finally:
        ai_thread = None


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/brain")
def get_brain():
    response = brain.get_all()
    print(f"[app] GET /api/brain -> {response}")
    return jsonify(response)


@app.post("/api/brain/items")
def update_items():
    payload = request.get_json(silent=True) or {}
    item = payload.get("item")
    if not item:
        return jsonify({"error": "Missing item name."}), 400

    operation = payload.get("operation", "add")
    quantity = int(payload.get("quantity", 1))
    print(f"[app] updating inventory: item={item}, operation={operation}, quantity={quantity}")

    if operation == "set":
        brain.set_item(item, quantity)
    elif operation == "add":
        brain.add_item(item, quantity)
    elif operation == "subtract":
        brain.update_item_count(item, -abs(quantity))
    elif operation == "remove":
        brain.remove_item(item)
    else:
        return jsonify({"error": "Unsupported operation."}), 400

    if brain.get_pending_items():
        _start_ai_worker_if_needed()

    print(f"[app] inventory changed -> new brain state: {brain.get_all()}")
    return jsonify(brain.get_all())


@app.post("/api/brain/budget")
def set_budget():
    payload = request.get_json(silent=True) or {}
    budget = payload.get("budget", brain.get_budget())
    print(f"[app] setting budget to {budget}")
    brain.set_budget(float(budget))
    return jsonify(brain.get_all())


@app.get("/api/macros")
def macros():
    pending_items = brain.get_pending_items()
    if pending_items:
        _start_ai_worker_if_needed()

    totals = brain.get_macro_totals()
    print(f"[app] /api/macros -> {totals}, pending={pending_items}")
    return jsonify({"status": "ready", **totals})


if __name__ == "__main__":
    port = 5001
    print(f"[app] starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
