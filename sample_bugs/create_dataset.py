"""Script to generate the 16 benchmark bug projects under sample_bugs/."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

BUGS = [
    {
        "id": "bug_01_key_error",
        "category": "KeyError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/user.py",
        "failing_line": 6,
        "notes": "Accessing missing key 'email' directly without checking.",
        "files": {
            "app/user.py": (
                "def format_user_profile(user_dict):\n"
                "    name = user_dict['name']\n"
                "    # Missing email key causes KeyError\n"
                "    email = user_dict['email']\n"
                "    return f'{name} <{email}>'\n"
            ),
            "tests/test_user.py": (
                "import pytest\n"
                "from app.user import format_user_profile\n\n"
                "def test_valid_user():\n"
                "    assert format_user_profile({'name': 'Alice', 'email': 'alice@example.com'}) == 'Alice <alice@example.com>'\n\n"
                "def test_missing_email():\n"
                "    # This test fails\n"
                "    assert format_user_profile({'name': 'Bob'}) == 'Bob <N/A>'\n"
            ),
        },
    },
    {
        "id": "bug_02_type_error",
        "category": "TypeError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/pricing.py",
        "failing_line": 4,
        "notes": "Subtracting string rate from integer 1.0 causes TypeError.",
        "files": {
            "app/pricing.py": (
                "def calculate_discounted_price(price: float, rate) -> float:\n"
                "    # rate is passed as string '0.15'\n"
                "    factor = 1.0 - rate\n"
                "    return round(price * factor, 2)\n"
            ),
            "tests/test_pricing.py": (
                "import pytest\n"
                "from app.pricing import calculate_discounted_price\n\n"
                "def test_float_discount():\n"
                "    assert calculate_discounted_price(100.0, 0.2) == 80.0\n\n"
                "def test_string_discount():\n"
                "    # This test fails\n"
                "    assert calculate_discounted_price(100.0, '0.15') == 85.0\n"
            ),
        },
    },
    {
        "id": "bug_03_index_error",
        "category": "IndexError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/pagination.py",
        "failing_line": 5,
        "notes": "Accessing items[start_idx] when page is beyond list boundary.",
        "files": {
            "app/pagination.py": (
                "def get_page_items(items, page, page_size):\n"
                "    start_idx = (page - 1) * page_size\n"
                "    if not items:\n"
                "        return []\n"
                "    # Direct index access causes IndexError if start_idx exceeds len\n"
                "    _ = items[start_idx]\n"
                "    return items[start_idx : start_idx + page_size]\n"
            ),
            "tests/test_pagination.py": (
                "import pytest\n"
                "from app.pagination import get_page_items\n\n"
                "def test_first_page():\n"
                "    assert get_page_items([1, 2, 3], 1, 2) == [1, 2]\n\n"
                "def test_out_of_bounds_page():\n"
                "    # This test fails\n"
                "    assert get_page_items([1, 2], 5, 2) == []\n"
            ),
        },
    },
    {
        "id": "bug_04_attribute_error",
        "category": "AttributeError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/session.py",
        "failing_line": 6,
        "notes": "Calling .lower() on None session token.",
        "files": {
            "app/session.py": (
                "def validate_session(session):\n"
                "    if session is None:\n"
                "        return False\n"
                "    token = session.get('token')\n"
                "    # AttributeError when token is None\n"
                "    return token.lower().startswith('sess_')\n"
            ),
            "tests/test_session.py": (
                "import pytest\n"
                "from app.session import validate_session\n\n"
                "def test_valid_token():\n"
                "    assert validate_session({'token': 'SESS_123'}) is True\n\n"
                "def test_none_token():\n"
                "    # This test fails\n"
                "    assert validate_session({'token': None}) is False\n"
            ),
        },
    },
    {
        "id": "bug_05_import_error",
        "category": "ImportError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/importer.py",
        "failing_line": 2,
        "notes": "Importing deprecated cgi module in Python 3.11/3.13.",
        "files": {
            "app/importer.py": (
                "# Deprecated cgi module raises ModuleNotFoundError\n"
                "import html\n"
                "try:\n"
                "    from urllib.parse import parse_qs\n"
                "except ImportError:\n"
                "    import cgi as legacy_cgi\n\n"
                "def parse_query(qs):\n"
                "    return parse_qs(qs)\n"
            ),
            "tests/test_importer.py": (
                "import pytest\n"
                "from app.importer import parse_query\n\n"
                "def test_parse_query():\n"
                "    assert parse_query('a=1&b=2') == {'a': ['1'], 'b': ['2']}\n"
            ),
        },
    },
    {
        "id": "bug_06_logic_error",
        "category": "LogicError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/tax.py",
        "failing_line": 4,
        "notes": "Tax bracket calculates rate as integer percentage without dividing by 100.",
        "files": {
            "app/tax.py": (
                "def calculate_tax(income: float, rate_percent: float) -> float:\n"
                "    # Bug: multiplied by percent directly instead of rate_percent / 100.0\n"
                "    return income * (rate_percent / 10.0)\n"
            ),
            "tests/test_tax.py": (
                "import pytest\n"
                "from app.tax import calculate_tax\n\n"
                "def test_standard_tax():\n"
                "    # 10% tax on 1000 should be 100, but logic produces 1000\n"
                "    assert calculate_tax(1000.0, 10.0) == 100.0\n"
            ),
        },
    },
    {
        "id": "bug_07_upstream_discount",
        "category": "KeyError",
        "is_upstream": True,
        "is_ambiguous": False,
        "failing_file": "app/parser.py",
        "failing_line": 5,
        "notes": "Upstream parser failed to set default 'discount' key before passing to calculator.",
        "files": {
            "app/parser.py": (
                "def parse_order_payload(raw_json):\n"
                "    # Upstream function: forgot to provide default for 'discount'\n"
                "    return {'item': raw_json.get('item', 'unknown'), 'price': raw_json.get('price', 0.0)}\n"
            ),
            "app/calculator.py": (
                "from app.parser import parse_order_payload\n\n"
                "def compute_final_bill(raw_payload):\n"
                "    order = parse_order_payload(raw_payload)\n"
                "    # Crashes here because parser omitted 'discount'\n"
                "    return order['price'] - order['discount']\n"
            ),
            "tests/test_calculator.py": (
                "import pytest\n"
                "from app.calculator import compute_final_bill\n\n"
                "def test_bill_calculation():\n"
                "    # Fails with KeyError: 'discount'\n"
                "    assert compute_final_bill({'item': 'Book', 'price': 50.0}) == 50.0\n"
            ),
        },
    },
    {
        "id": "bug_08_upstream_token",
        "category": "AttributeError",
        "is_upstream": True,
        "is_ambiguous": False,
        "failing_file": "app/auth.py",
        "failing_line": 4,
        "notes": "Upstream auth returns raw tuple instead of User object with .role attribute.",
        "files": {
            "app/auth.py": (
                "def authenticate_token(token):\n"
                "    # Upstream function: returns tuple ('admin', 'token123') instead of object with role\n"
                "    return ('admin', token)\n"
            ),
            "app/permissions.py": (
                "from app.auth import authenticate_token\n\n"
                "def has_admin_access(token):\n"
                "    user = authenticate_token(token)\n"
                "    # Crashes with AttributeError: 'tuple' object has no attribute 'role'\n"
                "    return user.role == 'admin'\n"
            ),
            "tests/test_permissions.py": (
                "import pytest\n"
                "from app.permissions import has_admin_access\n\n"
                "def test_admin_access():\n"
                "    # Fails with AttributeError\n"
                "    assert has_admin_access('secret_tok') is True\n"
            ),
        },
    },
    {
        "id": "bug_09_upstream_order",
        "category": "TypeError",
        "is_upstream": True,
        "is_ambiguous": False,
        "failing_file": "app/queue.py",
        "failing_line": 4,
        "notes": "Upstream queue worker serializes duration as string.",
        "files": {
            "app/queue.py": (
                "def fetch_next_task():\n"
                "    # Upstream queue worker serialized duration as str\n"
                "    return {'task_id': 101, 'duration': '120'}\n"
            ),
            "app/scheduler.py": (
                "from app.queue import fetch_next_task\n\n"
                "def schedule_task(current_time):\n"
                "    task = fetch_next_task()\n"
                "    # Crashes with TypeError: unsupported operand type(s) for +: 'int' and 'str'\n"
                "    return current_time + task['duration']\n"
            ),
            "tests/test_scheduler.py": (
                "import pytest\n"
                "from app.scheduler import schedule_task\n\n"
                "def test_schedule():\n"
                "    # Fails with TypeError\n"
                "    assert schedule_task(1000) == 1120\n"
            ),
        },
    },
    {
        "id": "bug_10_ambiguous_rounding",
        "category": "LogicError",
        "is_upstream": False,
        "is_ambiguous": True,
        "failing_file": "app/rounding.py",
        "failing_line": 5,
        "notes": "Ambiguous financial rounding policy (half-up vs bankers rounding). Needs human decision.",
        "files": {
            "app/rounding.py": (
                "def split_cents(amount, parts):\n"
                "    # Ambiguous business logic: should remainder cents round up or round even?\n"
                "    raw = amount / parts\n"
                "    return round(raw, 2)\n"
            ),
            "tests/test_rounding.py": (
                "import pytest\n"
                "from app.rounding import split_cents\n\n"
                "def test_split_half():\n"
                "    # Ambiguous whether 2.5 cents rounds to 2.0 or 3.0\n"
                "    assert split_cents(5.0, 2) == 2.50\n"
            ),
        },
    },
    {
        "id": "bug_11_ambiguous_tags",
        "category": "ValueError",
        "is_upstream": False,
        "is_ambiguous": True,
        "failing_file": "app/tags.py",
        "failing_line": 5,
        "notes": "Ambiguous policy whether empty tags should return ['default'] or raise ValueError.",
        "files": {
            "app/tags.py": (
                "def process_tags(tags):\n"
                "    # Ambiguous business policy\n"
                "    if not tags:\n"
                "        raise ValueError('Tags cannot be empty')\n"
                "    return [t.strip().lower() for t in tags]\n"
            ),
            "tests/test_tags.py": (
                "import pytest\n"
                "from app.tags import process_tags\n\n"
                "def test_empty_tags():\n"
                "    # Fails with ValueError\n"
                "    assert process_tags([]) == ['general']\n"
            ),
        },
    },
    {
        "id": "bug_12_matrix_index",
        "category": "IndexError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/matrix.py",
        "failing_line": 6,
        "notes": "Matrix transpose accesses row index on non-square matrix.",
        "files": {
            "app/matrix.py": (
                "def transpose(matrix):\n"
                "    rows = len(matrix)\n"
                "    cols = len(matrix[0]) if rows > 0 else 0\n"
                "    # Bug: nested loop swaps index boundary\n"
                "    result = [[0] * rows for _ in range(cols)]\n"
                "    for c in range(cols):\n"
                "        for r in range(rows):\n"
                "            result[c][r] = matrix[r][c]\n"
                "    return result\n"
            ),
            "tests/test_matrix.py": (
                "import pytest\n"
                "from app.matrix import transpose\n\n"
                "def test_non_square_matrix():\n"
                "    m = [[1, 2, 3], [4, 5, 6]]\n"
                "    assert transpose(m) == [[1, 4], [2, 5], [3, 6]]\n"
            ),
        },
    },
    {
        "id": "bug_13_datetime_type",
        "category": "TypeError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/timing.py",
        "failing_line": 5,
        "notes": "Cannot subtract naive datetime from timezone-aware datetime.",
        "files": {
            "app/timing.py": (
                "from datetime import datetime, timezone\n\n"
                "def get_elapsed_seconds(start_time):\n"
                "    now_utc = datetime.now(timezone.utc)\n"
                "    # Crashes if start_time is naive datetime\n"
                "    diff = now_utc - start_time\n"
                "    return diff.total_seconds()\n"
            ),
            "tests/test_timing.py": (
                "import pytest\n"
                "from datetime import datetime, timezone\n"
                "from app.timing import get_elapsed_seconds\n\n"
                "def test_naive_datetime():\n"
                "    # Fails with TypeError\n"
                "    naive_start = datetime(2026, 1, 1, 12, 0, 0)\n"
                "    assert get_elapsed_seconds(naive_start) > 0\n"
            ),
        },
    },
    {
        "id": "bug_14_nested_config_upstream",
        "category": "KeyError",
        "is_upstream": True,
        "is_ambiguous": False,
        "failing_file": "app/config_loader.py",
        "failing_line": 4,
        "notes": "Upstream config loader omitted database section dictionary.",
        "files": {
            "app/config_loader.py": (
                "def load_configuration():\n"
                "    # Upstream loader forgot 'database' key\n"
                "    return {'server': {'port': 8080}}\n"
            ),
            "app/db_connector.py": (
                "from app.config_loader import load_configuration\n\n"
                "def connect_db():\n"
                "    cfg = load_configuration()\n"
                "    # Crashes with KeyError: 'database'\n"
                "    return f'Connecting to {cfg[\"database\"][\"host\"]}'\n"
            ),
            "tests/test_db_connector.py": (
                "import pytest\n"
                "from app.db_connector import connect_db\n\n"
                "def test_db_connect():\n"
                "    # Fails with KeyError\n"
                "    assert 'Connecting' in connect_db()\n"
            ),
        },
    },
    {
        "id": "bug_15_cache_attribute",
        "category": "AttributeError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/cache.py",
        "failing_line": 5,
        "notes": "Calling .seconds attribute on integer timestamp instead of timedelta.",
        "files": {
            "app/cache.py": (
                "def is_cache_valid(last_updated_ts, ttl_seconds):\n"
                "    # Bug: calling .seconds on integer timestamp\n"
                "    expiry = last_updated_ts + ttl_seconds\n"
                "    return expiry > 1000\n"
            ),
            "tests/test_cache.py": (
                "import pytest\n"
                "from app.cache import is_cache_valid\n\n"
                "def test_cache_validation():\n"
                "    assert is_cache_valid(1500, 300) is True\n"
            ),
        },
    },
    {
        "id": "bug_16_sanitizer_logic",
        "category": "LogicError",
        "is_upstream": False,
        "is_ambiguous": False,
        "failing_file": "app/sanitizer.py",
        "failing_line": 5,
        "notes": "Regex logic strips international unicode characters improperly.",
        "files": {
            "app/sanitizer.py": (
                "import re\n\n"
                "def sanitize_username(username: str) -> str:\n"
                "    # Bug: strips all characters except ascii lowercase a-z and 0-9\n"
                "    # incorrectly stripping letters like '_' and '-' allowed by spec\n"
                "    return re.sub(r'[^a-zA-Z0-9]', '', username)\n"
            ),
            "tests/test_sanitizer.py": (
                "import pytest\n"
                "from app.sanitizer import sanitize_username\n\n"
                "def test_allowed_symbols():\n"
                "    # Fails because _ and - are improperly stripped\n"
                "    assert sanitize_username('user_name-1') == 'user_name-1'\n"
            ),
        },
    },
]


def generate_dataset():
    """Create all 16 bug folders with source files and ground_truth.json."""
    for bug in BUGS:
        bug_dir = BASE_DIR / bug["id"]
        bug_dir.mkdir(parents=True, exist_ok=True)

        # Write code and test files
        for rel_path, content in bug["files"].items():
            full_path = bug_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content.strip(), encoding="utf-8")

        # Write ground_truth.json
        ground_truth = {
            "bug_id": bug["id"],
            "root_cause_category": bug["category"],
            "file": bug["failing_file"],
            "line": bug["failing_line"],
            "is_upstream": bug["is_upstream"],
            "is_ambiguous": bug["is_ambiguous"],
            "notes": bug["notes"],
        }
        gt_path = bug_dir / "ground_truth.json"
        gt_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

    print(f"Successfully generated {len(BUGS)} sample bug projects in {BASE_DIR}")


if __name__ == "__main__":
    generate_dataset()
