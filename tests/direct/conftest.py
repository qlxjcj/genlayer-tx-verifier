"""Shared fixtures and mocks for Transaction Verifier tests."""

import json
import os
import pytest

CONTRACT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tx_verifier.py",
)

LLM_PATTERN = r".*transaction.*verifier.*|.*exists.*|.*receipt.*status.*"

TX_HASH = "0x" + "a" * 64

TX_DATA = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "hash": TX_HASH,
        "from": "0x1234567890123456789012345678901234567890",
        "to": "0x0987654321098765432109876543210987654321",
        "value": "0xde0b6b3a7640000",
        "gas": "21000",
    }
})

RECEIPT_DATA = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "transactionHash": TX_HASH,
        "status": "0x1",
        "blockNumber": "0x1234",
    }
})

LLM_RESPONSE_EXISTS = json.dumps({
    "exists": "true",
    "from_address": "0x1234567890123456789012345678901234567890",
    "to_address": "0x0987654321098765432109876543210987654321",
    "value": "1000000000000000000",
    "receipt_status": "SUCCESS",
    "sources_agreed": "2",
    "reasoning": "Transaction found in both sources."
})

LLM_RESPONSE_NOT_FOUND = json.dumps({
    "exists": "false",
    "from_address": "",
    "to_address": "",
    "value": "0",
    "receipt_status": "UNKNOWN",
    "sources_agreed": "0",
    "reasoning": "Transaction not found in any source."
})

LLM_RESPONSE_DISAGREE = json.dumps({
    "exists": "true",
    "from_address": "0x1234567890123456789012345678901234567890",
    "to_address": "0x0987654321098765432109876543210987654321",
    "value": "1000000000000000000",
    "receipt_status": "SUCCESS",
    "sources_agreed": "1",
    "reasoning": "Only one source confirmed the transaction."
})


def with_tx_data(vm):
    vm.mock_web(".*etherscan.*", {"method": "GET", "status": 200, "body": TX_DATA})
    vm.mock_web(".*bscscan.*", {"method": "GET", "status": 200, "body": TX_DATA})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_EXISTS)


def with_all_sources_down(vm):
    vm.mock_web(".*etherscan.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_web(".*bscscan.*", {"method": "GET", "status": 200, "body": ""})
    vm.mock_llm(LLM_PATTERN, LLM_RESPONSE_NOT_FOUND)


@pytest.fixture
def verifier(direct_vm, direct_deploy):
    vm = direct_vm
    c = direct_deploy(CONTRACT)
    with_tx_data(vm)
    return vm, c
