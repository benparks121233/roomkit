# services/sourcing/canopy_client.py
# Owns: HTTP client for the Canopy REST API (canopyapi.co).
# Isolated and mockable — the only module that talks to the Canopy service.
#
# Canopy API:
#   Base URL: https://rest.canopyapi.co
#   Auth: API-KEY header
#   Search: GET /api/amazon/search?searchTerm=...&minPrice=&maxPrice=&limit=
#   Product: GET /api/amazon/product?asin=...
#
# IMPORTANT: This client is ONLY called by the refresh script
# (scripts/refresh_catalog.py). Normal adapter reads go through the
# local cache (data/catalog/). Tests mock this client — never live calls.

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE_URL = "https://rest.canopyapi.co"


class CanopyClient:
    """Thin HTTP client for Canopy REST API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("CANOPY_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "CANOPY_API_KEY not set. Pass api_key or set the env var."
            )

    def search_products(
        self,
        search_term: str,
        *,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search Amazon products via Canopy.

        Returns a list of raw product dicts from the API response.
        Each dict has: title, url, asin, price{value,currency,display,symbol},
        mainImageUrl, rating, ratingsTotal, isPrime.
        """
        params: dict[str, Any] = {"searchTerm": search_term, "limit": limit}
        if min_price is not None:
            params["minPrice"] = min_price
        if max_price is not None:
            params["maxPrice"] = max_price

        data = self._get("/api/amazon/search", params)

        # Navigate the nested response shape.
        search_results = data.get("data", {}).get("amazonProductSearchResults", {})
        product_results = search_results.get("productResults", {})
        return product_results.get("results", []) or []

    def get_product(self, asin: str) -> dict[str, Any] | None:
        """Fetch a single product by ASIN.

        Returns the raw product dict or None if not found.
        Dict has: title, url, asin, price{value,currency,display,symbol},
        mainImageUrl, imageUrls, brand, featureBullets, categories, isPrime,
        isInStock, rating, ratingsTotal.
        """
        data = self._get("/api/amazon/product", {"asin": asin})
        return data.get("data", {}).get("amazonProduct")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make a GET request to the Canopy API."""
        url = f"{_BASE_URL}{path}"
        headers = {
            "API-KEY": self._api_key,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
