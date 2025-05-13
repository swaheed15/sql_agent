import streamlit as st
from pathlib import Path
from langchain.agents import create_sql_agent
from langchain.sql_database import SQLDatabase
from langchain.agents.agent_types import AgentType
from langchain.callbacks import StreamlitCallbackHandler
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from sqlalchemy import create_engine
import sqlite3
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.prompts import MessagesPlaceholder
from langchain.prompts import HumanMessagePromptTemplate
from langchain.prompts import SystemMessagePromptTemplate


st.set_page_config(page_title="SQL Agent", page_icon="🔍", layout="centered")  
st.title("🔍 SQL Agent") 

LOCALDB = "USE_LOCALDB"
MYSQL = "USE_MYSQL"

radio_opt = ["use sqlite3 database _ Student.db", "Connect to MySQL database"]

selected_opt=st.sidebar.radio(label="Select the DB to Chat", options=radio_opt)

if radio_opt.index(selected_opt) == 1:
    db_uri=MYSQL
    mysql_user = st.sidebar.text_input("Please enter the MySQL user")
    mysql_password = st.sidebar.text_input("Please enter the MySQL password", type="password")
    mysql_db = st.sidebar.text_input("Please enter the MySQL database name")
else:
    db_uri=LOCALDB

api_key = st.sidebar.text_input(label="Please enter your Groq API key", type="password")
if not api_key:
    st.warning("Please enter your Groq API key to continue.", icon="⚠️")
    st.stop()

##LLM model
llm = ChatGroq(
    groq_api_key=api_key,
    model="compound-beta",
    temperature=0,
    streaming=True
)

@st.cache_resource(ttl="2h")
def configure_db(db_uri, mysql_user=None, mysql_password=None, mysql_db=None):
    if db_uri == LOCALDB:
        dbfilepath = Path(__file__).parent / "Student.db"
        print(dbfilepath)
        # Creator lambda can be omitted if not required
        return SQLDatabase(create_engine(f"sqlite:///{dbfilepath}"))
    
    elif db_uri == MYSQL:
        if not mysql_user or not mysql_password or not mysql_db:
            st.warning("Please enter MySQL credentials to continue.", icon="⚠️")
            return None  # Instead of st.stop(), return None or handle it accordingly
        connection_string = f"mysql+pymysql://{mysql_user}:{mysql_password}@localhost/{mysql_db}"
        return SQLDatabase(create_engine(connection_string))
    else:
        st.warning("Invalid database URI. Please select a valid option.", icon="⚠️")
        return None

# Main part where the db is configured based on db_uri
if db_uri == MYSQL:
    db = configure_db(db_uri, mysql_user, mysql_password, mysql_db)
    if db is None:
        st.warning("Failed to connect to the MySQL database. Please check your credentials.", icon="⚠️")
        st.stop()
else:
    db = configure_db(db_uri)

## toolkit
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

## agent
agent = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    max_iterations=3,
    return_intermediate_steps=True
)

if "messages" not in st.session_state or st.sidebar.button("Clear chat", key="clear"):
    st.session_state.messages = [{"role": "system", "content": "You are a helpful assistant that can answer questions about the database."}]

for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user").markdown(message["content"])

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
import json
import streamlit as st

user_query = st.chat_input("Ask a question about the database")

# Check if the user has input a query
if user_query:
    # Append the user query to the session state messages
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Construct the prompt with structured output instructions
                prompt = f"""
                You are an AI assistant querying a database. Please follow these steps:
                - List all relevant tables in the database.
                - Provide the schema of the relevant tables.
                - Execute the SQL query to get students with marks less than 50.
                - Return the result as a **valid JSON object** inside a markdown code block.

                Example format:
                ```json
                [
                    {"name": "Jane Doe", "email": "jane@example.com", "mark": 30},
                    {"name": "John Doe", "email": "john@example.com", "mark": 40}
                ]
                ```

                Ensure that:
                - The JSON is **valid** (i.e., keys are quoted with double quotes).
                - The output is **fenced by three backticks** for markdown.
                - **Do not include extra text** outside of the JSON format.
                """

                # Execute the agent (prompting Compound Beta model)
                response = agent(
                    {"input": prompt}, 
                    callbacks=[StreamlitCallbackHandler(st.container())]
                )

                # Parse the response using JsonOutputParser if the output is in JSON markdown format
                message = AIMessage(content=response)  # Simulating model's response
                output_parser = JsonOutputParser()

                # Try parsing the response using the JsonOutputParser
                try:
                    parsed_response = output_parser.invoke(message)
                    st.session_state.messages.append({"role": "assistant", "content": parsed_response})
                    st.chat_message("assistant").markdown(parsed_response)
                except Exception as e:
                    st.error(f"Error processing the JSON response: {e}")

            except Exception as e:
                # Catch any errors during processing and show an error message
                st.error(f"Error processing the query: {e}")

else:
    # If no query is provided, display the last assistant message
    if 'messages' in st.session_state and len(st.session_state.messages) > 0:
        message = st.session_state.messages[-1]["content"]
        st.chat_message("assistant").markdown(message)
