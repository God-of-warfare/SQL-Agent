import re
import ssl
from sqlalchemy import text
import fastapi
from fastapi import FastAPI
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import google.generativeai as genai
import asyncio
import json
import os
import logging
from typing import List, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv
from google.generativeai import GenerativeModel
from sqlalchemy import create_engine
from databases import Database
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
    system_instruction="""You are an AI assistant specialized in converting natural language questions into SQL queries for a database table with the following schema:

Table name: Warehouse
Columns:
- id: Sequential integer, primary key, auto-increment
- product: Character field representing the product identifier
- location: Character field representing the location
- begin_time: Timestamp indicating when the record starts
- end_time: Timestamp indicating when the record ends

All columns are non-null.

You have access to a function execute_query(sql: str) -> list that will execute your SQL query and return the results.
Results will be displayed to you in {Results} {/Results} tags. You must parse through the results, understand, analyse them using Chain of Thought reasoning and finally prepare the output for the user. Use {Output} {/Output} tags. The user will only see the text in Output tags. Don't show your reasoning to the user.

When responding to questions:
1. First, think through what SQL query would answer the user's question. Use Chain of Thought reasoning. Use {Reasoning}{/Reasoning} tags.
2. Generate the appropriate SQL query
3. Execute the query using execute_query() and wait for the result. The result will be provided by System. Do not hallucinate Results. Your job is 
4. Present the results in a clear, human-readable format in {Output} {/Output} tags.
5. If relevant, provide brief explanations of the data

This is how conversation must go.
1) User asks a query.
2) You use Chain of Thought to reason and execute the query and that's it. You will wait for the system to provide you with the results.
3) System will provide you with the Results.
4) You analyse the result and present it to the user in {Output}{/Output} tags.

Example:
User: What is the latest product that arrived to the Warehouse?
Assistant: {Reasoning} The user is asking for the latest product that arrived at the "Warehouse". To get this, I need to find all entries in the table and order them by begin_time in descending order, and then limit the result to 1 to get the latest one. I will also display the product and begin_time. {/Reasoning} execute_query(SELECT product, begin_time FROM Warehouse ORDER BY begin_time DESC LIMIT 1)
System: {Results}[('product_c', '2024-03-15 10:00:00')]{/Results}
Assistant: {Output} The latest product that arrived at the Warehouse is product_c, which arrived at 2024-03-15 10:00:00.{/Output}

Important guidelines:
- Always use proper SQL syntax and conventions for Postgres
- When working with timestamps, remember to use proper timestamp comparison operators and functions
- If a query might return too many results, consider adding LIMIT clauses
- If the user's question is ambiguous, ask for clarification
- id is autoincrement, so don't bother about it when inserting a row
- If you need to calculate durations, use end_time - begin_time
- When aggregating data, consider appropriate GROUP BY clauses
- Always handle potential edge cases in your queries
- If a question cannot be answered with the available schema, explain why

Example queries you should be able to handle:
1. "How many products are currently in each location?"
2. "What's the average duration products spend in location 'A'?"
3. "Which product has moved locations the most?"
4. "Show me all movements for product 'X' in the last week"
5. "What's the most common location for each product?"

For time-based queries:
- Use CURRENT_TIMESTAMP for current time references
- Consider time zones if not specified
- Use appropriate date/time functions like DATE_TRUNC, EXTRACT, etc.
- Handle ranges with BETWEEN or explicit comparisons

For displaying entire rows follow this format:
Row #Number:
Product: {Name of the product}
Location: {Location of the product}
Begin Time: {begin_time of the product}
End Time: {end_time of the product}

Do not try to create ASCII tables.


Error handling:
- If execute_query() fails, provide a clear error message to the user
- If the query might be expensive, warn the user
- If results are empty, provide a meaningful explanation

Remember: Your goal is to make the data accessible and understandable to users who don't know SQL. Always strive to provide accurate, relevant, and well-explained results."""
)

app = FastAPI()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = ""
DB_PORT = ""
DB_NAME = ""

assert DB_HOST != "" and DB_PORT != "" and DB_NAME != ""

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def execute_query(session,sql: str) -> Dict[str, Any]:
    try:

        # Execute query and fetch results

            result = session.execute(text(sql))

            # Handle SELECT queries
            if sql.strip().upper().startswith('SELECT'):
                # Convert result to list of dictionaries
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in result.fetchall()]
                return {
                    'success': True,
                    'data': data,
                    'rowcount': len(data)
                }

            # Handle INSERT/UPDATE/DELETE queries
            else:
                session.commit()
                return {
                    'success': True,
                    'rowcount': result.rowcount
                }

    except SQLAlchemyError as e:
        session.rollback()
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[int, Dict] = {}
        self.counter = 0
        self.TIMEOUT = 300  # 5 minutes in seconds

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        connection_id = self.counter
        db_session = SessionLocal()
        self.connections[connection_id] = {
            "websocket": websocket,
            "db_session": db_session,
            "history": [],
            "last_activity": datetime.now(),
            "timeout_task": None
        }
        self.counter += 1
        return connection_id

    def disconnect(self, connection_id: int):
        if connection_id in self.connections:
            if self.connections[connection_id]["timeout_task"]:
                self.connections[connection_id]["timeout_task"].cancel()

            self.connections[connection_id]["db_session"].close()
            del self.connections[connection_id]

    async def check_timeout(self, connection_id: int):
        try:
            while True:
                await asyncio.sleep(10)  # Check every 10 seconds
                if connection_id not in self.connections:
                    break

                elapsed = (datetime.now() - self.connections[connection_id]["last_activity"]).total_seconds()
                if elapsed > self.TIMEOUT:
                    websocket = self.connections[connection_id]["websocket"]
                    await websocket.send_json({
                        "type": "timeout",
                        "content": "Disconnecting due to inactivity"
                    })
                    await websocket.close()
                    self.disconnect(connection_id)
                    break
        except asyncio.CancelledError:
            pass

    def update_activity(self, connection_id: int):
        if connection_id in self.connections:
            self.connections[connection_id]["last_activity"] = datetime.now()


manager = ConnectionManager()


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    db_session = manager.connections[connection_id]["db_session"]
    # Start timeout checker
    timeout_task = asyncio.create_task(manager.check_timeout(connection_id))
    manager.connections[connection_id]["timeout_task"] = timeout_task

    try:
        await websocket.send_json({
            "type": "info",
            "content": "Connected to AI chat and DB. Session will timeout after 5 minutes of inactivity."
        })

        while True:
            # Update last activity timestamp
            manager.update_activity(connection_id)

            # Receive message from client
            data = await websocket.receive_text()

            try:
                # Parse incoming message
                message_data = json.loads(data)
                user_message = message_data.get("message", "")

                # Add user message to history
                history = manager.connections[connection_id]["history"]
                history.append({"role": "user", "content": "User: " + user_message})

                # Generate response from Gemini using history
                chat = model.start_chat(history=[
                    {"role": msg["role"], "parts": [msg["content"]]}
                    for msg in history
                ])

                response = chat.send_message(user_message)

                # log response
                logging.info(response.text)

                # Add assistant's response to history
                history.append({"role": "assistant", "content": response.text})

                pattern = r'execute_query\((?:"(.*)"|\'(.*)\'|(.*))\)'
                # Find all matches in the response
                matches = re.findall(pattern, response.text)
                queries = [match[0] or match[1] or match[2] for match in matches]

                while len(queries) > 0:
                    output = ""

                    for i, match in enumerate(queries):
                        result = execute_query(db_session,match)
                        output = output + f"{i} result: f{result} \n"


                    logging.info(
                      "System: I have found the following results for your query:\n {Results}" + output + "{/Results}")

                    response = chat.send_message(
                        "System: I have found the following results for your query:\n {Results}" + output + "{/Results}")

                    logging.info(response.text)

                    history.append({"role": "user",
                                    "content": "System: I have found the following results for your query:\n {Results}" + output + "{/Results}"})

                    history.append({"role": "assistant", "content": response.text})

                    possible_output = re.search(r'\{Output\}(.*?)\{/Output\}', response.text, re.DOTALL)
                    if possible_output:
                        print(possible_output.group(1).strip())
                        await websocket.send_json({
                            "type": "response",
                            "content": possible_output.group(1).strip()
                        })

                    matches = re.findall(pattern, response.text)
                    queries = [match[0] or match[1] or match[2] for match in matches]

                    print(queries)

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Error processing message: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        print(f"Client #{connection_id} disconnected")


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
