"""Context strategy example using SlidingWindow.

This example demonstrates how strategies filter the history sent to the LLM
without modifying the underlying storage.
"""

from ai_components.conversation import Conversation
from ai_components.conversation.strategies import SlidingWindow

def main():
    # Initialize with a small window size of 2 (keeps system + last 2 messages)
    window_size = 2
    strategy = SlidingWindow(window_size=window_size)
    conv = Conversation(strategy=strategy)
    
    conv.add_system("System Prompt")
    
    # Add 5 user/assistant exchanges (10 messages)
    print("Adding 10 messages...")
    for i in range(5):
        conv.add_user(f"Question {i+1}")
        conv.add_assistant(f"Answer {i+1}")

    # 1. Check Storage (Everything is kept)
    all_messages = conv.get_all_messages()
    print(f"\nTotal messages in storage: {len(all_messages)}")
    # Expected: 1 system + 10 chat = 11 messages
    
    # 2. Check Context (Filtered by Strategy)
    context = conv.get_history()
    print(f"Messages in context window: {len(context)}")
    # Expected: 1 system + 2 chat = 3 messages
    
    print("\n--- Content of Context Window ---")
    for msg in context:
        print(f"{msg['role']}: {msg['content']}")
        
    # Verify it's the most recent ones
    last_msg = context[-1]
    assert "Answer 5" in last_msg["content"]
    print("\nSuccess: Context contains only the most recent messages + system prompt.")

if __name__ == "__main__":
    main()

