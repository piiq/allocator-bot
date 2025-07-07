# Allocator Bot

<p align="center">
  <img src="https://github.com/user-attachments/assets/2baee09d-0813-4e44-bc72-b7ef74a818b2" width="250px" />
</p>

A portfolio optimization copilot for OpenBB that uses PyPortfolioOpt to generate efficient frontier allocations.

## Features

<p align="center">
   <img width="1482" alt="image" src="https://github.com/user-attachments/assets/58cf19e9-4aa5-45fa-8b8b-8ed2fb911ffa" />
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

## Installation

### Install with pip from GitHub

```bash
pip install git+https://github.com/piiq/allocator-bot.git
```

### Install for development with uv

1. Clone the repository:

   ```bash
   git clone https://github.com/piiq/allocator-bot.git
   cd allocator-bot
   ```

2. Install dependencies using Poetry:

   ```bash
   uv sync
   ```

## Configuration

- Copy `.env.example` to `.env` and fill in the values.

## Usage

Start the server on localhost:

```bash
allocator-bot
```

### Adding to OpenBB Workspace

1. **Add as a Copilot**:

   - Click on the OpenBB Copilot dropdown
   - Click "Add Copilot"
   - Enter the server URL (e.g., `http://localhost:4322` for local deployment)
   - Add authorization header with the API key from `API_KEYS_FILE_PATH`
     - Header name: `Authorization`
     - Header value: `Bearer <API_KEY>`
   - Click "Create"

2. **Add as a Widget Source**:

   - Click "Add Data" on your dashboard
   - Go to "Custom Backends"
   - Select "Allocator Bot Backend"
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
