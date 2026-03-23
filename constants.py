DATASET_ORDER = ("inflation", "labor_market", "treasury_yields", "inflation_expectations")

DISPLAY_NAMES: dict[str, str] = {
    "inflation": "Inflation (CPI)",
    "labor_market": "Labor Market",
    "treasury_yields": "Treasury Yields",
    "inflation_expectations": "Inflation Expectations",
}

CHART_TITLES: dict[str, str] = {
    "inflation": "Inflation (CPI)",
    "labor_market": "Unemployment Rate",
    "treasury_yields": "10-Year Treasury Yield",
    "inflation_expectations": "10-Year Inflation Expectations",
}

TREND_ARROW: dict[str, str] = {
    "UP": "\u2191",
    "DOWN": "\u2193",
    "FLAT": "\u2192",
}

TREND_EMOJI: dict[str, str] = {
    "UP": "\U0001f4c8",
    "DOWN": "\U0001f4c9",
    "FLAT": "\u27a1\ufe0f",
}

TREND_COLOR: dict[str, str] = {
    "UP": "#ff6b6b",
    "DOWN": "#51cf66",
    "FLAT": "#ffd43b",
}

SIGNAL_MAP: dict[str, dict[str, str]] = {
    "inflation": {
        "UP": "Inflation pressure increasing",
        "DOWN": "Disinflation trend",
        "FLAT": "Inflation stable",
    },
    "labor_market": {
        "UP": "Labor softening (unemployment rising)",
        "DOWN": "Tight labor market (unemployment falling)",
        "FLAT": "Labor market stable",
    },
    "treasury_yields": {
        "UP": "Financial conditions tightening",
        "DOWN": "Easing financial conditions",
        "FLAT": "Yields stable",
    },
    "inflation_expectations": {
        "UP": "Forward inflation risk rising",
        "DOWN": "Inflation expectations anchored / falling",
        "FLAT": "Expectations stable",
    },
}

# Ordered list of fields to try per dataset when extracting the primary value
VALUE_FIELDS: dict[str, list[str]] = {
    "inflation": ["cpi_year_over_year", "cpi"],
    "labor_market": ["unemployment_rate"],
    "treasury_yields": ["yield_10_year"],
    "inflation_expectations": ["model_10_year"],
}

UNIT_LABELS: dict[str, str] = {
    "inflation": "% YoY CPI",
    "labor_market": "% unemployment",
    "treasury_yields": "% 10Y yield",
    "inflation_expectations": "% 10Y model",
}

UNIT_SUFFIXES: dict[str, str] = {
    "inflation": "",
    "labor_market": "%",
    "treasury_yields": "%",
    "inflation_expectations": "%",
}

FLAT_THRESHOLD = 0.005

HAWKISH_COMBOS: set[tuple[str, str]] = {
    ("inflation", "UP"),
    ("inflation_expectations", "UP"),
    ("treasury_yields", "UP"),
    ("labor_market", "DOWN"),
}

DOVISH_COMBOS: set[tuple[str, str]] = {
    ("inflation", "DOWN"),
    ("inflation_expectations", "DOWN"),
    ("treasury_yields", "DOWN"),
    ("labor_market", "UP"),
}

REGIME_LABELS: dict[str, str] = {
    "HAWKISH": "Hawkish / Tightening Bias",
    "DOVISH": "Dovish / Easing Bias",
    "NEUTRAL": "Neutral / Mixed Signals",
}

REGIME_DESCRIPTIONS: dict[str, str] = {
    "HAWKISH": (
        "The overall macro environment shows a hawkish / tightening bias. "
        "Rising inflation, tightening financial conditions, and elevated expectations "
        "suggest the Fed may maintain or increase restrictive policy."
    ),
    "DOVISH": (
        "The overall macro environment shows a dovish / easing bias. "
        "Falling inflation, loosening financial conditions, and softening labor "
        "suggest the Fed may ease monetary policy."
    ),
    "NEUTRAL": (
        "The macro environment is sending mixed signals. "
        "Some indicators point toward tightening while others suggest easing. "
        "Policy direction is uncertain."
    ),
}
