"""
Demo buggy calculator script for Project ORION live testing.
Contains a deliberate syntax/indentation error to demonstrate
Flake8 guardrail detection and autonomous self-correction.
"""


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculates discounted price with basic validation."""
    if price < 0 or discount_percent < 0:
        raise ValueError("Price and discount must be non-negative")

    # Deliberate syntax/indentation error on line 13:
    discount_amount = price * (discount_percent / 100.0)
   final_price = price - discount_amount  # E111/E113: unexpected indentation

    return final_price


def add(a: float, b: float) -> float:
    """Simple addition helper."""
    return a + b


if __name__ == "__main__":
    print("Testing calculator...")
    result = calculate_discount(100.0, 15.0)
    print(f"Final price: {result}")
