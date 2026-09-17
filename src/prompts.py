INVOICE_EXTRACTION_PROMPT = """
Please extract information from the invoice strictly into the following JSON format.
Pay special attention to the line items table and the currency.
Format all dates in the standard YYYY-MM-DD format (e.g., 2023-10-24).
If any information is missing, leave the field null.
Do not add any explanations or markdown formatting outside the JSON object.

Expected JSON Template to fill:
{
    "invoice_number": null,
    "iban": null,
    "dates": {
        "issue_date": null,
        "sale_date": null,
        "due_date": null
    },
    "seller": {
        "name": null,
        "address": null,
        "vat_id": null
    },
    "buyer": {
        "name": null,
        "address": null,
        "vat_id": null
    },
    "line_items": [
        {
            "description": null,
            "quantity": null,
            "net_value": null,
            "var_rate": null
        }
    ],
    "summary": {
        "total_net": null,
        "total_vat": null,
        "total_due": null,
        "currency": null
    }
}
"""

