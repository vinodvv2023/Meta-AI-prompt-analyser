import sys
sys.path.insert(0, '.')
from classifier import extract_mj_flags_with_values

TEST_CASES = [
    # Case 1: gtd2rcz orphaned before --exp, should attach to --profile
    "child perspective of organic chemistry gtd2rcz --exp 35 --profile --hd --v 8.1",
    # Case 2: igusadc and numeric IDs before flags, --sref 7831600625, --profile has no value
    "[imagine a photorealistic slim young woman facing camera surrounded by Heads up display panels ] :9 3152015730 3698601038 2056378216 1400881209::2 igusadc --chaos 20 --ar 16 --exp 30 --sref 7831600625 --profile --sw 500 --v 7",
]

for i, text in enumerate(TEST_CASES, 1):
    print(f"\n{'='*60}")
    print(f"Case {i}: {text[:80]}...")
    flags = extract_mj_flags_with_values(text)
    print("Parsed flags:")
    for f in flags:
        print(f"  {f}")
