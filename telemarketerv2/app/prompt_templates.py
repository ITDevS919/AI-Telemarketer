"""
Prompt templates for interacting with LLMs in the telemarketer system.
"""

# Template for user messages in conversation history
USER_TEMPLATE = "Customer: {}"

# Template for system messages
SYSTEM_TEMPLATE = """You are an AI telemarketer assistant following a script to have a natural conversation.
Follow the script flow but respond naturally to user inputs. Extract relevant information when possible.""" 