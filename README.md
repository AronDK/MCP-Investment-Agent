# Autonomous Investment Agent

An intelligent, AI-powered investment agent that autonomously manages a portfolio using real-time market data and advanced reasoning capabilities.

## 🚀 Features

- **Autonomous Decision Making**: Uses ReAct (Reasoning + Acting) framework for intelligent investment decisions
- **Real-time Market Data**: Integrates with SerpApi Google Finance for accurate stock prices and Grok Live Search for market analysis
- **Advanced AI**: Powered by Grok-4 with enhanced accuracy settings to prevent hallucinations
- **Accurate Price Data**: Uses Google Finance API via SerpApi for real-time, verified stock prices
- **Portfolio Management**: Automatically tracks positions, cash balance, and transaction history
- **Google Sheets Integration**: Seamlessly manages portfolio data in Google Sheets
- **Cloud-Native**: Deploys as a Google Cloud Function for scalable execution
- **Scheduled Execution**: Can be automated with Google Cloud Scheduler
- **Anti-Hallucination**: Enhanced prompts and validation to ensure accurate financial data

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Cloud Scheduler │───▶│ Cloud Function│───▶│  Investment     │
│  (Triggers)     │    │  (main.py)   │    │  Agent (Grok-4) │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                    ┌──────────────────┐    ┌─────────────────┐
                    │  Google Sheets   │    │ SerpApi Google  │
                    │  (Portfolio Data)│    │ Finance + Grok  │
                    └──────────────────┘    │ Live Search     │
                                           └─────────────────┘
```

## 🧠 How It Works

1. **Data Collection**: Reads current portfolio positions and cash balance from Google Sheets
2. **Price Validation**: Gets accurate, real-time stock prices from Google Finance via SerpApi
3. **Market Analysis**: Searches for current market conditions using Grok Live Search
4. **AI Reasoning**: Grok-4 analyzes data using ReAct framework with enhanced accuracy settings
5. **Decision Making**: Makes BUY/SELL/HOLD decisions with validated pricing data
6. **Action Execution**: Automatically executes investment decisions
7. **Transaction Logging**: Records all transactions and updates portfolio balance

## 📊 Investment Logic

The agent follows a structured decision-making process with enhanced accuracy:

- **Portfolio Assessment**: Analyzes current holdings, performance, and available cash
- **Price Verification**: Uses Google Finance API via SerpApi for accurate, real-time stock prices
- **Market Research**: Gathers real-time market data and news via Grok Live Search
- **Risk Evaluation**: Considers market conditions and portfolio diversification
- **Decision Making**: Makes BUY/SELL/HOLD decisions based on verified data within 7 reasoning steps
- **Execution**: Updates portfolio and logs all transactions with validated pricing

## 🛠️ Technology Stack

- **AI Model**: Grok-4 (xAI) for investment analysis with enhanced accuracy settings
- **Price Data**: SerpApi Google Finance API for real-time, verified stock prices
- **Web Search**: Grok Live Search for real-time market data and news
- **Data Storage**: Google Sheets for portfolio management
- **Cloud Platform**: Google Cloud Functions
- **Scheduling**: Google Cloud Scheduler
- **Language**: Python 3.11

## 📋 Prerequisites

- Google Cloud Platform account
- xAI API key (for Grok-4 access)
- SerpApi key (for Google Finance data)
- Google Sheets API credentials
- Python 3.11+

## 🚀 Deployment

### 1. Set up Google Cloud Function

```bash
gcloud functions deploy Investment-agent \
  --gen2 \
  --region=us-central1 \
  --runtime=python311 \
  --source=./investment-agent \
  --entry-point=run_investment_cycle \
  --trigger-http \
  --allow-unauthenticated \
  --service-account=your-service-account@your-project.iam.gserviceaccount.com \
  --timeout=300s \
  --set-env-vars="GCP_PROJECT_ID=your-project-id,GOOGLE_SHEET_ID=your-sheet-id,GROK_API_KEY=your-grok-key,SERPAPI_KEY=your-serpapi-key"
```

### 2. Set up Cloud Scheduler (Optional)

```bash
gcloud scheduler jobs create http investment-agent-scheduler \
  --schedule="0,30 13-20 * * 1-5" \
  --uri=https://your-region-your-project.cloudfunctions.net/Investment-agent \
  --http-method=POST \
  --time-zone="America/New_York"
```

## 📁 Project Structure

```
MCP-Investment-Agent/
├── investment-agent/          # Core investment agent code
│   ├── main.py               # Main Cloud Function entry point
│   ├── sheets_tool_advanced.py  # Google Sheets integration
│   └── moomoo_tool.py        # MooMoo trading API wrapper
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── .gitignore              # Git ignore configuration
```

## 🔧 Configuration

## 🔄 Recent Improvements (July 2025)

### Hallucination Prevention & Accuracy Enhancement
- **Doubled Token Limit**: Increased from 3,072 to 6,144 tokens for more detailed analysis
- **Reduced Temperature**: Lowered from 0.1 to 0.05 to minimize AI hallucinations
- **Enhanced Prompts**: Added explicit anti-hallucination warnings in system prompts
- **Price Validation**: Integrated SerpApi Google Finance for verified, real-time stock prices
- **Historical Data Accuracy**: Enhanced prompts to prevent fictional price generation

### Decision-Making Improvements
- **Extended Reasoning Steps**: Increased from 5 to 7 steps to reduce forced HOLD decisions
- **Progressive Decision Forcing**: Warns agent at step 4+ to encourage timely decisions
- **Enhanced Loop Detection**: Prevents repetitive analysis cycles
- **Step-Based Urgency**: Adds urgency prompts as steps progress to ensure completion

### Technical Enhancements
- **Dual Data Sources**: SerpApi for prices, Grok Live Search for market analysis
- **Validation Layer**: Cross-validates all price data before trading decisions
- **Error Handling**: Improved error recovery and fallback mechanisms
- **Performance Monitoring**: Better logging for debugging and optimization

## 🔧 Configuration

### Environment Variables

- `GCP_PROJECT_ID`: Your Google Cloud Project ID
- `GOOGLE_SHEET_ID`: ID of your Google Sheets portfolio tracker
- `GROK_API_KEY`: Your xAI API key for Grok-4 access
- `SERPAPI_KEY`: Your SerpApi key for Google Finance data access

### Google Sheets Structure

The agent expects a Google Sheet with these worksheets:
- `Portfolio Summary`: Contains cash balance and summary data
- `Summary_OSV`: Detailed portfolio positions
- `Transactions_OSV`: Transaction history
- `Stock_Ref`: Reference data for stocks
- `Ref`: Additional reference information

## 🔒 Security Considerations

- API keys are stored as environment variables (never in code)
- Uses Google Cloud IAM for secure authentication
- Service account with minimal required permissions
- HTTPS-only communication with all APIs

## 📈 Performance

- **Execution Time**: Typically completes analysis in 30-90 seconds (extended for accuracy)
- **Decision Quality**: Enhanced accuracy with verified price data and anti-hallucination measures
- **Success Rate**: Reduced forced HOLD decisions through improved reasoning framework
- **Rate Limits**: Respects API rate limits for all services (SerpApi, Grok, Google Sheets)
- **Scalability**: Serverless architecture scales automatically
- **Cost Efficient**: Pay-per-execution model with optimized API usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. It is not financial advice. Always consult with qualified financial professionals before making investment decisions. Use at your own risk.

## 🎯 Recent Accomplishments & Future Enhancements

### ✅ Recently Completed
- [x] **Price Accuracy Fix**: Integrated SerpApi Google Finance for verified stock prices
- [x] **Hallucination Prevention**: Enhanced prompts and validation to ensure accurate data
- [x] **Decision Optimization**: Extended reasoning steps to reduce forced HOLD decisions
- [x] **Performance Enhancement**: Doubled token limit for more detailed analysis

### 🔮 Future Enhancements
- [ ] Multi-asset class support (bonds, ETFs, crypto)
- [ ] Advanced portfolio optimization algorithms
- [ ] Risk management and stop-loss features
- [ ] Performance analytics and reporting dashboard
- [ ] Integration with brokerage APIs for live trading
- [ ] Machine learning for pattern recognition
- [ ] Backtesting capabilities with historical data
- [ ] Real-time portfolio rebalancing
- [ ] Sentiment analysis integration

## 📞 Support

For questions, issues, or contributions, please open an issue on GitHub.

---

*Built with ❤️ for the future of autonomous investing*
