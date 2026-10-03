#!/usr/bin/env python3
"""Smoke test script for live WooCommerce integration.

Runs representative read-only calls against a live WooCommerce store if
credentials are provided in the environment or .env file.
If credentials are not present, outputs setup instructions and exits gracefully.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

from woocommerce_connector.client import WooCommerceClient
from woocommerce_connector.config import ConfigurationError, Settings


async def run_live_smoke_test(settings: Settings) -> None:
    """Execute live read-only verification calls against the configured WooCommerce store."""
    print("=" * 70)
    print(f"Connecting to WooCommerce store: {settings.woocommerce_url}")
    print(f"Consumer Key: {settings.woocommerce_consumer_key[:6]}... (masked)")
    print("=" * 70)

    async with WooCommerceClient(settings=settings) as client:
        # 1. Test Products List
        print("\n[1/5] Testing list_products(page=1, limit=5)...")
        prod_resp = await client.list_products(page=1, limit=5)
        if prod_resp.success:
            count = len(prod_resp.data) if prod_resp.data else 0
            print(f"  ✓ Success! Retrieved {count} product(s).")
            sample_product_id = prod_resp.data[0]["id"] if count > 0 else None
        else:
            print(f"  ✗ Failed: {prod_resp.error.code} - {prod_resp.error.message}")
            sample_product_id = None

        # 2. Test Single Product Get
        if sample_product_id:
            print(f"\n[2/5] Testing get_product(product_id={sample_product_id})...")
            single_prod_resp = await client.get_product(sample_product_id)
            if single_prod_resp.success:
                print(f"  ✓ Success! Product name: '{single_prod_resp.data.get('name')}' (SKU: {single_prod_resp.data.get('sku')})")
            else:
                print(f"  ✗ Failed: {single_prod_resp.error.code} - {single_prod_resp.error.message}")
        else:
            print("\n[2/5] Skipping get_product (no products found in store).")

        # 3. Test Product Search
        print("\n[3/5] Testing search_products(query='shirt', page=1, limit=5)...")
        search_prod_resp = await client.search_products(query="shirt", page=1, limit=5)
        if search_prod_resp.success:
            count = len(search_prod_resp.data) if search_prod_resp.data else 0
            print(f"  ✓ Success! Found {count} matching product(s).")
        else:
            print(f"  ✗ Failed: {search_prod_resp.error.code} - {search_prod_resp.error.message}")

        # 4. Test Orders List
        print("\n[4/5] Testing list_orders(page=1, limit=5)...")
        order_resp = await client.list_orders(page=1, limit=5)
        if order_resp.success:
            count = len(order_resp.data) if order_resp.data else 0
            print(f"  ✓ Success! Retrieved {count} order(s).")
            sample_order_id = order_resp.data[0]["id"] if count > 0 else None
        else:
            print(f"  ✗ Failed: {order_resp.error.code} - {order_resp.error.message}")
            sample_order_id = None

        # 5. Test Single Order Get
        if sample_order_id:
            print(f"\n[5/5] Testing get_order(order_id={sample_order_id})...")
            single_order_resp = await client.get_order(sample_order_id)
            if single_order_resp.success:
                print(f"  ✓ Success! Order #{single_order_resp.data.get('order_number')} "
                      f"Status: {single_order_resp.data.get('status')}, Total: {single_order_resp.data.get('total')}")
            else:
                print(f"  ✗ Failed: {single_order_resp.error.code} - {single_order_resp.error.message}")
        else:
            print("\n[5/5] Skipping get_order (no orders found in store).")

    print("\n" + "=" * 70)
    print("Smoke test finished.")
    print("=" * 70)


def main() -> None:
    load_dotenv()

    try:
        settings = Settings.from_env(require_credentials=True)
    except ConfigurationError as err:
        print("\n" + "=" * 70)
        print("LIVE SMOKE TEST: Credentials Not Configured (Skipping)")
        print("=" * 70)
        print("Reason:", err)
        print("\nTo test against a real WooCommerce store:")
        print("1. Copy .env.example to .env")
        print("2. Set WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, and WOOCOMMERCE_CONSUMER_SECRET")
        print("3. Re-run: python scripts/smoke_test.py\n")
        sys.exit(0)

    asyncio.run(run_live_smoke_test(settings))


if __name__ == "__main__":
    main()
