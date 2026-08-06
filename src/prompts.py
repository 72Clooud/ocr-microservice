INVOICE_EXTRACTION_PROMPT = """
Please extract information from the invoice strictly into the following JSON format.
Pay special attention to the line items table and the currency.
If any information is missing, leave the field null.
Do not add any explanations or markdown formatting outside the JSON object.

Expected JSON Template to fill:
{
    "invoice_number": null,
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

