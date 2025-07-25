import os
import json
import re
import functions_framework
from google.cloud import secretmanager
import traceback
import time
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
MAX_REASONING_STEPS = 5 
CASH_ON_HAND_CELL = 'Portfolio Summary!B3'

# --- Initialize clients and tools ---
try:
    print("--- Initializing components ---")
    GROK_API_KEY = os.environ.get("GROK_API_KEY")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
    
    if not GROK_API_KEY:
        raise ValueError("GROK_API_KEY environment variable not set.")
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY environment variable not set.")
    
    print("Grok and Tavily API keys configured.")

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
    # Truncate history to avoid token limits
    if len(history) > 2000:
        history = "..." + history[-2000:]
    
    tool_definitions = """
    AVAILABLE TOOLS:
    1. sheets_get_cell_value(cell_notation: str): Read data from spreadsheet cells
    2. sheets_update_cell_value(cell_notation: str, value: any): Update spreadsheet data  
    3. web_search(query: str): Search the web for current market information
    4. final_decision(action: str, symbol: str, quantity: int, target_price: float, rationale: str): Make final investment decision
    
    Available data sources: Stock_Ref sheet and Ref sheet contain reference information.
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

def execute_web_search(query):
    """Execute web search using Tavily API"""
    print(f"Executing web search for: '{query}'")
    try:
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": 3,
            "search_depth": "advanced"
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        search_results = response.json()
        
        # Format results for the agent
        formatted_results = "\n".join([
            f"Title: {result.get('title', 'N/A')}\nContent: {result.get('content', 'N/A')}\nURL: {result.get('url', 'N/A')}\n"
            for result in search_results.get('results', [])
        ])
        
        return formatted_results if formatted_results else "No search results found."
        
    except Exception as e:
        print(f"Error during web search: {e}")
        return f"Error performing search: {e}"

def call_grok_api(prompt):
    """Call Grok API for investment analysis"""
    try:
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROK_API_KEY}"
        }
        
        data = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Grok, a highly intelligent, helpful AI assistant. Return only valid JSON responses in the exact format requested."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "model": "grok-4-0709",
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 300
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=3600)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
        
    except Exception as e:
        print(f"Error calling Grok API: {e}")
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
        # --- NEW DEBUGGING STEP ---
        # First, let's see what worksheets the service account can see.
        visible_sheets = sheets.list_all_worksheets()
        print(f"DEBUG: Service account can see the following worksheets: {visible_sheets}")
        # --- END DEBUGGING STEP ---

        initial_portfolio = sheets.get_portfolio_and_market_data()
        cash_on_hand_str = sheets.get_cell_value(CASH_ON_HAND_CELL)
        cash_on_hand = clean_and_convert_to_float(cash_on_hand_str)
        print(f"Initial cash on hand: {cash_on_hand}")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not read initial state from sheet. Error: {e}")
        traceback.print_exc()
        return (f"Could not read initial state from sheet. Error: {e}", 500)

    objective = f"""
    You are an autonomous investment agent managing a portfolio.
    
    Cash Available: ${cash_on_hand:,.2f}
    Current Portfolio: {json.dumps(initial_portfolio)}
    
    Investment objectives:
    1. If no holdings in portfolio: Analyze market data and identify good investment opportunities
    2. If holdings exist in portfolio: Analyze current positions and decide whether to:
       - Hold current positions
       - Buy more of existing holdings
       - Sell some positions
       - Buy new positions
    
    Use spreadsheet data and web search for current market information. Make profitable investment decisions.
    """
    
    history = f"Observation: Cycle started with ${cash_on_hand:,.2f} cash. Visible sheets are: {visible_sheets}"
    
    # Track recent actions to detect loops
    recent_actions = []
    
    for i in range(MAX_REASONING_STEPS):
        print(f"\n--- Reasoning Step {i+1}/{MAX_REASONING_STEPS} ---")
        print(f"Current history length: {len(history)} characters")
        
        prompt = build_react_prompt(objective, history)
        
        # No rate limiting needed for Grok - much more generous limits
        
        try:
            response_text = call_grok_api(prompt)
            
            if not response_text:
                print("Empty response detected. Using fallback logic.")
                # Use fallback logic
                if i == 0:
                    tool_name = "sheets_get_cell_value"
                    parameters = {"cell_notation": "Stock_Ref!A1"}
                    thought = "Starting analysis by examining reference information"
                else:
                    tool_name = "final_decision" 
                    parameters = {
                        "action": "HOLD",
                        "symbol": None,
                        "quantity": 0,
                        "target_price": None,
                        "rationale": "Analysis completed based on available information"
                    }
                    thought = "Completing investment analysis"
            else:
                print(f"Raw Grok response: '{response_text}'")
                
                decision_json = json.loads(response_text)
                thought = decision_json.get('thought', 'No analysis provided')
                action_details = decision_json.get('action', {})
                tool_name = action_details.get('tool_name')
                parameters = action_details.get('parameters', {})
            
            print(f"Thought: {thought}")
            print(f"Action: {tool_name} with {parameters}")
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            # Investment fallback: gather info or make decision
            if i == 0:  # First step, gather data
                tool_name = "sheets_get_cell_value"
                parameters = {"cell_notation": "Stock_Ref!A1"}
                thought = "Accessing reference data due to parsing error"
            else:  # Later steps, make investment decision
                tool_name = "final_decision"
                parameters = {
                    "action": "HOLD",
                    "symbol": "N/A", 
                    "quantity": 0,
                    "target_price": 0,
                    "rationale": "Investment analysis completed, maintaining current positions due to parsing limitations"
                }
                thought = "Concluding investment analysis due to parsing limitations"
        except Exception as e:
            print(f"Error with Grok API: {e}")
            history += f"\nObservation: API error. Trying fallback approach."
            continue

        if not tool_name:
            print("No tool chosen by agent. Ending cycle.")
            break
        
        # Check for repeated actions (potential loop)
        action_signature = f"{tool_name}({json.dumps(parameters, sort_keys=True)})"
        recent_actions.append(action_signature)
        if len(recent_actions) > 3:
            recent_actions.pop(0)
        
        if len(recent_actions) >= 3 and len(set(recent_actions)) == 1:
            print(f"LOOP DETECTED: Agent is repeating the same action: {action_signature}")
            history += f"\nObservation: Loop detected - you are repeating the same action. Please try a different approach or make a final_decision."
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
                    print(observation)
                    history += f"\nThought: {thought}\nAction: {tool_name}({json.dumps(parameters)})\nObservation: {observation}"
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

        elif tool_name == 'sheets_get_cell_value':
            observation = sheets.get_cell_value(**parameters)
        elif tool_name == 'sheets_update_cell_value':
            observation = sheets.update_cell_value(**parameters)
        elif tool_name == 'web_search':
            observation = execute_web_search(parameters.get('query', ''))
        else:
            observation = f"Unknown tool '{tool_name}'. Available tools: sheets_get_cell_value, sheets_update_cell_value, web_search, final_decision"
            
        print(f"Observation: {observation}")
        history += f"\nThought: {thought}\nAction: {tool_name}({json.dumps(parameters)})\nObservation: {observation}"

    print("Max reasoning steps reached. Ending cycle.")
    print(f"DEBUGGING: Recent actions taken: {recent_actions}")
    print(f"DEBUGGING: Final history length: {len(history)} characters")
    print(f"DEBUGGING: Last 500 characters of history: {history[-500:]}")
    return ("Cycle ended due to max steps.", 200)
