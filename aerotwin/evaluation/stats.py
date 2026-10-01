"""Exact confidence intervals for the small-count metrics the benchmark
reports. With 60 fault flights and ~80 healthy flight-hours, a point
estimate alone (\"100%\", \"0.00 /FH\") overstates what the data supports."""
from scipy.stats import beta, chi2


def clopper_pearson(k, n, conf=0.95):
    """Exact binomial CI for k successes in n trials -> (low, high)."""
    a = 1 - conf
    low = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    high = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return low, high


def poisson_rate_ci(events, exposure, conf=0.95):
    """Exact (Garwood) CI for a Poisson rate: events observed over
    `exposure` units (e.g. flight-hours) -> (low, high) per unit."""
    a = 1 - conf
    low = 0.0 if events == 0 else float(chi2.ppf(a / 2, 2 * events) / 2)
    high = float(chi2.ppf(1 - a / 2, 2 * events + 2) / 2)
    return low / exposure, high / exposure
