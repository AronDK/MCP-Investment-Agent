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
MAX_REASONING_STEPS = 6
CASH_ON_HAND_CELL = 'Portfolio Summary!B3'
MAX_FUNCTION_RUNTIME = 540

# --- Global variables ---
GROK_API_KEY = None
SERPAPI_KEY = None
sheets = None

# --- Initialize components ---
try:
    print("--- Initializing components ---")
    GROK_API_KEY = os.environ.get("GROK_API_KEY")
    SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
    
    if not GROK_API_KEY or not SERPAPI_KEY:
        raise ValueError("Missing required API keys")
    
    sheets_credentials_json = get_secret("google-sheets-credentials", GCP_PROJECT_ID)
    sheets = sheets_tool.SheetsTool(json.loads(sheets_credentials_json), GOOGLE_SHEET_ID)
    print("--- All components initialized ---")

except Exception as e:
    print(f"CRITICAL: Failed during initialization. Error: {e}")
    traceback.print_exc()
    sheets = None

def call_grok_api(prompt, use_live_search=False, max_retries=3):
    """Unified Grok API call with optional Live Search."""
    for attempt in range(max_retries):
        try:
            data = {
                "messages": [
                    {"role": "system", "content": "You are a highly intelligent investment analyst with access to real-time data through provided tools. Use current data for all analysis and recommendations. Return only valid JSON responses in the exact format requested."},
                    {"role": "user", "content": prompt}
                ],
                "model": "grok-4-0709",
                "stream": False,
                "temperature": 0.05,
                "max_tokens": 6144
            }

            # Add Live Search parameters if requested
            if use_live_search:
                data["search_parameters"] = {
                    "mode": "on",
                    "return_citations": True,
                    "max_search_results": 20,
                    "sources": [{"type": "web"}, {"type": "news"}, {"type": "x"}]
                }
                timeout = 120 + (attempt * 30)  # Longer timeout for live search
                print(f"Calling Grok API with Live Search (attempt {attempt + 1}/{max_retries})")
            else:
                timeout = 90 + (attempt * 30)
                print(f"Calling Grok API (attempt {attempt + 1}/{max_retries})")
            
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROK_API_KEY}"},
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Log Live Search usage if enabled
            if use_live_search and 'usage' in result and 'num_sources_used' in result['usage']:
                num_sources = result['usage']['num_sources_used']
                cost = num_sources * 0.025
                print(f"Live Search used {num_sources} sources (cost: ${cost:.3f})")
                
                if 'citations' in result and result['citations']:
                    print(f"Citations: {result['citations'][:3]}...")
            
            return result['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.Timeout as e:
            print(f"Timeout error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
            
        except Exception as e:
            print(f"Error calling Grok API (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    
    return None

def get_accurate_stock_price(symbol, max_retries=2):
    """Get accurate real-time stock price using SerpApi Google Finance."""
    for attempt in range(max_retries):
        try:
            # Format symbol with exchange
            formatted_symbol = symbol.upper()
            if ':' not in formatted_symbol:
                exchange_map = {
                    'AAPL': 'NASDAQ', 'MSFT': 'NASDAQ', 'GOOGL': 'NASDAQ', 'AMZN': 'NASDAQ',
                    'TSLA': 'NASDAQ', 'META': 'NASDAQ', 'NVDA': 'NASDAQ', 'INTC': 'NASDAQ',
                    'AMD': 'NASDAQ', 'MU': 'NASDAQ', 'QCOM': 'NASDAQ', 'NFLX': 'NASDAQ',
                    'BA': 'NYSE', 'WMT': 'NYSE', 'JPM': 'NYSE', 'V': 'NYSE', 'JNJ': 'NYSE'
                }
                exchange = exchange_map.get(formatted_symbol, 'NASDAQ')
                formatted_symbol = f"{formatted_symbol}:{exchange}"

            response = requests.get(
                "https://serpapi.com/search.json",
                params={"engine": "google_finance", "q": formatted_symbol, "api_key": SERPAPI_KEY, "hl": "en"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                print(f"SerpApi error for {symbol}: {data['error']}")
                if attempt < max_retries - 1:
                    continue
                return f"SerpApi error for {symbol}: {data['error']}"
            
            if 'summary' in data:
                summary = data['summary']
                current_price = summary.get('extracted_price', 0)
                
                if current_price == 0 and attempt < max_retries - 1:
                    continue
                
                # Get market info
                market_info = ""
                if 'market' in summary and 'price_movement' in summary['market']:
                    movement = summary['market']['price_movement']
                    direction = movement.get('movement', '')
                    percentage = movement.get('percentage', 0)
                    value = movement.get('value', 0)
                    market_info = f" {direction} {percentage:.2f}% (${value:.2f})"
                
                return {
                    'symbol': symbol,
                    'price': current_price,
                    'currency': summary.get('currency', '$'),
                    'market_info': market_info,
                    'source': 'Google Finance via SerpApi',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                if attempt < max_retries - 1:
                    continue
                return f"No summary data found for {symbol}"
                
        except Exception as e:
            print(f"Error fetching stock price for {symbol} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                continue
            return f"Error fetching price for {symbol}: {str(e)}"
    
    return f"Failed to fetch price for {symbol}"

class ToolHandler:
    """Centralized tool handling to reduce code duplication."""
    
    @staticmethod
    def web_search(parameters):
        search_query = parameters.get('query', '')
        print(f"Performing web search using Grok Live Search for: {search_query}")
        
        search_prompt = f"""
        Search the web for current information about: {search_query}
        
        Please provide:
        1. Latest news and developments
        2. Current market data and trends
        3. Expert opinions and analyst ratings (especially Goldman Sachs and JPMorgan ratings)
        4. Recent price movements or performance data (if applicable)
        5. Key insights for investment decision-making
        
        PRIORITY SOURCES for analyst ratings:
        - Goldman Sachs buy/sell recommendations: https://www.marketbeat.com/ratings/by-issuer/goldman-sachs-group-stock-recommendations/
        - JPMorgan buy/sell recommendations: https://www.marketbeat.com/ratings/by-issuer/jpmorgan-chase-co-stock-recommendations/
        
        Focus on the most recent and relevant information available, particularly from these major investment banks.
        """
        
        result = call_grok_api(search_prompt, use_live_search=True)
        
        # Fallback if Live Search fails
        if not result:
            print("Live Search failed, using knowledge-based analysis")
            fallback_prompt = f"""
            Provide analysis on: {search_query}
            Based on your knowledge, discuss market trends, investment considerations, and strategic insights.
            Note: This analysis is based on training data, not live search results.
            """
            result = call_grok_api(fallback_prompt, use_live_search=False)
        
        return result
    
    @staticmethod
    def get_stock_price(parameters):
        symbol = parameters.get('symbol', '')
        return get_accurate_stock_price(symbol) if symbol else "Error: No symbol provided"
        
    @staticmethod
    def validate_stock_price(parameters):
        symbol = parameters.get('symbol', '')
        if not symbol:
            return "Error: No symbol provided"
            
        price_data = get_accurate_stock_price(symbol)
        if isinstance(price_data, dict):
            return f"VALIDATED PRICE for {symbol}: ${price_data['price']:.2f} {price_data['market_info']} (Source: {price_data['source']}, Updated: {price_data['timestamp']}, Confidence: HIGH)"
        return str(price_data)
    
    @staticmethod
    def get_multiple_stock_prices(parameters):
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
        
        return f"Current stock prices: {prices}"
    
    @staticmethod
    def get_stock_price_history(parameters):
        symbol = parameters.get('symbol', '')
        period = parameters.get('period', '1mo')
        
        search_prompt = f"""
        Search for historical price data and performance analysis for {symbol} stock over the {period} period.
        
        Please find and provide:
        1. Historical price trends and chart patterns
        2. Key price levels (highs, lows, support, resistance)
        3. Recent performance compared to previous periods
        4. Volume and trading activity trends
        5. Factors driving price movements
        6. Technical analysis and price momentum
        
        Focus on actual historical data and avoid speculation.
        """
        
        return call_grok_api(search_prompt, use_live_search=True)
    
    @staticmethod
    def analyze_portfolio_performance(parameters):
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
        
        symbols_str = ', '.join(symbols)
        current_date = datetime.now().strftime("%B %d, %Y")
        price_info = ', '.join([f"{sym}: ${price}" if isinstance(price, (int, float)) else f"{sym}: {price}" for sym, price in current_prices.items()])
        
        analysis_prompt = f"""
        Analyze these portfolio stocks using current market data as of {current_date}:
        
        STOCKS TO ANALYZE: {symbols_str}
        CURRENT VERIFIED PRICES: {price_info}
        
        Please search for and provide current analysis for each stock:
        1. Performance analysis and recent trends
        2. Latest analyst ratings and price targets (especially Goldman Sachs and JPMorgan)
        3. Recent news and market developments
        4. Investment recommendations (buy/sell/hold)
        5. Risk factors and opportunities
        
        PRIORITY: Check Goldman Sachs and JPMorgan ratings for these stocks:
        - Goldman Sachs: https://www.marketbeat.com/ratings/by-issuer/goldman-sachs-group-stock-recommendations/
        - JPMorgan: https://www.marketbeat.com/ratings/by-issuer/jpmorgan-chase-co-stock-recommendations/
        
        Use the verified prices provided above for price references.
        """
        
        analysis = call_grok_api(analysis_prompt, use_live_search=True)
        return f"ACCURATE PRICES: {price_info}\n\nLIVE MARKET ANALYSIS: {analysis}"
    
    @staticmethod
    def find_trending_stocks(parameters):
        sector = parameters.get('sector', 'technology')
        current_date = datetime.now().strftime("%B %d, %Y")
        
        search_prompt = f"""
        Search for trending and high-performing stocks in the {sector} sector as of {current_date}.
        
        Please find and provide:
        1. Top trending {sector} stocks with strong momentum
        2. Current stock prices and recent performance
        3. Reasons for their growth and market momentum
        4. Latest analyst ratings and price targets (especially from Goldman Sachs and JPMorgan)
        5. Investment opportunities and risk factors
        6. Buy/sell recommendations from major investment banks
        
        CRITICAL: Focus specifically on Goldman Sachs and JPMorgan recommendations:
        - Goldman Sachs ratings: https://www.marketbeat.com/ratings/by-issuer/goldman-sachs-group-stock-recommendations/
        - JPMorgan ratings: https://www.marketbeat.com/ratings/by-issuer/jpmorgan-chase-co-stock-recommendations/
        
        Look for stocks with recent BUY ratings from these institutions and focus on stocks with high growth potential or undervalued opportunities.
        """
        
        result = call_grok_api(search_prompt, use_live_search=True)
        
        # Fallback if Live Search fails
        if not result:
            fallback_prompt = f"""
            Based on your knowledge of the {sector} sector, identify stocks that typically show:
            1. Strong growth potential and market leadership
            2. Innovation and competitive advantages
            3. Historical performance patterns
            4. Investment characteristics for portfolio consideration
            
            Provide general guidance for {sector} sector investment strategy.
            """
            result = call_grok_api(fallback_prompt, use_live_search=False)
        
        return result

    @staticmethod
    def check_major_bank_ratings(parameters):
        """Specifically check Goldman Sachs and JPMorgan ratings for investment opportunities."""
        sector = parameters.get('sector', 'all sectors')
        current_date = datetime.now().strftime("%B %d, %Y")
        
        search_prompt = f"""
        Search specifically for Goldman Sachs and JPMorgan stock ratings and recommendations as of {current_date}.
        
        FOCUS ON:
        1. Recent BUY ratings from Goldman Sachs: https://www.marketbeat.com/ratings/by-issuer/goldman-sachs-group-stock-recommendations/
        2. Recent BUY ratings from JPMorgan: https://www.marketbeat.com/ratings/by-issuer/jpmorgan-chase-co-stock-recommendations/
        
        For {sector}, provide:
        - Stocks with recent BUY or STRONG BUY ratings
        - Price targets and rationale from these banks
        - Timing of rating changes or upgrades
        - Specific reasons for bullish outlook
        - Target sectors or themes these banks are highlighting
        
        Prioritize stocks that both banks rate as BUY or where one has recently upgraded.
        """
        
        return call_grok_api(search_prompt, use_live_search=True)

def build_react_prompt(objective, history):
    """Builds the prompt for the ReAct loop."""
    if len(history) > 4000:
        history = "..." + history[-4000:]
    
    return f"""
    You are an autonomous investment agent running an active portfolio with advanced analytical capabilities.
    
    OBJECTIVE: {objective}
    PREVIOUS ACTIONS: {history}
        
    ANALYSIS FRAMEWORK (Complete in 6 steps maximum):
    1. Get current portfolio prices (use get_multiple_stock_prices) - REQUIRED
    2. Research growth/undervalued opportunities (use web_search or find_trending_stocks)
    3. If considering existing portfolio stock, review transaction history
    4. Deep dive analysis on selected opportunities
    5. Make decisive investment decision (use final_decision) - REQUIRED
    6. Final validation if needed
    
    AVAILABLE TOOLS:
    - web_search(query): Search web for market information using Grok Live Search
    - get_current_stock_price(symbol): Get accurate real-time stock price
    - validate_stock_price(symbol): Cross-validate stock price
    - get_multiple_stock_prices(symbols): Get prices for multiple stocks
    - get_stock_price_history(symbol, period): Get historical price data
    - analyze_portfolio_performance(symbols): Analyze portfolio stocks
    - find_trending_stocks(sector): Discover trending stocks
    - check_major_bank_ratings(sector): Get Goldman Sachs & JPMorgan BUY ratings
    - get_stock_transaction_history(symbol): Get transaction history
    - sheets_get_cell_value/sheets_get_range_values/sheets_update_cell_value: Spreadsheet operations
    - final_decision(action, symbol, quantity, target_price, rationale): Make investment decision
    
    CRITICAL: You have full access to real-time market data. Never claim lack of current data access.
    
    Return valid JSON only:
    {{
        "thought": "your investment analysis",
        "action": {{
            "tool_name": "name_of_tool_to_use",
            "parameters": {{"parameter_name": "parameter_value"}}
        }}
    }}
    """

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
        initial_portfolio = sheets.get_portfolio_and_market_data()
        cash_on_hand_str = sheets.get_cell_value(CASH_ON_HAND_CELL)
        cash_on_hand = clean_and_convert_to_float(cash_on_hand_str)
        print(f"Initial cash on hand: {cash_on_hand}")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not read initial state from sheet. Error: {e}")
        return (f"Could not read initial state from sheet. Error: {e}", 500)

    objective = f"""
    You are running an active portfolio focused on identifying and investing in stocks with high growth potential and/or that are undervalued. 
    Available cash: ${cash_on_hand:,.2f}
    Current portfolio: {json.dumps(initial_portfolio)}
    
    FOCUS: Growth stocks (emerging sectors, strong earnings) and undervalued stocks (low P/E, P/B).
    
    CRITICAL: Prioritize Goldman Sachs and JPMorgan buy/sell ratings for new opportunities:
    - Goldman Sachs ratings: https://www.marketbeat.com/ratings/by-issuer/goldman-sachs-group-stock-recommendations/
    - JPMorgan ratings: https://www.marketbeat.com/ratings/by-issuer/jpmorgan-chase-co-stock-recommendations/
    
    Look for stocks with recent BUY ratings from these major investment banks.
    """
    
    history = f"Cycle started with ${cash_on_hand:,.2f} cash."
    consecutive_errors = 0
    
    # Tool mapping for cleaner code
    tool_handlers = {
        'web_search': ToolHandler.web_search,
        'get_current_stock_price': ToolHandler.get_stock_price,
        'validate_stock_price': ToolHandler.validate_stock_price,
        'get_multiple_stock_prices': ToolHandler.get_multiple_stock_prices,
        'get_stock_price_history': ToolHandler.get_stock_price_history,
        'analyze_portfolio_performance': ToolHandler.analyze_portfolio_performance,
        'find_trending_stocks': ToolHandler.find_trending_stocks,
        'check_major_bank_ratings': ToolHandler.check_major_bank_ratings,
        'get_stock_transaction_history': lambda p: sheets.get_stock_transaction_history(p.get('symbol', '')),
        'sheets_get_cell_value': lambda p: sheets.get_cell_value(**p),
        'sheets_get_range_values': lambda p: sheets.get_range_values(**p),
        'sheets_update_cell_value': lambda p: sheets.update_cell_value(**p)
    }
    
    for i in range(MAX_REASONING_STEPS):
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_FUNCTION_RUNTIME:
            print(f"TIMEOUT: Making emergency HOLD decision.")
            return ("Emergency HOLD decision due to timeout.", 200)
        
        print(f"\n--- Reasoning Step {i+1}/{MAX_REASONING_STEPS} ---")
        
        prompt = build_react_prompt(objective, history)
        
        if i >= 3:
            prompt += f"\n\nURGENT: This is step {i+1}/{MAX_REASONING_STEPS}. Focus on NEW data!"
        if i >= 4:
            prompt += f"\n\nCRITICAL: Prepare to make final_decision in next step!"
        
        try:
            response_text = call_grok_api(prompt, use_live_search=False)
            
            if not response_text:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    return ("Emergency HOLD decision due to API errors.", 200)
                continue

            print(f"Raw Grok response: '{response_text}'")
            
            try:
                decision_json = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    decision_json = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in Grok response")
            
            thought = decision_json.get('thought', 'No analysis provided')
            action_details = decision_json.get('action', {})
            tool_name = action_details.get('tool_name')
            parameters = action_details.get('parameters', {})
            
            print(f"Thought: {thought}")
            print(f"Action: {tool_name} with {parameters}")
            
            consecutive_errors = 0
            
        except Exception as e:
            consecutive_errors += 1
            print(f"Error processing Grok response: {e}")
            if consecutive_errors >= 3:
                return ("Emergency HOLD decision due to parsing errors.", 200)
            history += f"\nObservation: Grok response error. Trying different approach."
            continue

        if not tool_name:
            break
        
        # Force decision if we're running out of steps
        if i >= 5 and tool_name != 'final_decision':
            return ("HOLD decision made - analysis complete.", 200)
        
        if tool_name == 'final_decision':
            print("Agent has reached a final investment decision.")
            action = parameters.get('action', 'HOLD').upper()
            rationale = parameters.get('rationale', 'No rationale provided.')
            
            if action in ['BUY', 'SELL']:
                quantity = float(parameters.get('quantity', 0))
                price = float(parameters.get('target_price', 0))
                trade_value = quantity * price

                if action == 'BUY' and trade_value > cash_on_hand:
                    observation = f"INSUFFICIENT FUNDS. Cannot execute BUY order of ${trade_value:,.2f} with only ${cash_on_hand:,.2f} available."
                    history += f"\nThought: {thought}\nAction: {tool_name}\nObservation: {observation}"
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
        
        # Handle other tools using the unified handler
        if tool_name in tool_handlers:
            try:
                observation = tool_handlers[tool_name](parameters)
            except Exception as e:
                observation = f"Error executing {tool_name}: {str(e)}"
        else:
            observation = f"Unknown tool '{tool_name}'."
            
        print(f"Observation: {observation}")
        history += f"\nThought: {thought}\nAction: {tool_name}\nObservation: {str(observation)}"

    print("Max reasoning steps reached. Ending cycle.")
    return ("Cycle ended due to max steps.", 200)
