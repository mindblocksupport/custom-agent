"""api_keys.hash_api_key 纯函数测试 (无 DB)."""

from api_server.db.api_keys import hash_api_key


def test_hash_deterministic():
    assert hash_api_key("hello") == hash_api_key("hello")


def test_hash_different_inputs_differ():
    assert hash_api_key("a") != hash_api_key("b")


def test_hash_is_64_hex_chars():
    h = hash_api_key("any-key-here")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_empty_string():
    """sha256('') 也是 64 字符 hex (不会崩, 但 lookup_principal 会拒绝空 key)."""
    h = hash_api_key("")
    assert len(h) == 64
