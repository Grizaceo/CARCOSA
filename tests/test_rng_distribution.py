"""
Test para validar que el RNG produce distribuciones uniformes de d6 y d4
"""
import pytest
from collections import Counter
from engine.rng import RNG


def _chi_square_test(observed, expected, alpha=0.05):
    """
    Implementación minimalista de chi-square test.
    Retorna (chi2_stat, p_value_approx).
    La distribución es uniforme si chi2_stat es bajo.
    """
    chi2_stat = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    # Aproximación: para df=5 o df=3, chi2 crítico ~11.07 (α=0.05)
    # Para nuestro test: si chi2 < crítico, asumir p >= 0.05 (uniforme)
    df = len(observed) - 1
    if df == 5:  # d6: 6 valores
        critical = 11.07
    elif df == 3:  # d4: 4 valores
        critical = 7.81
    else:
        critical = 12.0
    # Si chi2 < crítico, p > alpha (uniforme)
    p_value = 0.1 if chi2_stat < critical else 0.01
    return chi2_stat, p_value


def test_rng_d6_uniformity():
    """
    Validar que rng.randint(1, 6) produce distribución uniforme de d6.
    """
    rng = RNG(seed=42)
    rolls = [rng.randint(1, 6) for _ in range(1000)]
    
    # Contar ocurrencias
    counter = Counter(rolls)
    observed = [counter.get(i, 0) for i in range(1, 7)]
    
    # Esperado: 1000/6 ≈ 166.67 por valor
    expected = [1000 / 6] * 6
    
    # Chi-square test minimalista
    chi2_stat, p_value = _chi_square_test(observed, expected)
    
    # Si p_value > 0.05, la distribución es uniforme
    assert p_value > 0.05, f"d6 distribution not uniform: p={p_value:.4f}, chi2={chi2_stat:.2f}, observed={observed}"
    
    # Verificar rango
    assert min(rolls) == 1 and max(rolls) == 6, "d6 out of range [1, 6]"


def test_rng_d4_uniformity():
    """
    Validar que rng.randint(1, 4) produce distribución uniforme de d4.
    """
    rng = RNG(seed=123)
    rolls = [rng.randint(1, 4) for _ in range(1000)]
    
    # Contar ocurrencias
    counter = Counter(rolls)
    observed = [counter.get(i, 0) for i in range(1, 5)]
    
    # Esperado: 1000/4 = 250 por valor
    expected = [1000 / 4] * 4
    
    # Chi-square test minimalista
    chi2_stat, p_value = _chi_square_test(observed, expected)
    
    assert p_value > 0.05, f"d4 distribution not uniform: p={p_value:.4f}, chi2={chi2_stat:.2f}, observed={observed}"
    
    # Verificar rango
    assert min(rolls) == 1 and max(rolls) == 4, "d4 out of range [1, 4]"


def test_rng_reproducibility():
    """
    Validar que el mismo seed produce los mismos resultados.
    """
    rng1 = RNG(seed=42)
    rng2 = RNG(seed=42)
    
    rolls1 = [rng1.randint(1, 6) for _ in range(100)]
    rolls2 = [rng2.randint(1, 6) for _ in range(100)]
    
    assert rolls1 == rolls2, "Same seed should produce same results"


def test_rng_different_seeds():
    """
    Validar que diferentes seeds producen diferentes resultados (con alta probabilidad).
    """
    rng1 = RNG(seed=1)
    rng2 = RNG(seed=2)
    
    rolls1 = [rng1.randint(1, 6) for _ in range(100)]
    rolls2 = [rng2.randint(1, 6) for _ in range(100)]
    
    # Estadísticamente, deberían ser diferentes (muy baja probabilidad de ser iguales)
    assert rolls1 != rolls2, "Different seeds should likely produce different results"


if __name__ == "__main__":
    test_rng_d6_uniformity()
    print("✓ d6 uniformity test passed")
    
    test_rng_d4_uniformity()
    print("✓ d4 uniformity test passed")
    
    test_rng_reproducibility()
    print("✓ Reproducibility test passed")
    
    test_rng_different_seeds()
    print("✓ Different seeds test passed")
    
    print("\nAll RNG tests passed!")
