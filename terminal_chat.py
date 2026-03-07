import os
from google import genai

# --- CONFIGURATION ---
# paste your key below inside the quotes
API_KEY = AIzaSyBPTh9Pe7miMBSM0LH6URM6RHjHHl4O3SM 

# Define your persona here (Work, Comedy, or Dreamer)
SYSTEM_INSTRUCTION = "You are a helpful, concise assistant running in a Windows terminal."

client = genai.Client(api_key=API_KEY)

def start_chat():
    print(f"--- Gemini Terminal // {os.getlogin()} ---")
    print("Type 'quit' or 'exit' to stop.\n")

    # Initialize the chat with the system instruction
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION
        )
    )

    while True:
        try:
            # 1. Get User Input
            user_input = input("You > ")
            if user_input.lower() in ["quit", "exit"]:
                print("Exiting...")
                break
            
            # 2. Send to Gemini
            # (stream=True makes it look like it's typing)
            response = chat.send_message(user_input, config=genai.types.GenerateContentConfig(response_mime_type="text/plain"))
            
            # 3. Print the Response
            print("Gemini > ", end="")
            print(response.text)
            print("-" * 20)

        except Exception as e:
            print(f"\n[ERROR]: {e}")

if __name__ == "__main__":
    start_chat()
    