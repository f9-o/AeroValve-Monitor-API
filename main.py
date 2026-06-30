import time
import math
import random
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="AeroValve Telemetry Engine API",
    description="High-frequency mechanical telemetry ingestion and anomaly analysis API for pneumatic systems.",
    version="1.2.0"
)

@app.get("/", include_in_schema=False)
def index_redirect():
    return RedirectResponse(url="/docs")

class TelemetryPayload(BaseModel):
    valve_id: str = Field(..., example="valve-aero-01")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pressure_psi: float = Field(..., ge=0.0, description="Control valve inlet line pressure", example=95.4)
    vibration_hz: float = Field(..., ge=0.0, description="Actuator shell vibration frequency", example=24.5)
    friction_coeff: float = Field(..., ge=0.0, le=1.0, description="Calculated seal-to-stem friction coefficient", example=0.18)
    status: str = Field("HEALTHY", description="Evaluated operational state: HEALTHY, WARNING, CRITICAL")

# Thread-safe global store
telemetry_state: Dict[str, Any] = {
    "valve-aero-01": {
        "valve_id": "valve-aero-01",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pressure_psi": 95.0,
        "vibration_hz": 22.0,
        "friction_coeff": 0.16,
        "status": "HEALTHY"
    }
}

def simulate_valve_physics():
    """
    Background worker simulating realistic, physically bound pneumatic valve telemetry.
    Simulates seal friction degradation, pressure transients, and accelerometer chattering.
    """
    global telemetry_state
    valve_id = "valve-aero-01"
    t = 0.0
    
    base_pressure = 96.0
    base_vibration = 20.0
    base_friction = 0.15
    
    while True:
        try:
            t += 0.1
            # Random walk with sinusoidal wavelets
            pressure_noise = random.uniform(-0.5, 0.5) + 2.0 * math.sin(t * 0.2)
            vibration_noise = random.uniform(-0.8, 0.8) + 1.5 * math.cos(t * 0.5)
            
            # Slowly degrade the seal by drifting the friction coefficient upwards
            wear_cycle = (t % 300) / 300.0  # 5-minute cycle
            friction_drift = 0.3 * wear_cycle
            
            current_friction = round(base_friction + friction_drift + random.uniform(-0.01, 0.01), 3)
            current_pressure = round(base_pressure - (15.0 * wear_cycle) + pressure_noise, 2)
            
            # Friction/Vibration coupling logic
            if current_friction > 0.35:
                # Warning: seal stiction causes stick-slip chattering
                current_vibration = round(base_vibration + (vibration_noise * 3.0) + (current_friction * 100.0), 2)
                status = "WARNING"
            elif current_pressure < 80.0:
                # Critical: Major pressure loss
                current_vibration = round(base_vibration + (vibration_noise * 1.5), 2)
                status = "CRITICAL"
            else:
                current_vibration = round(base_vibration + vibration_noise + (current_friction * 15.0), 2)
                status = "HEALTHY"
                
            telemetry_state[valve_id] = {
                "valve_id": valve_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pressure_psi": max(0.0, current_pressure),
                "vibration_hz": max(0.0, current_vibration),
                "friction_coeff": min(1.0, max(0.0, current_friction)),
                "status": status
            }
            
            time.sleep(1.0)
        except Exception as e:
            # Strictly logged error without formatting emojis
            print(f"[ERROR] Physics thread exception: {e}")
            time.sleep(1.0)

# Init background telemetry simulation thread
simulator_thread = threading.Thread(target=simulate_valve_physics, daemon=True)
simulator_thread.start()

@app.get("/health", tags=["Diagnostics"])
def health_check():
    """
    Check telemetry engine and simulation thread state.
    """
    return {
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulator_thread_active": simulator_thread.is_alive()
    }

@app.get("/api/v1/telemetry", response_model=Dict[str, TelemetryPayload], tags=["Telemetry"])
def get_telemetry(valve_id: Optional[str] = None):
    """
    Get current telemetry payload.
    """
    if not telemetry_state:
        raise HTTPException(status_code=503, detail="Telemetry simulation engine initializing.")
        
    if valve_id:
        if valve_id not in telemetry_state:
            raise HTTPException(status_code=404, detail=f"Device ID '{valve_id}' not found.")
        return {valve_id: telemetry_state[valve_id]}
        
    return telemetry_state
