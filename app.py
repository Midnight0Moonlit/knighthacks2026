from flask import Flask, jsonify, request

from brain import Brain
from gemini import get_item_macros_for_names
from nutrition_scheduler import NutritionScheduler

app = Flask(__name__)
brain = Brain("brain.json")

nutrition_scheduler = NutritionScheduler(brain, get_item_macros_for_names)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/brain")
def get_brain():
    response = brain.get_all()
    print(f"[app] GET /api/brain -> {response}")
    return jsonify(response)


@app.post("/api/cart/entered")
def cart_entered():
    nutrition_scheduler.enter_cart()
    return jsonify({
        "status": "ok",
        "grace_period_seconds": nutrition_scheduler.cart_grace_seconds,
        "minimum_interval_seconds": nutrition_scheduler.minimum_interval_seconds,
    })


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

    if operation == "add" or (operation == "set" and quantity > 0):
        nutrition_scheduler.inventory_changed()

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
        totals = brain.get_macro_totals()
        error = nutrition_scheduler.get_error()
        status = "error" if error else "pending"
        return jsonify({
            "status": status,
            "pending_items": pending_items,
            "error": error,
            "retry_after_seconds": nutrition_scheduler.get_retry_after(),
            **totals,
        })

    totals = brain.get_macro_totals()
    print(f"[app] /api/macros -> {totals}, pending={pending_items}")
    return jsonify({"status": "ready", **totals})


if __name__ == "__main__":
    port = 5001
    print(f"[app] starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
