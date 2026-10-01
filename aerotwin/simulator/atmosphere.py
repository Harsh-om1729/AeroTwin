import numpy as np

T0, P0, L = 288.15, 101325.0, 0.0065   # K, Pa, K/m
G, R = 9.80665, 287.05

def isa(alt_ft: float, isa_dev_c: float = 0.0):
    """
    ISA troposphere model (valid below ~11 km).
    Returns Temperature (K), Pressure (Pa), and density ratio (sigma).
    """
    h = alt_ft * 0.3048
    T_std = T0 - L * h
    P = P0 * (T_std / T0) ** (G / (L * R))
    T = T_std + isa_dev_c              # hot/cold day offset
    rho = P / (R * T)
    sigma = rho / 1.225                # density ratio
    return T, P, sigma

def isa_from_oat(alt_ft: float, oat_c: float):
    """Atmosphere from pressure altitude and the measured outside air
    temperature (OAT). The ISA deviation is OAT minus the *standard
    temperature at that altitude* -- not minus 15 C, which would apply the
    lapse rate twice. Returns T (K, equal to the OAT), P (Pa), sigma.
    """
    t_std_c = T0 - L * alt_ft * 0.3048 - 273.15
    return isa(alt_ft, oat_c - t_std_c)

def power_lapse(sigma: float):
    """
    Gagg-Ferrar approximation for naturally aspirated engines.
    P_avail / P_sl ≈ 1.132 * sigma - 0.132
    Returns the available power ratio.
    """
    ratio = 1.132 * sigma - 0.132
    return np.maximum(0.0, ratio)
