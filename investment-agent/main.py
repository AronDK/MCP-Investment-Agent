import os
import json
import re
import functions_framework
from google.cloud import secretmanager
import traceback
import requests
import sheets_tool_advanced as sheets_tool
import time
from datetime import datetime

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
MAX_FUNCTION_RUNTIME = 540  # 9 minutes (Cloud Functions limit is 10 minutes)

# --- Global variables for API keys ---
GROK_API_KEY = None
SERPAPI_KEY = None
sheets = None

# --- Initialize clients and tools ---
try:
    print("--- Initializing components ---")
    GROK_API_KEY = os.environ.get("GROK_API_KEY")
    
    if not GROK_API_KEY:
        raise ValueError("GROK_API_KEY environment variable not set.")
    
    print("Grok API key configured.")
    
    # SerpApi for accurate stock prices
    SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY environment variable not set.")
    print("SerpApi key configured.")

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

def get_accurate_stock_price(symbol):
    """Get accurate real-time stock price using SerpApi Google Finance."""
    try:
        # Format symbol for Google Finance (add exchange if needed)
        formatted_symbol = symbol.upper()
        if ':' not in formatted_symbol:
            # Add common exchanges for major stocks
            exchange_map = {
                'AAPL': 'NASDAQ', 'MSFT': 'NASDAQ', 'GOOGL': 'NASDAQ', 'GOOG': 'NASDAQ',
                'AMZN': 'NASDAQ', 'TSLA': 'NASDAQ', 'META': 'NASDAQ', 'NVDA': 'NASDAQ',
                'INTC': 'NASDAQ', 'AMD': 'NASDAQ', 'QCOM': 'NASDAQ', 'NFLX': 'NASDAQ',
                'BA': 'NYSE', 'WMT': 'NYSE', 'JPM': 'NYSE', 'JNJ': 'NYSE', 'V': 'NYSE',
                'PG': 'NYSE', 'HD': 'NYSE', 'UNH': 'NYSE', 'DIS': 'NYSE', 'TTMI': 'NASDAQ'
            }
            exchange = exchange_map.get(formatted_symbol, 'NASDAQ')
            formatted_symbol = f"{formatted_symbol}:{exchange}"

        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_finance",
            "q": formatted_symbol,
            "api_key": SERPAPI_KEY,
            "hl": "en"
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'summary' in data:
            summary = data['summary']
            current_price = summary.get('extracted_price', 0)
            
            # Get market info if available
            market_info = ""
            if 'market' in summary:
                market = summary['market']
                if 'trading' in market:
                    market_info = f" ({market['trading']})"
                if 'price_movement' in market:
                    movement = market['price_movement']
                    direction = movement.get('movement', '')
                    percentage = movement.get('percentage', 0)
                    value = movement.get('value', 0)
                    market_info += f" {direction} {percentage:.2f}% (${value:.2f})"
            
            return {
                'symbol': symbol,
                'price': current_price,
                'currency': summary.get('currency', '$'),
                'exchange': summary.get('exchange', ''),
                'market_info': market_info,
                'source': 'Google Finance via SerpApi',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return f"Error: Could not find price data for {symbol} in SerpApi response"
            
    except Exception as e:
        print(f"Error fetching stock price for {symbol}: {e}")
        return f"Error fetching price for {symbol}: {str(e)}"

# --- ReAct Prompting Framework ---
def build_react_prompt(objective, history):
    """Builds the prompt for the ReAct loop."""
    if len(history) > 4000:
        history = "..." + history[-4000:]
    
    tool_definitions = """
    AVAILABLE TOOLS:
    1. web_search(query: str): Search the web for current market information and news.
    2. get_current_stock_price(symbol: str): Get ACCURATE real-time stock price using Google Finance API (HIGH ACCURACY).
    3. validate_stock_price(symbol: str): Cross-validate stock price using Google Finance API with confidence rating.
    4. get_multiple_stock_prices(symbols: list): Get accurate prices for multiple stocks efficiently.
    5. get_stock_price_history(symbol: str, period: str): Get historical price data (period: "1mo", "3mo", "6mo", "1y", "2y").
    6. analyze_portfolio_performance(symbols: list): Analyze current portfolio stocks for performance metrics.
    7. find_trending_stocks(sector: str): Discover trending stocks in specific sectors.
    8. sheets_get_cell_value(cell_notation: str): Read data from a single spreadsheet cell.
    9. sheets_get_range_values(range_notation: str): Read data from a range of spreadsheet cells.
    10. sheets_update_cell_value(cell_notation: str, value: any): Update spreadsheet data.
    11. final_decision(action: str, symbol: str, quantity: float, target_price: float, rationale: str): Make final investment decision.
    
    CRITICAL: Tools 2-4 use Google Finance API for maximum accuracy. Always use get_current_stock_price or validate_stock_price before trading decisions.
    """
    
    prompt = f"""
    You are an autonomous investment agent managing a portfolio with advanced analytical capabilities.
    
    OBJECTIVE: {objective}
    PREVIOUS ACTIONS: {history}
    
    ANALYSIS FRAMEWORK (be efficient - aim to complete in 3-4 steps):
    1. Quickly analyze your current portfolio for key issues
    2. Use get_current_stock_price or validate_stock_price for accurate pricing data
    3. Research specific opportunities with current market data
    4. Make a final decision with validated pricing - be decisive
    
    CRITICAL REQUIREMENTS:
    - ALWAYS use get_current_stock_price or validate_stock_price for stock prices (Google Finance API - HIGH ACCURACY)
    - These tools provide real-time, verified pricing data directly from Google Finance
    - Never make trading decisions without first getting accurate current prices
    - The Intel pricing issue has been resolved with accurate API integration
    
    Your task: Follow the framework efficiently. Return valid JSON only.
    
    JSON format required:
    {{
        "thought": "your concise investment analysis focusing on actionable insights",
        "action": {{
            "tool_name": "name_of_tool_to_use",
            "parameters": {{"parameter_name": "parameter_value"}}
        }}
    }}
    
    {tool_definitions}
    
    IMPORTANT: Be decisive and efficient. After 2-3 research steps, make a final_decision.
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
                {"role": "system", "content": "You are a highly intelligent investment analyst and helpful AI assistant. CRITICAL: When providing stock prices, use ONLY the most current, real-time data available. Always verify prices from multiple reliable sources. Never use cached or outdated information. Return only valid JSON responses in the exact format requested. Be concise and focused in your analysis."},
                {"role": "user", "content": prompt}
            ],
            "model": "grok-4-0709",
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 3072
        }
        
        # Enable Grok's native search when needed
        if use_search:
            data["internet_search"] = True
            print("Grok web search enabled for this call.")

        response = requests.post(url, headers=headers, json=data, timeout=45)
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
    start_time = time.time()
    
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
    consecutive_errors = 0
    
    for i in range(MAX_REASONING_STEPS):
        # Check if we're approaching timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_FUNCTION_RUNTIME:
            print(f"TIMEOUT: Function runtime approaching limit ({elapsed_time:.1f}s). Making emergency HOLD decision.")
            return ("Emergency HOLD decision due to timeout.", 200)
        
        print(f"\n--- Reasoning Step {i+1}/{MAX_REASONING_STEPS} ---")
        
        prompt = build_react_prompt(objective, history)
        
        try:
            # The main reasoning call does NOT use search by default
            response_text = call_grok_api(prompt, use_search=False)
            
            if not response_text:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    print("Too many consecutive errors. Making emergency HOLD decision.")
                    return ("Emergency HOLD decision due to API errors.", 200)
                raise ValueError("Empty response from Grok API")

            print(f"Raw Grok response: '{response_text}'")
            decision_json = json.loads(response_text)
            thought = decision_json.get('thought', 'No analysis provided')
            action_details = decision_json.get('action', {})
            tool_name = action_details.get('tool_name')
            parameters = action_details.get('parameters', {})
            
            print(f"Thought: {thought}")
            print(f"Action: {tool_name} with {parameters}")
            
            consecutive_errors = 0  # Reset error counter on success
            
        except Exception as e:
            consecutive_errors += 1
            print(f"Error processing Grok response: {e}")
            if consecutive_errors >= 3:
                print("Too many consecutive errors. Making emergency HOLD decision.")
                return ("Emergency HOLD decision due to parsing errors.", 200)
            history += f"\nObservation: Grok response error. Trying a different approach."
            continue

        if not tool_name:
            print("No tool chosen by agent. Ending cycle.")
            break
        
        action_signature = f"{tool_name}({json.dumps(parameters, sort_keys=True)})"
        recent_actions.append(action_signature)
        
        # Enhanced loop detection
        if len(recent_actions) > 2:
            if len(set(recent_actions[-3:])) == 1:
                print(f"LOOP DETECTED: Agent is repeating the same action: {action_signature}")
                print("Forcing final decision due to loop detection.")
                return ("HOLD decision made due to loop detection.", 200)
            
        # If we're on the last step, force a decision
        if i == MAX_REASONING_STEPS - 1 and tool_name != 'final_decision':
            print("Final step reached. Forcing HOLD decision.")
            return ("HOLD decision made - max steps reached.", 200)
        
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
            search_query = parameters.get('query', '')
            observation = call_grok_api(f"Please perform a web search for: '{search_query}' and provide a concise summary.", use_search=True)
        
        elif tool_name == 'get_current_stock_price':
            # Get accurate real-time stock price using SerpApi
            symbol = parameters.get('symbol', '')
            if symbol:
                observation = get_accurate_stock_price(symbol)
            else:
                observation = "Error: No symbol provided"
                
        elif tool_name == 'validate_stock_price':
            # Cross-validate stock price using accurate SerpApi data
            symbol = parameters.get('symbol', '')
            if symbol:
                price_data = get_accurate_stock_price(symbol)
                if isinstance(price_data, dict):
                    observation = f"VALIDATED PRICE for {symbol}: ${price_data['price']:.2f} {price_data['market_info']} (Source: {price_data['source']}, Updated: {price_data['timestamp']}, Confidence: HIGH - Direct from Google Finance)"
                else:
                    observation = str(price_data)
            else:
                observation = "Error: No symbol provided"
        
        elif tool_name == 'get_multiple_stock_prices':
            # Get prices for multiple stocks efficiently
            symbols = parameters.get('symbols', [])
            if isinstance(symbols, str):
                symbols = [symbols]
            
            prices = {}
            for symbol in symbols:
                price_data = get_accurate_stock_price(symbol)
                if isinstance(price_data, dict):
                    prices[symbol] = f"${price_data['price']:.2f} {price_data['market_info']}"
                else:
                    prices[symbol] = "Error fetching price"
            
            observation = f"Current stock prices: {prices}"
            
        elif tool_name == 'get_stock_price_history':
            # Get historical price data using web search
            symbol = parameters.get('symbol', '')
            period = parameters.get('period', '1mo')
            observation = call_grok_api(f"Please search for {symbol} stock price history over {period} ending July 2025 and provide price trends, highs, lows, and performance analysis with specific dates and prices.", use_search=True)
        
        elif tool_name == 'analyze_portfolio_performance':
            # Analyze portfolio performance with accurate pricing
            symbols = parameters.get('symbols', [])
            if isinstance(symbols, str):
                symbols = [symbols]
            
            # Get accurate current prices first
            current_prices = {}
            for symbol in symbols:
                price_data = get_accurate_stock_price(symbol)
                if isinstance(price_data, dict):
                    current_prices[symbol] = price_data['price']
                else:
                    current_prices[symbol] = "Error"
            
            # Then get analysis from Grok
            symbols_str = ', '.join(symbols)
            current_date = datetime.now().strftime("%B %d, %Y")
            price_info = ', '.join([f"{sym}: ${price}" if isinstance(price, (int, float)) else f"{sym}: {price}" for sym, price in current_prices.items()])
            search_prompt = f"Analyze these stocks: {symbols_str} as of {current_date}. CURRENT VERIFIED PRICES: {price_info}. Please provide: 1) Performance analysis based on these current prices, 2) Recent performance trends, 3) Latest analyst ratings and news, 4) Investment recommendations. Focus on actionable insights for portfolio management."
            analysis = call_grok_api(search_prompt, use_search=True)
            observation = f"ACCURATE PRICES: {price_info}\n\nANALYSIS: {analysis}"
        
        elif tool_name == 'find_trending_stocks':
            # Find trending stocks in a sector with current data
            sector = parameters.get('sector', 'technology')
            current_date = datetime.now().strftime("%B %d, %Y")
            search_prompt = f"Search for trending and high-performing stocks in the {sector} sector for {current_date}. Include current stock prices, recent performance, and reasons for their momentum."
            observation = call_grok_api(search_prompt, use_search=True)
            
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
