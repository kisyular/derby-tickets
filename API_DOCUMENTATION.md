# Tickets API Documentation

## Overview

The Tickets API provides JSON endpoints for external integrations to access ticket data. All API endpoints require authentication via API tokens.

## Authentication

All API requests must include a valid API token. Tokens can be provided in three ways:

### 1. Authorization Header (Recommended)

```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" http://127.0.0.1:8000/api/tickets/
```

### 2. X-API-Token Header

```bash
curl -H "X-API-Token: YOUR_TOKEN_HERE" http://127.0.0.1:8000/api/tickets/
```

### 3. Query Parameter

```bash
curl "http://127.0.0.1:8000/api/tickets/?token=YOUR_TOKEN_HERE"
```

## Endpoints

### GET /api/tickets/

Returns all tickets in the system.

**Response Format:**

```json
{
  "success": true,
  "count": 2,
  "tickets": [
    {
      "ticket_number": "6140",
      "title": "Create a client application",
      "description": "Detailed description...",
      "category": "Checksheets",
      "created_by": "John Doe",
      "assigned_to": "Jane Smith",
      "status": "Open",
      "priority": "High",
      "location": "Corporate",
      "department": "IT",
      "created_at": "2025-08-21T19:20:51+00:00",
      "closed_on": null
    }
  ],
  "timestamp": "2025-08-26T15:30:00+00:00"
}
```

### GET /api/tickets/{id}/

Returns a specific ticket by ID.

**Response Format:**

```json
{
  "success": true,
  "ticket": {
    "ticket_number": "6140",
    "title": "Create a client application",
    "description": "Detailed description...",
    "category": "Checksheets",
    "created_by": "John Doe",
    "assigned_to": "Jane Smith",
    "status": "Open",
    "priority": "High",
    "location": "Corporate",
    "department": "IT",
    "created_at": "2025-08-21T19:20:51+00:00",
    "closed_on": null
  },
  "timestamp": "2025-08-26T15:30:00+00:00"
}
```

## Field Descriptions

| Field         | Type   | Description                                  |
| ------------- | ------ | -------------------------------------------- |
| ticket_number | string | Unique ticket identifier                     |
| title         | string | Brief ticket title                           |
| description   | string | Detailed ticket description                  |
| category      | string | Ticket category name                         |
| created_by    | string | Full name of ticket creator                  |
| assigned_to   | string | Full name of assigned user (if any)          |
| status        | string | Current ticket status                        |
| priority      | string | Ticket priority level                        |
| location      | string | Location associated with ticket              |
| department    | string | Department associated with ticket            |
| created_at    | string | ISO 8601 timestamp of creation               |
| closed_on     | string | ISO 8601 timestamp of closure (null if open) |

## Status Codes

- `200 OK` - Request successful
- `401 Unauthorized` - Invalid or missing API token
- `404 Not Found` - Ticket not found (for specific ticket endpoint)
- `405 Method Not Allowed` - Unsupported HTTP method
- `500 Internal Server Error` - Server error

## Error Response Format

```json
{
  "success": false,
  "error": "Error description",
  "detail": "Additional error details (optional)",
  "timestamp": "2025-08-26T15:30:00+00:00"
}
```

## Managing API Tokens

### Create a Token

```bash
python manage.py api_tokens --create --name "Integration Name" --user admin
```

### List All Tokens

```bash
python manage.py api_tokens --list
```

### Deactivate a Token

```bash
python manage.py api_tokens --deactivate TOKEN_ID_OR_VALUE
```

### Activate a Token

```bash
python manage.py api_tokens --activate TOKEN_ID_OR_VALUE
```

## Example Usage

### Python with requests

```python
import requests

token = "YOUR_TOKEN_HERE"
headers = {"Authorization": f"Bearer {token}"}

# Get all tickets
response = requests.get("http://127.0.0.1:8000/api/tickets/", headers=headers)
data = response.json()

for ticket in data['tickets']:
    print(f"Ticket {ticket['ticket_number']}: {ticket['title']}")
```

### PowerShell

```powershell
$token = "YOUR_TOKEN_HERE"
$headers = @{"Authorization" = "Bearer $token"}

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/tickets/" -Headers $headers
$data = $response.Content | ConvertFrom-Json

foreach ($ticket in $data.tickets) {
    Write-Host "Ticket $($ticket.ticket_number): $($ticket.title)"
}
```

### cURL

```bash
TOKEN="YOUR_TOKEN_HERE"
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://127.0.0.1:8000/api/tickets/
```

## Security Notes

- Store API tokens securely and never expose them in client-side code
- Tokens are shown only once during creation
- Deactivate unused tokens immediately
- Monitor token usage via the `last_used` field
- Consider setting expiration dates for tokens used in temporary integrations
