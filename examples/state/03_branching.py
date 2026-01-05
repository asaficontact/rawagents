"""Branching conversation example (Tree of Thoughts).

This example demonstrates:
1. Forking a conversation into independent branches
2. Developing branches separately
3. Merging a branch back into the main trunk
"""

from ai_components.conversation import Conversation

def main():
    conv = Conversation()
    conv.add_system("You are a creative writer.")
    conv.add_user("Write a story about a robot.")
    
    print("Main trunk initialized.")
    
    # --- Forking ---
    print("\nForking into 2 branches...")
    branch_happy = conv.fork()
    branch_sad = conv.fork()
    
    # Develop Branch A (Happy ending)
    print("Developing Branch A (Happy)...")
    branch_happy.add_user("Make it a happy ending.")
    branch_happy.add_assistant("The robot found a puppy and they lived happily ever after.")
    
    # Develop Branch B (Sad ending)
    print("Developing Branch B (Sad)...")
    branch_sad.add_user("Make it a tragic ending.")
    branch_sad.add_assistant("The robot's battery died alone in the rain.")
    
    # --- Comparison ---
    # Original conversation is untouched
    print(f"\nMain trunk messages: {len(conv)}")
    print(f"Branch A messages: {len(branch_happy)}")
    print(f"Branch B messages: {len(branch_sad)}")
    
    # --- Merging ---
    print("\nMerging Branch A back to main...")
    conv.merge(branch_happy)
    
    print(f"Main trunk messages after merge: {len(conv)}")
    
    print("\n--- Final Story (Main Trunk) ---")
    for msg in conv.get_all_messages():
        if msg.role == "assistant":
            print(f"AI: {msg.content}")

if __name__ == "__main__":
    main()

