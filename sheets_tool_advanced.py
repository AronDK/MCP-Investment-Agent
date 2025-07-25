import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

class SheetsTool:
    """
    An advanced wrapper for gspread, providing high-level and granular functions
    for an AI agent to perform complex analysis and modeling.
    This version is tailored for the OSV spreadsheet template.
    """

    def __init__(self, credentials_json, sheet_id):
        """Initializes the connection to Google Sheets."""
        try:
            print("Authenticating with Google Sheets...")
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(credentials_json, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(sheet_id)
            print("Google Sheets authentication successful.")
        except Exception as e:
            print(f"Failed to initialize SheetsTool: {e}")
            raise

    # --- NEW DEBUGGING FUNCTION ---
    def list_all_worksheets(self):
        """Lists the titles of all worksheets in the spreadsheet."""
        try:
            print("Attempting to list all worksheets...")
            worksheets = self.spreadsheet.worksheets()
            return [w.title for w in worksheets]
        except Exception as e:
            print(f"Error listing worksheets: {e}")
            raise

    # --- HIGH-LEVEL FUNCTIONS ---

    def get_portfolio_and_market_data(self):
        """Retrieves and formats the current portfolio from the 'Summary_OSV' tab."""
        try:
            print("Fetching portfolio and market data from 'Summary_OSV' sheet...")
            portfolio_sheet = self.spreadsheet.worksheet("Summary_OSV")
            records = portfolio_sheet.get_all_records()
            
            print(f"DEBUG: Found {len(records)} total records")
            if records:
                print(f"DEBUG: First record keys: {list(records[0].keys())}")
                print(f"DEBUG: First few records: {records[:3]}")
            
            # Filter for records that have actual stock data (not empty rows)
            valid_records = []
            for record in records:
                # Based on your screenshot, look for the 'Stock Ticker' column
                ticker = record.get('Stock Ticker', '').strip()
                investment_category = record.get('Investment Category', '').strip()
                
                # A valid record should have a stock ticker and not be empty/placeholder rows
                if (ticker and ticker not in ['', '-', 'No Data', '~'] and 
                    investment_category and investment_category not in ['', '-', 'No Data', '~']):
                    valid_records.append(record)
            
            print(f"Found {len(valid_records)} valid records in portfolio.")
            
            formatted_portfolio = []
            for record in valid_records:
                formatted_portfolio.append({
                    "Symbol": record.get("Stock Ticker"),
                    "Investment_Category": record.get("Investment Category"),
                    "Shares": record.get("Shares"),
                    "Cost_Per_Share": record.get("Cost (Per Share)"),
                    "Last_Price": record.get("Last Price"),
                    "Market_Value": record.get("Mkt Value"),
                    "Unrealized_PL": record.get("Unrealized Gain/Loss"),
                    "Unrealized_Percent": record.get("Unrealized Gain/Loss %")
                })
            return formatted_portfolio
        except Exception as e:
            print(f"Error fetching portfolio: {e}")
            raise

    def log_transaction(self, symbol, action, quantity, price, rationale):
        """Appends a new record to the 'Transactions_OSV' tab."""
        try:
            print(f"Logging transaction: {action} {quantity} of {symbol}...")
            transactions_sheet = self.spreadsheet.worksheet("Transactions_OSV")
            
            date = datetime.now(pytz.utc).strftime('%m/%d/%Y')
            
            row_to_append = [
                date,
                symbol,
                action.upper(),
                quantity,
                price,
                0, # Fees
                f"=D{transactions_sheet.row_count + 1}*E{transactions_sheet.row_count + 1}", # Total
                rationale # Rationale goes into the 'Notes' column
            ]
            transactions_sheet.append_row(row_to_append, value_input_option='USER_ENTERED')
            print("Transaction entry added successfully.")
        except Exception as e:
            print(f"Error logging transaction: {e}")
            raise

    # --- GRANULAR MODELLING FUNCTIONS ---

    def get_cell_value(self, cell_notation):
        """
        Reads and returns the value of a single cell.
        :param cell_notation: Standard A1 notation (e.g., 'Portfolio Summary!B3').
        """
        try:
            print(f"Getting cell value from: {cell_notation}")
            sheet_name, cell_address = cell_notation.split('!')
            worksheet = self.spreadsheet.worksheet(sheet_name)
            result = worksheet.get(cell_address)
            return result[0][0] if result and result[0] else None
        except Exception as e:
            print(f"Error in get_cell_value for {cell_notation}: {e}")
            raise

    def update_cell_value(self, cell_notation, value):
        """
        Updates a single cell with a given value. Can write values or formulas.
        :param cell_notation: Standard A1 notation (e.g., 'Portfolio Summary!B3').
        :param value: The value or formula to write (e.g., 123 or '=SUM(A1:B1)').
        """
        try:
            print(f"Updating cell {cell_notation} with value: {value}")
            sheet_name, cell_address = cell_notation.split('!')
            worksheet = self.spreadsheet.worksheet(sheet_name)
            worksheet.update(cell_address, [[value]], value_input_option='USER_ENTERED')
            return f"Successfully updated {cell_notation}."
        except Exception as e:
            print(f"Error in update_cell_value for {cell_notation}: {e}")
            raise

    def create_worksheet(self, title):
        """Creates a new worksheet (tab) in the spreadsheet."""
        try:
            print(f"Creating new worksheet with title: {title}")
            self.spreadsheet.add_worksheet(title=title, rows="100", cols="20")
            return f"Worksheet '{title}' created successfully."
        except gspread.exceptions.APIError as e:
            if 'already exists' in str(e):
                return f"Worksheet '{title}' already exists."
            raise
        except Exception as e:
            print(f"Error creating worksheet '{title}': {e}")
            raise
            
    def delete_worksheet(self, title):
        """Deletes a worksheet by its title."""
        try:
            print(f"Deleting worksheet: {title}")
            worksheet_to_delete = self.spreadsheet.worksheet(title)
            self.spreadsheet.del_worksheet(worksheet_to_delete)
            return f"Worksheet '{title}' deleted successfully."
        except gspread.exceptions.WorksheetNotFound:
             return f"Worksheet '{title}' not found, cannot delete."
        except Exception as e:
            print(f"Error deleting worksheet '{title}': {e}")
            raise
