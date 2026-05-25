# Demo: convert_currency

**Archetype:** Data transformation + external API (free, no key required)

## Description to pass to `create_tool`

```
Create a tool called convert_currency that converts an amount between NGN, USD, EUR, and GBP using live rates from open.er-api.com (free, no key). It should take amount (number), from_currency, and to_currency. Return the converted amount, the exchange rate used, and a timestamp.
```

## How to create it

In Claude Desktop:

> "Use create_tool with this description: Create a tool called convert_currency that converts an amount between NGN, USD, EUR, and GBP using live rates from open.er-api.com (free, no key). It should take amount (number), from_currency, and to_currency. Return the converted amount, the exchange rate used, and a timestamp."

## Expected tool input

```json
{
  "amount": 10000,
  "from_currency": "NGN",
  "to_currency": "USD"
}
```

## Expected tool output

```json
{
  "status": "success",
  "data": {
    "original_amount": 10000,
    "from_currency": "NGN",
    "to_currency": "USD",
    "converted_amount": 6.25,
    "exchange_rate": 0.000625,
    "timestamp": "2026-05-21T10:30:00Z"
  },
  "message": "10000 NGN = 6.25 USD at rate 0.000625"
}
```

## What this demonstrates

- Live exchange rate API call
- Input validation (currency code allow-list)
- Numeric precision handling
- Timestamp generation
