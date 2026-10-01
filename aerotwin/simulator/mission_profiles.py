import numpy as np

def generate_profile(name="standard", duration_s=3600):
    """
    Generates a mission profile as a list of dicts.
    Returns lists for: t, phase, throttle_pct, rpm, alt_ft, ambient_c
    """
    t = np.arange(duration_s)
    phase = []
    throttle = []
    rpm = []
    alt = []
    ambient = []
    
    # Simple standard profile
    # 0-300s: warm-up/taxi (idle)
    # 300-600s: takeoff & climb (max continuous)
    # 600-3000s: cruise
    # 3000-3600s: descent & landing
    
    base_temp = 15.0 if name == "standard" else (35.0 if name == "hot_weather" else 5.0)
    target_alt = 5000 if name != "high_altitude" else 15000
    
    for time_s in t:
        if time_s < 300:
            p = "taxi"
            th = 20.0
            r = 2000
            a = 0
            amb = base_temp
        elif time_s < 600:
            p = "climb"
            th = 100.0
            r = 5500
            frac = (time_s - 300) / 300.0
            a = target_alt * frac
            amb = base_temp - (a / 1000.0) * 2.0  # simple temp lapse
        elif time_s < duration_s - 600:
            p = "cruise"
            th = 75.0
            r = 4800
            a = target_alt
            amb = base_temp - (a / 1000.0) * 2.0
            
            # rapid_throttle variant adds some jitter in cruise
            if name == "rapid_throttle" and (time_s % 100) < 10:
                th += np.random.uniform(-10, 10)
                r += np.random.uniform(-200, 200)
        else:
            p = "descent"
            th = 30.0
            r = 3000
            frac = 1.0 - (time_s - (duration_s - 600)) / 600.0
            a = target_alt * max(0, frac)
            amb = base_temp - (a / 1000.0) * 2.0
            
        phase.append(p)
        throttle.append(th)
        rpm.append(r)
        alt.append(a)
        ambient.append(amb)
        
    return {
        "t": t,
        "phase": phase,
        "throttle_pct": np.array(throttle),
        "rpm": np.array(rpm),
        "altitude_ft": np.array(alt),
        "ambient_c": np.array(ambient)
    }
