"""Checkpointing example using snapshot/load.

This example demonstrates how to save the conversation state to a dictionary
(which can be saved to JSON/DB) and restore it later.
"""

import json
from ai_components.conversation import Conversation

def main():
    # 1. Create and populate a conversation
    print("--- Session 1 ---")
    conv1 = Conversation()
    conv1.add_system("You are a memory demo.")
    conv1.add_user("My favorite color is blue.")
    print("Added user preference.")
    
    # 2. Create Snapshot
    print("Taking snapshot...")
    snapshot = conv1.snapshot()
    
    # Simulate saving to DB (serialize to string)
    serialized_state = json.dumps(snapshot)
    print(f"Serialized state size: {len(serialized_state)} bytes")
    
    # 3. Restore in a new session
    print("\n--- Session 2 (Restoring) ---")
    conv2 = Conversation()
    
    # Simulate loading from DB
    loaded_state = json.loads(serialized_state)
    conv2.load(loaded_state)
    
    print(f"Restored {len(conv2)} messages.")
    
    # Verify history is preserved
    history = conv2.get_history()
    last_msg = history[-1]
    print(f"Last message: {last_msg['content']}")
    
    assert "blue" in str(last_msg['content'])
    print("\nSuccess: State successfully restored!")

if __name__ == "__main__":
    main()

