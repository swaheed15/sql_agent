import streamlit as st
from pathlib import Path
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain.agents.agent_types import AgentType
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from sqlalchemy import create_engine
import sqlite3
from langchain_groq import ChatGroq
from langchain. prompts import PromptTemplate
from langchain. prompts import MessagesPlaceholder
from langchain. prompts import HumanMessagePromptTemplate
from langchain. prompts import SystemMessagePromptTemplate


st.set_page_config(page_title="SQL Agent", page_icon="🔍", layout="centered")  
st.title("🔍 SQL Agent") 

LOCALDB = "USE_LOCALDB"
MYSQL = "USE_MYSQL"

radio_opt = ["UseSQLite3database _ Student.db", "ConnecttoMySQLdatabase"]

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
    model="gemma2-9b-it",
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
        return_intermediate_steps=True,
        output_parsing_error=True,
        agent_kwargs {"prefix": "You are a helpful assistant that can answer questions about the database."}     
) 

if "messages" not in st.session_state or st. sidebar.button("Clear chat", key="clear"):
    st.session_state.messages = [{"role": "system", "content": "You are a helpful assistant that can answer questions about the database."}]

for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user").markdown(message["content"])

import json
import streamlit as st

user_query = st.chat_input("Ask a question about the database")

# Check if the user has input a query
if user_query:
    # Append the user query to the session state messages
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("assistant"):
        try:
            # Execute the agent with the user's query
            response = agent(
                {"input": user_query}, 
                callbacks=[StreamlitCallbackHandler(st.container())]
            )
        except ValueError as e:
            st.error(f"An error occurred: {str(e)}")
            st.stop()  # Stop execution if an error occurs

        # Check if the response contains a valid final answer
        if isinstance(response, str):
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.chat_message("assistant").markdown(response)
        elif isinstance(response, list):
            formatted_response = ""
            for student in response:
                # Formatting each student's details as a string
                formatted_response += f"Name: {student['name']}, Email: {student['email']}, Mark: {student['mark']}\n"
                    
            # Display the formatted result
            st.session_state.messages.append({"role": "assistant", "content": formatted_response})
            st.chat_message("assistant").markdown(formatted_response)
else:
    # If no query is provided, display the last assistant message
    if 'messages' in st.session_state and len(st.session_state.messages) > 0:
        message = st.session_state.messages[-1]["content"]
        st.chat_message("assistant").markdown(message)
