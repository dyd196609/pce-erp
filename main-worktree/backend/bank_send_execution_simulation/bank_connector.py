import hashlib
import json


class BankConnectorAdapter:
    """Design-only adapter. It never imports or invokes a network client."""

    allowed_environments = frozenset({"simulation", "sandbox"})

    def __init__(self, *, environment="simulation"):
        if environment not in self.allowed_environments:
            raise ValueError("Production bank connector is forbidden in V68")
        self.environment = environment

    def prepareRequest(self, payload):
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return {
            "result": "simulated",
            "environment": self.environment,
            "payload": payload,
            "payloadHash": hashlib.sha256(canonical.encode()).hexdigest(),
            "networkCallPerformed": False,
        }

    def signRequest(self, prepared):
        return {
            "result": "simulated",
            "algorithm": "SHA256_SIMULATION",
            "signature": hashlib.sha256(
                f"SIMULATION:{prepared['payloadHash']}".encode()
            ).hexdigest(),
            "productionCertificateUsed": False,
            "networkCallPerformed": False,
        }

    def sendRequest(self, signed):
        return {
            "result": "simulated",
            "responseStatus": "accepted",
            "requestSignature": signed["signature"],
            "realBankMessageSent": False,
            "networkCallPerformed": False,
        }

    def queryResult(self, receipt):
        return {
            "result": "simulated",
            "responseStatus": receipt["responseStatus"],
            "realBankReceipt": False,
            "networkCallPerformed": False,
        }
