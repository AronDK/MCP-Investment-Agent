import os
import json
import re
import functions_framework
from google.cloud import secretmanager
import traceback
import requests
import sheets_tool_advanced as sheets_tool

def get_secret(secret_name, project_id):
    """Retrieves a secret from Google Cloud Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        raise

# --- Configuration ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "your-google-sheet-id")
# MODIFICATION: Increased reasoning steps
MAX_REASONING_STEPS = 10 
CASH_ON_HAND_CELL = 'Portfolio Summary!B3'

# --- Initialize clients and tools ---
try:
    print("--- Initializing components ---")
    # MODIFICATION: Removed TAVILY_API_KEY
    GROK_API_KEY = os.environ.get("GROK_API_KEY")
    
    if not GROK_API_KEY:
        raise ValueError("GROK_API_KEY environment variable not set.")
    
    print("Grok API key configured.")

    print("Fetching credentials from Secret Manager...")
    sheets_credentials_json = get_secret("google-sheets-credentials", GCP_PROJECT_ID)
    print("Credentials fetched successfully.")

    print("Initializing SheetsTool...")
    sheets = sheets_tool.SheetsTool(json.loads(sheets_credentials_json), GOOGLE_SHEET_ID)
    print("SheetsTool initialized successfully.")
    
    print("APIs initialized successfully.")
    print("--- All components initialized ---")

except Exception as e:
    print(f"CRITICAL: Failed during initialization. Error: {e}")
    traceback.print_exc()
    sheets = None

# --- ReAct Prompting Framework ---
def build_react_prompt(objective, history):
    """Builds the prompt for the ReAct loop."""
    if len(history) > 4000:
        history = "..." + history[-4000:]
    
    tool_definitions = """
    AVAILABLE TOOLS:
    1. web_search(query: str): Search the web for current market information, news, and stock prices.
    2. sheets_get_cell_value(cell_notation: str): Read data from a single spreadsheet cell.
    3. sheets_get_range_values(range_notation: str): Read data from a range of spreadsheet cells.
    4. sheets_update_cell_value(cell_notation: str, value: any): Update spreadsheet data.
    5. final_decision(action: str, symbol: str, quantity: float, target_price: float, rationale: str): Make final investment decision.
    """
    
    prompt = f"""
    You are an autonomous investment agent managing a portfolio.
    
    OBJECTIVE: {objective}
    PREVIOUS ACTIONS: {history}
    
    Your task: Analyze the data and make your next decision. Return valid JSON only.
    
    JSON format required:
    {{
        "thought": "your investment analysis",
        "action": {{
            "tool_name": "name_of_tool_to_use",
            "parameters": {{"parameter_name": "parameter_value"}}
        }}
    }}
    
    {tool_definitions}
    
    Make smart investment decisions based on current market data.
    """
    return prompt

def call_grok_api(prompt, use_search=False):
    """Call Grok API for investment analysis, with an option for web search."""
    try:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROK_API_KEY}"
        }
        
        data = {
            "messages": [
                {"role": "system", "content": "You are Grok, a highly intelligent, helpful AI assistant. Return only valid JSON responses in the exact format requested."},
                {"role": "user", "content": prompt}
            ],
            "model": "grok-4-0709",
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        # --- MODIFICATION: Enable Grok's native search when needed ---
        if use_search:
            data["internet_search"] = True
            print("Grok web search enabled for this call.")

        response = requests.post(url, headers=headers, json=data, timeout=60) # 60s timeout for search
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP Error calling Grok API: {http_err}")
        print(f"Response status code: {http_err.response.status_code}")
        print(f"Response text: {http_err.response.text}")
        return None
    except Exception as e:
        print(f"General Error calling Grok API: {e}")
        traceback.print_exc()
        return None

def clean_and_convert_to_float(value_str):
    """Removes currency symbols and commas, then converts to float."""
    if isinstance(value_str, (int, float)):
        return float(value_str)
    cleaned_str = re.sub(r'[$,]', '', str(value_str))
    return float(cleaned_str)

@functions_framework.http
def run_investment_cycle(request):
    """Orchestrates the ReAct loop for autonomous analysis and decision-making."""
    if not sheets:
        return ("A critical component was not initialized.", 500)

    print("--- Starting new autonomous investment cycle ---")

    try:
        visible_sheets = sheets.list_all_worksheets()
        print(f"DEBUG: Service account can see the following worksheets: {visible_sheets}")

        initial_portfolio = sheets.get_portfolio_and_market_data()
        cash_on_hand_str = sheets.get_cell_value(CASH_ON_HAND_CELL)
        cash_on_hand = clean_and_convert_to_float(cash_on_hand_str)
        print(f"Initial cash on hand: {cash_on_hand}")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not read initial state from sheet. Error: {e}")
        traceback.print_exc()
        return (f"Could not read initial state from sheet. Error: {e}", 500)

    objective = f"""
    Analyze the current portfolio, research relevant stocks, perform modeling, and conclude with a single trading decision. You must consider your available cash of ${cash_on_hand:,.2f}. Current portfolio: {json.dumps(initial_portfolio)}
    """
    
    history = f"Observation: Cycle started with ${cash_on_hand:,.2f} cash. Visible sheets are: {visible_sheets}"
    recent_actions = []
    
    for i in range(MAX_REASONING_STEPS):
        print(f"\n--- Reasoning Step {i+1}/{MAX_REASONING_STEPS} ---")
        
        prompt = build_react_prompt(objective, history)
        
        try:
            # The main reasoning call does NOT use search by default
            response_text = call_grok_api(prompt, use_search=False)
            
            if not response_text:
                raise ValueError("Empty response from Grok API")

            print(f"Raw Grok response: '{response_text}'")
            decision_json = json.loads(response_text)
            thought = decision_json.get('thought', 'No analysis provided')
            action_details = decision_json.get('action', {})
            tool_name = action_details.get('tool_name')
            parameters = action_details.get('parameters', {})
            
            print(f"Thought: {thought}")
            print(f"Action: {tool_name} with {parameters}")
            
        except Exception as e:
            print(f"Error processing Grok response: {e}")
            history += f"\nObservation: Grok response error. Trying a different approach."
            continue

        if not tool_name:
            print("No tool chosen by agent. Ending cycle.")
            break
        
        action_signature = f"{tool_name}({json.dumps(parameters, sort_keys=True)})"
        recent_actions.append(action_signature)
        if len(recent_actions) > 2 and len(set(recent_actions[-3:])) == 1:
            print(f"LOOP DETECTED: Agent is repeating the same action: {action_signature}")
            history += f"\nObservation: Loop detected. Please try a different tool or make a final_decision."
            continue
        
        observation = ""
        if tool_name == 'final_decision':
            print("Agent has reached a final investment decision.")
            action = parameters.get('action', 'HOLD').upper()
            rationale = parameters.get('rationale', 'No investment rationale provided.')
            
            if action in ['BUY', 'SELL']:
                quantity = float(parameters.get('quantity', 0))
                price = float(parameters.get('target_price', 0))
                trade_value = quantity * price

                if action == 'BUY' and trade_value > cash_on_hand:
                    observation = f"INSUFFICIENT FUNDS. Cannot execute BUY order of ${trade_value:,.2f} with only ${cash_on_hand:,.2f} available."
                    history += f"\nThought: {thought}\nAction: {action_signature}\nObservation: {observation}"
                    continue

                sheets.log_transaction(
                    symbol=parameters.get('symbol'),
                    action=action,
                    quantity=quantity,
                    price=price,
                    rationale=rationale
                )
                new_cash_balance = cash_on_hand - trade_value if action == 'BUY' else cash_on_hand + trade_value
                sheets.update_cell_value(CASH_ON_HAND_CELL, new_cash_balance)
                print(f"Account balance updated to: ${new_cash_balance:,.2f}")
            else:
                print(f"HOLD decision made with rationale: {rationale}")
            
            print("--- Investment cycle completed successfully ---")
            return ("Investment cycle completed.", 200)

        elif tool_name == 'web_search':
            # --- MODIFICATION: Call Grok API with search enabled ---
            search_query = parameters.get('query', '')
            observation = call_grok_api(f"Please perform a web search for: '{search_query}' and provide a concise summary.", use_search=True)
        elif tool_name == 'sheets_get_cell_value':
            observation = sheets.get_cell_value(**parameters)
        elif tool_name == 'sheets_get_range_values':
            observation = sheets.get_range_values(**parameters)
        elif tool_name == 'sheets_update_cell_value':
            observation = sheets.update_cell_value(**parameters)
        else:
            observation = f"Unknown tool '{tool_name}'."
            
        print(f"Observation: {observation}")
        history += f"\nThought: {thought}\nAction: {action_signature}\nObservation: {str(observation)}"

    print("Max reasoning steps reached. Ending cycle.")
    return ("Cycle ended due to max steps.", 200)
