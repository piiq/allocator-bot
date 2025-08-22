# Allocator Bot

<p align="center">
  <img width="250px" alt="allocator-bot" src="https://github.com/user-attachments/assets/2baee09d-0813-4e44-bc72-b7ef74a818b2" />
</p>

A portfolio optimization copilot for OpenBB that uses PyPortfolioOpt to generate efficient frontier allocations.

## Features

<p align="center">
   <img width="1482" alt="dashboard" src="https://github.com/user-attachments/assets/b380c409-6569-47a1-ba73-cfd00d890e6f" />
</p>

- **OpenBB Integration**:
  - Plugs into OpenBB Workspace's copilot and widget interfaces
  - Fetches price data from FMP via OpenBB Platform's python library
  - Real-time feedback through server-sent events
  - Interactive portfolio visualization widgets
- **Portfolio Optimization Models**:
  - Maximum Sharpe Ratio optimization
  - Minimum Volatility optimization
  - Efficient Risk (target volatility)
  - Efficient Return (target return)

## Requirements and Tech Stack

- Python 3.10 to 3.12
- FMP API access (via [OpenBB Platform](https://docs.openbb.co/platform))
- OpenAI API access
- Dependencies listed in `pyproject.toml`
- **Tech Stack**:

  - FastAPI with Starlette SSE for real-time updates
  - OpenBB Platform Python library for data access
  - PyPortfolioOpt for optimization algorithms
  - Pydantic for data validation
  - Magentic for LLM interactions

## Installation & Usage

### Docker (Recommended)

The easiest way to run the Allocator Bot is using Docker:

```bash
docker run --rm -it --name allocator-bot \
  -e AGENT_HOST_URL=http://localhost:4322 \
  -e APP_API_KEY=your_api_key \
  -e OPENROUTER_API_KEY=your_openrouter_key \
  -e FMP_API_KEY=your_fmp_key \
  -e DATA_FOLDER_PATH=data \
  -e S3_ENABLED=false \
  -p 4299:4299 \
  ghcr.io/piiq/allocator-bot:latest
```

**Required Environment Variables:**

- `AGENT_HOST_URL`: The host URL where the app is running (e.g., `http://localhost:4322`)
- `APP_API_KEY`: Your API key to access the bot
- `OPENROUTER_API_KEY`: Your OpenRouter API key for LLM access
- `FMP_API_KEY`: Your Financial Modeling Prep API key for market data

**Storage Configuration (choose one):**

When S3 is disabled (default), local storage is required:
- `DATA_FOLDER_PATH`: Local storage path for allocation data (required when `S3_ENABLED=false`)

When S3 is enabled:
- `S3_ENABLED`: Set to `true` to enable S3 storage
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`: S3 configuration (all required when S3 enabled)

### Alternative Installation Methods

#### Install with pip from GitHub

```bash
pip install git+https://github.com/piiq/allocator-bot.git
```

#### Development Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/piiq/allocator-bot.git
   cd allocator-bot
   ```

2. Install dependencies:

   ```bash
   uv sync --extra dev
   ```

3. Copy `.env.example` to `.env` and fill in the values
4. Start the server:

   ```bash
   allocator-bot
   ```

### Adding to OpenBB Workspace

1. **Add as a Copilot**:

   - Click on the OpenBB Copilot dropdown
   - Click "Add Copilot"
   - Enter the server URL (e.g., `http://localhost:4299` for Docker deployment)
   - Add authorization header with your API key
     - Header name: `Authorization`
     - Header value: `Bearer <your_api_key>` (same as `APP_API_KEY` environment variable)
   - Click "Create"

2. **Add as a an App and Widget Source**:

   - Click "Apps" on your dashboard
   - Click "Connect Backend" on the Apps page
   - Enter the same URL and API key used for the copilot
   - Click "Add"

### Using the Copilot

- The copilot accepts natural language requests for portfolio optimization
- You can specify:
  - List of tickers
  - Total investment amount
  - Risk-free rate
  - Target volatility
  - Holding period
- The copilot will provide:
  - Optimized allocations with different risk models
  - Interactive tables and visualizations
  - Real-time feedback and error handling
  - Allocation IDs for widget integration

### Using the Widgets

- Load allocations using their IDs
- Filter by specific risk models
- Visualize allocations using various chart types (e.g., donut charts)
- Compare different optimization strategies

## Contributing

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Submit a pull request with a description of your changes

## License

This project is licensed under MIT.
PyPortfolioOpt is licensed under MIT.
OpenBB is licensed under AGPL.
