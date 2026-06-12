#!/usr/bin/env python3
import sys

from last_translation_benchmark.utils import get_config
from openrouter import OpenRouter

def format_usd(val):
    if val is None:
        return "N/A"
    return f"${val:,.1f}"

def format_usd_short(val):
    if val is None:
        return "N/A"
    return f"${val:,.1f}"

def main():
    # Load API key
    key = get_config("OPENROUTER_API_KEY")
    if not key:
        print("Error: OPENROUTER_API_KEY is not configured in config.toml or environment variables.")
        sys.exit(1)

    print("Initializing OpenRouter client...")
    client = OpenRouter(api_key=key)

    try:
        print("Querying current key metadata and credits...")
        meta_resp = client.api_keys.get_current_key_metadata()
        creds_resp = client.credits.get_credits()
    except Exception as e:
        print(f"\nError calling OpenRouter API: {e}")
        print("Please check if your OPENROUTER_API_KEY is valid and your network connection is active.")
        sys.exit(1)

    meta = meta_resp.data if hasattr(meta_resp, "data") else None
    creds = creds_resp.data if hasattr(creds_resp, "data") else None

    if not meta:
        print("Error: Failed to retrieve key metadata.")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("           OPENROUTER API KEY STATUS & LIMITS")
    print("=" * 55)
    print(f"Key Label:          {meta.label}")
    print(f"Creator User ID:    {meta.creator_user_id}")
    print(f"Expires At:         {meta.expires_at or 'Never'}")
    print("-" * 55)

    print("Usage and Limits for this Key:")
    print(f"  Usage (All-time): {format_usd(meta.usage)}")
    print(f"  Usage (Daily):    {format_usd(meta.usage_daily)}")
    print(f"  Usage (Weekly):   {format_usd(meta.usage_weekly)}")
    print(f"  Usage (Monthly):  {format_usd(meta.usage_monthly)}")
    print(f"  Key Limit:        {format_usd(meta.limit)}")
    print(f"  Limit Remaining:  {format_usd(meta.limit_remaining)}")
    print(f"  Limit Reset:      {meta.limit_reset}")

    if creds:
        print("-" * 55)
        print("OpenRouter Account Credits:")
        print(f"  Total Credits:    {format_usd_short(creds.total_credits)}")
        print(f"  Total Usage:      {format_usd_short(creds.total_usage)}")
        balance = creds.total_credits - creds.total_usage
        print(f"  Remaining Credit: {format_usd_short(balance)}")

    print("=" * 55 + "\n")

if __name__ == "__main__":
    main()
