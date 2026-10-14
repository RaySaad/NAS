"""Keep legacy flat JSON bodies compatible with Odoo 19 JSON-RPC params."""
import json


def parse_api_payload(raw_body):
    payload = json.loads(raw_body)
    if isinstance(payload, dict) and payload.get('jsonrpc') == '2.0':
        params = payload.get('params', {})
        if not isinstance(params, dict):
            raise ValueError('JSON-RPC params must be an object.')
        return params
    return payload
