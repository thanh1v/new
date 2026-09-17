from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from copy import deepcopy
from io import BytesIO
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, session


app = Flask(__name__)
app.secret_key = os.environ.get("BAD_CYBER_SHOP_SECRET", "dev-only-bad-cyber-shop")

STARTING_MONEY = 75
FLAG_PRICE = 1000

PRODUCTS = {
    "Eevee": {"price": 10, "sell": 8},
    "Chikorita": {"price": 25, "sell": 16},
    "Pachirisu": {"price": 50, "sell": 30},
    "Pikachu": {"price": 80, "sell": 50},
    "Swellow": {"price": 125, "sell": 89},
    "Totodile": {"price": 220, "sell": 170},
    "Charizard": {"price": 500, "sell": 399},
}

LEVELS = {
    1: {
        "name": "Loose Change",
        "eyebrow": "LEVEL 01 / CLIENT-SIDE TRUST",
        "accent": "lime",
    },
    2: {
        "name": "Signed, Not Safe",
        "eyebrow": "LEVEL 02 / WEAK INTEGRITY",
        "accent": "orange",
    },
    3: {
        "name": "Point Zero",
        "eyebrow": "LEVEL 03 / LOGIC ERROR",
        "accent": "pink",
    },
}

FLAGS = {
    1: "FLAG{save_files_are_not_secrets}",
    2: "FLAG{md5_is_not_a_signature}",
    3: "FLAG{decimal_logic_needs_boundaries}",
}


def fresh_player(name: str = "Player1", player_id: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "money": STARTING_MONEY,
        "ID": player_id or f"{secrets.randbelow(10000):04d}-{secrets.randbelow(1000):03d}-{secrets.randbelow(10000):04d}-{secrets.randbelow(10000):04d}",
    }


def ensure_session() -> None:
    if "player" not in session:
        session["player"] = fresh_player()
        session["inventory"] = {}
        session["level"] = 1
        session["completed"] = []
        session["flags"] = {}
        session["activity"] = [
            {"kind": "system", "text": "Session opened. Wallet seeded with $50."}
        ]
    session.setdefault("inventory", {})
    session.setdefault("completed", [])
    session.setdefault("flags", {})
    session.setdefault("activity", [])


def add_activity(text: str, kind: str = "event") -> None:
    activity = session.get("activity", [])
    activity.insert(0, {"kind": kind, "text": text})
    session["activity"] = activity[:12]


def packet_for(player: dict[str, Any]) -> tuple[str, str]:
    payload = json.dumps(player, separators=(",", ":"), ensure_ascii=True).encode()
    encoded = base64.b64encode(payload).decode()
    return encoded, hashlib.md5(encoded.encode()).hexdigest()


def save_integrity_values(players: list[Any]) -> tuple[str, str]:
    players_json = json.dumps(players, separators=(",", ":"), ensure_ascii=True)
    cluster_json = f'"players":{players_json}'
    encoded = base64.b64encode(cluster_json.encode()).decode()
    return encoded, hashlib.md5(encoded.encode()).hexdigest()


def public_state() -> dict[str, Any]:
    ensure_session()
    level = int(session["level"])
    player = deepcopy(session["player"])
    encoded, checksum = packet_for(player)
    packet = {
        "encoded": encoded,
        "checksum": checksum,
        "decoded": json.dumps(player, indent=2, ensure_ascii=True),
    }
    return {
        "level": level,
        "level_info": LEVELS[level],
        "player": player,
        "inventory": session.get("inventory", {}),
        "products": PRODUCTS,
        "flag_price": FLAG_PRICE,
        "completed": session.get("completed", []),
        "flags": session.get("flags", {}),
        "activity": session.get("activity", []),
        "packet": packet,
    }


def needs_player_name() -> bool:
    return "player" not in session


def ok(message: str, **extra: Any):
    payload = {"ok": True, "message": message, **extra}
    return jsonify(payload)


def fail(message: str, status: int = 400):
    return jsonify({"ok": False, "message": message}), status


def complete_level(level: int) -> None:
    completed = session.get("completed", [])
    if level not in completed:
        completed.append(level)
    session["completed"] = completed
    if level < 3:
        session["level"] = level + 1
        current_player = session["player"]
        session["player"] = fresh_player(current_player["name"], current_player["ID"])
        session["inventory"] = {}
        add_activity(f"Level {level} cleared. New sandbox loaded.", "success")

@app.before_request
def log_request():
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.remote_addr

    print(
        f"[REQUEST] {client_ip} "
        f"{request.method} {request.path}"
    )

@app.get("/")
def index():
    print("remote_addr:", request.remote_addr)
    print("X-Forwarded-For:", request.headers.get("X-Forwarded-For"))
    print("X-Real-IP:", request.headers.get("X-Real-IP"))

    return render_template("index.html", page="shopping")


@app.get("/shopping")
def shopping():
    return render_template("index.html", page="shopping")


@app.get("/inventory")
def inventory():
    return render_template("index.html", page="inventory")


@app.get("/save-file")
def save_file():
    return render_template("index.html", page="save")


@app.get("/icons/<path:filename>")
def icons(filename: str):
    return send_from_directory(os.path.join(app.root_path, "icons"), filename)


@app.get("/api/state")
def state():
    if needs_player_name():
        return jsonify({"needs_name": True})
    return jsonify(public_state())


@app.post("/api/start")
def start():
    if not needs_player_name():
        return fail("A player session is already active.")
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return fail("Player name is required.")
    if len(name) > 32:
        return fail("Player name must be 32 characters or fewer.")
    session["player"] = fresh_player(name)
    session["inventory"] = {}
    session["level"] = 1
    session["completed"] = []
    session["flags"] = {}
    session["activity"] = [{"kind": "system", "text": f"Session opened for {name}. Wallet seeded with $50."}]
    return ok("Player session created.", state=public_state())


@app.post("/api/reset")
def reset():
    session.clear()
    return ok("Session ended.", needs_name=True)


@app.get("/api/save")
def download_save():
    ensure_session()
    if session["level"] == 3:
        return fail("This level do not allowed to using save file")
    player = session["player"]
    player_record = {
        "ID": player["ID"],
        "money": player["money"],
        "name": player["name"],
    }
    encoded_cluster, checksum_md5 = save_integrity_values([player_record])
    save = {
        "players": [player_record],
        "base64": encoded_cluster,
        "checksum_md5": checksum_md5,
    }
    body = json.dumps(save, separators=(",", ":"), ensure_ascii=True).encode()
    return send_file(
        BytesIO(body),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"{player['name']}.json",
    )


@app.post("/api/upload-save")
def upload_save():
    ensure_session()
    level = int(session["level"])
    if level not in (1, 2):
        return fail("This level do not allowed to using save file")
    uploaded = request.get_json(silent=True)
    if not isinstance(uploaded, dict) or not isinstance(uploaded.get("players"), list):
        return fail("Invalid file.") if level == 2 else fail("The save must contain a players array.")
    if not uploaded["players"] or not isinstance(uploaded["players"][0], dict):
        return fail("Invalid file.") if level == 2 else fail("No player record found.")

    if level == 2:
        expected_base64, expected_md5 = save_integrity_values(uploaded["players"])
        uploaded_base64 = uploaded.get("base64")
        uploaded_md5 = str(uploaded.get("checksum_md5", "")).strip().lower()
        if uploaded_base64 != expected_base64 or uploaded_md5 != expected_md5:
            add_activity("Rejected player.json: invalid integrity values.", "danger")
            return fail("Invalid file.")

    incoming = uploaded["players"][0]
    try:
        money = float(incoming["money"])
    except (KeyError, TypeError, ValueError):
        return fail("Player money is missing or invalid.")
    if money < 0 or money > 10_000_000_000:
        return fail("That wallet value is outside the test sandbox.")

    player = fresh_player()
    player["name"] = str(incoming.get("name", player["name"]))[:32]
    player["ID"] = str(incoming.get("ID", player["ID"]))[:32]
    player["money"] = int(money) if money.is_integer() else money
    session["player"] = player
    add_activity(f"Imported player.json with wallet ${player['money']:,.2f}.", "warning")
    return ok("Save imported. The shop trusts the file.", state=public_state())


@app.post("/api/buy")
def buy():
    ensure_session()
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    if item == "flag":
        level = int(session["level"])
        if session["player"]["money"] < FLAG_PRICE:
            return fail(f"Flag requires ${FLAG_PRICE:,}. Wallet is too small.")
        session["player"]["money"] -= FLAG_PRICE
        add_activity(f"Flag purchased for ${FLAG_PRICE:,}.", "success")
        flags = session.get("flags", {})
        flags[str(level)] = FLAGS[level]
        session["flags"] = flags
        if level < 3:
            complete_level(level)
        else:
            if 3 not in session.get("completed", []):
                session["completed"] = session.get("completed", []) + [3]
        return ok("Flag unlocked.", flag=FLAGS[level], state=public_state())

    if item not in PRODUCTS:
        return fail("Unknown product.")
    product = PRODUCTS[item]
    if session["player"]["money"] < product["price"]:
        return fail("Insufficient funds.")
    session["player"]["money"] -= product["price"]
    inventory = session.get("inventory", {})
    inventory[item] = inventory.get(item, 0) + 1
    session["inventory"] = inventory
    add_activity(f"Bought 1 {item} for ${product['price']}.")
    return ok(f"Bought {item}.", state=public_state())


@app.post("/api/sell")
def sell():
    ensure_session()
    if session["level"] != 3:
        return fail("The decimal sale terminal is locked until level 3.")
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    try:
        quantity = float(body.get("quantity"))
    except (TypeError, ValueError):
        return fail("Quantity must be numeric.")
    if item not in PRODUCTS or quantity < 1 or quantity > 100:
        return fail("Use a positive quantity no larger than 100.")

    inventory = session.get("inventory", {})
    owned = inventory.get(item, 0)
    # Intentional level-3 bug: storage consumes an integer, payout keeps decimals.
    consumed = int(quantity)
    if consumed > owned:
        return fail(f"You own {owned} {item}. The terminal cannot consume {consumed}.")
    inventory[item] = owned - consumed
    payout = quantity * PRODUCTS[item]["sell"]
    session["inventory"] = inventory
    session["player"]["money"] += payout
    add_activity(f"Sold {quantity:g} {item}; credited ${payout:,.2f}.", "warning")
    return ok(f"Sale credited ${payout:,.2f}.", state=public_state())


@app.post("/api/inventory/sell")
def sell_inventory():
    """Intentional decimal sale flaw available from the inventory in every level."""
    ensure_session()
    body = request.get_json(silent=True) or {}
    item = body.get("item")
    try:
        quantity = float(body.get("quantity"))
    except (TypeError, ValueError):
        return fail("Quantity must be numeric.")
    if item not in PRODUCTS:
        return fail("Unknown product.")
    if quantity < 1 or quantity > 100:
        return fail("Quantity must be at least 1 and no larger than 100.")

    inventory = session.get("inventory", {})
    owned = inventory.get(item, 0)
    consumed = int(quantity)
    if consumed > owned:
        return fail(f"You own {owned} {item}. The inventory cannot consume {consumed}.")

    inventory[item] = owned - consumed
    payout = quantity * PRODUCTS[item]["sell"]
    session["inventory"] = inventory
    session["player"]["money"] += payout
    add_activity(f"Sold {quantity:g} {item}; credited ${payout:,.2f}.", "warning")
    return ok(f"Sale credited ${payout:,.2f}.", state=public_state())


@app.post("/api/level2/verify")
def verify_packet():
    ensure_session()
    if session["level"] != 2:
        return fail("Packet console is locked until level 2.")
    body = request.get_json(silent=True) or {}
    encoded = str(body.get("encoded", "")).strip()
    checksum = str(body.get("checksum", "")).strip().lower()
    if not encoded or not checksum:
        return fail("Both packet and checksum are required.")
    expected = hashlib.md5(encoded.encode()).hexdigest()
    if checksum != expected:
        add_activity("Rejected packet: checksum mismatch.", "danger")
        return fail("Checksum mismatch. The server rejected the packet.")
    try:
        decoded = base64.b64decode(encoded, validate=True).decode()
        player = json.loads(decoded)
        money = float(player["money"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return fail("Checksum is valid, but the packet is not valid player JSON.")
    if money < FLAG_PRICE:
        return fail(f"Packet accepted, but wallet still needs ${FLAG_PRICE:,}.")
    session["player"] = {
        "name": str(player.get("name", "Player1"))[:32],
        "ID": str(player.get("ID", "0034-145-7858-2003"))[:32],
        "money": int(money) if money.is_integer() else money,
    }
    add_activity("Accepted a packet with a valid MD5 checksum.", "success")
    session["player"]["money"] -= FLAG_PRICE
    flags = session.get("flags", {})
    flags["2"] = FLAGS[2]
    session["flags"] = flags
    complete_level(2)
    return ok("Packet accepted. Flag unlocked.", flag=FLAGS[2], state=public_state())


@app.get("/api/flag")
def current_flag():
    ensure_session()
    return jsonify({"flags": session.get("flags", {})})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
