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

    def list_all_worksheets(self):
        """Lists the titles of all worksheets in the spreadsheet."""
        try:
            print("Attempting to list all worksheets...")
            worksheets = self.spreadsheet.worksheets()
            return [w.title for w in worksheets]
        except Exception as e:
            print(f"Error listing worksheets: {e}")
            raise

    def get_portfolio_and_market_data(self):
        """Retrieves and formats the current portfolio from the 'Summary_OSV' tab."""
        try:
            print("Fetching portfolio and market data from 'Summary_OSV' sheet...")
            portfolio_sheet = self.spreadsheet.worksheet("Summary_OSV")
            records = portfolio_sheet.get_all_records()
            
            valid_records = [r for r in records if r.get('Stock Ticker')]
            print(f"Found {len(valid_records)} valid records in portfolio.")
            
            formatted_portfolio = []
            for record in valid_records:
                formatted_portfolio.append({
                    "Symbol": record.get("Stock Ticker"),
                    "Quantity": record.get("Shares"),
                    "Average Cost": record.get("Cost Per Share"),
                    "Current Price": record.get("Last Price"),
                    "Market Value": record.get("Mkt Value"),
                    "Unrealized P/L": record.get("Unrealized Gain/Loss")                })
            return formatted_portfolio
        except Exception as e:
            print(f"Error fetching portfolio: {e}")
            raise

    def log_transaction(self, symbol, action, quantity, price, rationale):
        """Appends a new record to the 'Transactions_OSV' tab with proper formulas."""
        try:
            print(f"Logging transaction: {action} {quantity} of {symbol}...")
            transactions_sheet = self.spreadsheet.worksheet("Transactions_OSV")
            
            # Get the next row number (current row count + 1)
            next_row = transactions_sheet.row_count + 1
            
            date = datetime.now(pytz.utc).strftime('%m/%d/%Y')  # Match format from screenshot
            
            # Initialize a row with 17 empty values (for columns A through Q)
            row_to_append = [''] * 17
            
            # Populate the data columns
            row_to_append[0] = date                   # Column A: Date
            row_to_append[1] = action.upper()        # Column B: Type (BUY/SELL)
            row_to_append[2] = symbol                # Column C: Stock
            row_to_append[3] = quantity              # Column D: Transacted Units
            row_to_append[4] = price                 # Column E: Transacted Price (per unit)
            row_to_append[5] = 3.0                   # Column F: Fees ($3 per transaction)
            row_to_append[6] = ""                    # Column G: Stock Split Ratio (empty for regular trades)
            
            # Column H: Previous Units formula
            row_to_append[7] = f'=if($C{next_row}="","",iferror(if(row()<>2,INDEX(arrayformula(filter($I$1:$I${next_row-1},$C$1:$C${next_row-1}<>"",row($C$1:$C${next_row-1})=max(if($C$1:$C${next_row-1}=C{next_row},row($C$1:$C${next_row-1}),0)))),1),0),0))'
            
            # Column I: Cumulative Units formula
            row_to_append[8] = f'=if(C{next_row}="","",if(B{next_row}="Buy",H{next_row}+D{next_row},if(B{next_row}="Sell",H{next_row}-D{next_row},if(or(B{next_row}="Div",B{next_row}="Fee"),H{next_row},if(B{next_row}="Split",H{next_row}*G{next_row},0)))))'
            
            # Column J: Transacted Value formula
            row_to_append[9] = f'=if(C{next_row}="","",if(B{next_row}="Buy",E{next_row}*D{next_row}+F{next_row},if(B{next_row}="Sell",E{next_row}*D{next_row}-F{next_row},E{next_row}*D{next_row}-F{next_row})))'
            
            # Column K: Previous Cost formula
            row_to_append[10] = f'=if(C{next_row}="","",iferror(if(row()<>2,INDEX(arrayformula(filter($N$1:$N${next_row-1},$C$1:$C${next_row-1}<>"",row($C$1:$C${next_row-1})=max(if($C$1:$C${next_row-1}=C{next_row},row($C$1:$C${next_row-1}),0)))),1),0),0))'
            
            # Column L: Cost of Transaction formula
            row_to_append[11] = f'=if(C{next_row}="","",if(B{next_row}="Sell",if(H{next_row}=0,0,D{next_row}/H{next_row}*K{next_row}),"-"))'
            
            # Column M: Avg Stock Price formula
            row_to_append[12] = f'=if(C{next_row}="","",if(B{next_row}="Sell",if(H{next_row}=0,0,K{next_row}/H{next_row}),"-"))'
            
            # Column N: Cumulative Cost formula
            row_to_append[13] = f'=if(C{next_row}="","",if(B{next_row}="Buy",K{next_row}+J{next_row},if(or(B{next_row}="Div",B{next_row}="Fee"),K{next_row},if(B{next_row}="Sell",if(K{next_row}<=0,"Error.No Previous units.",K{next_row}-L{next_row}),if(B{next_row}="Split",K{next_row},"Error")))))'
            
            # Column O: Gains/Losses from Sale formula
            row_to_append[14] = f'=if(C{next_row}="","",if(B{next_row}="Sell",J{next_row}-L{next_row},if(or(B{next_row}="Div",B{next_row}="Fee"),J{next_row},0)))'
            
            # Column P: Realised Gains/Losses % formula
            row_to_append[15] = f'=if(C{next_row}="","",if(B{next_row}="Sell",(J{next_row}-L{next_row})/L{next_row},""))'
            
            # Column Q: Reason
            row_to_append[16] = rationale
            
            transactions_sheet.append_row(row_to_append, value_input_option='USER_ENTERED')
            print("Transaction entry added successfully with all formulas.")
        except Exception as e:
            print(f"Error logging transaction: {e}")
            raise

    # --- GRANULAR MODELLING FUNCTIONS ---

    def get_cell_value(self, cell_notation):
        """Reads and returns the value of a single cell."""
        try:
            print(f"Getting cell value from: {cell_notation}")
            sheet_name, cell_address = cell_notation.split('!')
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet.acell(cell_address).value
        except Exception as e:
            print(f"Error in get_cell_value for {cell_notation}: {e}")
            raise

    def get_range_values(self, range_notation):
        """Reads and returns the values of a range of cells."""
        try:
            print(f"Getting range values from: {range_notation}")
            sheet_name, cell_range = range_notation.split('!')
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet.get(cell_range)
        except Exception as e:
            print(f"Error in get_range_values for {range_notation}: {e}")
            raise

    def update_cell_value(self, cell_notation, value):
        """Updates a single cell with a given value."""
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
