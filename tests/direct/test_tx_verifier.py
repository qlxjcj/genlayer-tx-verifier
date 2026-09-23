"""Direct-mode tests for Transaction Verifier."""

import json

from conftest import (
    LLM_PATTERN,
    LLM_RESPONSE_EXISTS,
    LLM_RESPONSE_NOT_FOUND,
    LLM_RESPONSE_DISAGREE,
    TX_HASH,
    TX_DATA,
    RECEIPT_DATA,
    with_tx_data,
    with_all_sources_down,
)


def test_verify_basic(verifier):
    vm, c = verifier
    vid = c.verify(TX_HASH, "ethereum")
    assert c.get_verification_count() == 1
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["tx_hash"] == TX_HASH
    assert v["exists"] == "true"


def test_verify_returns_verification_id(verifier):
    vm, c = verifier
    vid = c.verify(TX_HASH, "ethereum")
    assert vid == "1"
    vid2 = c.verify(TX_HASH, "bsc")
    assert vid2 == "2"


def test_source_outage_distinguished(verifier):
    vm, c = verifier
    vm.clear_mocks()
    with_all_sources_down(vm)
    vid = c.verify(TX_HASH, "ethereum")
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["source_outage"] == "true"
    assert v["exists"] == "false"


def test_verified_nonexistence(verifier):
    vm, c = verifier
    vm.clear_mocks()
    vm.mock_web(".*etherscan.*", {"method": "GET", "status": 200, "body": json.dumps({"result": None})})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_NOT_FOUND)
    vid = c.verify(TX_HASH, "ethereum")
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["exists"] == "false"
    assert v["source_outage"] == "false"


def test_receipt_status_success(verifier):
    vm, c = verifier
    vid = c.verify(TX_HASH, "ethereum")
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["receipt_status"] == "SUCCESS"


def test_receipt_status_failed(verifier):
    vm, c = verifier
    vm.clear_mocks()
    vm.mock_web(".*etherscan.*", {"method": "GET", "status": 200, "body": TX_DATA})
    vm.mock_llm(LLM_PATTERN, json.dumps({
        "exists": "true",
        "from_address": "0x1234567890123456789012345678901234567890",
        "to_address": "0x0987654321098765432109876543210987654321",
        "value": "1000000000000000000",
        "receipt_status": "FAILED",
        "sources_agreed": "2",
        "reasoning": "Transaction failed."
    }))
    vid = c.verify(TX_HASH, "ethereum")
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["receipt_status"] == "FAILED"


def test_source_disagreement(verifier):
    vm, c = verifier
    vm.clear_mocks()
    vm.mock_web(".*etherscan.*", {"method": "GET", "status": 200, "body": TX_DATA})
    vm.mock_web(".*bscscan.*", {"method": "GET", "status": 200, "body": json.dumps({"result": None})})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_DISAGREE)
    vid = c.verify(TX_HASH, "ethereum")
    raw = c.get_verification(vid)
    v = json.loads(raw)
    assert v["sources_agreed"] == "1"


def test_concurrent_writes(verifier):
    vm, c = verifier
    vid1 = c.verify(TX_HASH, "ethereum")
    vid2 = c.verify(TX_HASH, "bsc")
    vid3 = c.verify(TX_HASH, "polygon")
    assert vid1 != vid2 != vid3
    assert c.get_verification_count() == 3


def test_invalid_hash(verifier):
    vm, c = verifier
    try:
        c.verify("invalid", "ethereum")
        assert False, "Should have raised"
    except Exception:
        pass


def test_invalid_chain(verifier):
    vm, c = verifier
    try:
        c.verify(TX_HASH, "solana")
        assert False, "Should have raised"
    except Exception:
        pass


def test_empty_hash(verifier):
    vm, c = verifier
    try:
        c.verify("", "ethereum")
        assert False, "Should have raised"
    except Exception:
        pass


def test_get_supported_chains(verifier):
    vm, c = verifier
    chains = c.get_supported_chains()
    assert "ethereum" in chains
    assert "bsc" in chains


def test_stats(verifier):
    vm, c = verifier
    c.verify(TX_HASH, "ethereum")
    s = c.get_stats()
    assert s["total"] == 1
    assert s["confirmed"] == 1


def test_stats_with_outage(verifier):
    vm, c = verifier
    vm.clear_mocks()
    with_all_sources_down(vm)
    c.verify(TX_HASH, "ethereum")
    s = c.get_stats()
    assert s["outages"] == 1
