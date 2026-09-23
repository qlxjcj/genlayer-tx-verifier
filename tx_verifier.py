# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
import json
from dataclasses import dataclass
from genlayer import *


EXPLORER_SOURCES = {
    "ethereum": [
        "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash=",
        "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionReceipt&txhash=",
    ],
    "bsc": [
        "https://api.bscscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash=",
        "https://api.bscscan.com/api?module=proxy&action=eth_getTransactionReceipt&txhash=",
    ],
    "polygon": [
        "https://api.polygonscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash=",
        "https://api.polygonscan.com/api?module=proxy&action=eth_getTransactionReceipt&txhash=",
    ],
    "arbitrum": [
        "https://api.arbiscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash=",
        "https://api.arbiscan.io/api?module=proxy&action=eth_getTransactionReceipt&txhash=",
    ],
}


@allow_storage
@dataclass
class Verification:
    verification_id: str
    tx_hash: str
    chain: str
    exists: str
    from_address: str
    to_address: str
    value: str
    status: str
    sources_checked: str
    sources_agreed: str
    source_outage: str
    receipt_status: str
    reasoning: str
    fetched_at: str


class TransactionVerifier(gl.Contract):
    verifications: TreeMap[str, str]
    verification_count: u256

    def __init__(self):
        self.verification_count = 0

    def _decode_body(self, content) -> str:
        body = getattr(content, "body", None)
        if body is None:
            return str(content)
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body)

    def _verify_transaction(self, tx_hash: str, chain: str) -> dict:
        def gather_and_verify() -> dict:
            sources = EXPLORER_SOURCES.get(chain.lower(), [])
            if not sources:
                return {
                    "exists": "false",
                    "from_address": "",
                    "to_address": "",
                    "value": "0",
                    "status": "UNKNOWN",
                    "sources_checked": 0,
                    "sources_agreed": 0,
                    "source_outage": "true",
                    "receipt_status": "UNKNOWN",
                    "reasoning": "Unsupported chain: " + chain,
                }

            fetched_data = []
            for url in sources:
                try:
                    content = gl.nondet.web.render(url + tx_hash)
                    body = self._decode_body(content)[:2000]
                    fetched_data.append({"url": url, "data": body, "retrieved": True})
                except Exception:
                    fetched_data.append({"url": url, "data": "", "retrieved": False})

            retrieved = [d for d in fetched_data if d["retrieved"]]
            outage = len(retrieved) == 0

            if outage:
                return {
                    "exists": "false",
                    "from_address": "",
                    "to_address": "",
                    "value": "0",
                    "status": "UNKNOWN",
                    "sources_checked": len(sources),
                    "sources_agreed": 0,
                    "source_outage": "true",
                    "receipt_status": "UNKNOWN",
                    "reasoning": "All sources failed - source outage, not verified nonexistence.",
                }

            parts = []
            for i, d in enumerate(retrieved):
                parts.append("[Source " + str(i+1) + "] " + d["url"] + ":\n" + d["data"][:500])
            sources_text = "\n".join(parts)

            json_format = chr(123) + chr(34) + "exists" + chr(34) + ": " + chr(34) + "true" + chr(34) + "|" + chr(34) + "false" + chr(34) + ", " + chr(34) + "from_address" + chr(34) + ": " + chr(34) + "<address>" + chr(34) + ", " + chr(34) + "to_address" + chr(34) + ": " + chr(34) + "<address>" + chr(34) + ", " + chr(34) + "value" + chr(34) + ": " + chr(34) + "<number>" + chr(34) + ", " + chr(34) + "receipt_status" + chr(34) + ": " + chr(34) + "SUCCESS" + chr(34) + "|" + chr(34) + "FAILED" + chr(34) + "|" + chr(34) + "PENDING" + chr(34) + ", " + chr(34) + "sources_agreed" + chr(34) + ": " + chr(34) + "<count>" + chr(34) + ", " + chr(34) + "reasoning" + chr(34) + ": " + chr(34) + "<text>" + chr(34) + chr(125)

            task = (
                "You are a transaction verifier. Verify the following transaction using receipt/proof-backed evidence.\n"
                "TX HASH: " + tx_hash + "\n"
                "CHAIN: " + chain + "\n"
                "SOURCES (" + str(len(retrieved)) + " retrieved):\n" + sources_text + "\n\n"
                "Rules:\n"
                "1. exists=true ONLY if transaction data is found in retrieved sources\n"
                "2. receipt_status derived from receipt evidence (SUCCESS/FAILED/PENDING)\n"
                "3. sources_agreed = count of sources with matching transaction details\n"
                "4. If no transaction found in any source, exists=false (verified nonexistence)\n\n"
                "Respond ONLY in JSON: " + json_format
            )
            result = gl.nondet.exec_prompt(task)
            if isinstance(result, str):
                result = json.loads(result.replace("```json", "").replace("```", ""))
            if not isinstance(result, dict):
                raise gl.vm.UserError("[LLM_ERROR] LLM returned non-dict result")
            result["sources_checked"] = len(sources)
            result["source_outage"] = "false"
            result["status"] = result.get("receipt_status", "UNKNOWN")
            return result

        principle = (
            "Two results are equivalent if exists matches exactly, "
            "from_address matches exactly, to_address matches exactly, "
            "value matches exactly, receipt_status matches exactly, "
            "sources_checked matches exactly, sources_agreed matches exactly, "
            "and source_outage matches exactly. "
            "reasoning wording may differ."
        )
        return gl.eq_principle.prompt_comparative(gather_and_verify, principle)

    @gl.public.write
    def verify(self, tx_hash: str, chain: str) -> str:
        if not tx_hash or not tx_hash.strip():
            raise gl.vm.UserError("Transaction hash is required")
        tx_hash = tx_hash.strip().lower()
        if not tx_hash.startswith("0x") or len(tx_hash) != 66:
            raise gl.vm.UserError("Invalid transaction hash format")

        chain = (chain or "").strip().lower()
        if chain not in EXPLORER_SOURCES:
            raise gl.vm.UserError("Unsupported chain: " + chain)

        result = self._verify_transaction(tx_hash, chain)

        from datetime import datetime, timezone
        self.verification_count += 1
        verification_id = str(self.verification_count)

        verification = Verification(
            verification_id=verification_id,
            tx_hash=tx_hash,
            chain=chain,
            exists=str(result.get("exists", "false")).lower(),
            from_address=str(result.get("from_address", "")),
            to_address=str(result.get("to_address", "")),
            value=str(result.get("value", "0")),
            status=str(result.get("status", "UNKNOWN")),
            sources_checked=str(result.get("sources_checked", 0)),
            sources_agreed=str(result.get("sources_agreed", 0)),
            source_outage=str(result.get("source_outage", "false")).lower(),
            receipt_status=str(result.get("receipt_status", "UNKNOWN")),
            reasoning=str(result.get("reasoning", "")),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        self.verifications[verification_id] = json.dumps(verification.__dict__)
        return verification_id

    @gl.public.view
    def get_verification(self, verification_id: str) -> str:
        return self.verifications.get(str(verification_id), "{}")

    @gl.public.view
    def get_verification_count(self) -> int:
        return self.verification_count

    @gl.public.view
    def get_supported_chains(self) -> list:
        return list(EXPLORER_SOURCES.keys())

    @gl.public.view
    def get_stats(self) -> dict:
        total = 0
        confirmed = 0
        not_found = 0
        outages = 0
        by_chain = {}
        by_status = {}
        for v in self.verifications.values():
            r = json.loads(v)
            total += 1
            chain = r.get("chain", "unknown")
            by_chain[chain] = by_chain.get(chain, 0) + 1
            if r.get("source_outage") == "true":
                outages += 1
            elif r.get("exists") == "true":
                confirmed += 1
                status = r.get("status", "UNKNOWN")
                by_status[status] = by_status.get(status, 0) + 1
            else:
                not_found += 1
        return {
            "total": total,
            "confirmed": confirmed,
            "not_found": not_found,
            "outages": outages,
            "by_chain": by_chain,
            "by_status": by_status,
        }