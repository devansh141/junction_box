from flask import Flask, request, Response, render_template, send_from_directory, jsonify
import os
from datetime import datetime
import random
import json

app = Flask(__name__)
SAVE_DIR = "received_images"
MSG_FILE = "messages.txt"
ALERTS_FILE = "alerts_history.json"
os.makedirs(SAVE_DIR, exist_ok=True)

# Device data with locations
devices = [
    {"id": "DEV001", "name": "Junction Box A", "lat": 18.645917, "lng": 73.792500}
]

# Store alerts in memory (in production, use a database)
alerts = []

# Store power supply status for each device (simulated)
power_status = {
    "DEV001": {"main": True, "backup": True, "last_update": datetime.now()}
}

def load_alerts_from_file():
    """Load alerts from persistent storage"""
    global alerts
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r") as f:
                alerts = json.load(f)
        except:
            alerts = []
    return alerts

def save_alerts_to_file():
    """Save alerts to persistent storage"""
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

# Load alerts on startup
load_alerts_from_file()

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/devices")
def get_devices():
    return jsonify(devices)

@app.route("/device/<device_id>/alerts")
def get_device_alerts(device_id):
    # Filter alerts for this device
    device_alerts = [a for a in alerts if a["device_id"] == device_id]
    return jsonify(device_alerts)

@app.route("/alerts-history")
def get_alerts_history():
    """Get all alert history"""
    return jsonify(alerts)

@app.route("/device/<device_id>/power-status")
def get_power_status(device_id):
    """Get current power supply status for a device"""
    if device_id not in power_status:
        return jsonify({"error": "Device not found"}), 404
    
    status = power_status[device_id]
    main = status["main"]
    backup = status["backup"]
    
    # Determine power state
    if main and backup:
        state = "Normal - Both supplies active"
        state_class = "success"
    elif not main and backup:
        state = "Running on BACKUP power"
        state_class = "warning"
    elif main and not backup:
        state = "Main supply active, backup offline"
        state_class = "info"
    else:
        state = "No Power Available - CRITICAL"
        state_class = "danger"
    
    return jsonify({
        "device_id": device_id,
        "main_supply": "ON" if main else "OFF",
        "backup_supply": "ON" if backup else "OFF",
        "state": state,
        "state_class": state_class,
        "last_update": status["last_update"].strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/update-power-status", methods=["POST"])
def update_power_status():
    """Update power status from ESP32 or simulate for demo"""
    device_id = request.json.get("device_id")
    main_supply = request.json.get("main_supply")
    backup_supply = request.json.get("backup_supply")
    
    if device_id not in power_status:
        return jsonify({"error": "Device not found"}), 404
    
    power_status[device_id] = {
        "main": main_supply,
        "backup": backup_supply,
        "last_update": datetime.now()
    }
    
    return jsonify({"status": "success"})

@app.route("/simulate-power-change", methods=["POST"])
def simulate_power_change():
    """Simulate realistic power supply changes for continuous demo"""
    device_id = request.json.get("device_id")
    
    if device_id not in power_status:
        return jsonify({"error": "Device not found"}), 404
    
    # Simulate realistic power scenarios
    scenarios = [
        {"main": True, "backup": True},   # Normal - 70% probability
        {"main": True, "backup": True},
        {"main": True, "backup": True},
        {"main": True, "backup": True},
        {"main": True, "backup": True},
        {"main": True, "backup": True},
        {"main": True, "backup": True}
    ]
    
    scenario = random.choice(scenarios)
    power_status[device_id] = {
        "main": scenario["main"],
        "backup": scenario["backup"],
        "last_update": datetime.now()
    }
    
    # Create alert if power issue detected
    if not scenario["main"] and scenario["backup"]:
        alert = {
            "id": len(alerts) + 1,
            "device_id": device_id,
            "alert_type": "Power Alert",
            "message": "Main supply failed - Running on BACKUP power",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "image": "placeholder.jpg"
        }
        alerts.append(alert)
        save_alerts_to_file()
    elif not scenario["main"] and not scenario["backup"]:
        alert = {
            "id": len(alerts) + 1,
            "device_id": device_id,
            "alert_type": "Critical Power Alert",
            "message": "CRITICAL: No Power Available",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "image": "placeholder.jpg"
        }
        alerts.append(alert)
        save_alerts_to_file()
    
    return jsonify({"status": "success", "power_status": power_status[device_id]})

@app.route("/old", methods=["GET", "POST"])
def receive_from_esp32():
    """Handle incoming POST requests from ESP32-CAM"""
    if request.method == "POST":
        if request.content_type == "image/jpeg":
            # Save image with timestamp
            img_bytes = request.data
            fname = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
            path = os.path.join(SAVE_DIR, fname)
            with open(path, "wb") as f:
                f.write(img_bytes)
            
            # Try to get device_id from query params or headers
            device_id = request.args.get('device_id', 'UNKNOWN')
            
            # Create alert for the image
            alert = {
                "id": len(alerts) + 1,
                "device_id": device_id,
                "alert_type": "Image Captured",
                "message": "Photo captured by device",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": fname
            }
            alerts.append(alert)
            save_alerts_to_file()
            
            return Response("Image received", status=200)
        
        if request.content_type == "application/x-www-form-urlencoded":
            message = request.form.get("message", "")
            device_id = request.args.get('device_id', 'UNKNOWN')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Determine alert type based on message content
            alert_type = "General Alert"
            if "Access status changed" in message:
                alert_type = "Access Status Change"
            elif "Vibration detected" in message:
                alert_type = "Vibration Alert"
            elif "ALERT:" in message and "Access Denied" in message:
                alert_type = "Critical Alert"
            elif "Door opened" in message:
                alert_type = "Door Alert"
            
            # Create alert
            alert = {
                "id": len(alerts) + 1,
                "device_id": device_id,
                "alert_type": alert_type,
                "message": message,
                "timestamp": timestamp,
                "image": "placeholder.jpg"  # Will be updated when photo arrives
            }
            alerts.append(alert)
            save_alerts_to_file()
            
            # Append message to file with timestamp
            with open(MSG_FILE, "a") as f:
                f.write(f"{timestamp} | {device_id} | {message}\n")
            
            return Response("Message received", status=200)
        
        return Response("Unsupported Content-Type", status=400)
    
    # On GET, show message history and images (backward compatibility)
    messages = []
    if os.path.exists(MSG_FILE):
        with open(MSG_FILE, "r") as f:
            lines = f.readlines()
            messages = [line.strip() for line in lines[::-1]][:5]
    
    images = []
    files = sorted(os.listdir(SAVE_DIR), reverse=True)
    for fname in files:
        if fname.lower().endswith(".jpg") or fname.lower().endswith(".jpeg"):
            images.append(fname)
            if len(images) == 2:
                break
    
    return render_template("index.html", messages=messages, images=images)

@app.route("/images/<filename>")
def images(filename):
    return send_from_directory(SAVE_DIR, filename)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
