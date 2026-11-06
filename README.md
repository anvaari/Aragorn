# 🎵 Aragorn - Independent Music Event Collector

Aragorn is an intelligent music event collection and distribution system that automatically extracts music event information from Instagram posts and distributes them through Telegram channels. Built with modern Python technologies, it leverages AI to process Persian text and create structured event data.

## 🎯 Purpose

Aragorn serves as a centralized hub for independent music events, particularly those shared on Instagram. It bridges the gap between social media event announcements and organized event distribution by:

- **Intelligent Text Processing**: Uses OpenAI to extract structured event data from Persian text
- **Multi-Platform Distribution**: Shares formatted events via Telegram with rich media
- **Calendar Integration**: Provides Google Calendar links for easy event scheduling
- **Data Persistence**: Maintains a local database of all processed events

## ✨ Key Functionalities

### 🔍 Instagram Integration

- Receive Instagram post link through API
- Extracts captions and media from posts, reels, and carousels
- Handles proxy configurations for restricted environments

### 🤖 AI-Powered Text Processing

- Utilizes OpenAI GPT models to parse Persian event descriptions
- Extracts structured data: title, date, time, location, performers, ticket info
- Handles Shamsi (Persian) calendar conversion
- Provides intelligent defaults for missing information

### 📱 Telegram Distribution

- Sends formatted event announcements to configured channels
- Supports both text and image messages
- Uses Markdown formatting for enhanced readability
- Includes event media from original Instagram posts

### 📅 Calendar Integration

- Generates Google Calendar links for each event
- Converts Persian dates to Gregorian calendar
- Sets appropriate timezones and event duration

### 🗄️ Data Management

- SQLite database for event storage and tracking
- CRUD operations for event management
- Prevents duplicate event processing

### 🌐 REST API

- FastAPI-based REST endpoints
- Bearer token authentication
- Manual event submission capability
- Instagram URL processing endpoint

## 🏗️ System Architecture

### Core Modules

#### 📊 **API Layer** (`app/api/`)

- **`v1/endpoints/events.py`**: REST endpoints for event management
- **`v1/router.py`**: API routing configuration
- **Authentication**: Bearer token-based security

#### 🎭 **Instagram Scraper** (`app/ig_scrapper/`)

- **`extractor.py`**: Instagram content extraction logic
- **Features**: Post scraping, media extraction, proxy support
- **Authentication**: Cookie-based Instagram login

#### 🧠 **AI Processing** (`app/open_ai/`)

- **`text_events.py`**: Event data extraction from text
- **`gpt.py`**: OpenAI client configuration
- **Capabilities**: Persian text processing, structured data extraction

#### 💬 **Telegram Integration** (`app/telegram/`)

- **`bot.py`**: Telegram API communication
- **`event_formatter.py`**: Message formatting and styling
- **Features**: Text/image messages, Markdown support

#### 🎪 **Event Management** (`app/services/`)

- **`event_service.py`**: Business logic orchestration
- **Workflow**: Instagram → AI Processing → Database → Telegram

#### 🗃️ **Data Layer** (`app/db/`)

- **`database.py`**: Database initialization and connections
- **`crud_event.py`**: Event CRUD operations
- **Storage**: SQLite database

#### 🛠️ **Utilities** (`app/utils/`)

- **`google_calendar.py`**: Calendar link generation
- **Date/time conversion utilities

#### ⚙️ **Configuration** (`app/core/`)

- **`config.py`**: Environment-based settings management

#### 📝 **Logging** (`app/log/`)

- **`logger.py`**: Application logging setup
- **Features**: Configurable log levels, structured logging

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Instagram account (for scraping)
- OpenAI API key
- Telegram bot token
- Telegram channel/chat ID

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/anvaari/Aragorn.git
   cd Aragorn
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**

   Create a `.env` file in the root directory:

   ```env
   # Telegram Configuration
   telegram_bot_tk=your_telegram_bot_token
   telegram_chat=your_telegram_chat_id
   
   # OpenAI Configuration
   openai_api_k=your_openai_api_key
   openai_model=gpt-3.5-turbo
   
   # Instagram Configuration
   instagram_login_cookie={"csrftoken":"your_csrf_token","sessionid":"ypur_session_id","ds_user_id":"your_ds_user_id","mid":"your_mid","ig_did":"your_ig_did"}
   
   # API Security
   aragorn_tk=your_api_bearer_token
   
   # Proxy Settings (optional)
   tg_gpt_ig_proxy=http://proxy:port
   
   # Logging
   log_level=INFO
   database_file_path=./events.db
   ```

   Get Instagram configuration using [this guide](https://github.com/instaloader/instaloader/issues/2487#issue-2807621924)

4. **Run the application**

   ```bash
   cd app
   fastapi run app/main.py
   ```

### API Usage

#### Process Instagram Event

```bash
curl -X POST "http://localhost:8000/api/v1/ig_event" \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"ig_link": "https://instagram.com/p/POST_ID"}'
```

#### Submit Manual Event

```bash
curl -X POST "http://localhost:8000/api/v1/manual_event" \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Jazz Night",
    "date": "1403-01-15",
    "time": "20:00",
    "location": "Tehran Music Hall",
    "performers": "Jomee Trio",
    "ticket_info": "Call: 021-12345678",
    "instagram_link": "https://instagram.com/p/example",
    "description": "An evening of contemporary jazz"
  }'
```

## 🎨 Artist Donations Mini App

A Telegram Mini App (opened from the bot's main menu) where independent artists claim a profile and fans support them with real money:

| Rail | How it pays | Where the money goes |
|---|---|---|
| ⭐️ **Telegram Stars** | Native Stars invoice inside Telegram | The bot's Stars balance; the admin settles with the artist (Telegram has no Stars payout to users) |
| 💎 **GRAM** (TON, formerly Toncoin) | TON Connect (Telegram Wallet, Tonkeeper, …) | Straight to the artist's TON wallet; verified on-chain by its comment |
| 💵 **USDC on Base** | Any wallet or exchange; donor pastes the tx hash | Straight to the artist's Base wallet; verified from the tx receipt |

Artist profiles stay hidden until the admin approves them from a bot DM, and every edit sends the profile back for review.

### Setup

1. Serve the app over **HTTPS** (Telegram requires it). For local testing, a tunnel such as `cloudflared tunnel --url http://localhost:8000` works.
2. Set in `.env`:

   ```env
   miniapp_url=https://your-domain/miniapp/
   bot_admin_chat_id=your_numeric_telegram_id
   ```

3. In [@BotFather](https://t.me/BotFather): *Bot Settings → Configure Mini App → Enable Mini App* with the same `miniapp_url`. This makes the share links artists receive on approval (`https://t.me/<bot>?startapp=artist_<id>`) open the app directly.

Run the self-checks with `python tests/test_donations.py`.

> ⚠️ Before going live, review Telegram's [Stars payment rules](https://core.telegram.org/bots/payments-stars) (e.g. a `/terms` command) and whether collecting Stars for third parties fits your use.

## 🛠️ Development

### Project Structure

```text
app/
├── api/v1/              # REST API endpoints
├── core/                # Configuration management
├── db/                  # Database operations
├── ig_scrapper/         # Instagram scraping logic
├── log/                 # Logging utilities
├── models/              # Data models
├── open_ai/             # AI text processing
├── services/            # Business logic
├── telegram/            # Telegram integration
├── utils/               # Utility functions
└── main.py              # FastAPI application entry point
```

### Key Technologies

- **FastAPI**: Modern Python web framework
- **OpenAI**: AI-powered text processing
- **Instaloader**: Instagram content extraction
- **Pydantic**: Data validation and settings
- **SQLite**: Lightweight database
- **jdatetime**: Persian calendar support

### Contributing

We welcome contributions from developers who are passionate about music and technology!

#### 🔧 Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- All the independent artists who keep our hearts warm in this cold.
- OpenAI for providing powerful language processing capabilities
- The Instagram and Telegram communities for their APIs
- Persian calendar (jdatetime) maintainers
- All contributors who help improve Aragorn

---

**Made with ❤️ for the independent music community**

*Aragorn - Connecting music lovers, one event at a time*
