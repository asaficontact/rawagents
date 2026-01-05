"""Basic usage of the Conversation component.

This example demonstrates:
1. Initializing a conversation
2. Adding different types of messages (system, user, assistant)
3. Retrieving the history formatted for LLMs
"""

from ai_components.conversation import Conversation

def main():
    # 1. Initialize
    print("--- 1. Initialize ---")
    conv = Conversation()
    conv.add_system("You are a helpful AI assistant.")
    print("Conversation initialized.")

    # 2. Add Messages
    print("\n--- 2. Add Messages ---")
    
    # Add user message
    user_msg = conv.add_user("Hello! Who are you?")
    print(f"User: {user_msg.content}")

    # Add assistant response
    ai_msg = conv.add_assistant("I am a conversation component demo.")
    print(f"AI: {ai_msg.content}")

    # Add another user message with image (multimodal)
    # Note: In a real app, you'd provide a real URL
    conv.add_user(
        "What is in this image?",
        images=["https://example.com/image.png"]
    )
    print("User added multimodal message.")

    # 3. Get History
    print("\n--- 3. Get History (Formatted for LLM) ---")
    history = conv.get_history()
    print(f"History: {history}")
    
    for i, msg in enumerate(history):
        role = msg["role"]
        content = msg.get("content", "")
        # Truncate long content for display
        if isinstance(content, list):
            display_content = f"[Multimodal: {len(content)} blocks]"
        else:
            display_content = content
            
        print(f"[{i}] {role.upper()}: {display_content}")

if __name__ == "__main__":
    main()

