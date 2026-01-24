"""Builders para mensagens de localização e endereço."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest


class LocationPayloadBuilder:
    """Builder para mensagens de localização."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de localização."""
        return {
            "location": {
                "latitude": request.location_latitude,
                "longitude": request.location_longitude,
                "name": request.location_name or None,
                "address": request.location_address or None,
            }
        }


class AddressPayloadBuilder:
    """Builder para mensagens de endereço."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de endereço."""
        return {
            "address": {
                "street": request.address_street or None,
                "city": request.address_city or None,
                "state": request.address_state or None,
                "zip_code": request.address_zip_code or None,
                "country_code": request.address_country_code or None,
            }
        }
