"""Automated browser capture via Chrome DevTools Protocol and M1 Finance GraphQL API."""

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import websocket

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://lens.m1.com/graphql"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

ACCOUNTS_AND_BALANCES_QUERY = """
query GetAccountsAndBalances {
  viewer {
    accounts(first: 50) {
      edges {
        node {
          id
          name
          isCryptoAccount
          isRetirement
          isActive
          rootPortfolioSlice {
            id
            chartData {
              name
              data {
                date
                close
              }
            }
          }
        }
      }
    }
    netWorth {
      chartData {
        name
        data {
          date
          close
        }
      }
    }
    borrow {
      hasBorrowAccounts
      borrowAccounts {
        edges {
          node {
            id
            name
            hasBorrowedBefore
            hasCreditBorrowed
            creditBorrowed
            creditAvailable
            creditLimit
            investAccount {
              id
              name
            }
          }
        }
      }
    }
  }
}
"""

ACTIVITIES_QUERY = """
query InvestActivityById($id: ID!, $first: Int, $after: String) {
  node(id: $id) {
    ... on Account {
      investActivity {
        activity(first: $first, after: $after, neverSummarizeTrades: true) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              __typename
              id
              title
              date(local: true)
              description
              ... on InvestActivityTradeEntry {
                isBuy
                quantity
                sharePrice
                amount
                tradeSecurity {
                  descriptor
                  security {
                    symbol
                    name
                  }
                }
              }
              ... on InvestActivityCashEntry {
                amount
                isRelatedToSecurity
                cashSecurity {
                  descriptor
                  security {
                    symbol
                    name
                  }
                }
                transferDetails {
                  transferSummary
                  transferId
                  totalAmount
                }
              }
              ... on InvestActivityPositionEntry {
                quantity
                positionSecurity {
                  symbol
                  descriptor
                  security {
                    symbol
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

AUTH0_TOKEN_EVAL_SCRIPT = """
(() => {
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k.startsWith('@@auth0spajs@@')) {
            try {
                const data = JSON.parse(localStorage.getItem(k));
                if (data && data.body && data.body.access_token) {
                    return data.body.access_token;
                }
            } catch (e) {}
        }
    }
    return null;
})()
"""


class M1CaptureError(Exception):
    """Exception raised when capturing data from M1 fails."""
    pass


def extract_token_from_chrome(port: int = 9222) -> str:
    """Connect to a running Chrome instance via CDP and extract the Auth0 access token.

    Args:
        port: Remote debugging port for Chrome (default: 9222).

    Returns:
        The Bearer token extracted from localStorage.

    Raises:
        M1CaptureError: If Chrome cannot be reached or token is not found.
    """
    json_url = f"http://localhost:{port}/json"
    try:
        req = urllib.request.Request(json_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            tabs = json.loads(resp.read().decode())
    except Exception as e:
        raise M1CaptureError(
            f"Failed to connect to Chrome at {json_url}. Is Chrome running with "
            f"--remote-debugging-port={port}? Error: {e}"
        ) from e

    target_tab = None
    for tab in tabs:
        url = tab.get("url", "")
        if "m1.com" in url or "m1finance.com" in url:
            target_tab = tab
            break

    if not target_tab and tabs:
        target_tab = tabs[0]

    if not target_tab or "webSocketDebuggerUrl" not in target_tab:
        raise M1CaptureError("No suitable Chrome tab found for M1 Finance.")

    ws_url = target_tab["webSocketDebuggerUrl"]
    try:
        ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        eval_payload = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": AUTH0_TOKEN_EVAL_SCRIPT,
                "returnByValue": True,
            },
        }
        ws.send(json.dumps(eval_payload))
        response_raw = ws.recv()
        ws.close()
        res = json.loads(response_raw)
        token = res.get("result", {}).get("result", {}).get("value")
        if not token:
            raise M1CaptureError(
                "M1 Auth0 token not found in Chrome localStorage. "
                "Ensure you are logged into dashboard.m1.com."
            )
        return str(token)
    except Exception as e:
        if isinstance(e, M1CaptureError):
            raise
        raise M1CaptureError(f"CDP WebSocket communication error: {e}") from e


def query_graphql(
    token: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Execute a GraphQL query against M1 Lens endpoint.

    Args:
        token: Bearer JWT token.
        query: GraphQL query string.
        variables: Optional GraphQL variables dictionary.
        timeout: HTTP request timeout in seconds.

    Returns:
        Parsed JSON dictionary from GraphQL response.

    Raises:
        M1CaptureError: If HTTP or GraphQL errors occur.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "Origin": "https://dashboard.m1.com",
        "Referer": "https://dashboard.m1.com/",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GRAPHQL_ENDPOINT, data=data_bytes, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "errors" in data and not data.get("data"):
                raise M1CaptureError(f"GraphQL error: {data['errors']}")
            return data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise M1CaptureError(f"HTTP Error {e.code}: {e.reason} - {err_body}") from e
    except Exception as e:
        raise M1CaptureError(f"Failed to query M1 GraphQL: {e}") from e


def fetch_all_m1_data(
    token: Optional[str] = None,
    port: int = 9222,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """Capture all account metadata, daily balance histories, and transaction activities.

    Args:
        token: Optional Bearer token. If omitted, extracts from Chrome on port.
        port: Chrome remote debugging port.
        progress_callback: Optional callable(message: str) to report progress.

    Returns:
        Structured dictionary containing captured data.
    """
    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            logger.info(msg)

    if not token:
        log(f"Extracting Auth0 token from Chrome CDP on port {port}...")
        token = extract_token_from_chrome(port)
        log("Auth0 token retrieved successfully.")

    log("Fetching accounts, daily balance histories, and net worth...")
    overview_resp = query_graphql(token, ACCOUNTS_AND_BALANCES_QUERY)
    viewer = overview_resp.get("data", {}).get("viewer", {})

    accounts_edges = viewer.get("accounts", {}).get("edges", [])
    accounts_data = [edge["node"] for edge in accounts_edges if "node" in edge]
    net_worth = viewer.get("netWorth", {})
    borrow = viewer.get("borrow", {})

    log(f"Found {len(accounts_data)} accounts.")

    activities_by_account: Dict[str, List[Dict[str, Any]]] = {}

    for acc in accounts_data:
        acc_id = acc["id"]
        acc_name = acc["name"]
        log(f"Fetching transaction activities for account '{acc_name}'...")
        acc_activities: List[Dict[str, Any]] = []
        after: Optional[str] = None

        while True:
            variables: Dict[str, Any] = {"id": acc_id, "first": 100}
            if after:
                variables["after"] = after

            resp = query_graphql(token, ACTIVITIES_QUERY, variables)
            node = resp.get("data", {}).get("node", {})
            invest_activity = node.get("investActivity", {})
            activity_data = invest_activity.get("activity", {})

            edges = activity_data.get("edges", [])
            for edge in edges:
                if "node" in edge:
                    acc_activities.append(edge["node"])

            page_info = activity_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

        log(f"Account '{acc_name}': captured {len(acc_activities)} activities.")
        activities_by_account[acc_id] = acc_activities

    captured_payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts_data,
        "net_worth": net_worth,
        "borrow": borrow,
        "activities": activities_by_account,
    }
    return captured_payload


def save_captured_data(data: Dict[str, Any], filepath: str) -> None:
    """Save captured payload to a JSON file.

    Args:
        data: Structured captured dictionary.
        filepath: Destination file path.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
