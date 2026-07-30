import sys
sys.path.append('.')

from engine.utils.data_loader import get_expected_xi

rcb = get_expected_xi("Royal Challengers Bengaluru")
mi = get_expected_xi("Mumbai Indians")

print("\nRCB raw data (first 3):")
for p in rcb[:3]:
    print(f"  {p}")
    print(f"  Keys: {list(p.keys())}")

print("\nMI raw data (first 3):")
for p in mi[:3]:
    print(f"  {p}")
    print(f"  Keys: {list(p.keys())}")