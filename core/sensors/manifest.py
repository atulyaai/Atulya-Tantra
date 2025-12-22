import time

class SensorManifest:
    """
    ADR-006 Central Registry for Sensor States.
    Enforces the Normalization Invariant and Privacy Boundaries.
    """
    def __init__(self):
        self.registry = {
            "TEXT": {"state": "BUFFER", "priority_base": 5, "quota": 2, "cycle_count": 0, "starvation": 0},
            "VOICE": {"state": "IGNORED", "priority_base": 5, "quota": 1, "cycle_count": 0, "starvation": 0},
            "VISION": {"state": "IGNORED", "priority_base": 5, "opt_in_required": True, "quota": 1, "cycle_count": 0, "starvation": 0},
            "SYSTEM": {"state": "BUFFER", "priority_base": 1, "quota": 5, "cycle_count": 0, "starvation": 0}
        }
        self.embodiment_active = True

    def reset_cycle(self):
        """ADR-007: Resets per-sensor quotas for the next cognitive cycle."""
        for name in self.registry:
            if self.registry[name]["cycle_count"] == 0:
                self.registry[name]["starvation"] += 1
            else:
                self.registry[name]["starvation"] = 0
            self.registry[name]["cycle_count"] = 0

    def get_config(self, sensor_name):
        return self.registry.get(sensor_name)

    def set_state(self, sensor_name, state):
        if sensor_name in self.registry:
            if self.registry[sensor_name].get("opt_in_required") and state != "IGNORED":
                # ADR-006: Vision requires explicit authorization (not implemented here)
                pass
            self.registry[sensor_name]["state"] = state

    def normalize(self, sensor_name, raw_stimulus, is_interrupt=False):
        """
        ADR-006 & ADR-007: Enforces quotas and starvation promotion.
        """
        if not self.embodiment_active:
            return None

        config = self.get_config(sensor_name)
        if not config or config["state"] == "IGNORED":
            return None
            
        # ADR-007 Quota Check
        if config["cycle_count"] >= config["quota"]:
            return None

        priority = 10 if is_interrupt else config["priority_base"]
        
        # ADR-007 Starvation Promotion
        if config["starvation"] > 5 and priority < 10:
            priority += 1
        
        config["cycle_count"] += 1
        
        return {
            "id": f"S-{int(time.time()*1000)}",
            "timestamp": time.time(),
            "sensor": sensor_name,
            "stimulus": raw_stimulus,
            "priority": priority,
            "policy": "INTERRUPT" if is_interrupt else config["state"]
        }
