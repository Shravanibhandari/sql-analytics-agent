import pytest
from app.guardrails import check_input, regex_check


@pytest.mark.parametrize("text", [
    "DROP TABLE orders; --",
    "show orders <script>alert(1)</script>",
    "show orders where id = 1 OR 1=1",
    "orders /* hidden */",
])
def test_blocks_malicious_input(text):
    assert not regex_check(text)
    assert not check_input(text)


def test_allows_normal_question():
    assert check_input("Show orders sorted by date.")
