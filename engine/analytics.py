import numpy as np
import pandas as pd

def calculate_overround_margin(odds: list[float]) -> float:
    """
    Calcula el margen porcentual de sobreprecio (overround/vig) de la casa de apuestas.
    """
    if not odds or any(o <= 1.0 for o in odds):
        return 0.0
    implied_sum = sum(1.0 / o for o in odds)
    return round((implied_sum - 1.0) * 100, 2)

def calculate_fair_probabilities(odds: list[float]) -> list[float]:
    """
    Elimina el margen comercial de la casa de apuestas para obtener las probabilidades reales/justas (Normalized Implied Probs).
    """
    if not odds or any(o <= 1.0 for o in odds):
        return []
    raw_probs = [1.0 / o for o in odds]
    total_prob = sum(raw_probs)
    return [round(p / total_prob, 4) for p in raw_probs]

def calculate_expected_value(predicted_prob: float, decimal_odds: float) -> float:
    """
    Calcula el Valor Esperado (EV %) de una apuesta dada la probabilidad real predicha por el modelo.
    EV = (Probabilidad * Cuota) - 1
    """
    if decimal_odds <= 1.0 or not (0.0 <= predicted_prob <= 1.0):
        return 0.0
    ev = (predicted_prob * decimal_odds) - 1.0
    return round(ev * 100, 2)

def detect_arbitrage(market_odds: list[dict]) -> dict:
    """
    Detecta oportunidades de arbitraje buscando la mejor cuota para cada 
    resultado posible en diferentes fuentes.
    """
    if not market_odds:
        return {"arbitrage_found": False, "error": "No data provided"}

    num_outcomes = len(market_odds[0]["odds"])
    best_market_lines = []

    for index in range(num_outcomes):
        best_source = max(market_odds, key=lambda base: base["odds"][index])
        
        best_market_lines.append({
            "outcome_index": index,
            "source": best_source["source"],
            "odd": best_source["odds"][index]
        })

    implied_probabilities_sum = sum(1 / item["odd"] for item in best_market_lines)

    if implied_probabilities_sum < 1:
        margin = (1 - implied_probabilities_sum) * 100
        
        return {
            "arbitrage_found": True,
            "margin_percentage": round(margin, 4),
            "implied_prob_sum": round(implied_probabilities_sum, 4),
            "best_odds": best_market_lines
        }
    else:
        return {
            "arbitrage_found": False,
            "implied_prob_sum": round(implied_probabilities_sum, 4),
            "best_odds": best_market_lines
        }

def calculate_kelly_stake(
    predicted_prob: float, 
    decimal_odds: float, 
    bankroll: float, 
    kelly_fraction: float = 1.0
) -> dict:
    """
    Calcula el stake optimo utilizando el Criterio de Kelly.
    """
    if decimal_odds <= 1.0:
        raise ValueError("Las cuotas decimales deben ser estrictamente mayores a 1.0")
    if not (0.0 <= predicted_prob <= 1.0):
        raise ValueError("La probabilidad predictiva debe estar en el rango [0.0, 1.0]")

    b = decimal_odds - 1.0
    q = 1.0 - predicted_prob
    
    f_star = (b * predicted_prob - q) / b
    fractional_f_star = f_star * kelly_fraction
    
    if fractional_f_star > 0:
        recommended_stake = bankroll * fractional_f_star
        return {
            "edge_found": True,
            "kelly_fraction_used": kelly_fraction,
            "bankroll_percentage_to_stake": round(fractional_f_star * 100, 2),
            "recommended_stake_amount": round(recommended_stake, 2)
        }
    else:
        return {
            "edge_found": False,
            "kelly_fraction_used": kelly_fraction,
            "bankroll_percentage_to_stake": 0.0,
            "recommended_stake_amount": 0.0
        }

def calculate_market_dispersion(odds_series: list[float]) -> dict:
    """
    Calcula la varianza, desviacion estandar y rango de cuotas entre casas para medir la incertidumbre del mercado.
    """
    if not odds_series or len(odds_series) < 2:
        return {"std": 0.0, "range": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0}
    
    arr = np.array(odds_series)
    return {
        "mean": round(float(np.mean(arr)), 3),
        "std": round(float(np.std(arr)), 3),
        "min": round(float(np.min(arr)), 3),
        "max": round(float(np.max(arr)), 3),
        "range": round(float(np.ptp(arr)), 3)
    }
