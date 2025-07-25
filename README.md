# Autonomous Investment Agent

An intelligent, AI-powered investment agent that autonomously manages a portfolio using real-time market data and advanced reasoning capabilities.

## 🚀 Features

- **Autonomous Decision Making**: Uses ReAct (Reasoning + Acting) framework for intelligent investment decisions
- **Real-time Market Data**: Integrates with Grok Live Search for current market information and news
- **Advanced AI**: Powered by Grok-4 for sophisticated financial analysis
- **Portfolio Management**: Automatically tracks positions, cash balance, and transaction history
- **Google Sheets Integration**: Seamlessly manages portfolio data in Google Sheets
- **Cloud-Native**: Deploys as a Google Cloud Function for scalable execution
- **Scheduled Execution**: Can be automated with Google Cloud Scheduler

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Cloud Scheduler │───▶│ Cloud Function│───▶│  Investment     │
│  (Triggers)     │    │  (main.py)   │    │  Agent (Grok-4) │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                    ┌──────────────────┐    ┌─────────────────┐
                    │  Google Sheets   │    │ Grok Live Search│
                    │  (Portfolio Data)│    │  (Market Data)  │
                    └──────────────────┘    └─────────────────┘
```

## 🧠 How It Works

1. **Data Collection**: Reads current portfolio positions and cash balance from Google Sheets
2. **Market Analysis**: Searches for current market conditions using Grok Live Search
3. **AI Reasoning**: Grok-4 analyzes data using ReAct framework to make investment decisions
4. **Action Execution**: Automatically executes BUY/SELL/HOLD decisions
5. **Transaction Logging**: Records all transactions and updates portfolio balance

## 📊 Investment Logic

The agent follows a structured decision-making process:

- **Portfolio Assessment**: Analyzes current holdings, performance, and available cash
- **Market Research**: Gathers real-time market data and news
- **Risk Evaluation**: Considers market conditions and portfolio diversification
- **Decision Making**: Makes BUY/SELL/HOLD decisions based on comprehensive analysis
- **Execution**: Updates portfolio and logs all transactions

## 🛠️ Technology Stack

- **AI Model**: Grok-4 (xAI) for investment analysis
- **Web Search**: Grok Live Search for real-time market data
- **Data Storage**: Google Sheets for portfolio management
- **Cloud Platform**: Google Cloud Functions
- **Scheduling**: Google Cloud Scheduler
- **Language**: Python 3.11

## 📋 Prerequisites

- Google Cloud Platform account
- xAI API key (for Grok-4 access)
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
  --set-env-vars="GCP_PROJECT_ID=your-project-id,GOOGLE_SHEET_ID=your-sheet-id,GROK_API_KEY=your-grok-key"
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

### Environment Variables

- `GCP_PROJECT_ID`: Your Google Cloud Project ID
- `GOOGLE_SHEET_ID`: ID of your Google Sheets portfolio tracker
- `GROK_API_KEY`: Your xAI API key for Grok-4 access

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

- **Execution Time**: Typically completes analysis in 30-60 seconds
- **Rate Limits**: Respects API rate limits for all services
- **Scalability**: Serverless architecture scales automatically
- **Cost Efficient**: Pay-per-execution model

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

## 🎯 Future Enhancements

- [ ] Multi-asset class support (bonds, ETFs, crypto)
- [ ] Advanced portfolio optimization algorithms
- [ ] Risk management and stop-loss features
- [ ] Performance analytics and reporting
- [ ] Integration with brokerage APIs for live trading
- [ ] Machine learning for pattern recognition
- [ ] Backtesting capabilities

## 📞 Support

For questions, issues, or contributions, please open an issue on GitHub.

---

*Built with ❤️ for the future of autonomous investing*
