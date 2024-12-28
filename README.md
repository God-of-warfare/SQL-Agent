# Database-Interfacing LLM Agent

A real-time AI agent system that enables natural language interactions with any SQL database. Built with FastAPI, WebSocket, and Google's Gemini AI, this system allows users to query databases using natural language. The example implementation shows integration with a warehouse management database, but the system can be adapted for any database schema by modifying the system prompt.

## Features

- Natural language to SQL conversion using Google's Gemini AI
- Real-time communication using WebSocket
- Flexible database integration (example using PostgreSQL/YugabyteDB)
- Automatic session management with timeout
- Comprehensive error handling and result formatting
- Adaptable to any database schema through system prompt modification

## How It Works

1. The system uses a customizable system prompt that defines:
   - Database schema and structure
   - Query patterns and examples
   - Response formatting rules
   - Error handling guidelines

2. Users send natural language queries through WebSocket
3. Gemini AI converts these queries to SQL based on the system prompt
4. Queries are executed against the database
5. Results are processed and formatted by the AI for human readability

## Prerequisites

- Python 3.8+
- SQL Database (example uses PostgreSQL/YugabyteDB)
- Google Cloud API key for Gemini AI

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key
DB_USER=your_database_username
DB_PASSWORD=your_database_password
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd database-llm-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install fastapi uvicorn google-generativeai sqlalchemy databases python-dotenv websockets
```

## Customizing for Your Database

1. Modify the system prompt in the code:
   - Update the database schema description
   - Adjust example queries
   - Customize response formatting
   - Define domain-specific guidelines

Example system prompt structure:
```python
system_instruction = """
You are an AI assistant specialized in converting natural language questions into SQL queries for a database table with the following schema:

Table name: [Your Table]
Columns:
- [Column 1]: [Description]
- [Column 2]: [Description]
...

Example queries you should be able to handle:
1. [Example 1]
2. [Example 2]
...

[Additional instructions for query handling and response formatting]
"""
```

2. Update database connection settings in the code to match your database configuration

## Running the Application

Start the server with:

```bash
python main.py
```

The application will run on `http://localhost:8000`

## WebSocket API Usage

Connect to the WebSocket endpoint at `/ws/chat` to start interacting with the system.

### Message Format

Send messages in JSON format:
```json
{
    "message": "Your natural language query here"
}
```

### Response Format

Responses will be in JSON format:
```json
{
    "type": "response",
    "content": "AI-formatted response based on database query results"
}
```

## Example Implementation

The included example implements a warehouse management system with the following schema:

```sql
CREATE TABLE Warehouse (
    id SERIAL PRIMARY KEY,
    product VARCHAR NOT NULL,
    location VARCHAR NOT NULL,
    begin_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL
);
```

This can be modified to work with any database structure by updating the system prompt and database connection settings.

## Features Details

### Session Management
- WebSocket connections timeout after 5 minutes of inactivity
- Automatic database session cleanup on disconnect
- Real-time activity tracking

### Error Handling
- SQL query execution error handling
- WebSocket connection error management
- Invalid message format handling

### Query Processing
- Natural language processing using Gemini AI
- SQL query generation and execution
- Result formatting and presentation

## Security Considerations

- Environment variables for sensitive credentials
- Database session management
- Connection timeouts for inactive sessions
- SQL injection prevention through parameterized queries

